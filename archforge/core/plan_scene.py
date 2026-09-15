from __future__ import annotations
from dataclasses import dataclass,field
from math import cos,sin,radians,pi
from typing import List,Tuple,Optional,Dict,Any
from .model import Document
from .viewport import PreviewState
Point2=Tuple[float,float]
@dataclass(frozen=True)
class Primitive2D:kind:str;points:Tuple[Point2,...]=();radius_x:float=0.;radius_y:float=0.;rotation:float=0.;entity_id:str='';role:str='model';meta:Tuple[Tuple[str,Any],...]=()
@dataclass(frozen=True)
class Handle2D:x:float;y:float;entity_id:str;handle:str;cursor:str='size'
@dataclass
class PlanFrame:primitives:List[Primitive2D]=field(default_factory=list);handles:List[Handle2D]=field(default_factory=list);hud:Dict[str,float]=field(default_factory=dict);snap:Optional[Dict[str,Any]]=None

def _box_corners(p):
    a=radians(p.get('rotation',0.));c,s=cos(a),sin(a);hw,hd=p['width']/2,p['depth']/2;return [(p['x']+lx*c-ly*s,p['y']+lx*s+ly*c) for lx,ly in [(-hw,-hd),(hw,-hd),(hw,hd),(-hw,hd)]]
def _box_handles(eid,p):
    pts=_box_corners(p);a=radians(p.get('rotation',0.));c,s=cos(a),sin(a);hw,hd=p['width']/2,p['depth']/2
    def world(lx,ly):return(p['x']+lx*c-ly*s,p['y']+lx*s+ly*c)
    return [Handle2D(x,y,eid,h) for h,(x,y) in [('left',world(-hw,0)),('right',world(hw,0)),('bottom',world(0,-hd)),('top',world(0,hd)),('bottom_left',pts[0]),('bottom_right',pts[1]),('top_right',pts[2]),('top_left',pts[3])]]
def _pod_handles(eid,p):
    cx,cy=p['cx'],p['cy'];rx,ry=p['diameter_x']/2,p['diameter_y']/2;return [Handle2D(cx-rx,cy,eid,'left'),Handle2D(cx+rx,cy,eid,'right'),Handle2D(cx,cy-ry,eid,'bottom'),Handle2D(cx,cy+ry,eid,'top')]
def _clip_plan_polygon(points,plane,keep_sign,tolerance=1e-9):
    if not points:return []
    px,py=map(float,plane['point']);nx,ny=map(float,plane['normal']);sign=1.0 if keep_sign>=0 else -1.0
    def value(q):return sign*((float(q[0])-px)*nx+(float(q[1])-py)*ny)
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
    clean=[]
    for q in out:
        if not clean or abs(q[0]-clean[-1][0])>1e-10 or abs(q[1]-clean[-1][1])>1e-10:clean.append(q)
    if len(clean)>1 and abs(clean[0][0]-clean[-1][0])<=1e-10 and abs(clean[0][1]-clean[-1][1])<=1e-10:clean.pop()
    return clean
def _active_pod_junction_planes(doc,pod_id):
    from archforge.organic.biospectre import junction_plane,junction_section_polygon
    out=[]
    if pod_id not in doc.entities:return out
    pod=doc.get(pod_id)
    for entity in doc.entities.values():
        if entity.kind!='organic_junction' or entity.params.get('status')!='active':continue
        a_id,b_id=entity.params.get('component_a'),entity.params.get('component_b')
        if pod_id not in (a_id,b_id) or a_id not in doc.entities or b_id not in doc.entities:continue
        a,b=doc.get(a_id),doc.get(b_id)
        if a.kind!='pod' or b.kind!='pod':continue
        plane=junction_plane(a.params,b.params)
        if plane is None or junction_section_polygon(a.params,b.params) is None:continue
        px,py=map(float,plane['point']);nx,ny=map(float,plane['normal']);signed=(float(pod.params['cx'])-px)*nx+(float(pod.params['cy'])-py)*ny
        if abs(signed)<=1e-12:continue
        out.append((plane,1.0 if signed>0 else -1.0))
    return out
