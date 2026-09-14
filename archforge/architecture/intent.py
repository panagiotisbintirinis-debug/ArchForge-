from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from archforge.core.model import Entity
from .room_identity import reconcile_room_bindings


@dataclass(frozen=True)
class ArchitectureDefaults:
    floor_thickness: float=.15
    ceiling_thickness: float=.12
    foundation_thickness: float=.30
    roof_thickness: float=.18
    auto_floor: bool=True
    auto_ceiling: bool=True
    auto_foundation: bool=True
    auto_roof: bool=True


@dataclass(frozen=True)
class IntentResult:
    room_signatures: Tuple[str,...]
    created_ids: Tuple[str,...]


def _existing(doc,kind,room_id,signature):
    return next((e for e in doc.entities.values()
                 if e.kind==kind and (e.params.get('room_id')==room_id or e.params.get('room_signature')==signature)),None)


def _sync_dependencies(doc,entity_id,wall_ids):
    for deps in doc.dependencies.values():
        deps.discard(entity_id)
    for wid in wall_ids:
        if wid in doc.entities and entity_id not in doc.dependencies.get(wid,set()):
            doc.add_dependency(wid,entity_id)


def infer_architecture(doc, defaults=ArchitectureDefaults(), z=None):
    """Materialize editable architecture while preserving semantic room identity.

    Topology signatures remain boundary fingerprints. Persistent room IDs are reconciled
    separately, so replacing an equivalent boundary wall does not duplicate the room's
    derived floor/ceiling/foundation/roof entities.
    """
    if z is None:z=float(doc.work_plane.origin[2])
    bound_faces=reconcile_room_bindings(doc,z=z);created=[]
    for face,room_id in bound_faces:
        sig=face.signature
        wall_heights=[float(doc.get(w).params['height']) for w in face.wall_ids if w in doc.entities]
        height=min(wall_heights) if wall_heights else 2.7
        specs=[]
        if defaults.auto_foundation: specs.append(('room_foundation',{'room_id':room_id,'room_signature':sig,'thickness':defaults.foundation_thickness,'offset_z':-defaults.foundation_thickness}))
        if defaults.auto_floor: specs.append(('room_floor',{'room_id':room_id,'room_signature':sig,'thickness':defaults.floor_thickness,'offset_z':0.0}))
        if defaults.auto_ceiling: specs.append(('room_ceiling',{'room_id':room_id,'room_signature':sig,'thickness':defaults.ceiling_thickness,'offset_z':height-defaults.ceiling_thickness}))
        if defaults.auto_roof: specs.append(('room_roof',{'room_id':room_id,'room_signature':sig,'thickness':defaults.roof_thickness,'offset_z':height,'roof_type':'auto'}))
        for kind,params in specs:
            e=_existing(doc,kind,room_id,sig)
            if e is None:
                e=Entity(kind,params,name='Auto '+kind.replace('room_','').title());doc.add(e);created.append(e.id)
            else:
                changes={}
                if e.params.get('room_id')!=room_id:changes['room_id']=room_id
                if e.params.get('room_signature')!=sig:changes['room_signature']=sig
                if changes:doc.update(e.id,changes)
            _sync_dependencies(doc,e.id,face.wall_ids)
    return IntentResult(tuple(face.signature for face,_ in bound_faces),tuple(created))


def infer_building_architecture(doc, defaults=ArchitectureDefaults(), levels=None) -> IntentResult:
    """Infer editable architecture across multiple building storeys.

    Discovers all distinct vertical wall planes or applies the requested storey levels,
    materializing room elements per level with persistent room identity.
    """
    if levels is not None:
        target_levels = sorted({float(lvl) for lvl in levels})
    else:
        wall_levels = {float(e.params['z']) for e in doc.entities.values() if e.kind == 'wall' and e.visible}
        if wall_levels:
            target_levels = sorted(wall_levels)
        else:
            target_levels = [float(doc.work_plane.origin[2])]

    all_signatures = []
    all_created = []
    for z in target_levels:
        res = infer_architecture(doc, defaults=defaults, z=z)
        all_signatures.extend(res.room_signatures)
        all_created.extend(res.created_ids)

    return IntentResult(tuple(all_signatures), tuple(all_created))

