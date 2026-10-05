#!/usr/bin/env python3
"""EXPERIMENTAL: extract triangle meshes from Home Designer 3D symbol records.

Status: hypothesis under test (see references/calib-format.md, "3D symbols").
Reported layout (from analysis of Belwith-Keeler.calib, not yet verified here):

    SymbolData4LibraryObjects.SymbolData contains records starting with CD AB.
    A geometry record holds a uint32 triangle count N, followed by N
    fixed-size records of 162 bytes; the first 72 bytes of each are
    9 little-endian float64 = three (x, y, z) vertices.  Units: inches.

The scanner does not trust fixed offsets.  After every CD AB marker it looks
for a uint32 N whose following N*162 bytes all decode as finite, bounded
coordinates and whose triangles share vertices (a real mesh is connected).
Every accepted block is reported with its offset so the hypothesis can be
checked or refuted object by object.

Output OBJ files are for local format study only (licensed content).

Usage:
    python calib_mesh.py CATALOG.calib|.calibz [--name TEXT] [--ids 1,2] [--limit 5]
                         [--out-dir DIR] [--unit inch|mm|m]
"""
import argparse
import math
import os
import sqlite3
import struct
import sys

import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from calib_open import connect_ro, open_catalog, resolve  # noqa: E402

MARKER = b"\xcd\xab"
STRIDE = 162
SEARCH = 64            # bytes after a marker in which the count may sit
MAX_ABS = 2000.0       # |coordinate| in source units (inches): larger is not furniture geometry
DATA_OFFSET = 24       # verified: records start 24 bytes after the CD AB marker
MIN_TRIANGLES = 4      # 1-3 "triangles" validate by coincidence
UNITS = {"inch": 0.0254, "mm": 0.001, "m": 1.0}


def _triangles_at(blob, start, n):
    end = start + n * STRIDE
    if end > len(blob):
        return None
    tris = []
    for i in range(n):
        vals = struct.unpack_from("<9d", blob, start + i * STRIDE)
        if not all(math.isfinite(v) and abs(v) < MAX_ABS for v in vals):
            return None
        tris.append((vals[0:3], vals[3:6], vals[6:9]))
    return tris


def _connected_enough(tris):
    """Most triangles of a real mesh share at least one vertex with another."""
    if len(tris) < 2:
        return True
    seen = {}
    for t in tris:
        for v in t:
            k = tuple(round(c, 6) for c in v)
            seen[k] = seen.get(k, 0) + 1
    shared = sum(1 for t in tris if any(seen[tuple(round(c, 6) for c in v)] > 1 for v in t))
    return shared >= 0.8 * len(tris)


def find_meshes(blob):
    """Return [(marker_offset, data_offset, triangles)] for every plausible block.

    At each CD AB marker every candidate count in the window is tried and the
    largest block that validates wins: small counts validate by coincidence
    (a few doubles that happen to be finite), the real count explains the data.
    """
    found = []
    pos = 0
    covered_until = -1
    while True:
        m = blob.find(MARKER, pos)
        if m < 0:
            break
        pos = m + 1
        if m < covered_until:
            continue
        best = None
        for k in range(m + 2, min(m + 2 + SEARCH, len(blob) - 4)):
            n = struct.unpack_from("<I", blob, k)[0]
            if not MIN_TRIANGLES <= n <= 5_000_000 or (best and n <= len(best[2])):
                continue
            # Real file: data starts 14 bytes after the count.  Several
            # alignments can decode as finite doubles; the true one shares the
            # most vertices (fewest unique points).
            options = []
            for gap in range(4, 34, 2):
                tris = _triangles_at(blob, k + gap, n)
                if tris and _connected_enough(tris) and _has_extent(tris):
                    options.append((_unique_vertices(tris), k + gap, tris))
            if options:
                # Verified layout puts the records at marker+24; prefer it.
                verified = [o for o in options if o[1] == m + DATA_OFFSET]
                _, start, tris = verified[0] if verified else min(options, key=lambda o: o[0])
                best = (m, start, tris)
        if best:
            found.append(best)
            covered_until = best[1] + len(best[2]) * STRIDE
    return found


def _unique_vertices(tris):
    return len({tuple(round(c, 6) for c in v) for t in tris for v in t})


def _has_extent(tris):
    xs = [v[i] for t in tris for v in t for i in range(3)]
    return max(xs) - min(xs) > 1e-9


def to_obj(tris, scale):
    index, verts, faces = {}, [], []
    for t in tris:
        f = []
        for v in t:
            k = tuple(round(c * scale, 9) for c in v)
            if k not in index:
                index[k] = len(verts) + 1
                verts.append(k)
            f.append(index[k])
        if len(set(f)) == 3:
            faces.append(f)
    lines = [f"v {x:.9g} {y:.9g} {z:.9g}" for x, y, z in verts]
    lines += [f"f {a} {b} {c}" for a, b, c in faces]
    return "\n".join(lines) + "\n", len(verts), len(faces)


def bbox(tris, scale):
    pts = [v for t in tris for v in t]
    lo = [min(p[i] for p in pts) * scale for i in range(3)]
    hi = [max(p[i] for p in pts) * scale for i in range(3)]
    return lo, hi


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("catalog")
    ap.add_argument("--name", help="only objects whose name contains this text")
    ap.add_argument("--ids", help="comma-separated LibraryObjectId values")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--out-dir")
    ap.add_argument("--unit", choices=sorted(UNITS), default="inch")
    a = ap.parse_args(argv)
    conn = open_catalog(a.catalog)
    sql = ("SELECT l.LibraryObjectId, l.Name, l.Type, s.SymbolData FROM LibraryObjects l "
           "JOIN SymbolData4LibraryObjects s USING(LibraryObjectId) WHERE LENGTH(s.SymbolData) > 1000")
    params = []
    if a.ids:
        ids = [int(x) for x in a.ids.split(",")]
        sql += f" AND l.LibraryObjectId IN ({','.join('?' * len(ids))})"
        params += ids
    if a.name:
        sql += " AND l.Name LIKE ?"
        params.append(f"%{a.name}%")
    sql += " ORDER BY l.LibraryObjectId LIMIT ?"
    params.append(a.limit)
    scale = UNITS[a.unit]
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
    for oid, name, typ, blob in conn.execute(sql, params):
        blob = bytes(blob)
        meshes = find_meshes(blob)
        print(f"[{oid}] {name}  type={typ}  SymbolData={len(blob)} bytes  "
              f"markers={blob.count(MARKER)}  mesh blocks={len(meshes)}")
        all_tris = []
        for m, start, tris in meshes:
            lo, hi = bbox(tris, scale)
            size = [h - l for l, h in zip(lo, hi)]
            print(f"    marker@{m} data@{start} triangles={len(tris)} "
                  f"size(m)={size[0]:.4f} x {size[1]:.4f} x {size[2]:.4f}")
            all_tris += tris
        covered = sum(len(t) * STRIDE for _, _, t in meshes)
        print(f"    bytes explained by mesh blocks: {covered / max(1, len(blob)):.0%}")
        if a.out_dir and all_tris:
            text, nv, nf = to_obj(all_tris, scale)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:60]
            path = os.path.join(a.out_dir, f"{oid}_{safe}.obj")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {name} (Home Designer catalog, local study only)\n# unit: metres\n" + text)
            print(f"    wrote {path}  vertices={nv} faces={nf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
