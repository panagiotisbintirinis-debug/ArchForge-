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

    @property
    def active(self) -> bool:
        """Whether a transient wall-top pointer transaction is currently active."""
        return self.controller.active

    def rebind(self, doc, stack) -> None:
        self.controller.rebind(doc, stack)

    def handles(self):
        """Return view-only semantic handles for direct renderer consumption.

        The WebGL viewport can use this typed payload when it already owns the Python
        object, while ``handles_json`` remains the serialization boundary used by JS.
        Neither form creates or mutates authoritative design state.
        """
        return self.controller.handles()

    def handles_json(self) -> str:
        return json.dumps(self.handles(), separators=(",", ":"))

    def begin_handle(self, handle_id: str) -> None:
        """Begin from the stable renderer identity attached to a picked handle mesh.

        The renderer does not get to invent entity/endpoint semantics. A handle id is
        accepted only when present in the currently derived handle payload; this also
        rejects stale meshes after selection or model changes.
        """
        handle_id = str(handle_id)
        handle = next((item for item in self.handles() if item["handle_id"] == handle_id), None)
        if handle is None:
            raise ValueError("wall-top handle is stale or not currently selectable")
        self.controller.begin(str(handle["entity_id"]), str(handle["endpoint"]))

    def begin_json(self, payload_json: str) -> None:
        payload = self._object(payload_json)
        self.controller.begin(str(payload["entity_id"]), str(payload["endpoint"]))

    def update_ray(self, origin, direction) -> float:
        """Update the transient preview from a typed camera ray.

        The live Qt/WebGL bridge can validate JSON once at its boundary and then call
        this method directly.  Keeping the controller API typed avoids a second JSON
        round-trip inside Python while preserving the same semantic transaction.
        """
        return self.controller.update_from_ray(
            self._vec3(origin, "origin"),
            self._vec3(direction, "direction"),
        )

    def update_ray_json(self, payload_json: str) -> float:
        payload = self._object(payload_json)
        return self.update_ray(payload.get("origin"), payload.get("direction"))

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