def _pod_plan_polygon(doc,e,segments=96):
    planes=_active_pod_junction_planes(doc,e.id)
    if not planes:return None
    p=e.params;cx,cy=float(p['cx']),float(p['cy']);rx,ry=float(p['diameter_x'])/2.0,float(p['diameter_y'])/2.0;a=radians(float(p.get('rotation',0.0)));c,s=cos(a),sin(a)
    points=[]
    for i in range(max(24,int(segments))):
        t=2.0*pi*i/max(24,int(segments));lx=rx*cos(t);ly=ry*sin(t);points.append((cx+c*lx-s*ly,cy+s*lx+c*ly))
    for plane,keep_sign in planes:
        points=_clip_plan_polygon(points,plane,keep_sign)
        if len(points)<3:return None
    return tuple(points)
def _junction_plan_segment(doc,e):
    from archforge.organic.biospectre import junction_plane,junction_section_polygon
    if e.params.get('status')!='active':return None
    a_id,b_id=e.params.get('component_a'),e.params.get('component_b')
    if a_id not in doc.entities or b_id not in doc.entities:return None
    a,b=doc.get(a_id),doc.get(b_id)
    if a.kind!='pod' or b.kind!='pod':return None
    plane=junction_plane(a.params,b.params);section=junction_section_polygon(a.params,b.params)
    if plane is None or section is None:return None
    px,py=map(float,plane['point']);nx,ny=map(float,plane['normal']);tx,ty=-ny,nx
    qs=[(float(x)-px)*tx+(float(y)-py)*ty for x,y,_ in section]
    if not qs:return None
    q0,q1=min(qs),max(qs)
    if q1-q0<=1e-9:return None
    return ((px+tx*q0,py+ty*q0),(px+tx*q1,py+ty*q1))
def _opening_segment(doc,e):
    if not e.parent_id or e.parent_id not in doc.entities:return None
    host=doc.get(e.parent_id)
    from archforge.architecture.openings import plan_segment,pod_opening_plan_segment
    if host.kind=='wall':return plan_segment(host.params,e.params)
    if host.kind=='pod':return pod_opening_plan_segment(host.params,{**e.params,'_kind':e.kind})
    return None
def entity_primitive(doc,eid):
    e=doc.get(eid);p=e.params
    if not e.visible:return None
    if e.kind=='wall':return Primitive2D('line',((p['x1'],p['y1']),(p['x2'],p['y2'])),entity_id=eid,meta=(('thickness',p['thickness']),))
    if e.kind=='box':return Primitive2D('polygon',tuple(_box_corners(p)),entity_id=eid)
    if e.kind=='pod':
        clipped=_pod_plan_polygon(doc,e)
        if clipped is not None:return Primitive2D('polygon',clipped,entity_id=eid,role='pod-junction-clipped',meta=(('semantic','pod'),('junction_clipped',True)))
        return Primitive2D('ellipse',((p['cx'],p['cy']),),p['diameter_x']/2,p['diameter_y']/2,p.get('rotation',0.),eid)
    if e.kind=='organic_junction':
        seg=_junction_plan_segment(doc,e)
        if seg is None:return None
        return Primitive2D('line',seg,entity_id=eid,role='organic-junction',meta=(('semantic','organic_junction'),('component_a',p.get('component_a')),('component_b',p.get('component_b'))))
    if e.kind in ('floor','room'):return Primitive2D('polygon',tuple(tuple(q) for q in p['points']),entity_id=eid,meta=(('semantic',e.kind),))
    if e.kind=='room_floor':
        from archforge.architecture.rooms import room_floor_geometry
        g=room_floor_geometry(doc,e)
        if g is None:return None
        return Primitive2D('polygon',tuple(g['points']),entity_id=eid,role='room-floor',meta=(('semantic','room_floor'),('signature',g['room_signature']),('thickness',g['thickness']),('z',g['z'])))
    if e.kind in ('door','window'):
        seg=_opening_segment(doc,e)
        if seg is None:return None
        a,b=seg;return Primitive2D('line',(a,b),entity_id=eid,role='opening',meta=(('semantic',e.kind),('host',e.parent_id)))
