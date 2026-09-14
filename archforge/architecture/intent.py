from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from archforge.core.model import Entity
from .topology import room_faces


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


def _existing(doc,kind,signature):
    return next((e for e in doc.entities.values() if e.kind==kind and e.params.get('room_signature')==signature),None)


def infer_architecture(doc, defaults=ArchitectureDefaults(), z=None):
    """Materialize obvious editable architecture from closed semantic wall topology.

    This is intentionally deterministic and idempotent: drawing the closing wall can call
    it immediately; calling it again does not duplicate derived elements. Generated
    elements remain normal semantic entities and can later be edited/replaced/removed.
    """
    if z is None:z=float(doc.work_plane.origin[2])
    faces=room_faces(doc,z=z);created=[]
    for face in faces:
        sig=face.signature
        wall_heights=[float(doc.get(w).params['height']) for w in face.wall_ids if w in doc.entities]
        height=min(wall_heights) if wall_heights else 2.7
        specs=[]
        if defaults.auto_foundation: specs.append(('room_foundation',{'room_signature':sig,'thickness':defaults.foundation_thickness,'offset_z':-defaults.foundation_thickness}))
        if defaults.auto_floor: specs.append(('room_floor',{'room_signature':sig,'thickness':defaults.floor_thickness,'offset_z':0.0}))
        if defaults.auto_ceiling: specs.append(('room_ceiling',{'room_signature':sig,'thickness':defaults.ceiling_thickness,'offset_z':height-defaults.ceiling_thickness}))
        if defaults.auto_roof: specs.append(('room_roof',{'room_signature':sig,'thickness':defaults.roof_thickness,'offset_z':height,'roof_type':'auto'}))
        for kind,params in specs:
            if _existing(doc,kind,sig):continue
            e=Entity(kind,params,name='Auto '+kind.replace('room_','').title());doc.add(e);created.append(e.id)
            for wid in face.wall_ids:
                if wid in doc.entities and e.id not in doc.dependencies.get(wid,set()):doc.add_dependency(wid,e.id)
    return IntentResult(tuple(f.signature for f in faces),tuple(created))
