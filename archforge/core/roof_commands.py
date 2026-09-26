from __future__ import annotations

from dataclasses import dataclass
import copy
import math

from .commands import Command
from .model import Document


@dataclass
class SetRoofEdgeOffset(Command):
    """Set one semantic flat-roof boundary offset as an exactly reversible edit.

    Boundary identity is the host wall id, not a polygon index or global axis.  Zero
    removes the sparse override so undo/redo and save/load preserve legacy roofs that
    did not have ``edge_offsets`` at all.
    """

    roof_id: str
    wall_id: str
    offset: float
    before_offsets: dict[str, float] | None = None
    before_present: bool | None = None

    def do(self, doc: Document) -> None:
        roof = doc.get(self.roof_id)
        if roof.kind != 'room_roof' or roof.params.get('roof_type', 'flat') != 'flat':
            raise ValueError('roof edge offset edit requires a flat room roof')
        if self.wall_id not in doc.entities or doc.get(self.wall_id).kind != 'wall':
            raise ValueError('roof edge offset requires an existing boundary wall')
        value = float(self.offset)
        if not math.isfinite(value):
            raise ValueError('roof edge offset must be finite')

        if self.before_present is None:
            self.before_present = 'edge_offsets' in roof.params
            self.before_offsets = copy.deepcopy(roof.params.get('edge_offsets', {}))

        offsets = copy.deepcopy(roof.params.get('edge_offsets', {}))
        if abs(value) <= 1e-12:
            offsets.pop(self.wall_id, None)
        else:
            offsets[self.wall_id] = value
        doc.update(self.roof_id, {'edge_offsets': offsets})

    def undo(self, doc: Document) -> None:
        if self.before_present is None:
            return
        roof = doc.get(self.roof_id)
        if self.before_present:
            doc.update(self.roof_id, {'edge_offsets': copy.deepcopy(self.before_offsets or {})})
        else:
            roof.params.pop('edge_offsets', None)
            roof.revision += 1
            doc.mark_dirty(self.roof_id)
