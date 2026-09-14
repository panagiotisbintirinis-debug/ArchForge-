from __future__ import annotations

import uuid
from typing import Tuple

from .topology import RoomFace, room_faces


def _polygon_key(polygon, tolerance: float = 1e-6):
    """Return a rotation/direction-invariant quantized polygon key."""
    if tolerance <= 0:
        raise ValueError('tolerance must be > 0')
    pts=[(round(float(x)/tolerance),round(float(y)/tolerance)) for x,y in polygon]
    if not pts:
        return ()
    forward=[tuple(pts[i:]+pts[:i]) for i in range(len(pts))]
    rev=list(reversed(pts));backward=[tuple(rev[i:]+rev[:i]) for i in range(len(rev))]
    return min(forward+backward)


def reconcile_room_bindings(doc, z=None, tolerance: float = 1e-5) -> Tuple[Tuple[RoomFace,str],...]:
    """Bind transient topology faces to persistent semantic room IDs conservatively.

    Exact topology signature is the primary match. If boundary objects were recreated,
    an exact geometric polygon match may heal the binding. Split/merge inheritance is
    intentionally not guessed: unmatched predecessor rooms become ``unclosed`` and new
    faces receive new IDs until an explicit policy is implemented.
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
            key=_polygon_key(face.polygon,tolerance)
            polygon_matches=[rid for rid,b in bindings.items()
                             if rid not in used and abs(float(b.get('z',z))-float(z))<=tolerance
                             and _polygon_key(b.get('polygon',()),tolerance)==key]
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

        # Migrate legacy metadata keyed by topology signature to stable room ID.
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
