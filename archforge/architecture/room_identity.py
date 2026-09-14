from __future__ import annotations

import math
import uuid
from typing import Tuple

from .topology import RoomFace, room_faces


def _point_close(a,b,tolerance):
    return math.hypot(float(a[0])-float(b[0]),float(a[1])-float(b[1]))<=tolerance


def _redundant_collinear_vertex(a,b,c,tolerance):
    """Return True when b only subdivides the straight boundary segment a-c."""
    ax,ay=map(float,a);bx,by=map(float,b);cx,cy=map(float,c)
    acx,acy=cx-ax,cy-ay
    length2=acx*acx+acy*acy
    if length2<=tolerance*tolerance:
        return _point_close(a,b,tolerance) or _point_close(b,c,tolerance)
    t=((bx-ax)*acx+(by-ay)*acy)/length2
    if t < -tolerance or t > 1.0+tolerance:
        return False
    px,py=ax+t*acx,ay+t*acy
    return math.hypot(bx-px,by-py)<=tolerance


def _simplify_polygon(polygon,tolerance):
    """Remove duplicate/collinear subdivision vertices without changing polygon shape."""
    pts=[tuple(map(float,p)) for p in polygon]
    if len(pts)>1 and _point_close(pts[0],pts[-1],tolerance):
        pts.pop()
    changed=True
    while changed and len(pts)>3:
        changed=False
        keep=[];n=len(pts)
        for i,p in enumerate(pts):
            prev=pts[(i-1)%n];nxt=pts[(i+1)%n]
            if _point_close(prev,p,tolerance) or _redundant_collinear_vertex(prev,p,nxt,tolerance):
                changed=True
                continue
            keep.append(p)
        if len(keep)<3:
            break
        pts=keep
    return pts


def _polygon_matches(a,b,tolerance: float = 1e-5):
    """Compare physical polygon cycles independent of start/direction and collinear splits."""
    if tolerance<=0:raise ValueError('tolerance must be > 0')
    aa=_simplify_polygon(a,tolerance);bb=_simplify_polygon(b,tolerance)
    if len(aa)!=len(bb) or not aa:return False
    n=len(aa)
    for start in range(n):
        if all(_point_close(aa[i],bb[(start+i)%n],tolerance) for i in range(n)):return True
        if all(_point_close(aa[i],bb[(start-i)%n],tolerance) for i in range(n)):return True
    return False


def reconcile_room_bindings(doc, z=None, tolerance: float = 1e-5) -> Tuple[Tuple[RoomFace,str],...]:
    """Bind transient topology faces to persistent semantic room IDs conservatively.

    Exact topology signature is the primary match. If boundary objects were recreated
    or a straight boundary was subdivided into collinear wall segments, an equivalent
    physical polygon within geometric tolerance may heal the binding. Genuine split/
    merge inheritance is intentionally not guessed: unmatched predecessor rooms become
    ``unclosed`` and new faces receive new IDs until an explicit policy is implemented.
    """
    if z is None:
        z=float(doc.work_plane.origin[2])
    faces=room_faces(doc,tolerance=tolerance,z=z)
    bindings=doc.room_bindings
    used=set();out=[]

    for face in faces:
        room_id=None
        signature_matches=[rid for rid,b in bindings.items()
                           if b.get('signature')==face.signature and abs(float(b.get('z',z))-float(z))<=tolerance]
        if len(signature_matches)==1:
            room_id=signature_matches[0]
        if room_id is None:
            polygon_matches=[rid for rid,b in bindings.items()
                             if rid not in used and abs(float(b.get('z',z))-float(z))<=tolerance
                             and _polygon_matches(b.get('polygon',()),face.polygon,tolerance)]
            if len(polygon_matches)==1:
                room_id=polygon_matches[0]
        if room_id is None:
            room_id=str(uuid.uuid4())
            bindings[room_id]={}

        binding=bindings[room_id]
        old_signature=binding.get('signature')
        binding.update({
            'signature':face.signature,
            'polygon':[list(p) for p in face.polygon],
            'z':float(z),
            'status':'enclosed',
        })
        used.add(room_id);out.append((face,room_id))

        for sig in (old_signature,face.signature):
            if sig and sig in doc.room_data and sig!=room_id:
                if room_id not in doc.room_data:
                    doc.room_data[room_id]=doc.room_data[sig]
                doc.room_data.pop(sig,None)

    for rid,binding in bindings.items():
        if rid not in used and abs(float(binding.get('z',z))-float(z))<=tolerance:
            binding['status']='unclosed'
    return tuple(out)


def room_id_for_signature(doc, signature: str, z=None, tolerance: float = 1e-5):
    for face,room_id in reconcile_room_bindings(doc,z=z,tolerance=tolerance):
        if face.signature==signature:
            return room_id
    return None


def room_binding(doc, room_id: str):
    return doc.room_bindings.get(room_id)


def resolve_room_metadata_key(doc, key: str):
    if key in doc.room_bindings:
        return key
    for room_id,binding in doc.room_bindings.items():
        if binding.get('signature')==key:
            return room_id
    return key
