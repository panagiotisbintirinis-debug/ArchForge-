from __future__ import annotations
import math
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
def _beam_corners(p):
    x1,y1,x2,y2=map(float,(p['x1'],p['y1'],p['x2'],p['y2']))
    dx,dy=x2-x1,y2-y1;length=(dx*dx+dy*dy)**0.5
    if length<=1e-12:return [(x1,y1)]*4
    nx,ny=-dy/length,dx/length;half=float(p['width'])/2.0
    return [
        (x1+nx*half,y1+ny*half),(x2+nx*half,y2+ny*half),
        (x2-nx*half,y2-ny*half),(x1-nx*half,y1-ny*half),
    ]

def _structural_support_point(doc,e):
    if not e.parent_id or e.parent_id not in doc.entities:
        return None
    host=doc.get(e.parent_id);end=str(e.params.get('member_end','start'))
    if host.kind=='structural_column':
        return (float(host.params['x']),float(host.params['y']))
    if host.kind=='structural_beam':
        if end=='start':
            return (float(host.params['x1']),float(host.params['y1']))
        return (float(host.params['x2']),float(host.params['y2']))
    return None

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
    from archforge.architecture.openings import plan_segment,pod_opening_plan_segment,pod_opening_junction_conflict
    if host.kind=='wall':return plan_segment(host.params,e.params)
    if host.kind=='pod':
        if pod_opening_junction_conflict(doc,e.id) is not None:return None
        return pod_opening_plan_segment(host.params,{**e.params,'_kind':e.kind})
    return None
def _entity_on_active_level(doc,e,tolerance=1e-5):
    """Keep FLOOR PLAN focused on the active storey while 3D remains whole-building."""
    z=float(doc.work_plane.origin[2]);p=e.params
    if e.kind=='section_line':return True          # a section cuts every storey
    if e.kind=='camera':return abs(float(p.get('level_z',0.0))-z)<=tolerance
    if e.kind=='wall':return abs(float(p.get('z',0.0))-z)<=tolerance
    if e.kind=='pod':return abs(float(p.get('floor_level',0.0))-z)<=tolerance
    if e.kind in ('floor','room'):return abs(float(p.get('z',0.0))-z)<=tolerance
    if e.kind=='mep_terminal':return abs(float(p.get('level_z',0.0))-z)<=tolerance
    if e.kind in ('slab_opening','drywall_ceiling') or (e.kind in ('room_floor','room_roof','room_ceiling') and p.get('scope')=='storey'):
        return abs(float(p.get('level_z',0.0))-z)<=tolerance
    if e.kind=='structural_column':
        return str(p.get('base_level',''))==doc.active_level_name() or abs(float(p.get('z',0.0))-z)<=tolerance
    if e.kind=='structural_beam':
        return str(p.get('level',''))==doc.active_level_name()
    if e.kind=='structural_support':
        if not e.parent_id or e.parent_id not in doc.entities:return False
        return _entity_on_active_level(doc,doc.get(e.parent_id),tolerance)
    if e.kind in ('stair','ramp'):
        return abs(float(p.get('lower_z',0.0))-z)<=tolerance or abs(float(p.get('upper_z',0.0))-z)<=tolerance
    if e.kind in ('door','window','opening'):
        if not e.parent_id or e.parent_id not in doc.entities:return False
        host=doc.get(e.parent_id);hp=host.params
        if host.kind=='wall':return abs(float(hp.get('z',0.0))-z)<=tolerance
        if host.kind=='pod':return abs(float(hp.get('floor_level',0.0))-z)<=tolerance
        return False
    if e.kind in ('room_floor','room_ceiling','room_foundation','room_roof'):
        from archforge.architecture.rooms import find_room_face,find_room_face_by_id
        room_id=p.get('room_id')
        found=(
            find_room_face_by_id(doc,room_id,tolerance=tolerance)
            if room_id
            else find_room_face(doc,p.get('room_signature',''),tolerance=tolerance)
        )
        # A derived slab belongs to the storey of its semantic room even when
        # its physical plane is offset above/below that work plane (ceiling,
        # roof, or foundation). Filtering on the slab's rendered Z would hide
        # those dependants from the plan that owns them.
        return found is not None and abs(float(found[1])-z)<=tolerance
    if e.kind=='pitched_roof':
        # A roof belongs to the storey whose walls carry it.
        ez=float(p.get('eave_z',0.0))-0.05
        owner=max([float(v) for v in doc.levels.values() if float(v)<=ez]+[min([float(v) for v in doc.levels.values()]+[0.0])])
        return abs(owner-z)<=tolerance
    if e.kind=='electrical_point':
        from archforge.mep.electrical import _floor_of as elec_floor
        return abs(elec_floor(doc,float(p.get('z',0.0)))-z)<=tolerance
    if e.kind=='plumbing_point':
        from archforge.mep.plumbing import _floor_of
        return abs(_floor_of(doc,float(p.get('z',0.0)))-z)<=tolerance
    if e.kind=='ceiling_joists':return abs(float(p.get('z',0.0))-z)<=tolerance
    if e.kind=='drainage_point':
        from archforge.mep.drainage import _floor_of as drain_floor
        return abs(drain_floor(doc,float(p.get('z',0.0)))-z)<=tolerance
    if e.kind=='ventilation_point':
        from archforge.mep.ventilation import _floor_of as vent_floor
        return abs(vent_floor(doc,float(p.get('z',0.0)))-z)<=tolerance
    if e.kind=='cabinet':
        # Wall cabinets hang above their storey's floor: they belong to the
        # highest level at or below their base.
        cz=float(p.get('z',0.0))
        owner=max([float(v) for v in doc.levels.values() if float(v)<=cz+tolerance]+[min([float(v) for v in doc.levels.values()]+[0.0])])
        return abs(owner-z)<=tolerance
    if e.kind in ('plant','site_path','library_object'):return abs(float(p.get('z',0.0))-z)<=tolerance
    if e.kind=='railing':
        # Its storey, and (a stair railing) the storey its walking line reaches.
        rz=float(p.get('z',0.0))
        return abs(rz-z)<=tolerance or any(abs(rz+(float(q[2]) if len(q)>2 else 0.0)-z)<=max(tolerance,.02) for q in p.get('points',()))
    if e.kind=='terrain':
        # The site belongs to the lowest storey's plan only.
        lowest=min([float(v) for v in doc.levels.values()]+[0.0])
        return z<=lowest+tolerance
    return True

