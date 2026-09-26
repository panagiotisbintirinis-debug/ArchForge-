import copy
import math
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.ui.main_window import MainWindow
from archforge.ui.viewport_3d import Viewport3D


class _PointerEvent:
    def __init__(self, button, x=120.0, y=120.0):
        self._button = button
        self._pos = QPointF(x, y)
        self.accepted = False

    def button(self):
        return self._button

    def position(self):
        return QPointF(self._pos)

    def modifiers(self):
        return Qt.KeyboardModifier.NoModifier

    def accept(self):
        self.accepted = True


class _MoveEvent:
    def __init__(self, x, y):
        self._pos = QPointF(x, y)

    def position(self):
        return QPointF(self._pos)


class _Delta:
    def __init__(self, y):
        self._y = y

    def y(self):
        return self._y


class _WheelEvent:
    def __init__(self, y):
        self._delta = _Delta(y)
        self.accepted = False

    def angleDelta(self):
        return self._delta

    def accept(self):
        self.accepted = True


def _box():
    return Entity(
        'box',
        {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0,
            'width': 1.0,
            'depth': 1.0,
            'height': 1.0,
            'rotation': 0.0,
        },
        id='recovery-box',
    )


def test_recovery_launcher_exists_and_main_window_constructs():
    assert Path('run_app.py').read_text(encoding='utf-8').startswith(
        'from archforge.ui.app import main'
    )
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.tabs.count() == 5
        assert window.tabs.tabText(0) == 'FLOOR PLAN'
        assert window.tabs.tabText(1) == 'FRONT ELEVATION'
        assert window.tabs.tabText(2) == 'SIDE ELEVATION'
        assert window.tabs.tabText(3) == '3D EDIT'
        assert window.tabs.tabText(4) == '3D STUDIO'
        assert window.axes_action.isCheckable()
        assert window.cutaway_action.isCheckable()
        assert window.auto_rotate_action.isCheckable()
    finally:
        window.close()
        app.processEvents()


def test_viewport_contains_no_temporary_bounding_box_substitution():
    source = Path('archforge/ui/viewport_3d.py').read_text(encoding='utf-8')
    for token in (
        '_update_interaction_proxies',
        '_begin_interaction',
        '_finish_deferred_view_change',
        'proxy_items',
        'ensure_proxy_items',
        '_bbox_corners',
        'EntityRenderProxy',
    ):
        assert token not in source


def test_right_drag_orbits_and_wheel_zooms_without_document_mutation():
    app = QApplication.instance() or QApplication([])
    doc = Document()
    doc.add(_box())
    stack = CommandStack(doc)
    view = Viewport3D(doc, stack)
    view.resize(800, 600)
    try:
        before = copy.deepcopy(doc.to_dict())
        yaw = view.camera.yaw
        pitch = view.camera.pitch

        press = _PointerEvent(Qt.MouseButton.RightButton, 100.0, 100.0)
        view.mousePressEvent(press)
        assert press.accepted
        assert view._is_orbiting

        view.mouseMoveEvent(_MoveEvent(150.0, 125.0))
        release = _PointerEvent(Qt.MouseButton.RightButton, 150.0, 125.0)
        view.mouseReleaseEvent(release)

        assert release.accepted
        assert not view._is_orbiting
        assert view.camera.yaw != yaw
        assert view.camera.pitch != pitch
        assert doc.to_dict() == before
        assert stack.done == []

        view.camera.distance = 12.0
        wheel = _WheelEvent(120)
        view.wheelEvent(wheel)
        assert wheel.accepted
        assert math.isclose(view.camera.distance, 11.5)

        view.wheelEvent(_WheelEvent(120 * 1000))
        assert view.camera.distance == 0.5
        view.wheelEvent(_WheelEvent(-120 * 1000))
        assert view.camera.distance == 50.0

        assert doc.to_dict() == before
        assert stack.done == []
    finally:
        view.close()
        app.processEvents()


def test_real_viewport_event_filter_captures_right_drag_orbit():
    app = QApplication.instance() or QApplication([])
    doc = Document()
    doc.add(_box())
    stack = CommandStack(doc)
    view = Viewport3D(doc, stack)
    view.resize(800, 600)
    view.show()
    app.processEvents()
    try:
        before_yaw = view.camera.yaw
        before_pitch = view.camera.pitch

        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(100.0, 100.0),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(160.0, 135.0),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(160.0, 135.0),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

        assert QApplication.sendEvent(view.viewport(), press)
        assert view._is_orbiting

        QApplication.sendEvent(view.viewport(), move)
        app.processEvents()

        assert view.camera.yaw != before_yaw
        assert view.camera.pitch != before_pitch

        assert QApplication.sendEvent(view.viewport(), release)
        assert not view._is_orbiting
    finally:
        view.close()
        app.processEvents()


def test_solid_surface_renderer_hides_internal_triangle_edges():
    app = QApplication.instance() or QApplication([])
    doc = Document()
    doc.add(_box())
    stack = CommandStack(doc)
    view = Viewport3D(doc, stack)
    view.resize(800, 600)
    view.show()
    app.processEvents()
    try:
        view.redraw(force_full=True)
        items = view._render_cache['recovery-box']
        assert items.mesh_items

        for item in items.mesh_items:
            assert item.pen().color() == item.brush().color()
            assert item.pen().widthF() == 0.0
            assert item.brush().color().alpha() == 255

        doc.select(['recovery-box'])
        view.refresh_selection()
        for item in items.mesh_items:
            assert item.pen().color() == item.brush().color()
            assert item.pen().widthF() == 0.0
            assert item.brush().color().alpha() == 255
    finally:
        view.close()
        app.processEvents()
