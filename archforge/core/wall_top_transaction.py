from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .commands import CommandStack
from .model import Document
from .wall_profile_commands import SetWallTopEndpoint
from .wall_top_3d import vertical_height_from_ray, wall_top_endpoint_world

Vec3 = Tuple[float, float, float]


@dataclass
class WallTopEndpointTransaction:
    """Transient direct-manipulation transaction for one semantic wall-top endpoint.

    Pointer motion updates only ``preview_height``.  The authoritative Document is
    untouched until ``commit`` executes the same SetWallTopEndpoint command used by
    exact numeric editing.  This keeps 3D handle previews view-local and reversible.
    """

    doc: Document
    stack: CommandStack
    wall_id: str
    endpoint: str
    preview_height: Optional[float] = None

    def __post_init__(self) -> None:
        wall = self.doc.get(self.wall_id)
        if wall.kind != 'wall':
            raise ValueError('wall top transaction requires a wall entity')
        # Validate endpoint identity and seed preview from authoritative state.
        _x, _y, top_z = wall_top_endpoint_world(wall.params, self.endpoint)
        self.preview_height = top_z - float(wall.params['z'])

    def update_from_ray(self, ray_origin: Vec3, ray_direction: Vec3) -> float:
        wall = self.doc.get(self.wall_id)
        x, y, _top_z = wall_top_endpoint_world(wall.params, self.endpoint)
        height = vertical_height_from_ray(
            float(wall.params['z']),
            (x, y),
            ray_origin,
            ray_direction,
        )
        self.preview_height = height
        return height

    def preview_world_point(self) -> Vec3:
        wall = self.doc.get(self.wall_id)
        x, y, _top_z = wall_top_endpoint_world(wall.params, self.endpoint)
        return (x, y, float(wall.params['z']) + float(self.preview_height))

    def commit(self) -> None:
        if self.preview_height is None:
            return
        self.stack.execute(
            SetWallTopEndpoint(self.wall_id, self.endpoint, float(self.preview_height))
        )

    def cancel(self) -> None:
        """Cancel is intentionally a no-op on authoritative state."""
        return None
