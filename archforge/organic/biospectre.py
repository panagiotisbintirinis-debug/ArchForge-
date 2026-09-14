from __future__ import annotations
import math

def shell_top(p): return p['floor_level']+p['height']
def profile_radius(p,z):
    if z < p['floor_level'] or z > shell_top(p): return None
    # upper half ellipsoid only: floor is the equator/hard boundary
    t=(z-p['floor_level'])/p['height']
    factor=math.sqrt(max(0.0,1.0-t*t))
    return p['diameter_x']/2*factor,p['diameter_y']/2*factor

def overlap(a,b):
    dx=b['cx']-a['cx'];dy=b['cy']-a['cy']
    rx=(a['diameter_x']+b['diameter_x'])/2; ry=(a['diameter_y']+b['diameter_y'])/2
    return (dx/rx)**2+(dy/ry)**2 < 1.0

def junction_plane(a,b):
    if not overlap(a,b): return None
    ax=max(a['diameter_x']/2,1e-9); ay=max(a['diameter_y']/2,1e-9)
    bx=max(b['diameter_x']/2,1e-9); by=max(b['diameter_y']/2,1e-9)
    # weighted perpendicular separator through center-weighted midpoint
    nx=b['cx']-a['cx'];ny=b['cy']-a['cy'];L=math.hypot(nx,ny)
    if L==0:return None
    nx/=L;ny/=L
    ra=1.0/math.sqrt((nx/ax)**2+(ny/ay)**2);rb=1.0/math.sqrt((nx/bx)**2+(ny/by)**2)
    t=ra/(ra+rb)
    px=a['cx']+(b['cx']-a['cx'])*t;py=a['cy']+(b['cy']-a['cy'])*t
    return {'point':(px,py),'normal':(nx,ny),'z0':min(a['floor_level'],b['floor_level']),'z1':min(shell_top(a),shell_top(b))}


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
    seen = set()
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

