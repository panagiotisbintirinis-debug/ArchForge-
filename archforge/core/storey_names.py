"""Storey names as the human reads them (Ground → Ισόγειο, Floor 2 → 1ος όροφος); the stored ids stay as they are.

One source for every list that prints a storey: plan, PDF, take-off, slabs, IFC (Σ7 κριτική v5: «Ground / Floor 2» in
the take-off while the IFC wrote «Ισόγειο / 1ος όροφος»).  No Qt here, so quantities can use it.
"""
from __future__ import annotations

import re

LEVEL_NAMES = {"Ground": "Ισόγειο", "XY": "Ισόγειο", "": "Ισόγειο", "Basement": "Υπόγειο", "Roof": "Δώμα"}


def level_name(name):
    m = re.match(r"Floor (\d+)$", str(name))
    return f"{int(m.group(1)) - 1}ος όροφος" if m else LEVEL_NAMES.get(str(name), str(name))
