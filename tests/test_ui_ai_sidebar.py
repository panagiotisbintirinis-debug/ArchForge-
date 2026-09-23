import json
import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_OPENGL', 'software')

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from archforge.core.commands import RouteAndConnectInfrastructure
from archforge.core.model import Entity
from archforge.ui.main_window import MainWindow


def _box(entity_id, x, name):
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
        name=name,
    )


def _drain_ai_worker(app):
    assert QThreadPool.globalInstance().waitForDone(5000)
    for _ in range(6):
        app.processEvents()


def test_ai_sidebar_creates_ghost_before_explicit_human_acceptance():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.doc.add(_box('source', 0.0, 'Pump cabinet'))
        window.doc.add(_box('sink', 2.0, 'Distribution cabinet'))

        response_payload = {
            'action': 'connect_infrastructure',
            'start_id': 'source',
            'end_id': 'sink',
            'system_type': 'electrical',
        }
        fake_response = SimpleNamespace(output_text=json.dumps(response_payload))
        before_entities = set(window.doc.entities)
        before_done = len(window.stack.done)

        with (
            patch.dict(
                os.environ,
                {
                    'OPENAI_API_KEY': 'test-api-key',
                    'OPENAI_MODEL': 'gpt-5.6-luna',
                },
                clear=False,
            ),
            patch('openai.OpenAI') as openai_cls,
        ):
            openai_cls.return_value.responses.create.return_value = fake_response
            window.ai_input_line.setText(
                'Please run power from the pump cabinet over to the distribution cabinet.'
            )
            window.ai_input_line.returnPressed.emit()
            _drain_ai_worker(app)

        assert set(window.doc.entities) == before_entities
        assert len(window.stack.done) == before_done
        assert window.active_ghost_preview is not None
        assert len(window.active_ghost_preview) >= 2
        assert window._active_ghost_command['system_type'] == 'electrical'
        assert not window.intent_confirmation_hud.isHidden()
        assert window.plan_view._ghost_faces
        assert window.view_3d._ghost_mesh is not None

        assert window.trigger_ui_accept() is True

        generated_id = 'mep_source_sink'
        assert set(window.doc.entities) == before_entities | {generated_id}
        assert len(window.stack.done) == before_done + 1
        assert isinstance(window.stack.done[-1], RouteAndConnectInfrastructure)
        assert window.active_ghost_preview is None
        assert window.view_3d._ghost_mesh is None
        assert window.plan_view._ghost_faces == ()

        pipe = window.doc.get(generated_id)
        assert pipe.kind == 'mesh'
        assert pipe.params['metadata']['system_type'] == 'electrical'
        assert pipe.params['metadata']['routing']['algorithm'] == 'astar-3d'
    finally:
        window.view_3d.thread_pool.waitForDone(5000)
        QThreadPool.globalInstance().waitForDone(5000)
        window.close()
        app.processEvents()


def test_ai_sidebar_reject_clears_ghost_without_document_or_history_mutation():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.doc.add(_box('source', 0.0, 'Pump cabinet'))
        window.doc.add(_box('sink', 2.0, 'Distribution cabinet'))
        before_entities = set(window.doc.entities)
        before_done = len(window.stack.done)

        window._execute_parsed_ai_command(json.dumps({
            'action': 'connect_infrastructure',
            'start_id': 'source',
            'end_id': 'sink',
            'system_type': 'hydraulic',
        }))

        assert window.active_ghost_preview is not None
        assert set(window.doc.entities) == before_entities
        assert len(window.stack.done) == before_done

        assert window.trigger_ui_reject() is True
        assert window.active_ghost_preview is None
        assert set(window.doc.entities) == before_entities
        assert len(window.stack.done) == before_done
        assert 'proposal rejected; document unchanged' in window.ai_chat_log.toPlainText()
    finally:
        window.close()
        app.processEvents()


def test_ai_sidebar_rejects_bad_model_entity_ids_without_state_leakage():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.doc.add(_box('source', 0.0, 'Pump cabinet'))
        window.doc.add(_box('sink', 2.0, 'Distribution cabinet'))
        before_entities = set(window.doc.entities)
        before_done = len(window.stack.done)

        window._execute_parsed_ai_command(json.dumps({
            'action': 'connect_infrastructure',
            'start_id': 'source',
            'end_id': 'hallucinated-target',
            'system_type': 'hydraulic',
        }))

        assert set(window.doc.entities) == before_entities
        assert len(window.stack.done) == before_done
        assert window.active_ghost_preview is None
        assert 'unknown entity id(s): hallucinated-target' in window.ai_chat_log.toPlainText()
    finally:
        window.close()
        app.processEvents()
