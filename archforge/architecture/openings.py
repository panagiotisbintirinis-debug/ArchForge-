from __future__ import annotations
from dataclasses import dataclass
from math import atan2, cos, hypot, isfinite, pi, radians, sin, sqrt


def wall_length(wall_params):
    return hypot(wall_params["x2"]-wall_params["x1"], wall_params["y2"]-wall_params["y1"])


def _wall_height_at(wall_params, offset, length):
    """Return available wall height at host-local offset, preserving legacy walls."""
    legacy=float(wall_params["height"])
    start=float(wall_params.get("start_height", legacy)); end=float(wall_params.get("end_height", legacy))
    if not all(isfinite(v) and v > 0 for v in (start, end)):
        raise ValueError("wall endpoint heights must be finite and positive")
    if length <= 1e-12:
        raise ValueError("host wall has zero length")
    t=max(0.0,min(1.0,float(offset)/float(length)))
    return start+(end-start)*t


def validate_opening(wall_params, opening_params, kind="window"):
    length=wall_length(wall_params)
    width=float(opening_params["width"]); height=float(opening_params["height"]); offset=float(opening_params["offset"]); sill=float(opening_params.get("sill",0.0))
    if width <= 0 or height <= 0: raise ValueError("opening width/height must be positive")
    u0=offset-width/2;u1=offset+width/2
    if u0 < 0 or u1 > length: raise ValueError("opening must fit within host wall")
    # A linear semantic wall top reaches its minimum over the opening at one jamb.
    available=min(_wall_height_at(wall_params,u0,length),_wall_height_at(wall_params,u1,length))
    if sill < 0 or sill+height > available+1e-9: raise ValueError("opening must fit within local wall height")
    if kind=="door" and abs(sill)>1e-12: raise ValueError("door sill must be zero")
    return True


def validate_pod_opening(pod_params, opening_params, kind="window"):
    """Validate a conventional planar door/window attached to an organic pod shell."""
    width=float(opening_params["width"]); height=float(opening_params["height"]); sill=float(opening_params.get("sill",0.0))
    u=float(opening_params["surface_u"]); margin=float(opening_params.get("flat_margin",0.25))
    if not all(isfinite(v) for v in (width,height,sill,u,margin)):raise ValueError("pod opening values must be finite")
    if width<=0 or height<=0:raise ValueError("opening width/height must be positive")
    if margin<0:raise ValueError("flat opening margin must be non-negative")
    if sill<0 or sill+height>float(pod_params["height"]):raise ValueError("opening must fit within pod height")
    if kind=="door" and abs(sill)>1e-12:raise ValueError("door sill must be zero")
    # Semantic azimuth is cyclic, but canonical persisted values remain normalized.
    if u < 0.0 or u >= 1.0:raise ValueError("pod opening surface_u must be in [0,1)")
    return True


def plan_segment(wall_params, opening_params):
    length=wall_length(wall_params)
    if length <= 0: raise ValueError("host wall has zero length")
    ux=(wall_params["x2"]-wall_params["x1"])/length; uy=(wall_params["y2"]-wall_params["y1"])/length
    c=float(opening_params["offset"]); h=float(opening_params["width"])/2
    return ((wall_params["x1"]+ux*(c-h),wall_params["y1"]+uy*(c-h)),(wall_params["x1"]+ux*(c+h),wall_params["y1"]+uy*(c+h)))


def _pod_frame(pod_params, u, z_world):
    """Return shell point and outward/tangent axes for a stable intrinsic pod azimuth."""
    cx=float(pod_params['cx']);cy=float(pod_params['cy']);floor=float(pod_params['floor_level'])
    rx=float(pod_params['diameter_x'])/2.0;ry=float(pod_params['diameter_y'])/2.0;rz=float(pod_params['height'])
    theta=2.0*pi*(float(u)%1.0);rot=radians(float(pod_params.get('rotation',0.0)));cr,sr=cos(rot),sin(rot)
    rel=max(0.0,min(1.0,(float(z_world)-floor)/rz));factor=sqrt(max(0.0,1.0-rel*rel))
    lx=rx*factor*cos(theta);ly=ry*factor*sin(theta)
    px=cx+cr*lx-sr*ly;py=cy+sr*lx+cr*ly
    # Ellipse normal uses the implicit-gradient direction, not the center radial vector.
    nlx=cos(theta)/max(rx,1e-12);nly=sin(theta)/max(ry,1e-12);nn=hypot(nlx,nly)
    nlx/=nn;nly/=nn
    nx=cr*nlx-sr*nly;ny=sr*nlx+cr*nly
    tx,ty=-ny,nx
    return (px,py),(nx,ny),(tx,ty)


