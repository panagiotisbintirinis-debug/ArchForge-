"""Surface patterns of stone and tile finishes (pure geometry, no Qt).

A material preset may carry a ``pattern`` dict (see ``rendering/materials.py``):

    {"type": "rubble" | "ashlar" | "polygonal" | "slab" | "tiles" | "planks" | "speckle" | "grain",
     "unit_w": m, "unit_h": m,      # typical stone / tile size, real metres
                                    # (speckle: grain size of granite / quartz;
                                    #  grain: board length x width of a veneer leaf)
     "joint": m,                    # joint (mortar, grout) width, metres
     "joint_color": "#rrggbb",      # mortar / grout colour
     "offset": 0..1,                # row stagger in units of unit_w (tiles, planks)
     "variation": 0..1,             # tone difference stone to stone
     "veins": 0..1}                 # optional, marble-like veins

``pattern_geometry`` turns it into one repeating period ("tile" of the
texture) in metres: polygons with their colour, plus thin lines (wood grain,
marble veins).  The 3D view (``ui/pbr_viewport.py``) draws that period on a
canvas and repeats it at real size; the materials dialog draws the same
period with QPainter (``ui/pattern_swatch.py``).  One geometry, two painters,
so the swatch shows what the 3D view shows.

Everything is deterministic: the random generator is seeded from the
material id, so a wall looks the same every time the project opens.
Appearance only: no structural or physical claim is made by a pattern.
"""
from __future__ import annotations

import colorsys
import json
import math
import random
import zlib
from functools import lru_cache
from typing import Mapping

PATTERN_TYPES = ("rubble", "ashlar", "polygonal", "slab", "tiles", "planks", "speckle", "grain")

# Greek names of the pattern types (tooltips, dialog).
PATTERN_NAMES = {
    "rubble": "αργολιθοδομή (ακανόνιστες πέτρες)",
    "ashlar": "λαξευτή πέτρα σε στρώσεις",
    "polygonal": "πολυγωνική πέτρα",
    "slab": "πλακοειδής πέτρα σε λεπτές στρώσεις",
    "tiles": "πλακάκια με αρμό",
    "planks": "σανίδες / πλακάκια σανίδας / νερά ξύλου",
    "speckle": "κόκκοι γρανίτη / χαλαζία",
    "grain": "συνεχή νερά ξύλου (επένδυση μελαμίνης)",
}

_MAX_CELLS = 2500          # keeps the 3D payload and the canvas small


def validate_pattern(pattern) -> list[str]:
    """Problems with a pattern dict (empty list = valid)."""
    errors = []
    if not isinstance(pattern, Mapping):
        return ["pattern is not a dict"]
    if pattern.get("type") not in PATTERN_TYPES:
        errors.append(f"unknown type {pattern.get('type')!r}")
    lo_w = 0.001 if pattern.get("type") == "speckle" else 0.01
    for key, lo, hi in (("unit_w", lo_w, 3.0), ("unit_h", min(lo_w, 0.005), 3.0), ("joint", 0.0, 0.08)):
        value = pattern.get(key)
        if not isinstance(value, (int, float)) or not (lo <= float(value) <= hi):
            errors.append(f"{key}={value!r} not in [{lo}, {hi}] m")
    for key in ("offset", "variation", "veins"):
        value = pattern.get(key, 0.0)
        if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
            errors.append(f"{key}={value!r} not in [0, 1]")
    color = pattern.get("joint_color")
    if not (isinstance(color, str) and len(color) == 7 and color.startswith("#")):
        errors.append(f"joint_color={color!r}")
    if not errors and float(pattern["joint"]) >= 0.5 * min(float(pattern["unit_w"]), float(pattern["unit_h"])):
        errors.append("joint wider than half a unit")
    return errors


def pattern_key(material_id: str, pattern: Mapping, color: str) -> str:
    """Stable cache key: same material + same params = same texture."""
    blob = json.dumps({"id": str(material_id), "p": dict(pattern), "c": str(color)}, sort_keys=True)
    return f"{material_id}-{zlib.crc32(blob.encode('utf-8')):08x}"


