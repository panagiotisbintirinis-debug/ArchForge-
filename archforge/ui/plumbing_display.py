"""Plumbing plan display controls.

View-only presentation.  No engineering rule, quantity, price or model entity is
changed here.  The plumbing network stays authoritative in mep.plumbing; this
module only decides what the plan shows and which optional labels are visible.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class PlumbingDisplayState:
    show_network: bool = True
    show_points: bool = True
    show_manifolds: bool = True
    show_diameters: bool = False
    show_lengths: bool = False


_STATES: dict[int, PlumbingDisplayState] = {}


def state_for(doc) -> PlumbingDisplayState:
    return _STATES.setdefault(id(doc), PlumbingDisplayState())


def _pipe_role(role: str) -> bool:
    return role in ("pipe-cold", "pipe-hot")


def _length(points) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def _midpoint(points):
    if len(points) < 2:
        return points[0] if points else (0.0, 0.0)
    total = _length(points)
    if total <= 1e-12:
        a, b = points[0], points[-1]
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    target = total / 2.0
    walked = 0.0
    for a, b in zip(points, points[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if walked + seg >= target and seg > 1e-12:
            t = (target - walked) / seg
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        walked += seg
    return points[-1]


def pipe_label(primitive, state: PlumbingDisplayState) -> str:
    """Optional compact label.  Empty string means keep the drawing clean."""
    if not _pipe_role(str(getattr(primitive, "role", ""))):
        return ""
    parts = []
    meta = dict(getattr(primitive, "meta", ()) or ())
    if state.show_diameters and meta.get("diameter") is not None:
        parts.append(f"Ø{meta['diameter']}")
    if state.show_lengths:
        metres = _length(getattr(primitive, "points", ()) or ())
        parts.append((f"{metres:.2f} m").replace(".", ","))
    return " · ".join(parts)


def apply_display_state(doc, frame):
    """Filter plumbing primitives and add only user-requested compact labels."""
    from archforge.core.plan_scene import Primitive2D

    state = state_for(doc)
    out = []
    labels = []
    for primitive in frame.primitives:
        role = str(getattr(primitive, "role", ""))
        if _pipe_role(role):
            if not state.show_network:
                continue
            out.append(primitive)
            text = pipe_label(primitive, state)
            if text:
                labels.append(
                    Primitive2D(
                        "label",
                        (_midpoint(primitive.points),),
                        role="plumbing-overlay-label",
                        meta=(("text", text), ("min_scale", 18.0)),
                    )
                )
            continue
        if role == "plumbing-point" and not state.show_points:
            continue
        if role == "manifold" and not state.show_manifolds:
            continue
        out.append(primitive)
    frame.primitives = out + labels
    return frame


def _redraw(window):
    try:
        from archforge.ui.plan_view import PlanView
        for view in window.findChildren(PlanView):
            view.redraw()
    except Exception:
        if hasattr(window, "_redraw_views"):
            window._redraw_views(all_views=True)


def _set(window, field: str, value: bool):
    setattr(state_for(window.doc), field, bool(value))
    _redraw(window)


def _install_menu(window):
    menu = getattr(window, "_mockup_plumbing_menu", None)
    if menu is None:
        return
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenu

    menu.addSeparator()
    display = QMenu("Εμφάνιση", menu)
    menu.addMenu(display)
    state = state_for(window.doc)
    rows = (
        ("Δίκτυο σωληνώσεων", "show_network"),
        ("Σημεία", "show_points"),
        ("Συλλέκτες", "show_manifolds"),
        ("Διάμετροι", "show_diameters"),
        ("Μήκη", "show_lengths"),
    )
    actions = {}
    for label, field in rows:
        action = QAction(label, display)
        action.setCheckable(True)
        action.setChecked(bool(getattr(state, field)))
        action.toggled.connect(lambda on, f=field: _set(window, f, on))
        display.addAction(action)
        actions[field] = action
    actions["show_diameters"].setToolTip("Κλειστό από προεπιλογή για καθαρή κάτοψη")
    actions["show_lengths"].setToolTip("Κλειστό από προεπιλογή για καθαρή κάτοψη")
    window._plumbing_display_menu = display
    window._plumbing_display_actions = actions


def install_plumbing_display(MainWindow):
    """Install once: wrap plan-frame presentation and add plumbing display toggles."""
    if getattr(MainWindow, "_archforge_plumbing_display_installed", False):
        return

    import archforge.ui.plan_view as plan_view
    original_build = plan_view.build_plan_frame
    if not getattr(original_build, "_archforge_plumbing_display_wrapper", False):
        def wrapped_build(doc, *args, **kwargs):
            return apply_display_state(doc, original_build(doc, *args, **kwargs))
        wrapped_build._archforge_plumbing_display_wrapper = True
        plan_view.build_plan_frame = wrapped_build

    original_init = MainWindow.__init__
    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _install_menu(self)
    MainWindow.__init__ = wrapped_init
    MainWindow._archforge_plumbing_display_installed = True
