"""Semantic site terrain: a planar-graded ground solid around the building.

The terrain is an authoritative Document entity (``kind='terrain'``):

- ``x0, y0, x1, y1``: plan extent of the site (metres)
- ``elevation``: ground level at (x0, y0); default 0.15 m below Ground
- ``slope_x`` / ``slope_y``: grade in percent along +x / +y
- ``thickness``: depth of the ground solid below its lowest point
- ``points``: optional elevation data ``[[x, y, z], ...]``; the ground
  passes exactly through each point and blends back to the graded plane
  within ``blend_radius`` (default 6 m)
- ``levels``: terrace levels ``[[x, y, z], ...]`` (a drawing's «F.L.»): flat around each, up to the walls
  that hold them — the ground steps at a retaining wall, slopes through a gap between two levels
- ``regions``: closed elevation shapes, constant inside their perimeter,
  blending into the surrounding field over their ``transition`` distance
- ``strokes``: sculpt strokes ``[{"x", "y", "radius", "dz", "sharp"}, ...]`` (owner 29/10: Γλυπτική on the ground):
  each raises (``dz`` > 0) or lowers the ground by ``dz`` at its centre, fading smoothly to 0 at ``radius``;
  added on top of everything above, in order, so plan contours, sections and 3D read the same ground

The base field is ``elevation + slope_x% * (x - x0) + slope_y% * (y - y0)``.
The preview samples this deterministic field; closed building footprints
and wall strips are subtracted before tessellation, including basement walls.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

DEFAULT_ELEVATION = -0.15
DEFAULT_THICKNESS = 0.50
DEFAULT_MARGIN = 5.0


DEFAULT_BLEND_RADIUS = 6.0


def _plane_height(params: Dict, x: float, y: float) -> float:
    x0 = float(params['x0']); y0 = float(params['y0'])
    return (
        float(params.get('elevation', DEFAULT_ELEVATION))
        + float(params.get('slope_x', 0.0)) / 100.0 * (float(x) - x0)
        + float(params.get('slope_y', 0.0)) / 100.0 * (float(y) - y0)
    )


def _point_height(params: Dict, x: float, y: float) -> float:
    """Graded plane plus a local, exact correction from elevation points."""
    base = _plane_height(params, x, y)
    points = params.get('points') or ()
    if not points:
        return base
    radius = max(0.5, float(params.get('blend_radius', DEFAULT_BLEND_RADIUS)))
    num = 0.0; den = 1.0 / (radius * radius)
    for px, py, pz in points:
        d = math.hypot(float(x) - float(px), float(y) - float(py))
        if d < 1e-9:
            return float(pz)
        if d >= radius:
            continue
        w = (1.0 - d / radius) ** 2 / (d * d)
        num += w * (float(pz) - _plane_height(params, px, py)); den += w
    return base + num / den


# --- Terrace levels, held by walls (owner 22/10: the masterplan is terraces at written levels held by retaining
# walls).  ``levels`` [[x, y, z]] are finished levels of terraces («+137.10m [F.L.]»), apart from the survey
# ``points`` (which keep their smooth, local blend).  A level reaches the ground it «sees»: the line from it to a place crossing no wall.  So a terrace with
# one level is flat at it, the ground behind its retaining wall takes the next terrace's level — the step is at
# the wall — and through a stair or a gap two levels meet in a slope.  Nothing has to be closed or traced.
BARRIER_REACH = 12.0     # m — how far a written level holds its terrace
BARRIER_POWER = 4        # Shepard power: flat around each level, the change half-way between two


def barriers(doc):
    """What holds the ground: the visible walls' axes in plan ``(x1, y1, x2, y2)``."""
    return [(float(e.params['x1']), float(e.params['y1']), float(e.params['x2']), float(e.params['y2']))
            for e in doc.entities.values() if e.kind == 'wall' and e.visible]


GREEN_SOIL = 0.10        # m — least soil on a green roof (the NEW VILLA's layers 3,60 → 3,70)


