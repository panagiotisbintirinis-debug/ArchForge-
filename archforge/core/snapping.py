from __future__ import annotations
from dataclasses import dataclass
from math import cos,sin,radians,hypot
from typing import List,Set
from .model import Document

@dataclass(frozen=True)
class SnapPoint:
    x:float;y:float;z:float;kind:str;entity_id:str

def points_for(doc:Document,eid:str)->List[SnapPoint]:
    e=doc.get(eid);p=e.params;out=[]
    if e.kind=='wall':
        z=p['z']; pts=[(p['x1'],p['y1'],'endpoint'),(p['x2'],p['y2'],'endpoint'),((p['x1']+p['x2'])/2,(p['y1']+p['y2'])/2,'midpoint')]
        out=[SnapPoint(x,y,z,k,eid) for x,y,k in pts]
    elif e.kind=='box':
        a=radians(p.get('rotation',0));c,s=cos(a),sin(a);hw,hd=p['width']/2,p['depth']/2
        loc=[(-hw,-hd,'corner'),(hw,-hd,'corner'),(hw,hd,'corner'),(-hw,hd,'corner'),(0,-hd,'midpoint'),(hw,0,'midpoint'),(0,hd,'midpoint'),(-hw,0,'midpoint'),(0,0,'center')]
        for lx,ly,k in loc: out.append(SnapPoint(p['x']+lx*c-ly*s,p['y']+lx*s+ly*c,p['z'],k,eid))
    elif e.kind=='structural_column':
        a=radians(p.get('rotation',0));c,s=cos(a),sin(a);hw,hd=p['width']/2,p['depth']/2
        loc=[(-hw,-hd,'corner'),(hw,-hd,'corner'),(hw,hd,'corner'),(-hw,hd,'corner'),(0,0,'center')]
        for lx,ly,k in loc:
            out.append(SnapPoint(p['x']+lx*c-ly*s,p['y']+lx*s+ly*c,p['z'],k,eid))
    elif e.kind=='structural_beam':
        # Plan snapping follows the beam's semantic storey, not the physical
        # bottom elevation of its section near the storey above.
        z=float(doc.levels.get(str(p.get('level','')),p['z']))
        pts=[
            (p['x1'],p['y1'],'endpoint'),
            (p['x2'],p['y2'],'endpoint'),
            ((p['x1']+p['x2'])/2,(p['y1']+p['y2'])/2,'midpoint'),
        ]
        out=[SnapPoint(float(x),float(y),z,k,eid) for x,y,k in pts]
    elif e.kind=='pod':
        rx,ry=p['diameter_x']/2,p['diameter_y']/2;z=p['floor_level']
        out=[SnapPoint(p['cx'],p['cy'],z,'center',eid),SnapPoint(p['cx']+rx,p['cy'],z,'quadrant',eid),SnapPoint(p['cx']-rx,p['cy'],z,'quadrant',eid),SnapPoint(p['cx'],p['cy']+ry,z,'quadrant',eid),SnapPoint(p['cx'],p['cy']-ry,z,'quadrant',eid)]
    elif e.kind in ('floor','room'):
        z=p['z'];pts=p['points']
        for i,(x,y) in enumerate(pts):
            out.append(SnapPoint(x,y,z,'vertex',eid));x2,y2=pts[(i+1)%len(pts)];out.append(SnapPoint((x+x2)/2,(y+y2)/2,z,'midpoint',eid))
    return out

def _segment_intersection(a1,a2,b1,b2,tolerance=1e-12):
    x1,y1=map(float,a1);x2,y2=map(float,a2);x3,y3=map(float,b1);x4,y4=map(float,b2)
    den=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
    if abs(den)<=tolerance:return None
    t=((x1-x3)*(y3-y4)-(y1-y3)*(x3-x4))/den
    u=-((x1-x2)*(y1-y3)-(y1-y2)*(x1-x3))/den
    if t < -tolerance or t > 1.0+tolerance or u < -tolerance or u > 1.0+tolerance:
        return None
    return (x1+t*(x2-x1),y1+t*(y2-y1))

