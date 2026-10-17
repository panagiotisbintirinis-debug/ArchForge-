"""Install separate 3D plumbing manifold presentation objects."""
from __future__ import annotations


def install() -> None:
    """Append explicit manifold objects to the normal PBR payload.

    The existing scene builder still owns pipe geometry.  This wrapper only
    adds a separate, identifiable manifold/cabinet presentation object so the
    collector is no longer visually buried inside the pipe mesh.
    """
    from archforge.ui import pbr_viewport

    current = pbr_viewport.build_pbr_scene_payload
    if getattr(current, "_archforge_plumbing_manifold_objects", False):
        return

    def wrapped(evaluation, selected_ids=(), mesh_overrides=None, doc=None):
        payload = current(
            evaluation,
            selected_ids,
            mesh_overrides=mesh_overrides,
            doc=doc,
        )
        if doc is not None:
            from archforge.mep.plumbing_visuals import manifold_scene_objects
            payload.setdefault("objects", []).extend(manifold_scene_objects(doc))
        return payload

    wrapped._archforge_plumbing_manifold_objects = True
    wrapped._archforge_original = current
    pbr_viewport.build_pbr_scene_payload = wrapped
