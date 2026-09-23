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
    for _ in range(4):
        app.processEvents()


def test_ai_sidebar_free_form_language_uses_openai_json_and_executes_command_stack():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.doc.add(_box('source', 0.0, 'Pump cabinet'))
        window.doc.add(_box('sink', 2.0, 'Distribution cabinet'))

        assert window.sidebar_widget is not None
        assert window.ai_chat_log.isReadOnly()
        assert window.main_splitter.indexOf(window.sidebar_widget) >= 0

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
            assert window.ai_input_line.text() == ''

            _drain_ai_worker(app)

            openai_cls.assert_called_once_with(api_key='test-api-key')
            create_call = openai_cls.return_value.responses.create.call_args
            assert create_call.kwargs['model'] == 'gpt-5.6-luna'
            assert create_call.kwargs['text']['format']['type'] == 'json_schema'
            assert create_call.kwargs['text']['format']['strict'] is True
            assert (
                create_call.kwargs['text']['format']['schema']['additionalProperties']
                is False
            )
            request_context = json.loads(create_call.kwargs['input'][1]['content'])
            assert request_context['user_request'].startswith('Please run power')
            catalog_ids = {
                entity['id']
                for entity in request_context['available_entities']
            }
            assert {'source', 'sink'} <= catalog_ids

        generated_id = 'mep_source_sink'
        assert set(window.doc.entities) == before_entities | {generated_id}
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

        log = window.ai_chat_log.toPlainText()
        assert 'Please run power from the pump cabinet' in log
        assert 'connected source to sink as electrical' in log
    finally:
        window.view_3d.thread_pool.waitForDone(5000)
        QThreadPool.globalInstance().waitForDone(5000)
        window.close()
        app.processEvents()


def test_ai_sidebar_rejects_bad_model_entity_ids_without_state_leakage():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.doc.add(_box('source', 0.0, 'Pump cabinet'))
        window.doc.add(_box('sink', 2.0, 'Distribution cabinet'))

        fake_response = SimpleNamespace(
            output_text=json.dumps(
                {
                    'action': 'connect_infrastructure',
                    'start_id': 'source',
                    'end_id': 'hallucinated-target',
                    'system_type': 'hydraulic',
                }
            )
        )
        before_entities = set(window.doc.entities)
        before_done = len(window.stack.done)

        with (
            patch.dict(os.environ, {'OPENAI_API_KEY': 'test-api-key'}, clear=False),
            patch('openai.OpenAI') as openai_cls,
        ):
            openai_cls.return_value.responses.create.return_value = fake_response
            window.ai_input_line.setText(
                'Connect the pump cabinet to the target with water.'
            )
            window._handle_ai_ui_command()
            _drain_ai_worker(app)

        assert set(window.doc.entities) == before_entities
        assert len(window.stack.done) == before_done
        assert 'unknown entity id(s): hallucinated-target' in window.ai_chat_log.toPlainText()
    finally:
        window.view_3d.thread_pool.waitForDone(5000)
        QThreadPool.globalInstance().waitForDone(5000)
        window.close()
        app.processEvents()