def _best_wall_intersection(doc,x,y,tolerance,exclude,active_z):
    walls=[]
    for eid,e in doc.entities.items():
        if eid in exclude or e.kind!='wall' or not e.visible:continue
        p=e.params
        if abs(float(p.get('z',0.0))-active_z)>1e-5:continue
        walls.append((eid,p))
    best=None;bestd=float(tolerance)
    for i,(aid,a) in enumerate(walls):
        for bid,b in walls[i+1:]:
            point=_segment_intersection(
                (a['x1'],a['y1']),(a['x2'],a['y2']),
                (b['x1'],b['y1']),(b['x2'],b['y2']),
            )
            if point is None:continue
            d=hypot(point[0]-x,point[1]-y)
            if d<=bestd:
                bestd=d
                best=SnapPoint(point[0],point[1],active_z,'intersection',f'{aid}|{bid}')
    return best

def _wall_projection(eid,p,x,y,tolerance):
    dx=p['x2']-p['x1'];dy=p['y2']-p['y1'];ll=dx*dx+dy*dy
    if ll<=1e-18:return None
    t=((x-p['x1'])*dx+(y-p['y1'])*dy)/ll
    if t<=1e-9 or t>=1-1e-9:return None
    px=p['x1']+t*dx;py=p['y1']+t*dy
    if hypot(px-x,py-y)>tolerance:return None
    return SnapPoint(px,py,p['z'],'wall',eid)

def best_snap(doc:Document,x:float,y:float,tolerance:float,grid:float|None=None,exclude:Set[str]|None=None):
    exclude=exclude or set();best=None;bestd=tolerance;active_z=float(doc.work_plane.origin[2])
    # A true crossing is the strongest architectural target. Check it before
    # coincident endpoint/midpoint candidates so the user receives the more
    # specific intersection identity and feedback.
    intersection=_best_wall_intersection(doc,x,y,tolerance,exclude,active_z)
    if intersection is not None:return intersection
    # Explicit semantic snap points are next, and only on the active storey.
    for eid in doc.entities:
        if eid in exclude:continue
        for sp in points_for(doc,eid):
            if abs(float(sp.z)-active_z)>1e-5:continue
            d=hypot(sp.x-x,sp.y-y)
            if d <= bestd:best,bestd=sp,d
    if best:return best
    # Then allow arbitrary projection to a wall centerline on the active storey.
    for eid,e in doc.entities.items():
        if eid in exclude or e.kind!='wall' or not e.visible:continue
        if abs(float(e.params.get('z',0.0))-active_z)>1e-5:continue
        sp=_wall_projection(eid,e.params,x,y,tolerance)
        if sp is None:continue
        d=hypot(sp.x-x,sp.y-y)
        if d<=bestd:best,bestd=sp,d
    if best:return best
    # Tracing an upper storey: corners/ends of the walls on the storey
    # directly below snap too (projected onto the active work plane).
    lower=[(float(e.params.get('z',0.0)),e.params) for eid,e in doc.entities.items()
           if eid not in exclude and e.kind=='wall' and e.visible and float(e.params.get('z',0.0))<active_z-1e-5]
    if lower:
        below=max(z for z,_ in lower)
        for z,p in lower:
            if abs(z-below)>1e-5:continue
            for px,py in ((float(p['x1']),float(p['y1'])),(float(p['x2']),float(p['y2']))):
                d=hypot(px-x,py-y)
                if d<=bestd:best,bestd=SnapPoint(px,py,active_z,'underlay_endpoint',''),d
        if best:return best
    if grid:
        gx=round(x/grid)*grid;gy=round(y/grid)*grid
        # Construction grid is a soft magnet, not a quantizer. With a 0.10 m
        # step, using the full semantic snap tolerance would capture virtually
        # every pointer position. Limit grid capture to 20% of the step.
        grid_tolerance=min(float(tolerance),abs(float(grid))*0.20)
        if hypot(gx-x,gy-y)<=grid_tolerance:
            return SnapPoint(gx,gy,active_z,'construction_grid','')
    return None