def entity_primitive(doc,eid):
    e=doc.get(eid);p=e.params
    if not e.visible:return None
    if e.kind=='wall':return Primitive2D('line',((p['x1'],p['y1']),(p['x2'],p['y2'])),entity_id=eid,meta=(('thickness',p['thickness']),))
    if e.kind=='section_line':
        return Primitive2D('polyline',((float(p['x1']),float(p['y1'])),(float(p['x2']),float(p['y2']))),entity_id=eid,role='section-line')
    if e.kind=='camera':
        # Saved camera (core/cameras.py): the body is what the mouse picks; cone and name follow below.
        from archforge.core.cameras import plan_body
        return plan_body(p,eid)
    if e.kind=='site_path':
        from archforge.site.paths import path_outline
        return Primitive2D('polygon',tuple(path_outline(p)),entity_id=eid,role='site-path')
    if e.kind=='railing':
        from archforge.architecture.railings import plan_outline
        rings=plan_outline(p)
        if len(rings)==1:return Primitive2D('polygon',tuple(rings[0]),entity_id=eid,role='railing',meta=(('railing_type',p.get('railing_type','')),))
        return Primitive2D('polyline',tuple(rings[0]),entity_id=eid,role='railing',meta=(('railing_type',p.get('railing_type','')),))
    if e.kind=='plant':
        r=float(p['canopy'])/2.0
        return Primitive2D('ellipse',((float(p['x']),float(p['y'])),),r,r,0.,eid,'plant')
    if e.kind=='pitched_roof':
        from archforge.structure.timber_roof import planes
        pts=[q for plane in planes(p) for q in plane[0]]
        xs=[q[0] for q in pts];ys=[q[1] for q in pts]
        return Primitive2D('polyline',((min(xs),min(ys)),(max(xs),min(ys)),(max(xs),max(ys)),(min(xs),max(ys)),(min(xs),min(ys))),entity_id=eid,role='roof-outline')
    if e.kind=='electrical_point':
        from archforge.mep.electrical import POINT_TYPES as ELEC
        return Primitive2D('ellipse',((float(p['x']),float(p['y'])),),.10,.10,0.,eid,'electrical-point',
                           meta=(('text',ELEC[p['point_type']][4]),('point_type',p['point_type'])))
    if e.kind=='ceiling_joists':return Primitive2D('polygon',tuple(tuple(q) for q in p['points']),entity_id=eid,role='joists-area')
    if e.kind=='drainage_point':
        r=.30 if p['point_type']=='manhole' else (.09 if p['point_type']=='stack' else .08)
        x,y=float(p['x']),float(p['y'])
        return Primitive2D('polygon',((x-r,y-r),(x+r,y-r),(x+r,y+r),(x-r,y+r)),entity_id=eid,role='drainage-point',meta=(('point_type',p['point_type']),))
    if e.kind=='ventilation_point':
        from archforge.mep.ventilation import POINT_TYPES as VENT
        r=.30 if p['point_type']=='hood' else .10
        x,y=float(p['x']),float(p['y'])
        return Primitive2D('polygon',((x-r,y-r*.8),(x+r,y-r*.8),(x+r,y+r*.8),(x-r,y+r*.8)),entity_id=eid,role='ventilation-point',
                           meta=(('text',VENT[p['point_type']][4]),('point_type',p['point_type'])))
    if e.kind=='plumbing_point':
        from archforge.mep.plumbing import POINT_TYPES
        return Primitive2D('ellipse',((float(p['x']),float(p['y'])),),.12,.12,0.,eid,'plumbing-point',
                           meta=(('text',POINT_TYPES[p['point_type']][4]),('point_type',p['point_type'])))
    if e.kind=='cabinet':
        from archforge.kitchen.cabinets import footprint as cabinet_footprint
        role='cabinet-wall' if p.get('cabinet_type')=='wall' else 'cabinet'
        return Primitive2D('polygon',tuple(cabinet_footprint(p)),entity_id=eid,role=role)
    if e.kind=='library_object':
        from archforge.library.objects import footprint
        return Primitive2D('polygon',tuple(footprint(p)),entity_id=eid,role='library-object')
    if e.kind=='terrain':
        x0,y0,x1,y1=(float(p[k]) for k in ('x0','y0','x1','y1'))
        # Outline only: clicking inside the site must still hit the model.
        return Primitive2D('polyline',((x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)),entity_id=eid,role='terrain')
    if e.kind=='mep_terminal':
        radius=max(0.06,float(p.get('diameter',0.02))*1.5)
        return Primitive2D(
            'ellipse',((float(p['x']),float(p['y'])),),
            radius,radius,0.0,eid,'mep-terminal',
            meta=(('semantic','mep_terminal'),('system_type',p.get('system_type',''))),
        )
    if e.kind=='mesh' and p.get('metadata',{}).get('semantic_type')=='conduit':
        points=tuple(
            (float(q[0]),float(q[1]))
            for q in p.get('metadata',{}).get('source_path_vertices',())
            if isinstance(q,(list,tuple)) and len(q)>=2
        )
        if len(points)>=2:
            return Primitive2D(
                'polyline',points,entity_id=eid,role='mep-conduit',
                meta=(('semantic','conduit'),('system_type',p.get('metadata',{}).get('system_type',''))),
            )
    if e.kind=='structural_column':
        return Primitive2D(
            'polygon',tuple(_box_corners(p)),entity_id=eid,role='structural-column',
            meta=(('semantic','structural_column'),('role',p.get('role','structural')),('construction',p.get('construction','generic'))),
        )
    if e.kind=='structural_beam':
        return Primitive2D(
            'polygon',tuple(_beam_corners(p)),entity_id=eid,role='structural-beam',
            meta=(('semantic','structural_beam'),('role',p.get('role','structural')),('construction',p.get('construction','generic'))),
        )
    if e.kind=='structural_support':
        point=_structural_support_point(doc,e)
        if point is None:return None
        x,y=point;r=.16
        return Primitive2D(
            'polygon',((x-r,y-r),(x+r,y-r),(x,y+r)),entity_id=eid,role='structural-support',
            meta=(('semantic','structural_support'),('support_type',p.get('support_type','fixed')),('member_end',p.get('member_end','start'))),
        )
    if e.kind=='box':return Primitive2D('polygon',tuple(_box_corners(p)),entity_id=eid)
    if e.kind=='stair':
        from archforge.architecture.stairs import candidate_from_params,stair_footprint
        candidate=candidate_from_params(p)
        return Primitive2D(
            'polygon',
            tuple(stair_footprint(candidate)),
            entity_id=eid,
            role='stair',
            meta=(('semantic','stair'),('layout',candidate.layout),('risers',candidate.riser_count)),
        )
    if e.kind=='ramp':
        from archforge.architecture.ramps import candidate_from_params,ramp_footprint
        candidate=candidate_from_params(p)
        return Primitive2D(
            'polygon',
            tuple(ramp_footprint(candidate)),
            entity_id=eid,
            role='ramp',
            meta=(('semantic','ramp'),('slope_pct',candidate.slope_pct),('run_length',candidate.run_length)),
        )
    if e.kind=='pod':
        clipped=_pod_plan_polygon(doc,e)
        if clipped is not None:return Primitive2D('polygon',clipped,entity_id=eid,role='pod-junction-clipped',meta=(('semantic','pod'),('junction_clipped',True)))
        return Primitive2D('ellipse',((p['cx'],p['cy']),),p['diameter_x']/2,p['diameter_y']/2,p.get('rotation',0.),eid)
    if e.kind=='organic_junction':
        seg=_junction_plan_segment(doc,e)
        if seg is None:return None
        return Primitive2D('line',seg,entity_id=eid,role='organic-junction',meta=(('semantic','organic_junction'),('component_a',p.get('component_a')),('component_b',p.get('component_b'))))
    if e.kind in ('floor','room'):return Primitive2D('polygon',tuple(tuple(q) for q in p['points']),entity_id=eid,meta=(('semantic',e.kind),))
    if e.kind in ('room_floor','room_ceiling','room_foundation','room_roof'):
        from archforge.architecture.rooms import room_slab_geometry
        g=room_slab_geometry(doc,e)
        if g is None:return None
        role=e.kind.replace('_','-')
        islands=g.get('islands') or ()
        cut=(('islands',tuple((tuple(o),tuple(tuple(h) for h in hs)) for o,hs in islands)),) if len(islands)>1 or any(hs for _o,hs in islands) else ()
        return Primitive2D(
            'polygon',
            tuple(g['points']),
            entity_id=eid,
            role=role,
            meta=(
                ('semantic',e.kind),
                ('signature',g['room_signature']),
                ('thickness',g['thickness']),
                ('z',g['z']),
            )+cut,
        )
    if e.kind=='drywall_ceiling':
        # Suspended ceiling: above the cut plane, dashed (Greek practice for Ψ/Ο).
        from archforge.construction.drywall import outline
        poly=outline(doc,e)
        if not poly:return None
        return Primitive2D('polygon',tuple(poly),entity_id=eid,role='drywall-ceiling',meta=(('semantic','drywall_ceiling'),('board',p.get('board','standard'))))
    if e.kind=='slab_opening':
        from archforge.architecture.storey_slabs import opening_polygon
        poly=opening_polygon(doc,e)
        if not poly:return None
        # Above the cut plane (roof only): dashed, as a void in the slab over the storey.
        return Primitive2D('polygon',tuple(poly),entity_id=eid,role='slab-opening',
                           meta=(('semantic','slab_opening'),('above',p.get('cuts')=='roof'),('use',p.get('use','void'))))
    if e.kind in ('door','window','opening'):
        seg=_opening_segment(doc,e)
        if seg is None:return None
        a,b=seg
        typed=e.kind in ('door','window') and str(p.get('opening_type','basic'))!='basic'
        return Primitive2D('line',(a,b),entity_id=eid,role='opening',meta=(('semantic',e.kind),('host',e.parent_id))+((('typed',True),) if typed else ()))
    if e.kind=='arboreal_branch':
        from archforge.organic.arboreal import arboreal_branch_geometry
        geom=arboreal_branch_geometry(doc,eid)
        s,t=geom['start'],geom['end']
        return Primitive2D('line',((s[0],s[1]),(t[0],t[1])),entity_id=eid,role='arboreal-branch',meta=(('semantic','arboreal_branch'),('core_id',p.get('core_id')),('mounted_pod_id',p.get('mounted_pod_id')),('engineering_verified',False)))
