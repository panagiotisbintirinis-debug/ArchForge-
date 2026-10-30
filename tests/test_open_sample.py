"""Owner 18/10: the program carries sample projects — Αρχείο ▸ Άνοιγμα δείγματος… opens one, the sample stays untouched."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QFileDialog

from archforge.ui.main_window import MainWindow


def test_open_sample_from_the_file_menu(monkeypatch, tmp_path):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    app = QApplication.instance() or QApplication([])
    window = MainWindow(); app.processEvents()
    try:
        samples = os.path.normpath(window.samples_dir())
        names = sorted(n for n in os.listdir(samples) if n[:1] == 'S' and n.endswith('.archforge'))
        assert len(names) == 10
        file_menu = window._work_sections[('Έργο', 'Αρχείο')]
        assert window.open_sample_action in file_menu.actions()
        assert window.check_updates_action in window._work_sections[('⚙ Ρυθμίσεις', 'Γενικά')].actions()
        seen = {}

        def pick(_parent, _title, folder, _filter):
            seen['folder'] = folder
            return os.path.join(folder, names[0]), ''

        monkeypatch.setattr(QFileDialog, 'getOpenFileName', staticmethod(pick))
        assert window.open_sample()
        assert seen['folder'] == samples
        assert len(window.doc.entities) > 50
        assert window.current_path is None          # Αποθήκευση asks for a new place
    finally:
        window.close()