def green_roofs(doc):
    """Roofs under the ground (φυτεμένο δώμα / υπόσκαφο): ``[(outline, lowest ground)]`` — the ground is not cut
    there and never comes lower than the slab's top plus its soil."""
    from archforge.architecture.storey_slabs import storey_slab_geometry
    out = []
    for e in doc.entities.values():
        if e.kind != 'room_roof' or not e.visible or not int(e.params.get('green', 0)):
            continue
        try:
            if e.params.get('scope') == 'storey':
                g = storey_slab_geometry(doc, e)
            else:
                from archforge.architecture.rooms import room_slab_geometry
                g = room_slab_geometry(doc, e)
        except Exception as exc:
            from archforge.core.notices import not_computed
            not_computed('site.terrain_slab', f'Έδαφος: η πλάκα «{e.name or e.id}» δεν λήφθηκε υπόψη', e.id, exc)
            g = None
        if not g:
            continue
        top = float(g['z']) + float(g['thickness'])
        soil = float(e.params.get('soil', GREEN_SOIL))
        for outer, _holes in g.get('islands') or [(g['points'], [])]:
            out.append(([tuple(map(float, q)) for q in outer], top + soil))
    return out


def _zone(x, y, zones):
    from archforge.geometry.regions import point_in_polygon
    return next((k for k, z in enumerate(zones) if point_in_polygon(x, y, z)), -1)


def _walled_heights(params, xs, ys, walls, zones=()):
    """Heights at (xs, ys) (numpy arrays) where the terrace levels (``levels``) are seen past the walls ``walls``.
    ``(heights, weight)``: weight 1 near a seen level, 0 where none is within reach (the open field rules)."""
    import numpy as np
    pts = [(float(a), float(b), float(c)) for a, b, c in (params.get('levels') or ())]
    n = len(xs)
    num = np.zeros(n); den = np.zeros(n); nearest = np.full(n, np.inf); exact = np.full(n, np.nan)
    W = np.asarray([tuple(w)[:4] for w in walls], float).reshape(-1, 4)
    # A green roof is its own ground: the soil the drawing writes on it is seen only on it (over the building's
    # walls), and the ground around it never takes it (the terrace in front of a buried house stays down).
    from archforge.geometry.regions import point_in_polygon
    zq = np.array([_zone(x, y, zones) for x, y in zip(xs, ys)]) if zones else np.full(n, -1)
    for px, py, pz in pts:
        zp = _zone(px, py, zones) if zones else -1
        dx, dy = xs - px, ys - py
        d = np.hypot(dx, dy)
        near = (d < BARRIER_REACH) & (zq == zp)
        if not near.any():
            continue
        idx = np.nonzero(near)[0]
        qx, qy = xs[idx], ys[idx]
        seen = np.ones(len(idx), bool)
        if len(W) and zp < 0:
            box = ((np.minimum(W[:, 0], W[:, 2]) <= px + BARRIER_REACH) & (np.maximum(W[:, 0], W[:, 2]) >= px - BARRIER_REACH) &
                   (np.minimum(W[:, 1], W[:, 3]) <= py + BARRIER_REACH) & (np.maximum(W[:, 1], W[:, 3]) >= py - BARRIER_REACH))
            for ax, ay, bx, by in W[box]:
                # Proper crossing of [q, p] and [a, b]: each segment's ends on both sides of the other.
                d1 = (bx - ax) * (qy - ay) - (by - ay) * (qx - ax)
                d2 = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
                d3 = (px - qx) * (ay - qy) - (py - qy) * (ax - qx)
                d4 = (px - qx) * (by - qy) - (py - qy) * (bx - qx)
                seen &= ~((d1 * d2 < 0) & (d3 * d4 < 0))
        k = idx[seen]
        dk = d[k]
        hit = dk < 1e-9
        exact[k[hit]] = pz
        w = 1.0 / np.maximum(dk, 1e-9) ** BARRIER_POWER
        num[k] += w * pz; den[k] += w
        nearest[k] = np.minimum(nearest[k], dk)
    h = np.where(den > 0, num / np.where(den > 0, den, 1.0), 0.0)
    h = np.where(np.isnan(exact), h, exact)
    weight = np.clip((BARRIER_REACH - nearest) / 2.0, 0.0, 1.0)
    return h, weight


def stroke_falloff(distance: float, radius: float, sharp: bool = False) -> float:
    """1 at the centre → 0 at ``radius``, smooth (cosine); ``sharp`` = squared (a crease)."""
    if radius <= 0 or distance >= radius:
        return 0.0
    w = 0.5 * (1.0 + math.cos(math.pi * distance / radius))
    return w * w if sharp else w