def _nearest_on_segment(ax, ay, bx, by, x, y):
    dx=bx-ax;dy=by-ay;ll=dx*dx+dy*dy
    if ll<=1e-18:return (ax,ay)
    t=max(0.0,min(1.0,((x-ax)*dx+(y-ay)*dy)/ll))
    return (ax+t*dx,ay+t*dy)

def wall_face_segments(doc:Document,exclude:Set[str]|None=None):
    """Physical wall-face segments on the active storey, not only centerlines."""
    exclude=exclude or set();active_z=float(doc.work_plane.origin[2]);out=[]
    for eid,e in doc.entities.items():
        if eid in exclude or e.kind!='wall' or not e.visible:continue
        p=e.params
        if abs(float(p.get('z',0.0))-active_z)>1e-5:continue
        x1,y1,x2,y2=map(float,(p['x1'],p['y1'],p['x2'],p['y2']))
        dx,dy=x2-x1,y2-y1;length=hypot(dx,dy)
        if length<=1e-12:continue
        nx,ny=-dy/length,dx/length;half=float(p.get('thickness',0.0))/2.0
        for sign in (-1.0,1.0):
            ox,oy=nx*half*sign,ny*half*sign
            out.append(((x1+ox,y1+oy),(x2+ox,y2+oy),eid,'wall_face'))
    return out

def snap_polygon_translation_to_wall_faces(
    doc:Document,
    polygon,
    dx:float,
    dy:float,
    tolerance:float,
    exclude:Set[str]|None=None,
):
    """Return a correction that makes a moved polygon touch a physical wall face.

    Corners and edge midpoints are considered so a stair/ramp can be placed
    flush against a wall rather than snapping its origin to the wall centreline.
    """
    pts=[(float(x)+float(dx),float(y)+float(dy)) for x,y in polygon]
    if len(pts)<2:return None
    probes=[]
    for i,(x,y) in enumerate(pts):
        probes.append((x,y))
        x2,y2=pts[(i+1)%len(pts)]
        probes.append(((x+x2)/2.0,(y+y2)/2.0))
    best=None;bestd=float(tolerance)
    for a,b,eid,kind in wall_face_segments(doc,exclude):
        for px,py in probes:
            qx,qy=_nearest_on_segment(a[0],a[1],b[0],b[1],px,py)
            d=hypot(qx-px,qy-py)
            if d<=bestd:
                bestd=d
                best={
                    'correction':(qx-px,qy-py),
                    'point':(qx,qy),
                    'kind':kind,
                    'entity_id':eid,
                    'distance':d,
                }
    return best


def snap_translation_points(
    doc:Document,
    points,
    dx:float,
    dy:float,
    tolerance:float,
    exclude:Set[str]|None=None,
):
    """Find the smallest translation correction that snaps one moved probe point.

    Useful for moving whole walls: their endpoint/midpoint geometry snaps to
    another wall's semantic endpoint/midpoint/centerline instead of snapping
    only the mouse cursor.
    """
    exclude=exclude or set();best=None;bestd=float(tolerance)
    for x,y in points:
        tx=float(x)+float(dx);ty=float(y)+float(dy)
        sp=best_snap(doc,tx,ty,tolerance,grid=None,exclude=exclude)
        if sp is None:continue
        d=hypot(float(sp.x)-tx,float(sp.y)-ty)
        if d<=bestd:
            bestd=d
            best={
                'correction':(float(sp.x)-tx,float(sp.y)-ty),
                'point':(float(sp.x),float(sp.y)),
                'kind':str(sp.kind),
                'entity_id':str(sp.entity_id),
                'distance':d,
            }
    return best


