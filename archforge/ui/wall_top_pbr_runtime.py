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

    def begin_json(self, payload_json: str) -> None:
        """Begin a drag from the renderer-owned handle identity only.

        JavaScript is allowed to return the stable ``handle_id`` attached to the
        picked view mesh, but it does not send entity or endpoint semantics.  Those
        are resolved again from the currently derived handles in Python so stale
        renderer meshes cannot mutate the authoritative model.
        """
        payload = self._object(payload_json)
        handle_id = payload.get("handle_id")
        if not isinstance(handle_id, str) or not handle_id:
            raise ValueError("wall-top PBR begin payload requires handle_id")
        self.begin(handle_id)

    def update_ray(self, origin: Iterable[float], direction: Iterable[float]) -> float:
        return self.web.update_ray(origin, direction)

    def update_ray_json(self, payload_json: str) -> float:
        """Update transient preview from a camera ray supplied by Three.js."""
        payload = self._object(payload_json)
        return self.update_ray(payload.get("origin"), payload.get("direction"))

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

    @staticmethod
    def _object(payload_json: str) -> Mapping[str, Any]:
        payload = json.loads(payload_json)
        if not isinstance(payload, dict):
            raise ValueError("wall-top PBR payload must be an object")
        return payload
