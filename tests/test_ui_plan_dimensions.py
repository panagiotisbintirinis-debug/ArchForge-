import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_OPENGL', 'software')

from PySide6.QtCore import QMimeData, QPointF, Qt
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QFormLayout

from archforge.core.commands import AddEntity
from archforge.core.interaction import VertexMoveTransaction
from archforge.core.model import Entity
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


def _wall():
    return Entity(
        'wall',
        {
            'x1': 0.0,
            'y1': 0.0,
            'z': 0.0,
            'x2': 4.0,
            'y2': 0.0,
            'height': 2.7,
            'thickness': 0.20,
        },
        id='wall-dimension-test',
    )


def _mesh():
    return Entity(
        'mesh',
        {
            'vertices': [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            'faces': [[0, 1, 2, 3]],
            'matrix': [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ],
        },
        id='mesh-dimension-test',
    )


def test_inspector_wall_length_and_thickness_updates_plan_dimensions_immediately():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        wall = _wall()
        window.stack.execute(AddEntity(wall))
        window.doc.select([wall.id])
        window.refresh_inspector()
        window.plan_view.redraw()

        assert '4000 mm' in window.plan_view._dimension_labels
        assert '200 mm' in window.plan_view._dimension_labels

        x2_spin = _form_spin(window, 'x2')
        x2_spin.setValue(5.0)
        x2_spin.editingFinished.emit()
        app.processEvents()

        assert window.doc.get(wall.id).params['x2'] == 5.0
        assert '5000 mm' in window.plan_view._dimension_labels

        thickness_spin = _form_spin(window, 'thickness')
        thickness_spin.setValue(0.25)
        thickness_spin.editingFinished.emit()
        app.processEvents()

        assert window.doc.get(wall.id).params['thickness'] == 0.25
        assert '250 mm' in window.plan_view._dimension_labels
        assert '5000 mm' in window.plan_view._dimension_labels
    finally:
        window.view_3d.thread_pool.waitForDone(5000)
        window.close()
        app.processEvents()


def test_vertex_move_transaction_recalculates_mesh_boundary_dimensions_before_commit():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        mesh = _mesh()
        window.stack.execute(AddEntity(mesh))
        window.doc.select([mesh.id])
        window.plan_view.redraw()
        assert window.plan_view._dimension_labels.count('1000 mm') >= 4

        before = copy.deepcopy(window.doc.get(mesh.id).params['vertices'])
        tx = VertexMoveTransaction(window.stack, mesh.id, 1)
        tx.update_drag(1.0, 0.0, 0.0)
        window.plan_view._vertex_tx = tx
        window.plan_view.redraw()

        assert window.doc.get(mesh.id).params['vertices'] == before
        assert '2000 mm' in window.plan_view._dimension_labels
        assert any(
            record[0] == mesh.id and record[2] == '2000 mm'
            for record in window.plan_view._dimension_records
        )

        tx.cancel()
        window.plan_view._vertex_tx = None
        window.plan_view.redraw()
        assert '2000 mm' not in window.plan_view._dimension_labels
    finally:
        window.view_3d.thread_pool.waitForDone(5000)
        window.close()
        app.processEvents()


class _DropEvent:
    def __init__(self, key, x=250.0, y=250.0):
        self._mime = QMimeData()
        self._mime.setData(
            'application/x-archforge-catalog-item',
            key.encode('utf-8'),
        )
        self._position = QPointF(x, y)
        self.accepted = False

    def mimeData(self):
        return self._mime

    def position(self):
        return QPointF(self._position)

    def acceptProposedAction(self):
        self.accepted = True


def test_library_browser_drop_creates_component_through_command_stack():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        labels = [
            window.inspector_tabs.tabText(index)
            for index in range(window.inspector_tabs.count())
        ]
        assert labels == ['Inspector', 'Library Browser']
        assert window.library_browser.topLevelItem(0).text(0) == (
            'Core Catalogs (Pods, Walls, Framing)'
        )
        assert window.library_browser.topLevelItem(1).text(0) == (
            'Manufacturer Catalogs (MEP Profiles)'
        )
        assert window.library_browser.topLevelItem(2).text(0) == 'User Catalog'

        before_entities = set(window.doc.entities)
        before_history = len(window.stack.done)

        event = _DropEvent('core:wall')
        window.plan_view.dropEvent(event)
        app.processEvents()

        assert event.accepted
        assert len(window.doc.entities) == len(before_entities) + 1
        assert len(window.stack.done) == before_history + 1

        created_ids = set(window.doc.entities) - before_entities
        assert len(created_ids) == 1
        wall = window.doc.get(created_ids.pop())
        assert wall.kind == 'wall'
        assert wall.name == 'Catalog Wall'
        assert abs((wall.params['x2'] - wall.params['x1']) - 2.0) < 1e-9
        assert window.doc.selection == [wall.id]
    finally:
        window.view_3d.thread_pool.waitForDone(5000)
        window.close()
        app.processEvents()
