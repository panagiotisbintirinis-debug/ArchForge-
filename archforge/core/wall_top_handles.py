from __future__ import annotations

from typing import Iterable, Optional

from .wall_top_3d import wall_top_endpoint_world


def wall_top_handle_payload(
    doc,
    selection: Iterable[str],
    *,
    preview_endpoint: Optional[str] = None,
    preview_height: Optional[float] = None,
):
    """Build view-only 3D handle descriptors for one selected semantic wall.

    The descriptors are derived from the authoritative wall parameters.  A drag
    preview may replace only the Z coordinate of the active endpoint; it never
    mutates the Document and never changes endpoint XY identity.
    """
    selected = list(selection)
    if len(selected) != 1:
        return []
    entity_id = selected[0]
    if entity_id not in doc.entities:
        return []
    wall = doc.get(entity_id)
    if wall.kind != 'wall':
        return []
    if preview_endpoint is not None and preview_endpoint not in ('start', 'end'):
        raise ValueError("preview_endpoint must be 'start' or 'end'")
    if preview_height is not None and preview_endpoint is None:
        raise ValueError('preview_height requires preview_endpoint')

    handles = []
    base_z = float(wall.params['z'])
    for endpoint in ('start', 'end'):
        x, y, z = wall_top_endpoint_world(wall.params, endpoint)
        preview = endpoint == preview_endpoint and preview_height is not None
        if preview:
            height = float(preview_height)
            if height <= 0.0:
                raise ValueError('wall top preview must remain above base')
            z = base_z + height
        handles.append({
            'entity_id': entity_id,
            'endpoint': endpoint,
            'position': [x, y, z],
            'preview': preview,
        })
    return handles
