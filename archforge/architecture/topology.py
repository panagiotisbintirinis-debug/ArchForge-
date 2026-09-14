from __future__ import annotations

from dataclasses import dataclass
from math import atan2, hypot
from typing import Dict, List, Optional, Sequence, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class WallEdge:
    wall_id: str
    a: int
    b: int


@dataclass
class WallGraph:
    nodes: List[Point]
    edges: List[WallEdge]


def _dist(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _signed_area(poly: Sequence[Point]) -> float:
    return 0.5 * sum(
        poly[i][0] * poly[(i + 1) % len(poly)][1]
        - poly[(i + 1) % len(poly)][0] * poly[i][1]
        for i in range(len(poly))
    )


def polygon_area(poly: Sequence[Point]) -> float:
    return abs(_signed_area(poly))


def _segment_intersection(a: Point, b: Point, c: Point, d: Point, tolerance: float):
    """Return (point, t, u) for a non-collinear segment intersection, else None."""
    rx=b[0]-a[0]; ry=b[1]-a[1]
    sx=d[0]-c[0]; sy=d[1]-c[1]
    den=rx*sy-ry*sx
    scale=max(1.0,hypot(rx,ry),hypot(sx,sy))
    if abs(den) <= tolerance*scale:
        return None
    qx=c[0]-a[0]; qy=c[1]-a[1]
    t=(qx*sy-qy*sx)/den
    u=(qx*ry-qy*rx)/den
    eps=tolerance/scale
    if t < -eps or t > 1.0+eps or u < -eps or u > 1.0+eps:
        return None
    t=max(0.0,min(1.0,t));u=max(0.0,min(1.0,u))
    return ((a[0]+t*rx,a[1]+t*ry),t,u)


def build_wall_graph(doc, tolerance: float = 1e-6, z: Optional[float] = None) -> WallGraph:
    """Build a planar connectivity graph from visible semantic walls.

    Endpoints within ``tolerance`` are merged. Non-collinear wall crossings and
    T-junctions are split into graph nodes without destructively splitting the source
    wall entities. Intersections only connect walls on the same base elevation.
    """
    if tolerance <= 0:
        raise ValueError('tolerance must be > 0')

    segments=[]
    for eid,e in doc.entities.items():
        if e.kind!='wall' or not e.visible:
            continue
        p=e.params; wz=float(p['z'])
        if z is not None and abs(wz-float(z))>tolerance:
            continue
        a=(float(p['x1']),float(p['y1']));b=(float(p['x2']),float(p['y2']))
        if _dist(a,b)<=tolerance:
            continue
        segments.append({'id':eid,'a':a,'b':b,'z':wz,'cuts':[0.0,1.0]})

    # Split topological edges wherever same-level wall centerlines intersect.
    for i in range(len(segments)):
        for j in range(i+1,len(segments)):
            si,sj=segments[i],segments[j]
            if abs(si['z']-sj['z'])>tolerance:
                continue
            hit=_segment_intersection(si['a'],si['b'],sj['a'],sj['b'],tolerance)
            if hit is None:
                continue
            _,ti,tj=hit
            si['cuts'].append(ti);sj['cuts'].append(tj)

    nodes: List[Point]=[]
    edges: List[WallEdge]=[]

    def node_for(p: Point) -> int:
        for i,q in enumerate(nodes):
            if _dist(p,q)<=tolerance:
                return i
        nodes.append((float(p[0]),float(p[1])))
        return len(nodes)-1

    for s in segments:
        a,b=s['a'],s['b'];dx=b[0]-a[0];dy=b[1]-a[1]
        cuts=sorted(s['cuts'])
        unique=[]
        for t in cuts:
            if not unique or abs(t-unique[-1])>1e-12:
                unique.append(t)
        for t0,t1 in zip(unique,unique[1:]):
            p0=(a[0]+t0*dx,a[1]+t0*dy);p1=(a[0]+t1*dx,a[1]+t1*dy)
            if _dist(p0,p1)<=tolerance:
                continue
            i0=node_for(p0);i1=node_for(p1)
            if i0!=i1:
                edges.append(WallEdge(s['id'],i0,i1))
    return WallGraph(nodes,edges)


def connected_components(graph: WallGraph) -> List[List[int]]:
    adj: Dict[int, List[int]]={i:[] for i in range(len(graph.nodes))}
    for e in graph.edges:
        adj[e.a].append(e.b);adj[e.b].append(e.a)
    out=[];seen=set()
    for start in range(len(graph.nodes)):
        if start in seen:continue
        stack=[start];comp=[]
        while stack:
            n=stack.pop()
            if n in seen:continue
            seen.add(n);comp.append(n);stack.extend(adj[n])
        out.append(comp)
    return out


def _halfedge_faces(graph: WallGraph) -> List[List[int]]:
    """Traverse planar straight-line graph faces using angularly ordered half-edges."""
    adjacency: Dict[int,List[int]]={i:[] for i in range(len(graph.nodes))}
    for e in graph.edges:
        if e.b not in adjacency[e.a]:adjacency[e.a].append(e.b)
        if e.a not in adjacency[e.b]:adjacency[e.b].append(e.a)
    for n,nbrs in adjacency.items():
        x,y=graph.nodes[n]
        nbrs.sort(key=lambda m:atan2(graph.nodes[m][1]-y,graph.nodes[m][0]-x))

    visited=set();faces=[];max_steps=max(1,2*len(graph.edges)+5)
    for u,nbrs in adjacency.items():
        for v in nbrs:
            if (u,v) in visited:continue
            start=(u,v);cu,cv=start;face=[]
            for _ in range(max_steps):
                if (cu,cv) in visited:
                    if (cu,cv)==start:break
                    face=[];break
                visited.add((cu,cv));face.append(cu)
                around=adjacency.get(cv,[])
                if not around or cu not in around:
                    face=[];break
                idx=around.index(cu);nw=around[(idx-1)%len(around)];cu,cv=cv,nw
                if (cu,cv)==start:break
            else:face=[]
            if len(face)>=3 and (cu,cv)==start:faces.append(face)
    return faces


def closed_room_polygons(doc, tolerance: float = 1e-6, z: Optional[float] = None, min_area: float = 1e-6) -> List[List[Point]]:
    """Return bounded closed faces formed by connected/intersecting walls.

    The result is derived topology, not persistent room entities. Polygons are returned
    counter-clockwise and recompute immediately when their wall boundaries change.
    """
    graph=build_wall_graph(doc,tolerance=tolerance,z=z);raw=_halfedge_faces(graph)
    rooms=[];seen=set()
    for face in raw:
        poly=[graph.nodes[i] for i in face];area=_signed_area(poly)
        if area<=min_area:continue
        ids=list(face);rotations=[tuple(ids[i:]+ids[:i]) for i in range(len(ids))];key=min(rotations)
        if key in seen:continue
        seen.add(key);rooms.append(poly)
    rooms.sort(key=lambda p:(round(polygon_area(p),12),tuple(p)))
    return rooms


def room_metrics(poly: Sequence[Point]) -> Dict[str, object]:
    if len(poly)<3:raise ValueError('room polygon needs at least 3 points')
    area_signed=_signed_area(poly);area=abs(area_signed)
    if area<=0:raise ValueError('room polygon area must be > 0')
    perimeter=sum(_dist(poly[i],poly[(i+1)%len(poly)]) for i in range(len(poly)))
    c=1.0/(6.0*area_signed)
    cx=c*sum((poly[i][0]+poly[(i+1)%len(poly)][0])*(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1]) for i in range(len(poly)))
    cy=c*sum((poly[i][1]+poly[(i+1)%len(poly)][1])*(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1]) for i in range(len(poly)))
    return {'area':area,'perimeter':perimeter,'centroid':(cx,cy)}
