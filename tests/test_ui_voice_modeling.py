import json
import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_OPENGL', 'software')

from PySide6.QtCore import QEvent, Qt, QThreadPool
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from archforge.core.commands import RouteAndConnectInfrastructure
from archforge.core.model import Entity
from archforge.ui.main_window import MainWindow


class _FakeAudioChunk:
    def copy(self):
        return self

    def tobytes(self):
        # 100 ms of mono 16-bit silence at 16 kHz.
        return b'\x00\x00' * 1600


class _FakeInputStream:
    def __init__(self, *, samplerate, channels, dtype, callback):
        assert samplerate == 16000
        assert channels == 1
        assert dtype == 'int16'
        self.callback = callback

    def __enter__(self):
        self.callback(_FakeAudioChunk(), 1600, None, None)
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


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


def _drain_workers(app):
    assert QThreadPool.globalInstance().waitForDone(5000)
    for _ in range(6):
        app.processEvents()


def test_hold_space_voice_command_transcribes_and_executes_native_transaction():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    try:
        window.doc.add(_box('pump', 0.0, 'Αντλία'))
        window.doc.add(_box('panel', 2.0, 'Ηλεκτρικός πίνακας'))
        window.setFocus()
        app.processEvents()

        transcription = SimpleNamespace(
            text='Σύνδεσε την αντλία με τον ηλεκτρικό πίνακα με καλώδιο.'
        )
        structured = SimpleNamespace(
            output_text=json.dumps(
                {
                    'action': 'connect_infrastructure',
                    'start_id': 'pump',
                    'end_id': 'panel',
                    'system_type': 'electrical',
                }
            )
        )

        before_entities = set(window.doc.entities)
        before_done = len(window.stack.done)

        with (
            patch.dict(
                os.environ,
                {
                    'OPENAI_API_KEY': 'test-api-key',
                    'OPENAI_MODEL': 'gpt-5.6-luna',
                    'OPENAI_TRANSCRIPTION_MODEL': 'whisper-1',
                },
                clear=False,
            ),
            patch('sounddevice.InputStream', _FakeInputStream),
            patch('openai.OpenAI') as openai_cls,
        ):
            client = openai_cls.return_value
            client.audio.transcriptions.create.return_value = transcription
            client.responses.create.return_value = structured

            press = QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Space,
                Qt.KeyboardModifier.NoModifier,
            )
            window.keyPressEvent(press)
            assert window._voice_capture_worker is not None
            assert not window.voice_hud.isHidden()

            release = QKeyEvent(
                QEvent.Type.KeyRelease,
                Qt.Key.Key_Space,
                Qt.KeyboardModifier.NoModifier,
            )
            window.keyReleaseEvent(release)
            _drain_workers(app)

            client.audio.transcriptions.create.assert_called_once()
            transcription_call = client.audio.transcriptions.create.call_args
            assert transcription_call.kwargs['model'] == 'whisper-1'
            uploaded = transcription_call.kwargs['file']
            assert uploaded.name.endswith('.wav')
            assert uploaded.getvalue().startswith(b'RIFF')

            client.responses.create.assert_called_once()
            semantic_context = json.loads(
                client.responses.create.call_args.kwargs['input'][1]['content']
            )
            assert semantic_context['user_request'].startswith('Σύνδεσε την αντλία')

        generated_id = 'mep_pump_panel'
        assert set(window.doc.entities) == before_entities | {generated_id}
        assert len(window.stack.done) == before_done + 1
        assert isinstance(window.stack.done[-1], RouteAndConnectInfrastructure)

        pipe = window.doc.get(generated_id)
        assert pipe.kind == 'mesh'
        assert pipe.params['metadata']['system_type'] == 'electrical'
        assert pipe.params['metadata']['routing']['algorithm'] == 'astar-3d'

        log = window.ai_chat_log.toPlainText()
        assert 'Voice:' in log
        assert 'Σύνδεσε την αντλία' in log
        assert 'connected pump to panel as electrical' in log
    finally:
        if window._voice_capture_worker is not None:
            window._voice_capture_worker.stop()
        window.view_3d.thread_pool.waitForDone(5000)
        QThreadPool.globalInstance().waitForDone(5000)
        window.close()
        app.processEvents()


def test_spacebar_does_not_start_voice_capture_while_text_entry_has_focus():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.ai_input_line.setFocus()
        app.processEvents()
        press = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Space,
            Qt.KeyboardModifier.NoModifier,
        )
        window.keyPressEvent(press)

        assert window._voice_capture_worker is None
        assert window.voice_hud.isHidden()
    finally:
        window.close()
        app.processEvents()
