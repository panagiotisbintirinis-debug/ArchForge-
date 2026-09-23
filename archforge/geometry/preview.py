from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple
import math

from .backend import ContractBackend, GeometryBackend, GeometryBody, GeometryEvaluation, GeometryIssue

Vec3=Tuple[float,float,float]; Bounds=Tuple[Vec3,Vec3]

@dataclass(frozen=True)
class PreviewPayload:
    primitive:str
    bounds:Bounds

def _bounds(points:Iterable[Vec3])->Bounds:
    pts=list(points)
    if not pts: raise ValueError('cannot bound empty geometry')
    return (tuple(min(p[i] for p in pts) for i in range(3)),tuple(max(p[i] for p in pts) for i in range(3)))

def _transform_point(matrix,p:Vec3)->Vec3:
    x,y,z=p
    return tuple(matrix[r][0]*x+matrix[r][1]*y+matrix[r][2]*z+matrix[r][3] for r in range(3))

def _box_corners(width,depth,height):
    return [(x,y,z) for x in (0.0,width) for y in (0.0,depth) for z in (0.0,height)]

def _room_slab_payload(doc,node)->Optional[PreviewPayload]:
    from archforge.architecture.rooms import room_slab_geometry
    g=room_slab_geometry(doc,doc.get(node.entity_id))
    if g is None:return None
    pts=[(float(x),float(y),float(g['z'])) for x,y in g['points']];top=float(g['z'])+float(g['thickness'])
    return PreviewPayload('polygon_prism',_bounds(pts+[(x,y,top) for x,y,_ in pts]))

def _organic_junction_payload(doc,node)->Optional[PreviewPayload]:
    from archforge.organic.biospectre import junction_section_polygon
    p=node.params
    if p.get('status')!='active':return None
    a_id,b_id=p.get('component_a'),p.get('component_b')
    if a_id not in doc.entities or b_id not in doc.entities:return None
    a,b=doc.get(a_id),doc.get(b_id)
    if a.kind!='pod' or b.kind!='pod':return None
    points=junction_section_polygon(a.params,b.params)
    if points is None:return None
    return PreviewPayload('organic_junction',_bounds(points))

def _organic_opening_patch_payload(doc,node)->Optional[PreviewPayload]:
    from archforge.architecture.openings import pod_opening_patch_geometry,pod_opening_junction_conflict
    if node.params.get('status')!='active':return None
    opening_id=node.params.get('opening_id')
    if pod_opening_junction_conflict(doc,opening_id) is not None:return None
    g=pod_opening_patch_geometry(doc,opening_id)
    if g is None:return None
    return PreviewPayload('organic_opening_patch',_bounds(g['points']))

def _arboreal_branch_payload(doc,node)->PreviewPayload:
    from archforge.organic.arboreal import arboreal_branch_geometry
    g=arboreal_branch_geometry(doc,node.entity_id)
    a=tuple(float(v) for v in g['start']);b=tuple(float(v) for v in g['end'])
    radius=max(float(g['root_radius']),float(g['tip_radius']))
    lo=tuple(min(a[i],b[i])-radius for i in range(3));hi=tuple(max(a[i],b[i])+radius for i in range(3))
    return PreviewPayload('arboreal_branch',(lo,hi))

