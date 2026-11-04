"""One click = indication (owner 23/10: «το μονό κλικ είναι ένδειξη, το διπλό επιλογή, το πατημένο χρήση»): what the
object under the mouse is, in a few words with its main numbers — shown, not picked."""
from __future__ import annotations

import math


def _m(v):
    return f"{float(v):.2f}".replace(".", ",")


def storey_of(doc, z):
    """The human name of the storey at ``z`` (Ground → Ισόγειο), or None."""
    from archforge.core.cameras import storey_name
    from archforge.output.pdf import level_name
    name = storey_name(doc, float(z))
    return level_name(name) if name else None


def wall_details(doc, e):
    """« · Διπλή τοιχοποιία… · Ισόγειο · U 0,48» — type, storey and U of a wall (κριτική v5: «τι είναι αυτό;» με μηδέν
    κλικ· ο όροφος με όνομα, όχι «Στάθμη (z) 0.0000»)."""
    p = e.params
    parts = []
    try:
        from archforge.architecture import wall_types as wt
        key = p.get("wall_type") or "generic"
        label = wt.label(key, doc) if hasattr(wt, "label") else None
        if not label:
            entry = wt.WALL_TYPES.get(key)
            label = entry[0] if entry else str(key)
        parts.append(label)
        storey = storey_of(doc, p.get("z", 0.0))
        if storey:
            parts.append(storey)
        u = wt.indicative_u(key, doc)
        if u is not None:
            parts.append(f"U {u:.2f} W/m²K".replace(".", ","))
    except Exception:                           # noqa: BLE001 — a description must never break the plan
        return ""
    return " · " + " · ".join(parts)


def describe(doc, eid):
    """«Τοίχος 4,00 × 0,25 · ύψος 2,70» and the like."""
    from archforge.ui.project_outline import KIND_LABELS
    e = doc.get(eid)
    p = e.params
    word = KIND_LABELS.get(e.kind, e.kind)
    name = f" «{e.name}»" if e.name and e.name not in (word,) else ""
    try:
        if e.kind == "wall":
            L = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
            return (f"{word}{name} {_m(L)} × {_m(p.get('thickness', 0.2))} · ύψος {_m(p.get('height', 0))}"
                    + wall_details(doc, e))
        if e.kind in ("door", "window", "opening"):
            return f"{word}{name} {_m(p['width'])} × {_m(p['height'])}" + (f" · ποδιά {_m(p['sill'])}" if float(p.get('sill', 0)) else "")
        if e.kind == "stair":
            return (f"{word}{name} {p.get('riser_count', '')} ρίχτια × {float(p.get('riser_height', 0)) * 100:.1f} cm · "
                    f"πλάτος {_m(p.get('width', 0))}").replace(".", ",")
        if "width" in p and "depth" in p:
            return f"{word}{name} {_m(p['width'])} × {_m(p['depth'])}" + (f" · ύψος {_m(p['height'])}" if "height" in p else "")
    except (KeyError, TypeError, ValueError):
        pass
    return f"{word}{name}"