def pod_opening_plane(pod_params, opening_params):
    kind=str(opening_params.get('_kind','window'))
    validate_pod_opening(pod_params,opening_params,kind)
    floor=float(pod_params['floor_level']);sill=float(opening_params.get('sill',0.0));height=float(opening_params['height'])
    z_ref=floor+sill+height/2.0
    point,normal,tangent=_pod_frame(pod_params,float(opening_params['surface_u']),z_ref)
    return {'point':point,'normal':normal,'tangent':tangent,'z_ref':z_ref}


def pod_opening_plan_segment(pod_params, opening_params):
    plane=pod_opening_plane(pod_params,opening_params);px,py=plane['point'];tx,ty=plane['tangent'];half=float(opening_params['width'])/2.0
    return ((px-tx*half,py-ty*half),(px+tx*half,py+ty*half))


def project_to_pod(pod_params, x, y):
    """Project an XY pointer to the pod footprint and return stable surface_u + distance."""
    cx=float(pod_params['cx']);cy=float(pod_params['cy']);rx=float(pod_params['diameter_x'])/2.0;ry=float(pod_params['diameter_y'])/2.0
    rot=radians(float(pod_params.get('rotation',0.0)));cr,sr=cos(rot),sin(rot);dx=float(x)-cx;dy=float(y)-cy
    lx=cr*dx+sr*dy;ly=-sr*dx+cr*dy
    if abs(lx)<=1e-15 and abs(ly)<=1e-15:theta=0.0
    else:theta=atan2(ly/max(ry,1e-12),lx/max(rx,1e-12))
    u=(theta/(2.0*pi))%1.0
    qx=rx*cos(theta);qy=ry*sin(theta);px=cx+cr*qx-sr*qy;py=cy+sr*qx+cr*qy
    return (u,px,py,hypot(float(x)-px,float(y)-py))


def nearest_opening_host(doc, x, y, tolerance=0.35):
    """Return nearest visible wall or pod that can host a standard opening."""
    best=None
    for eid,e in doc.entities.items():
        if not e.visible or e.kind not in ('wall','pod'):continue
        try:
            if e.kind=='wall':
                off,px,py,dist=project_to_wall(e.params,x,y);raw={'host_id':eid,'host_kind':'wall','offset':off,'x':px,'y':py,'distance':dist}
            else:
                u,px,py,dist=project_to_pod(e.params,x,y);raw={'host_id':eid,'host_kind':'pod','surface_u':u,'x':px,'y':py,'distance':dist}
        except ValueError:continue
        if dist<=tolerance and (best is None or dist<best['distance']):best=raw
    return best


def elevation_rect(wall_params, opening_params, axis="XZ"):
    if axis not in ("XZ","YZ"): raise ValueError("axis must be XZ or YZ")
    a1=wall_params["x1"] if axis=="XZ" else wall_params["y1"]; a2=wall_params["x2"] if axis=="XZ" else wall_params["y2"]
    length=wall_length(wall_params)
    if length <= 0: raise ValueError("host wall has zero length")
    component=(a2-a1)/length; c=float(opening_params["offset"]); h=float(opening_params["width"])/2
    lo=a1+component*(c-h); hi=a1+component*(c+h); lo,hi=min(lo,hi),max(lo,hi)
    z0=wall_params["z"]+float(opening_params.get("sill",0.0)); z1=z0+float(opening_params["height"]); return ((lo,z0),(hi,z0),(hi,z1),(lo,z1))


def project_to_wall(wall_params, x, y):
    """Project an XY point to a wall centerline and return (offset, px, py, distance)."""
    x1=float(wall_params["x1"]); y1=float(wall_params["y1"]); x2=float(wall_params["x2"]); y2=float(wall_params["y2"])
    dx=x2-x1; dy=y2-y1; ll=dx*dx+dy*dy
    if ll <= 1e-18: raise ValueError("host wall has zero length")
    t=((float(x)-x1)*dx+(float(y)-y1)*dy)/ll
    t=max(0.0,min(1.0,t))
    px=x1+t*dx; py=y1+t*dy
    length=ll**0.5
    return (t*length,px,py,hypot(float(x)-px,float(y)-py))


def nearest_wall_projection(doc, x, y, tolerance=0.35):
    """Return nearest visible wall projection within tolerance, or None."""
    best=None
    for eid,e in doc.entities.items():
        if e.kind!='wall' or not e.visible: continue
        try: off,px,py,dist=project_to_wall(e.params,x,y)
        except ValueError: continue
        if dist <= tolerance and (best is None or dist < best["distance"]):
            best={"wall_id":eid,"offset":off,"x":px,"y":py,"distance":dist}
    return best
