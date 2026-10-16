"""Authoritative, editable terrain plateaus and their plan outlines (metres).

Regions live in the terrain entity, alongside legacy survey points. Their
boundary is a height constraint, not a new solid or a second terrain model.
Different heights need a gap for the slope; they cannot overlap or share
boundary points with contradictory elevations.
"""
from __future__ import annotations
import math
import copy

from archforge.geometry.regions import point_in_polygon, signed_area, region_loops, group_loops, islands_area

SHAPES = {'rectangle': 'Ορθογώνιο', 'circle': 'Κύκλος', 'polygon': 'Ελεύθερο πολύγωνο'}


def segment_distance(x, y, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    den = dx*dx + dy*dy
    t = max(0., min(1., ((x-a[0])*dx+(y-a[1])*dy)/den)) if den else 0.
    return math.hypot(x-a[0]-t*dx, y-a[1]-t*dy)


def distance_to_region(x, y, points):
    distance = min(segment_distance(x,y,a,points[(i+1)%len(points)]) for i,a in enumerate(points))
    return 0. if distance < 1e-8 or point_in_polygon(x,y,points) else distance


def validate_regions(value):
    out = []
    ids = set()
    for raw in value or ():
        r = copy.deepcopy(raw)
        if not isinstance(r, dict) or not r.get('id') or r['id'] in ids:
            raise ValueError('κάθε υψομετρική περιοχή χρειάζεται μοναδικό id')
        ids.add(r['id'])
        if r.get('shape', 'polygon') not in SHAPES:
            raise ValueError('άγνωστο υψομετρικό σχήμα')
        pts = [[float(x),float(y)] for x,y in r.get('points',())]
        if len(pts)>1 and pts[0]==pts[-1]: pts.pop()
        if len(pts)<3 or not all(math.isfinite(q) for p in pts for q in p) or abs(signed_area(pts))<1e-6:
            raise ValueError('η περιοχή χρειάζεται τουλάχιστον 3 διαφορετικές κορυφές και επιφάνεια')
        # Non-adjacent edges cannot cross or touch. Adjacent zero-length edges are invalid too.
        for i,a in enumerate(pts):
            b=pts[(i+1)%len(pts)]
            if math.dist(a,b)<1e-6: raise ValueError('διπλή κορυφή στο περίγραμμα')
            for j in range(i+1,len(pts)):
                if j==i+1 or (i==0 and j==len(pts)-1): continue
                c,d=pts[j],pts[(j+1)%len(pts)]
                def cross(p,q,s): return (q[0]-p[0])*(s[1]-p[1])-(q[1]-p[1])*(s[0]-p[0])
                if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:
                    raise ValueError('το περίγραμμα τέμνει τον εαυτό του')
                if any(segment_distance(*p,u,v)<1e-8 for p,u,v in ((a,c,d),(b,c,d),(c,a,b),(d,a,b))):
                    raise ValueError('το περίγραμμα αγγίζει τον εαυτό του')
        elevation=float(r['elevation']); transition=float(r.get('transition',5.))
        if not math.isfinite(elevation) or not math.isfinite(transition) or transition<=0:
            raise ValueError('χρειάζεται πεπερασμένο υψόμετρο και θετική απόσταση μετάβασης')
        r.update(points=pts,elevation=elevation,transition=transition,shape=r.get('shape','polygon'))
        for prev in out:
            if abs(prev['elevation']-elevation)<1e-8: continue
            if any(distance_to_region(x,y,prev['points'])<1e-8 for x,y in pts) or any(
                    distance_to_region(x,y,pts)<1e-8 for x,y in prev['points']):
                raise ValueError('περιοχές με διαφορετικό υψόμετρο χρειάζονται κενό για την κλίση')
            overlap=group_loops(region_loops([prev['points'],pts],
                lambda x,y: point_in_polygon(x,y,prev['points']) and point_in_polygon(x,y,pts)))
            if islands_area(overlap)>1e-7:
                raise ValueError('περιοχές με διαφορετικό υψόμετρο δεν μπορούν να επικαλύπτονται')
        out.append(r)
    return out


def shape_points(shape, a, b):
    if shape=='rectangle':
        x0,x1=sorted((a[0],b[0])); y0,y1=sorted((a[1],b[1]))
        return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
    if shape=='circle':
        radius=math.dist(a,b)
        return [[a[0]+radius*math.cos(i*math.tau/48),a[1]+radius*math.sin(i*math.tau/48)] for i in range(48)]
    raise ValueError('χρειάζεται ορθογώνιο ή κύκλος')


def blended_height(params, x, y, base):
    num=0.; den=1.
    for r in params.get('regions') or ():
        d=distance_to_region(x,y,r['points'])
        if d<1e-8: return float(r['elevation'])
        radius=float(r.get('transition',5.))
        if d>=radius: continue
        w=(1.-d/radius)**2*(radius/d)**2
        num+=w*(float(r['elevation'])-base); den+=w
    return base+num/den