def pattern_geometry(pattern: Mapping, color: str, seed: str = "") -> dict:
    """One repeating period of the pattern, in metres (see module docstring).

    Returns ``{"type", "width", "height", "joint", "joint_color", "base_color",
    "relief", "noise", "cells": [{"pts": [[x, y], ...], "color": "#.."}],
    "lines": [{"pts": [[x, y], ...], "color": "#..", "width": m}]}``.
    ``y`` grows upwards (along the wall height).  Cells that cross the period
    edge are already repeated on the other side, so a painter only fills them.
    """
    blob = json.dumps(dict(pattern), sort_keys=True)
    return json.loads(_geometry_json(blob, str(color), str(seed)))


@lru_cache(maxsize=256)
def _geometry_json(blob: str, color: str, seed: str) -> str:
    p = json.loads(blob)
    rng = random.Random(zlib.crc32(f"{seed}|{blob}|{color}".encode("utf-8")))
    kind = p["type"]
    builder = {
        "tiles": _tiles, "planks": _tiles, "ashlar": _ashlar, "slab": _slab,
        "rubble": _voronoi_stones, "polygonal": _voronoi_stones, "speckle": _speckle,
        "grain": _wood_grain,
    }[kind]
    width, height, cells, lines = builder(p, color, rng)
    if float(p.get("veins", 0.0)) > 0:
        lines += _veins(p, color, rng, width, height)
    cells = _wrapped(cells, width, height)
    out = {
        "type": kind,
        "width": round(width, 5),
        "height": round(height, 5),
        "joint": float(p["joint"]),
        "joint_color": str(p["joint_color"]),
        "base_color": color,
        # Stone stands out of its mortar; tiles are almost flush.
        "relief": _relief(p),
        "noise": {"rubble": 0.07, "polygonal": 0.06, "ashlar": 0.05, "slab": 0.06}.get(kind, 0.02),
        "cells": [{"pts": [[round(x, 5), round(y, 5)] for x, y in pts], "color": c} for pts, c in cells],
        "lines": [{"pts": [[round(x, 5), round(y, 5)] for x, y in pts], "color": c, "width": round(w, 5)}
                  for pts, c, w in lines],
    }
    return json.dumps(out, separators=(",", ":"))


def _relief(p) -> float:
    """How far units stand out of their joints (0..1), drives shadow and bump.

    Stone stands proud of its mortar; brick and pavers with a wide mortar
    joint a little; tiles are almost flush, and small ones (mosaic) flatter
    still, so the bump does not shimmer at a distance.
    """
    kind = p["type"]
    if kind in ("speckle", "grain") or float(p["joint"]) <= 0.0:
        return 0.0                      # one flush surface (decor paper, polished slab)
    if kind in ("rubble", "slab"):
        return 1.0
    if kind in ("polygonal", "ashlar"):
        return 0.8 if kind == "polygonal" else 0.7
    if float(p["joint"]) >= 0.008:
        return 0.6
    return round(0.35 * min(1.0, min(float(p["unit_w"]), float(p["unit_h"])) / 0.15), 3)


# ---------------------------------------------------------------- colours --

def _rgb(hex_color: str):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb)


def shade(hex_color: str, light: float = 0.0, hue: float = 0.0, sat: float = 0.0) -> str:
    """``hex_color`` with lightness scaled by (1 + light), hue/saturation nudged."""
    h, l, s = colorsys.rgb_to_hls(*_rgb(hex_color))
    l = min(0.97, max(0.03, l * (1.0 + light)))
    s = min(1.0, max(0.0, s * (1.0 + sat)))
    return _hex(colorsys.hls_to_rgb((h + hue) % 1.0, l, s))


def _cell_color(base: str, rng: random.Random, variation: float, stone: bool) -> str:
    light = rng.gauss(0.0, 0.55 * variation)
    light = max(-1.6 * variation, min(1.6 * variation, light))
    hue = rng.uniform(-1, 1) * (0.035 if stone else 0.01) * variation
    sat = rng.uniform(-1, 1) * (0.6 if stone else 0.2) * variation
    if stone and rng.random() < 0.12:
        # Now and then a stone of a clearly different tone (rust, grey, cream).
        hue += rng.choice((-0.02, 0.015, 0.025))
        sat += rng.choice((0.2, -0.3))
        light += rng.choice((-0.7, 0.5)) * variation
    return shade(base, light, hue, sat)


# --------------------------------------------------------------- polygons --

