import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_OPENGL', 'software')

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QFormLayout

from archforge.core.commands import AddEntity, MutateEntityProperty
from archforge.ui.main_window import MainWindow


def _form_spin(window, label_text):
    for row in range(window.form.rowCount()):
        label_item = window.form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        field_item = window.form.itemAt(row, QFormLayout.ItemRole.FieldRole)
        if label_item is None or field_item is None:
            continue
        label = label_item.widget()
        field = field_item.widget()
        if label is not None and label.text() == label_text:
            assert isinstance(field, QDoubleSpinBox)
            return field
    raise AssertionError(f'inspector field not found: {label_text}')


def _drain_geometry(app, window):
    assert window.view_3d.thread_pool.waitForDone(5000)
    for _ in range(6):
        app.processEvents()


def test_wall_toolbar_action_drives_real_3d_click_drag_transaction():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    try:
        window.tabs.setCurrentWidget(window.view_3d)
        app.processEvents()

        before_entities = set(window.doc.entities)
        before_history = len(window.stack.done)

        window.tool_actions['Wall'].trigger()
        app.processEvents()

        assert window.plan_view.controller.tool == 'wall'
        assert window.view_3d.active_tool == 'wall'
        assert window.view_3d.controller.tool == 'wall'

        viewport = window.view_3d.viewport()
        center = viewport.rect().center()
        end = QPoint(center.x() + 140, center.y() + 20)

        QTest.mousePress(
            viewport,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            center,
        )
        app.processEvents()

        assert window.view_3d._wall_drawing is True
        assert window.view_3d.controller.active is not None
        assert window.view_3d._wall_preview_item is not None

        QTest.mouseMove(viewport, end)
        app.processEvents()

        QTest.mouseRelease(
            viewport,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            end,
        )
        _drain_geometry(app, window)

        created = set(window.doc.entities) - before_entities
        assert len(created) == 1
        wall_id = created.pop()
        wall = window.doc.get(wall_id)

        assert wall.kind == 'wall'
        assert len(window.stack.done) == before_history + 1
        assert isinstance(window.stack.done[-1], AddEntity)
        assert window.view_3d._wall_drawing is False
        assert window.view_3d._wall_preview_item is None
        assert window.doc.selection == [wall_id]
        assert (
            (wall.params['x2'] - wall.params['x1']) ** 2
            + (wall.params['y2'] - wall.params['y1']) ** 2
        ) ** 0.5 > 0.0
    finally:
        window.view_3d.thread_pool.waitForDone(5000)
        window.close()
        app.processEvents()


def test_visible_inspector_height_spin_executes_mutation_and_refreshes_3d_geometry():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    try:
        window.tabs.setCurrentWidget(window.view_3d)
        app.processEvents()

        window.tool_actions['Wall'].trigger()
        viewport = window.view_3d.viewport()
        center = viewport.rect().center()
        end = QPoint(center.x() + 150, center.y())

        QTest.mousePress(
            viewport,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            center,
        )
        QTest.mouseMove(viewport, end)
        QTest.mouseRelease(
            viewport,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            end,
        )
        _drain_geometry(app, window)

        wall_id = window.doc.selection[0]
        window.refresh_inspector()
        height_spin = _form_spin(window, 'height')

        before_payload = window.view_3d._mesh_payload_cache[wall_id]
        before_top = max(vertex[2] for vertex in before_payload.vertices)
        before_history = len(window.stack.done)

        height_spin.setValue(3.60)
        _drain_geometry(app, window)

        assert window.doc.get(wall_id).params['height'] == 3.60
        assert len(window.stack.done) == before_history + 1
        mutation = window.stack.done[-1]
        assert isinstance(mutation, MutateEntityProperty)
        assert mutation.eid == wall_id
        assert mutation.property_key == 'height'

        after_payload = window.view_3d._mesh_payload_cache[wall_id]
        after_top = max(vertex[2] for vertex in after_payload.vertices)
        assert after_top > before_top
        assert abs(after_top - 3.60) < 1e-6
    finally:
        window.view_3d.thread_pool.waitForDone(5000)
        window.close()
        app.processEvents()
