"""Install persistent plumbing component presentation in technical 2D and PBR 3D."""
from __future__ import annotations


def install() -> None:
    from archforge.ui import pbr_viewport, plumbing_tab

    # Technical plumbing plan only: the normal floor plan intentionally stays
    # pipe-only and uncluttered.
    cls = plumbing_tab.PlumbingTechnicalPlan
    if not getattr(cls, "_archforge_component_visuals_installed", False):
        original_redraw = cls.redraw

        def redraw(self):
            original_redraw(self)
            from archforge.mep.plumbing_component_visuals import plan_primitives
            for primitive in plan_primitives(self.doc):
                self._draw_primitive(primitive)

        cls.redraw = redraw
        cls._archforge_component_visuals_installed = True

    # PBR 3D: explicit accessories remain visible as identifiable MEP objects.
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
