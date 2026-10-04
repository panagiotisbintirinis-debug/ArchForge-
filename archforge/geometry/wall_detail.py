from __future__ import annotations

from typing import List, Tuple
import math

Vec3=Tuple[float,float,float]
Tri=Tuple[int,int,int]


def _plain_wall_geometry(p,target_step:float):
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
        if raw.get('kind') not in ('door','window','opening'):
            continue
        width=float(raw.get('width',0.0));opening_height=float(raw.get('height',0.0))
        center=float(raw.get('offset',0.0));sill=float(raw.get('sill',0.0))
        if width<=0 or opening_height<=0:
            continue
        u0=max(0.0,center-width/2.0);u1=min(length,center+width/2.0)
        z0=max(0.0,sill);z1=min(height,sill+opening_height)
        if u1-u0<=1e-9 or z1-z0<=1e-9:
            continue
        shape='rectangle'
        arch_rise=0.0
        if raw.get('kind')=='opening':
            shape=str(raw.get('shape','rectangle')).lower()
            if shape=='arch':
                arch_rise=max(1e-6,min(float(raw.get('arch_rise',width/2.0)),z1-z0))
        out.append({
            'u0':u0,'u1':u1,'z0':z0,'z1':z1,
            'shape':shape,'arch_rise':arch_rise,
        })
    return tuple(out)


def _opening_contains(opening,u,z):
    u0,u1=float(opening['u0']),float(opening['u1'])
    z0,z1=float(opening['z0']),float(opening['z1'])
    if not (u0<u<u1 and z0<z<z1):
        return False
    if opening.get('shape')!='arch':
        return True
    rise=float(opening.get('arch_rise',0.0))
    if rise<=1e-9:
        return True
    spring=z1-rise
    if z<=spring:
        return True
    half=(u1-u0)/2.0
    if half<=1e-12:
        return False
    center=(u0+u1)/2.0
    x=(u-center)/half
    if abs(x)>=1.0:
        return False
    cap=spring+rise*math.sqrt(max(0.0,1.0-x*x))
    return z<cap

