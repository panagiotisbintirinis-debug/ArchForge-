from __future__ import annotations
from dataclasses import dataclass, field
from math import radians, cos, sin, pi, sqrt
from typing import List, Tuple, Optional, Dict, Any

from .model import Document

Point2 = Tuple[float, float]

@dataclass(frozen=True)
class ViewPrimitive:
    kind: str
    points: Tuple[Point2, ...] = ()
    radius_a: float = 0.0
    radius_b: float = 0.0
    entity_id: str = ''
    role: str = 'model'
    meta: Tuple[Tuple[str, Any], ...] = ()

@dataclass
class ViewFrame:
    axis: str
    primitives: List[ViewPrimitive] = field(default_factory=list)


def _box_xy_corners(p):
    a=radians(p.get('rotation',0.0));c,s=cos(a),sin(a);hw,hd=p['width']/2,p['depth']/2
    return [(p['x'] + lx*c - ly*s, p['y'] + lx*s + ly*c) for lx,ly in [(-hw,-hd),(hw,-hd),(hw,hd),(-hw,hd)]]


def _extent(values):
    return min(values), max(values)


def _pod_has_active_junction(doc: Document, pod_id: str) -> bool:
    for entity in doc.entities.values():
        if entity.kind != 'organic_junction' or entity.params.get('status') != 'active':
            continue
        if pod_id in (entity.params.get('component_a'), entity.params.get('component_b')):
            return True
    return False


def _clip_polygon_axis(points, limit, keep_positive, tolerance=1e-9):
    if not points:return []
    sign=1.0 if keep_positive else -1.0
    def value(q):return sign*(float(q[0])-float(limit))
    def intersection(a,b,va,vb):
        den=va-vb
        if abs(den)<=1e-15:return a
        t=va/den
        return (a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]))
    out=[];s=points[-1];sv=value(s);s_in=sv>=-tolerance
    for e in points:
        ev=value(e);e_in=ev>=-tolerance
        if e_in:
            if not s_in:out.append(intersection(s,e,sv,ev))
            out.append(e)
        elif s_in:out.append(intersection(s,e,sv,ev))
        s=e;sv=ev;s_in=e_in
    return out


def _pod_supported_orthographic_polygon(doc: Document, pod_id: str, axis: str, p):
    """Return deterministic elevation geometry for proven projection cases.

    Circular pods retain the issue-66 axis-aligned contract. Issue 68 additionally
    proves rotated non-circular ellipses via their exact world-axis support function.
    Axis-aligned non-circular ellipses and oblique projected separators remain explicit
    unsupported boundaries until independently covered by a regression contract.
    """
    from archforge.organic.biospectre import junction_plane, junction_section_polygon
    active=[]
    for entity in doc.entities.values():
        if entity.kind!='organic_junction' or entity.params.get('status')!='active':continue
        a_id,b_id=entity.params.get('component_a'),entity.params.get('component_b')
        if pod_id not in (a_id,b_id) or a_id not in doc.entities or b_id not in doc.entities:continue
        a,b=doc.get(a_id),doc.get(b_id)
        if a.kind!='pod' or b.kind!='pod':continue
        plane=junction_plane(a.params,b.params)
        if plane is None or junction_section_polygon(a.params,b.params) is None:continue
        active.append(plane)
    if not active:return None

    dx=float(p['diameter_x']);dy=float(p['diameter_y'])
    rotation=float(p.get('rotation',0.0))
    non_circular=abs(dx-dy)>1e-9
    rotated=abs(rotation)%90.0>1e-9
    if non_circular and not rotated:
        return False
    theta=radians(rotation)
    semi_x=dx/2.0;semi_y=dy/2.0
    if axis=='XZ':
        center=float(p['cx'])
        radius=sqrt((semi_x*cos(theta))**2+(semi_y*sin(theta))**2)
    else:
        center=float(p['cy'])
        radius=sqrt((semi_x*sin(theta))**2+(semi_y*cos(theta))**2)
    z0=float(p['floor_level']);height=float(p['height'])
    points=[(center+radius*cos(pi*i/48.0),z0+height*sin(pi*i/48.0)) for i in range(49)]
    points.append((center,z0))
    for plane in active:
        nx,ny=map(float,plane['normal']);px,py=map(float,plane['point'])
        if abs(nx)>1.0-1e-9 and abs(ny)<=1e-9:
            if axis=='XZ':
                signed=(float(p['cx'])-px)*nx
                if abs(signed)<=1e-12:return False
                points=_clip_polygon_axis(points,px,signed*nx>0)
        elif abs(ny)>1.0-1e-9 and abs(nx)<=1e-9:
            if axis=='YZ':
                signed=(float(p['cy'])-py)*ny
                if abs(signed)<=1e-12:return False
                points=_clip_polygon_axis(points,py,signed*ny>0)
        else:
            return False
        if len(points)<3:return False
    return tuple(points)


