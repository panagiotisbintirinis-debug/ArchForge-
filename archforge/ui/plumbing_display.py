"""Plumbing plan presentation.

The plan is deliberately kept visually quiet: only derived cold/hot pipe runs
are shown for plumbing.  Points, manifolds, dimensions, lengths, costs and rule
metadata belong to the separate Plumbing details tab, not to labels over the
drawing.

This module is view-only.  It never changes the Document, engineering rules,
quantities or prices.
"""
from __future__ import annotations


def _pipe_role(role: str) -> bool:
    return role in ("pipe-cold", "pipe-hot")


def apply_display_state(doc, frame):
    """Keep plumbing presentation in the plan to pipe runs only.

    Other non-plumbing primitives remain untouched.  Plumbing point/manifold
    symbols and any legacy plumbing overlay labels are removed from the frame;
    their information is available in the dedicated Plumbing tab.
    """
    del doc  # presentation currently has no per-document switches
    out = []
    for primitive in frame.primitives:
        role = str(getattr(primitive, "role", ""))
        if role in ("plumbing-point", "manifold", "plumbing-overlay-label", "plumbing-label"):
            continue
        out.append(primitive)
    frame.primitives = out
    return frame


def install_plumbing_display(MainWindow):
    """Install once by wrapping the plan-frame presentation only."""
    if getattr(MainWindow, "_archforge_plumbing_display_installed", False):
        return

    import archforge.ui.plan_view as plan_view
    original_build = plan_view.build_plan_frame
    if not getattr(original_build, "_archforge_plumbing_display_wrapper", False):
        def wrapped_build(doc, *args, **kwargs):
            return apply_display_state(doc, original_build(doc, *args, **kwargs))
        wrapped_build._archforge_plumbing_display_wrapper = True
        plan_view.build_plan_frame = wrapped_build

    MainWindow._archforge_plumbing_display_installed = True
