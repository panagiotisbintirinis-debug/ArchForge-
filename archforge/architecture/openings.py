from __future__ import annotations
from math import hypot


def wall_length(wall_params):
    return hypot(wall_params["x2"]-wall_params["x1"], wall_params["y2"]-wall_params["y1"])


def validate_opening(wall_params, opening_params, kind="window"):
    length=wall_length(wall_params)
    width=float(opening_params["width"]); height=float(opening_params["height"]); offset=float(opening_params["offset"]); sill=float(opening_params.get("sill",0.0))
    if width <= 0 or height <= 0: raise ValueError("opening width/height must be positive")
    if offset-width/2 < 0 or offset+width/2 > length: raise ValueError("opening must fit within host wall")
    if sill < 0 or sill+height > wall_params["height"]: raise ValueError("opening must fit within wall height")
    if kind=="door" and abs(sill)>1e-12: raise ValueError("door sill must be zero")
    return True


def plan_segment(wall_params, opening_params):
    length=wall_length(wall_params)
    if length <= 0: raise ValueError("host wall has zero length")
    ux=(wall_params["x2"]-wall_params["x1"])/length; uy=(wall_params["y2"]-wall_params["y1"])/length
    c=float(opening_params["offset"]); h=float(opening_params["width"])/2
    return ((wall_params["x1"]+ux*(c-h),wall_params["y1"]+uy*(c-h)),(wall_params["x1"]+ux*(c+h),wall_params["y1"]+uy*(c+h)))


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
