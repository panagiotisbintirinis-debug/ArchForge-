"""Move / rotate / mirror / duplicate / delete for everything the user places.

One place that knows, per kind, what "the object" is (a pergola is all its
posts and beams), where it turns (its centre) and where the plan shows its
rotation handle.  Every action is one shared command (MoveEntities,
RotateEntities, UpdateEntity, AddEntities, DeleteEntities) — one undo — so
the plan, the 3D view and the mouse menu all converge on the same Document.
"""
from __future__ import annotations

import copy
import math

from archforge.core.commands import (AddEntities, CompositeCommand, DeleteEntities, MoveEntities,
                                     RotateEntities, UpdateEntity)

# Kinds placed by the user that can be moved, rotated and deleted with the mouse.
POINT_KINDS = ('plumbing_point', 'electrical_point', 'ventilation_point', 'drainage_point', 'mep_terminal')
XY_KINDS = ('library_object', 'cabinet', 'kitchen_part', 'box', 'plant') + POINT_KINDS
USER_PLACED_KINDS = XY_KINDS + ('stair', 'ramp', 'railing', 'structural_column', 'structural_beam', 'door', 'window')
# Doors and windows slide along their wall (OpeningEditTransaction) and flip instead of turning.
ROTATABLE_KINDS = tuple(k for k in USER_PLACED_KINDS if k not in ('door', 'window'))
# Kinds with a rotation of their own (the rest only turn about the pivot).
OWN_ROTATION = ('library_object', 'cabinet', 'kitchen_part', 'box', 'structural_column')


def is_user_placed(e):
    return e.kind in USER_PLACED_KINDS and not e.locked


def _bbox_of(pts):
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return min(xs), min(ys), max(xs), max(ys)


def plan_outline(doc, eid):
    """Plan points of one entity (for pivots, handles and groups)."""
    e = doc.get(eid)
    p = e.params
    if e.kind in ('library_object', 'cabinet', 'kitchen_part', 'box', 'structural_column'):
        w, d = float(p.get('width', .3)), float(p.get('depth', .3))
        a = math.radians(float(p.get('rotation', 0.0)))
        c, s = math.cos(a), math.sin(a)
        x, y = float(p['x']), float(p['y'])
        return [(x + c * u - s * v, y + s * u + c * v) for u, v in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))]
    if e.kind == 'structural_beam':
        return [(float(p['x1']), float(p['y1'])), (float(p['x2']), float(p['y2']))]
    if e.kind == 'railing':
        return [(float(q[0]), float(q[1])) for q in p['points']]
    if e.kind == 'stair':
        from archforge.architecture.stairs import candidate_from_params, stair_footprint
        return list(stair_footprint(candidate_from_params(p)))
    if e.kind == 'ramp':
        from archforge.architecture.ramps import candidate_from_params, ramp_footprint
        return list(ramp_footprint(candidate_from_params(p)))
    if e.kind == 'plant':
        r = float(p.get('canopy', 1.0)) / 2
        x, y = float(p['x']), float(p['y'])
        return [(x - r, y - r), (x + r, y + r)]
    if 'x' in p and 'y' in p:
        x, y = float(p['x']), float(p['y'])
        return [(x - .1, y - .1), (x + .1, y + .1)]
    return []


def group_ids(doc, eid):
    """The whole object behind one entity: a pergola is its posts and beams together."""
    e = doc.get(eid)
    if e.kind not in ('structural_column', 'structural_beam') or e.params.get('role') != 'pergola':
        return [eid]
    members = {i: q for i, q in doc.entities.items()
               if q.kind in ('structural_column', 'structural_beam') and q.params.get('role') == 'pergola'}
    boxes = {i: _bbox_of(plan_outline(doc, i)) for i in members}
    out, todo = {eid}, [eid]
    while todo:
        a = boxes[todo.pop()]
        for i, b in boxes.items():
            if i not in out and a[0] - .05 <= b[2] and b[0] - .05 <= a[2] and a[1] - .05 <= b[3] and b[1] - .05 <= a[3]:
                out.add(i)
                todo.append(i)
    return sorted(out, key=lambda i: list(doc.entities).index(i))


def pivot(doc, ids):
    """Centre of the plan bounding box of the entities."""
    pts = [q for i in ids for q in plan_outline(doc, i)]
    if not pts:
        return 0.0, 0.0
    e = doc.get(ids[0])
    if len(ids) == 1 and e.kind in XY_KINDS + ('structural_column',):
        return float(e.params['x']), float(e.params['y'])
    x0, y0, x1, y1 = _bbox_of(pts)
    return (x0 + x1) / 2, (y0 + y1) / 2


