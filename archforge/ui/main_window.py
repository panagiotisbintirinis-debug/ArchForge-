from __future__ import annotations

import io
import json
import os
import threading
import wave
from PySide6.QtCore import Qt, QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QDockWidget, QWidget, QFormLayout, QDoubleSpinBox,
    QLabel, QTabWidget, QStatusBar, QFileDialog, QMessageBox, QSplitter,
    QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QCheckBox, QAbstractSpinBox,
)

from archforge.core.model import (
    Document, LAYER_ALL, LAYER_STRUCTURAL,
)
from archforge.core.commands import CommandStack, UpdateEntity, CreateRoomFloors, RouteAndConnectInfrastructure
from .plan_view import PlanView
from .ortho_view import OrthoView
from .viewport_3d import Viewport3D


SYSTEM_PROMPT = """You are the central semantic orchestration agent of ArchForge CAD.
Analyze the user's natural language design request and map it strictly to a structured JSON object.
Use exact entity IDs from the supplied ArchForge document entity catalog.
Do not output markdown code blocks or explanations. Output ONLY raw valid JSON matching this scheme:
{
  "action": "connect_infrastructure",
  "start_id": "string_id",
  "end_id": "string_id",
  "system_type": "hydraulic" | "electrical" | "hvac"
}
"""


OPENAI_COMMAND_SCHEMA = {
    'type': 'object',
    'properties': {
        'action': {
            'type': 'string',
            'enum': ['connect_infrastructure'],
        },
        'start_id': {'type': 'string'},
        'end_id': {'type': 'string'},
        'system_type': {
            'type': 'string',
            'enum': ['hydraulic', 'electrical', 'hvac'],
        },
    },
    'required': ['action', 'start_id', 'end_id', 'system_type'],
    'additionalProperties': False,
}


class OpenAICommandSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class OpenAICommandWorker(QRunnable):
    """Run one natural-language command classification without blocking the Qt UI thread."""

    def __init__(self, user_text, entity_catalog):
        super().__init__()
        self.user_text = str(user_text)
        self.entity_catalog = list(entity_catalog)
        self.signals = OpenAICommandSignals()

    @Slot()
    def run(self):
        try:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise RuntimeError('OPENAI_API_KEY is not configured')

            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            model = os.environ.get('OPENAI_MODEL', 'gpt-5.6-luna')
            context = json.dumps(
                {
                    'user_request': self.user_text,
                    'available_entities': self.entity_catalog,
                },
                ensure_ascii=False,
            )
            response = client.responses.create(
                model=model,
                input=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': context},
                ],
                text={
                    'format': {
                        'type': 'json_schema',
                        'name': 'archforge_command',
                        'strict': True,
                        'schema': OPENAI_COMMAND_SCHEMA,
                    }
                },
            )
            raw = str(response.output_text).strip()
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError('OpenAI command response must be a JSON object')
            self.signals.result.emit(json.dumps(parsed, separators=(',', ':')))
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class VoiceWaveformHUD(QLabel):
    """Small non-interactive recording overlay centered over the CAD workspace."""

    def __init__(self, parent=None):
        super().__init__('●  Recording voice command…', parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(250, 58)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            'QLabel {'
            'background: rgba(20, 24, 30, 210);'
            'color: white;'
            'border: 1px solid rgba(255,255,255,80);'
            'border-radius: 12px;'
            'font-size: 14px;'
            'font-weight: 600;'
            'padding: 8px;'
            '}'
        )
        self.hide()

    def show_centered(self):
        parent = self.parentWidget()
        if parent is not None:
            self.move(
                max(0, (parent.width() - self.width()) // 2),
                max(0, (parent.height() - self.height()) // 2),
            )
        self.show()
        self.raise_()


class VoiceCaptureSignals(QObject):
    audio_ready = Signal(bytes)
    error = Signal(str)
    finished = Signal()


class VoiceCaptureWorker(QRunnable):
    """Open the microphone and collect PCM in a worker thread until stop() is called."""

    def __init__(self, sample_rate=16000, channels=1):
        super().__init__()
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.signals = VoiceCaptureSignals()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    @Slot()
    def run(self):
        chunks = []
        try:
            import sounddevice as sd

            def callback(indata, frames, time_info, status):
                del frames, time_info, status
                chunks.append(indata.copy().tobytes())

            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='int16',
                callback=callback,
            ):
                self._stop_event.wait()

            pcm = b''.join(chunks)
            if not pcm:
                raise RuntimeError('voice recording contained no audio samples')

            output = io.BytesIO()
            with wave.open(output, 'wb') as wav:
                wav.setnchannels(self.channels)
                wav.setsampwidth(2)
                wav.setframerate(self.sample_rate)
                wav.writeframes(pcm)
            self.signals.audio_ready.emit(output.getvalue())
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class OpenAIVoiceCommandSignals(QObject):
    transcript = Signal(str)
    error = Signal(str)
    finished = Signal()


class OpenAIVoiceCommandWorker(QRunnable):
    """Transcribe one in-memory WAV buffer through the OpenAI audio API."""

    def __init__(self, audio_bytes):
        super().__init__()
        self.audio_bytes = bytes(audio_bytes)
        self.signals = OpenAIVoiceCommandSignals()

    @Slot()
    def run(self):
        try:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise RuntimeError('OPENAI_API_KEY is not configured')

            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            audio_file = io.BytesIO(self.audio_bytes)
            audio_file.name = 'archforge-voice-command.wav'
            transcription = client.audio.transcriptions.create(
                model=os.environ.get('OPENAI_TRANSCRIPTION_MODEL', 'whisper-1'),
                file=audio_file,
            )
            transcript = str(transcription.text).strip()
            if not transcript:
                raise ValueError('OpenAI transcription returned empty text')
            self.signals.transcript.emit(transcript)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class IntentConfirmationHUD(QWidget):
    """Human approval gate for transient AI geometry proposals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(390, 96)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            'QWidget {'
            'background: rgba(16, 22, 30, 225);'
            'color: white;'
            'border: 1px solid rgba(0,235,255,150);'
            'border-radius: 12px;'
            '}'
            'QPushButton {'
            'background: rgba(36,48,62,230);'
            'color: white;'
            'padding: 6px 14px;'
            'border-radius: 7px;'
            '}'
        )
        layout = QVBoxLayout(self)
        self.message = QLabel('AI proposal ready — Accept [Y] / Reject [N]')
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.message)
        buttons = QHBoxLayout()
        self.accept_button = QPushButton('Accept [Y]')
        self.reject_button = QPushButton('Reject [N]')
        buttons.addWidget(self.accept_button)
        buttons.addWidget(self.reject_button)
        layout.addLayout(buttons)
        self.hide()

    def show_centered(self):
        parent = self.parentWidget()
        if parent is not None:
            self.move(
                max(0, (parent.width() - self.width()) // 2),
                max(0, (parent.height() - self.height()) // 2),
            )
        self.show()
        self.raise_()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ArchForge Development')
        self.resize(1400, 900)
        self.doc = Document()
        self.stack = CommandStack(self.doc)
        self.current_path = None
        self._ai_workers = set()
        self._voice_workers = set()
        self._voice_capture_worker = None
        self.active_ghost_preview = None
        self._active_ghost_command = None
        self._ghost_selection_snapshot = None
        self.tabs = QTabWidget()
        self.plan_view = PlanView(self.doc, self.stack)
        self.front_view = OrthoView(self.doc, self.stack, 'XZ')
        self.side_view = OrthoView(self.doc, self.stack, 'YZ')
        self.view_3d = Viewport3D(self.doc, self.stack)
        self.tabs.addTab(self.plan_view, 'XY PLAN')
        self.tabs.addTab(self.front_view, 'XZ FRONT')
        self.tabs.addTab(self.side_view, 'YZ SIDE')
        self.tabs.addTab(self.view_3d, '3D PERSPECTIVE')

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(self.tabs)
        self._init_ai_sidebar()
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setSizes([1080, 320])
        self.setCentralWidget(self.main_splitter)
        self.voice_hud = VoiceWaveformHUD(self)
        self.intent_confirmation_hud = IntentConfirmationHUD(self)
        self.intent_confirmation_hud.accept_button.clicked.connect(self.trigger_ui_accept)
        self.intent_confirmation_hud.reject_button.clicked.connect(self.trigger_ui_reject)
        self.view = self.plan_view
        self.setStatusBar(QStatusBar())
        for view in (self.plan_view, self.front_view, self.side_view, self.view_3d):
            view.statusChanged.connect(self.statusBar().showMessage)
            view.selectionChangedByView.connect(self._selection_from_view)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._build_toolbar()
        self._build_inspector()
        self.stack.subscribe(self._redraw_views)
        self.refresh_inspector()

    def _on_tab_changed(self, idx):
        widgets = [self.plan_view, self.front_view, self.side_view, self.view_3d]
        if 0 <= idx < len(widgets):
            self.view = widgets[idx]

    def _set_active_tool(self, tool):
        if hasattr(self.view, 'set_tool'):
            self.view.set_tool(tool)

    def _build_toolbar(self):
        toolbar = QToolBar('Tools')
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, tool, key in [
            ('Select', 'select', 'S'), ('Wall', 'wall', 'W'), ('Door', 'door', 'D'),
            ('Window', 'window', 'N'), ('Move', 'move', 'G'), ('Stretch', 'stretch', 'T'),
            ('Rotate', 'rotate', 'R'),
        ]:
            action = QAction(text, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(lambda checked=False, t=tool: self._set_active_tool(t))
            toolbar.addAction(action)
        sculpt = QAction('Sculpt 3D', self)
        sculpt.setShortcut(QKeySequence('C'))
        sculpt.triggered.connect(lambda: self.view_3d.set_tool('sculpt'))
        toolbar.addAction(sculpt)
        toolbar.addSeparator()
        auto_floors = QAction('Auto Floors', self)
        auto_floors.triggered.connect(self._create_auto_floors)
        toolbar.addAction(auto_floors)
        toolbar.addSeparator()
        self.structural_only_checkbox = QCheckBox('Show Structural Frame Only')
        self.structural_only_checkbox.toggled.connect(self._set_structural_only)
        toolbar.addWidget(self.structural_only_checkbox)
        toolbar.addSeparator()
        undo = QAction('Undo', self)
        undo.setShortcut(QKeySequence.StandardKey.Undo)
        undo.triggered.connect(self._undo)
        toolbar.addAction(undo)
        redo = QAction('Redo', self)
        redo.setShortcut(QKeySequence.StandardKey.Redo)
        redo.triggered.connect(self._redo)
        toolbar.addAction(redo)
        toolbar.addSeparator()
        save = QAction('Save', self)
        save.setShortcut(QKeySequence.StandardKey.Save)
        save.triggered.connect(self.save)
        toolbar.addAction(save)
        open_action = QAction('Open', self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open)
        toolbar.addAction(open_action)
        stl_action = QAction('Export STL', self)
        stl_action.triggered.connect(self.export_stl)
        toolbar.addAction(stl_action)

    def _build_inspector(self):
        self.dock = QDockWidget('Inspector', self)
        self.dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.inspector = QWidget()
        self.form = QFormLayout(self.inspector)
        self.dock.setWidget(self.inspector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)

    def _init_ai_sidebar(self):
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setMinimumWidth(280)
        sidebar_layout = QVBoxLayout(self.sidebar_widget)

        self.ai_chat_log = QTextEdit()
        self.ai_chat_log.setReadOnly(True)
        self.ai_chat_log.setPlaceholderText('ArchForge command history')
        sidebar_layout.addWidget(self.ai_chat_log, 1)

        self.ai_input_line = QLineEdit()
        self.ai_input_line.setPlaceholderText(
            'connect pod_1 to wall_2 hydraulic'
        )
        self.ai_input_line.returnPressed.connect(self._handle_ai_ui_command)
        sidebar_layout.addWidget(self.ai_input_line)

        self.ai_send_button = QPushButton('Run Command')
        self.ai_send_button.clicked.connect(self._handle_ai_ui_command)
        sidebar_layout.addWidget(self.ai_send_button)

        self.main_splitter.addWidget(self.sidebar_widget)

    def _entity_catalog_for_ai(self):
        return [
            {
                'id': entity.id,
                'kind': entity.kind,
                'name': entity.name or '',
            }
            for entity in self.doc.entities.values()
        ]

    def _start_ai_command_worker(self, user_text):
        worker = OpenAICommandWorker(
            user_text,
            self._entity_catalog_for_ai(),
        )
        self._ai_workers.add(worker)
        worker.signals.result.connect(self._execute_parsed_ai_command)
        worker.signals.error.connect(self._handle_ai_worker_error)
        worker.signals.finished.connect(
            lambda active=worker: self._ai_workers.discard(active)
        )
        QThreadPool.globalInstance().start(worker)

    def _handle_ai_ui_command(self):
        user_text = self.ai_input_line.text().strip()
        if not user_text:
            return

        self.ai_input_line.clear()
        self.ai_chat_log.append(f'<b>Human:</b> {user_text}')
        self._start_ai_command_worker(user_text)

    def _text_entry_has_focus(self):
        focus = self.focusWidget()
        return isinstance(
            focus,
            (QLineEdit, QTextEdit, QAbstractSpinBox),
        )

    def _start_voice_capture(self):
        if self._voice_capture_worker is not None:
            return

        worker = VoiceCaptureWorker()
        self._voice_capture_worker = worker
        self._voice_workers.add(worker)
        worker.signals.audio_ready.connect(self._dispatch_voice_audio)
        worker.signals.error.connect(self._handle_voice_worker_error)
        worker.signals.finished.connect(
            lambda active=worker: self._voice_capture_finished(active)
        )
        self.voice_hud.show_centered()
        self.statusBar().showMessage('Recording voice command…')
        QThreadPool.globalInstance().start(worker)

    def _stop_voice_capture(self):
        worker = self._voice_capture_worker
        if worker is None:
            return
        self.voice_hud.hide()
        self.statusBar().showMessage('Transcribing voice command…')
        worker.stop()

    def _voice_capture_finished(self, worker):
        self._voice_workers.discard(worker)
        if self._voice_capture_worker is worker:
            self._voice_capture_worker = None
        self.voice_hud.hide()

    def _dispatch_voice_audio(self, audio_bytes):
        worker = OpenAIVoiceCommandWorker(audio_bytes)
        self._voice_workers.add(worker)
        worker.signals.transcript.connect(self._handle_voice_transcript)
        worker.signals.error.connect(self._handle_voice_worker_error)
        worker.signals.finished.connect(
            lambda active=worker: self._voice_workers.discard(active)
        )
        QThreadPool.globalInstance().start(worker)

    def _handle_voice_transcript(self, transcript):
        text = str(transcript).strip()
        if not text:
            return
        self.ai_chat_log.append(f'<b>Voice:</b> {text}')
        self.statusBar().showMessage('Interpreting voice command…')
        self._start_ai_command_worker(text)

    def _handle_voice_worker_error(self, message):
        self.voice_hud.hide()
        self.ai_chat_log.append(
            f'<b>ArchForge:</b> voice command failed: {message}'
        )
        self.statusBar().showMessage(
            f'Voice command failed: {message}',
            5000,
        )

    def keyPressEvent(self, event):
        if self.active_ghost_preview is not None and not event.isAutoRepeat():
            if event.key() == Qt.Key.Key_Y:
                self.trigger_ui_accept()
                event.accept()
                return
            if event.key() == Qt.Key.Key_N:
                self.trigger_ui_reject()
                event.accept()
                return
        if (
            event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
            and not self._text_entry_has_focus()
        ):
            self._start_voice_capture()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if (
            event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
            and self._voice_capture_worker is not None
        ):
            self._stop_voice_capture()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _handle_ai_worker_error(self, message):
        self.ai_chat_log.append(f'<b>ArchForge:</b> AI request failed: {message}')
        self.statusBar().showMessage(f'AI request failed: {message}', 5000)

    def _set_preview_interaction_locked(self, locked):
        self.plan_view.set_interaction_locked(locked)
        self.front_view.set_interaction_locked(locked)
        self.side_view.set_interaction_locked(locked)
        self.view_3d.set_interaction_locked(locked)

    def _show_ghost_preview(self, path_vertices, diameter):
        self.plan_view.set_ghost_preview(path_vertices, diameter)
        self.view_3d.set_ghost_preview(path_vertices, diameter)
        self._set_preview_interaction_locked(True)
        self.intent_confirmation_hud.show_centered()
        self.setFocus()

    def _clear_active_ghost_preview(self, *, restore_selection=True):
        self.plan_view.clear_ghost_preview()
        self.view_3d.clear_ghost_preview()
        self.front_view.set_interaction_locked(False)
        self.side_view.set_interaction_locked(False)
        self.intent_confirmation_hud.hide()
        self.active_ghost_preview = None
        self._active_ghost_command = None
        if restore_selection and self._ghost_selection_snapshot is not None:
            self.doc.select([
                eid for eid in self._ghost_selection_snapshot
                if eid in self.doc.entities
            ])
        self._ghost_selection_snapshot = None
        self.plan_view.redraw()
        self.front_view.redraw()
        self.side_view.redraw()
        self.view_3d.refresh_selection()

    def _execute_parsed_ai_command(self, json_string):
        try:
            payload = json.loads(str(json_string))
            if not isinstance(payload, dict):
                raise ValueError('AI payload must be a JSON object')
            if payload.get('action') != 'connect_infrastructure':
                raise ValueError('unsupported AI action')

            start_id = payload.get('start_id')
            end_id = payload.get('end_id')
            system_type = payload.get('system_type')
            if not isinstance(start_id, str) or not start_id:
                raise ValueError('AI payload requires start_id')
            if not isinstance(end_id, str) or not end_id:
                raise ValueError('AI payload requires end_id')
            if system_type not in ('hydraulic', 'electrical', 'hvac'):
                raise ValueError('AI payload contains invalid system_type')

            missing = [
                entity_id
                for entity_id in (start_id, end_id)
                if entity_id not in self.doc.entities
            ]
            if missing:
                raise ValueError(
                    'unknown entity id(s): ' + ', '.join(missing)
                )

            from archforge.core.router import (
                MEPPathRouter,
                nominal_diameter_for_system,
            )

            diameter = nominal_diameter_for_system(system_type)
            router = MEPPathRouter(
                self.doc,
                grid_resolution=0.05,
                clearance=max(0.0, diameter / 2.0),
                ignore_entity_ids={start_id, end_id},
            )
            start = router.entity_anchor(start_id)
            end = router.entity_anchor(end_id)
            path_vertices = router.compute_route(start, end)

            if self.active_ghost_preview is not None:
                self._clear_active_ghost_preview(restore_selection=True)

            self._ghost_selection_snapshot = list(self.doc.selection)
            self.active_ghost_preview = [
                tuple(float(value) for value in point)
                for point in path_vertices
            ]
            self._active_ghost_command = {
                'start_id': start_id,
                'end_id': end_id,
                'diameter': diameter,
                'system_type': system_type,
                'grid_resolution': 0.05,
            }
            self._show_ghost_preview(self.active_ghost_preview, diameter)
            self.ai_chat_log.append(
                f'<b>ArchForge:</b> proposal ready for {system_type} '
                f'{start_id} → {end_id}; Accept [Y] / Reject [N]'
            )
            self.statusBar().showMessage(
                'AI proposal ready — press Y to accept or N to reject'
            )
        except Exception as exc:
            self.ai_chat_log.append(f'<b>ArchForge:</b> proposal failed: {exc}')
            self.statusBar().showMessage(f'AI proposal failed: {exc}', 5000)

    def trigger_ui_accept(self):
        if self.active_ghost_preview is None or self._active_ghost_command is None:
            return False

        proposal = dict(self._active_ghost_command)
        cached_route = [
            tuple(float(value) for value in point)
            for point in self.active_ghost_preview
        ]
        command = RouteAndConnectInfrastructure(
            proposal['start_id'],
            proposal['end_id'],
            proposal['diameter'],
            proposal['system_type'],
            grid_resolution=proposal['grid_resolution'],
        )
        command.route = cached_route
        self._clear_active_ghost_preview(restore_selection=True)
        self.stack.execute(command)
        self.ai_chat_log.append(
            f'<b>ArchForge:</b> accepted and committed '
            f'{command.generated_id}'
        )
        self.statusBar().showMessage(
            f'Committed AI proposal {command.generated_id}',
            4000,
        )
        self.refresh_inspector()
        return True

    def trigger_ui_reject(self):
        if self.active_ghost_preview is None:
            return False
        self._clear_active_ghost_preview(restore_selection=True)
        self.ai_chat_log.append(
            '<b>ArchForge:</b> proposal rejected; document unchanged'
        )
        self.statusBar().showMessage('AI proposal rejected', 3000)
        return True

    def _set_structural_only(self, checked):
        self.doc.set_visible_layers_mask(
            LAYER_STRUCTURAL if bool(checked) else LAYER_ALL
        )
        self.doc.selection = [
            eid for eid in self.doc.selection
            if eid in self.doc.entities and self.doc.entity_is_visible(self.doc.entities[eid])
        ]
        self.plan_view.redraw()
        self.front_view.redraw()
        self.side_view.redraw()
        self.view_3d.on_document_modified(None)
        self.refresh_inspector()
        self.statusBar().showMessage(
            'Structural frame isolated' if checked else 'All system layers visible',
            3000,
        )

    def _clear_form(self):
        while self.form.rowCount():
            self.form.removeRow(0)

    def refresh_inspector(self):
        self._clear_form()
        if len(self.doc.selection) != 1:
            self.form.addRow(QLabel(f'{len(self.doc.selection)} selected'))
            return
        eid = self.doc.selection[0]
        entity = self.doc.get(eid)
        self.form.addRow('Type', QLabel(entity.kind))
        self.form.addRow('Name', QLabel(entity.name or entity.kind.title()))
        if entity.parent_id and entity.parent_id in self.doc.entities:
            host = self.doc.get(entity.parent_id)
            self.form.addRow('Host', QLabel(host.name or f'{host.kind.title()} {host.id[:8]}'))
        for key, value in entity.params.items():
            if isinstance(value, (int, float)):
                spin = QDoubleSpinBox()
                spin.setDecimals(4)
                spin.setRange(-1e6, 1e6)
                spin.setValue(float(value))
                spin.setSingleStep(.1)
                spin.editingFinished.connect(
                    lambda property_key=key, widget=spin: self._commit_property(eid, property_key, widget.value())
                )
                self.form.addRow(key, spin)
            elif entity.kind == 'room_floor' and key == 'room_signature':
                self.form.addRow('Room', QLabel(str(value)))

    def _commit_property(self, eid, key, value):
        try:
            self.stack.execute(UpdateEntity(eid, {key: value}))
        except Exception as exc:
            QMessageBox.warning(self, 'Invalid value', str(exc))
            self.refresh_inspector()

    def _create_auto_floors(self):
        faces = self.doc.active_room_faces()
        if not faces:
            self.statusBar().showMessage('No closed rooms on the current work plane', 4000)
            return
        existing = {
            entity.params.get('room_signature')
            for entity in self.doc.entities.values()
            if entity.kind == 'room_floor'
        }
        signatures = [face.signature for face in faces if face.signature not in existing]
        if not signatures:
            self.statusBar().showMessage('All current rooms already have automatic floors', 4000)
            return
        try:
            self.stack.execute(CreateRoomFloors(signatures))
            self.refresh_inspector()
            self.statusBar().showMessage(f'Created {len(signatures)} automatic floor(s)', 4000)
        except Exception as exc:
            QMessageBox.warning(self, 'Auto Floors', str(exc))

    def _selection_from_view(self):
        sender = self.sender()
        if sender is self.view_3d:
            self.view_3d.refresh_selection()
        self.refresh_inspector()

    def _redraw_views(self, modified_ids=None):
        for view in (self.plan_view, self.front_view, self.side_view, self.view_3d):
            if view is self.view_3d:
                view.redraw(force_full=True)
            else:
                view.redraw()

    def _undo(self):
        self.stack.undo()
        self.refresh_inspector()

    def _redo(self):
        self.stack.redo()
        self.refresh_inspector()

    def save(self):
        path = self.current_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, 'Save ArchForge Project', '', 'ArchForge Project (*.archforge)')
        if path:
            if not path.lower().endswith('.archforge'):
                path += '.archforge'
            self.doc.save(path)
            self.current_path = path
            self.statusBar().showMessage(f'Saved {os.path.basename(path)}', 3000)

    def open(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open ArchForge Project', '', 'ArchForge Project (*.archforge)')
        if not path:
            return
        try:
            self.doc = Document.load(path)
            self.stack = CommandStack(self.doc)
            self.plan_view.rebind(self.doc, self.stack)
            self.front_view.rebind(self.doc, self.stack)
            self.side_view.rebind(self.doc, self.stack)
            self.view_3d.rebind(self.doc, self.stack)
            self.stack.subscribe(self._redraw_views)
            self.current_path = path
            self.structural_only_checkbox.blockSignals(True)
            self.structural_only_checkbox.setChecked(
                self.doc.visible_layers_mask == LAYER_STRUCTURAL
            )
            self.structural_only_checkbox.blockSignals(False)
            self.refresh_inspector()
        except Exception as exc:
            QMessageBox.critical(self, 'Open failed', str(exc))

    def export_stl(self):
        from archforge.geometry.fabrication import export_document_stl
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export STL for Fabrication / 3D Printing', '', 'Stereolithography (*.stl)'
        )
        if not path:
            return
        if not path.lower().endswith('.stl'):
            path += '.stl'
        try:
            scope = list(self.doc.selection) if self.doc.selection else None
            count = export_document_stl(self.doc, path, entity_ids=scope, binary=True)
            self.statusBar().showMessage(f'Exported {count} triangles to {os.path.basename(path)}', 4000)
        except Exception as exc:
            QMessageBox.warning(self, 'Fabrication Gate Failed', f'Cannot export STL: {exc}')
