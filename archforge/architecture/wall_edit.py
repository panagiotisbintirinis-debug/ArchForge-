"""Walls that move and split, keeping everything that hangs on them.

Owner (2026-10-08): «Τα στοιχεία να προσαρμόζονται εάν μετακινήσω ένα τοίχο·
όλοι οι τοίχοι πρέπει να είναι μετακινήσιμοι. Η δημιουργία ενός μεσοκάθετου σε
ένα τοίχο αυτόματα διαχωρίζει τον τοίχο αυτό σε μικρότερα κομμάτια.»

Moving a wall (perpendicular to its axis):
- the whole straight run moves (collinear walls joined end to end — an 8 m wall
  split by a partition is still one line on site);
- walls joined at its corners (L) or ending on it (T) stretch along their own
  axis and stay joined; walls it ends on keep their place, its end slides on them;
- its doors/windows go with it, those of the stretched walls stay where they are;
- cabinets, fixtures, MEP points and library objects whose side touches a face
  of it (≤ 5 cm) go with it;
- rooms keep their ids (their signature is made of wall ids, which do not change).

Splitting (T junction or crossing): the wall touched in its body becomes two
walls at the axis of the new one.  Each piece is a copy of the original (type,
thickness, height, finishes per side, phase…) and independent afterwards.
Openings go to the piece they sit on; an opening on the junction is left alone
and the wall is not split there (a warning, never a silent loss).

Both are single commands; the UI amends the split into the wall's own undo step.
"""
from __future__ import annotations

import copy
import math
import uuid

from archforge.core.commands import Command, _restore_document_state

JOIN = 1e-3            # wall ends closer than this are one junction (m)
ON_AXIS = 1e-3         # a wall end this close to another wall's axis is a T
MIN_PIECE = 0.05       # shortest wall piece a split or a move may leave (m)
TOUCH = 0.05           # objects whose side is this close to a wall face ride along (m)

# Things that stand against a wall (kitchen, fixtures, MEP points, library objects).
RIDING_KINDS = ('cabinet', 'kitchen_part', 'library_object', 'box', 'plumbing_point', 'electrical_point',
                'ventilation_point', 'drainage_point', 'mep_terminal')
POINT_KINDS = ('plumbing_point', 'electrical_point', 'ventilation_point', 'drainage_point', 'mep_terminal')
OPENING_KINDS = ('door', 'window', 'opening')


def _ends(p):
    return (float(p['x1']), float(p['y1'])), (float(p['x2']), float(p['y2']))


def _walls(doc, z):
    return [e for e in doc.entities.values()
            if e.kind == 'wall' and e.visible and abs(float(e.params.get('z', 0.0)) - z) <= 1e-4]


