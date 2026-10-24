"""Shared plan/3D presentation of the existing conduit map.

The map remains the source of sizes, bundle contents and quantities. Coincident
pipes are separated schematically so two real pipes do not look like one.
Display offsets are never installation clearances or measured take-off lengths.
Endpoints stay on the source boxes/devices. No Document mutation occurs here.
"""
from __future__ import annotations

import math
from archforge.core.provenance import DESIGN_DEFAULT, Rule, register

register(Rule('electrical.conduit_display', 'Παράλληλες σωληνώσεις διακρίνονται σχηματικά σε κάτοψη και 3D',
              DESIGN_DEFAULT, source='Αίτημα ιδιοκτήτη 23/10: αν έχει δύο, να φαίνονται δύο',
              note='Η απόσταση σχεδίασης δεν είναι κανονιστική απόσταση εγκατάστασης.'))


def _key(point):
    return tuple(round(float(v), 6) for v in point)


def display_pieces(cmap):
    """One display path per actual pipe copy; source endpoints and points retained."""
    pieces = cmap.get('pieces', ())
    members = {(p['conduit'], i) for p in pieces for i in range(int(p['count']))}
    if not members:
        return []
    graph = {key: set() for key in members}
    edges = {}
    # Exact shared grid edges include reversed traversal. Each map path retains
    # the router's grid vertices, rather than replacing bends with a chord.
    for p in pieces:
        for a, b in zip(p['points'], p['points'][1:]):
            if math.dist(a, b) < 1e-9:
                continue
            edge = tuple(sorted((_key(a), _key(b))))
            edges.setdefault(edge, set()).update((p['conduit'], i) for i in range(int(p['count'])))
    for group in edges.values():
        for key in group:
            graph[key].update(group - {key})
    offsets = {}
    unseen = set(members)
    spacing = max(float(p['dn']) for p in pieces) / 1000 * 1.5  # drawing convention only
    while unseen:
        todo = [min(unseen)]; component = set()
        while todo:
            key = todo.pop()
            if key in component:
                continue
            component.add(key); todo.extend(graph[key] - component)
        unseen -= component
        for n, key in enumerate(sorted(component)):
            offsets[key] = (n - (len(component)-1)/2) * spacing
    out = []
    for p in pieces:
        source = tuple(tuple(float(v) for v in q) for q in p['points'])
        for i in range(int(p['count'])):
            shift = offsets[(p['conduit'], i)]
            moved = tuple((x+shift, y+shift, z+shift) for x, y, z in source)
            # Short schematic connections inside the source junction/terminal.
            points = moved if abs(shift)<1e-12 else (source[0],) + moved + (source[-1],)
            out.append(dict(p, pipe_index=i, points=points, source_points=source,
                            display_offset=shift, schematic=abs(shift)>1e-12))
    return out


def display_segments(piece):
    """Drawn segment, source segment, connector flag; both views consume this."""
    src = piece['source_points']; pts = piece['points']
    if piece['schematic']:
        yield pts[0], pts[1], (src[0], src[0]), True
        core = pts[1:-1]
    else:
        core = pts
    for a, b, sa, sb in zip(core, core[1:], src, src[1:]):
        yield a, b, (sa, sb), False
    if piece['schematic']:
        yield pts[-2], pts[-1], (src[-1], src[-1]), True


def circuit_group(piece, wiring):
    groups = {c['id']: c['group'] for c in wiring['circuits']}
    return next((groups[c] for c in piece['lines'] if c in groups), 'switch')


def low_voltage_segments(route, power_pieces=()):
    """Separate schematic rows for network/TV/KNX, above the power rows in plan.

    Actual elevations come from low_voltage/knx routing. Additional row offsets are
    presentation only, identical in the technical plan and 3D preview.
    """
    systems = sorted({r[2] for r in route.get('runs', ())})
    bound = max((abs(p['display_offset']) for p in power_pieces), default=0)
    adj = {}
    for a,b,system,_tid in route.get('runs', ()):
        adj.setdefault((system,_key(a)),set()).add(_key(b))
        adj.setdefault((system,_key(b)),set()).add(_key(a))
    boxes = {_key((x,y,z)) for x,y,z,*_ in route.get('boxes',())}
    connected = set()
    for a,b,system,tid in route.get('runs', ()):
        shift = bound + .12 + systems.index(system)*.06  # schematic row spacing
        rise = bound + systems.index(system)*.06
        aa = (a[0]+shift,a[1]+shift,a[2]+rise); bb = (b[0]+shift,b[1]+shift,b[2]+rise)
        yield aa,bb,system,tid,(a,b),False
        # Only real terminals/boxes, not a connector at every router grid cell.
        for source,moved in ((a,aa),(b,bb)):
            key = (system,_key(source))
            if key not in connected and (len(adj[key])==1 or _key(source) in boxes):
                connected.add(key)
                yield tuple(source),moved,system,tid,(source,source),True
