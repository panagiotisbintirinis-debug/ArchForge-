#!/usr/bin/env python3
"""Build an ArchForge-original library object from a primitive spec (cm).

Used for objects modelled from a reference photo: the agent reads the
photo, writes a JSON spec of simple solids in centimetres, builds it, then
compares the verification sheet (asset_preview.py) against the photo and
iterates.  The photo is reference only; it is never stored or shipped.

Spec (JSON):
{
  "name": "Καρέκλα τραπεζαρίας",           # generic name, no brands
  "category": ["Έπιπλα", "Καθίσματα"],
  "expect_cm": [45, 52, 90],                # optional: checked against result
  "parts": [
    {"shape": "box", "min": [0, 0, 43], "max": [45, 45, 47], "color": "#8a6a4a"},
    {"shape": "cylinder", "base": [3, 3, 0], "radius": 1.8, "height": 43, "color": "#5a4632"},
    {"shape": "taper", "base": [3, 3, 0], "r0": 1.5, "r1": 2.2, "height": 43},
    {"shape": "rounded_box", "min": [...], "max": [...], "radius": 4}
  ]
}
Shapes are closed meshes; Z is up.

Usage:
    python build_model.py spec.json [--out sheet.png]
"""
import argparse
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4]))
from archforge.library.assets import store_asset  # noqa: E402

CM = 0.01


def box(lo, hi):
    c = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return [tuple(c[i] for i in t) for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]


def frustum(base, r0, r1, height, segments=20):
    x, y, z = base
    ring = [(math.cos(2 * math.pi * k / segments), math.sin(2 * math.pi * k / segments)) for k in range(segments)]
    lo = [(x + r0 * c, y + r0 * s, z) for c, s in ring]
    hi = [(x + r1 * c, y + r1 * s, z + height) for c, s in ring]
    tris = []
    for k in range(segments):
        n = (k + 1) % segments
        tris += [(lo[k], lo[n], hi[n]), (lo[k], hi[n], hi[k])]
        tris += [((x, y, z), lo[n], lo[k]), ((x, y, z + height), hi[k], hi[n])]
    return tris


def rounded_box(lo, hi, radius, segments=6):
    """Box with vertical edges rounded (cushions, table tops)."""
    r = min(radius, (hi[0] - lo[0]) / 2, (hi[1] - lo[1]) / 2)
    corners = [(hi[0] - r, hi[1] - r, 0), (lo[0] + r, hi[1] - r, 90), (lo[0] + r, lo[1] + r, 180), (hi[0] - r, lo[1] + r, 270)]
    outline = []
    for cx, cy, start in corners:
        for k in range(segments + 1):
            a = math.radians(start + 90 * k / segments)
            outline.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    tris = []
    n = len(outline)
    for k in range(n):
        (ax, ay), (bx, by) = outline[k], outline[(k + 1) % n]
        tris += [((ax, ay, lo[2]), (bx, by, lo[2]), (bx, by, hi[2])), ((ax, ay, lo[2]), (bx, by, hi[2]), (ax, ay, hi[2]))]
        tris += [((cx, cy, lo[2]), (bx, by, lo[2]), (ax, ay, lo[2])), ((cx, cy, hi[2]), (ax, ay, hi[2]), (bx, by, hi[2]))]
    return tris


def build(spec):
    tris, colors = [], []
    for part in spec["parts"]:
        shape = part["shape"]
        if shape == "box":
            t = box(part["min"], part["max"])
        elif shape == "rounded_box":
            t = rounded_box(part["min"], part["max"], part.get("radius", 2))
        elif shape == "cylinder":
            t = frustum(part["base"], part["radius"], part["radius"], part["height"], part.get("segments", 20))
        elif shape == "taper":
            t = frustum(part["base"], part["r0"], part["r1"], part["height"], part.get("segments", 20))
        else:
            raise ValueError(f"unknown shape {shape!r}")
        t = [tuple(tuple(c * CM for c in v) for v in tri) for tri in t]
        tris += t
        colors += [part.get("color", "#c8bfb0")] * len(t)
    return tris, colors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    spec = json.loads(pathlib.Path(a.spec).read_text(encoding="utf-8"))
    tris, colors = build(spec)
    provenance = {"source": "archforge-original", "license": "project",
                  "reference": spec.get("reference", "photo (not stored)"), "redistributable": True}
    asset_id, size = store_asset(spec["name"], tris, provenance, colors=colors, category=spec.get("category"))
    msg = f"{spec['name']}: {asset_id}  {size[0] * 100:.1f} x {size[1] * 100:.1f} x {size[2] * 100:.1f} cm"
    if spec.get("expect_cm"):
        off = [abs(s * 100 - e) for s, e in zip(size, spec["expect_cm"])]
        msg += "  size ok" if max(off) <= 1.0 else f"  SIZE DIFFERS by {max(off):.1f} cm"
    print(msg)
    if a.out:
        from asset_preview import load, sheet
        sheet(load(asset_id), spec.get("expect_cm")).save(a.out)
        print(a.out)


if __name__ == "__main__":
    main()
