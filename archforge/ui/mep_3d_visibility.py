"""Resolve legacy 3D MEP visibility against the authoritative Layers workspace.

ArchForge historically kept a ``PBRViewport.hidden_layers`` set for derived
MEP meshes (``mep``, ``drain``, ``elec``, ``vent``).  The newer Layers system
in ``core.layers`` is now the authoritative view state.  Keeping both active
can make an H/M layer look enabled in the UI while the old hidden set silently
removes the same mesh from the PBR payload.

This compatibility shim removes only that conflict.  Explicit visibility in
the current Layers workspace is still applied later by ``apply_to_scene_objects``.
No model, routing or quantity state is changed.
"""
from __future__ import annotations

LEGACY_MEP_LAYERS = frozenset({"mep", "drain", "elec", "vent"})


def effective_hidden_layers(doc, hidden):
    """Return legacy hidden layers that are still allowed to affect PBR.

    Once the new Layers system is active, it alone owns MEP visibility.  Other
    unrelated legacy hidden entries are preserved for compatibility.
    """
    current = set(hidden or ())
    from archforge.core.layers import layers_active
    if layers_active(doc):
        current.difference_update(LEGACY_MEP_LAYERS)
    return current


def install(PBRViewport):
    if getattr(PBRViewport, "_archforge_mep_visibility_resolved", False):
        return
    original_redraw = PBRViewport.redraw

    def wrapped_redraw(self, force_full=False):
        before = set(getattr(self, "hidden_layers", set()) or ())
        resolved = effective_hidden_layers(self.doc, before)
        self.hidden_layers = resolved
        try:
            return original_redraw(self, force_full=force_full)
        finally:
            # Do not erase legacy UI state; only prevent it from overriding the
            # authoritative Layers system while a frame is being rendered.
            self.hidden_layers = before

    PBRViewport.redraw = wrapped_redraw
    PBRViewport._archforge_mep_visibility_resolved = True