def stroke_offset(params: Dict, x: float, y: float) -> float:
    """Height the sculpt ``strokes`` add at (x, y)."""
    total = 0.0
    for s in params.get('strokes') or ():
        r = float(s.get('radius', 0.0))
        d = math.hypot(float(x) - float(s['x']), float(y) - float(s['y']))
        if d < r:
            total += float(s.get('dz', 0.0)) * stroke_falloff(d, r, bool(s.get('sharp')))
    return total


def stroke_extent(params: Dict):
    """Plan box (x0, y0, x1, y1) of all strokes, or None."""
    strokes = params.get('strokes') or ()
    if not strokes:
        return None
    return (min(float(s['x']) - float(s['radius']) for s in strokes), min(float(s['y']) - float(s['radius']) for s in strokes),
            max(float(s['x']) + float(s['radius']) for s in strokes), max(float(s['y']) + float(s['radius']) for s in strokes))


def terrain_heights(params: Dict, xy, walls=None, floors=None):
    """``terrain_height`` at many points at once (the 3D grid); ``walls``: what holds the ground (``barriers``);
    ``floors``: green roofs ``[(outline, lowest)]`` the ground covers (``green_roofs``)."""
    from .elevation_regions import blended_height
    base = [_point_height(params, x, y) for x, y in xy]
    if params.get('levels') and xy:
        import numpy as np
        xs = np.array([p[0] for p in xy], float); ys = np.array([p[1] for p in xy], float)
        h, w = _walled_heights(params, xs, ys, walls or [], [outline for outline, _lowest in floors or ()])
        base = [float(wi * hi + (1.0 - wi) * b) for b, hi, wi in zip(base, h, w)]
    out = [blended_height(params, float(x), float(y), b) + stroke_offset(params, x, y) for (x, y), b in zip(xy, base)]
    if floors:
        from archforge.geometry.regions import point_in_polygon
        for k, (x, y) in enumerate(xy):
            for outline, lowest in floors:
                if out[k] < lowest and point_in_polygon(x, y, outline):
                    out[k] = lowest
    return out


def terrain_height(params: Dict, x: float, y: float, walls=None, floors=None) -> float:
    """Same height field for 3D, plan annotations, site elements and sections."""
    from .elevation_regions import blended_height
    if params.get('levels') or floors:
        return terrain_heights(params, [(float(x), float(y))], walls or [], floors)[0]
    return blended_height(params, float(x), float(y), _point_height(params,x,y)) + stroke_offset(params, x, y)


def terrain_contains(params: Dict, x: float, y: float) -> bool:
    return (
        float(params['x0']) <= float(x) <= float(params['x1'])
        and float(params['y0']) <= float(y) <= float(params['y1'])
    )


def terrain_height_at(doc, x: float, y: float):
    """Ground height under (x, y) from the site terrain, or None."""
    for entity in doc.entities.values():
        if entity.kind == 'terrain' and entity.visible and terrain_contains(entity.params, x, y):
            return terrain_height(entity.params, x, y, barriers(doc), green_roofs(doc))
    return None


def default_terrain_params(doc, margin: float = DEFAULT_MARGIN) -> Dict:
    """Site around the walls' extent (or 20 x 20 m around the origin)."""
    xs: List[float] = []; ys: List[float] = []
    for entity in doc.entities.values():
        if entity.kind == 'wall':
            p = entity.params
            xs += [float(p['x1']), float(p['x2'])]; ys += [float(p['y1']), float(p['y2'])]
    if xs:
        x0, x1, y0, y1 = min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin
    else:
        x0, x1, y0, y1 = -10.0, 10.0, -10.0, 10.0
    return {
        'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
        'elevation': DEFAULT_ELEVATION, 'slope_x': 0.0, 'slope_y': 0.0,
        'thickness': DEFAULT_THICKNESS,
    }


def _stroke_cell(params: Dict, cell: float) -> float:
    """Fine enough for the smallest stroke to show its shape (4 cells across its radius), never below 0.15 m."""
    radii = [float(s.get('radius', 0.0)) for s in params.get('strokes') or () if float(s.get('radius', 0.0)) > 0]
    return max(0.15, min([cell] + [r / 4.0 for r in radii]))


