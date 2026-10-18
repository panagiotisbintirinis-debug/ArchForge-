"""Wheel zoom about the mouse, shared by the plan, the elevations and the section."""
from PySide6.QtWidgets import QGraphicsView

STEP = 1.15


def zoom_about(view: QGraphicsView, event) -> None:
    """Zoom one wheel notch; the drawing point under the cursor stays under it. Two fingers on a touchpad pan instead,
    in every 2D view (plan, elevations, section) and every workspace."""
    if is_touchpad_scroll(event):
        pan_by(view, event)
        return
    pos = event.position().toPoint()
    anchor = view.mapToScene(pos)
    f = STEP if event.angleDelta().y() > 0 else 1 / STEP
    keep = view.transformationAnchor()
    view.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
    view.scale(f, f)
    delta = view.mapToScene(pos) - anchor
    view.translate(delta.x(), delta.y())
    view.setTransformationAnchor(keep)


def is_touchpad_scroll(event) -> bool:
    """Two fingers on a touchpad (owner 18/10, laptop: «δεν μπορώ να το μετακινήσω»): pixel deltas, a sideways
    component or steps finer than a wheel notch (120). Ctrl + scroll and a pinch still zoom."""
    from PySide6.QtCore import Qt
    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
        return False
    if not event.pixelDelta().isNull():
        return True
    a = event.angleDelta()
    return a.x() != 0 or (a.y() != 0 and a.y() % 120 != 0)


def pan_by(view: QGraphicsView, event) -> None:
    """Move the drawing with the fingers, like the middle-button pan (scroll bars, screen pixels)."""
    d = event.pixelDelta()
    if d.isNull():
        d = event.angleDelta() / 4      # 120 per notch ≈ 30 px
    view.horizontalScrollBar().setValue(view.horizontalScrollBar().value() - round(d.x()))
    view.verticalScrollBar().setValue(view.verticalScrollBar().value() - round(d.y()))
