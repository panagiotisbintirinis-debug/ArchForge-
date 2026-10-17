"""Install persistent 2D/3D presentation for explicit plumbing components."""
from __future__ import annotations


def install() -> None:
    from archforge.ui import plan_view, pbr_viewport

    current_plan = plan_view.build_plan_frame
    if not getattr(current_plan, "_archforge_plumbing_component_visuals", False):
        def wrapped_plan(doc, preview=None, layers=True):
            frame = current_plan(doc, preview, layers=layers)
            from archforge.mep.plumbing_component_visuals import plan_primitives
            frame.primitives.extend(plan_primitives(doc))
            return frame
        wrapped_plan._archforge_plumbing_component_visuals = True
        wrapped_plan._archforge_original = current_plan
        plan_view.build_plan_frame = wrapped_plan

    current_pbr = pbr_viewport.build_pbr_scene_payload
    if not getattr(current_pbr, "_archforge_plumbing_component_visuals", False):
        def wrapped_pbr(evaluation, selected_ids=(), mesh_overrides=None, doc=None):
            payload = current_pbr(evaluation, selected_ids, mesh_overrides=mesh_overrides, doc=doc)
            if doc is not None:
                from archforge.mep.plumbing_component_visuals import scene_objects
                payload.setdefault("objects", []).extend(scene_objects(doc))
            return payload
        wrapped_pbr._archforge_plumbing_component_visuals = True
        wrapped_pbr._archforge_original = current_pbr
        pbr_viewport.build_pbr_scene_payload = wrapped_pbr
