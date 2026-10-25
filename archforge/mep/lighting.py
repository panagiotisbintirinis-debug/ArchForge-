"""Luminaires as one thing: construction + electricity + light effect (owner, 2026-10-15).

A luminaire is an ``electrical_point`` of the lighting group (light, spot,
downlight, wall washer, wall light, LED strip).  The same entity carries

* **ουσία** — its load (W, or W/m × length for a strip), circuit, switch or
  dimmer, automation group and cable route (``mep/electrical.py``);
* **ομορφιά** — lumen, Kelvin, beam (from the data sheet), aim, direction, dim level, read here by
  ``light_spec`` for the renderer (night scenes) so the picture and the
  installation never disagree;
* **κατασκευή** — where it sits: a strip inside the cove of a plasterboard
  ceiling (``drywall_ceiling`` with ``cove``) sits on the low band behind the
  upstand and throws its light up into the slot; it follows the ceiling when
  its drop or cove changes.

No catalogue defaults (owner's rule 15/10): W, lm, K and beam are the data
sheet values the user enters; nothing here is a lighting study.
"""
from __future__ import annotations

import math

from archforge.core.provenance import DESIGN_DEFAULT, MANUFACTURER_DATA, Rule, register
from archforge.mep.electrical import electrical_points, point_load_w, route_cables_cached, strip_length

register(
    Rule("lighting.photometry", "Φωτεινή ροή (lm ή lm/m), χρώμα (K), δέσμη (°) ανά φωτιστικό", MANUFACTURER_DATA,
         note="Χωρίς προεπιλογή· χωρίς αυτά το 3D δείχνει εμφάνιση οθόνης, όχι πραγματικό φως"),
    Rule("lighting.strip_w_per_m", "Ισχύς ταινίας LED ανά μέτρο", MANUFACTURER_DATA, note="Από το φύλλο της ταινίας"),
    Rule("lighting.beam_presets", "Γρήγορες επιλογές δέσμης 10° / 24° / 36° / 60°", DESIGN_DEFAULT,
         note="Λίστα του ιδιοκτήτη 15/10· η δέσμη του φωτιστικού είναι στοιχείο κατασκευαστή"),
    Rule("lighting.cove_set_back", "Ταινία στην εσοχή: 5 cm μπροστά από το σκαλοπάτι, πάνω στη χαμηλή ζώνη", DESIGN_DEFAULT),
    Rule("lighting.candela", "Ένταση για το 3D: I = Φ/(2π(1−cos(β/2))) για δέσμη β, Φ/4π ισότροπα, Φ/2π ταινία",
         DESIGN_DEFAULT, note="Μετατροπή για την απεικόνιση, όχι φωτοτεχνικός υπολογισμός"),
)

PROVENANCE = ("Φωτομετρικά στοιχεία (lm, K, δέσμη) και ισχύς: μόνο από το φύλλο του φωτιστικού που εισάγει ο χρήστης — "
              "το πρόγραμμα δεν βάζει τυπικές τιμές (κανόνας ιδιοκτήτη 15/10). Όχι φωτοτεχνική μελέτη")

# type -> direction when the user has not chosen one (geometry of the fitting, not a catalogue value)
DEFAULT_DIRECTION = {"light": "down", "spot": "down", "downlight": "down", "wall_washer": "wall",
                     "wall_light": "both", "led_strip": "down"}
PHOTOMETRY = DEFAULT_DIRECTION            # the luminaire types
BEAM_PRESETS = (10.0, 24.0, 36.0, 60.0)   # owner's list (15/10): 10° / 24° / 36° / 60° or custom
DIRECTIONS = ("down", "up", "wall", "both")
# Fittings with an adjustable head: their beam is aimed (tilt from the vertical, compass bearing); the rest are fixed.
AIMABLE = ("spot", "wall_washer")
AIM_REACH = 2.0            # length of the aim line to the renderer's target point (m) — direction only, not a range
COVE_SET_BACK = 0.05       # strip this far in front of the upstand, on the low band (placement, not a rating)


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
    return DEFAULT_DIRECTION[p["point_type"]]


def is_on(params):
    """The luminaire is switched on in the picture: «Αναμμένο» ticked and the dimmer above 0 %."""
    return bool(int(params.get("light_on", 1))) and float(params.get("dim_level", 1.0)) > 0


