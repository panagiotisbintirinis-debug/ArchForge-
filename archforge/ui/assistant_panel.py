"""Assistant cockpit: existing commands, explicit local connection, readable chat."""
import os
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QListWidget, QLineEdit, QTextBrowser, QTabWidget, QScrollArea)
from archforge.orchestration.ollama import OllamaClient, OllamaError

STYLE = '''
QWidget#assistantCockpit { background:#101925; color:#e5edf7; }
QWidget#assistantCockpit QLabel { color:#c4d4e5; background:transparent; }
QWidget#assistantCockpit QLabel#assistantTitle { color:#67e8e0; font-size:19px; font-weight:700; }
QWidget#assistantCockpit QTextBrowser, QWidget#assistantCockpit QListWidget,
QWidget#assistantCockpit QLineEdit, QWidget#assistantCockpit QComboBox {
 background:#172536; color:#e5edf7; border:1px solid #334a62; border-radius:7px; padding:7px; }
QWidget#assistantCockpit QPushButton { background:#21374b; color:#e5edf7;
 border:1px solid #405a70; border-radius:7px; padding:8px; }
QWidget#assistantCockpit QPushButton:hover { background:#2c4c62; border-color:#67e8e0; }
QWidget#assistantCockpit QPushButton:disabled { color:#7b8a9a; background:#17212d; }
QWidget#assistantCockpit QPushButton#assistantPrimary { background:#67e8e0; color:#0d2029; font-weight:700; }
QWidget#assistantCockpit QTabWidget::pane { background:#101925; border:0; }
QWidget#assistantCockpit QTabBar::tab { background:#172536; color:#a9bfd2; padding:9px; }
QWidget#assistantCockpit QTabBar::tab:selected { color:#67e8e0; border-bottom:2px solid #67e8e0; }
'''


