"""«Δείξε την επιλογή στο 3D» (Shift+F3, κριτική v5 k8 — παρουσίαση 3D «1η προτεραιότητα»)."""
import pytest

from archforge.core.model import Document, Entity
from archforge.scenarios import click3d


def _doc():
    doc = Document()
    doc.add(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 20.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2}))
    box = Entity('box', {'x': 18.0, 'y': 6.0, 'z': 0.0, 'width': 0.6, 'depth': 0.6, 'height': 0.8})
    doc.add(box)
    return doc, box


def test_the_camera_keeps_its_direction_and_comes_close_to_the_chosen_object():
    if not click3d.available():
        pytest.skip('χωρίς Node / Playwright / Chromium')
    doc, box = _doc()
    result = click3d.run_in_page(doc, """
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    await wait(300);
    const state = () => {
      const {position: p, target: t} = window.__cameraState();
      const d = [p[0] - t[0], p[1] - t[1], p[2] - t[2]], n = Math.hypot(...d);
      return {dir: d.map((v) => v / n), dist: n, t};
    };
    const before = state();
    const found = window.frameEntities([%s]);
    const after = state();
    const none = window.frameEntities(["nothing-here"], false);
    const sameDir = before.dir[0] * after.dir[0] + before.dir[1] * after.dir[1] + before.dir[2] * after.dir[2];
    return {found, none, sameDir, closer: after.dist < before.dist * 0.6, target: after.t,
            moved: window.__cameraMovedByHuman()};
    """ % repr(box.id))
    assert result['found'] >= 1 and result['none'] == 0, result
    assert result['sameDir'] > 0.999 and result['closer'], result
    x, y, z = result['target']
    assert abs(x - 18.0) < 0.5 and abs(y - 6.0) < 0.5 and 0.0 <= z <= 0.8, result
    assert result['moved'], result                       # a later scene update keeps this view


class _Page:
    def __init__(self):
        self.scripts = []

    def runJavaScript(self, script):
        self.scripts.append(script)


class _View:
    def __init__(self):
        self.p = _Page()

    def page(self):
        return self.p


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w, app
    w.pbr_view.web_view = None
    w._mark_clean(); w.close(); app.processEvents()


def test_shift_f3_opens_3d_on_the_selection_and_waits_for_a_page_still_loading(window):
    from archforge.core.commands import AddEntity
    from archforge.ui.shortcuts import show_selection_3d
    w, app = window
    action = w.shortcuts.actions['view.selection_3d']
    assert action.shortcut().toString() == 'Shift+F3' and any(action in m.actions() for m in w.findChildren(__import__('PySide6.QtWidgets', fromlist=['QMenu']).QMenu) if m.title() == 'Κάμερα 3D')
    assert show_selection_3d(w) is None                  # nothing selected: says so, does nothing
    wall = Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
    w.stack.execute(AddEntity(wall)); w.doc.select([wall.id])

    view = w.pbr_view
    view.web_view, view._page_ready = _View(), False     # page created, HTML not loaded yet
    view.frame_entities([wall.id])
    assert not view.web_view.page().scripts and view._pending_frame == [wall.id]

    view._page_ready = True                              # loaded page: the request goes straight to it
    action.trigger(); app.processEvents()
    assert any('frameEntities' in s and wall.id in s for s in view.web_view.page().scripts)
    assert w._central_tabs.currentIndex() == 1 if w._central_tabs.count() > 1 else True
