#!/usr/bin/env python3
"""Extract polygon meshes from Home Designer 3D symbol records (local study only).

Layout (verified 2026-10-05 on Belwith-Keeler handles and a Bonus grouped
living room; see references/calib-format.md, "3D symbols"):

    SymbolData4LibraryObjects.SymbolData is a series of records that start
    with CD AB <uint16 record type>.  A mesh record is type 0x0074:

      +0   CD AB 74 00
      +4   uint16 version (B2 0B, AF 08 seen)
      +6   FF FF FF FF
      +10  uint32 P                      polygon count
      +14  P polygon records, back to back, variable length:
             uint16 n                    vertex count (3, 4, 5, ...)
             uint16 flags
             uint32 surface index?       (0, 1, 2, ... seen)
             uint16 ?
             n x 3 float64               vertices (x, y, z), inches
             n x int32                   neighbour polygon per edge (-1 = open)
             uint32 k                    UV pair count (0 or n)
             k x 2 float64               UV pairs
             2 float64                   texture scale? (20.0, 20.0 seen)

The parser walks the records exactly; a mesh is accepted only if all P
polygons parse with finite, bounded coordinates.  Polygons are fan-
triangulated for OBJ output.  Each mesh is written as its own OBJ object, in
its local coordinates (placement of parts inside grouped objects is not
decoded yet).

Output OBJ files are licensed Home Designer content: local format study only.

Usage:
    python calib_mesh.py CATALOG.calib|.calibz [--name TEXT] [--ids 1,2] [--limit 5]
                         [--out-dir DIR] [--unit inch|mm|m]
"""
import argparse
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calib_open import open_catalog  # noqa: E402

from archforge.library.hd_calib import (  # noqa: E402
    MAX_ABS, MAX_INDEX, MAX_VERTS, MESH_RECORD, find_meshes, parse_mesh_record, triangulate)

MARKER = b"\xcd\xab"
UNITS = {"inch": 0.0254, "mm": 0.001, "m": 1.0}


def bbox(points, scale):
    lo = [min(p[i] for p in points) * scale for i in range(3)]
    hi = [max(p[i] for p in points) * scale for i in range(3)]
    return lo, hi


def to_obj(parts, scale):
    """parts: [(name, triangles)] -> OBJ text with one object per part."""
    index, verts, body, nf = {}, [], [], 0
    for name, tris in parts:
        body.append(f"o {name}")
        for t in tris:
            f = []
            for v in t:
                k = tuple(round(c * scale, 9) for c in v)
                if k not in index:
                    index[k] = len(verts) + 1
                    verts.append(k)
                f.append(index[k])
            if len(set(f)) == 3:
                body.append(f"f {f[0]} {f[1]} {f[2]}")
                nf += 1
    lines = [f"v {x:.9g} {y:.9g} {z:.9g}" for x, y, z in verts] + body
    return "\n".join(lines) + "\n", len(verts), nf


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
              f"records={blob.count(MARKER)}  meshes={len(meshes)}")
        parts = []
        for m, polys, complete in meshes:
            lo, hi = bbox([v for pl in polys for v in pl], scale)
            size = [h - l for l, h in zip(lo, hi)]
            state = "" if complete else "  INCOMPLETE (truncated or undecoded)"
            print(f"    mesh@{m} polygons={len(polys)} "
                  f"size(m)={size[0]:.3f} x {size[1]:.3f} x {size[2]:.3f}{state}")
            if complete:
                parts.append((f"mesh_{m}", triangulate(polys)))
        if a.out_dir and parts:
            text, nv, nf = to_obj(parts, scale)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:60]
            path = os.path.join(a.out_dir, f"{oid}_{safe}.obj")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {name} (Home Designer catalog, local study only)\n"
                        f"# unit: metres; each 'o' is one mesh record in its local coordinates\n" + text)
            print(f"    wrote {path}  vertices={nv} triangles={nf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
