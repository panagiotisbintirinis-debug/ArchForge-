from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional
import copy
import uuid


SUPPORTED_SCULPT_OPS = {
    'pull', 'push', 'inflate', 'recess', 'crease', 'smooth', 'cut', 'add_volume',
}


@dataclass
class SurfaceRef:
    """Stable semantic reference to a deformable surface.

    Persistent references use semantic owner + role + backend-neutral subregion data;
    they never persist transient mesh/B-rep face indices.
    """
    owner_id: str
    surface_role: str
    subregion: Dict[str, Any] = field(default_factory=dict)

    def validate(self, doc) -> None:
        if self.owner_id not in doc.entities:
            raise ValueError('surface owner does not exist')
        if not self.surface_role or not isinstance(self.surface_role, str):
            raise ValueError('surface_role must be a non-empty string')
        if not isinstance(self.subregion, dict):
            raise ValueError('surface subregion must be a dictionary')
        from archforge.geometry.surfaces import validate_surface_role
        validate_surface_role(doc, self.owner_id, self.surface_role, require_deformable=True)


@dataclass
class SurfaceModifier:
    """Non-destructive sculpt operation evaluated after semantic base geometry."""
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
        if self.operation in ('pull', 'push', 'inflate', 'recess'):
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
    if owner_id is None:
        mods = list(doc.surface_modifiers.values())
    else:
        mods = [
            doc.surface_modifiers[mid]
            for mid in doc.modifier_ids_for_owner(owner_id)
            if mid in doc.surface_modifiers
        ]
    return sorted(mods, key=lambda m: (m.order, m.id))


def add_modifier(doc, modifier: SurfaceModifier) -> str:
    modifier.validate(doc)
    if modifier.id in doc.surface_modifiers:
        raise ValueError('duplicate modifier id')
    stored = copy.deepcopy(modifier)
    doc.surface_modifiers[stored.id] = stored
    doc._index_modifier(stored)
    doc.mark_dirty(stored.target.owner_id)
    return stored.id


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
    new_owner = after.target.owner_id
    if old_owner != new_owner:
        doc._deindex_modifier(modifier_id, before)
    doc.surface_modifiers[modifier_id] = after
    if old_owner != new_owner:
        doc._index_modifier(after)

    doc.mark_dirty(old_owner)
    if new_owner != old_owner:
        doc.mark_dirty(new_owner)


def remove_modifier(doc, modifier_id: str) -> SurfaceModifier:
    if modifier_id not in doc.surface_modifiers:
        raise KeyError(modifier_id)
    modifier = doc.surface_modifiers[modifier_id]
    doc._deindex_modifier(modifier_id, modifier)
    modifier = doc.surface_modifiers.pop(modifier_id)
    doc.mark_dirty(modifier.target.owner_id)
    return modifier
