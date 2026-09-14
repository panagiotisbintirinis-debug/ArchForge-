from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional
import copy
import uuid


SUPPORTED_SCULPT_OPS = {
    'pull',          # displace a selected surface region along a direction/normal
    'push',          # inverse displacement
    'inflate',       # smooth outward bulge
    'recess',        # smooth inward depression
    'crease',        # sharpen/fold a region
    'smooth',        # relaxation/smoothing operation
    'cut',           # subtractive sculptural cut
    'add_volume',    # additive local mass
}


@dataclass
class SurfaceRef:
    """Stable semantic reference to a deformable building surface.

    ``owner_id`` points to the semantic object (wall, floor, roof, pod, room_floor, etc.).
    ``surface_role`` names the semantic surface (exterior, interior, ceiling, junction,
    roof_top, soffit, pod_shell, ...). ``subregion`` stores a backend-neutral selector
    such as UV bounds, a brush mask identifier, or a named patch.  Persistent modifiers
    never depend on transient mesh face indices.
    """
    owner_id: str
    surface_role: str
    subregion: Dict[str, Any] = field(default_factory=dict)

    def validate(self, doc) -> None:
        if self.owner_id not in doc.entities:
            raise ValueError('surface owner does not exist')
        if not self.surface_role or not isinstance(self.surface_role, str):
            raise ValueError('surface_role must be a non-empty string')


@dataclass
class SurfaceModifier:
    """Non-destructive sculpt operation applied after semantic base geometry.

    The semantic building object remains the source of truth. Geometry backends may
    evaluate these modifiers into B-rep, mesh, or hybrid output for viewport/export.
    """
    target: SurfaceRef
    operation: str
    params: Dict[str, Any]
    name: str = ''
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True
    order: int = 0

    def validate(self, doc) -> None:
        self.target.validate(doc)
        if self.operation not in SUPPORTED_SCULPT_OPS:
            raise ValueError(f'unsupported sculpt operation: {self.operation}')
        if not isinstance(self.params, dict):
            raise ValueError('modifier params must be a dictionary')
        if self.operation in ('pull','push','inflate','recess'):
            amount = float(self.params.get('amount', 0.0))
            if amount < 0:
                raise ValueError('modifier amount must be >= 0')


def modifier_from_dict(raw: Dict[str, Any]) -> SurfaceModifier:
    data = copy.deepcopy(raw)
    target = data.get('target')
    if isinstance(target, dict):
        data['target'] = SurfaceRef(**target)
    return SurfaceModifier(**data)


def modifier_to_dict(modifier: SurfaceModifier) -> Dict[str, Any]:
    return asdict(modifier)


def ordered_modifiers(doc, owner_id: Optional[str] = None) -> List[SurfaceModifier]:
    mods = list(doc.surface_modifiers.values())
    if owner_id is not None:
        mods = [m for m in mods if m.target.owner_id == owner_id]
    return sorted(mods, key=lambda m: (m.order, m.id))


def add_modifier(doc, modifier: SurfaceModifier) -> str:
    modifier.validate(doc)
    if modifier.id in doc.surface_modifiers:
        raise ValueError('duplicate modifier id')
    doc.surface_modifiers[modifier.id] = copy.deepcopy(modifier)
    doc.mark_dirty(modifier.target.owner_id)
    return modifier.id


def update_modifier(doc, modifier_id: str, **changes) -> None:
    if modifier_id not in doc.surface_modifiers:
        raise KeyError(modifier_id)
    before = doc.surface_modifiers[modifier_id]
    data = modifier_to_dict(before)
    if 'target' in changes and isinstance(changes['target'], SurfaceRef):
        changes = dict(changes)
        changes['target'] = asdict(changes['target'])
    data.update(copy.deepcopy(changes))
    after = modifier_from_dict(data)
    after.validate(doc)
    old_owner = before.target.owner_id
    doc.surface_modifiers[modifier_id] = after
    doc.mark_dirty(old_owner)
    doc.mark_dirty(after.target.owner_id)


def remove_modifier(doc, modifier_id: str) -> SurfaceModifier:
    if modifier_id not in doc.surface_modifiers:
        raise KeyError(modifier_id)
    modifier = doc.surface_modifiers.pop(modifier_id)
    doc.mark_dirty(modifier.target.owner_id)
    return modifier
