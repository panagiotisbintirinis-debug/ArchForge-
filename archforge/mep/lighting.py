"""Luminaires as one thing: construction + electricity + light effect (owner, 2026-10-15).

A luminaire is an ``electrical_point`` of the lighting group (light, spot,
downlight, wall washer, wall light, LED strip).  The same entity carries

* **ουσία** — its load (W, or W/m × length for a strip), circuit, switch or
  dimmer, automation group and cable route (``mep/electrical.py``);
* **ομορφιά** — lumen, Kelvin, beam, aim, direction, dim level, read here by
  ``light_spec`` for the renderer (night scenes) so the picture and the
  installation never disagree;
* **κατασκευή** — where it sits: a strip inside the cove of a plasterboard
  ceiling (``drywall_ceiling`` with ``cove``) sits on the low band behind the
  upstand and throws its light up into the slot; it follows the ceiling when
  its drop or cove changes.

Photometric defaults are typical catalogue values, stated so they can be
replaced by the luminaire's data sheet; nothing here is a lighting study.
"""
from __future__ import annotations

import math

from archforge.mep.electrical import (POINT_TYPES, STRIP_W_PER_M, electrical_points, point_load_w, route_cables_cached,
                                      strip_length)

PROVENANCE = ("Φωτομετρικές τιμές: τυπικές τιμές καταλόγου (lm, K, δέσμη) — αντικαταστήστε από το φύλλο του φωτιστικού· "
              "ταινία LED 9,6 W/m, ≈ 90 lm/W· τροφοδοτικό με 20 % περιθώριο (οδηγίες κατασκευαστών)· όχι φωτοτεχνική μελέτη")

# type: lumen (per metre for strips), Kelvin, beam (°), default direction
PHOTOMETRY = {
    "light": (800.0, 3000.0, 120.0, "down"),
    "spot": (500.0, 3000.0, 36.0, "down"),
    "downlight": (800.0, 3000.0, 60.0, "down"),
    "wall_washer": (700.0, 3000.0, 90.0, "wall"),
    "wall_light": (400.0, 2700.0, 120.0, "both"),
    "led_strip": (STRIP_W_PER_M * 90.0, 3000.0, 120.0, "down"),
}
BEAM_PRESETS = (10.0, 24.0, 36.0, 60.0)
DIRECTIONS = ("down", "up", "wall", "both")
DRIVER_MARGIN = 1.20
COVE_SET_BACK = 0.05       # strip this far in front of the upstand, on the low band


def is_luminaire(entity):
    return entity.kind == "electrical_point" and entity.params.get("point_type") in PHOTOMETRY


def _cove_of(doc, x, y, floor):
    """(ceiling entity, board level z, band?) of a plasterboard ceiling over (x, y) on that storey, or None."""
    from archforge.construction.drywall import BOARD_THICKNESS, ceiling_level, inner_outline, outline
    from archforge.mep.electrical import _floor_of
    for e in doc.entities.values():
        if e.kind != "drywall_ceiling" or abs(_floor_of(doc, float(e.params["level_z"])) - floor) > 1e-4:
            continue
        try:
            poly = outline(doc, e)
            level = ceiling_level(doc, e.params)
        except Exception:
            continue
        if not poly or not _inside(poly, x, y):
            continue
        board = float(e.params["level_z"]) + level
        t = BOARD_THICKNESS * int(e.params.get("layers", 1))
        inner = inner_outline(poly, float(e.params.get("cove_width", 0.30))) if int(e.params.get("cove", 0)) else None
        if inner is not None and not _inside(inner, x, y):
            return e, board + t, True                              # on the low band, in the slot
        return e, board + (float(e.params.get("cove_depth", 0.10)) if inner is not None else 0.0), False
    return None


def _inside(poly, x, y):
    inside = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def ceiling_mount_z(doc, params, floor, slab_ceiling):
    """Height of a ceiling luminaire: in the plasterboard ceiling (or its cove) when there is one, else the slab."""
    x, y = float(params["x"]), float(params["y"])
    if params.get("point_type") == "led_strip":
        x = (x + float(params.get("x2", x))) / 2
        y = (y + float(params.get("y2", y))) / 2
    found = _cove_of(doc, x, y, floor)
    return found[1] if found else slab_ceiling


def direction_of(doc, entity):
    p = entity.params
    if p.get("direction") in DIRECTIONS:
        return p["direction"]
    if p["point_type"] == "led_strip":
        from archforge.mep.electrical import _floor_of
        floor = _floor_of(doc, float(p["z"]))
        mx, my = (float(p["x"]) + float(p.get("x2", p["x"]))) / 2, (float(p["y"]) + float(p.get("y2", p["y"]))) / 2
        found = _cove_of(doc, mx, my, floor)
        if found and found[2]:
            return "up"                                             # indirect: into the cove slot
    return PHOTOMETRY[p["point_type"]][3]


def lumen_of(params):
    lm = float(params.get("lumen", PHOTOMETRY[params["point_type"]][0]))
    return lm * strip_length(params) if params["point_type"] == "led_strip" else lm


