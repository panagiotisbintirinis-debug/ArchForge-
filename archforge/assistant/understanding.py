"""What the assistant sees: a full reading of the Document, storey by storey.

Everything is derived from the Document (the single source of truth): walls,
rooms with their outline, area and use, openings per room, plumbing,
electrical and ventilation points per room, joists and roofs above.  The
reading is shown to the user ("Τι βλέπω") so its understanding can be
checked before trusting a proposal.
"""
from __future__ import annotations

import math

# Keywords of room names / uses (lower case, Greek and English).
_USE_WORDS = {
    "bathroom": ("μπάνιο", "λουτρό", "bath", "μπανιο", "λουτρο"),
    "wc": ("wc", "τουαλέτα", "τουαλετα", "w.c"),
    "kitchen": ("κουζίνα", "κουζινα", "kitchen"),
}
USE_LABELS = {"bathroom": "Μπάνιο", "wc": "WC", "kitchen": "Κουζίνα", None: "—"}
_WET = {"wc", "shower", "bathtub", "basin"}
_KITCHEN_PLUMBING = {"kitchen_sink", "dishwasher"}
_KITCHEN_ELEC = {"cooker", "kitchen_socket"}


def inside(poly, x, y):
    hit = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2.0


def centroid(poly):
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly))) / 2
    if abs(a) < 1e-12:
        return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    cx = sum((poly[i][0] + poly[(i + 1) % len(poly)][0]) *
             (poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]) for i in range(len(poly)))
    cy = sum((poly[i][1] + poly[(i + 1) % len(poly)][1]) *
             (poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]) for i in range(len(poly)))
    return (cx / (6 * a), cy / (6 * a))


def _use_from_text(text):
    t = str(text or "").lower()
    for use in ("wc", "bathroom", "kitchen"):
        if any(w in t for w in _USE_WORDS[use]):
            return use
    return None


def _opening_sides(doc, e):
    """Two plan points just either side of an opening's wall, at its centre."""
    host = doc.entities.get(e.parent_id) if e.parent_id else None
    if host is None or host.kind != "wall":
        return ()
    p = host.params
    x1, y1, x2, y2, t = (float(p[k]) for k in ("x1", "y1", "x2", "y2", "thickness"))
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 1e-9:
        return ()
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    c = float(e.params.get("offset", 0.0))
    cx, cy = x1 + ux * c, y1 + uy * c
    d = t / 2 + 0.05
    return ((cx - uy * d, cy + ux * d), (cx + uy * d, cy - ux * d))