def terrain_mesh(params: Dict, cell: float | None = None, exclusions=(), walls=None, floors=None):
    """Closed ground solid: graded top grid, flat bottom, four sides (``walls`` holding the ground, ``floors`` the
    green roofs it covers)."""
    if exclusions or params.get('regions') or walls or floors:
        return _region_mesh(params,cell,exclusions,walls,floors)
    x0, y0, x1, y1 = (float(params[k]) for k in ('x0', 'y0', 'x1', 'y1'))
    if x1 - x0 <= 1e-6 or y1 - y0 <= 1e-6:
        raise ValueError('terrain extent must be positive')
    if cell is None:
        cell = _stroke_cell(params, 0.5 if params.get('points') else 1.0)
    nx = max(1, min(120, int(math.ceil((x1 - x0) / cell))))
    ny = max(1, min(120, int(math.ceil((y1 - y0) / cell))))
    lowest = min(
        terrain_height(params, x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny)
        for i in range(nx + 1) for j in range(ny + 1)
    )
    bottom = lowest - max(0.05, float(params.get('thickness', DEFAULT_THICKNESS)))
    verts: List[Tuple[float, float, float]] = []
    index: Dict[Tuple, int] = {}

    def vid(i, j, top):
        key = (i, j, top)
        if key not in index:
            x = x0 + (x1 - x0) * i / nx; y = y0 + (y1 - y0) * j / ny
            index[key] = len(verts)
            verts.append((x, y, terrain_height(params, x, y) if top else bottom))
        return index[key]

    tris: List[Tuple[int, int, int]] = []; roles: List[str] = []

    def quad(a, b, c, d, role):
        tris.extend(((a, b, c), (a, c, d))); roles.extend((role, role))

    for i in range(nx):
        for j in range(ny):
            quad(vid(i, j, True), vid(i + 1, j, True), vid(i + 1, j + 1, True), vid(i, j + 1, True), 'top')
            quad(vid(i, j, False), vid(i, j + 1, False), vid(i + 1, j + 1, False), vid(i + 1, j, False), 'bottom')
    for i in range(nx):  # south (y0) and north (y1)
        quad(vid(i, 0, False), vid(i + 1, 0, False), vid(i + 1, 0, True), vid(i, 0, True), 'side')
        quad(vid(i + 1, ny, False), vid(i, ny, False), vid(i, ny, True), vid(i + 1, ny, True), 'side')
    for j in range(ny):  # west (x0) and east (x1)
        quad(vid(0, j + 1, False), vid(0, j, False), vid(0, j, True), vid(0, j + 1, True), 'side')
        quad(vid(nx, j, False), vid(nx, j + 1, False), vid(nx, j + 1, True), vid(nx, j, True), 'side')
    return tuple(verts), tuple(tris), tuple(roles)


def building_exclusions(doc):
    """Excavation at ground/basement exterior wall faces, derived on every edit.

    Closed room footprints clear the interior; wall footprints also clear
    unclosed outlines. Upper-storey cantilevers do not excavate the site.
    """
    from archforge.geometry.regions import region, offset_loop
    from archforge.architecture.storey_slabs import _edge_wall
    ground=float(doc.levels.get('Ground',0.))
    walls=[e for e in doc.entities.values() if e.kind=='wall' and e.visible and float(e.params.get('z',0.))<=ground+1e-5]
    out=[]
    for z in sorted({float(e.params.get('z',0.)) for e in walls}):
        local=[e for e in walls if abs(float(e.params.get('z',0.))-z)<1e-5]
        faces=doc.active_room_faces(z=z)
        for outer,holes in region([f.polygon for f in faces]):
            # Each exterior segment gets its own actual wall thickness.
            distances=[]
            for i,a in enumerate(outer):
                w=_edge_wall(local,a,outer[(i+1)%len(outer)])
                distances.append(float(w.params['thickness'])/2 if w else 0.)
            out.append(offset_loop(outer,distances))
        for w in local:
            p=w.params; ax,ay,bx,by=(float(p[k]) for k in ('x1','y1','x2','y2'))
            length=math.hypot(bx-ax,by-ay)
            if length<1e-9: continue
            dx,dy=(bx-ax)/length,(by-ay)/length; h=float(p['thickness'])/2
            # Square caps meet cleanly at corners; the room union above fills the interior.
            out.append([(ax-dx*h-dy*h,ay-dy*h+dx*h),(ax-dx*h+dy*h,ay-dy*h-dx*h),
                        (bx+dx*h+dy*h,by+dy*h-dx*h),(bx+dx*h-dy*h,by+dy*h+dx*h)])
    # A green roof (υπόσκαφο) is under the ground: no cut there (site/terrain.green_roofs).
    green=[outline for outline,_lowest in green_roofs(doc)]
    if green:
        from archforge.geometry.regions import region as _region
        out=[outer for outer,_holes in _region(out,green)]
    # A pool is dug into the ground: its basin (with its walls) is a hole in the terrain, not water under a lid
    # of soil (open since 17/10: «η λεκάνη χωρίς τρύπα στο έδαφος του 3D»).
    from archforge.site.pool import param as pool_param, rim
    for e in doc.entities.values():
        if e.kind=='pool' and e.visible:
            out.append([tuple(q) for q in rim(e.params,pool_param(e.params,'wall'))])
    return out


