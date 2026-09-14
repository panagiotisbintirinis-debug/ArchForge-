from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .commands import Command
from .model import Entity


@dataclass
class AddOpeningEntity(Command):
    """Add a door/window and its derived pod flat patch as one undoable transaction.

    Wall-hosted openings behave like ordinary entity additions. For pod-hosted openings,
    the first execution reconciles the derived planar patch and snapshots that semantic
    entity. Undo removes the opening (and cascades to its patch child); redo restores the
    exact same patch entity ID instead of manufacturing a new derived identity.
    """

    entity: Entity
    patch_entity: Optional[Entity] = None

    def do(self, doc):
        doc.add(self.entity.clone())
        if not self.entity.parent_id or self.entity.parent_id not in doc.entities:
            return
        host = doc.get(self.entity.parent_id)
        if host.kind != 'pod':
            return
        if self.patch_entity is None:
            from archforge.architecture.openings import infer_organic_opening_patches
            result = infer_organic_opening_patches(doc)
            match = next((doc.get(pid) for pid in result.active_ids
                          if doc.get(pid).params.get('opening_id') == self.entity.id), None)
            if match is None:
                raise RuntimeError('pod opening did not produce its planar host patch')
            self.patch_entity = match.clone()
        elif self.patch_entity.id not in doc.entities:
            doc.add(self.patch_entity.clone())
            doc.add_dependency(self.entity.parent_id, self.patch_entity.id)
            doc.add_dependency(self.entity.id, self.patch_entity.id)

    def undo(self, doc):
        if self.entity.id in doc.entities:
            doc.remove(self.entity.id)
