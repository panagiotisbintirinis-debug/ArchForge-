from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from .commands import Command
from .model import Document


@dataclass
class SetWallTopEndpoint(Command):
    """Set one semantic wall-top endpoint height as one reversible edit.

    The value is a height above the wall base, not a world-axis position.  This keeps
    the edit intrinsic to the wall profile so pointer handles, orthographic views and
    exact numeric input can all commit through the same command semantics.
    """

    wall_id: str
    endpoint: str
    height: float
    before_value: Optional[float] = None
    before_present: Optional[bool] = None

    def do(self, doc: Document):
        wall = doc.get(self.wall_id)
        if wall.kind != 'wall':
            raise ValueError('wall top endpoint edit requires a wall entity')
        if self.endpoint not in ('start', 'end'):
            raise ValueError("endpoint must be 'start' or 'end'")
        value = float(self.height)
        if not math.isfinite(value) or value <= 0:
            raise ValueError('wall endpoint height must be finite and > 0')

        key = f'{self.endpoint}_height'
        if self.before_present is None:
            self.before_present = key in wall.params
            self.before_value = float(wall.params[key]) if self.before_present else None
        doc.update(self.wall_id, {key: value})

    def undo(self, doc: Document):
        if self.before_present is None:
            return
        key = f'{self.endpoint}_height'
        if self.before_present:
            doc.update(self.wall_id, {key: self.before_value})
        else:
            wall = doc.get(self.wall_id)
            wall.params.pop(key, None)
            doc.mark_dirty(self.wall_id)
