from __future__ import annotations

import json
from typing import Iterable, Mapping, Any

from .wall_top_pbr import wall_top_pbr_handles
from .wall_top_web import WallTopWebInteraction


class PBRWallTopRuntime:
    """View-owned runtime for semantic wall-top handles in the PBR surface.

    The runtime deliberately owns no design state. Handle meshes are derived from the
    current Document selection, pointer motion updates only the controller preview,
    and release commits through the existing SetWallTopEndpoint CommandStack path.
    This gives the PBR viewport one narrow integration object instead of duplicating
    wall/profile semantics in JavaScript or renderer state.
    """

    def __init__(self, doc, stack, *, handle_radius: float = 0.11):
        self.doc = doc
        self.stack = stack
        self.handle_radius = float(handle_radius)
        self.web = WallTopWebInteraction(doc, stack)

    @property
    def active(self) -> bool:
        return self.web.active

    def rebind(self, doc, stack) -> None:
        if self.active:
            self.web.cancel()
        self.doc = doc
        self.stack = stack
        self.web.rebind(doc, stack)

    def handles(self) -> list[dict[str, Any]]:
        """Return visible/pickable PBR descriptors for the current selection."""
        return wall_top_pbr_handles(self.web.handles(), radius=self.handle_radius)

    def begin(self, handle_id: str) -> None:
        self.web.begin_handle(handle_id)

    def update_ray(self, origin: Iterable[float], direction: Iterable[float]) -> float:
        return self.web.update_ray(origin, direction)

    def finish(self) -> bool:
        return self.web.finish()

    def cancel(self) -> None:
        self.web.cancel()

    def scene_payload(self) -> Mapping[str, Any]:
        """Renderer payload kept separate from authoritative model geometry."""
        return {"wall_top_handles": self.handles()}

    def scene_payload_json(self) -> str:
        """Serialize only view-owned handles for the WebGL handle root.

        The active PBR viewport can inject this payload independently of the model
        scene payload. Keeping the serialization boundary separate makes it impossible
        for handle meshes to be mistaken for authoritative model entities merely by
        sharing the normal scene update path.
        """
        return json.dumps(self.scene_payload(), separators=(",", ":"))