def _region_mesh(params, cell, exclusions, walls=None, floors=None):
    """Clip grid cells exactly at footprints and plateau edges; weld into one solid.

    Never discard whole intersecting triangles: that would leave a jagged gap
    at the walls. The existing polygon arrangement/triangulator supplies the cut.
    """
    from collections import Counter
    from archforge.geometry.regions import region, region_loops, group_loops, winding, triangulate_with_holes
    x0,y0,x1,y1=(float(params[k]) for k in ('x0','y0','x1','y1'))
    if x1<=x0 or y1<=y0: raise ValueError('terrain extent must be positive')
    cell=_stroke_cell(params,.5) if cell is None else max(.1,float(cell))
    nx=max(1,min(120,math.ceil((x1-x0)/cell))); ny=max(1,min(120,math.ceil((y1-y0)/cell)))
    # Union once, so overlapping wall footprints cannot create duplicate cut edges.
    cuts=[outer for outer,holes in region(exclusions)] if exclusions else []
    regions=[r['points'] for r in params.get('regions') or ()]
    def box(poly): return min(x for x,y in poly),min(y for x,y in poly),max(x for x,y in poly),max(y for x,y in poly)
    cut_boxes=[(p,box(p)) for p in cuts]; reg_boxes=[(p,box(p)) for p in regions]
    xy=[]; index={}; top=[]
    def vid(p):
        key=(round(p[0],8),round(p[1],8))
        if key not in index: index[key]=len(xy); xy.append(key)
        return index[key]
    for i in range(nx):
        ax=x0+(x1-x0)*i/nx; bx=x0+(x1-x0)*(i+1)/nx
        for j in range(ny):
            ay=y0+(y1-y0)*j/ny; by=y0+(y1-y0)*(j+1)/ny
            square=[(ax,ay),(bx,ay),(bx,by),(ax,by)]
            def nearby(items): return [p for p,(lx,ly,hx,hy) in items if hx>=ax-1e-8 and lx<=bx+1e-8 and hy>=ay-1e-8 and ly<=by+1e-8]
            local_cuts=nearby(cut_boxes)
            islands=region([square],local_cuts) if local_cuts else [(square,[])]
            for control in nearby(reg_boxes):
                divided=[]
                for outer,holes in islands:
                    loops=[outer]+holes
                    for inside_region in (False,True):
                        divided.extend(group_loops(region_loops(loops+[control],
                            lambda x,y,ls=loops,c=control,inside=inside_region:
                            sum(winding(x,y,q) for q in ls)>0 and bool(winding(x,y,c))==inside)))
                islands=divided
            for outer,holes in islands:
                pts,tris=triangulate_with_holes(outer,holes)
                for a,b,c in tris:
                    ids=vid(pts[a]),vid(pts[b]),vid(pts[c])
                    if len(set(ids))==3: top.append(ids)
    if not xy: return (),(),()
    heights=terrain_heights(params,xy,walls,floors)
    bottom=min(heights)-max(.05,float(params.get('thickness',DEFAULT_THICKNESS)))
    verts=[(x,y,z) for (x,y),z in zip(xy,heights)]+[(x,y,bottom) for x,y in xy]
    n=len(xy); tris=list(top)+[(c+n,b+n,a+n) for a,b,c in top]; roles=['top']*len(top)+['bottom']*len(top)
    counts=Counter(tuple(sorted(edge)) for a,b,c in top for edge in ((a,b),(b,c),(c,a)))
    for a,b,c in top:
        for u,v in ((a,b),(b,c),(c,a)):
            if counts[tuple(sorted((u,v)))]==1:
                tris.extend(((u,v+n,v),(u,u+n,v+n))); roles.extend(('side','side'))
    return tuple(verts),tuple(tris),tuple(roles)