COLUMN_SNAP_TOLERANCE=0.30
# Two walls meeting at less than ~11.5 deg off straight are a continuation
# (e.g. a short closing segment), not a corner to anchor a column on.
CORNER_MIN_SIN=0.2


def _slab_vertices(doc,active_z,tolerance=1e-5):
    """Corners of floor slabs on the active storey (authored and room floors)."""
    out=[]
    for eid,e in doc.entities.items():
        if not e.visible:continue
        if e.kind in ('floor','room'):
            if abs(float(e.params.get('z',0.0))-active_z)>tolerance:continue
            pts=e.params.get('points',())
        elif e.kind=='room_floor':
            from archforge.architecture.rooms import room_slab_geometry,find_room_face,find_room_face_by_id
            p=e.params;room_id=p.get('room_id')
            found=(find_room_face_by_id(doc,room_id,tolerance=tolerance) if room_id
                   else find_room_face(doc,p.get('room_signature',''),tolerance=tolerance))
            if found is None or abs(float(found[1])-active_z)>tolerance:continue
            geom=room_slab_geometry(doc,e,tolerance=tolerance)
            pts=geom['points'] if geom else ()
        else:
            continue
        out.extend(SnapPoint(float(x),float(y),active_z,'slab_corner',eid) for x,y in pts)
    return out


def _unit(dx,dy):
    l=hypot(dx,dy)
    return (dx/l,dy/l) if l>1e-12 else None


def _angle(u):
    from math import atan2,degrees
    return degrees(atan2(u[1],u[0]))


def _point_in_polygon(pt,poly):
    x,y=pt;inside=False;n=len(poly)
    for i in range(n):
        x1,y1=poly[i];x2,y2=poly[(i+1)%n]
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1:inside=not inside
    return inside


def _room_polygons(doc):
    try:return [tuple(face.polygon) for face in doc.active_room_faces()]
    except Exception:return []


def _outward_side(base,u,perp,thickness,polys):
    """+1/-1 for the perp side that faces away from the rooms, or None."""
    if not polys:return None
    off=thickness/2.0+0.05
    q1=(base[0]+perp[0]*off,base[1]+perp[1]*off)
    q2=(base[0]-perp[0]*off,base[1]-perp[1]*off)
    in1=any(_point_in_polygon(q1,poly) for poly in polys)
    in2=any(_point_in_polygon(q2,poly) for poly in polys)
    if in1==in2:return None
    return -1.0 if in1 else 1.0


def _line_intersection(p,u,q,v):
    den=u[0]*v[1]-u[1]*v[0]
    if abs(den)<1e-12:return None
    t=((q[0]-p[0])*v[1]-(q[1]-p[1])*v[0])/den
    return (p[0]+t*u[0],p[1]+t*u[1])


def _corner_placement(P,arm_a,arm_b,polys,width,depth):
    """Column centre/rotation whose outer corner meets the walls' outer corner.

    ``arm_a``/``arm_b`` are (unit direction away from P, thickness, length)
    for the two walls forming the corner. The column's outer faces are flush
    with the outer faces of both walls; when the column is thicker than a
    wall the extra shows on the inside. Rooms decide which side is outside
    (so inner/reflex corners work); with no rooms the convex side between
    the two walls is treated as inside.
    """
    uA,tA,lenA=arm_a;uB,tB,lenB=arm_b
    if abs(uA[0]*uB[1]-uA[1]*uB[0])<CORNER_MIN_SIN:return None
    bis=(uA[0]+uB[0],uA[1]+uB[1])
    def outward(u,t,length):
        perp=(-u[1],u[0]);probe=min(0.30,length/2.0)
        side=_outward_side((P[0]+u[0]*probe,P[1]+u[1]*probe),u,perp,t,polys)
        if side is None:side=-1.0 if perp[0]*bis[0]+perp[1]*bis[1]>0 else 1.0
        return (perp[0]*side,perp[1]*side)
    nA=outward(uA,tA,lenA);nB=outward(uB,tB,lenB)
    O=_line_intersection((P[0]+nA[0]*tA/2,P[1]+nA[1]*tA/2),uA,(P[0]+nB[0]*tB/2,P[1]+nB[1]*tB/2),uB)
    if O is None:return None
    sigma=-1.0 if -(nB[0]*uA[0]+nB[1]*uA[1])<0 else 1.0
    cx=O[0]-nA[0]*depth/2+sigma*uA[0]*width/2
    cy=O[1]-nA[1]*depth/2+sigma*uA[1]*width/2
    return (cx,cy),_angle(uA)


