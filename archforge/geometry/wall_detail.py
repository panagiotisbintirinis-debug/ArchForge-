from __future__ import annotations

from typing import List, Tuple
import math

Vec3=Tuple[float,float,float]
Tri=Tuple[int,int,int]


def detailed_wall_geometry(p, target_step: float=0.5):
    """Return a closed wall prism with subdivided exterior/interior surfaces.

    Subdivision is backend detail only; the semantic wall remains one wall.  This gives
    brush sculpting enough local vertices to deform a region without converting the wall
    into a destructive free mesh.
    """
    x1,y1,z,x2,y2=map(float,(p['x1'],p['y1'],p['z'],p['x2'],p['y2']))
    h,t=float(p['height']),float(p['thickness'])
    dx,dy=x2-x1,y2-y1;L=math.hypot(dx,dy)
    if L<=1e-12: raise ValueError('wall has zero length')
    if h<=0 or t<=0: raise ValueError('wall height and thickness must be > 0')
    step=max(float(target_step),0.05)
    nu=max(1,int(math.ceil(L/step)));nv=max(1,int(math.ceil(h/step)))
    ux,uy=dx/L,dy/L;nx,ny=-uy,ux
    verts:List[Vec3]=[]
    ext=[[None]*(nu+1) for _ in range(nv+1)]
    inn=[[None]*(nu+1) for _ in range(nv+1)]
    for j in range(nv+1):
        zz=z+h*j/nv
        for i in range(nu+1):
            s=L*i/nu;cx,cy=x1+ux*s,y1+uy*s
            ext[j][i]=len(verts);verts.append((cx+nx*t/2,cy+ny*t/2,zz))
            inn[j][i]=len(verts);verts.append((cx-nx*t/2,cy-ny*t/2,zz))
    tris:List[Tri]=[];roles=[]
    def add(a,b,c,d,role,reverse=False):
        if reverse: tris.extend(((a,c,b),(a,d,c)))
        else: tris.extend(((a,b,c),(a,c,d)))
        roles.extend((role,role))
    for j in range(nv):
        for i in range(nu):
            # +centreline normal is exterior, so reverse standard grid winding.
            add(ext[j][i],ext[j][i+1],ext[j+1][i+1],ext[j+1][i],'exterior',True)
            add(inn[j][i],inn[j][i+1],inn[j+1][i+1],inn[j+1][i],'interior',False)
    for i in range(nu):
        add(ext[nv][i],ext[nv][i+1],inn[nv][i+1],inn[nv][i],'top',False)
        add(inn[0][i],inn[0][i+1],ext[0][i+1],ext[0][i],'bottom',False)
    for j in range(nv):
        add(ext[j][0],inn[j][0],inn[j+1][0],ext[j+1][0],'start',False)
        add(inn[j][nu],ext[j][nu],ext[j+1][nu],inn[j+1][nu],'end',False)
    return tuple(verts),tuple(tris),tuple(roles)