def _on_body(q, a, b, margin=MIN_PIECE / 2, tol=ON_AXIS):
    """Distance along a→b when q lies on that axis away from its ends, else None."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L <= 1e-9:
        return None
    t = ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / L
    off = abs((q[0] - a[0]) * dy - (q[1] - a[1]) * dx) / L
    if off <= tol and margin < t < L - margin:
        return t
    return None


def _line_hit(a1, a2, b1, b2):
    """Intersection of the infinite lines a1a2 and b1b2, or None when parallel."""
    d = (a1[0] - a2[0]) * (b1[1] - b2[1]) - (a1[1] - a2[1]) * (b1[0] - b2[0])
    if abs(d) < 1e-9 * max(1.0, math.dist(a1, a2) * math.dist(b1, b2)):
        return None
    t = ((a1[0] - b1[0]) * (b1[1] - b2[1]) - (a1[1] - b1[1]) * (b1[0] - b2[0])) / d
    return (a1[0] + t * (a2[0] - a1[0]), a1[1] + t * (a2[1] - a1[1]))


def _openings(doc, wid):
    return [doc.get(i) for i in doc.children.get(wid, ()) if i in doc.entities and doc.get(i).kind in OPENING_KINDS]


def _label(e):
    return {'door': 'η πόρτα', 'window': 'το παράθυρο'}.get(e.kind, 'το άνοιγμα')


# ---------------------------------------------------------------- moving

def straight_run(doc, wid):
    """The wall and the collinear walls joined to it end to end (one straight line on site)."""
    w = doc.get(wid)
    z = float(w.params.get('z', 0.0))
    a, b = _ends(w.params)
    L = math.dist(a, b)
    if L <= 1e-9:
        return [wid]
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    walls = [o for o in _walls(doc, z)]

    def on_line(q):
        return abs((q[0] - a[0]) * uy - (q[1] - a[1]) * ux) <= JOIN

    run = [wid]
    frontier = [wid]
    while frontier:
        cur = doc.get(frontier.pop())
        ce = _ends(cur.params)
        for o in walls:
            if o.id in run:
                continue
            oe = _ends(o.params)
            if not (on_line(oe[0]) and on_line(oe[1])):
                continue
            if any(math.dist(p, q) <= JOIN for p in ce for q in oe):
                run.append(o.id)
                frontier.append(o.id)
    return run


def is_joined(doc, wid):
    """True when another wall meets this one (shared end, T or crossing)."""
    w = doc.get(wid)
    a, b = _ends(w.params)
    for o in _walls(doc, float(w.params.get('z', 0.0))):
        if o.id == wid:
            continue
        oa, ob = _ends(o.params)
        if any(math.dist(p, q) <= JOIN for p in (a, b) for q in (oa, ob)):
            return True
        if any(_on_body(q, oa, ob, margin=0.0) is not None for q in (a, b)) or \
                any(_on_body(q, a, b, margin=0.0) is not None for q in (oa, ob)):
            return True
    return False


def wall_normal(params):
    """Unit normal of a wall, pointing right or up on the plan (the + side of a move)."""
    a, b = _ends(params)
    L = math.dist(a, b)
    if L <= 1e-9:
        raise ValueError('ο τοίχος έχει μηδενικό μήκος')
    nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
    if nx < -1e-9 or (abs(nx) <= 1e-9 and ny < 0):
        nx, ny = -nx, -ny
    return nx, ny


def _footprint(e):
    p = e.params
    if e.kind in POINT_KINDS:
        return [(float(p['x']), float(p['y']))]
    if e.kind == 'cabinet':
        from archforge.kitchen.cabinets import footprint
        return footprint(p)
    from archforge.library.objects import footprint
    return footprint(p)


def _touches(e, a, b, half):
    """True when the object stands against a face of the wall a→b (thickness 2·half)."""
    try:
        pts = _footprint(e)
    except (KeyError, TypeError, ValueError):
        return False
    L = math.dist(a, b)
    if L <= 1e-9:
        return False
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    s = [(q[0] - a[0]) * -uy + (q[1] - a[1]) * ux for q in pts]
    t = [(q[0] - a[0]) * ux + (q[1] - a[1]) * uy for q in pts]
    if max(t) < 0.01 or min(t) > L - 0.01:
        return False
    if e.kind in POINT_KINDS:
        return abs(s[0]) <= half + TOUCH
    if min(s) >= 0:
        gap = min(s) - half
    elif max(s) <= 0:
        gap = -max(s) - half
    else:
        return False                                   # straddles the wall: not standing against it
    return -0.02 <= gap <= TOUCH


def plan_move(doc, wid, distance):
    """What changes when wall ``wid`` moves ``distance`` m along ``wall_normal``.

    Returns ``{'walls': {id: {x1,y1,x2,y2}}, 'openings': {id: offset}, 'objects': {id: {x,y}}, 'run': [...]}``
    or raises ValueError (Greek, for the status bar) when the move would break something.
    """
    w = doc.get(wid)
    if w.kind != 'wall':
        raise ValueError('μετακίνηση τοίχου: δεν είναι τοίχος')
    z = float(w.params.get('z', 0.0))
    nx, ny = wall_normal(w.params)
    dx, dy = nx * float(distance), ny * float(distance)
    run = straight_run(doc, wid)
    others = [o for o in _walls(doc, z) if o.id not in run]
    for rid in run:
        if str(doc.get(rid).params.get('phase', 'new')) == 'existing':
            raise ValueError('υφιστάμενος τοίχος (ανακαίνιση): δεν μετακινείται — σήμανέ τον «Καθαίρεση» και σχεδίασε νέο')
        if doc.get(rid).locked:
            raise ValueError('ο τοίχος είναι κλειδωμένος')
    old = {o.id: _ends(o.params) for o in [doc.get(r) for r in run] + others}
    a0, b0 = old[wid]
    moved_line = ((a0[0] + dx, a0[1] + dy), (b0[0] + dx, b0[1] + dy))

    new = {}
    for rid in run:
        ends = []
        for p in old[rid]:
            q = (p[0] + dx, p[1] + dy)
            slide = follow = None
            for o in others:
                oa, ob = old[o.id]
                if math.dist(p, oa) <= JOIN or math.dist(p, ob) <= JOIN:
                    follow = follow or o
                elif _on_body(p, oa, ob, margin=0.0) is not None:
                    slide = slide or o
            partner = slide or follow
            if partner is not None:
                hit = _line_hit(*moved_line, *old[partner.id])
                if hit is not None:
                    q = hit
            ends.append(q)
        new[rid] = ends

    for o in others:
        ends = list(old[o.id])
        changed = False
        for k, q in enumerate(old[o.id]):
            attached = False
            for rid in run:
                ra, rb = old[rid]
                if math.dist(q, ra) <= JOIN or math.dist(q, rb) <= JOIN or _on_body(q, ra, rb, margin=0.0) is not None:
                    attached = True
                    break
            if not attached:
                continue
            hit = _line_hit(*old[o.id], *moved_line)
            ends[k] = hit if hit is not None else (q[0] + dx, q[1] + dy)
            changed = True
        if changed:
            if str(o.params.get('phase', 'new')) == 'existing':
                raise ValueError('ο τοίχος είναι ενωμένος με υφιστάμενο τοίχο (ανακαίνιση), που δεν αλλάζει μήκος')
            new[o.id] = ends

    walls, openings = {}, {}
    for eid, (na, nb) in new.items():
        oa, ob = old[eid]
        L0 = math.dist(oa, ob)
        L1 = math.dist(na, nb)
        ux, uy = (ob[0] - oa[0]) / L0, (ob[1] - oa[1]) / L0
        if L1 < MIN_PIECE or ((nb[0] - na[0]) * ux + (nb[1] - na[1]) * uy) <= 0:
            raise ValueError('η μετακίνηση μηδενίζει έναν συνδεδεμένο τοίχο — μικρότερη απόσταση')
        walls[eid] = {'x1': na[0], 'y1': na[1], 'x2': nb[0], 'y2': nb[1]}
        # Doors and windows keep their place on the wall (moved ones ride with it).
        along = (na[0] - oa[0] - (dx if eid in run else 0.0)) * ux + (na[1] - oa[1] - (dy if eid in run else 0.0)) * uy
        for op in _openings(doc, eid):
            off = float(op.params['offset']) - along
            half = float(op.params['width']) / 2
            if off - half < -1e-9 or off + half > L1 + 1e-9:
                raise ValueError(f'{_label(op)} δεν χωράει πια στον τοίχο που κονταίνει — μικρότερη απόσταση ή μετακίνησέ το πρώτα')
            if abs(along) > 1e-12:
                openings[op.id] = off

    objects = {}
    for e in doc.entities.values():
        if e.kind not in RIDING_KINDS or not e.visible or e.locked:
            continue
        ez = float(e.params.get('z', z)) if e.kind != 'mep_terminal' else z
        if not (z - 0.6 <= ez <= z + float(w.params.get('height', 3.0)) + 0.05):
            continue
        for rid in run:
            ra, rb = old[rid]
            if _touches(e, ra, rb, float(doc.get(rid).params['thickness']) / 2):
                objects[e.id] = {'x': float(e.params['x']) + dx, 'y': float(e.params['y']) + dy}
                break
    return {'walls': walls, 'openings': openings, 'objects': objects, 'run': run}


class MoveWall(Command):
    """Move a wall perpendicular to its axis with everything joined to it (one undo step)."""

    def __init__(self, wall_id, distance):
        self.wall_id = str(wall_id)
        self.distance = float(distance)
        self.plan = None
        self.before_state = None
        self.before_selection = None

    def do(self, doc):
        if self.plan is None:
            self.plan = plan_move(doc, self.wall_id, self.distance)
            self.before_state = copy.deepcopy(doc.to_dict())
            self.before_selection = list(doc.selection)
        try:
            _apply(doc, self.plan)
        except Exception:
            _restore_document_state(doc, self.before_state, self.before_selection or [])
            raise

    def undo(self, doc):
        if self.before_state is not None:
            _restore_document_state(doc, self.before_state, self.before_selection or [])


def _apply(doc, plan):
    # Offsets first (raw), so each wall validates its openings against its new length.
    for oid, off in plan['openings'].items():
        doc.get(oid).params['offset'] = float(off)
    for eid, changes in plan['walls'].items():
        doc.update(eid, changes)
    for oid, off in plan['openings'].items():
        doc.update(oid, {'offset': float(off)})
    for eid, changes in plan['objects'].items():
        doc.update(eid, changes)


class WallMoveTransaction:
    """Drag a wall's body: it moves perpendicular to its axis; preview, then one MoveWall."""

    def __init__(self, doc, stack, eid, x, y, step=0.01):
        self.doc, self.stack, self.eid = doc, stack, str(eid)
        if eid not in doc.entities or doc.get(eid).kind != 'wall':
            raise ValueError('μετακίνηση τοίχου: δεν είναι τοίχος')
        self.start = (float(x), float(y))
        self.normal = wall_normal(doc.get(eid).params)
        self.step = float(step)
        self.distance = 0.0
        self.plan = {'walls': {}, 'openings': {}, 'objects': {}, 'run': [self.eid]}
        self.problem = None
        self.cancelled = False

    def update(self, x, y):
        d = (float(x) - self.start[0]) * self.normal[0] + (float(y) - self.start[1]) * self.normal[1]
        if self.step > 0:
            d = round(d / self.step) * self.step
        self.distance = d
        try:
            self.plan = plan_move(self.doc, self.eid, d)
            self.problem = None
        except ValueError as exc:
            self.problem = str(exc)
        return self.preview()

    def preview(self):
        """Plan preview: moved/stretched wall lines, riding objects and the distance mark."""
        walls = {}
        for eid in set(self.plan['walls']) | set(self.plan['run']):
            p = dict(self.doc.get(eid).params)
            p.update(self.plan['walls'].get(eid, {}))
            walls[eid] = {k: p[k] for k in ('x1', 'y1', 'x2', 'y2', 'thickness')}
        openings = []
        for eid, p in walls.items():
            a, b = _ends(p)
            L = math.dist(a, b)
            for op in _openings(self.doc, eid) if L > 1e-9 else ():
                c = float(self.plan['openings'].get(op.id, op.params['offset']))
                h = float(op.params['width']) / 2
                openings.append(tuple((a[0] + (b[0] - a[0]) * u / L, a[1] + (b[1] - a[1]) * u / L) for u in (c - h, c + h)))
        objects = {}
        for oid, xy in self.plan['objects'].items():
            try:
                e = self.doc.get(oid)
                q = copy.deepcopy(e)
                q.params.update(xy)
                objects[oid] = _footprint(q)
            except (KeyError, ValueError):
                continue
        a, b = _ends(self.doc.get(self.eid).params)
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        n = self.normal
        to = (mid[0] + n[0] * self.distance, mid[1] + n[1] * self.distance)
        return {'walls': walls, 'openings': openings, 'objects': objects, 'from': mid, 'to': to,
                'distance': self.distance, 'problem': self.problem}

    def commit(self):
        if self.cancelled:
            raise RuntimeError('transaction cancelled')
        if self.problem:
            raise ValueError(self.problem)
        if abs(self.distance) < 1e-9:
            return None
        self.stack.execute(MoveWall(self.eid, self.distance))
        return self.eid

    def cancel(self):
        self.cancelled = True