def entity_view_primitives(doc: Document, eid: str, axis: str, override_params: Optional[Dict[str, Any]] = None) -> List[ViewPrimitive]:
    if axis not in ('XY','XZ','YZ'): raise ValueError('axis must be XY, XZ or YZ')
    e=doc.get(eid)
    if not e.visible:return []
    p=override_params if override_params is not None else e.params
    if e.kind=='wall':
        if axis=='XY':return [ViewPrimitive('line',((p['x1'],p['y1']),(p['x2'],p['y2'])),entity_id=eid,meta=(('thickness',p['thickness']),))]
        vals=(p['x1'],p['x2']) if axis=='XZ' else (p['y1'],p['y2']); lo,hi=_extent(vals); z0=p['z'];z1=z0+p['height']
        if hi-lo < p['thickness']:
            mid=(lo+hi)/2;lo=mid-p['thickness']/2;hi=mid+p['thickness']/2
        return [ViewPrimitive('polygon',((lo,z0),(hi,z0),(hi,z1),(lo,z1)),entity_id=eid)]
    if e.kind=='box':
        if axis=='XY':return [ViewPrimitive('polygon',tuple(_box_xy_corners(p)),entity_id=eid)]
        corners=_box_xy_corners(p);vals=[q[0] for q in corners] if axis=='XZ' else [q[1] for q in corners];lo,hi=_extent(vals);z0=p['z'];z1=z0+p['height']
        return [ViewPrimitive('polygon',((lo,z0),(hi,z0),(hi,z1),(lo,z1)),entity_id=eid)]
    if e.kind=='floor':
        pts=[tuple(q) for q in p['points']]
        if axis=='XY':return [ViewPrimitive('polygon',tuple(pts),entity_id=eid,meta=(('semantic','floor'),))]
        vals=[q[0] for q in pts] if axis=='XZ' else [q[1] for q in pts];lo,hi=_extent(vals);z0=p['z'];z1=z0+p['thickness']
        return [ViewPrimitive('polygon',((lo,z0),(hi,z0),(hi,z1),(lo,z1)),entity_id=eid,meta=(('semantic','floor'),))]
    if e.kind=='room_floor':
        from archforge.architecture.rooms import room_floor_geometry
        g=room_floor_geometry(doc,e)
        if g is None:return []
        pts=g['points']
        if axis=='XY':return [ViewPrimitive('polygon',tuple(pts),entity_id=eid,role='room-floor',meta=(('semantic','room_floor'),('signature',g['room_signature'])))]
        vals=[q[0] for q in pts] if axis=='XZ' else [q[1] for q in pts];lo,hi=_extent(vals);z0=g['z'];z1=z0+g['thickness']
        return [ViewPrimitive('polygon',((lo,z0),(hi,z0),(hi,z1),(lo,z1)),entity_id=eid,role='room-floor',meta=(('semantic','room_floor'),('signature',g['room_signature'])))]
    if e.kind=='room':
        pts=[tuple(q) for q in p['points']]
        if axis=='XY':return [ViewPrimitive('polygon',tuple(pts),entity_id=eid,meta=(('semantic','room'),))]
        vals=[q[0] for q in pts] if axis=='XZ' else [q[1] for q in pts];lo,hi=_extent(vals);z0=p['z'];z1=z0+p['height']
        return [ViewPrimitive('polygon',((lo,z0),(hi,z0),(hi,z1),(lo,z1)),entity_id=eid,meta=(('semantic','room'),))]
    if e.kind=='pod':
        if axis=='XY':
            from archforge.core.plan_scene import _pod_plan_polygon
            clipped=_pod_plan_polygon(doc,e)
            if clipped is not None:
                return [ViewPrimitive('polygon',clipped,entity_id=eid,role='pod-junction-clipped',meta=(('semantic','pod'),('junction_clipped',True)))]
            return [ViewPrimitive('ellipse',((p['cx'],p['cy']),),p['diameter_x']/2,p['diameter_y']/2,eid)]
        center=p['cx'] if axis=='XZ' else p['cy'];radius=(p['diameter_x']/2) if axis=='XZ' else (p['diameter_y']/2);z0=p['floor_level'];z1=z0+p['height']
        if _pod_has_active_junction(doc, eid):
            clipped=_pod_supported_orthographic_polygon(doc,eid,axis,p)
            if clipped:
                non_circular=abs(float(p['diameter_x'])-float(p['diameter_y']))>1e-9
                rotated=abs(float(p.get('rotation',0.0)))%90.0>1e-9
                projection='supported-rotated-ellipse' if non_circular and rotated else 'supported-axis-aligned'
                return [ViewPrimitive('polygon',clipped,entity_id=eid,role='pod-junction-clipped',meta=(('top',z1),('semantic','pod'),('junction_projection',projection)))]
            return [ViewPrimitive('upper_ellipse',((center,z0),),radius,p['height'],eid,role='pod-junction-unclipped-unsupported',meta=(('top',z1),('semantic','pod'),('junction_projection','unsupported')))]
        return [ViewPrimitive('upper_ellipse',((center,z0),),radius,p['height'],eid,meta=(('top',z1),))]
    if e.kind=='organic_junction':
        if p.get('status')!='active':return []
        a_id,b_id=p.get('component_a'),p.get('component_b')
        if a_id not in doc.entities or b_id not in doc.entities:return []
        a,b=doc.get(a_id),doc.get(b_id)
        if a.kind!='pod' or b.kind!='pod':return []
        if axis=='XY':
            from archforge.core.plan_scene import _junction_plan_segment
            seg=_junction_plan_segment(doc,e)
            if seg is None:return []
            return [ViewPrimitive('line',seg,entity_id=eid,role='organic-junction',meta=(('semantic','organic_junction'),('component_a',a_id),('component_b',b_id)))]
        return []
    return []
