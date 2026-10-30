"""Ollama in the existing assistant panel; networking never runs on the GUI thread."""
from __future__ import annotations

import logging
import os
from dataclasses import asdict

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot, Qt

from archforge.orchestration.ollama import OllamaClient, OllamaError, ProjectAssistant, ProjectContext


class _Signals(QObject):
    finished = Signal(object, str)


class _Question(QRunnable):
    def __init__(self, context, question, history, model=None):
        super().__init__()
        self.context, self.question, self.history = context, question, history
        self.model = model
        self.signals = _Signals()

    def run(self):
        try:
            answer = ProjectAssistant(OllamaClient(model=self.model)).ask(self.context, self.question, self.history)
            self.signals.finished.emit(answer, '')
        except OllamaError as exc:
            self.signals.finished.emit(None, str(exc))
        except Exception:
            logging.getLogger(__name__).exception('Ollama assistant request failed')
            self.signals.finished.emit(None, 'Ο βοηθός απέτυχε. Η αιτία καταγράφηκε στο log· δεν εφαρμόστηκε αλλαγή.')


class Controller(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.pending = None
        self.history = []
        self.history_stamp = None
        self._job = None
        self._document = None

    def start(self, text):
        window = self.window
        window.assistant_reply.setTextFormat(Qt.TextFormat.PlainText)
        if self._job is not None:
            window.assistant_reply.setText('Το Ollama εξετάζει ήδη την προηγούμενη ερώτηση. Περίμενε την απάντηση.')
            return
        if text.strip() == '/νέα':
            self.history.clear(); self.pending = None
            window.assistant_text.clear()
            window.assistant_reply.setText('Νέα συνομιλία Ollama. Το έργο δεν άλλαξε.')
            window._refresh_assistant()
            return
        try:
            target = getattr(window, '_assistant_target', None)
            context = ProjectContext(window.doc, asdict(target) if target is not None else None)
        except Exception:
            logging.getLogger(__name__).exception('Cannot capture Ollama project snapshot')
            window.assistant_reply.setText('Δεν μπόρεσα να διαβάσω το έργο. Η αιτία καταγράφηκε στο log.')
            return
        changed = self.history_stamp is not None and self.history_stamp != context.stamp
        if changed:
            self.history.clear()
        self.pending = None
        self._document = window.doc
        self._job = _Question(context, text, list(self.history), window.assistant_model.currentText().strip() or None)
        window.assistant_send.setEnabled(False)
        self._job.signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        window.assistant_reply.setText('Ollama: εξετάζω το έργο…' + (' Νέο πλαίσιο: το έργο άλλαξε.' if changed else ''))
        window._refresh_assistant()
        QThreadPool.globalInstance().start(self._job)

    @Slot(object, str)
    def _finished(self, answer, error):
        job = self._job
        self._job = None
        window = self.window
        window.assistant_send.setEnabled(True)
        if self._document is not window.doc or not job.context.current(window.doc):
            self.pending = None
            window.assistant_reply.setText('Το έργο άλλαξε όσο απαντούσε το Ollama. Η παλιά απάντηση απορρίφθηκε· ξαναστείλε την ερώτηση.')
            return
        if error:
            window.assistant_reply.setText(error + '\nΓια νέα συνομιλία γράψε /νέα.')
            return
        self.history.extend([{'role': 'user', 'content': job.question}, {'role': 'assistant', 'content': answer.text}])
        self.history_stamp = job.context.stamp
        self.pending = (job.context, answer.proposal) if answer.proposal is not None else None
        # Evidence is produced by the adapter, not claimed by the model.
        evidence = '\n'.join(f"• {e['tool']}: {e['arguments']}" for e in answer.evidence)
        window.assistant_reply.setText(answer.text + '\n\nΠηγές ανάγνωσης: επισκόπηση όλου του έργου'
                                       + ('\n' + evidence if evidence else '')
                                       + '\nΔεν εφαρμόστηκε αλλαγή.'
                                       + (' Η πρόταση βρίσκεται στη λίστα: έλεγξε και πάτησε Εφαρμογή.' if self.pending else ''))
        if window.assistant_text.text().strip() == job.question:
            window.assistant_text.clear()
        window._refresh_assistant()
        if self.pending:
            window.assistant_pages.setTabText(1, "Προτάσεις • νέα")

    def proposal(self):
        if self.pending:
            context, proposal = self.pending
            if context.current(self.window.doc) and self._document is self.window.doc:
                return proposal
            self.pending = None
        return None


def enabled(window=None):
    if window is not None and hasattr(window, "assistant_provider"):
        return window.assistant_provider.currentIndex() == 1
    return os.getenv('ARCHFORGE_AI_PROVIDER', '').strip().lower() == 'ollama'


def ask(window, text):
    controller = getattr(window, '_ollama_controller', None)
    if controller is None:
        controller = window._ollama_controller = Controller(window)
    controller.start(text)


def pending_proposal(window):
    controller = getattr(window, '_ollama_controller', None)
    return controller.proposal() if controller is not None else None


def apply_proposal(window, proposal):
    """Existing Apply button -> existing shared apply -> one CommandStack undo step."""
    from archforge.assistant.suggestions import apply
    controller = getattr(window, '_ollama_controller', None)
    try:
        if controller is None or controller.proposal() is not proposal:
            raise OllamaError('Η πρόταση δεν είναι πλέον τρέχουσα. Ζήτησε νέα πρόταση.')
        apply(window.stack, proposal)
    except Exception as exc:
        logging.getLogger(__name__).exception('Cannot apply Ollama proposal')
        window.assistant_reply.setText('Δεν εφαρμόστηκε η πρόταση: ' + str(exc))
        return
    controller.pending = None
    window._refresh_project_tree()
    window._redraw_views(all_views=True)
    window.assistant_reply.setText('Εφαρμόστηκε η πρόταση μέσω των Ιδιοτήτων. Ctrl+Z για αναίρεση.')
    window._refresh_assistant()