# ---------------------------------------------------------------- splitting

def junction_cuts(doc, wid):
    """Where walls must split because of wall ``wid``: ``({wall_id: [distance along it]}, [warnings])``.

    A T (an end on the body of another wall) splits the other wall; a crossing
    splits both.  A cut that would fall on a door/window is skipped with a warning.
    """
    if wid not in doc.entities or doc.get(wid).kind != 'wall':
        return {}, []
    w = doc.get(wid)
    z = float(w.params.get('z', 0.0))
    wa, wb = _ends(w.params)
    cuts = {}
    for o in _walls(doc, z):
        if o.id == wid:
            continue
        oa, ob = _ends(o.params)
        for q in (wa, wb):                              # the new wall ends on o's body
            t = _on_body(q, oa, ob)
            if t is not None:
                cuts.setdefault(o.id, []).append((t, wid))
        for q in (oa, ob):                              # o ends on the new wall's body
            t = _on_body(q, wa, wb)
            if t is not None:
                cuts.setdefault(wid, []).append((t, o.id))
        hit = _line_hit(wa, wb, oa, ob)
        if hit is not None:                             # a crossing, away from every end
            t_w = _on_body(hit, wa, wb)
            t_o = _on_body(hit, oa, ob)
            if t_w is not None and t_o is not None:
                cuts.setdefault(wid, []).append((t_w, o.id))
                cuts.setdefault(o.id, []).append((t_o, wid))
    out, warnings = {}, []
    for host, items in cuts.items():
        ops = _openings(doc, host)
        keep = []
        for t, by in sorted(items):
            if keep and abs(t - keep[-1]) <= JOIN:
                continue
            margin = float(doc.get(by).params.get('thickness', 0.0)) / 2
            hit = next((op for op in ops
                        if float(op.params['offset']) - float(op.params['width']) / 2 - margin < t
                        < float(op.params['offset']) + float(op.params['width']) / 2 + margin), None)
            if hit is not None:
                warnings.append(f'⚠ {_label(hit).capitalize()} πέφτει πάνω στη συμβολή των τοίχων — '
                                f'ο τοίχος δεν χωρίστηκε εκεί· μετακίνησε {"την" if hit.kind == "door" else "το"} και ξανασχεδίασε')
                continue
            keep.append(t)
        if keep:
            out[host] = keep
    return out, warnings


