"""Elevation sections and explicit design controls on the shared terrain field.

Survey ``points`` and terrace ``levels`` are read-only anchors here. New controls
have stable ids and DESIGN_DEFAULT provenance; they never replace survey records.
Their correction uses terrain._point_height's existing local interpolation, with
zero correction at every source anchor. This is model interpolation, not inferred
survey evidence or a general vertical-face/breakline terrain representation.
"""
from __future__ import annotations

import copy
import math
from uuid import uuid4

from archforge.output.section_cut import frame
from archforge.core.commands import UpdateEntity

TOL = 1e-7


class ProfileEdit(UpdateEntity):
    """The shared UpdateEntity semantics, with no empty undo step for an unchanged control."""
    def do(self,doc):
        self.noop = all(doc.get(self.eid).params.get(key)==value for key,value in self.changes.items())
        if not self.noop:
            super().do(doc)


def anchors(params):
    return list(params.get('points') or ()) + list(params.get('levels') or ())


def validate_controls(params):
    controls = params.get('profile_controls') or []
    if not isinstance(controls, list):
        raise ValueError('Τα σημεία σχεδιασμού του προφίλ πρέπει να είναι λίστα')
    ids, xy = set(), []
    for c in controls:
        if not isinstance(c, dict) or not isinstance(c.get('id'), str) or not c['id']:
            raise ValueError('Κάθε σημείο σχεδιασμού χρειάζεται σταθερό αναγνωριστικό')
        if c['id'] in ids:
            raise ValueError('Διπλό αναγνωριστικό σημείου σχεδιασμού')
        ids.add(c['id'])
        try:
            finite = all(k in c and math.isfinite(float(c[k])) for k in ('x','y','z'))
        except (TypeError,ValueError):
            finite = False
        if not finite:
            raise ValueError('Οι συντεταγμένες του σημείου σχεδιασμού πρέπει να είναι αριθμοί')
        p = float(c['x']), float(c['y'])
        if not (float(params['x0']) <= p[0] <= float(params['x1']) and
                float(params['y0']) <= p[1] <= float(params['y1'])):
            raise ValueError('Το σημείο σχεδιασμού είναι έξω από το έδαφος')
        if any(math.dist(p, q[:2]) < TOL for q in anchors(params)):
            raise ValueError('Οι μετρήσεις και τα υψόμετρα πλατειών είναι προστατευμένα')
        if any(math.dist(p, q) < TOL for q in xy):
            raise ValueError('Δύο σημεία σχεδιασμού δεν μπορούν να είναι στην ίδια θέση')
        xy.append(p)
        from archforge.site.elevation_regions import distance_to_region
        if any(distance_to_region(*p,r['points']) <= TOL for r in params.get('regions') or ()):
            raise ValueError('Το σημείο σχεδιασμού πέφτει σε περιοχή σταθερού υψομέτρου')
    if 'profile_radius' in params and (not math.isfinite(float(params['profile_radius'])) or
                                       float(params['profile_radius']) < .5):
        raise ValueError('Η ακτίνα επιρροής του προφίλ πρέπει να είναι τουλάχιστον 0,5 m (όριο της παρεμβολής εδάφους)')


def correction(params, xy, base, control_base):
    """Use the existing interpolator; zero corrections pin every measured anchor."""
    from archforge.site.terrain import _point_height, DEFAULT_BLEND_RADIUS
    from archforge.site.elevation_regions import distance_to_region
    controls = params.get('profile_controls') or []
    points = [[float(c['x']), float(c['y']), float(c['z']) - z] for c,z in zip(controls, control_base)]
    points += [[float(x), float(y), 0.] for x,y,_z in anchors(params)]
    delta = dict(x0=0., y0=0., elevation=0., points=points,
                 blend_radius=params.get('profile_radius', params.get('blend_radius', DEFAULT_BLEND_RADIUS)))
    regions = params.get('regions') or ()
    return [z if any(distance_to_region(x,y,r['points']) <= TOL for r in regions)
            else z + _point_height(delta,x,y) for (x,y),z in zip(xy,base)]


def grid(params, nx, ny):
    """Keep the old grid and add design coordinates, merging numerical coincidences.

    Survey coordinates remain constraints in the field, not an O(survey_count²)
    Cartesian mesh. No stored coordinate is rounded or moved.
    """
    x0,y0,x1,y1 = (float(params[k]) for k in ('x0','y0','x1','y1'))
    xs = {x0+(x1-x0)*i/nx for i in range(nx+1)}
    ys = {y0+(y1-y0)*j/ny for j in range(ny+1)}
    if params.get('profile_controls'):
        for c in params['profile_controls']:
            for axis,value,lo,hi in ((xs,float(c['x']),x0,x1),(ys,float(c['y']),y0,y1)):
                if lo <= value <= hi and all(abs(value-q)>TOL for q in axis):
                    axis.add(value)
    return sorted(xs), sorted(ys)


