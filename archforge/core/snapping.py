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
    elif e.kind=='pod':
        rx,ry=p['diameter_x']/2,p['diameter_y']/2;z=p['floor_level']
        out=[SnapPoint(p['cx'],p['cy'],z,'center',eid),SnapPoint(p['cx']+rx,p['cy'],z,'quadrant',eid),SnapPoint(p['cx']-rx,p['cy'],z,'quadrant',eid),SnapPoint(p['cx'],p['cy']+ry,z,'quadrant',eid),SnapPoint(p['cx'],p['cy']-ry,z,'quadrant',eid)]
    elif e.kind in ('floor','room'):
        z=p['z'];pts=p['points']
        for i,(x,y) in enumerate(pts):
            out.append(SnapPoint(x,y,z,'vertex',eid));x2,y2=pts[(i+1)%len(pts)];out.append(SnapPoint((x+x2)/2,(y+y2)/2,z,'midpoint',eid))
    return out

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
    # Explicit semantic snap points have highest priority, but only on the active storey.
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
    if grid:
        gx=round(x/grid)*grid;gy=round(y/grid)*grid
        if hypot(gx-x,gy-y)<=tolerance:return SnapPoint(gx,gy,active_z,'grid','')
    return None