class SplitWalls(Command):
    """Split walls at given distances along them; each piece copies the original wall."""

    def __init__(self, cuts):
        self.cuts = {str(k): sorted(float(t) for t in v) for k, v in dict(cuts).items() if v}
        self.pieces = None                              # {host: [new ids]} fixed on the first do (redo keeps ids)
        self.before_state = None
        self.before_selection = None

    def do(self, doc):
        if self.before_state is None:
            self.before_state = copy.deepcopy(doc.to_dict())
            self.before_selection = list(doc.selection)
        if self.pieces is None:
            self.pieces = {h: [str(uuid.uuid4()) for _ in ts] for h, ts in self.cuts.items()}
        try:
            for host, ts in self.cuts.items():
                _split_one(doc, host, ts, self.pieces[host])
        except Exception:
            _restore_document_state(doc, self.before_state, self.before_selection or [])
            raise

    def undo(self, doc):
        if self.before_state is not None:
            _restore_document_state(doc, self.before_state, self.before_selection or [])

    @property
    def new_ids(self):
        return [i for ids in (self.pieces or {}).values() for i in ids]


def _split_one(doc, host_id, ts, new_ids):
    from archforge.core.model import Entity
    host = doc.get(host_id)
    a, b = _ends(host.params)
    L = math.dist(a, b)
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    bounds = [0.0] + list(ts) + [L]
    point = lambda t: (a[0] + ux * t, a[1] + uy * t)
    openings = _openings(doc, host_id)
    # Dependants of the wall other than its own openings (room slabs …) depend on every piece.
    deps = [d for d in doc.dependencies.get(host_id, ()) if d not in {op.id for op in openings}]
    for k, nid in enumerate(new_ids, start=1):
        p0, p1 = point(bounds[k]), point(bounds[k + 1])
        params = copy.deepcopy(host.params)
        params.update({'x1': p0[0], 'y1': p0[1], 'x2': p1[0], 'y2': p1[1]})
        doc.add(Entity('wall', params, name=host.name, id=nid, locked=host.locked, visible=host.visible))
        for d in deps:
            if d in doc.entities:
                doc.add_dependency(nid, d)
    # Openings to the piece they sit on, same place in the world.
    for op in openings:
        c = float(op.params['offset'])
        k = max(i for i in range(len(bounds) - 1) if c >= bounds[i]) if c >= 0 else 0
        if k == 0:
            continue
        _reparent(doc, op.id, new_ids[k - 1], c - bounds[k])
    p1 = point(bounds[1])
    doc.update(host_id, {'x2': p1[0], 'y2': p1[1]})
    # A flat roof's per-wall edge offset holds for every piece of that wall.
    for e in list(doc.entities.values()):
        offsets = e.params.get('edge_offsets') if e.kind == 'room_roof' else None
        if offsets and host_id in offsets:
            merged = dict(offsets)
            merged.update({nid: offsets[host_id] for nid in new_ids})
            doc.update(e.id, {'edge_offsets': merged})