def _rect(x0, y0, x1, y1, inset):
    return [(x0 + inset, y0 + inset), (x1 - inset, y0 + inset), (x1 - inset, y1 - inset), (x0 + inset, y1 - inset)]


def _clip(poly, a, b, c):
    """Keep the part of ``poly`` with a*x + b*y <= c (Sutherland-Hodgman)."""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        dp = a * p[0] + b * p[1] - c
        dq = a * q[0] + b * q[1] - c
        if dp <= 0:
            out.append(p)
        if (dp < 0 < dq) or (dq < 0 < dp):
            t = dp / (dp - dq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def _area(poly):
    return 0.5 * sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))


def _inset_convex(poly, d):
    """Convex polygon shrunk by ``d`` on every edge (exact for convex)."""
    if _area(poly) < 0:
        poly = poly[::-1]
    out = list(poly)
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        ex, ey = x1 - x0, y1 - y0
        length = math.hypot(ex, ey)
        if length < 1e-9:
            continue
        nx, ny = ey / length, -ex / length     # outward normal of a CCW polygon
        out = _clip(out, nx, ny, nx * x0 + ny * y0 - d)
        if len(out) < 3:
            return []
    return out


def _chaikin(poly, rounds=2):
    for _ in range(rounds):
        nxt = []
        for i in range(len(poly)):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
            nxt.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            nxt.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        poly = nxt
    return poly


def _chamfer(poly, d):
    """Corners cut by ``d`` (hand-dressed arrises), polygon stays inside."""
    out = []
    n = len(poly)
    for i in range(n):
        (px, py), (x, y), (qx, qy) = poly[i - 1], poly[i], poly[(i + 1) % n]
        for ax, ay in ((px, py), (qx, qy)):
            length = math.hypot(ax - x, ay - y)
            t = min(0.45, d / length) if length > 1e-9 else 0.0
            out.append((x + t * (ax - x), y + t * (ay - y)))
    return out


def _roughen(poly, rng, amount):
    """Irregular rubble outline: edge midpoints pushed in by up to ``amount``."""
    cx = sum(x for x, _ in poly) / len(poly)
    cy = sum(y for _, y in poly) / len(poly)
    out = []
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        out.append((x0, y0))
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        dx, dy = cx - mx, cy - my
        dist = math.hypot(dx, dy)
        if dist > 1e-9 and math.hypot(x1 - x0, y1 - y0) > 2 * amount:
            k = min(rng.uniform(0.0, amount), 0.3 * dist) / dist
            out.append((mx + k * dx, my + k * dy))
    return out


def _wrapped(cells, width, height):
    """Repeat cells that stick out of [0,W]x[0,H] on the opposite side."""
    out = []
    for pts, color in cells:
        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        for dx in (-width, 0.0, width):
            if max(xs) + dx <= 0 or min(xs) + dx >= width:
                continue
            for dy in (-height, 0.0, height):
                if max(ys) + dy <= 0 or min(ys) + dy >= height:
                    continue
                out.append(([(x + dx, y + dy) for x, y in pts], color))
    return out


def _period(unit, lo=0.5, hi=1.2):
    """A period of whole units about lo..hi metres (at least two units)."""
    target = max(2 * unit, min(hi, max(lo, 12 * unit)))
    return max(2, round(target / unit))


# ---------------------------------------------------------------- builders --

