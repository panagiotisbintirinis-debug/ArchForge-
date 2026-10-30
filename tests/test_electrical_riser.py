"""Owner 29/10: «γιατί οι σωληνώσεις είναι εξωτερικά στον αέρα; δεν μπορεί να ακολουθήσει το κτίριο;»

The panel is on the ground floor; a circuit of the upper storey used to be routed wholly at the upper storey's height,
so it left the storey, crossed the terrace in the air to above the panel and came down there.  Now it runs from the
panel inside the ground-floor walls to a riser in a wall the two storeys share, up inside that wall, then on in the
upper storey's walls — never outside the upper storey up there.
"""
import json
import math
import os

from archforge.core.model import Document
from archforge.mep.electrical import route_cables

FILE = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')


def _doc():
    with open(FILE, encoding='utf-8') as fh:
        return Document.from_dict(json.load(fh))


def _upper_bbox(doc):
    up = [e for e in doc.entities.values() if e.kind == 'wall' and float(e.params.get('z', 0)) >= 2.9]
    xs = [float(w.params[k]) for w in up for k in ('x1', 'x2')]
    ys = [float(w.params[k]) for w in up for k in ('y1', 'y2')]
    return min(xs) - 0.3, max(xs) + 0.3, min(ys) - 0.3, max(ys) + 0.3


def test_upper_storey_cables_stay_inside_the_upper_storey():
    doc = _doc()
    x0, x1, y0, y1 = _upper_bbox(doc)
    routes = route_cables(doc)
    outside = [(a, b, g, c) for a, b, g, c in routes['runs'] if a[2] > 3.0 and b[2] > 3.0
               and not all(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in (a, b))]
    assert outside == []


def test_every_upper_device_is_connected_to_the_panel_through_a_riser_in_a_shared_wall():
    doc = _doc()
    routes = route_cables(doc)
    panel = next(e for e in doc.entities.values() if e.kind == 'electrical_point' and e.params['point_type'] == 'panel')
    key = lambda p: tuple(round(v, 3) for v in p)
    for circuit in routes['circuits']:
        upper = [doc.get(i) for i in circuit['points'] if float(doc.get(i).params['z']) >= 2.9]
        if not upper:
            continue
        runs = [(a, b) for a, b, _g, c in routes['runs'] if c == circuit['id']]
        adj = {}
        for a, b in runs:
            adj.setdefault(key(a), set()).add(key(b))
            adj.setdefault(key(b), set()).add(key(a))
        start = next(k for k in adj if math.isclose(k[0], float(panel.params['x']), abs_tol=0.11)
                     and math.isclose(k[1], float(panel.params['y']), abs_tol=0.11))
        seen, todo = {start}, [start]
        while todo:
            for n in adj[todo.pop()]:
                if n not in seen:
                    seen.add(n); todo.append(n)
        risers = [(a, b) for a, b in runs if math.isclose(a[0], b[0]) and math.isclose(a[1], b[1])
                  and min(a[2], b[2]) < 3.0 < max(a[2], b[2])]
        assert risers, circuit['id']
        for a, b in risers:      # the riser stands in a wall of both storeys
            for floor in (0.0, 3.0):
                walls = [w for w in doc.entities.values() if w.kind == 'wall' and abs(float(w.params.get('z', 0)) - floor) < 0.05]
                assert min(_dist(w, a[0], a[1]) for w in walls) <= 0.2, (circuit['id'], a, floor)
        reached = {n for n in seen if n[2] > 3.0}
        assert reached, circuit['id']


def _dist(w, x, y):
    p = w.params
    x1, y1, x2, y2 = (float(p[k]) for k in ('x1', 'y1', 'x2', 'y2'))
    dx, dy = x2 - x1, y2 - y1
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / ((dx * dx + dy * dy) or 1.0)))
    return math.hypot(x - x1 - t * dx, y - y1 - t * dy)