PERIMETER = "perimeter:"          # section id of the plot's perimeter: "perimeter:<terrain id>"


def perimeter_id(terrain_id):
    return PERIMETER + str(terrain_id)


def _entities(doc, terrain_id, section_id):
    terrain = doc.get(terrain_id)
    if terrain.kind != 'terrain':
        raise ValueError('Διαλέξτε έδαφος και αποθηκευμένη γραμμή τομής')
    if str(section_id).startswith(PERIMETER):
        if len(terrain.params.get('boundary') or ()) < 3:
            raise ValueError('Το έδαφος δεν έχει όριο οικοπέδου — σχεδιάστε το: Περιβάλλων χώρος ▸ Οικόπεδο')
        return terrain, None
    section = doc.get(section_id)
    if section.kind != 'section_line':
        raise ValueError('Διαλέξτε έδαφος και αποθηκευμένη γραμμή τομής')
    return terrain, section


def _path(terrain, section):
    """``[(origin, direction, length, start station)]``: one straight run for a section line; the plot's sides one
    after the other, unrolled (owner 07/11: «ανάπτυγμα» of the perimeter — station = distance along the boundary
    from its first corner)."""
    if section is not None:
        o, d, _n, length = frame(section.params)
        return [(o, d, length, 0.0)]
    pts = [(float(x), float(y)) for x, y, *_ in terrain.params['boundary']]
    runs, start = [], 0.0
    for a, b in zip(pts, pts[1:] + pts[:1]):
        L = math.dist(a, b)
        if L > TOL:
            runs.append((a, ((b[0] - a[0]) / L, (b[1] - a[1]) / L), L, start))
            start += L
    return runs


def _at(runs, station):
    """Plan point of a station on the path (None outside it)."""
    for o, d, L, s0 in runs:
        if s0 - TOL <= station <= s0 + L + TOL:
            u = min(max(station - s0, 0.0), L)
            return o[0] + d[0] * u, o[1] + d[1] * u
    return None


def _editable(doc, terrain):
    from archforge.core.layers import editable
    if terrain.locked or not terrain.visible or not editable(doc, terrain.id):
        raise PermissionError('Το έδαφος είναι κρυφό, κλειδωμένο ή σε κλειδωμένο επίπεδο')


def _range(params, origin, along, length):
    lo, hi = 0., length
    for o,d,a,b in zip(origin, along, (params['x0'],params['y0']), (params['x1'],params['y1'])):
        if abs(d) < 1e-12:
            if not float(a) <= o <= float(b):
                return None
        else:
            u,v = sorted(((float(a)-o)/d, (float(b)-o)/d))
            lo, hi = max(lo,u), min(hi,v)
    return (lo,hi) if hi-lo > TOL else None


def profile(doc, terrain_id, section_id, samples=201):
    """Sample the same height field used by plan/3D, clipped to this finite section (or the plot's perimeter,
    unrolled) and the site.

    Sampled elevations are distinguished from measured records and design controls.
    No model edits and no extrapolation beyond the site. ``station`` starts at the
    currently viewed end (the existing section frame handles reverse direction), or at the
    boundary's first corner for the perimeter; ``corners`` are the stations of its corners.
    """
    from archforge.site.terrain import terrain_heights, barriers, green_roofs
    terrain, section = _entities(doc, terrain_id, section_id)
    p = terrain.params
    runs = _path(terrain, section)
    length = sum(L for _o, _d, L, _s in runs)
    ref = float(p.get('altitude_ref',0.))
    result = dict(range=None, samples=[], survey=[], controls=[],
                  altitude_ref=ref if ref or p.get('altitude_ref_confirmed') else None,
                  length=length, corners=[s0 for _o, _d, _L, s0 in runs][1:] if section is None else [])
    pieces = []
    for o, d, L, s0 in runs:
        interval = _range(p, o, d, L)
        if interval is not None:
            pieces.append((o, d, L, s0, interval))
    if not pieces:
        return result
    result['range'] = (pieces[0][3] + pieces[0][4][0], pieces[-1][3] + pieces[-1][4][1])
    count = max(2, int(samples))
    stations = set()
    for o, d, L, s0, (lo, hi) in pieces:
        n = max(2, int(round(count * (hi - lo) / max(length, TOL))) + 1)
        stations.update(s0 + lo + (hi - lo) * i / (n - 1) for i in range(n))

    def on_path(x, y):
        for o, d, L, s0, (lo, hi) in pieces:
            u = (float(x)-o[0])*d[0]+(float(y)-o[1])*d[1]
            off = abs((float(x)-o[0])*d[1]-(float(y)-o[1])*d[0])
            if off < TOL and lo-TOL <= u <= hi+TOL:
                return s0 + u
        return None

    for source in ('points','levels'):
        for i,(x,y,z) in enumerate(p.get(source) or ()):
            u = on_path(x,y)
            if u is not None:
                stations.add(u)
                result['survey'].append(dict(station=u,x=x,y=y,z=z,source=source,index=i))
    for c in p.get('profile_controls') or ():
        u = on_path(c['x'],c['y'])
        if u is not None:
            stations.add(u)
            result['controls'].append(dict(c,station=u))
    # Include existing polygon edges, so a narrow plateau is not skipped between uniform samples.
    for o, d, L, s0, (lo, hi) in pieces:
        for r in p.get('regions') or ():
            poly = r['points']
            for a,b in zip(poly,poly[1:]+poly[:1]):
                ex,ey = b[0]-a[0], b[1]-a[1]
                den = d[0]*ey-d[1]*ex
                if abs(den) < 1e-12:
                    continue
                ax,ay = a[0]-o[0],a[1]-o[1]
                u,v = (ax*ey-ay*ex)/den, (ax*d[1]-ay*d[0])/den
                if 0 <= v <= 1 and lo <= u <= hi:
                    stations.update(s0 + q for q in (u-TOL,u,u+TOL) if lo <= q <= hi)
    us = []
    for u in sorted(stations):
        if not us or u - us[-1] > TOL * 10:
            us.append(u)
    xy = [_at(runs, u) for u in us]
    heights = terrain_heights(p,xy,barriers(doc),green_roofs(doc))
    result['samples'] = [dict(station=u,x=x,y=y,z=z) for u,(x,y),z in zip(us,xy,heights)]
    return result