def selection_handles(doc):
    out=[]
    for eid in doc.selection:
        if eid not in doc.entities:continue
        e=doc.get(eid);p=e.params
        if e.locked or not _entity_on_active_level(doc,e):continue
        if e.kind=='wall':out.extend([Handle2D(p['x1'],p['y1'],eid,'endpoint1'),Handle2D(p['x2'],p['y2'],eid,'endpoint2')])
        elif e.kind=='structural_column':
            out.append(Handle2D(float(p['x']),float(p['y']),eid,'move','move'))
        elif e.kind=='structural_beam':
            mx=(float(p['x1'])+float(p['x2']))/2.0;my=(float(p['y1'])+float(p['y2']))/2.0
            out.extend([
                Handle2D(float(p['x1']),float(p['y1']),eid,'endpoint1','stretch'),
                Handle2D(float(p['x2']),float(p['y2']),eid,'endpoint2','stretch'),
                Handle2D(mx,my,eid,'move','move'),
            ])
        elif e.kind=='mep_terminal':out.append(Handle2D(float(p['x']),float(p['y']),eid,'move','move'))
        elif e.kind=='camera':
            # Camera: drag the eye to move it, the tip of the cone to turn it (ui/camera_tool.py).
            from archforge.core.cameras import aim_point
            ax,ay=aim_point(p)
            out.extend([Handle2D(float(p['x']),float(p['y']),eid,'camera_move','move'),Handle2D(ax,ay,eid,'camera_aim','rotate')])
        elif e.kind=='slab_opening' and p.get('points'):
            pts=p['points'];out.append(Handle2D(sum(q[0] for q in pts)/len(pts),sum(q[1] for q in pts)/len(pts),eid,'move','move'))
        elif e.kind=='box':out.extend(_box_handles(eid,p))
        elif e.kind=='pod':out.extend(_pod_handles(eid,p))
        elif e.kind=='arboreal_branch':
            from archforge.organic.arboreal import arboreal_branch_geometry
            geom=arboreal_branch_geometry(doc,eid)
            s,t=geom['start'],geom['end']
            out.extend([Handle2D(s[0],s[1],eid,'root','move'),Handle2D(t[0],t[1],eid,'tip','stretch')])
        elif e.kind in ('door','window','opening') and e.parent_id in doc.entities:
            seg=_opening_segment(doc,e)
            if seg is None:continue
            a,b=seg;mx=(a[0]+b[0])/2;my=(a[1]+b[1])/2
            out.extend([Handle2D(a[0],a[1],eid,'left','stretch'),Handle2D(b[0],b[1],eid,'right','stretch'),Handle2D(mx,my,eid,'move','move')])
            if e.kind in ('door','window'):
                # Small handle on the swing arc: a click turns the opening the other way (one undo).
                flip=_swing_handle_point(doc,e,a,b)
                if flip:out.append(Handle2D(flip[0],flip[1],eid,'flip_swing','flip'))
    if len(doc.selection)==1 and doc.selection[0] in doc.entities:
        # Round rotation handle in front of the selected object (object_ops).
        from archforge.core.object_ops import ROTATABLE_KINDS,rotate_handle_point
        e=doc.get(doc.selection[0])
        if e.kind in ROTATABLE_KINDS and (not e.kind.startswith('structural_') or e.params.get('role')=='pergola') and not e.locked and str(e.params.get('phase','new'))!='existing' and _entity_on_active_level(doc,e):
            try:
                hx,hy=rotate_handle_point(doc,e.id);out.append(Handle2D(hx,hy,e.id,'rotate','rotate'))
            except (KeyError,ValueError,TypeError):pass
    return out
def _swing_handle_point(doc,e,a,b):
    """Point on the side the door/window opens to, half a leaf out from the wall."""
    host=doc.entities.get(e.parent_id)
    if host is None or host.kind!='wall':return None
    from archforge.architecture.joinery import SWINGING,inside_sign,resolved
    r=resolved(e.kind,e.params)
    if e.kind=='window' and r['opening_type'] not in SWINGING:return None
    L=math.hypot(b[0]-a[0],b[1]-a[1])
    if L<1e-9:return None
    nx,ny=-(b[1]-a[1])/L,(b[0]-a[0])/L
    side=inside_sign(doc,host)*(1 if r['swing']=='in' else -1)
    reach=float(host.params.get('thickness',.2))/2+min(.45,L*.45)
    return ((a[0]+b[0])/2+nx*side*reach,(a[1]+b[1])/2+ny*side*reach)