def _tiles(p, color, rng):
    uw, uh = float(p["unit_w"]), float(p["unit_h"])
    joint = float(p["joint"])
    offset = float(p.get("offset", 0.0)) % 1.0
    variation = float(p.get("variation", 0.05))
    cols = _period(uw)
    rows = _period(uh)
    if offset > 1e-6:
        # Rows needed before the stagger comes back to zero (0.5 -> 2, 1/3 -> 3).
        repeat = next((r for r in range(1, 9) if abs(r * offset - round(r * offset)) < 1e-3), 4)
        rows = max(repeat, int(math.ceil(rows / repeat)) * repeat)
    while cols * rows > _MAX_CELLS:
        cols = max(2, cols // 2)
        rows = max(2, rows // 2)
    width, height = cols * uw, rows * uh
    cells, lines = [], []
    planks = p["type"] == "planks"
    for r in range(rows):
        shift = ((r * offset) % 1.0) * uw
        for c in range(cols):
            x0 = c * uw + shift
            y0 = r * uh
            tone = _cell_color(color, rng, variation, stone=False)
            cells.append((_rect(x0, y0, x0 + uw, y0 + uh, joint / 2.0), tone))
            if planks:
                lines += _grain(x0 + joint, y0 + joint, x0 + uw - joint, y0 + uh - joint, tone, rng)
    return width, height, cells, _wrap_lines(lines, width, height)


def _grain(x0, y0, x1, y1, tone, rng):
    """A few long wavy streaks along a plank (wood-look)."""
    out = []
    horizontal = (x1 - x0) >= (y1 - y0)
    length = (x1 - x0) if horizontal else (y1 - y0)
    across = (y1 - y0) if horizontal else (x1 - x0)
    for _ in range(rng.randint(3, 6)):
        c = rng.uniform(0.1, 0.9) * across
        amp = rng.uniform(0.02, 0.12) * across
        phase = rng.uniform(0, 6.28)
        waves = rng.uniform(0.5, 2.0)
        pts = []
        for k in range(13):
            t = k / 12.0
            d = c + amp * math.sin(phase + waves * 6.28 * t)
            pts.append((x0 + t * length, y0 + d) if horizontal else (x0 + d, y0 + t * length))
        out.append((pts, shade(tone, rng.choice((-0.16, -0.10, 0.08))), rng.uniform(0.0015, 0.004)))
    return out


def _wrap_lines(lines, width, height):
    out = []
    for pts, color, w in lines:
        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        for dx in (-width, 0.0, width):
            if max(xs) + dx < 0 or min(xs) + dx > width:
                continue
            for dy in (-height, 0.0, height):
                if max(ys) + dy < 0 or min(ys) + dy > height:
                    continue
                out.append(([(x + dx, y + dy) for x, y in pts], color, w))
    return out


def _courses(p, rng, heights, lengths, width_target, height_target):
    """Rows of stones: list of (y0, h, [(x0, x1), ...]) with the row wrapping in x."""
    uw = float(p["unit_w"])
    n = max(2, round(width_target / uw))
    width = n * uw
    rows = []
    y = 0.0
    while y < height_target - 1e-9:
        h = heights()
        if y + h > height_target:
            h = height_target - y if height_target - y > 0.5 * h else h
        rows.append((y, h))
        y += h
    # Snap the period height to the rows so the pattern repeats exactly.
    height = y
    out = []
    for y0, h in rows:
        start = rng.uniform(0, width)
        xs = [start]
        while xs[-1] - start < width - 1e-9:
            xs.append(xs[-1] + lengths())
        # Close the row exactly at one period; avoid a sliver stone.
        xs[-1] = start + width
        if xs[-1] - xs[-2] < 0.35 * uw and len(xs) > 2:
            xs.pop(-2)
        out.append((y0, h, list(zip(xs[:-1], xs[1:]))))
    return width, height, out


def _ashlar(p, color, rng):
    uw, uh = float(p["unit_w"]), float(p["unit_h"])
    joint = float(p["joint"])
    variation = float(p.get("variation", 0.2))
    width, height, rows = _courses(
        p, rng,
        heights=lambda: uh * rng.choice((0.75, 1.0, 1.0, 1.25)),
        lengths=lambda: uw * rng.uniform(0.6, 1.6),
        width_target=max(2.4, 5 * uw), height_target=max(1.6, 6 * uh),
    )
    cells = []
    for y0, h, spans in rows:
        for x0, x1 in spans:
            pts = _rect(x0, y0, x1, y0 + h, joint / 2.0)
            # Hand-dressed arrises: corners slightly cut.
            pts = _chamfer(pts, min(0.12 * h, 0.012)) if rng.random() < 0.7 else pts
            cells.append((pts, _cell_color(color, rng, variation, stone=True)))
    return width, height, cells, []


def _slab(p, color, rng):
    """Thin stacked slabs (ledgestone): long, low, with ragged beds."""
    uw, uh = float(p["unit_w"]), float(p["unit_h"])
    joint = float(p["joint"])
    variation = float(p.get("variation", 0.25))
    width, height, rows = _courses(
        p, rng,
        heights=lambda: uh * rng.uniform(0.45, 1.7),
        lengths=lambda: uw * rng.uniform(0.35, 1.9),
        width_target=max(1.6, 4 * uw), height_target=max(1.2, 14 * uh),
    )
    cells = []
    for y0, h, spans in rows:
        for x0, x1 in spans:
            inset = joint / 2.0
            ragged = 0.18 * h
            bottom = [(x0 + inset, y0 + inset + rng.uniform(0, ragged))]
            top = [(x1 - inset, y0 + h - inset - rng.uniform(0, ragged))]
            steps = max(1, int((x1 - x0) / (0.6 * uw)))
            for k in range(1, steps + 1):
                t = k / (steps + 1)
                bottom.append((x0 + t * (x1 - x0), y0 + inset + rng.uniform(0, ragged)))
            bottom.append((x1 - inset, y0 + inset + rng.uniform(0, ragged)))
            for k in range(steps, 0, -1):
                t = k / (steps + 1)
                top.append((x0 + t * (x1 - x0), y0 + h - inset - rng.uniform(0, ragged)))
            top.append((x0 + inset, y0 + h - inset - rng.uniform(0, ragged)))
            cells.append((bottom + top, _cell_color(color, rng, variation, stone=True)))
    return width, height, cells, []


def _voronoi_stones(p, color, rng):
    """Rubble (rounded, roughly coursed) or polygonal (straight-edged) stones."""
    uw, uh = float(p["unit_w"]), float(p["unit_h"])
    joint = float(p["joint"])
    variation = float(p.get("variation", 0.25))
    rubble = p["type"] == "rubble"
    cols = max(3, round(max(1.6, 5 * uw) / uw))
    rows = max(3, round(max(1.6, 6 * uh) / uh))
    width, height = cols * uw, rows * uh
    seeds = []
    for r in range(rows):
        row_shift = rng.uniform(0, uw)
        for c in range(cols):
            jx = rng.uniform(-0.38, 0.38) * uw
            jy = rng.uniform(-0.18 if rubble else -0.32, 0.18 if rubble else 0.32) * uh
            x = (c * uw + row_shift + jx) % width
            y = (r * uh + 0.5 * uh + jy) % height
            seeds.append((x, y))
    # Rubble courses: stones wider than tall (measure distances with y stretched).
    sx, sy = 1.0, (uw / uh if rubble else 1.0)
    copies = [((x + dx) * sx, (y + dy) * sy, i)
              for i, (x, y) in enumerate(seeds)
              for dx in (-width, 0.0, width) for dy in (-height, 0.0, height)]
    reach = 2.6 * max(uw * sx, uh * sy)
    cells = []
    for i, (x, y) in enumerate(seeds):
        px, py = x * sx, y * sy
        poly = [(px - reach, py - reach), (px + reach, py - reach), (px + reach, py + reach), (px - reach, py + reach)]
        for qx, qy, j in copies:
            if j == i and abs(qx - px) < 1e-9 and abs(qy - py) < 1e-9:
                continue
            dx, dy = qx - px, qy - py
            if abs(dx) > 2 * reach or abs(dy) > 2 * reach:
                continue
            mx, my = (px + qx) / 2.0, (py + qy) / 2.0
            poly = _clip(poly, dx, dy, dx * mx + dy * my)
            if len(poly) < 3:
                break
        if len(poly) < 3:
            continue
        poly = [(u / sx, v / sy) for u, v in poly]
        # Mortar: rubble joints vary along the stone, polygonal ones are even.
        poly = _inset_convex(poly, joint / 2.0 * (rng.uniform(0.8, 1.4) if rubble else 1.0))
        if len(poly) < 3:
            continue
        if rubble:
            poly = _chaikin(_roughen(poly, rng, 0.06 * min(uw, uh)), 1)
        cells.append((poly, _cell_color(color, rng, variation, stone=True)))
    return width, height, cells, []


def _mix(color: str, other: str, t: float) -> str:
    a, b = _rgb(color), _rgb(other)
    return _hex(tuple(x + (y - x) * t for x, y in zip(a, b)))


def _speckle(p, color, rng):
    """Granite / quartz / stone-look decor: one slab with many small grains.

    ``unit_w`` is the typical grain size; ``variation`` sets how strongly the
    grains differ from the base (quartz faint, salt-and-pepper granite strong)
    and how much of the surface they cover.
    """
    grain = float(p["unit_w"])
    variation = float(p.get("variation", 0.3))
    period = max(0.15, min(0.5, 60 * grain))
    cells = [(_rect(0.0, 0.0, period, period, 0.0), color)]
    coverage = 0.18 + 0.45 * variation
    count = int(min(2200, coverage * period * period / (math.pi * (0.5 * grain) ** 2)))
    dark = _mix(color, "#0b0b0c", 0.25 + 0.65 * variation)
    light = _mix(color, "#f7f6f2", 0.20 + 0.70 * variation)
    mid = shade(color, 0.0, rng.uniform(-0.02, 0.02), 0.5 * variation)
    for _ in range(count):
        x, y = rng.uniform(0, period), rng.uniform(0, period)
        r = 0.5 * grain * rng.uniform(0.45, 1.35)
        sides = rng.randint(5, 7)
        start = rng.uniform(0, 6.28)
        pts = [(x + r * rng.uniform(0.6, 1.0) * math.cos(start + 6.283 * k / sides),
                y + r * rng.uniform(0.6, 1.0) * math.sin(start + 6.283 * k / sides)) for k in range(sides)]
        pick = rng.random()
        tone = dark if pick < 0.45 else (light if pick < 0.8 else mid)
        cells.append((pts, shade(tone, rng.uniform(-0.08, 0.08))))
    return period, period, cells, []


def _wood_grain(p, color, rng):
    """Continuous wood decor (melamine board): leaves of veneer side by side,
    long fine streaks along the board and a few cathedral arches; no butt
    joints, since a board shows one sheet of decor paper."""
    length, leaf = float(p["unit_w"]), float(p["unit_h"])
    variation = float(p.get("variation", 0.05))
    leaves = max(3, round(0.6 / leaf))
    width, height = length, leaves * leaf
    cells, lines = [], []
    for k in range(leaves):
        y0 = k * leaf
        tone = _cell_color(color, rng, variation, stone=False)
        cells.append((_rect(0.0, y0, width, y0 + leaf, 0.0), tone))
        # Straight-grain streaks: whole sine waves over the period, so they wrap.
        for _ in range(rng.randint(7, 12)):
            c = y0 + rng.uniform(0.04, 0.96) * leaf
            amp = rng.uniform(0.01, 0.05) * leaf
            waves = rng.randint(1, 3)
            phase = rng.uniform(0, 6.28)
            pts = [(width * t / 40.0, c + amp * math.sin(phase + waves * 6.2832 * t / 40.0)) for t in range(41)]
            lines.append((pts, shade(tone, rng.choice((-0.18, -0.12, -0.07, 0.07))), rng.uniform(0.0006, 0.0018)))
        # Flat-sawn leaves: nested arches (the «cathedral» figure).
        if rng.random() < 0.5:
            cx = rng.uniform(0.1, 0.9) * width
            span = rng.uniform(0.25, 0.5) * width
            for n in range(rng.randint(3, 5)):
                half = 0.5 * leaf * (0.85 - 0.15 * n)
                if half <= 0:
                    break
                tip = cx + span * (0.5 - 0.1 * n)
                pts = []
                for t in range(25):
                    u = -1.0 + 2.0 * t / 24.0               # across the leaf
                    pts.append((tip - span * u * u, y0 + 0.5 * leaf + half * u))   # parabola, tip at ``tip``
                lines.append((pts, shade(tone, -0.16), rng.uniform(0.0008, 0.0016)))
    return width, height, cells, _wrap_lines(lines, width, height)


def _veins(p, color, rng, width, height):
    """Soft meandering veins across the period (marble look)."""
    amount = float(p.get("veins", 0.0))
    lines = []
    h, l, s = colorsys.rgb_to_hls(*_rgb(color))
    vein = shade(color, -0.28 if l > 0.4 else 0.9, 0.0, -0.3)
    for _ in range(max(1, round(4 * amount * max(width, height)))):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        angle = rng.uniform(-0.9, 0.9) + (0 if rng.random() < 0.5 else math.pi / 2)
        pts = [(x, y)]
        step = 0.03 * max(width, height)
        for _k in range(24):
            angle += rng.uniform(-0.35, 0.35)
            x += step * math.cos(angle)
            y += step * math.sin(angle)
            pts.append((x, y))
        # Whole-slab veins (worktops, 3 m slabs) are broader than a tile's.
        lines.append((pts, vein, rng.uniform(0.0012, 0.004) * max(1.0, max(width, height) / 2.4)))
    return _wrap_lines(lines, width, height)
