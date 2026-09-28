from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Optional

from .commands import CommandStack
from .model import Document
from .roof_commands import SetRoofEdgeOffset


@dataclass
class RoofEdgeOffsetTransaction:
    """Transient direct edit for one semantic flat-roof boundary edge.

    The edge is identified by its host wall id, never by a global axis or polygon
    index. Pointer/raycast code supplies displacement along the edge's local outward
    normal; preview remains transaction-local until commit routes through the shared
    ``SetRoofEdgeOffset`` command.
    """

    doc: Document
    stack: CommandStack
    roof_id: str
    wall_id: str
    preview_offset: Optional[float] = None
    _initial_offset: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        roof = self.doc.get(self.roof_id)
        if roof.kind != "room_roof" or roof.params.get("roof_type", "flat") != "flat":
            raise ValueError("roof edge drag requires a flat room roof")
        if self.wall_id not in self.doc.entities or self.doc.get(self.wall_id).kind != "wall":
            raise ValueError("roof edge drag requires an existing boundary wall")
        offsets = roof.params.get("edge_offsets", {})
        self._initial_offset = float(offsets.get(self.wall_id, 0.0))
        self.preview_offset = self._initial_offset

    def update_local_displacement(self, displacement: float) -> float:
        """Preview a signed displacement in the selected edge's local normal frame."""
        value = self._initial_offset + float(displacement)
        if not math.isfinite(value):
            raise ValueError("roof edge displacement must be finite")
        self.preview_offset = value
        return value

    def commit(self) -> bool:
        """Commit one real edit; a click/no-op gesture remains history-neutral."""
        if self.preview_offset is None:
            return False
        value = float(self.preview_offset)
        if abs(value - self._initial_offset) <= 1e-9:
            return False
        self.stack.execute(SetRoofEdgeOffset(self.roof_id, self.wall_id, value))
        self._initial_offset = value
        return True

    def cancel(self) -> None:
        """Discard transient preview without touching authoritative state/history."""
        self.preview_offset = self._initial_offset