def aim_target(doc, params, x, y, z):
    """Point the beam is aimed at, or None when the fitting has no aim (renderer keeps its own default).

    An adjustable head (``AIMABLE``) aimed in Ιδιότητες: ``aim_tilt_deg`` from the vertical (0° = straight down,
    90° = horizontal) and ``aim_azimuth_deg`` as a compass bearing in plan (0° = +y Βορράς, 90° = +x Ανατολή);
    «Προς τα πάνω» turns the same aim upwards.  Otherwise an explicit ``target_x/y/z``, else the direction.
    """
    p = params
    kind = p.get("point_type")
    direction = p.get("direction", "auto")
    if kind in AIMABLE and "aim_tilt_deg" in p:
        tilt = math.radians(float(p["aim_tilt_deg"]))
        bearing = math.radians(float(p.get("aim_azimuth_deg", 0.0)))
        reach = AIM_REACH * math.sin(tilt)
        rise = AIM_REACH * math.cos(tilt) * (1.0 if direction == "up" else -1.0)
        return [x + reach * math.sin(bearing), y + reach * math.cos(bearing), z + rise]
    if "target_x" in p:
        return [float(p["target_x"]), float(p.get("target_y", y)), float(p.get("target_z", z - AIM_REACH))]
    if direction == "up":
        return [x, y, z + AIM_REACH]
    if direction == "wall" or (kind == "wall_washer" and direction == "auto"):
        return _toward_wall(doc, x, y, z) if doc is not None else [x, y, z - AIM_REACH]
    if direction == "down" or kind in ("spot", "downlight", "wall_washer"):
        return [x, y, z - AIM_REACH]
    return None


def lumen_of(params):
    """Luminous flux (lm) from the data sheet value the user entered (lm/m for a strip), or None."""
    if not params.get("lumen"):
        return None
    lm = float(params["lumen"])
    return lm * strip_length(params) if params["point_type"] == "led_strip" else lm


def light_spec(doc, entity):
    """The renderer's view of one luminaire (same entity as the electrical point), or None.

    Only the user's data-sheet values: ``lumen``/``kelvin``/``beam_deg`` are None
    when not entered (the renderer then uses its own display look and the
    luminaire is listed as «χωρίς φωτομετρικά»).  With lumen entered,
    ``intensity`` is in candela: cone I = Φ / (2π(1 − cos(β/2))) when the beam
    is entered, isotropic I = Φ / 4π, a strip into a half space I = Φ / 2π;
    scaled by ``dim_level``.
    """
    if not is_luminaire(entity):
        return None
    from archforge.mep.electrical import mount_z
    p = entity.params
    kind = p["point_type"]
    beam = float(p["beam_deg"]) if "beam_deg" in p else None
    dim = float(p.get("dim_level", 1.0))
    flux = lumen_of(p)
    flux = None if flux is None else flux * dim
    x, y, z = float(p["x"]), float(p["y"]), mount_z(doc, p)
    direction = direction_of(doc, entity)
    wiring = route_cables_cached(doc)
    circuit = next((c["id"] for c in wiring["circuits"] if entity.id in c["points"]), "")
    control = next((l for l in wiring["switch_links"] if entity.id in l["lights"]), None)
    spec = {"id": entity.id, "type": kind, "kelvin": float(p["kelvin"]) if p.get("kelvin") else None,
            "lumen": None if flux is None else round(flux, 1), "beam_deg": beam, "dim_level": dim, "enabled": is_on(p),
            "direction": direction, "position": [x, y, z], "circuit": circuit,
            "switch": control["switch"] if control else "", "dimmer": bool(control and control["dimmer"]),
            "automation_group": str(p.get("automation_group", "")), "load_w": round(point_load_w(p), 1),
            "dimming": p.get("dimming", ""), "catalog_id": p.get("catalog_id", ""),
            "data_status": _data_status(p),
            "photometry_entered": all(p.get(k) for k in ("lumen", "kelvin")) and (beam is not None or kind in ("light", "wall_light", "led_strip"))}
    if kind == "led_strip":
        spec.update(kind="strip", start=[x, y, z], end=[float(p.get("x2", x)), float(p.get("y2", y)), z],
                    length_m=round(strip_length(p), 3), intensity=None if flux is None else flux / (2 * math.pi))
        if beam is not None:
            spec["angle_deg"] = beam / 2
    elif kind in ("spot", "downlight", "wall_washer"):
        spec.update(kind="spot", target=aim_target(doc, p, x, y, z), shadows=kind == "spot")
        if beam is not None:
            spec["angle_deg"] = beam / 2
        spec["intensity"] = (None if flux is None or beam is None
                             else flux / (2 * math.pi * (1 - math.cos(math.radians(min(beam, 179.0) / 2)))))
    else:
        spec.update(kind="point", intensity=None if flux is None else flux / (4 * math.pi))
    return spec