def preview_primitives(preview):
    g=preview.geometry
    if preview.kind=='wall' and g:
        out=[Primitive2D('line',((g['x1'],g['y1']),(g['x2'],g['y2'])),entity_id=preview.entity_id or '',role='preview')]
        hud=dict(preview.hud or {})
        if 'corner_deg' in hud:
            # Corner mark: an arc from the previous wall to the new one, with the degrees.
            x0,y0=float(g['x1']),float(g['y1']);a0=float(hud['previous_deg']);a1=float(hud['angle_deg'])
            sweep=(a1-a0+180.0)%360.0-180.0;r=.45
            pts=tuple((x0+r*cos(radians(a0+sweep*k/16)),y0+r*sin(radians(a0+sweep*k/16))) for k in range(17))
            out.append(Primitive2D('polyline',pts,role='angle-arc',meta=(('magnet',float(hud.get('magnet',0.0))),)))
            mid=radians(a0+sweep/2);mag=float(hud.get('magnet',0.0))
            out.append(Primitive2D('label',((x0+(r+.25)*cos(mid),y0+(r+.25)*sin(mid)),),role='angle-label',
                                   meta=(('text',f"{float(hud['corner_deg']):.0f}°"+(' ◆' if mag else '')),)))
        return out
    if preview.kind=='component' and g:
        return [Primitive2D('polygon',tuple(_box_corners(g)),entity_id=preview.entity_id or '',role='preview',meta=(('semantic','component-preview'),('fits',bool(g.get('fits',True)))))]
    if preview.kind=='structural-column' and g:
        return [Primitive2D('polygon',tuple(_box_corners(g)),entity_id=preview.entity_id or '',role='preview',meta=(('semantic','structural-column-preview'),))]
    if preview.kind=='structural-beam' and g:
        return [Primitive2D('polygon',tuple(_beam_corners(g)),entity_id=preview.entity_id or '',role='preview',meta=(('semantic','structural-beam-preview'),))]
    if preview.kind=='mep-terminal' and g:
        radius=max(0.06,float(g.get('diameter',0.02))*1.5)
        return [Primitive2D('ellipse',((float(g['x']),float(g['y'])),),radius,radius,0.0,preview.entity_id or '','preview',meta=(('semantic','mep_terminal'),('system_type',g.get('system_type',''))))]
    if preview.kind=='stair' and g:
        candidates=list(g.get('candidates',()))
        if not candidates:return []
        index=max(0,min(int(g.get('active_index',0)),len(candidates)-1))
        from archforge.architecture.stairs import candidate_from_params,stair_footprint
        candidate=candidate_from_params(candidates[index])
        return [
            Primitive2D(
                'polygon',
                tuple(stair_footprint(candidate)),
                role='preview',
                meta=(
                    ('semantic','stair-preview'),
                    ('layout',candidate.layout),
                    ('option_index',index),
                ),
            )
        ]
    if preview.kind=='ramp' and g:
        candidates=list(g.get('candidates',()))
        if not candidates:return []
        index=max(0,min(int(g.get('active_index',0)),len(candidates)-1))
        from archforge.architecture.ramps import candidate_from_params,ramp_footprint
        candidate=candidate_from_params(candidates[index])
        return [
            Primitive2D(
                'polygon',
                tuple(ramp_footprint(candidate)),
                role='preview',
                meta=(
                    ('semantic','ramp-preview'),
                    ('slope_pct',candidate.slope_pct),
                    ('option_index',index),
                ),
            )
        ]
    if preview.kind in ('opening','opening-edit') and {'x1','y1','x2','y2'}<=set(g):return [Primitive2D('line',((g['x1'],g['y1']),(g['x2'],g['y2'])),entity_id=preview.entity_id or '',role='preview',meta=(('semantic',g.get('opening_kind','opening')),))]
    if preview.kind=='wall-move' and g:
        # Dragged wall: moved/stretched wall lines, the objects riding along, the distance.
        bad=bool(g.get('problem'))
        out=[Primitive2D('line',((p['x1'],p['y1']),(p['x2'],p['y2'])),entity_id=eid,role='preview',meta=(('fits',not bad),))
             for eid,p in g.get('walls',{}).items()]
        out+=[Primitive2D('polygon',tuple(pts),entity_id=oid,role='preview') for oid,pts in g.get('objects',{}).items() if len(pts)>2]
        out+=[Primitive2D('line',tuple(seg),role='wall-move-opening') for seg in g.get('openings',())]
        a,b=g['from'],g['to']
        out.append(Primitive2D('polyline',(tuple(a),tuple(b)),role='wall-move-arrow'))
        d=float(g.get('distance',0.0))
        text=f"{'⚠ '+g['problem'] if bad else ('↔ ' if abs(a[1]-b[1])<abs(a[0]-b[0])+1e-9 else '↕ ')+format(abs(d)*100,'.0f')+' cm'}"
        out.append(Primitive2D('label',((b[0]+.15,b[1]+.15),),role='wall-move-label',meta=(('text',text),)))
        return out
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
            elif 'layout' in p and {'x','y','riser_count','tread_depth'}<=set(p):
                from archforge.architecture.stairs import candidate_from_params,stair_footprint
                out.append(Primitive2D('polygon',tuple(stair_footprint(candidate_from_params(p))),entity_id=eid,role='preview'))
            elif 'slope_pct' in p and {'x','y','run_length','width'}<=set(p):
                from archforge.architecture.ramps import candidate_from_params,ramp_footprint
                out.append(Primitive2D('polygon',tuple(ramp_footprint(candidate_from_params(p))),entity_id=eid,role='preview'))
            elif {'x','y','width','depth'}<=set(p):out.append(Primitive2D('polygon',tuple(_box_corners(p)),entity_id=eid,role='preview'))
            elif {'cx','cy','diameter_x','diameter_y'}<=set(p):out.append(Primitive2D('ellipse',((p['cx'],p['cy']),),p['diameter_x']/2,p['diameter_y']/2,p.get('rotation',0.),eid,'preview'))
        return out
    return []
def _storey_z(doc,e):
    p=e.params
    if e.kind=='wall':return float(p.get('z',0.0))
    if e.kind=='pod':return float(p.get('floor_level',0.0))
    if e.kind in ('door','window','opening'):
        if not e.parent_id or e.parent_id not in doc.entities:return None
        hp=doc.get(e.parent_id).params
        return float(hp.get('z',hp.get('floor_level',0.0)))
    if e.kind in ('structural_column',):return float(p.get('z',0.0))
    if e.kind in ('floor','room'):return float(p.get('z',0.0))
    return None


def _lower_storey_underlay(doc,f,tolerance=1e-5):
    """Grey, non-editable reference of the storey directly below.

    Drawing an upper floor needs the lower walls to trace over; they carry no
    entity id, so they cannot be picked, selected or edited from here.
    """
    active_z=float(doc.work_plane.origin[2])
    kinds=('wall','pod','door','window','opening','structural_column','floor','room')
    below=[]
    for eid,e in doc.entities.items():
        if e.kind not in kinds or not e.visible:continue
        z=_storey_z(doc,e)
        if z is not None and z<active_z-tolerance:below.append((z,eid))
    if not below:return
    target=max(z for z,_ in below)
    for z,eid in below:
        if abs(z-target)>tolerance:continue
        primitive=entity_primitive(doc,eid)
        if primitive is None or primitive.kind=='label':continue
        f.primitives.append(Primitive2D(
            primitive.kind,primitive.points,primitive.radius_x,primitive.radius_y,
            primitive.rotation,'','floor-underlay',primitive.meta,
        ))


