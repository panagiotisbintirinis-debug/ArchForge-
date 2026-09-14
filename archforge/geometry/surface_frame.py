from __future__ import annotations

import copy
import math


def _wall_frame(p):
    x1,y1,z,x2,y2=map(float,(p['x1'],p['y1'],p['z'],p['x2'],p['y2']))
    dx,dy=x2-x1,y2-y1;length=math.hypot(dx,dy)
    if length<=1e-12:raise ValueError('wall has zero length')
    ux,uy=dx/length,dy/length;nx,ny=-uy,ux
    return x1,y1,z,length,float(p['height']),float(p['thickness']),ux,uy,nx,ny


def _pod_frame(p):
    cx=float(p['cx']);cy=float(p['cy']);z=float(p['floor_level'])
    rx=float(p['diameter_x'])/2.0;ry=float(p['diameter_y'])/2.0;rz=float(p['height'])
    if min(rx,ry,rz)<=1e-12:raise ValueError('pod dimensions must be positive')
    a=math.radians(float(p.get('rotation',0.0)));c,s=math.cos(a),math.sin(a)
    return cx,cy,z,rx,ry,rz,c,s


def project_surface_point(doc, owner_id, role, world_point):
    """Project a world hit to backend-neutral semantic surface coordinates.

    Returns normalized (u,v) where a stable intrinsic frame exists. Unsupported surface
    kinds return None so callers can retain legacy world-space behavior during migration.

    For ``pod_shell``, ``u`` is azimuth around the pod's own rotated ellipse and ``v`` is
    normalized elevation from equator/floor (0) to crown (1). The coordinates therefore
    survive pod translation, rotation and parametric reshaping without depending on mesh
    triangle identity.
    """
    e=doc.get(owner_id);p=e.params;x,y,zp=map(float,world_point)
    if e.kind=='wall':
        x1,y1,z,L,h,t,ux,uy,nx,ny=_wall_frame(p)
        sx=(x-x1)*ux+(y-y1)*uy;sn=(x-x1)*nx+(y-y1)*ny
        if role in ('exterior','interior'):
            return (sx/L,(zp-z)/h)
        if role in ('top','bottom'):
            return (sx/L,sn/t+0.5)
        if role in ('start','end'):
            return (sn/t+0.5,(zp-z)/h)
    if e.kind in ('box','mechanical_part'):
        # Rest-pose inverse transform. Posed mechanical parts are reconstructed through
        # the evaluation node transform when resolving the modifier.
        a=math.radians(float(p.get('rotation',0.0)));c,s=math.cos(a),math.sin(a)
        dx=x-float(p['x']);dy=y-float(p['y']);lx=c*dx+s*dy;ly=-s*dx+c*dy;lz=zp-float(p['z'])
        w,d,h=map(float,(p['width'],p['depth'],p['height']))
        if role in ('top','bottom'):return (lx/w,ly/d)
        if role in ('front','back'):return (lx/w,lz/h)
        if role in ('left','right'):return (ly/d,lz/h)
    if e.kind=='pod' and role=='pod_shell':
        cx,cy,z,rx,ry,rz,c,s=_pod_frame(p)
        dx=x-cx;dy=y-cy
        # Inverse Z rotation into the pod's semantic local ellipse frame.
        lx=c*dx+s*dy;ly=-s*dx+c*dy
        nx=lx/rx;ny=ly/ry
        if abs(nx)<=1e-12 and abs(ny)<=1e-12:
            u=0.0  # azimuth is geometrically degenerate at the crown
        else:
            u=(math.atan2(ny,nx)/(2.0*math.pi))%1.0
        sin_phi=max(0.0,min(1.0,(zp-z)/rz))
        v=math.asin(sin_phi)/(0.5*math.pi)
        return (u,v)
    return None


def _transform_point(matrix,p):
    x,y,z=p
    return tuple(matrix[r][0]*x+matrix[r][1]*y+matrix[r][2]*z+matrix[r][3] for r in range(3))


def evaluate_surface_point(doc, owner_id, role, uv, transform=None):
    """Reconstruct a live world point from semantic surface coordinates."""
    u,v=map(float,uv);e=doc.get(owner_id);p=e.params
    if e.kind=='wall':
        x1,y1,z,L,h,t,ux,uy,nx,ny=_wall_frame(p)
        if role=='exterior':return (x1+ux*(u*L)+nx*t/2,y1+uy*(u*L)+ny*t/2,z+v*h)
        if role=='interior':return (x1+ux*(u*L)-nx*t/2,y1+uy*(u*L)-ny*t/2,z+v*h)
        if role in ('top','bottom'):
            sn=(v-.5)*t;zz=z+h if role=='top' else z
            return (x1+ux*(u*L)+nx*sn,y1+uy*(u*L)+ny*sn,zz)
        if role in ('start','end'):
            sn=(u-.5)*t;s=0.0 if role=='start' else L
            return (x1+ux*s+nx*sn,y1+uy*s+ny*sn,z+v*h)
    if e.kind in ('box','mechanical_part'):
        w,d,h=map(float,(p['width'],p['depth'],p['height']))
        if role=='top':local=(u*w,v*d,h)
        elif role=='bottom':local=(u*w,v*d,0.0)
        elif role=='front':local=(u*w,0.0,v*h)
        elif role=='back':local=(u*w,d,v*h)
        elif role=='left':local=(0.0,u*d,v*h)
        elif role=='right':local=(w,u*d,v*h)
        else:return None
        if transform is not None:return _transform_point(transform,local)
        a=math.radians(float(p.get('rotation',0.0)));c,s=math.cos(a),math.sin(a)
        ox,oy,oz=map(float,(p['x'],p['y'],p['z']));x,y,z=local
        return (ox+c*x-s*y,oy+s*x+c*y,oz+z)
    if e.kind=='pod' and role=='pod_shell':
        cx,cy,z,rx,ry,rz,c,s=_pod_frame(p)
        theta=2.0*math.pi*(u%1.0);phi=0.5*math.pi*max(0.0,min(1.0,v))
        rr=math.cos(phi)
        lx=rx*rr*math.cos(theta);ly=ry*rr*math.sin(theta)
        point=(cx+c*lx-s*ly,cy+s*lx+c*ly,z+rz*math.sin(phi))
        return _transform_point(transform,point) if transform is not None else point
    return None


def resolve_modifier_for_node(doc,node,raw):
    """Resolve persistent semantic coordinates into the current evaluated world frame."""
    data=copy.deepcopy(raw);target=data.get('target') or {};region=target.get('subregion') or {}
    uv=region.get('uv_center')
    if uv is not None:
        point=evaluate_surface_point(doc,node.entity_id,str(target.get('surface_role','')),uv,transform=node.transform)
        if point is not None:
            region['world_center']=list(point);target['subregion']=region;data['target']=target
    return data