def rotate_handle_point(doc, eid):
    """Where the plan shows the round rotation handle: in front of the object, 35 cm out."""
    e = doc.get(eid)
    p = e.params
    if e.kind in OWN_ROTATION:
        a = math.radians(float(p.get('rotation', 0.0)))
        reach = float(p.get('depth', .3)) / 2 + .35
        x, y = float(p['x']), float(p['y'])
        return x + math.sin(a) * reach, y - math.cos(a) * reach        # local -Y = front
    ids = group_ids(doc, eid)
    px, py = pivot(doc, ids)
    pts = [q for i in ids for q in plan_outline(doc, i)]
    y0 = min(q[1] for q in pts) if pts else py
    return px, y0 - .35


def rotated_params(kind, p, angle, about):
    """Params of an XY kind turned by ``angle`` degrees about ``about`` (None: unsupported)."""
    if kind not in XY_KINDS:
        return None
    r = math.radians(angle)
    c, s = math.cos(r), math.sin(r)
    px, py = about
    dx, dy = float(p['x']) - px, float(p['y']) - py
    out = dict(p, x=px + dx * c - dy * s, y=py + dx * s + dy * c)
    if kind in OWN_ROTATION:
        out['rotation'] = (float(p.get('rotation', 0.0)) + angle) % 360.0
    return out


def rotate_command(doc, eid, angle):
    ids = group_ids(doc, eid)
    return RotateEntities(ids, float(angle), pivot=pivot(doc, ids))


def move_command(doc, eid, dx, dy):
    return MoveEntities(group_ids(doc, eid), float(dx), float(dy))


def delete_command(doc, eid):
    return DeleteEntities(group_ids(doc, eid))


def flip_command(doc, eid, key):
    """Door / window: other hinge side (``hinge``) or other opening direction (``swing``)."""
    from archforge.architecture.joinery import resolved
    e = doc.get(eid)
    r = resolved(e.kind, e.params)
    value = {'hinge': {'left': 'right', 'right': 'left'}, 'swing': {'in': 'out', 'out': 'in'}}[key][r[key]]
    return UpdateEntity(eid, {key: value})


def mirror_command(doc, eid):
    """Mirror image in place: doors change hinge, cabinets their blind side, stairs their turn,
    library objects flip about their own depth axis (``mirror``)."""
    e = doc.get(eid)
    p = e.params
    if e.kind in ('door', 'window'):
        return flip_command(doc, eid, 'hinge')
    if e.kind == 'cabinet' and p.get('cabinet_type') == 'corner_blind':
        return UpdateEntity(eid, {'blind_side': 'right' if p.get('blind_side', 'left') == 'left' else 'left'})
    if e.kind == 'stair' and p.get('layout') in ('l', 'u', 'spiral'):
        return UpdateEntity(eid, {'turn_direction': -1 if int(p.get('turn_direction', 1)) > 0 else 1})
    if e.kind == 'library_object':
        return UpdateEntity(eid, {'mirror': 0.0 if p.get('mirror') else 1.0})
    if e.kind in OWN_ROTATION:
        # Symmetric pieces: the mirror image is the piece turned to face the other way.
        return rotate_command(doc, eid, 180.0)
    return None


def duplicate_command(doc, eid, offset=None):
    """A copy beside the original (to the right along its own X, or 50 cm aside), one undo."""
    ids = [i for i in group_ids(doc, eid) if doc.get(i).kind in USER_PLACED_KINDS]
    if any(doc.get(i).kind in ('door', 'window') for i in ids):
        return None, []
    from archforge.core.model import Entity
    clones = [Entity(doc.get(i).kind, copy.deepcopy(doc.get(i).params), name=doc.get(i).name,
                     parent_id=doc.get(i).parent_id) for i in ids]
    e = doc.get(eid)
    if offset is None:
        if e.kind in OWN_ROTATION:
            a = math.radians(float(e.params.get('rotation', 0.0)))
            step = float(e.params.get('width', .5))
            offset = (math.cos(a) * step, math.sin(a) * step)
        else:
            x0, y0, x1, y1 = _bbox_of([q for i in ids for q in plan_outline(doc, i)] or [(0, 0)])
            offset = (max(.5, x1 - x0 + .2), 0.0)
    for c in clones:
        c.params.pop('layout_id', None)
        c.params.pop('layout_host', None)
    add = AddEntities(clones)
    move = MoveEntities([c.id for c in clones], float(offset[0]), float(offset[1]))
    return CompositeCommand([add, move], label='Διπλασιασμός'), [c.id for c in clones]