def _data_status(params):
    from archforge.mep.luminaire_catalog import status_of
    return status_of(params)[0]


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
        # No W/m, lm/m or K: the strip's data sheet values are entered once for the group (Ιδιότητες).
        out.append({"x": float(x1), "y": float(y1), "x2": float(x2), "y2": float(y2), "z": float(p["level_z"]),
                    "point_type": "led_strip", "power_w": 0.0, "dim_level": 1.0, "automation_group": group})
    return out


def lighting_report(doc):
    """Per automation group: luminaires, W, lumen, strip metres, controls; what still needs data-sheet values."""
    wiring = route_cables_cached(doc)
    groups = {}
    for e in electrical_points(doc):
        if not is_luminaire(e):
            continue
        key = str(e.params.get("automation_group", "")) or "—"
        g = groups.setdefault(key, {"group": key, "lights": [], "load_w": 0.0, "lumen": 0.0, "strip_m": 0.0,
                                    "controls": [], "missing": []})
        g["lights"].append(e.id)
        g["load_w"] += point_load_w(e.params)
        lm = lumen_of(e.params)
        g["lumen"] += lm or 0.0
        g["strip_m"] += strip_length(e.params)
        need = [k for k in (("w_per_m" if e.params["point_type"] == "led_strip" else "power_w"), "lumen", "kelvin")
                if not e.params.get(k)]
        if need:
            g["missing"].append((e.id, need))
    for link in wiring["switch_links"]:
        for g in groups.values():
            if set(link["lights"]) & set(g["lights"]):
                g["controls"].append(("Ροοστάτης " if link["dimmer"] else "Διακόπτης ") + link["switch"][:6])
    from archforge.mep.luminaire_catalog import DIMMING, DRIVER_MARGIN
    points = {e.id: e for e in electrical_points(doc)}
    out, warnings = [], []
    for g in groups.values():
        protocols = {points[i].params.get("dimming") or "onoff" for i in g["lights"]}     # owner 15/10: On/Off by default
        g["dimming"] = sorted(p for p in protocols if p)
        if len(g["dimming"]) > 1:
            warnings.append(f"Ομάδα «{g['group']}»: διαφορετικά πρωτόκολλα ρύθμισης "
                            f"({', '.join(DIMMING[p] for p in g['dimming'])}) — ένας ροοστάτης δεν τα ελέγχει όλα")
        if any("Ροοστάτης" in c for c in g["controls"]) and "onoff" in protocols:
            warnings.append(f"Ομάδα «{g['group']}»: ροοστάτης σε φωτιστικό χωρίς ρύθμιση έντασης (On/Off)")
        strip_w = sum(point_load_w(points[i].params) for i in g["lights"] if points[i].params["point_type"] == "led_strip")
        g["driver_hint_w"] = round(strip_w * DRIVER_MARGIN, 1) if strip_w else None      # ENGINEER_REVIEW (registry)
        g["load_w"], g["lumen"], g["strip_m"] = round(g["load_w"], 1), round(g["lumen"]), round(g["strip_m"], 2)
        out.append(g)
    return {"groups": out, "warnings": warnings, "provenance": PROVENANCE}


# The lights of the building by room (owner 25/10: «μικρό μενού που θα μας δείχνει όλα τα φώτα του κτιρίου ανά χώρο —
# δωμάτιο 1: κρυφός φωτισμός, απλίκες, κεντρικό …»): the lighting strip of the 3D (ui/lighting_panel.py).
GROUP_LABELS = {"light": "Κεντρικό", "downlight": "Χωνευτά", "spot": "Σποτ", "wall_washer": "Wall washer",
                "wall_light": "Απλίκες", "led_strip": "Κρυφός φωτισμός"}
