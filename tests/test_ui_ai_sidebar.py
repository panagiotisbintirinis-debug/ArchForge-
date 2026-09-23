import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_OPENGL', 'software')

from PySide6.QtWidgets import QApplication

from archforge.core.commands import RouteAndConnectInfrastructure
from archforge.core.model import Entity
from archforge.ui.main_window import MainWindow


def _box(entity_id, x):
    return Entity(
        'box',
        {
            'x': x,
            'y': 0.0,
            'z': 0.0,
            'width': 0.30,
            'depth': 0.30,
            'height': 1.0,
            'rotation': 0.0,
        },
        id=entity_id,
    )


def test_ai_sidebar_input_executes_routed_mesh_command():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.doc.add(_box('source', 0.0))
        window.doc.add(_box('sink', 2.0))

        assert window.sidebar_widget is not None
        assert window.ai_chat_log.isReadOnly()
        assert window.ai_input_line.placeholderText()
        assert window.main_splitter.indexOf(window.sidebar_widget) >= 0

        before_done = len(window.stack.done)
        window.ai_input_line.setText('connect source to sink electrical')
        window.ai_input_line.returnPressed.emit()

        generated_id = 'mep_source_sink'
        assert generated_id in window.doc.entities
        pipe = window.doc.get(generated_id)
        assert pipe.kind == 'mesh'
        assert pipe.params['vertices']
        assert pipe.params['faces']
        assert pipe.params['metadata']['semantic_type'] == 'conduit'
        assert pipe.params['metadata']['system_type'] == 'electrical'
        assert pipe.params['metadata']['diameter'] == 0.020
        assert pipe.params['metadata']['routing']['algorithm'] == 'astar-3d'

        assert len(window.stack.done) == before_done + 1
        assert isinstance(window.stack.done[-1], RouteAndConnectInfrastructure)
        assert window.ai_input_line.text() == ''

        log = window.ai_chat_log.toPlainText()
        assert 'Human: connect source to sink electrical' in log
        assert 'ArchForge: connected source to sink as electrical' in log
    finally:
        window.view_3d.thread_pool.waitForDone(5000)
        window.close()
        app.processEvents()
