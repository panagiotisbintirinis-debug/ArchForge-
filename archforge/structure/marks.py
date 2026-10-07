"""Member marks: every column and beam has its own name (Κ1, Κ2 … / Δ1, Δ2 …).

The mark is the entity's name, so the same «Κ7» appears in the Properties,
the project tree, the structural analysis, the formwork sheet (ξυλότυπος)
and the reinforcement schedules.  Rules:

* a new member without a name of its own gets the next free number of its
  kind (``Document.add``), a whole proposed frame is numbered in plan
  reading order (lowest storey first, then top-to-bottom, left-to-right);
* a name the user typed (anything that is not a generic «Κολόνα»/«Beam» …)
  is never touched;
* «Αρίθμηση» renumbers all marked members in reading order (one undo).
"""
from __future__ import annotations

import re

PREFIX = {"structural_column": "Κ", "structural_beam": "Δ"}
GENERIC = {"", "Column", "Beam", "Structural_Column", "Structural_Beam", "Κολόνα", "Κολώνα", "Δοκός", "Δοκάρι"}


def is_mark(kind, name):
    return bool(re.fullmatch(PREFIX[kind] + r"\d+", str(name or "")))


def is_unnamed(entity):
    return entity.kind in PREFIX and str(entity.name or "").strip() in GENERIC


def _number(kind, name):
    return int(str(name)[1:]) if is_mark(kind, name) else 0


def next_mark(doc, kind):
    used = [_number(kind, e.name) for e in doc.entities.values() if e.kind == kind]
    return f"{PREFIX[kind]}{max(used, default=0) + 1}"


def reading_key(entity):
    p = entity.params
    x = float(p.get("x", p.get("x1", 0.0))); y = float(p.get("y", p.get("y1", 0.0)))
    if "x2" in p:
        x = min(x, float(p["x2"])); y = max(y, float(p["y2"]))
    return (round(float(p.get("z", 0.0)), 1), -round(y, 1), round(x, 1))


def name_new(doc, entities):
    """Give the unnamed members of ``entities`` (not yet in ``doc``) the next marks, in reading order."""
    count = {k: int(next_mark(doc, k)[1:]) for k in PREFIX}
    for e in sorted((e for e in entities if is_unnamed(e)), key=reading_key):
        e.name = f"{PREFIX[e.kind]}{count[e.kind]}"
        count[e.kind] += 1
    return entities


def renumber(doc):
    """``{eid: new mark}`` for every generic or marked member, in reading order (user names kept)."""
    out = {}
    for kind, prefix in PREFIX.items():
        members = sorted((e for e in doc.entities.values() if e.kind == kind and (is_unnamed(e) or is_mark(kind, e.name))),
                         key=reading_key)
        for i, e in enumerate(members, 1):
            if e.name != f"{prefix}{i}":
                out[e.id] = f"{prefix}{i}"
    return out