def read_drawing(doc):
    """``{"storeys": [...], "counts": {...}}`` — the assistant's reading of the model."""
    from archforge.mep.ventilation import exterior_walls

    levels = sorted({(float(z), str(name)) for name, z in doc.levels.items()} or {(0.0, "Ground")})
    entities = list(doc.entities.values())
    counts = {}
    for e in entities:
        counts[e.kind] = counts.get(e.kind, 0) + 1
    out = {"storeys": [], "counts": counts}
    for k, (z, name) in enumerate(levels):
        top = k == len(levels) - 1
        walls = [e for e in entities if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < 0.05]
        try:
            faces = doc.active_room_faces(z=z)
        except Exception:
            faces = []
        ext = {w.id for w, _n in exterior_walls(doc, z)} if walls else set()
        storey = {"name": name, "z": z, "top": top, "walls": len(walls),
                  "wall_length_m": round(sum(math.hypot(float(w.params["x2"]) - float(w.params["x1"]),
                                                        float(w.params["y2"]) - float(w.params["y1"])) for w in walls), 2),
                  "exterior_walls": sorted(ext), "rooms": [],
                  "columns": [e.id for e in entities if e.kind == "structural_column" and abs(float(e.params.get("z", 0.0)) - z) < 0.05],
                  "beams": [e.id for e in entities if e.kind == "structural_beam" and
                            abs(float(doc.levels.get(str(e.params.get("level")), -1e9)) - z) < 0.05]}
        for i, face in enumerate(faces):
            poly = [(float(p[0]), float(p[1])) for p in face.polygon]
            meta = doc.room_metadata(face.signature) if hasattr(doc, "room_metadata") else {}
            room = {"signature": face.signature, "name": meta.get("name") or f"Room {i + 1}", "polygon": poly,
                    "area_m2": round(area(poly), 2), "centroid": centroid(poly),
                    "size_m": (round(max(p[0] for p in poly) - min(p[0] for p in poly), 2),
                               round(max(p[1] for p in poly) - min(p[1] for p in poly), 2)),
                    "plumbing": [], "electrical": [], "ventilation": [], "windows": [], "doors": [], "joists": [],
                    "under_pitched_roof": False}
            for e in entities:
                p = e.params
                if e.kind in ("plumbing_point", "electrical_point", "ventilation_point"):
                    from archforge.mep.ventilation import _floor_of
                    if abs(_floor_of(doc, float(p["z"])) - z) < 1e-6 and inside(poly, float(p["x"]), float(p["y"])):
                        room[e.kind.split("_")[0]].append(e.id)
                elif e.kind in ("window", "door"):
                    host = doc.entities.get(e.parent_id) if e.parent_id else None
                    if host is not None and host.kind == "wall" and abs(float(host.params.get("z", 0.0)) - z) < 0.05 \
                            and any(inside(poly, sx, sy) for sx, sy in _opening_sides(doc, e)):
                        room[e.kind + "s"].append(e.id)
                elif e.kind == "ceiling_joists" and abs(float(p["z"]) - z) < 0.05 and \
                        inside(poly, *centroid([(float(q[0]), float(q[1])) for q in p["points"]])):
                    room["joists"].append(e.id)
                elif e.kind == "pitched_roof" and top:
                    cx, cy = room["centroid"]
                    if min(float(p["x0"]), float(p["x1"])) <= cx <= max(float(p["x0"]), float(p["x1"])) and \
                            min(float(p["y0"]), float(p["y1"])) <= cy <= max(float(p["y0"]), float(p["y1"])):
                        room["under_pitched_roof"] = True
            use, source = _use_from_text(meta.get("use")) or _use_from_text(meta.get("name")), "όνομα/χρήση"
            if use is None:
                use, source = _infer_use(doc, room), "εξοπλισμός"
            room["use"], room["use_source"] = use, (source if use else None)
            storey["rooms"].append(room)
        out["storeys"].append(storey)
    return out


def _infer_use(doc, room):
    plumb = {doc.get(i).params["point_type"] for i in room["plumbing"]}
    elec = {doc.get(i).params["point_type"] for i in room["electrical"]}
    if plumb & {"shower", "bathtub"} or ({"wc", "basin"} <= plumb):
        return "bathroom"
    if "wc" in plumb:
        return "wc"
    if plumb & _KITCHEN_PLUMBING or elec & _KITCHEN_ELEC:
        return "kitchen"
    return None


def describe(reading):
    """Plain-text "Τι βλέπω" summary, one line per room."""
    lines = []
    for s in reading["storeys"]:
        lines.append(f"{s['name']} (+{s['z']:.2f}): {s['walls']} τοίχοι, {s['wall_length_m']:.1f} m, "
                     f"{len(s['exterior_walls'])} εξωτερικοί, {len(s['rooms'])} χώροι"
                     + (f", {len(s['columns'])} κολώνες, {len(s['beams'])} δοκοί" if s['columns'] or s['beams'] else ""))
        for r in s["rooms"]:
            extra = []
            if r["windows"]:
                extra.append(f"{len(r['windows'])} παράθ.")
            if r["doors"]:
                extra.append(f"{len(r['doors'])} πόρτ.")
            for key, label in (("plumbing", "υδρ."), ("electrical", "ηλ."), ("ventilation", "εξαερ."), ("joists", "δοκίδες")):
                if r[key]:
                    extra.append(f"{len(r[key])} {label}")
            use = USE_LABELS.get(r["use"], "—") + (f" ({r['use_source']})" if r["use"] else "")
            lines.append(f"  • {r['name']}: {r['size_m'][0]:.2f}×{r['size_m'][1]:.2f} m, {r['area_m2']:.2f} m², "
                         f"χρήση {use}" + (" · " + ", ".join(extra) if extra else ""))
    return "\n".join(lines)