def light_spec(doc, entity):
    """The renderer's view of one luminaire (same entity as the electrical point), or None.

    ``intensity`` is in candela for physically based lights: spot cone
    I = Φ / (2π(1 − cos(β/2))), isotropic point I = Φ / 4π, a strip into a
    half space I = Φ / 2π; all scaled by ``dim_level``.
    """
    if not is_luminaire(entity):
        return None
    from archforge.mep.electrical import mount_z
    p = entity.params
    kind = p["point_type"]
    lm, kelvin, beam, _d = PHOTOMETRY[kind]
    beam = float(p.get("beam_deg", beam))
    dim = float(p.get("dim_level", 1.0))
    flux = lumen_of(p) * dim
    x, y, z = float(p["x"]), float(p["y"]), mount_z(doc, p)
    direction = direction_of(doc, entity)
    wiring = route_cables_cached(doc)
    circuit = next((c["id"] for c in wiring["circuits"] if entity.id in c["points"]), "")
    control = next((l for l in wiring["switch_links"] if entity.id in l["lights"]), None)
    spec = {"id": entity.id, "type": kind, "kelvin": float(p.get("kelvin", kelvin)), "lumen": round(flux, 1),
            "dim_level": dim, "enabled": dim > 0, "direction": direction, "position": [x, y, z],
            "circuit": circuit, "switch": control["switch"] if control else "", "dimmer": bool(control and control["dimmer"]),
            "automation_group": str(p.get("automation_group", "")), "load_w": round(point_load_w(p), 1)}
    if kind == "led_strip":
        spec.update(kind="strip", start=[x, y, z], end=[float(p.get("x2", x)), float(p.get("y2", y)), z],
                    angle_deg=beam / 2, intensity=flux / (2 * math.pi), length_m=round(strip_length(p), 3))
    elif kind in ("spot", "downlight", "wall_washer"):
        half = math.radians(min(beam, 179.0) / 2)
        target = [float(p.get("target_x", x)), float(p.get("target_y", y)), float(p.get("target_z", z - 2.0))]
        if kind == "wall_washer" and "target_x" not in p:
            target = _toward_wall(doc, x, y, z)
        spec.update(kind="spot", angle_deg=beam / 2, penumbra=0.5 if kind == "wall_washer" else 0.3, target=target,
                    intensity=flux / (2 * math.pi * (1 - math.cos(half))), shadows=kind == "spot")
    else:
        spec.update(kind="point", intensity=flux / (4 * math.pi))
    return spec


def _toward_wall(doc, x, y, z):
    from archforge.mep.electrical_board import _dist_to_wall
    walls = [w for w in doc.entities.values() if w.kind == "wall"]
    if not walls:
        return [x, y, z - 2.0]
    w = min(walls, key=lambda w: _dist_to_wall(w, x, y))
    p = w.params
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy or 1.0
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
    return [x1 + dx * t, y1 + dy * t, z - 1.2]


def light_specs(doc):
    return [s for s in (light_spec(doc, e) for e in electrical_points(doc)) if s is not None]


def cove_strips(doc, ceiling):
    """LED strip points along the cove of a plasterboard ceiling: one per side, one automation group."""
    from archforge.construction.drywall import inner_outline, outline
    p = ceiling.params
    if not int(p.get("cove", 0)):
        raise ValueError("η ψευδοροφή δεν έχει εσοχή κρυφού φωτισμού (ενεργοποιήστε «Εσοχή» στις Ιδιότητες)")
    poly = outline(doc, ceiling)
    loop = inner_outline(poly, max(0.02, float(p.get("cove_width", 0.30)) - COVE_SET_BACK)) if poly else None
    if not loop:
        raise ValueError("η εσοχή είναι πολύ στενή για ταινία")
    group = f"Κρυφός φωτισμός {ceiling.name or 'ψευδοροφής'}"
    out = []
    for i in range(len(loop)):
        (x1, y1), (x2, y2) = loop[i], loop[(i + 1) % len(loop)]
        if math.hypot(x2 - x1, y2 - y1) < 0.10:
            continue
        out.append({"x": float(x1), "y": float(y1), "x2": float(x2), "y2": float(y2), "z": float(p["level_z"]),
                    "point_type": "led_strip", "power_w": 0.0, "w_per_m": STRIP_W_PER_M,
                    "lumen": PHOTOMETRY["led_strip"][0], "kelvin": 3000.0, "dim_level": 1.0, "automation_group": group})
    return out


def lighting_report(doc):
    """Per automation group: luminaires, W, lumen, dimmer; LED drivers sized with the stated margin."""
    wiring = route_cables_cached(doc)
    groups = {}
    for e in electrical_points(doc):
        if not is_luminaire(e):
            continue
        key = str(e.params.get("automation_group", "")) or "—"
        g = groups.setdefault(key, {"group": key, "lights": [], "load_w": 0.0, "lumen": 0.0, "strip_m": 0.0, "controls": []})
        g["lights"].append(e.id)
        g["load_w"] += point_load_w(e.params)
        g["lumen"] += lumen_of(e.params)
        g["strip_m"] += strip_length(e.params)
    for link in wiring["switch_links"]:
        for g in groups.values():
            if set(link["lights"]) & set(g["lights"]):
                g["controls"].append(("Ροοστάτης " if link["dimmer"] else "Διακόπτης ") + link["switch"][:6])
    out = []
    for g in groups.values():
        strip_w = sum(point_load_w(e.params) for e in electrical_points(doc)
                      if e.id in g["lights"] and e.params["point_type"] == "led_strip")
        g["driver_w"] = round(strip_w * DRIVER_MARGIN, 1) if strip_w else 0.0
        g["load_w"], g["lumen"], g["strip_m"] = round(g["load_w"], 1), round(g["lumen"]), round(g["strip_m"], 2)
        out.append(g)
    return {"groups": out, "provenance": PROVENANCE}