def _arms_at(P,walls,tolerance=5e-4):
    """Wall directions leaving junction P: one per ending wall, two per wall
    that passes through P (e.g. a wall drawn past the corner)."""
    arms=[]
    for eid,p in walls:
        a=(float(p['x1']),float(p['y1']));b=(float(p['x2']),float(p['y2']));t=float(p['thickness'])
        da=hypot(a[0]-P[0],a[1]-P[1]);db=hypot(b[0]-P[0],b[1]-P[1])
        if da<=tolerance or db<=tolerance:
            far,length=(b,db) if da<=db else (a,da)
            u=_unit(far[0]-P[0],far[1]-P[1])
            if u is not None:arms.append((eid,(u,t,length)))
            continue
        u=_unit(b[0]-a[0],b[1]-a[1])
        if u is None:continue
        along=(P[0]-a[0])*u[0]+(P[1]-a[1])*u[1]
        off=abs((P[0]-a[0])*u[1]-(P[1]-a[1])*u[0])
        if off<=tolerance and tolerance<along<hypot(b[0]-a[0],b[1]-a[1])-tolerance:
            arms.append((eid,((-u[0],-u[1]),t,da)));arms.append((eid,(u,t,db)))
    return arms


def _slab_corner_placement(poly,i,width,depth):
    V=poly[i];nxt=poly[(i+1)%len(poly)];prv=poly[i-1]
    e1=_unit(nxt[0]-V[0],nxt[1]-V[1]);e2=_unit(prv[0]-V[0],prv[1]-V[1])
    if e1 is None or e2 is None:return None
    n1=(-e1[1],e1[0])
    if n1[0]*e2[0]+n1[1]*e2[1]<0:n1=(-n1[0],-n1[1])
    return (V[0]+e1[0]*width/2+n1[0]*depth/2,V[1]+e1[1]*width/2+n1[1]*depth/2),_angle(e1)


