"""One click = indication (owner 23/10: «το μονό κλικ είναι ένδειξη, το διπλό επιλογή, το πατημένο χρήση»): what the
object under the mouse is, in a few words with its main numbers — shown, not picked."""
from __future__ import annotations

import math


def _m(v):
    return f"{float(v):.2f}".replace(".", ",")


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
            return f"{word}{name} {_m(L)} × {_m(p.get('thickness', 0.2))} · ύψος {_m(p.get('height', 0))}"
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
