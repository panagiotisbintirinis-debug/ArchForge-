"""What the user points at, and what the assistant can do there.

The marker removes the ambiguity of text in a 3D model: a click in the plan
(or the current selection, e.g. from the 3D view) becomes a *target* — one
entity or one room — and the assistant offers only the actions that make
sense for it.  Typed requests are matched to those actions by keywords (no
AI): an unmatched request is answered with the list of what is possible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

POINT_KINDS = ("plumbing_point", "electrical_point", "ventilation_point", "library_object", "cabinet", "box", "plant")
KIND_LABELS = {"wall": "Τοίχος", "structural_column": "Κολώνα", "structural_beam": "Δοκός", "door": "Πόρτα",
               "window": "Παράθυρο", "plumbing_point": "Υδραυλικό σημείο", "electrical_point": "Ηλεκτρολογικό σημείο",
               "ventilation_point": "Εξαερισμός", "ceiling_joists": "Δοκίδες", "cabinet": "Ντουλάπι",
               "library_object": "Αντικείμενο", "stair": "Σκάλα"}


@dataclass
class Target:
    kind: str                         # entity kind, or 'room'
    entity_id: Optional[str]
    label: str
    x: float
    y: float
    z: float
    room: Optional[dict] = None       # the room under the point (from the shared reading)


@dataclass
class Action:
    key: str
    label: str
    keywords: Tuple[str, ...]
    build: Optional[Callable] = field(default=None, repr=False)   # doc -> Command
    run: Optional[str] = None                                       # UI action ('analyze')
    info: str = ""


def _seg_distance(x, y, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
    return math.hypot(x - (a[0] + dx * t), y - (a[1] + dy * t))


def target_at(doc, x, y, z=None):
    """The most specific thing under a plan point of the active storey."""
    from archforge.assistant.suggestions import room_at
    from archforge.ui.project_outline import _levels, entity_level
    level = float(doc.work_plane.origin[2]) if z is None else float(z)
    levels = _levels(doc)
    name = next((n for n, lz in levels if abs(lz - level) < 1e-6), None)
    room = room_at(doc, x, y, level)
    best = None                        # (priority, distance, entity)
    for e in doc.entities.values():
        if name is not None and entity_level(doc, e, levels) != name:
            continue
        p = e.params
        cand = None
        if e.kind in POINT_KINDS and "x" in p:
            d = math.hypot(x - float(p["x"]), y - float(p["y"]))
            cand = (0, d, e) if d <= 0.35 else None
        elif e.kind == "structural_column":
            half = max(float(p["width"]), float(p["depth"])) / 2 + 0.10
            d = max(abs(x - float(p["x"])), abs(y - float(p["y"])))
            cand = (1, d, e) if d <= half else None
        elif e.kind in ("door", "window") and e.parent_id in doc.entities:
            from archforge.assistant.understanding import _opening_sides
            sides = _opening_sides(doc, e)
            if not sides:
                continue
            cx, cy = (sides[0][0] + sides[1][0]) / 2, (sides[0][1] + sides[1][1]) / 2
            d = math.hypot(x - cx, y - cy)
            cand = (1, d, e) if d <= float(p["width"]) / 2 + 0.1 else None
        elif e.kind == "structural_beam":
            d = _seg_distance(x, y, (float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"])))
            cand = (2, d, e) if d <= float(p["width"]) / 2 + 0.10 else None
        elif e.kind == "wall":
            d = _seg_distance(x, y, (float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"])))
            cand = (3, d, e) if d <= float(p["thickness"]) / 2 + 0.10 else None
        if cand and (best is None or cand[:2] < best[:2]):
            best = cand
    if best is not None:
        e = best[2]
        return Target(e.kind, e.id, describe_entity(doc, e), x, y, level, room)
    if room is not None:
        return Target("room", None, room_label(room), x, y, level, room)
    return Target("empty", None, "Κενό σημείο (εκτός χώρων)", x, y, level, None)


def target_of_entity(doc, entity_id):
    """Target from a selection (e.g. picked in the 3D view)."""
    from archforge.assistant.suggestions import room_at
    e = doc.get(entity_id)
    p = e.params
    if "x" in p and "y" in p:
        x, y = float(p["x"]), float(p["y"])
    elif "x1" in p:
        x, y = (float(p["x1"]) + float(p["x2"])) / 2, (float(p["y1"]) + float(p["y2"])) / 2
    else:
        x = y = 0.0
    level = float(doc.work_plane.origin[2])
    return Target(e.kind, e.id, describe_entity(doc, e), x, y, level, room_at(doc, x, y, level))


def room_label(room):
    from archforge.assistant.understanding import USE_LABELS
    use = f" · {USE_LABELS[room['use']]}" if room.get("use") else ""
    return f"{room['name']}{use} · {room['size_m'][0]:.2f}×{room['size_m'][1]:.2f} m · {room['area_m2']:.2f} m²"


def describe_entity(doc, e):
    """Same wording as the project tree (one vocabulary everywhere)."""
    from archforge.ui.project_outline import _label, _labels_from_analysis
    if e.kind in ("structural_column", "structural_beam"):
        return _labels_from_analysis(doc).get(e.id, _label(e))
    return f"{KIND_LABELS.get(e.kind, e.kind)}: {_label(e)}"


def actions_for(doc, target: Target) -> List[Action]:
    """What the assistant can do at the target (each one = shared commands, one undo)."""
    from archforge.assistant.suggestions import _update, _vent_entity, joists_entity
    from archforge.core.commands import AddEntity
    out: List[Action] = []
    room = target.room
    floor = target.z
    if target.kind in ("room", "empty") or room is not None and target.kind not in ("structural_column", "structural_beam"):
        if room is not None:
            if not room["joists"]:
                ent = joists_entity(room["polygon"], floor, name=f"Δοκίδες — {room['name']}")
                out.append(Action("joists", "Διανομή δοκίδων ταβανιού σε αυτόν τον χώρο",
                                  ("δοκίδ", "δοκιδ", "ταβάν", "ταβαν", "joist"), lambda _d, e=ent: AddEntity(e)))
            out.append(Action("fan", "Ανεμιστήρας απαγωγής στο σημείο",
                              ("εξαερισ", "ανεμιστ", "απαγωγ", "fan"),
                              lambda _d: AddEntity(_vent_entity("bath_fan" if room.get("use") != "wc" else "wc_fan",
                                                                target.x, target.y, floor))))
            out.append(Action("hood", "Απορροφητήρας στο σημείο", ("απορροφ", "hood", "κουζιν"),
                              lambda _d: AddEntity(_vent_entity("hood", target.x, target.y, floor))))
    if target.kind in ("structural_column", "structural_beam"):
        from archforge.structure.analysis import fresh_result
        result = fresh_result(doc)
        info = result["members"].get(target.entity_id) if result else None
        out.append(Action("analyze", "Στατική ανάλυση (οπλισμός / διατομή)",
                          ("ανάλυσ", "αναλυσ", "στατικ", "οπλισ", "υπολόγ", "υπολογ"), run="analyze",
                          info=info["text"] if info else "Δεν υπάρχει ενημερωμένη ανάλυση"))
        if info and info.get("proposal"):
            prop = info["proposal"]
            size = prop.get("profile") or f"{prop['width'] * 100:.0f}/{prop.get('height', prop.get('depth', 0)) * 100:.0f}"
            out.append(Action("resize", f"Διατομή {size} από τον υπολογισμό",
                              ("μεγάλω", "μεγαλω", "διατομ", "αύξη", "αυξη", "διόρθ", "διορθ", "ενίσχ", "ενισχ"),
                              _update(target.entity_id, prop)))
    if target.kind == "ventilation_point":
        for value, label in (("wall", "Έξοδος από εξωτερικό τοίχο"), ("roof", "Έξοδος από τη στέγη")):
            out.append(Action(f"outlet_{value}", label, (("τοίχ", "τοιχ") if value == "wall" else ("στέγ", "στεγ", "ταράτσ")),
                              _update(target.entity_id, {"outlet": value})))
    if target.kind == "electrical_point":
        for value, label in (("wall", "Όδευση από τοίχο"), ("floor", "Όδευση από δάπεδο")):
            out.append(Action(f"routing_{value}", label, (("τοίχ", "τοιχ") if value == "wall" else ("δάπεδ", "δαπεδ", "πάτωμ")),
                              _update(target.entity_id, {"routing": value})))
    if target.kind == "ceiling_joists":
        for s in (0.40, 0.30):
            out.append(Action(f"spacing_{s}", f"Απόσταση δοκίδων {s * 100:.0f} cm",
                              ("πυκν", f"{s * 100:.0f}"), _update(target.entity_id, {"spacing": s})))
    return out


def match(text, actions):
    """The action a typed request asks for, or None (keyword match, Greek with or without accents)."""
    t = str(text or "").lower()
    scored = []
    for a in actions:
        score = sum(1 for k in a.keywords if k in t)
        if score:
            scored.append((score, a))
    if not scored:
        return None
    scored.sort(key=lambda s: -s[0])
    return scored[0][1]
