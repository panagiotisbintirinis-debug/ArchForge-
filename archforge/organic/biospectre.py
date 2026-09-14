from __future__ import annotations
import math


def shell_top(p): return p['floor_level']+p['height']


def profile_radius(p,z):
    if z < p['floor_level'] or z > shell_top(p): return None
    # upper half ellipsoid only: floor is the equator/hard boundary
    t=(z-p['floor_level'])/p['height']
    factor=math.sqrt(max(0.0,1.0-t*t))
    return p['diameter_x']/2*factor,p['diameter_y']/2*factor


def _radial_extent(p,nx,ny):
    """Distance from pod center to its rotated XY ellipse along a world-space ray."""
    rx=max(float(p['diameter_x'])/2.0,1e-9);ry=max(float(p['diameter_y'])/2.0,1e-9)
    angle=math.radians(float(p.get('rotation',0.0)));c,s=math.cos(angle),math.sin(angle)
    # Rotate the world direction into the ellipse's intrinsic frame.
    lx=c*nx+s*ny;ly=-s*nx+c*ny
    return 1.0/math.sqrt((lx/rx)**2+(ly/ry)**2)


def overlap(a,b):
    """Return whether the two rotated pod footprints physically overlap in XY.

    The center-to-center line is sufficient for centered convex ellipses: each ellipse
    contains the radial segment from its center to its boundary along that line, so the
    footprints intersect iff the center distance is less than the two radial reaches.
    Vertical shell overlap is checked separately by ``junction_plane``.
    """
    dx=float(b['cx'])-float(a['cx']);dy=float(b['cy'])-float(a['cy']);distance=math.hypot(dx,dy)
    if distance<=1e-12:return True
    nx,ny=dx/distance,dy/distance
    return distance < _radial_extent(a,nx,ny)+_radial_extent(b,-nx,-ny)


def junction_plane(a,b):
    if not overlap(a,b): return None
    z0=max(float(a['floor_level']),float(b['floor_level']))
    z1=min(float(shell_top(a)),float(shell_top(b)))
    if z1<=z0:return None
    # Weighted perpendicular semantic separator. The weights use each pod's actual
    # rotated radial reach along the center line, so rotating an elliptical pod changes
    # its junction location/eligibility without changing the underlying semantic IDs.
    nx=float(b['cx'])-float(a['cx']);ny=float(b['cy'])-float(a['cy']);L=math.hypot(nx,ny)
    if L<=1e-12:return None
    nx/=L;ny/=L
    ra=_radial_extent(a,nx,ny);rb=_radial_extent(b,-nx,-ny)
    t=ra/(ra+rb)
    px=float(a['cx'])+(float(b['cx'])-float(a['cx']))*t
    py=float(a['cy'])+(float(b['cy'])-float(a['cy']))*t
    return {'point':(px,py),'normal':(nx,ny),'z0':z0,'z1':z1}


def junction_key_for_pods(id_a: str, id_b: str) -> str:
    """Generate a canonical order-independent junction key for two pods."""
    return f"{min(id_a, id_b)}-{max(id_a, id_b)}"


def find_pod_junctions(doc, pod_id: str):
    """Find all organic flat junctions formed between a pod and overlapping neighboring pods."""
    if pod_id not in doc.entities:
        return []
    pod = doc.get(pod_id)
    if pod.kind != 'pod':
        return []
    junctions = []
    for other_id, other in doc.entities.items():
        if other_id == pod_id or other.kind != 'pod' or not other.visible:
            continue
        plane = junction_plane(pod.params, other.params)
        if plane is not None:
            junctions.append({
                'junction_key': junction_key_for_pods(pod_id, other_id),
                'pod_id': pod_id,
                'other_pod_id': other_id,
                'plane': plane,
            })
    return junctions


def all_pod_junctions(doc):
    """Find all unique organic pod junctions across the entire document."""
    result = {}
    pod_entities = [e for e in doc.entities.values() if e.kind == 'pod' and e.visible]
    for i in range(len(pod_entities)):
        for j in range(i + 1, len(pod_entities)):
            p1 = pod_entities[i]
            p2 = pod_entities[j]
            plane = junction_plane(p1.params, p2.params)
            if plane is not None:
                key = junction_key_for_pods(p1.id, p2.id)
                result[key] = {
                    'junction_key': key,
                    'pod_a': p1.id,
                    'pod_b': p2.id,
                    'plane': plane,
                }
    return result
