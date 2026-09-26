from __future__ import annotations

from typing import List, Tuple
import math

Vec3=Tuple[float,float,float]
Tri=Tuple[int,int,int]


def wall_top_heights(p):
    """Return semantic start/end wall heights, preserving legacy uniform-height walls."""
    legacy=float(p['height'])
    start=float(p.get('start_height',legacy));end=float(p.get('end_height',legacy))
    if not math.isfinite(start) or not math.isfinite(end) or start<=0 or end<=0:
        raise ValueError('wall endpoint heights must be finite and > 0')
    return start,end


def wall_height_at(p,u,length=None):
    """Linearly interpolate available wall height in the host-local longitudinal frame."""
    start,end=wall_top_heights(p)
    if length is None:
        length=math.hypot(float(p['x2'])-float(p['x1']),float(p['y2'])-float(p['y1']))
    if length<=1e-12:raise ValueError('wall has zero length')
    t=max(0.0,min(1.0,float(u)/float(length)))
    return start+(end-start)*t


def opening_fits_wall_profile(p, opening, length=None):
    """Validate an opening in the wall-local frame against the semantic top profile.

    Because the top profile is linear, checking the two opening jamb positions is
    sufficient: the lower available height across the opening occurs at one of them.
    """
    if length is None:
        length=math.hypot(float(p['x2'])-float(p['x1']),float(p['y2'])-float(p['y1']))
    width=float(opening.get('width',0.0));height=float(opening.get('height',0.0))
    center=float(opening.get('offset',0.0));sill=float(opening.get('sill',0.0))
    if width<=0 or height<=0 or sill<0:return False
    u0=center-width/2.0;u1=center+width/2.0
    if u0<0 or u1>length:return False
    head=sill+height
    return head<=min(wall_height_at(p,u0,length),wall_height_at(p,u1,length))+1e-9


def _plain_wall_geometry(p,target_step:float):
    x1,y1,z,x2,y2=map(float,(p['x1'],p['y1'],p['z'],p['x2'],p['y2']))
    h0,h1=wall_top_heights(p);t=float(p['thickness'])
    dx,dy=x2-x1,y2-y1;L=math.hypot(dx,dy)
    if L<=1e-12: raise ValueError('wall has zero length')
    if t<=0: raise ValueError('wall thickness must be > 0')
    step=max(float(target_step),0.05)
    nu=max(1,int(math.ceil(L/step)));nv=max(1,int(math.ceil(max(h0,h1)/step)))
    ux,uy=dx/L,dy/L;nx,ny=-uy,ux
    verts:List[Vec3]=[]
    ext=[[None]*(nu+1) for _ in range(nv+1)]
    inn=[[None]*(nu+1) for _ in range(nv+1)]
    for j in range(nv+1):
        f=j/nv
        for i in range(nu+1):
            s=L*i/nu;cx,cy=x1+ux*s,y1+uy*s
            local_h=h0+(h1-h0)*(s/L);zz=z+local_h*f
            ext[j][i]=len(verts);verts.append((cx+nx*t/2,cy+ny*t/2,zz))
            inn[j][i]=len(verts);verts.append((cx-nx*t/2,cy-ny*t/2,zz))
    tris:List[Tri]=[];roles=[]
    def add(a,b,c,d,role,reverse=False):
        if reverse: tris.extend(((a,c,b),(a,d,c)))
        else: tris.extend(((a,b,c),(a,c,d)))
        roles.extend((role,role))
    for j in range(nv):
        for i in range(nu):
            add(ext[j][i],ext[j][i+1],ext[j+1][i+1],ext[j+1][i],'exterior',True)
            add(inn[j][i],inn[j][i+1],inn[j+1][i+1],inn[j+1][i],'interior',False)
    for i in range(nu):
        add(ext[nv][i],ext[nv][i+1],inn[nv][i+1],inn[nv][i],'top',True)
        add(inn[0][i],inn[0][i+1],ext[0][i+1],ext[0][i],'bottom',True)
    for j in range(nv):
        add(ext[j][0],inn[j][0],inn[j+1][0],ext[j+1][0],'start',False)
        add(inn[j][nu],ext[j][nu],ext[j+1][nu],inn[j+1][nu],'end',False)
    return tuple(verts),tuple(tris),tuple(roles)


