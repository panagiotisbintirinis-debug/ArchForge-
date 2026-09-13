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
