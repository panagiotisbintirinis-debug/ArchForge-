from __future__ import annotations

from typing import Iterable, Mapping, Any


def wall_top_pbr_handles(handles: Iterable[Mapping[str, Any]], *, radius: float = 0.11):
    """Translate semantic wall-top handles into view-only PBR handle descriptors.

    The renderer receives stable semantic identity and a world-space center only.  It
    may draw/pick the descriptor as a sphere, but it must send ``handle_id`` back to
    the interaction adapter rather than deriving wall/endpoint semantics from mesh
    order, screen axes, or tessellation indices.
    """
    radius = float(radius)
    if radius <= 0.0:
        raise ValueError("wall-top PBR handle radius must be > 0")

    rendered = []
    seen = set()
    for handle in handles:
        handle_id = str(handle["handle_id"])
        if not handle_id or handle_id in seen:
            raise ValueError("wall-top PBR handle ids must be unique")
        seen.add(handle_id)

        position = handle["position"]
        if not isinstance(position, (list, tuple)) or len(position) != 3:
            raise ValueError("wall-top PBR handle position must contain three coordinates")

        rendered.append(
            {
                "handle_id": handle_id,
                "center": [float(value) for value in position],
                "radius": radius,
                "preview": bool(handle.get("preview", False)),
                "pickable": True,
            }
        )
    return rendered
