"""Bio-Spectre domes from the UI (owner 21/10: «η μηχανή υπάρχει, κανένα εργαλείο»).

* ``dome_params``: one pod (upper-half ellipsoid shell) at a point of a storey.
* ``resting_level``: a dome placed over lower domes sits on their shell — its floor is the
  highest lower shell at its centre (``z = floor + h·√(1 − (d/R)²)``, R = the rotated
  ellipse's reach towards the point), so a «θόλος επάνω» needs no level typed in.
* ``SyncOrganicJunctions``: where two domes overlap in 3D the curved shells become one flat
  shared partition (``organic_junction``, organic/junctions.py).  The command reconciles them
  with the pods and snapshots before/after, so undo/redo restore the same junction ids.
"""
from __future__ import annotations

import math

from archforge.core.commands import Command
from archforge.organic.biospectre import _radial_extent, all_pod_junctions, shell_top

SHELL = 0.018                       # 18 mm Bio-Spectre shell (organic/materials.py presets)
DEFAULT_DIAMETER = 6.0
DEFAULT_HEIGHT = 3.2


def dome_params(cx, cy, level, diameter=DEFAULT_DIAMETER, height=DEFAULT_HEIGHT, depth=None, rotation=0.0, shell=SHELL):
    return {'cx': float(cx), 'cy': float(cy), 'floor_level': float(level), 'diameter_x': float(diameter),
            'diameter_y': float(depth if depth else diameter), 'height': float(height),
            'shell_thickness': float(shell), 'rotation': float(rotation)}


def shell_height_at(p, x, y):
    """Height of pod ``p``'s shell above (x, y), or None outside its footprint."""
    dx, dy = float(x) - float(p['cx']), float(y) - float(p['cy'])
    d = math.hypot(dx, dy)
    reach = _radial_extent(p, dx / d, dy / d) if d > 1e-12 else 1.0
    if d > reach:
        return None
    return float(p['floor_level']) + float(p['height']) * math.sqrt(max(0.0, 1.0 - (d / reach) ** 2))


def resting_level(doc, x, y, base=0.0):
    """Floor level of a dome over (x, y): on the highest shell below it, else ``base``."""
    best = None
    for e in doc.entities.values():
        if e.kind != 'pod' or not e.visible or shell_top(e.params) <= base + 1e-6:
            continue
        z = shell_height_at(e.params, x, y)
        if z is not None and z > base + 1e-6 and (best is None or z > best):
            best = z
    return base if best is None else best


def junctions_out_of_date(doc):
    """True when the active organic_junction entities differ from the domes' live 3D overlaps."""
    live = set(all_pod_junctions(doc))
    active = {e.params.get('junction_key') for e in doc.entities.values()
              if e.kind == 'organic_junction' and e.params.get('status') == 'active'}
    return live != active


def _snapshot(doc):
    return [e.clone() for e in doc.entities.values() if e.kind == 'organic_junction']


def _restore(doc, snapshot):
    for e in [e for e in doc.entities.values() if e.kind == 'organic_junction']:
        doc.remove(e.id)
    for e in snapshot:
        doc.add(e.clone())
        for source in (e.params.get('component_a'), e.params.get('component_b')):
            if source in doc.entities:
                doc.add_dependency(source, e.id)


class SyncOrganicJunctions(Command):
    """Flat shared partitions follow the domes: new overlaps get one, separated ones go dormant."""

    def __init__(self):
        self.before = None
        self.after = None

    def do(self, doc):
        if self.after is not None:                       # redo: the same junction entities again
            _restore(doc, self.after)
            return
        from archforge.organic.junctions import infer_organic_junctions
        self.before = _snapshot(doc)
        infer_organic_junctions(doc)
        self.after = _snapshot(doc)

    def undo(self, doc):
        _restore(doc, self.before or [])
