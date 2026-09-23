import copy
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_OPENGL', 'software')

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.ui.viewport_3d import Viewport3D


class _PointerEvent:
    def __init__(self, button, x=100.0, y=100.0, modifiers=Qt.KeyboardModifier.NoModifier):
        self._button = button
        self._pos = QPointF(x, y)
        self._modifiers = modifiers
        self.accepted = False

    def button(self):
        return self._button

    def position(self):
        return QPointF(self._pos)

    def modifiers(self):
        return self._modifiers

    def accept(self):
        self.accepted = True


class _MoveEvent:
    def __init__(self, x, y):
        self._pos = QPointF(x, y)

    def position(self):
        return QPointF(self._pos)


class _AngleDelta:
    def __init__(self, y):
        self._y = int(y)

    def y(self):
        return self._y


class _WheelEvent:
    def __init__(self, angle_delta_y):
        self._delta = _AngleDelta(angle_delta_y)
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
        id='box-1',
    )


def _view():
    app = QApplication.instance() or QApplication([])
    doc = Document()
    doc.add(_box())
    stack = CommandStack(doc)
    view = Viewport3D(doc, stack)
    view.resize(800, 600)
    app.processEvents()
    view.thread_pool.waitForDone(5000)
    app.processEvents()
    return app, doc, stack, view


def test_right_button_orbit_is_navigation_only_and_never_raycast_or_document_mutation():
    app, doc, stack, view = _view()
    try:
        before_doc = copy.deepcopy(doc.to_dict())
        before_done = list(stack.done)
        before_yaw = view.camera.yaw
        before_pitch = view.camera.pitch

        def forbidden_raycast(*args, **kwargs):
            raise AssertionError('right-button navigation must never execute raycast')

        view._execute_raycast_hit_detection = forbidden_raycast

        press = _PointerEvent(Qt.MouseButton.RightButton, 100.0, 100.0)
        view.mousePressEvent(press)
        assert press.accepted
        assert view._is_orbiting
        assert not view._is_panning

        view.mouseMoveEvent(_MoveEvent(140.0, 120.0))

        release = _PointerEvent(Qt.MouseButton.RightButton, 140.0, 120.0)
        view.mouseReleaseEvent(release)
        assert release.accepted
        assert not view._is_orbiting

        assert view.camera.yaw != before_yaw
        assert view.camera.pitch != before_pitch
        assert doc.to_dict() == before_doc
        assert stack.done == before_done
    finally:
        view.thread_pool.waitForDone(5000)
        view.close()
        app.processEvents()


def test_left_button_is_the_only_raycast_entry_point():
    app, doc, stack, view = _view()
    try:
        calls = []

        def record_raycast(pos, modifiers):
            calls.append((pos.x(), pos.y(), modifiers))

        view._execute_raycast_hit_detection = record_raycast

        left = _PointerEvent(Qt.MouseButton.LeftButton, 25.0, 35.0)
        view.mousePressEvent(left)
        assert left.accepted
        assert len(calls) == 1

        right = _PointerEvent(Qt.MouseButton.RightButton, 25.0, 35.0)
        view.mousePressEvent(right)
        assert right.accepted
        assert len(calls) == 1

        middle = _PointerEvent(Qt.MouseButton.MiddleButton, 25.0, 35.0)
        view.mousePressEvent(middle)
        assert middle.accepted
        assert len(calls) == 1
    finally:
        view._is_orbiting = False
        view._is_panning = False
        view.thread_pool.waitForDone(5000)
        view.close()
        app.processEvents()


def test_wheel_zoom_clamps_camera_distance_and_preserves_document_state():
    app, doc, stack, view = _view()
    try:
        before_doc = copy.deepcopy(doc.to_dict())
        before_target = tuple(view.camera.target)
        before_yaw = view.camera.yaw
        before_pitch = view.camera.pitch

        view.camera.distance = 12.0
        event = _WheelEvent(120)
        view.wheelEvent(event)
        assert event.accepted
        assert view.camera.distance == 11.5

        view.wheelEvent(_WheelEvent(120 * 1000))
        assert view.camera.distance == 0.5

        view.wheelEvent(_WheelEvent(-120 * 1000))
        assert view.camera.distance == 50.0

        assert tuple(view.camera.target) == before_target
        assert math.isclose(view.camera.yaw, before_yaw)
        assert math.isclose(view.camera.pitch, before_pitch)
        assert doc.to_dict() == before_doc
        assert stack.done == []
    finally:
        view.thread_pool.waitForDone(5000)
        view.close()
        app.processEvents()


def test_camera_projection_stays_finite_at_zoom_boundaries():
    app, doc, stack, view = _view()
    try:
        for distance in (0.5, 50.0):
            view.camera.distance = distance
            view._update_camera_projection_matrices()
            eye = view.camera.eye_position()
            forward = view.camera.forward_ray()
            assert all(math.isfinite(value) for value in eye)
            assert all(math.isfinite(value) for value in forward)
            assert math.isclose(
                math.sqrt(sum(value * value for value in forward)),
                1.0,
                rel_tol=1e-9,
            )
            projected = view.camera.project((0.0, 0.0, 0.0), 800.0, 600.0)
            assert projected is not None
            assert all(math.isfinite(value) for value in projected)
    finally:
        view.thread_pool.waitForDone(5000)
        view.close()
        app.processEvents()