# Structural labels keep a constant size on screen (pixels), so their box in metres
# depends on the zoom. Estimated from Qt's default 9 pt font (measured: ≈6.8 px per
# character, 15.5 px per line, 8 px of margins).
LABEL_CHAR_PX=6.8;LABEL_LINE_PX=15.5;LABEL_MARGIN_PX=8.0
# px per metre: below it the structural labels hide (no carpet of text when zoomed out).
LABEL_MIN_SCALE=40.0
_LABEL_SCALES=(1.0,1.25,1.6,2.0,2.5,3.2,4.0,5.0,6.4,8.0)

def label_box(anchor,align,text,scale):
    """(x0,y0,x1,y1) in metres of a label drawn at ``scale`` px/m.

    ``align`` (hx,vy) is the point of the text box on the anchor: (0,0) top-left
    (text below-right of the anchor), (1,1) bottom-right, (.5,1) centred above.
    The box shrinks towards its anchor as the view zooms in, so labels apart at
    one zoom stay apart at every closer zoom.
    """
    lines=str(text).split('\n')
    w=(LABEL_MARGIN_PX+LABEL_CHAR_PX*max(len(q) for q in lines))/scale
    h=(LABEL_MARGIN_PX+LABEL_LINE_PX*len(lines))/scale
    (x,y),(hx,vy)=anchor,align
    return (x-hx*w,y-(1-vy)*h,x+(1-hx)*w,y+vy*h)

from functools import lru_cache
@lru_cache(maxsize=8)
def place_labels(items):
    """Simple label collision avoidance: ``items`` = ((text, ((anchor, align), ...)), ...) in priority order.

    Each label takes its first candidate position that overlaps no label placed
    before it; if none fits at the base zoom, the closest zoom where one fits is
    kept as its ``min_scale`` (the view hides it until then). Returns
    ((anchor, align, min_scale), ...).
    """
    placed=[];cells={};out=[];cell=1.0
    def keys(b):
        for i in range(int(math.floor(b[0]/cell)),int(math.floor(b[2]/cell))+1):
            for j in range(int(math.floor(b[1]/cell)),int(math.floor(b[3]/cell))+1):
                yield (i,j)
    def free(text,anchor,align,scale):
        b=label_box(anchor,align,text,scale);seen=set()
        for k in keys(b):
            for n in cells.get(k,()):
                if n in seen:continue
                seen.add(n);t2,a2,al2,s2=placed[n];o=label_box(a2,al2,t2,max(scale,s2))
                if b[0]<o[2] and o[0]<b[2] and b[1]<o[3] and o[1]<b[3]:return False
        return True
    for text,candidates in items:
        choice=None
        for factor in _LABEL_SCALES:
            scale=LABEL_MIN_SCALE*factor
            for anchor,align in candidates:
                if free(text,anchor,align,scale):choice=(anchor,align,scale);break
            if choice:break
        if choice is None:
            anchor,align=candidates[0];choice=(anchor,align,LABEL_MIN_SCALE*_LABEL_SCALES[-1]*2)
        n=len(placed);placed.append((text,)+choice)
        for k in keys(label_box(choice[0],choice[1],text,choice[2])):cells.setdefault(k,[]).append(n)
        out.append(choice)
    return tuple(out)

def _corner_candidates(x,y,hx,hy,gap=.05,order=('ne','se','nw','sw')):
    spots={'ne':((x+hx+gap,y+hy+gap),(0.,1.)),'se':((x+hx+gap,y-hy-gap),(0.,0.)),
           'nw':((x-hx-gap,y+hy+gap),(1.,1.)),'sw':((x-hx-gap,y-hy-gap),(1.,0.))}
    return tuple(spots[k] for k in order)

def _axis_candidates(a,b,offset,first_side=1):
    """Beside a member's axis, on one side then the other, at mid then at the quarters."""
    (ax,ay),(bx,by)=a,b;L=math.hypot(bx-ax,by-ay) or 1.0;nx,ny=-(by-ay)/L,(bx-ax)/L
    out=[]
    for t in (.5,.25,.75):
        for side in (first_side,-first_side):
            sx,sy=nx*side,ny*side
            hx=0. if sx>.35 else (1. if sx<-.35 else .5)
            vy=1. if sy>.35 else (0. if sy<-.35 else .5)
            out.append(((ax+(bx-ax)*t+sx*offset,ay+(by-ay)*t+sy*offset),(hx,vy)))
    return tuple(out)

_CONTOURS={'key':None,'value':[]}