def _reparent(doc, oid, new_host, offset):
    e = doc.get(oid)
    old = e.parent_id
    doc._deindex_entity(e)
    if old in doc.children and oid in doc.children[old]:
        doc.children[old].remove(oid)
    doc.dependencies.get(old, set()).discard(oid)
    e.parent_id = new_host
    doc.children.setdefault(new_host, []).append(oid)
    doc._index_entity(e)
    doc.add_dependency(new_host, oid)
    doc.update(oid, {'offset': float(offset)})


def split_at_point(doc, wid, x, y):
    """Cuts for splitting wall ``wid`` by hand at the point nearest (x, y)."""
    a, b = _ends(doc.get(wid).params)
    L = math.dist(a, b)
    t = ((x - a[0]) * (b[0] - a[0]) + (y - a[1]) * (b[1] - a[1])) / L
    t = round(t, 3)
    if not (MIN_PIECE < t < L - MIN_PIECE):
        raise ValueError('κοντά στην άκρη του τοίχου — κλικ πιο μέσα για διαχωρισμό')
    for op in _openings(doc, wid):
        if float(op.params['offset']) - float(op.params['width']) / 2 < t < float(op.params['offset']) + float(op.params['width']) / 2:
            raise ValueError(f'{_label(op).capitalize()} είναι σε αυτό το σημείο — διαχωρισμός δίπλα του')
    return {wid: [t]}
