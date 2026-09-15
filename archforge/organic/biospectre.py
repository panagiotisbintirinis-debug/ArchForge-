from __future__ import annotations
import math


def shell_top(p): return p['floor_level']+p['height']


def _slice_scale(p,z):
    """Upper-half ellipsoid XY scale at world elevation z, or 0 outside the pod."""
    floor=float(p['floor_level']);height=float(p['height']);z=float(z)
    if height<=0 or z<floor or z>floor+height:return 0.0
    t=(z-floor)/height
    return math.sqrt(max(0.0,1.0-t*t))


def profile_radius(p,z):
    factor=_slice_scale(p,z)
    if factor<=0.0 and not math.isclose(float(z),float(p['floor_level']),abs_tol=1e-12):return None
    # upper half ellipsoid only: floor is the equator/hard boundary
    return p['diameter_x']/2*factor,p['diameter_y']/2*factor


def _radial_extent(p,nx,ny):
    """Distance from pod center to its rotated XY ellipse along a world-space ray."""
    rx=max(float(p['diameter_x'])/2.0,1e-9);ry=max(float(p['diameter_y'])/2.0,1e-9)
    angle=math.radians(float(p.get('rotation',0.0)));c,s=math.cos(angle),math.sin(angle)
    # Rotate the world direction into the ellipse's intrinsic frame.
    lx=c*nx+s*ny;ly=-s*nx+c*ny
    return 1.0/math.sqrt((lx/rx)**2+(ly/ry)**2)


def _slice_radial_extent(p,nx,ny,z):
    """World-space radial reach of the actual horizontal pod slice at elevation z."""
    return _radial_extent(p,nx,ny)*_slice_scale(p,z)


def overlap(a,b):
    """Return whether the two rotated pod base footprints physically overlap in XY.

    This is intentionally a footprint query. A real 3D organic junction additionally
    requires overlap of the live upper-ellipsoid slices and is decided by
    ``junction_plane``.
    """
    dx=float(b['cx'])-float(a['cx']);dy=float(b['cy'])-float(a['cy']);distance=math.hypot(dx,dy)
    if distance<=1e-12:return True
    nx,ny=dx/distance,dy/distance
    return distance < _radial_extent(a,nx,ny)+_radial_extent(b,-nx,-ny)


def junction_plane(a,b):
    """Return a stable flat separator only when the pod volumes truly overlap in 3D.

    Upper-half ellipsoid slices monotonically narrow above each pod's floor, so the
    largest possible overlap in the shared vertical interval occurs at its lowest
    elevation ``z0``. Testing the actual rotated radial reaches there is therefore enough
    to reject base-footprint false positives. The same live slice reaches also weight the
    separator position, keeping it inside both staggered pod slices.
    """
    z0=max(float(a['floor_level']),float(b['floor_level']))
    z1=min(float(shell_top(a)),float(shell_top(b)))
    if z1<=z0:return None
    nx=float(b['cx'])-float(a['cx']);ny=float(b['cy'])-float(a['cy']);L=math.hypot(nx,ny)
    if L<=1e-12:return None
    nx/=L;ny/=L
    ra=_slice_radial_extent(a,nx,ny,z0);rb=_slice_radial_extent(b,-nx,-ny,z0)
    if ra<=1e-12 or rb<=1e-12 or L>=ra+rb-1e-10:return None
    t=ra/(ra+rb)
    px=float(a['cx'])+(float(b['cx'])-float(a['cx']))*t
    py=float(a['cy'])+(float(b['cy'])-float(a['cy']))*t
    return {'point':(px,py),'normal':(nx,ny),'z0':z0,'z1':z1}


def _line_interval_in_pod(p, point, tangent, z, tolerance=1e-10):
    """Return the interval along a horizontal plane-line that lies inside one pod slice."""
    floor=float(p['floor_level']);height=float(p['height'])
    rel=(float(z)-floor)/height
    if rel < -tolerance or rel > 1.0+tolerance:return None
    factor2=max(0.0,1.0-rel*rel)
    if factor2<=tolerance:return None
    rx=float(p['diameter_x'])/2.0*math.sqrt(factor2)
    ry=float(p['diameter_y'])/2.0*math.sqrt(factor2)
    if min(rx,ry)<=tolerance:return None

    angle=math.radians(float(p.get('rotation',0.0)));c,s=math.cos(angle),math.sin(angle)
    dx=float(point[0])-float(p['cx']);dy=float(point[1])-float(p['cy'])
    # World XY -> local ellipse coordinates.
    x0=c*dx+s*dy;y0=-s*dx+c*dy
    tx=c*float(tangent[0])+s*float(tangent[1])
    ty=-s*float(tangent[0])+c*float(tangent[1])

    A=(tx/rx)**2+(ty/ry)**2
    B=2.0*(x0*tx/(rx*rx)+y0*ty/(ry*ry))
    C=(x0/rx)**2+(y0/ry)**2-1.0
    if A<=tolerance:return None
    disc=B*B-4.0*A*C
    if disc < -tolerance:return None
    root=math.sqrt(max(0.0,disc))
    q0=(-B-root)/(2.0*A);q1=(-B+root)/(2.0*A)
    return (min(q0,q1),max(q0,q1))


def junction_section_polygon(a,b,samples=24):
    """Approximate the shared flat vertical section between two overlapping pod volumes.

    This is a derived preview/semantic surface, not a Boolean-unioned fabrication shell.
    The polygon is sampled in the stable vertical junction plane and recomputed from the
    current pod parameters whenever geometry is evaluated.
    """
    plane=junction_plane(a,b)
    if plane is None:return None
    samples=max(4,int(samples))
    px,py=map(float,plane['point']);nx,ny=map(float,plane['normal'])
    tangent=(-ny,nx);z0=float(plane['z0']);z1=float(plane['z1'])
    left=[];right=[]
    # Include enough interior samples that a crown degeneracy cannot erase the section.
    for i in range(samples+1):
        z=z0+(z1-z0)*i/samples
        ia=_line_interval_in_pod(a,(px,py),tangent,z)
        ib=_line_interval_in_pod(b,(px,py),tangent,z)
        if ia is None or ib is None:continue
        lo=max(ia[0],ib[0]);hi=min(ia[1],ib[1])
        if hi-lo<=1e-8:continue
        left.append((px+tangent[0]*lo,py+tangent[1]*lo,z))
        right.append((px+tangent[0]*hi,py+tangent[1]*hi,z))
    if len(left)<2:return None
    polygon=left+list(reversed(right))
    # Remove adjacent numerical duplicates while preserving the section cycle.
    cleaned=[]
    for point in polygon:
        if not cleaned or math.dist(point,cleaned[-1])>1e-9:cleaned.append(point)
    if len(cleaned)>2 and math.dist(cleaned[0],cleaned[-1])<=1e-9:cleaned.pop()
    return tuple(cleaned) if len(cleaned)>=4 else None


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
