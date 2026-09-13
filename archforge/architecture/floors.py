from __future__ import annotations
from math import fabs
from typing import Iterable, Tuple, List

Point2 = Tuple[float, float]

def validate_polygon(points: Iterable[Iterable[float]]) -> List[Point2]:
    pts=[(float(p[0]),float(p[1])) for p in points]
    if len(pts) < 3:
        raise ValueError('polygon requires at least 3 points')
    if abs(signed_area(pts)) <= 1e-9:
        raise ValueError('polygon area must be non-zero')
    return pts

def signed_area(points: Iterable[Point2]) -> float:
    pts=list(points); s=0.0
    for i,(x1,y1) in enumerate(pts):
        x2,y2=pts[(i+1)%len(pts)]; s += x1*y2-x2*y1
    return s/2.0

def area(points: Iterable[Point2]) -> float:
    return fabs(signed_area(points))

def perimeter(points: Iterable[Point2]) -> float:
    from math import hypot
    pts=list(points); total=0.0
    for i,(x1,y1) in enumerate(pts):
        x2,y2=pts[(i+1)%len(pts)]; total += hypot(x2-x1,y2-y1)
    return total

def centroid(points: Iterable[Point2]) -> Point2:
    pts=list(points); a=signed_area(pts)
    if abs(a)<=1e-12: raise ValueError('degenerate polygon')
    cx=cy=0.0
    for i,(x1,y1) in enumerate(pts):
        x2,y2=pts[(i+1)%len(pts)]; cross=x1*y2-x2*y1
        cx += (x1+x2)*cross; cy += (y1+y2)*cross
    return cx/(6*a),cy/(6*a)
