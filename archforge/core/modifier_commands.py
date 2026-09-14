from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import copy

from .commands import Command
from .modifiers import SurfaceModifier, modifier_from_dict, modifier_to_dict


@dataclass
class AddSurfaceModifier(Command):
    modifier: SurfaceModifier
    def do(self,doc): doc.add_surface_modifier(copy.deepcopy(self.modifier))
    def undo(self,doc): doc.remove_surface_modifier(self.modifier.id)


@dataclass
class UpdateSurfaceModifier(Command):
    modifier_id: str
    changes: Dict[str,Any]
    before: Optional[Dict[str,Any]] = None
    def do(self,doc):
        if self.before is None:
            if self.modifier_id not in doc.surface_modifiers: raise KeyError(self.modifier_id)
            self.before=modifier_to_dict(doc.surface_modifiers[self.modifier_id])
        doc.update_surface_modifier(self.modifier_id,**copy.deepcopy(self.changes))
    def undo(self,doc):
        if self.before is None: return
        current=doc.surface_modifiers.get(self.modifier_id)
        if current is None: raise KeyError(self.modifier_id)
        old_owner=current.target.owner_id
        restored=modifier_from_dict(copy.deepcopy(self.before));restored.validate(doc)
        doc.surface_modifiers[self.modifier_id]=restored
        doc.mark_dirty(old_owner);doc.mark_dirty(restored.target.owner_id)


@dataclass
class RemoveSurfaceModifier(Command):
    modifier_id: str
    removed: Optional[SurfaceModifier] = None
    def do(self,doc): self.removed=copy.deepcopy(doc.remove_surface_modifier(self.modifier_id))
    def undo(self,doc):
        if self.removed is None: return
        doc.add_surface_modifier(copy.deepcopy(self.removed))