def _payload(doc,node)->Optional[PreviewPayload]:
    p=node.params;kind=node.semantic_kind
    if kind in ('box','mechanical_part'):
        corners=_box_corners(float(p['width']),float(p['depth']),float(p['height']))
        if node.transform is not None: corners=[_transform_point(node.transform,q) for q in corners]
        else:
            angle=math.radians(float(p.get('rotation',0.0)));c,s=math.cos(angle),math.sin(angle);ox,oy,oz=float(p['x']),float(p['y']),float(p['z'])
            corners=[(ox+c*x-s*y,oy+s*x+c*y,oz+z) for x,y,z in corners]
        return PreviewPayload('box',_bounds(corners))
    if kind=='wall':
        x1,y1,z,x2,y2=map(float,(p['x1'],p['y1'],p['z'],p['x2'],p['y2']));h,t=float(p['height']),float(p['thickness']);dx,dy=x2-x1,y2-y1;length=math.hypot(dx,dy)
        if length<=1e-12:raise ValueError('wall has zero length')
        nx,ny=-dy/length*t/2.0,dx/length*t/2.0
        footprint=[(x1+nx,y1+ny,z),(x1-nx,y1-ny,z),(x2+nx,y2+ny,z),(x2-nx,y2-ny,z)]
        return PreviewPayload('wall_prism',_bounds(footprint+[(x,y,z+h) for x,y,_ in footprint]))
    if kind=='pod':
        cx,cy,z=float(p['cx']),float(p['cy']),float(p['floor_level']);rx=float(p['diameter_x'])/2;ry=float(p['diameter_y'])/2
        angle=math.radians(float(p.get('rotation',0.0)));c,s=math.cos(angle),math.sin(angle)
        ex=math.sqrt((rx*c)**2+(ry*s)**2);ey=math.sqrt((rx*s)**2+(ry*c)**2)
        return PreviewPayload('upper_ellipsoid',((cx-ex,cy-ey,z),(cx+ex,cy+ey,z+float(p['height']))))
    if kind=='mesh':
        m=[float(v) for v in p['matrix']]
        pts=[]
        for x,y,z in p['vertices']:
            pts.append((
                m[0]*x+m[1]*y+m[2]*z+m[3],
                m[4]*x+m[5]*y+m[6]*z+m[7],
                m[8]*x+m[9]*y+m[10]*z+m[11],
            ))
        return PreviewPayload('mesh',_bounds(pts))
    if kind=='conduit':
        radius=float(p['diameter'])/2.0
        pts=[tuple(map(float,point)) for point in p['path_vertices']]
        lo=tuple(min(point[i] for point in pts)-radius for i in range(3))
        hi=tuple(max(point[i] for point in pts)+radius for i in range(3))
        return PreviewPayload('conduit',(lo,hi))
    if kind=='arboreal_branch':return _arboreal_branch_payload(doc,node)
    if kind=='organic_junction':return _organic_junction_payload(doc,node)
    if kind=='organic_opening_patch':return _organic_opening_patch_payload(doc,node)
    if kind in ('floor','room'):
        pts=[(float(x),float(y),float(p['z'])) for x,y in p['points']];top=float(p['z'])+float(p.get('thickness',p.get('height',0.0)))
        return PreviewPayload('polygon_prism' if kind=='floor' else 'room_volume',_bounds(pts+[(x,y,top) for x,y,_ in pts]))
    if kind in ('room_floor','room_ceiling','room_foundation','room_roof'):
        return _room_slab_payload(doc,node)
    raise ValueError(f'preview backend does not support {kind}')

class PreviewBackend(GeometryBackend):
    """Fast viewport geometry; explicitly not evidence of printability."""
    name='preview'
    def evaluate_plan(self,doc,plan)->GeometryEvaluation:
        contract=ContractBackend().evaluate_plan(doc,plan);issues=list(contract.issues);bodies:List[GeometryBody]=[]
        for node in plan.geometry_nodes():
            base=contract.body(node.entity_id)
            try:
                payload=_payload(doc,node)
                if payload is None:
                    if node.semantic_kind in ('room_floor','room_ceiling','room_foundation','room_roof'):
                        message='derived room element has no currently closed room'
                    elif node.semantic_kind=='organic_junction':
                        message='organic junction is dormant or has no current section'
                    elif node.semantic_kind=='organic_opening_patch':
                        from archforge.architecture.openings import pod_opening_junction_conflict
                        junction_id=pod_opening_junction_conflict(doc,node.params.get('opening_id'))
                        message=(f'organic opening patch conflicts with active junction {junction_id}' if junction_id else 'organic opening patch is dormant or has no valid host opening')
                    else:
                        message='derived geometry is currently unavailable'
                    issues.append(GeometryIssue('warning','preview_geometry_unavailable',message,node.entity_id))
                    continue
                bodies.append(GeometryBody(node.entity_id,node.semantic_kind,base.surface_keys,base.modifier_ids,payload,quality='preview',modifiers_applied=False))
            except Exception as exc:issues.append(GeometryIssue('error','preview_geometry_failed',str(exc),node.entity_id))
        return GeometryEvaluation(self.name,tuple(bodies),tuple(issues))
