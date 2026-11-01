"""3D must show walls drawn in the plan even if its WebGL page was opened earlier."""

import pytest

from archforge.core.commands import AddEntity, UpdateEntity
from archforge.core.model import Entity


class _RecordingPage:
    def __init__(self):
        self.scripts = []

    def runJavaScript(self, script):
        self.scripts.append(script)


class _RecordingWebView:
    def __init__(self):
        self.recording_page = _RecordingPage()

    def page(self):
        return self.recording_page


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow

    QApplication.instance() or QApplication([])
    w = MainWindow()
    w.pbr_view.web_view = _RecordingWebView()
    yield w
    w.pbr_view.web_view = None
    w.hide()


def _wall(y, wall_type="generic"):
    return Entity("wall", {
        "x1": -3.0, "y1": y, "x2": 3.0, "y2": y,
        "z": 0.0, "height": 2.7, "thickness": 0.30,
        "wall_type": wall_type,
    })


@pytest.mark.parametrize("wall_type", ["generic", "isotex_hdiii_30_7"])
def test_switching_back_to_3d_uploads_walls_drawn_after_its_initial_empty_scene(window, wall_type):
    viewport = window.pbr_view
    viewport._evaluation_cache.sync(window.doc)
    viewport._sent_scene = {}  # page was opened while the plan was still empty
    wall = _wall(0, wall_type)
    window.stack.execute(AddEntity(wall))

    window._show_3d_view()

    scripts = viewport.web_view.page().scripts
    assert any("archforgeSetScene" in script and wall.id in script for script in scripts)
    assert any("true);" in script for script in scripts)  # first building gets framed


def test_switching_back_to_3d_pushes_only_new_wall_without_resetting_camera(window):
    viewport = window.pbr_view
    first = _wall(0)
    window.stack.execute(AddEntity(first))
    viewport.redraw(force_full=True)
    viewport.web_view.page().scripts.clear()

    second = _wall(4)
    window.stack.execute(AddEntity(second))
    window._show_3d_view()

    scripts = viewport.web_view.page().scripts
    assert any("archforgeSetScene" in script and second.id in script for script in scripts)
    assert any('"keep"' in script and "false);" in script for script in scripts)


def test_wall_type_and_layer_changes_in_plan_reach_already_open_3d_view(window):
    viewport = window.pbr_view
    wall = _wall(0)
    window.stack.execute(AddEntity(wall))
    viewport.redraw(force_full=True)
    viewport.web_view.page().scripts.clear()

    window.stack.execute(UpdateEntity(wall.id, {
        "wall_type": "isotex_hdiii_30_7", "thickness": 0.30,
    }))
    window._show_3d_view()

    scripts = viewport.web_view.page().scripts
    assert any(wall.id in script and "__layer_" in script for script in scripts)
    assert any("false);" in script for script in scripts)  # no camera jump
