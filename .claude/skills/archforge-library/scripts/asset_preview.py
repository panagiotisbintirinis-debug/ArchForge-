#!/usr/bin/env python3
"""Verification sheet for a library asset: 3D views + top view + 2D plan symbol.

Use it after every import (Home Designer, online CC0/CC-BY, photo-built) to
compare geometry with the visual result:

  * three shaded 3D views (part colours when the asset has a palette),
  * an orthographic top view of the mesh,
  * the derived 2D plan symbol (outline + height-step lines) drawn over the
    same frame, so plan and 3D can be checked against each other,
  * the measured size (cm) next to the expected size when one is given.

Requires numpy and Pillow (agent tooling; ArchForge itself does not).

Usage:
    python asset_preview.py ASSET_ID|ASSET.json [--expect W,D,H cm] --out sheet.png
"""
import argparse
import json
import os
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4]))
from archforge.library.assets import asset_dir  # noqa: E402

W = 300


def _font(size=13):
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()
LIGHT = np.array([0.35, -0.55, 0.75]) / np.linalg.norm([0.35, -0.55, 0.75])


def _rot(az, el):
    a, e = np.radians(az), np.radians(el)
    rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
    return rx @ rz


def _hex(c):
    return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], float)


def render(v, f, colors, az, el, size=W, scale=None, center=None):
    """Z-buffered flat-shaded render; el=90 gives an orthographic top view."""
    p = (v - (v.mean(0) if center is None else center)) @ _rot(az, el).T
    s = scale or size * 0.42 / max(np.abs(p[:, [0, 2]]).max(), 1e-9)
    X, Y, Z = size / 2 + p[:, 0] * s, size / 2 - p[:, 2] * s, p[:, 1]
    img = np.full((size, size, 3), 246.0)
    zb = np.full((size, size), np.inf)
    for k, tri in enumerate(f):
        x, y, z = X[tri], Y[tri], Z[tri]
        n = np.cross(p[tri[1]] - p[tri[0]], p[tri[2]] - p[tri[0]])
        nn = np.linalg.norm(n)
        if nn == 0:
            continue
        shade = 0.3 + 0.7 * abs(n @ LIGHT) / nn
        x0, x1 = int(max(0, np.floor(x.min()))), int(min(size - 1, np.ceil(x.max())))
        y0, y1 = int(max(0, np.floor(y.min()))), int(min(size - 1, np.ceil(y.max())))
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-12:
            continue
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        m &= zz < sub
        sub[m] = zz[m]
        img[y0:y1 + 1, x0:x1 + 1][m] = colors[k] * shade
    return Image.fromarray(img.clip(0, 255).astype(np.uint8)), s


def load(arg):
    path = pathlib.Path(arg)
    if not path.is_file():
        path = asset_dir() / f"{arg}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def sheet(record, expect=None):
    v = np.array(record["vertices"], float)
    f = np.array(record["triangles"], int)
    if "palette" in record:
        pal = np.array([_hex(c) for c in record["palette"]])
        colors = pal[np.array(record["tri_part"])]
    else:
        colors = np.tile(_hex("#c8bfb0"), (len(f), 1))
    views = [render(v, f, colors, az, el)[0] for az, el in ((-35, 22), (145, 18), (-90, 8))]
    # Top view and symbol share one frame: scale from the footprint.
    half = max(record["size"][0], record["size"][1]) / 2
    scale = W * 0.45 / max(half, 1e-9)
    center = np.array([0.0, 0.0, v[:, 2].mean()])
    top, _ = render(v, f, colors, 0, 90, scale=scale, center=center)
    sym = Image.new("RGB", (W, W), (255, 255, 255))
    d = ImageDraw.Draw(sym)

    def px(q):
        return (W / 2 + q[0] * scale, W / 2 - q[1] * scale)
    for loop in record["plan"]["outline"]:
        d.line([px(q) for q in loop + loop[:1]], fill=(30, 40, 50), width=2)
    for line in record["plan"]["lines"]:
        d.line([px(q) for q in line], fill=(90, 100, 110), width=1)
    overlay = top.copy()
    od = ImageDraw.Draw(overlay)
    for loop in record["plan"]["outline"]:
        od.line([px(q) for q in loop + loop[:1]], fill=(220, 30, 30), width=1)
    out = Image.new("RGB", (W * 3, 2 * W + 60), "white")
    for i, im in enumerate(views):
        out.paste(im, (i * W, 40))
    for i, im in enumerate((top, overlay, sym)):
        out.paste(im, (i * W, W + 60))
    dd = ImageDraw.Draw(out)
    size = [round(c * 100, 1) for c in record["size"]]
    prov = record.get("provenance", {})
    text = f"{record['name']}   measured {size[0]} x {size[1]} x {size[2]} cm"
    if expect:
        text += f"   expected {expect[0]} x {expect[1]} x {expect[2]} cm"
    font, small = _font(14), _font(11)
    dd.text((8, 4), text, fill="black", font=font)
    dd.text((8, 22), f"source: {prov.get('source', '?')}  license: {prov.get('license', '?')}", fill=(80, 80, 80), font=small)
    for i, label in enumerate(("top view (mesh)", "top view + outline (red)", "2D plan symbol")):
        dd.text((i * W + 8, W + 44), label, fill=(80, 80, 80), font=small)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("asset")
    ap.add_argument("--expect", help="expected W,D,H in cm")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    expect = [float(x) for x in a.expect.split(",")] if a.expect else None
    sheet(load(a.asset), expect).save(a.out)
    print(os.path.abspath(a.out))


if __name__ == "__main__":
    main()