def build_plan_frame(doc,preview=None,layers=True):
    f=PlanFrame()
    _lower_storey_underlay(doc,f)
    try:
        from archforge.architecture.topology import room_metrics
        for index,face in enumerate(doc.active_room_faces(),start=1):
            m=room_metrics(face.polygon);data=doc.room_metadata(face.signature)
            name=data.get('name') or f'Χώρος {index}';use=data.get('use','')
            label=name+(f' — {use}' if use else '')+f'\n{m["area"]:.2f} m²'
            meta=(('semantic','derived-room'),('signature',face.signature),('wall_ids',face.wall_ids),('area',m['area']),('perimeter',m['perimeter']),('name',name),('use',use))
            f.primitives.append(Primitive2D('polygon',tuple(face.polygon),role='derived-room',meta=meta))
            cx,cy=m['centroid'];f.primitives.append(Primitive2D('label',((cx,cy),),role='derived-room-label',meta=(('signature',face.signature),('text',label))))
    except (ValueError,KeyError):
        pass
    for eid,e in doc.entities.items():
        if e.kind!='terrain' or not e.visible or not _entity_on_active_level(doc,e):continue
        # The plot: its boundary with the area, and the ground's contour lines.
        bnd=e.params.get('boundary') or ()
        if len(bnd)>=3:
            pts=tuple((float(x),float(y)) for x,y in bnd)
            f.primitives.append(Primitive2D('polyline',pts+(pts[0],),entity_id=eid,role='plot-boundary'))
            area=abs(sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts))))/2
            f.primitives.append(Primitive2D('label',((min(x for x,_ in pts)+.3,max(y for _,y in pts)-.3),),role='plot-label',
                                            meta=(('text',f'Οικόπεδο {area:.1f} m²'),)))
        if e.params.get('points') and len(e.params['points'])>3:
            from archforge.site.survey import contours
            key=(e.id,repr(sorted(e.params.items())))
            if _CONTOURS.get('key')!=key:
                _CONTOURS['key'],_CONTOURS['value']=key,contours(e.params)
            for level,segment in _CONTOURS['value']:
                f.primitives.append(Primitive2D('polyline',tuple(segment),role='contour',meta=(('z',level),)))
        survey=len(e.params.get('points') or ())>40
        for px,py,pz in e.params.get('points') or ():
            if survey:
                continue                       # a survey: the contours say it; hundreds of labels would hide the plan
            f.primitives.append(Primitive2D('ellipse',((float(px),float(py)),),.12,.12,0.,eid,'terrain'))
            f.primitives.append(Primitive2D('label',((float(px)+.15,float(py)+.15),),role='terrain-label',
                                            meta=(('text',f'{float(pz):+.2f}'),)))
    for eid in doc.entities:
        # FLOOR PLAN shows the active storey only; a stair/ramp touching it
        # (e.g. the flight down from an upper storey) stays visible.
        if not _entity_on_active_level(doc,doc.get(eid)):continue
        p=entity_primitive(doc,eid)
        if p:f.primitives.append(p)
        if p and doc.get(eid).kind=='stair':
            # Plan symbol of the stair for this storey: the flight it starts (ΑΝ, cut at ~1,10 m)
            # or the one arriving from below (opening + visible steps, ΚΑΤ) — architecture/stairs.py.
            from archforge.architecture.stairs import candidate_from_params,stair_plan_symbol
            q=doc.get(eid).params;level=float(doc.work_plane.origin[2])
            view='lower' if abs(float(q.get('lower_z',0.0))-level)<=1e-5 else 'upper'
            lines,labels=stair_plan_symbol(candidate_from_params(q),view,numbers=bool(q.get('plan_numbers',0)))
            for style,pts in lines:
                f.primitives.append(Primitive2D('polyline',tuple(pts),entity_id=eid,role='stair-'+style,meta=(('view',view),)))
            for text,at,kind in labels:
                f.primitives.append(Primitive2D('label',(at,),entity_id=eid,role='stair-label',
                                                meta=(('text',text),('align',(.5,.5)),('kind',kind))))
        if p and p.role=='section-line':
            # Section mark (output/section_cut.py): arrows where you look and the letter at both ends.
            from archforge.output.section_cut import plan_symbol,section_letter
            sym=plan_symbol(doc.get(eid).params,section_letter(doc.get(eid).name))
            for tail,head,(w1,w2) in sym['arrows']:
                f.primitives.append(Primitive2D('polyline',(tail,head),entity_id=eid,role='section-arrow'))
                f.primitives.append(Primitive2D('polygon',(head,w1,w2),entity_id=eid,role='section-arrow'))
            for text,at in sym['labels']:
                f.primitives.append(Primitive2D('label',(at,),entity_id=eid,role='section-label',meta=(('text',text),('align',(.5,.5)))))
        if p and p.role=='camera':
            # Saved camera: view cone, lens and name (core/cameras.py); the cone goes under everything.
            from archforge.core.cameras import plan_extras
            extras=plan_extras(doc.get(eid).params,doc.get(eid).name,eid,eid in (doc.selection or ()))
            f.primitives[0:0]=extras[:2];f.primitives.extend(extras[2:])
        if p and p.role=='slab-opening':
            # Void in the slab: diagonal cross (Greek drafting practice).
            from archforge.architecture.storey_slabs import plan_cross
            for a,b in plan_cross(list(p.points)):
                f.primitives.append(Primitive2D('line',(a,b),entity_id=eid,role='slab-opening-cross',meta=p.meta))
        if p and p.role=='drywall-ceiling':
            # Step of a cove ceiling (dashed inner line) and the level label «Ψ/Ο +2,60».
            from archforge.construction.drywall import ceiling_level,inner_outline
            q=doc.get(eid).params
            inner=inner_outline(list(p.points),float(q.get('cove_width',.30))) if int(q.get('cove',0)) else None
            if inner:f.primitives.append(Primitive2D('polyline',tuple(inner)+(inner[0],),entity_id=eid,role='drywall-ceiling-step'))
            xs=[a for a,_b in p.points];ys=[b for _a,b in p.points]
            text=f"Ψ/Ο +{ceiling_level(doc,q):.2f}".replace('.',',')
            f.primitives.append(Primitive2D('label',((min(xs)+.08,min(ys)+.30),),entity_id=eid,role='drywall-ceiling-label',meta=(('text',text),)))
        if p and doc.get(eid).kind=='room_roof':
            # A terrace in several pieces (around a smaller upper floor): the other pieces too.
            from archforge.architecture.rooms import room_slab_geometry
            for part in (room_slab_geometry(doc,doc.get(eid)) or {}).get('parts',())[1:]:
                f.primitives.append(Primitive2D('polygon',tuple(part),entity_id=eid,role=p.role,meta=p.meta))
        if p and doc.get(eid).kind=='wall' and doc.get(eid).params.get('wall_type','generic')!='generic':
            # Layer boundaries of the wall assembly; insulation drawn dashed.
            from archforge.architecture.wall_types import layer_lines
            for pts,insulation in layer_lines(doc.get(eid).params,doc.get(eid).params['wall_type']):
                f.primitives.append(Primitive2D('polyline',tuple(pts),entity_id=eid,role='wall-insulation' if insulation else 'wall-layer'))
        if p and doc.get(eid).kind=='pitched_roof':
            from archforge.structure.timber_roof import members
            for role,a,b,_size in members(doc.get(eid).params):
                if role in ('ridge','hip'):
                    f.primitives.append(Primitive2D('polyline',((a[0],a[1]),(b[0],b[1])),entity_id=eid,role='roof-ridge'))
        if p and doc.get(eid).kind=='cabinet':
            from archforge.kitchen.cabinets import front_line,footprint as cabinet_footprint,plan_marks
            q=doc.get(eid).params
            f.primitives.append(Primitive2D('polyline',tuple(front_line(q)),entity_id=eid,role='cabinet-front'))
            # Mechanisms that show in plan (carousel, half-moon trays): hidden (dashed) lines.
            for pts in plan_marks(q):
                f.primitives.append(Primitive2D('polyline',tuple(pts),entity_id=eid,role='cabinet-wall'))
            if q.get('cabinet_type')=='wall':
                # Plan convention for cabinets above the work plane: dashed outline and a cross.
                c=cabinet_footprint(q)
                f.primitives.append(Primitive2D('polyline',(c[0],c[2]),entity_id=eid,role='cabinet-wall'))
                f.primitives.append(Primitive2D('polyline',(c[1],c[3]),entity_id=eid,role='cabinet-wall'))
        if p and doc.get(eid).kind in ('door','window'):
            # Typed joinery: plan symbol with the opening direction (architecture/joinery.py).
            from archforge.architecture.joinery import plan_symbol_world
            for style,pts in plan_symbol_world(doc,doc.get(eid)):
                f.primitives.append(Primitive2D('polyline',tuple(pts),entity_id=eid,
                                                role='opening-symbol-hidden' if style=='dashed' else 'opening-symbol',
                                                meta=(('style',style),)))
        if p and doc.get(eid).kind=='railing':
            # Inner ring of a closed railing and the posts, from the same parameters as the 3D.
            from archforge.architecture.railings import plan_outline,plan_posts
            q=doc.get(eid).params
            for ring in plan_outline(q)[1:]:
                f.primitives.append(Primitive2D('polyline',tuple(ring),entity_id=eid,role='railing'))
            for sq in plan_posts(q):
                f.primitives.append(Primitive2D('polyline',tuple(sq),entity_id=eid,role='railing-post'))
        if p and doc.get(eid).kind=='library_object':
            # The derived 2D symbol (outline + inner lines) of the same asset.
            from archforge.library.objects import plan_symbol_world
            for closed,pts in plan_symbol_world(doc.get(eid).params):
                if len(pts)>=2:
                    f.primitives.append(Primitive2D('polyline',tuple(pts+pts[:1] if closed else pts),entity_id=eid,role='library-symbol'))
    # Derived parts of the cabinet runs (kitchen/cabinet_run.py): worktop with its cut-outs, sink, hob, hood.
    if any(e.kind=='cabinet' and e.params.get('run_id') for e in doc.entities.values()):
        from archforge.kitchen.cabinet_run import plan_primitives as run_primitives
        for role,pts,closed in run_primitives(doc):
            f.primitives.append(Primitive2D('polyline',tuple(pts)+((pts[0],) if closed else ()),role=role))
    # Derived water pipes of the active storey (horizontal runs in the screed).
    if any(e.kind=='plumbing_point' for e in doc.entities.values()):
        from archforge.mep.plumbing import POINT_TYPES,SCREED,route_plumbing_cached
        level=float(doc.work_plane.origin[2])
        network=route_plumbing_cached(doc)
        for system in ('cold','hot'):
            for a,b,dia in network[system]:
                if abs(a[2]-b[2])<1e-9 and abs(a[2]-(level+SCREED))<1e-6:
                    f.primitives.append(Primitive2D('polyline',((a[0],a[1]),(b[0],b[1])),role=f'pipe-{system}',meta=(('diameter',dia),)))
        # Manifolds (πίνακες υδροληψίας): box, collector bar and one valve per outlet.
        for m in network.get('manifolds',()):
            if abs(m['z']-level)>1e-6:
                continue
            n=len(m['outlets']);w=.10+.05*n;x=m['x'];y=m['y']+(.10 if m['system']=='hot' else -.10)
            f.primitives.append(Primitive2D('polyline',((x-w/2,y-.06),(x+w/2,y-.06),(x+w/2,y+.06),(x-w/2,y+.06),(x-w/2,y-.06)),role='manifold',meta=(('system',m['system']),)))
            f.primitives.append(Primitive2D('polyline',((x-w/2+.02,y),(x+w/2-.02,y)),role=f"pipe-{m['system']}",meta=(('diameter',m['feed_mm']),)))
            for k in range(n):
                px=x-w/2+.05*(k+1)+.025
                f.primitives.append(Primitive2D('polyline',((px,y-.05),(px,y+.05)),role='manifold',meta=(('system',m['system']),)))
            f.primitives.append(Primitive2D('label',((x+w/2+.05,y),),role='plumbing-label',
                                            meta=(('text',f"Π.Υ. {'κρύο' if m['system']=='cold' else 'ζεστό'} {n} εξ."),)))
        for eid in doc.entities:
            e=doc.get(eid)
            if e.kind=='plumbing_point' and _entity_on_active_level(doc,e):
                f.primitives.append(Primitive2D('label',((float(e.params['x'])+.15,float(e.params['y'])+.15),),entity_id=eid,role='plumbing-label',
                                                meta=(('text',POINT_TYPES[e.params['point_type']][0]),)))
    # Derived cable runs of the active storey, labelled with their circuit.
    if any(e.kind=='electrical_point' for e in doc.entities.values()):
        from archforge.mep.electrical import POINT_TYPES as ELEC,_floor_of as elec_floor,route_cables_cached
        level=float(doc.work_plane.origin[2])
        wiring=route_cables_cached(doc)
        for a,b,group,cid in wiring['runs']:
            rel=a[2]-level
            if abs(a[2]-b[2])<1e-9 and elec_floor(doc,a[2])==level:
                run='floor' if rel<1.0 else ('wall' if rel<2.45 else 'ceiling')
                f.primitives.append(Primitive2D('polyline',((a[0],a[1]),(b[0],b[1])),role='cable',meta=(('group',group),('circuit',cid),('run',run))))
        for x,y,z,kind,cid in wiring['boxes']:
            if elec_floor(doc,z)==level:
                r=.07
                pts=((x,y-r),(x+r,y),(x,y+r),(x-r,y),(x,y-r)) if kind=='floor' else ((x-r,y-r),(x+r,y-r),(x+r,y+r),(x-r,y+r),(x-r,y-r))
                f.primitives.append(Primitive2D('polyline',pts,role='elec-box',meta=(('box',kind),('circuit',cid))))
                if kind=='pull':
                    f.primitives.append(Primitive2D('polyline',((x-r,y-r),(x+r,y+r)),role='elec-box',meta=(('box',kind),)))
                    f.primitives.append(Primitive2D('polyline',((x-r,y+r),(x+r,y-r)),role='elec-box',meta=(('box',kind),)))
        names={pid:c['id'] for c in wiring['circuits'] for pid in c['points']}
        for eid in doc.entities:
            e=doc.get(eid)
            if e.kind=='electrical_point' and _entity_on_active_level(doc,e):
                text=ELEC[e.params['point_type']][4]+(f" {names[eid]}" if eid in names else '')
                f.primitives.append(Primitive2D('label',((float(e.params['x'])+.12,float(e.params['y'])-.25),),entity_id=eid,role='electrical-label',meta=(('text',text),)))
    # Derived joists of the active storey: one dashed line per joist and the solver's label.
    for eid in doc.entities:
        e=doc.get(eid)
        if e.kind!='ceiling_joists' or not e.visible or not _entity_on_active_level(doc,e):
            continue
        from archforge.structure.joists import positions,size_joists
        rep=size_joists(e.params)
        for a,b in positions(e.params):
            f.primitives.append(Primitive2D('polyline',(a,b),role='joist',meta=(('ok',rep['ok']),)))
        sec=rep['section']
        text=(f"Δοκίδες {sec['b']*100:.0f}/{sec['h']*100:.0f} @{rep['spacing_m']*100:.0f} ×{rep['count']}" if sec else 'Δοκίδες: ανεπαρκής διατομή ⚠')
        xs=[float(q[0]) for q in e.params['points']];ys=[float(q[1]) for q in e.params['points']]
        f.primitives.append(Primitive2D('label',((min(xs)+.2,min(ys)+.2),),entity_id=eid,role='joists-label',meta=(('text',text),)))
    # Structural analysis results of the active storey (only when up to date; never computed here).
    if any(e.kind in ('structural_column','structural_beam') for e in doc.entities.values()):
        from archforge.structure.analysis import fresh_result
        result=fresh_result(doc)
        level=float(doc.work_plane.origin[2])
        specs=[]                                     # (priority, text, candidates, entity id, role)
        for eid,info in (result or {}).get('members',{}).items():
            e=doc.entities.get(eid)
            if e is None:
                continue
            p=e.params
            if e.kind=='structural_column':
                if abs(float(p['z'])-level)>.05:
                    continue
                cands=_corner_candidates(float(p['x']),float(p['y']),float(p['width'])/2,float(p['depth'])/2)
                bars=info.get('bars');extra=f" {bars['n']}Ø{bars['d']}" if bars else '';rank=0
            else:
                if abs(float(doc.levels.get(str(p.get('level')),-1e9))-level)>.05:
                    continue
                # Beam above / left of its axis; the tie beam on the same axis takes the other side.
                cands=_axis_candidates((float(p['x1']),float(p['y1'])),(float(p['x2']),float(p['y2'])),float(p.get('width',.25))/2+.05)
                extra='';rank=1
            text=f"{info['name']} {info.get('section','')}{extra}"+('' if info.get('ok',True) else ' ⚠')
            specs.append((rank,text,cands,eid,'structural-label'))
        # Foundation under the base storey: footings and tie beams (hidden lines), from the same analysis.
        from archforge.structure.analysis import last_result
        fd=(last_result(doc) or {}).get('foundation') or {}
        for ft in fd.get('footings',()):
            if abs(float(ft.get('z',0.0))-level)>.05:
                continue
            x,y,h=float(ft['x']),float(ft['y']),float(ft['B_m'])/2
            f.primitives.append(Primitive2D('polyline',((x-h,y-h),(x+h,y-h),(x+h,y+h),(x-h,y+h),(x-h,y-h)),role='footing',
                                            entity_id=ft.get('column_id') or None,meta=(('name',ft['name']),)))
            # Two lines, at the corner diagonal to the column's label.
            specs.append((2,f"{ft['name']} {ft['B_m']:.2f}×{ft['B_m']:.2f}\nh{ft['h_m']:.2f} {ft['mesh']}",
                          _corner_candidates(x,y,h,h,order=('sw','nw','se','ne')),'','footing-label'))
        for sp in fd.get('strips',()):
            if abs(float(sp.get('z',0.0))-level)>.05:
                continue
            # Strip footing: flange outline (hidden) and the web, mark along it.
            (ax,ay),(bx,by)=sp['a'],sp['b']
            L=math.hypot(bx-ax,by-ay) or 1.0
            ux,uy=(bx-ax)/L,(by-ay)/L
            for half in (float(sp['B_m'])/2,float(sp['bw_m'])/2):
                nx,ny=-uy*half,ux*half
                f.primitives.append(Primitive2D('polyline',((ax+nx,ay+ny),(bx+nx,by+ny),(bx-nx,by-ny),(ax-nx,ay-ny),(ax+nx,ay+ny)),
                                                role='footing',meta=(('name',sp['name']),)))
            specs.append((3,f"{sp['name']} {sp['section']} {sp['bars_top']}+{sp['bars_bottom']} {sp['stirrups']}",_axis_candidates((ax,ay),(bx,by),float(sp['B_m'])/2+.25),'','footing-label'))
        for t in fd.get('ties',()):
            if abs(float(t.get('z',0.0))-level)>.05:
                continue
            (ax,ay),(bx,by)=t['a'],t['b']
            L=math.hypot(bx-ax,by-ay) or 1.0
            nx,ny=-(by-ay)/L*.125,(bx-ax)/L*.125
            for s_ in (1,-1):
                f.primitives.append(Primitive2D('polyline',((ax+nx*s_,ay+ny*s_),(bx+nx*s_,by+ny*s_)),role='tie-beam',meta=(('name',t['name']),)))
            specs.append((3,f"{t['name']} {t['section']} {t['bars']}",_axis_candidates((ax,ay),(bx,by),.175,first_side=-1),'','footing-label'))
        specs.sort(key=lambda q:q[0])
        placed=place_labels(tuple((text,cands) for _r,text,cands,_e,_role in specs))
        for (_r,text,_c,eid,role),(anchor,align,min_scale) in zip(specs,placed):
            f.primitives.append(Primitive2D('label',(anchor,),entity_id=eid,role=role,
                                            meta=(('text',text),('align',align),('min_scale',min_scale))))
    # Derived drainage of the active storey: sloped pipes with Φ and slope, fittings.
    if any(e.kind=='plumbing_point' for e in doc.entities.values()):
        from archforge.mep.drainage import SLOPE,_floor_of as drain_floor,route_drainage_cached
        level=float(doc.work_plane.origin[2])
        drain=route_drainage_cached(doc)
        labelled=set()
        for a,b,dn,kind in drain['pipes']:
            if kind=='stack':
                f.primitives.append(Primitive2D('ellipse',((a[0],a[1]),),dn/2000+.03,dn/2000+.03,0.,'','drain-stack',meta=(('diameter',dn),)))
                continue
            if drain_floor(doc,max(a[2],b[2])+.5)!=level:
                continue
            f.primitives.append(Primitive2D('polyline',((a[0],a[1]),(b[0],b[1])),role='drain',meta=(('diameter',dn),('kind',kind))))
            if kind=='collector' and (dn,round(a[0],1),) not in labelled and abs(a[0]-b[0])+abs(a[1]-b[1])>.15 and len(labelled)<12:
                labelled.add((dn,round(a[0],1)))
                f.primitives.append(Primitive2D('label',(((a[0]+b[0])/2+.05,(a[1]+b[1])/2+.12),),role='drain-label',meta=(('text',f"Φ{dn} {SLOPE*100:.0f}%"),)))
        for n in drain['nodes']:
            if abs(n['z']-level)>.05:
                continue
            r={'manhole':.30,'floor_drain':.08,'stack':.10}[n['kind']]
            x,y=n['x'],n['y']
            f.primitives.append(Primitive2D('polyline',((x-r,y-r),(x+r,y-r),(x+r,y+r),(x-r,y+r),(x-r,y-r)),role='drain-node',meta=(('kind',n['kind']),('auto',n['auto']))))
            f.primitives.append(Primitive2D('label',((x+r+.05,y-r-.12),),role='drain-label',meta=(('text',{'manhole':'Φρεάτιο','floor_drain':'Σιφώνι','stack':f"Στήλη Φ{n.get('dn',100)}"}[n['kind']]+(' (αυτ.)' if n['auto'] else '')),)))
    # Derived extract ducts of the active storey (under the ceiling) and their outlets.
    if any(e.kind=='ventilation_point' for e in doc.entities.values()):
        from archforge.mep.ventilation import POINT_TYPES as VENT,_floor_of as vent_floor,route_ventilation_cached
        level=float(doc.work_plane.origin[2])
        vent=route_ventilation_cached(doc)
        for a,b,dia,pid in vent['ducts']:
            if abs(a[2]-b[2])<1e-9 and vent_floor(doc,a[2])==level:
                f.primitives.append(Primitive2D('polyline',((a[0],a[1]),(b[0],b[1])),role='duct',meta=(('diameter',dia),('point',pid))))
        for t in vent['terminals']:
            src=doc.entities.get(t['point'])
            if src is None or vent_floor(doc,float(src.params['z']))!=level:
                continue
            x,y=t['x'],t['y'];r=t['diameter']/2000.+.03
            if t['kind']=='roof':
                pts=tuple((x+r*cos(k*pi/6),y+r*sin(k*pi/6)) for k in range(13))
            else:
                pts=((x-r,y-r),(x+r,y-r),(x+r,y+r),(x-r,y+r),(x-r,y-r))
            f.primitives.append(Primitive2D('polyline',pts,role='vent-terminal',meta=(('kind',t['kind']),('diameter',t['diameter']))))
        for eid in doc.entities:
            e=doc.get(eid)
            if e.kind=='ventilation_point' and _entity_on_active_level(doc,e):
                info=vent['report']['points'].get(eid,{})
                where={'wall':'τοίχο','roof':'στέγη'}.get(info.get('outlet'),'')
                text=f"{VENT[e.params['point_type']][4]} Ø{info.get('diameter','')} → {where}"
                f.primitives.append(Primitive2D('label',((float(e.params['x'])+.15,float(e.params['y'])+.30),),entity_id=eid,role='ventilation-label',meta=(('text',text),)))
    f.handles=selection_handles(doc)
    if layers:
        # Layers / environment (core/layers.py): hidden out, locked unpickable, dim faint.
        from .layers import apply_to_frame
        apply_to_frame(doc,f)
    if preview:f.primitives.extend(preview_primitives(preview));f.hud=dict(preview.hud);f.snap=preview.snap
    return f
