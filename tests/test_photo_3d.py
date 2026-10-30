"""«Φωτογραφία» (owner 29/10): the 3D view as a PNG instead of a screenshot of the whole screen."""
import base64
import os

from archforge.ui.photo_3d import MAX_SIDE, default_path, photo_size, take_photo

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')


def test_photo_size_is_twice_the_view_and_never_huge():
    assert photo_size(800, 500) == (1600, 1000)
    w, h = photo_size(3000, 1500)
    assert max(w, h) == MAX_SIDE and abs(w / h - 2.0) < 0.01


def test_default_path_names_the_project_and_the_time(tmp_path):
    class W:
        current_path = str(tmp_path / 'Σπίτι Παπαδόπουλου.archforge')
    path = default_path(W())
    assert os.path.basename(path).startswith('ArchForge_Σπίτι Παπαδόπουλου_') and path.endswith('.png')


def test_the_photo_button_saves_what_the_3d_page_draws(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    QApplication.instance() or QApplication([])
    w = MainWindow()
    asked = []

    class Page:
        def runJavaScript(self, script, world=0, callback=None):
            asked.append(script)
            if callback is not None and 'archforgeCaptureFrame' in script:
                callback('data:image/png;base64,' + base64.b64encode(PNG).decode())

    class Web:
        def width(self): return 640
        def height(self): return 400
        def page(self): return Page()
    w.pbr_view.web_view = Web()
    result = []
    target = str(tmp_path / 'shot')
    take_photo(w, target, done=result.append)
    assert result == [target + '.png']
    assert open(target + '.png', 'rb').read() == PNG
    assert any('archforgeCaptureFrame(1280, 800)' in s for s in asked)
    assert w._mockup_photo_action.text() == 'Φωτογραφία'
    undo_before = len(w.stack.done)
    take_photo(w, str(tmp_path / 'again.png'))
    assert len(w.stack.done) == undo_before                      # a photo never touches the project
    w.hide()


def test_without_the_3d_page_it_says_so(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    QApplication.instance() or QApplication([])
    w = MainWindow()
    w.pbr_view.web_view = None
    result = []
    take_photo(w, str(tmp_path / 'x.png'), done=result.append)
    assert result == [None] and not os.path.exists(tmp_path / 'x.png')
    w.hide()
