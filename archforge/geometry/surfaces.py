from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class SurfaceDescriptor:
    """Stable semantic surface identity independent of tessellation face indices."""
    owner_id: str
    role: str
    deformable: bool = True
    fabrication_surface: bool = True
    description: str = ''

    @property
    def key(self) -> str:
        return f'{self.owner_id}:{self.role}'


# Roles are intentionally semantic. Backends may subdivide a role into many transient
# B-rep faces or mesh triangles without changing persistent modifier targets.
_KIND_ROLES: Dict[str, Tuple[Tuple[str, bool, bool, str], ...]] = {
    'wall': (
        ('exterior', True, True, 'wall exterior face'),
        ('interior', True, True, 'wall interior face'),
        ('top', True, True, 'wall top'),
        ('start', True, True, 'wall start return'),
        ('end', True, True, 'wall end return'),
        ('bottom', False, True, 'wall bottom'),
    ),
    'box': tuple((r, True, True, f'box {r} face') for r in ('top','bottom','left','right','front','back')),
    'mechanical_part': tuple((r, True, True, f'mechanical part {r} face') for r in ('top','bottom','left','right','front','back')),
    'pod': (
        ('pod_shell', True, True, 'curved pod shell'),
        ('junction', True, True, 'generated flat pod junction'),
        ('floor', True, True, 'pod floor'),
    ),
    'floor': (
        ('top', True, True, 'floor top'),
        ('bottom', True, True, 'floor underside'),
        ('edge', True, True, 'floor perimeter'),
    ),
    'room_floor': (
        ('top', True, True, 'derived room floor top'),
        ('bottom', True, True, 'derived room floor underside'),
        ('edge', True, True, 'derived room floor perimeter'),
    ),
    # A room is semantic space rather than a printable solid, but its ceiling is a valid
    # architectural sculpt target. Evaluation later maps it to generated ceiling geometry.
    'room': (
        ('ceiling', True, False, 'generated room ceiling'),
        ('floor_boundary', False, False, 'room floor boundary'),
    ),
}


def surface_catalog(doc, owner_id: str) -> Tuple[SurfaceDescriptor, ...]:
    if owner_id not in doc.entities:
        raise ValueError('surface owner does not exist')
    entity = doc.entities[owner_id]
    roles = _KIND_ROLES.get(entity.kind, ())
    return tuple(SurfaceDescriptor(owner_id, role, deformable, fabrication, description)
                 for role, deformable, fabrication, description in roles)


def surface_roles(doc, owner_id: str) -> Tuple[str, ...]:
    return tuple(s.role for s in surface_catalog(doc, owner_id))


def resolve_surface(doc, owner_id: str, role: str) -> SurfaceDescriptor:
    for surface in surface_catalog(doc, owner_id):
        if surface.role == role:
            return surface
    kind = doc.entities[owner_id].kind if owner_id in doc.entities else '<missing>'
    raise ValueError(f'unsupported semantic surface role {role!r} for {kind}')


def validate_surface_role(doc, owner_id: str, role: str, *, require_deformable: bool = False) -> SurfaceDescriptor:
    surface = resolve_surface(doc, owner_id, role)
    if require_deformable and not surface.deformable:
        raise ValueError(f'surface {surface.key} is not deformable')
    return surface