def edit_control(doc, terrain_id, section_id, station, z, control_id=None):
    """One UpdateEntity command; a declined edit has no side effects or undo entry."""
    from archforge.core.commands import UpdateEntity
    from archforge.site.terrain import terrain_contains, green_roofs
    from archforge.site.elevation_regions import distance_to_region
    from archforge.geometry.regions import point_in_polygon
    terrain, section = _entities(doc,terrain_id,section_id)
    _editable(doc,terrain)
    station,z = float(station),float(z)
    if not math.isfinite(station) or not math.isfinite(z):
        raise ValueError('Απόσταση και υψόμετρο πρέπει να είναι αριθμοί')
    runs = _path(terrain, section)
    at = _at(runs, station)
    if at is None or not terrain_contains(terrain.params,*at):
        raise ValueError('Το σημείο είναι έξω από την τομή ή το έδαφος')
    x, y = at
    if any(distance_to_region(x,y,r['points']) <= TOL for r in terrain.params.get('regions') or ()):
        raise ValueError('Το σημείο ανήκει σε περιοχή σταθερού υψομέτρου — αλλάξτε την περιοχή')
    if any(z < lowest-TOL and point_in_polygon(x,y,outline) for outline,lowest in green_roofs(doc)):
        raise ValueError('Το σημείο θα έπεφτε κάτω από το ελάχιστο έδαφος του υπόσκαφου')
    controls = copy.deepcopy(terrain.params.get('profile_controls') or [])
    if control_id is not None:
        c = next((c for c in controls if c['id'] == control_id), None)
        if c is None:
            raise ValueError('Το σημείο σχεδιασμού έχει διαγραφεί')
        c.update(x=x,y=y,z=z)
    else:
        controls.append(dict(id=uuid4().hex,x=x,y=y,z=z,provenance='DESIGN_DEFAULT'))
    candidate = dict(terrain.params,profile_controls=controls)
    validate_controls(candidate)
    return ProfileEdit(terrain_id, {'profile_controls': controls})


def remove_control(doc, terrain_id, control_id):
    from archforge.core.commands import UpdateEntity
    terrain = doc.get(terrain_id)
    _editable(doc,terrain)
    controls = terrain.params.get('profile_controls') or []
    kept = [copy.deepcopy(c) for c in controls if c['id'] != control_id]
    if len(kept) == len(controls):
        raise ValueError('Το σημείο σχεδιασμού έχει διαγραφεί')
    return ProfileEdit(terrain_id, {'profile_controls': kept})


def edit_grade(doc, terrain_id, section_id, station, grade_percent, control_id=None):
    """Set an endpoint from an average grade to the preceding record, not a constant-gradient earthwork."""
    data = profile(doc,terrain_id,section_id)
    station,grade = float(station),float(grade_percent)
    if not math.isfinite(grade):
        raise ValueError('Η κλίση πρέπει να είναι αριθμός')
    candidates = [r for r in data['survey']+data['controls']
                  if r['station'] < station-TOL and (control_id is None or r.get('id') != control_id)]
    if not candidates:
        raise ValueError('Για κλίση χρειάζεται προηγούμενο σημείο (μέτρηση ή σχεδιασμού)')
    previous = max(candidates,key=lambda r:r['station'])
    z = previous['z']+grade/100.*(station-previous['station'])
    return edit_control(doc,terrain_id,section_id,station,z,control_id)