def _arch_cap(opening,u):
    """Height of the arch intrados above ``u`` (spring at the jambs)."""
    u0,u1=float(opening['u0']),float(opening['u1'])
    rise=float(opening.get('arch_rise',0.0));spring=float(opening['z1'])-rise
    half=(u1-u0)/2.0
    if half<=1e-12:return spring
    x=max(-1.0,min(1.0,(u-(u0+u1)/2.0)/half))
    return spring+rise*math.sqrt(max(0.0,1.0-x*x))


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
    arches=[]
    for opening in openings:
        u0,u1,z0,z1=(opening['u0'],opening['u1'],opening['z0'],opening['z1'])
        ubreaks.update((u0,u1));zbreaks.update((z0,z1))
        if opening.get('shape')=='arch' and float(opening.get('arch_rise',0.0))>1e-9:
            zbreaks.add(z1-float(opening['arch_rise']))
            arches.append(opening)
            # Dense samples across the span; between samples the intrados is
            # a straight sloped segment, so the arch reads as a smooth curve.
            steps=max(16,int(math.ceil((u1-u0)/0.06)))
            steps+=steps%2  # even: the apex is a vertex, not a flat slice
            for k in range(1,steps):
                ubreaks.add(u0+(u1-u0)*k/steps)
    # Never let a grid line fall a hair away from an opening edge (that
    # produced slivers / zero-area triangles).
    us=[]
    for u in sorted(ubreaks):
        if not us or u-us[-1]>1e-7:us.append(u)
    zs=[]
    for z in sorted(zbreaks):
        if not zs or z-zs[-1]>1e-7:zs.append(z)
    ni=len(us)-1;nj=len(zs)-1

    # Column i lies under an arch: everything from the sill up to the
    # intrados is void and the solid above starts on the sloped intrados.
    arch_of=[None]*ni
    for i in range(ni):
        uc=(us[i]+us[i+1])/2.0
        for opening in arches:
            if opening['u0']<uc<opening['u1']:arch_of[i]=opening;break

    def is_void(u,z):
        return any(_opening_contains(opening,u,z) for opening in openings)

    solid=[]
    for i in range(ni):
        uc=(us[i]+us[i+1])/2.0;column=[]
        for j in range(nj):
            zc=(zs[j]+zs[j+1])/2.0
            if arch_of[i] is not None and zc>arch_of[i]['z0']:
                column.append(False)  # handled by the arch column builder
            else:
                column.append(not is_void(uc,zc))
        solid.append(column)

    def edge_covered(i,j,side):
        """Is column i solid along its left/right edge over cell row j?"""
        if i<0 or i>=ni:return False
        opening=arch_of[i]
        zc=(zs[j]+zs[j+1])/2.0
        if opening is not None and zc>opening['z0']:
            u=us[i] if side=='left' else us[i+1]
            return zc>_arch_cap(opening,u)
        return solid[i][j]

    def covered_at(i,side,z):
        """Is column i solid at height z along its left/right edge?"""
        if i<0 or i>=ni:return False
        opening=arch_of[i]
        if opening is not None and z>opening['z0']:
            return z>_arch_cap(opening,us[i] if side=='left' else us[i+1])
        row=next((j for j in range(nj) if zs[j]<=z<zs[j+1]),None)
        return row is not None and solid[i][row]

    verts:List[Vec3]=[];indices={};tris:List[Tri]=[];roles=[]
    def vid(u,side,zlocal):
        key=(round(float(u),9),int(side),round(float(zlocal),9))
        if key in indices:return indices[key]
        cx=x1+ux*u;cy=y1+uy*u;off=side*thickness/2.0
        idx=len(verts);verts.append((cx+nx*off,cy+ny*off,zbase+zlocal));indices[key]=idx
        return idx
    def quad(a,b,c,d,role):
        tris.extend(((a,b,c),(a,c,d)));roles.extend((role,role))

    for i in range(ni):
        u0,u1=us[i],us[i+1]
        for j in range(nj):
            if not solid[i][j]:continue
            z0,z1=zs[j],zs[j+1]
            # Exterior (+normal) and interior (-normal) skins.
            quad(vid(u0,1,z0),vid(u0,1,z1),vid(u1,1,z1),vid(u1,1,z0),'exterior')
            quad(vid(u0,-1,z0),vid(u1,-1,z0),vid(u1,-1,z1),vid(u0,-1,z1),'interior')

            left_solid=edge_covered(i-1,j,'right')
            right_solid=edge_covered(i+1,j,'left')
            below_solid=j>0 and solid[i][j-1]
            above_solid=j+1<nj and solid[i][j+1]

            if not left_solid:
                role='start' if i==0 else 'opening_reveal'
                quad(vid(u0,-1,z0),vid(u0,-1,z1),vid(u0,1,z1),vid(u0,1,z0),role)
            if not right_solid:
                role='end' if i==ni-1 else 'opening_reveal'
                quad(vid(u1,-1,z0),vid(u1,1,z0),vid(u1,1,z1),vid(u1,-1,z1),role)
            if not below_solid:
                role='bottom' if j==0 else 'opening_reveal'
                quad(vid(u0,-1,z0),vid(u0,1,z0),vid(u1,1,z0),vid(u1,-1,z0),role)
            if not above_solid:
                role='top' if j==nj-1 else 'opening_reveal'
                quad(vid(u0,-1,z1),vid(u1,-1,z1),vid(u1,1,z1),vid(u0,1,z1),role)

    # Arch columns: solid from the sloped intrados (capL -> capR) to the top.
    for i in range(ni):
        opening=arch_of[i]
        if opening is None:continue
        u0,u1=us[i],us[i+1]
        capL=_arch_cap(opening,u0);capR=_arch_cap(opening,u1)
        left=[capL]+[z for z in zs if z>capL+1e-7]
        right=[capR]+[z for z in zs if z>capR+1e-7]
        # Zip the two edge chains bottom-up into triangles (both skins).
        a=b=0
        while a<len(left)-1 or b<len(right)-1:
            advance_left=b>=len(right)-1 or (a<len(left)-1 and left[a+1]<=right[b+1])
            if advance_left:
                tri_ext=(vid(u0,1,left[a]),vid(u0,1,left[a+1]),vid(u1,1,right[b]))
                tri_int=(vid(u0,-1,left[a]),vid(u1,-1,right[b]),vid(u0,-1,left[a+1]))
                a+=1
            else:
                tri_ext=(vid(u0,1,left[a]),vid(u1,1,right[b+1]),vid(u1,1,right[b]))
                tri_int=(vid(u0,-1,left[a]),vid(u1,-1,right[b]),vid(u1,-1,right[b+1]))
                b+=1
            tris.extend((tri_ext,tri_int));roles.extend(('exterior','interior'))
        # Intrados (soffit) of this slice.
        quad(vid(u0,-1,capL),vid(u0,1,capL),vid(u1,1,capR),vid(u1,-1,capR),'opening_reveal')
        # Wall top over this slice.
        quad(vid(u0,-1,height),vid(u1,-1,height),vid(u1,1,height),vid(u0,1,height),'top')
        # Side faces where the neighbouring column does not cover this edge.
        for side,u,chain in (('left',u0,left),('right',u1,right)):
            nb=i-1 if side=='left' else i+1
            for k in range(len(chain)-1):
                za,zb=chain[k],chain[k+1]
                if covered_at(nb,'right' if side=='left' else 'left',(za+zb)/2.0):continue
                end_role=('start' if nb<0 else 'end') if nb<0 or nb>=ni else 'opening_reveal'
                if side=='left':
                    quad(vid(u,-1,za),vid(u,-1,zb),vid(u,1,zb),vid(u,1,za),end_role)
                else:
                    quad(vid(u,-1,za),vid(u,1,za),vid(u,1,zb),vid(u,-1,zb),end_role)

    return tuple(verts),tuple(tris),tuple(roles)


def detailed_wall_geometry(p,target_step:float=0.5):
    """Return a closed wall mesh with local sculpt resolution and semantic openings.

    Without openings this preserves the original subdivided wall prism.  When door/window
    intent is present, the host wall becomes the geometry authority: exterior/interior
    skins are removed inside each opening and thickness-spanning `opening_reveal` faces
    close the jambs, sill and header so the result remains a manifold closed shell.
    """
    if p.get('_opening_intents'):
        return _wall_with_openings(p,target_step)
    return _plain_wall_geometry(p,target_step)
