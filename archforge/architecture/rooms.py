from __future__ import annotations

from typing import Optional

from archforge.core.model import Entity
from archforge.architecture.topology import room_faces


ROOM_SLAB_KINDS=frozenset({'room_floor','room_ceiling','room_foundation','room_roof'})


def find_room_face(doc, signature: str, tolerance: float = 1e-5):
    """Find an active derived room face by stable signature across all wall levels."""
    # The semantic wall IDs encoded by a signature are globally unique, so scanning all
    # active faces is safe and keeps room floors valid when the current work plane changes.
    levels=sorted({float(e.params['z']) for e in doc.entities.values() if e.kind=='wall' and e.visible})
    for z in levels:
        for face in room_faces(doc,tolerance=tolerance,z=z):
            if face.signature==signature:
                return face,z
    return None


def create_room_floor(doc, signature: str, thickness: float = 0.15, offset_z: float = 0.0, name: str = 'Auto Floor') -> Entity:
    """Create a semantic floor linked to a derived room instead of copying its polygon."""
    found=find_room_face(doc,signature)
    if found is None:
        raise ValueError('room signature is not currently active')
    face,_=found
    e=Entity('room_floor',{'room_signature':signature,'thickness':float(thickness),'offset_z':float(offset_z)},name=name)
    doc.add(e)
    for wid in face.wall_ids:
        if wid in doc.entities and e.id not in doc.dependencies.get(wid,set()):
            doc.add_dependency(wid,e.id)
    return e


def room_slab_geometry(doc, slab_entity: Entity, tolerance: float = 1e-5) -> Optional[dict]:
    """Resolve any inferred room slab against the room's current live topology."""
    if slab_entity.kind not in ROOM_SLAB_KINDS:
        raise ValueError('entity is not a derived room slab')
    p=slab_entity.params
    found=find_room_face(doc,p['room_signature'],tolerance=tolerance)
    if found is None:
        return None
    face,base_z=found
    z=base_z+float(p.get('offset_z',0.0))
    return {'points':[tuple(q) for q in face.polygon],
            'z':z,
            'thickness':float(p['thickness']),
            'room_signature':face.signature,
            'wall_ids':tuple(face.wall_ids)}


def room_floor_geometry(doc, floor_entity: Entity, tolerance: float = 1e-5) -> Optional[dict]:
    """Resolve a room floor's live polygon; return None while its room is not closed."""
    if floor_entity.kind!='room_floor':
        raise ValueError('entity is not a room_floor')
    return room_slab_geometry(doc,floor_entity,tolerance=tolerance)
