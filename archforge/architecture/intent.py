from __future__ import annotations
from dataclasses import dataclass, replace
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


def _derived_room_level(doc, entity):
    room_id=entity.params.get('room_id')
    if room_id in doc.room_bindings:
        return float(doc.room_bindings[room_id].get('z',0.0))
    signature=entity.params.get('room_signature')
    matches=[float(binding.get('z',0.0)) for binding in doc.room_bindings.values()
             if binding.get('signature')==signature]
    return matches[0] if len(matches)==1 else None


def _auto_derived(entity):
    """Recognize inference-owned entities without claiming manually-authored overrides."""
    return bool(entity.params.get('auto_inferred')) or entity.name.startswith('Auto ')


def _prune_building_envelope(doc,target_levels,bottom_level,top_level,defaults,tolerance=1e-6):
    """Remove obsolete automatic envelope layers left by earlier per-storey inference.

    Only automatic derived foundation/roof entities are removed. Manual entities of the
    same semantic kind are left untouched, preserving the manual-override contract.
    """
    def close(a,b):return abs(float(a)-float(b))<=tolerance
    for entity in list(doc.entities.values()):
        if entity.kind not in ('room_foundation','room_roof') or not _auto_derived(entity):
            continue
        z=_derived_room_level(doc,entity)
        if z is None or not any(close(z,target) for target in target_levels):
            continue
        if entity.kind=='room_foundation':
            keep=bool(defaults.auto_foundation and close(z,bottom_level))
        else:
            keep=bool(defaults.auto_roof and close(z,top_level))
        if not keep and entity.id in doc.entities:
            doc.remove(entity.id)


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
        common={'room_id':room_id,'room_signature':sig,'auto_inferred':True}
        if defaults.auto_foundation: specs.append(('room_foundation',{**common,'thickness':defaults.foundation_thickness,'offset_z':-defaults.foundation_thickness}))
        if defaults.auto_floor: specs.append(('room_floor',{**common,'thickness':defaults.floor_thickness,'offset_z':0.0}))
        if defaults.auto_ceiling: specs.append(('room_ceiling',{**common,'thickness':defaults.ceiling_thickness,'offset_z':height-defaults.ceiling_thickness}))
        if defaults.auto_roof: specs.append(('room_roof',{**common,'thickness':defaults.roof_thickness,'offset_z':height,'roof_type':'auto'}))
        for kind,params in specs:
            e=_existing(doc,kind,room_id,sig)
            if e is None:
                e=Entity(kind,params,name='Auto '+kind.replace('room_','').title());doc.add(e);created.append(e.id)
            else:
                changes={}
                if e.params.get('room_id')!=room_id:changes['room_id']=room_id
                if e.params.get('room_signature')!=sig:changes['room_signature']=sig
                if e.name.startswith('Auto ') and e.params.get('auto_inferred') is not True:
                    changes['auto_inferred']=True
                if changes:doc.update(e.id,changes)
            _sync_dependencies(doc,e.id,face.wall_ids)
    return IntentResult(tuple(face.signature for face,_ in bound_faces),tuple(created))


def infer_building_architecture(doc, defaults=ArchitectureDefaults(), levels=None) -> IntentResult:
    """Infer conventional storey layers without turning ArchForge into a 2.5D modeler.

    Storeys are semantic/elevation references inside universal XYZ space. This routine
    only governs automatic conventional room slabs: the lowest inferred storey may own
    the building foundation, every storey may own its floor/ceiling layers, and the
    highest inferred storey may own the automatic roof. Organic pods/domes, sculpted
    geometry, mechanical assemblies and arbitrary work planes are not reassigned or
    flattened by storey inference.
    """
    if levels is not None:
        target_levels = sorted({float(lvl) for lvl in levels})
    else:
        wall_levels = {float(e.params['z']) for e in doc.entities.values() if e.kind == 'wall' and e.visible}
        if wall_levels:
            target_levels = sorted(wall_levels)
        else:
            target_levels = [float(doc.work_plane.origin[2])]

    bottom_level=target_levels[0]
    top_level=target_levels[-1]
    all_signatures=[]
    all_created=[]
    for z in target_levels:
        level_defaults=replace(
            defaults,
            auto_foundation=defaults.auto_foundation and z==bottom_level,
            auto_roof=defaults.auto_roof and z==top_level,
        )
        res=infer_architecture(doc,defaults=level_defaults,z=z)
        all_signatures.extend(res.room_signatures)
        all_created.extend(res.created_ids)

    _prune_building_envelope(doc,target_levels,bottom_level,top_level,defaults)
    return IntentResult(tuple(all_signatures),tuple(all_created))