def column_snap(doc:Document,x:float,y:float,tolerance:float=COLUMN_SNAP_TOLERANCE,width:float=.25,depth:float=.25):
    """Place a column centre near wall corners, slab corners, or on a wall.

    Returns (SnapPoint at the column centre, rotation_degrees_or_None) or
    (None, None). Wall corners win over slab corners, which win over a wall
    axis. Columns are flush with outer wall faces where outside is known.
    """
    active_z=float(doc.work_plane.origin[2]);width=float(width);depth=float(depth)
    walls=[(eid,e.params) for eid,e in doc.entities.items()
           if e.kind=='wall' and e.visible and abs(float(e.params.get('z',0.0))-active_z)<=1e-5]
    polys=None
    def rooms():
        nonlocal polys
        if polys is None:polys=_room_polygons(doc)
        return polys
    # 1) Wall corners, ends and crossings.
    junctions=[]
    for eid,p in walls:
        for P in ((float(p['x1']),float(p['y1'])),(float(p['x2']),float(p['y2']))):
            d=hypot(P[0]-x,P[1]-y)
            if d<tolerance:junctions.append((d,P))
    crossing=_best_wall_intersection(doc,x,y,tolerance,set(),active_z)
    if crossing is not None:junctions.append((hypot(crossing.x-x,crossing.y-y),(crossing.x,crossing.y)))
    def corner_at(P):
        arms=_arms_at(P,walls)
        pairs=[(i,j) for i in range(len(arms)) for j in range(i+1,len(arms))
               if arms[i][0]!=arms[j][0]
               and abs(arms[i][1][0][0]*arms[j][1][0][1]-arms[i][1][0][1]*arms[j][1][0][0])>=CORNER_MIN_SIN]
        chosen=None
        if len(pairs)==1 and len(arms)==2:
            chosen=pairs[0]
        elif pairs and rooms():
            # A wall passing through the corner: the real corner is the
            # pair of arms whose sector holds the room.
            inside=[]
            for i,j in pairs:
                ui=arms[i][1][0];uj=arms[j][1][0];b=_unit(ui[0]+uj[0],ui[1]+uj[1])
                if b is None:continue
                q=(P[0]+b[0]*0.2,P[1]+b[1]*0.2)
                if any(_point_in_polygon(q,poly) for poly in rooms()):inside.append((i,j))
            if len(inside)==1:chosen=inside[0]
        if chosen is None:return None,arms
        i,j=chosen
        placed=_corner_placement(P,arms[i][1],arms[j][1],rooms(),width,depth)
        if placed is None:return None,arms
        (cx,cy),rot=placed
        return (SnapPoint(cx,cy,active_z,'wall_corner',f'{arms[i][0]}|{arms[j][0]}'),rot),arms
    if junctions:
        junctions.sort(key=lambda item:item[0])
        # The nearest real corner wins; a near-straight junction (short
        # closing wall) is skipped in favour of the corner next to it.
        for _,P in junctions:
            placed,_arms=corner_at(P)
            if placed is not None:return placed
        _,P=junctions[0]
        arms=_arms_at(P,walls)
        if len(arms)==1:
            return SnapPoint(P[0],P[1],active_z,'endpoint',arms[0][0]),_angle(arms[0][1][0])
        if len(arms)==2 and abs(arms[0][1][0][0]*arms[1][1][0][1]-arms[0][1][0][1]*arms[1][1][0][0])<CORNER_MIN_SIN:
            pass  # near-straight continuation: place on the wall below
        else:
            return SnapPoint(P[0],P[1],active_z,'intersection',''),None
    # 2) Floor slab corners (no wall corner nearby).
    best=None;bestd=float(tolerance)
    for sp in _slab_vertices(doc,active_z):
        d=hypot(sp.x-x,sp.y-y)
        if d<bestd:best,bestd=sp,d
    if best is not None:
        slab=doc.get(best.entity_id)
        if slab.kind=='room_floor':
            from archforge.architecture.rooms import room_slab_geometry
            poly=list((room_slab_geometry(doc,slab) or {}).get('points',()))
        else:
            poly=list(slab.params.get('points',()))
        idx=min(range(len(poly)),key=lambda i:hypot(poly[i][0]-best.x,poly[i][1]-best.y))
        placed=_slab_corner_placement([(float(a),float(b)) for a,b in poly],idx,width,depth)
        if placed is not None:
            (cx,cy),rot=placed
            return SnapPoint(cx,cy,active_z,'slab_corner',best.entity_id),rot
        return best,None
    # 3) On a wall: follow its direction, flush with its outer face.
    for eid,p in walls:
        sp=_wall_projection(eid,p,x,y,tolerance)
        if sp is None:continue
        d=hypot(sp.x-x,sp.y-y)
        if d<bestd:best,bestd=(sp,eid,p),d
    if best is not None:
        sp,eid,p=best
        u=_unit(float(p['x2'])-float(p['x1']),float(p['y2'])-float(p['y1']))
        perp=(-u[1],u[0]);t=float(p['thickness'])
        side=_outward_side((sp.x,sp.y),u,perp,t,rooms())
        cx,cy=sp.x,sp.y
        if side is not None:
            shift=t/2.0-depth/2.0
            cx+=perp[0]*side*shift;cy+=perp[1]*side*shift
        return SnapPoint(cx,cy,active_z,'wall',eid),_angle(u)
    return None,None
