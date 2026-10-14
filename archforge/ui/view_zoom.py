"""Wheel zoom about the mouse, shared by the plan, the elevations and the section."""
from PySide6.QtWidgets import QGraphicsView

STEP = 1.15


def zoom_about(view: QGraphicsView, event) -> None:
    """Zoom one wheel notch; the drawing point under the cursor stays under it."""
    pos = event.position().toPoint()
    anchor = view.mapToScene(pos)
    f = STEP if event.angleDelta().y() > 0 else 1 / STEP
    keep = view.transformationAnchor()
    view.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
    view.scale(f, f)
    delta = view.mapToScene(pos) - anchor
    view.translate(delta.x(), delta.y())
    view.setTransformationAnchor(keep)