OUTSIDE_ROOMS = "Εκτός χώρων"
# What a luminaire can be replaced with at the same point: a strip is a line, the rest are points.
LINE_TYPES = ("led_strip",)
KEPT_ON_REPLACE = ("x", "y", "z", "x2", "y2", "automation_group", "light_on", "dim_level", "routing", "direction",
                   "aim_tilt_deg", "aim_azimuth_deg")


def is_fixture(entity):
    """A light of the building: an electrical luminaire or a luminous library object (GLB with emitters)."""
    from archforge.library.lighting import is_luminous
    return is_luminaire(entity) or is_luminous(entity)


def fixture_on(entity):
    """Switched on: one state per kind — ``light_on``/``dim_level`` (electrical), ``light_enabled``/``light_level``
    (library object, the content pack's fields).  Never a second copy of either."""
    p = entity.params
    if entity.kind == "library_object":
        return bool(float(p.get("light_enabled", 1))) and float(p.get("light_level", 1.0)) > 0
    return is_on(p)


def fixture_switch(entity):
    p = entity.params
    return bool(float(p.get("light_enabled", 1))) if entity.kind == "library_object" else bool(int(p.get("light_on", 1)))


def fixture_level(entity):
    key = "light_level" if entity.kind == "library_object" else "dim_level"
    return float(entity.params.get(key, 1.0))


def fixture_changes(entity, on=None, level=None):
    """Params of ONE fixture for on/off and the dimmer (owner 25/10: «όχι μαζική, τοπική αλλαγή»)."""
    library = entity.kind == "library_object"
    out = {}
    if on is not None:
        out["light_enabled" if library else "light_on"] = (1.0 if on else 0.0) if library else (1 if on else 0)
    if level is not None:
        out["light_level" if library else "dim_level"] = max(0.0, min(1.0, float(level)))
    return out


def fixture_aimable(entity):
    """Turns: an electrical spot / wall washer, or a library model that declares ``aimable``."""
    from archforge.library.lighting import capabilities, is_luminous
    if is_luminous(entity):
        return capabilities(entity)["aimable"]
    return entity.params.get("point_type") in AIMABLE


def _fixture_group(entity):
    from archforge.library.lighting import capabilities, role_label
    if entity.kind == "library_object":
        label = role_label(capabilities(entity)["role"])
        return f"lib:{label}", label
    t = entity.params["point_type"]
    return t, GROUP_LABELS[t]


def lights_by_room(doc):
    """``[{"title", "groups": [{"type", "label", "ids"}]}]`` — rooms in drawing order, then «Εκτός χώρων».

    Electrical luminaires by their type, luminous library objects by the role their model declares.
    """
    from archforge.assistant.understanding import read_drawing
    from archforge.mep.electrical import _floor_of
    lights = [e for e in doc.entities.values() if is_fixture(e)]
    if not lights:
        return []
    order = list(GROUP_LABELS)
    reading = read_drawing(doc)["storeys"]
    several = len(reading) > 1
    placed, out = set(), []

    def groups_of(ids):
        by_key, labels = {}, {}
        for i in ids:
            key, label = _fixture_group(doc.get(i))
            by_key.setdefault(key, []).append(i); labels[key] = label
        keys = [k for k in order if k in by_key] + sorted((k for k in by_key if k not in order), key=lambda k: labels[k])
        return [{"type": k, "label": labels[k], "ids": by_key[k]} for k in keys]

    library = [e for e in lights if e.kind == "library_object"]
    for storey in reading:
        for room in storey["rooms"]:
            ids = [i for i in room["electrical"] if i not in placed and is_luminaire(doc.get(i))]
            ids += [e.id for e in library if e.id not in placed
                    and abs(_floor_of(doc, float(e.params.get("z", 0.0))) - storey["z"]) < 1e-6
                    and _inside(room["polygon"], float(e.params["x"]), float(e.params["y"]))]
            if not ids:
                continue
            placed.update(ids)
            out.append({"title": f"{storey['name']} · {room['name']}" if several else room["name"], "groups": groups_of(ids)})
    rest = [e.id for e in lights if e.id not in placed]
    if rest:
        out.append({"title": OUTSIDE_ROOMS, "groups": groups_of(rest)})
    return out