def _normalized_openings(p,length,height):
    out=[]
    for raw in p.get('_opening_intents',()) or ():
        if raw.get('kind') not in ('door','window'):
            continue
        width=float(raw.get('width',0.0));opening_height=float(raw.get('height',0.0))
        center=float(raw.get('offset',0.0));sill=float(raw.get('sill',0.0))
        if width<=0 or opening_height<=0:
            continue
        u0=max(0.0,center-width/2.0);u1=min(length,center+width/2.0)
        z0=max(0.0,sill);z1=min(height,sill+opening_height)
        if u1-u0<=1e-9 or z1-z0<=1e-9:
            continue
        if not opening_fits_wall_profile(p,raw,length):
            raise ValueError('opening exceeds available local wall height')
        out.append((u0,u1,z0,z1))
    return tuple(out)


def _wall_with_openings(p,target_step:float):
    x1,y1,zbase,x2,y2=map(float,(p['x1'],p['y1'],p['z'],p['x2'],p['y2']))
    height,thickness=float(p['height']),float(p['thickness'])
    dx,dy=x2-x1,y2-y1;length=math.hypot(dx,dy)
    if length<=1e-12:raise ValueError('wall has zero length')
    if height<=0 or thickness<=0:raise ValueError('wall height and thickness must be > 0')
    openings=_normalized_openings(p,length,height)
    if not openings:return _plain_wall_geometry(p,target_step)

    ux,uy=dx/length,dy/length;nx,ny=-uy,ux
    step=max(float(target_step),0.05)
    nu=max(1,int(math.ceil(length/step)));nv=max(1,int(math.ceil(height/step)))
    ubreaks={length*i/nu for i in range(nu+1)}
    zbreaks={height*j/nv for j in range(nv+1)}
    for u0,u1,z0,z1 in openings:
        ubreaks.update((u0,u1));zbreaks.update((z0,z1))
    us=sorted(ubreaks);zs=sorted(zbreaks)

    def is_void(u,z):
        return any(u0<u<u1 and z0<z<z1 for u0,u1,z0,z1 in openings)

    solid=[]
    for i in range(len(us)-1):
        column=[]
        uc=(us[i]+us[i+1])/2.0
        for j in range(len(zs)-1):
            zc=(zs[j]+zs[j+1])/2.0
            column.append(not is_void(uc,zc))
        solid.append(column)

    verts:List[Vec3]=[];indices={};tris:List[Tri]=[];roles=[]
    def vid(u,side,zlocal):
        key=(round(float(u),12),int(side),round(float(zlocal),12))
        if key in indices:return indices[key]
        cx=x1+ux*u;cy=y1+uy*u;off=side*thickness/2.0
        idx=len(verts);verts.append((cx+nx*off,cy+ny*off,zbase+zlocal));indices[key]=idx
        return idx
    def quad(a,b,c,d,role):
        tris.extend(((a,b,c),(a,c,d)));roles.extend((role,role))

    ni=len(us)-1;nj=len(zs)-1
    for i in range(ni):
        u0,u1=us[i],us[i+1]
        for j in range(nj):
            if not solid[i][j]:continue
            z0,z1=zs[j],zs[j+1]
            quad(vid(u0,1,z0),vid(u0,1,z1),vid(u1,1,z1),vid(u1,1,z0),'exterior')
            quad(vid(u0,-1,z0),vid(u1,-1,z0),vid(u1,-1,z1),vid(u0,-1,z1),'interior')
            left_solid=i>0 and solid[i-1][j]
            right_solid=i+1<ni and solid[i+1][j]
            below_solid=j>0 and solid[i][j-1]
            above_solid=j+1<nj and solid[i][j+1]
            if not left_solid:
                role='start' if i==0 else 'opening_reveal';quad(vid(u0,-1,z0),vid(u0,-1,z1),vid(u0,1,z1),vid(u0,1,z0),role)
            if not right_solid:
                role='end' if i==ni-1 else 'opening_reveal';quad(vid(u1,-1,z0),vid(u1,1,z0),vid(u1,1,z1),vid(u1,-1,z1),role)
            if not below_solid:
                role='bottom' if j==0 else 'opening_reveal';quad(vid(u0,-1,z0),vid(u0,1,z0),vid(u1,1,z0),vid(u1,-1,z0),role)
            if not above_solid:
                role='top' if j==nj-1 else 'opening_reveal';quad(vid(u0,-1,z1),vid(u1,-1,z1),vid(u1,1,z1),vid(u0,1,z1),role)
    return tuple(verts),tuple(tris),tuple(roles)


def detailed_wall_geometry(p,target_step:float=0.5):
    """Return a closed semantic wall mesh, including endpoint-specific sloped tops.

    Legacy walls use ``height`` at both ends. ``start_height`` and ``end_height`` are
    optional semantic profile values; they linearly define the top in the wall-local
    longitudinal frame without converting the wall to an arbitrary mesh.
    """
    if p.get('_opening_intents'):
        return _wall_with_openings(p,target_step)
    return _plain_wall_geometry(p,target_step)
