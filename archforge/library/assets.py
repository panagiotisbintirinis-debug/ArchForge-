"""Local store of imported library meshes ("assets").

An asset is a static mesh normalised to metres, centred on X/Y with its base
at Z = 0, plus its native size and provenance.  Assets live in the user data
folder, never in the repository or in saved projects: a ``library_object``
entity in the Document only references an asset id and carries its own
placement and size, so the Document stays the design truth and a project
opened on a machine without the asset still loads (with a placeholder box).
"""
import hashlib
import json
import os
import pathlib
import sys


def data_dir():
    """User data folder for ArchForge (override with ARCHFORGE_DATA)."""
    if os.environ.get("ARCHFORGE_DATA"):
        return pathlib.Path(os.environ["ARCHFORGE_DATA"])
    if sys.platform.startswith("win"):
        return pathlib.Path(os.environ.get("APPDATA", pathlib.Path.home())) / "ArchForge"
    return pathlib.Path(os.environ.get("XDG_DATA_HOME", pathlib.Path.home() / ".local/share")) / "ArchForge"


def asset_dir():
    return data_dir() / "library" / "assets"


def normalise(triangles, colors=None):
    """Weld vertices and move the mesh so it is centred on X/Y with base at Z=0.

    Returns (vertices, triangles, size) or, when per-triangle ``colors`` are
    given, (vertices, triangles, size, kept_colors) aligned with the triangles.
    """
    pts = [v for t in triangles for v in t]
    if not pts:
        raise ValueError("asset has no geometry")
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    size = [hi[i] - lo[i] for i in range(3)]
    if min(size) <= 0:
        # Flat items (rugs) get a token thickness so scaling stays defined.
        size = [max(s, 1e-3) for s in size]
    off = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2])
    index, verts, tris, kept = {}, [], [], []
    for n, t in enumerate(triangles):
        face = []
        for v in t:
            k = tuple(round(v[i] - off[i], 7) for i in range(3))
            if k not in index:
                index[k] = len(verts)
                verts.append(list(k))
            face.append(index[k])
        if len(set(face)) == 3:
            tris.append(face)
            if colors is not None:
                kept.append(colors[n])
    if colors is not None:
        return verts, tris, size, kept
    return verts, tris, size


def store_asset(name, triangles, provenance, colors=None, category=None):
    """Normalise and save a mesh with its plan symbol; return (id, size).

    ``colors`` are optional per-triangle hex colours (kept as a palette).  The
    id is a content hash, so importing the same geometry again dedupes.
    """
    from archforge.library.plan_symbol import plan_symbol
    if colors is not None:
        verts, tris, size, kept = normalise(triangles, colors)
    else:
        verts, tris, size = normalise(triangles)
        kept = None
    digest = hashlib.sha1(json.dumps([verts, tris]).encode()).hexdigest()[:16]
    asset_id = f"a{digest}"
    folder = asset_dir()
    folder.mkdir(parents=True, exist_ok=True)
    record = {"id": asset_id, "name": name, "size": size, "vertices": verts,
              "triangles": tris, "provenance": dict(provenance),
              "plan": plan_symbol(verts, tris)}
    if category:
        record["category"] = list(category)
    if kept is not None:
        palette = sorted(set(kept))
        lookup = {c: i for i, c in enumerate(palette)}
        record["palette"] = palette
        record["tri_part"] = [lookup[c] for c in kept]
    (folder / f"{asset_id}.json").write_text(json.dumps(record), encoding="utf-8")
    return asset_id, size


_CACHE = {}


def load_asset(asset_id):
    """Return the asset record, or None when it is not on this machine."""
    if asset_id in _CACHE:
        return _CACHE[asset_id]
    path = asset_dir() / f"{asset_id}.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    _CACHE[asset_id] = record
    return record


def list_assets():
    folder = asset_dir()
    if not folder.is_dir():
        return []
    out = []
    for p in sorted(folder.glob("*.json")):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            out.append({k: r[k] for k in ("id", "name", "size", "provenance")} | {"category": r.get("category", [])})
        except (OSError, ValueError, KeyError):
            continue
    return sorted(out, key=lambda r: r["name"].lower())