def replacement_choices(entity):
    """``[(label, point_type, catalog_id or None)]`` that can take this luminaire's place (same point / same line).

    A luminous library object is replaced by another luminous model of the library: ``(name, "library", asset id)``.
    """
    if entity.kind == "library_object":
        from archforge.library import assets
        return [(r["name"], "library", r["id"]) for r in assets.list_assets() if r.get("lit")]
    from archforge.mep.electrical import POINT_TYPES
    from archforge.mep.luminaire_catalog import entries_for
    line = entity.params.get("point_type") in LINE_TYPES
    types = [t for t in PHOTOMETRY if (t in LINE_TYPES) == line]
    out = []
    for t in types:
        out.append((POINT_TYPES[t][0], t, None))
        out += [(e.label, t, e.id) for e in entries_for(t)]
    return out


LIBRARY_KEPT_ON_REPLACE = ("light_enabled", "light_level", "light_shadows", "aim_tilt_deg", "aim_azimuth_deg")


def replace_fixture(doc, eid, kind, ref=None):
    """(command, new entity) for a row of ``replacement_choices`` — the strip's «Αλλαγή»."""
    if kind == "library":
        return replace_library_fixture(doc, eid, ref)
    return replace_luminaire(doc, eid, kind, ref)


def replace_library_fixture(doc, eid, asset_id):
    """Another luminous library model at the same place and turn; on/off, level, shadows and aim stay (the aim only
    when the new model turns too); its emitters, size and Kelvin are the new model's."""
    from archforge.core.commands import AddEntity, CompositeCommand, DeleteEntities
    from archforge.core.model import Entity
    from archforge.library import assets
    from archforge.library.lighting import capabilities
    from archforge.ui.library_instance_integration import library_instance_params
    old = doc.get(eid)
    record = assets.load_asset(str(asset_id))
    if not record or not record.get("lights"):
        raise ValueError("το μοντέλο δεν έχει πηγές φωτός — δεν είναι φωτιστικό")
    p = old.params
    params = library_instance_params(record, x=float(p["x"]), y=float(p["y"]), z=float(p.get("z", 0.0)))
    params["rotation"] = float(p.get("rotation", 0.0))
    params.update({k: p[k] for k in LIBRARY_KEPT_ON_REPLACE if k in p})
    new = Entity("library_object", params, name=record["name"])
    new.parent_id = old.parent_id
    if not capabilities(new)["aimable"]:
        new.params.pop("aim_tilt_deg", None); new.params.pop("aim_azimuth_deg", None)
    return CompositeCommand([DeleteEntities([eid]), AddEntity(new)], "Αντικατάσταση φωτιστικού"), new


def replace_luminaire(doc, eid, point_type, catalog_id=None):
    """(command, new entity): another luminaire at the same place, one undo step.

    The place, the control (group, on/off, dimmer level), the routing and the aim stay; the product's own values
    (W, lm, K, beam, driver) do not — they belong to the removed fitting (a catalogue entry fills them in).
    """
    from archforge.core.commands import AddEntity, CompositeCommand, DeleteEntities
    from archforge.core.model import Entity
    from archforge.mep.electrical import POINT_TYPES
    from archforge.mep.luminaire_catalog import apply_values
    old = doc.get(eid)
    if (old.params.get("point_type") in LINE_TYPES) != (point_type in LINE_TYPES) or point_type not in PHOTOMETRY:
        raise ValueError("μια ταινία αντικαθίσταται μόνο με ταινία και ένα σημειακό φωτιστικό με σημειακό")
    params = {k: old.params[k] for k in KEPT_ON_REPLACE if k in old.params}
    if point_type not in LINE_TYPES:
        params.pop("x2", None); params.pop("y2", None)
    params.update(point_type=point_type, power_w=float(POINT_TYPES[point_type][2]))
    if catalog_id:
        params.update(apply_values(catalog_id))
    new = Entity("electrical_point", params, name=POINT_TYPES[point_type][0])
    new.parent_id = old.parent_id
    return CompositeCommand([DeleteEntities([eid]), AddEntity(new)], "Αντικατάσταση φωτιστικού"), new
