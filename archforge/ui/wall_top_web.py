from __future__ import annotations

import json
from typing import Any, Mapping

from .wall_top_3d_controller import WallTop3DController


class WallTopWebInteraction:
    """Thin WebGL adapter for semantic wall-top direct manipulation.

    This object deliberately owns no design state.  It converts JSON payloads from the
    WebGL view into calls on ``WallTop3DController``; previews remain transient and the
    eventual commit still flows through CommandStack -> Document.
    """

    def __init__(self, doc, stack):
        self.controller = WallTop3DController(doc, stack)

    def rebind(self, doc, stack) -> None:
        self.controller.rebind(doc, stack)

    def handles_json(self) -> str:
        return json.dumps(self.controller.handles(), separators=(",", ":"))

    def begin_json(self, payload_json: str) -> None:
        payload = self._object(payload_json)
        self.controller.begin(str(payload["entity_id"]), str(payload["endpoint"]))

    def update_ray_json(self, payload_json: str) -> float:
        payload = self._object(payload_json)
        origin = self._vec3(payload.get("origin"), "origin")
        direction = self._vec3(payload.get("direction"), "direction")
        return self.controller.update_from_ray(origin, direction)

    def finish(self) -> bool:
        return self.controller.finish()

    def cancel(self) -> None:
        self.controller.cancel()

    @staticmethod
    def _object(payload_json: str) -> Mapping[str, Any]:
        payload = json.loads(payload_json)
        if not isinstance(payload, dict):
            raise ValueError("wall-top WebGL payload must be an object")
        return payload

    @staticmethod
    def _vec3(value: Any, name: str):
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise ValueError(f"{name} must contain three coordinates")
        return tuple(float(component) for component in value)
