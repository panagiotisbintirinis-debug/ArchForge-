from __future__ import annotations
from dataclasses import dataclass, field
from math import radians, cos, sin
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


def entity_view_primitives(doc: Document, eid: str, axis: str, override_params: Optional[Dict[str, Any]] = None) -> List[ViewPrimitive]:
    if axis not in ('XY','XZ','YZ'):
        raise ValueError('axis must be XY, XZ or YZ')
    e=doc.get(eid)
    if not e.visible:return []
    p=override_params if override_params is not None else e.params
    if e.kind=='wall':
        if axis=='XY':return [ViewPrimitive('line',((p['x1'],p['y1']),(p['x2'],p['y2'])),entity_id=eid,meta=(('thickness',p['thickness']),))]
        vals=(p['x1'],p['x2']) if axis=='XZ' else (p['y1'],p['y2']);lo,hi=_extent(vals);z0=p['z'];z1=z0+p['height']
        if hi-lo < p['thickness']:
            mid=(lo+hi)/2;lo=mid-p['thickness']/2;hi=mid+p['thickness']/2
        return [ViewPrimitive('polygon',((lo,z0),(hi,z0),(hi,z1),(lo,z1)),entity_id=eid)]
    if e.kind=='box':
        if axis=='XY':return [ViewPrimitive('polygon',tuple(_box_xy_corners(p)),entity_id=eid)]
        corners=_box_xy_corners(p);z0=p['z'];z1=z0+p['height'];vals=[q[0] for q in corners] if axis=='XZ' else [q[1] for q in corners];lo,hi=_extent(vals)
        return [ViewPrimitive('polygon',((lo,z0),(hi,z0),(hi,z1),(lo,z1)),entity_id=eid)]
    if e.kind in ('floor','room'):
        pts=[tuple(q) for q in p['points']]
        if axis=='XY':return [ViewPrimitive('polygon',tuple(pts),entity_id=eid,meta=(('semantic',e.kind),))]
        vals=[q[0] for q in pts] if axis=='XZ' else [q[1] for q in pts];lo,hi=_extent(vals);z0=p['z'];z1=z0+(p['thickness'] if e.kind=='floor' else p['height'])
        return [ViewPrimitive('polygon',((lo,z0),(hi,z0),(hi,z1),(lo,z1)),entity_id=eid,meta=(('semantic',e.kind),))]
    if e.kind=='pod':
        if axis=='XY':return [ViewPrimitive('ellipse',((p['cx'],p['cy']),),p['diameter_x']/2,p['diameter_y']/2,eid)]
        center=p['cx'] if axis=='XZ' else p['cy'];radius=p['diameter_x']/2 if axis=='XZ' else p['diameter_y']/2;z0=p['floor_level'];z1=z0+p['height']
        return [ViewPrimitive('upper_ellipse',((center,z0),),radius,p['height'],eid,meta=(('top',z1),))]
    return []


def build_view_frame(doc: Document, axis: str, overrides: Optional[Dict[str, Dict[str, Any]]] = None) -> ViewFrame:
    if axis not in ('XY','XZ','YZ'):raise ValueError('axis must be XY, XZ or YZ')
    f=ViewFrame(axis);overrides=overrides or {}
    for eid in doc.entities:f.primitives.extend(entity_view_primitives(doc,eid,axis,overrides.get(eid)))
    return f


def elevation_top_handle(doc: Document, eid: str, axis: str, override_params: Optional[Dict[str, Any]] = None) -> Optional[Point2]:
    if axis not in ('XZ','YZ'):raise ValueError('elevation handle requires XZ or YZ')
    e=doc.get(eid);p=override_params if override_params is not None else e.params
    if e.kind=='wall':
        a0=p['x1'] if axis=='XZ' else p['y1'];a1=p['x2'] if axis=='XZ' else p['y2'];return ((a0+a1)/2.0,p['z']+p['height'])
    if e.kind=='box':
        corners=_box_xy_corners(p);vals=[q[0] for q in corners] if axis=='XZ' else [q[1] for q in corners];lo,hi=_extent(vals);return ((lo+hi)/2.0,p['z']+p['height'])
    if e.kind=='pod':return (p['cx'] if axis=='XZ' else p['cy'],p['floor_level']+p['height'])
    if e.kind=='room':
        vals=[q[0] for q in p['points']] if axis=='XZ' else [q[1] for q in p['points']];lo,hi=_extent(vals);return ((lo+hi)/2.0,p['z']+p['height'])
    return None