class Transcript(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last = ''
        self.setOpenExternalLinks(False)
        self.document().setMaximumBlockCount(1000)
        self.setAccessibleName('Συνομιλία με τον βοηθό')
    def add_message(self, author, text):
        cursor = self.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(('\n\n' if not self.document().isEmpty() else '') + author + '\n' + text)
        self.setTextCursor(cursor); self.ensureCursorVisible()
    def setText(self, text):
        self._last = str(text)
        self.add_message('ARCHFORGE', self._last)
    def text(self):
        return self._last
    def setTextFormat(self, _format):
        # Compatibility with the controller: all messages are inserted as plain text.
        return None


class ModelSignals(QObject):
    finished = Signal(object, str)


class ModelQuery(QRunnable):
    def __init__(self):
        super().__init__(); self.signals = ModelSignals()
    def run(self):
        try:
            self.signals.finished.emit(OllamaClient(timeout=10).models(), '')
        except OllamaError as exc:
            self.signals.finished.emit([], str(exc))
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Ollama model discovery failed')
            self.signals.finished.emit([], 'Η ανίχνευση μοντέλων απέτυχε· δες το log.')


class Connection(QObject):
    def __init__(self, window):
        super().__init__(window); self.window = window; self.job = None
    def refresh(self):
        if self.job is not None: return
        w = self.window
        w.assistant_connect.setEnabled(False)
        w.assistant_connection.setText('Αναζήτηση τοπικού Ollama…')
        self.job = ModelQuery()
        self.job.signals.finished.connect(self.finished, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(self.job)
    @Slot(object, str)
    def finished(self, models, error):
        self.job = None; w = self.window
        w.assistant_connect.setEnabled(True)
        if error:
            w.assistant_connection.setText('Εκτός σύνδεσης')
            w.assistant_reply.setText(error)
            return
        previous = w.assistant_model.currentText()
        w.assistant_model.clear(); w.assistant_model.addItems(models)
        if previous in models: w.assistant_model.setCurrentText(previous)
        elif len(models) > 1: w.assistant_model.setCurrentIndex(-1)
        w.assistant_connection.setText(f'Ollama διαθέσιμο · {len(models)} μοντέλα' if models else 'Ollama διαθέσιμο · δεν υπάρχει εγκατεστημένο μοντέλο')
        if models: w.assistant_provider.setCurrentIndex(1)


def build(window):
    w = window
    panel = QWidget(w); panel.setObjectName('assistantCockpit'); panel.setStyleSheet(STYLE)
    layout = QVBoxLayout(panel); layout.setContentsMargins(14,14,14,14); layout.setSpacing(10)
    title = QLabel('◈  ARCHFORGE ASSIST', panel); title.setObjectName('assistantTitle'); layout.addWidget(title)
    subtitle = QLabel('Το έργο σου. Οι αποφάσεις σου.', panel); layout.addWidget(subtitle)
    row = QHBoxLayout()
    w.assistant_provider = QComboBox(panel); w.assistant_provider.addItems(['Κανόνες έργου', 'Τοπικό Ollama'])
    w.assistant_provider.setAccessibleName('Τρόπος λειτουργίας βοηθού')
    w.assistant_provider.setCurrentIndex(1 if os.getenv('ARCHFORGE_AI_PROVIDER','').lower() == 'ollama' else 0)
    w.assistant_connect = QPushButton('Σύνδεση Ollama', panel)
    row.addWidget(w.assistant_provider,1); row.addWidget(w.assistant_connect); layout.addLayout(row)
    w.assistant_model = QComboBox(panel); w.assistant_model.setEditable(True)
    w.assistant_model.lineEdit().setPlaceholderText('Σύνδεση → επιλογή εγκατεστημένου μοντέλου')
    w.assistant_model.setCurrentText(os.getenv('ARCHFORGE_OLLAMA_MODEL',''))
    w.assistant_model.setAccessibleName('Μοντέλο Ollama'); layout.addWidget(w.assistant_model)
    w.assistant_connection = QLabel('Σύνδεση μη ελεγμένη · οι κανόνες λειτουργούν χωρίς AI',panel)
    w.assistant_connection.setWordWrap(True); layout.addWidget(w.assistant_connection)
    w._assistant_connection_controller = Connection(w)
    w.assistant_connect.clicked.connect(w._assistant_connection_controller.refresh)
    w.assistant_pages = QTabWidget(panel); layout.addWidget(w.assistant_pages,1)
    chat = QWidget(panel); chat_layout = QVBoxLayout(chat); chat_layout.setContentsMargins(0,10,0,0)
    w.assistant_reply = Transcript(chat); chat_layout.addWidget(w.assistant_reply,1)
    w.assistant_reply.setText('Πάτησε «Σύνδεση Ollama», διάλεξε μοντέλο και γράψε τι χρειάζεσαι. Οι προτάσεις αλλαγών εμφανίζονται στην καρτέλα «Προτάσεις».')
    w.assistant_text = QLineEdit(chat); w.assistant_text.setPlaceholderText('Ρώτησε για το έργο ή ζήτησε αλλαγή…')
    w.assistant_text.setAccessibleName('Ερώτηση στον βοηθό'); w.assistant_text.returnPressed.connect(w._assistant_ask)
    chat_layout.addWidget(w.assistant_text)
    controls = QHBoxLayout(); fresh = QPushButton('Νέα συνομιλία',chat)
    w.assistant_send = QPushButton('Αποστολή  →',chat); w.assistant_send.setObjectName('assistantPrimary')
    w.assistant_send.clicked.connect(w._assistant_ask)
    def reset():
        controller = getattr(w,'_ollama_controller',None)
        if controller and controller._job is not None:
            w.assistant_reply.setText('Περίμενε να ολοκληρωθεί η τρέχουσα ερώτηση.'); return
        if controller: controller.history.clear(); controller.pending = None
        w.assistant_reply.clear(); w.assistant_reply.setText('Νέα συνομιλία. Το έργο δεν άλλαξε.')
        w._refresh_assistant()
    fresh.clicked.connect(reset); controls.addWidget(fresh); controls.addWidget(w.assistant_send,1); chat_layout.addLayout(controls)
    w.assistant_pages.addTab(chat,'Συνομιλία')
    proposals = QWidget(panel); pl = QVBoxLayout(proposals)
    w.assistant_list = QListWidget(proposals); w.assistant_list.currentRowChanged.connect(w._show_assistant_detail); pl.addWidget(w.assistant_list,1)
    w.assistant_detail = QLabel(proposals); w.assistant_detail.setWordWrap(True); pl.addWidget(w.assistant_detail)
    row = QHBoxLayout(); w.assistant_apply = QPushButton('Εφαρμογή',proposals); w.assistant_apply.setObjectName('assistantPrimary')
    w.assistant_apply.clicked.connect(w._apply_assistant_proposal)
    w.assistant_dismiss = QPushButton('Αγνόηση',proposals); w.assistant_dismiss.clicked.connect(w._dismiss_assistant_proposal)
    row.addWidget(w.assistant_apply); row.addWidget(w.assistant_dismiss); pl.addLayout(row)
    pl.addWidget(QLabel('Ελέγχεις τη μεταβολή πριν εφαρμοστεί. Ctrl+Z: αναίρεση.',proposals))
    w.assistant_pages.addTab(proposals,'Προτάσεις')
    target = QWidget(panel); tl = QVBoxLayout(target)
    w.assistant_pick = QPushButton('Δείξε στην κάτοψη',target)
    w.assistant_pick.clicked.connect(lambda:w._start_site_tool('assist_point','Κλικ στον στόχο — Esc για τέλος'))
    w.assistant_from_selection = QPushButton('Στόχος = επιλογή (2D/3D)',target); w.assistant_from_selection.clicked.connect(w._assistant_target_from_selection)
    clear = QPushButton('Καθαρισμός στόχου',target); clear.clicked.connect(lambda:w._set_assistant_target(None))
    for button in (w.assistant_pick,w.assistant_from_selection,clear): tl.addWidget(button)
    w.assistant_target_label = QLabel(target); w.assistant_target_label.setWordWrap(True); tl.addWidget(w.assistant_target_label)
    w.assistant_actions = QListWidget(target)
    w.assistant_actions.itemDoubleClicked.connect(lambda item:w._run_assistant_action(w.assistant_actions.row(item)))
    tl.addWidget(w.assistant_actions,1)
    w.assistant_joists_button = QPushButton('Διανομή δοκίδων · κλικ σε χώρο',target)
    w.assistant_joists_button.clicked.connect(lambda:w._start_site_tool('assist_joists','Κλικ μέσα σε χώρο — Esc για τέλος'))
    tl.addWidget(w.assistant_joists_button); w.assistant_pages.addTab(target,'Στόχος / εργαλεία')
    arrangement = QScrollArea(panel); arrangement.setWidgetResizable(True)
    arrangement_body = QWidget(arrangement)
    w.assistant_tools_layout = QVBoxLayout(arrangement_body)
    w.assistant_tools_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    arrangement.setWidget(arrangement_body)
    w.assistant_arrangement_page = arrangement
    w.assistant_pages.addTab(arrangement,'Διαρρύθμιση')
    w._assistant_target = None; w._assistant_target_actions = []; w._assistant_proposals = []; w._assistant_dismissed = set()
    return panel


def install_launcher(window, dock):
    button = QPushButton('◈  Βοηθός',window)
    button.setObjectName('assistantLauncher')
    button.setStyleSheet('QPushButton {background:#15283b;color:#67e8e0;border:1px solid #67e8e0;border-radius:8px;padding:7px 16px;font-weight:700;} QPushButton:hover {background:#27465e;}')
    button.setToolTip('Άνοιγμα βοηθού · συνομιλία, Ollama και προτάσεις')
    def reveal():
        dock.show(); dock.raise_(); window.assistant_pages.setCurrentIndex(0); window.assistant_text.setFocus()
    button.clicked.connect(reveal)
    window.statusBar().addPermanentWidget(button)
    window.assistant_launcher = button
    window._show_assistant = reveal