def selection_handles(doc):
    out=[]
    for eid in doc.selection:
        if eid not in doc.entities:continue
        e=doc.get(eid);p=e.params
        if e.locked:continue
        if e.kind=='wall':out.extend([Handle2D(p['x1'],p['y1'],eid,'endpoint1'),Handle2D(p['x2'],p['y2'],eid,'endpoint2')])
        elif e.kind=='box':out.extend(_box_handles(eid,p))
        elif e.kind=='pod':out.extend(_pod_handles(eid,p))
        elif e.kind in ('door','window') and e.parent_id in doc.entities:
            seg=_opening_segment(doc,e)
            if seg is None:continue
            a,b=seg;mx=(a[0]+b[0])/2;my=(a[1]+b[1])/2
            out.extend([Handle2D(a[0],a[1],eid,'left','stretch'),Handle2D(b[0],b[1],eid,'right','stretch'),Handle2D(mx,my,eid,'move','move')])
    return out
def preview_primitives(preview):
    g=preview.geometry
    if preview.kind=='wall' and g:return [Primitive2D('line',((g['x1'],g['y1']),(g['x2'],g['y2'])),entity_id=preview.entity_id or '',role='preview')]
    if preview.kind in ('opening','opening-edit') and {'x1','y1','x2','y2'}<=set(g):return [Primitive2D('line',((g['x1'],g['y1']),(g['x2'],g['y2'])),entity_id=preview.entity_id or '',role='preview',meta=(('semantic',g.get('opening_kind','opening')),))]
    if preview.kind=='stretch' and 'entities' in g:
        out=[]
        for eid,p in g['entities'].items():
            if {'x1','y1','x2','y2'}<=set(p):out.append(Primitive2D('line',((p['x1'],p['y1']),(p['x2'],p['y2'])),entity_id=eid,role='preview'))
        if out:return out
    if preview.kind in ('stretch','rotate') and g:
        eid=preview.entity_id or ''
        if {'x1','y1','x2','y2'}<=set(g):return [Primitive2D('line',((g['x1'],g['y1']),(g['x2'],g['y2'])),entity_id=eid,role='preview')]
        if {'x','y','width','depth'}<=set(g):return [Primitive2D('polygon',tuple(_box_corners(g)),entity_id=eid,role='preview')]
        if {'cx','cy','diameter_x','diameter_y'}<=set(g):return [Primitive2D('ellipse',((g['cx'],g['cy']),),g['diameter_x']/2,g['diameter_y']/2,g.get('rotation',0.),eid,'preview')]
    if preview.kind=='move' and 'entities' in g:
        out=[]
        for eid,p in g['entities'].items():
            if {'x1','y1','x2','y2'}<=set(p):out.append(Primitive2D('line',((p['x1'],p['y1']),(p['x2'],p['y2'])),entity_id=eid,role='preview'))
            elif {'x','y','width','depth'}<=set(p):out.append(Primitive2D('polygon',tuple(_box_corners(p)),entity_id=eid,role='preview'))
            elif {'cx','cy','diameter_x','diameter_y'}<=set(p):out.append(Primitive2D('ellipse',((p['cx'],p['cy']),),p['diameter_x']/2,p['diameter_y']/2,p.get('rotation',0.),eid,'preview'))
        return out
    return []
def build_plan_frame(doc,preview=None):
    f=PlanFrame()
    try:
        from archforge.architecture.topology import room_metrics
        for index,face in enumerate(doc.active_room_faces(),start=1):
            m=room_metrics(face.polygon);data=doc.room_metadata(face.signature)
            name=data.get('name') or f'Room {index}';use=data.get('use','')
            label=name+(f' — {use}' if use else '')+f'\n{m["area"]:.2f} m²'
            meta=(('semantic','derived-room'),('signature',face.signature),('wall_ids',face.wall_ids),('area',m['area']),('perimeter',m['perimeter']),('name',name),('use',use))
            f.primitives.append(Primitive2D('polygon',tuple(face.polygon),role='derived-room',meta=meta))
            cx,cy=m['centroid'];f.primitives.append(Primitive2D('label',((cx,cy),),role='derived-room-label',meta=(('signature',face.signature),('text',label))))
    except (ValueError,KeyError):
        pass
    for eid in doc.entities:
        p=entity_primitive(doc,eid)
        if p:f.primitives.append(p)
    f.handles=selection_handles(doc)
    if preview:f.primitives.extend(preview_primitives(preview));f.hud=dict(preview.hud);f.snap=preview.snap
    return f
