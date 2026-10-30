"""HANDOFF 30/10: with «Ταυτόχρονα 2D + 3D» the point tools of the site (tree, pool …) wanted a click in the plan —
a click on the 3D ground did nothing.  Now it places them through the same path as the plan."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _plants(w):
    return [e for e in w.doc.entities.values() if e.kind == 'plant']


def test_a_click_on_the_3d_ground_plants_the_tree_like_a_click_in_the_plan(window):
    w = window
    w._simultaneous_action.setChecked(True)
    w._start_site_tool('plant_tree', 'Κλικ για δέντρο')
    assert w.pbr_view.active_tool == 'site:plant_tree'
    w.pbr_view.sitePointRequested.emit('plant_tree', 3.0, 4.0)
    [tree] = _plants(w)
    assert (tree.params['x'], tree.params['y'], tree.params['species']) == (3.0, 4.0, 'tree')
    w.stack.undo()
    assert not _plants(w)


def test_a_stale_3d_click_after_the_tool_changed_places_nothing(window):
    w = window
    w._simultaneous_action.setChecked(True)
    w._start_site_tool('plant_tree', 'Κλικ για δέντρο')
    w.plan_view.controller.set_tool('select')
    w.pbr_view.sitePointRequested.emit('plant_tree', 3.0, 4.0)
    assert not _plants(w) and w.pbr_view.active_tool == 'orbit'


def test_without_both_views_the_3d_stays_as_it_was(window):
    w = window
    w._simultaneous_action.setChecked(False)
    w._start_site_tool('plant_tree', 'Κλικ για δέντρο')
    assert not str(w.pbr_view.active_tool).startswith('site:')


def test_the_real_3d_page_sends_ground_points_for_clicks_not_drags():
    from archforge.core.model import Document
    from archforge.scenarios import click3d
    if not click3d.available():
        pytest.skip('χωρίς Node / Playwright / Chromium')
    calls = click3d.clicks(Document(), 'site:pool_place', cols=6, rows=4)
    points = [c for c in calls if c[0] == 'placeSitePoint']
    assert points and all(c[1] == 'pool_place' for c in points)
    assert len({(round(c[2], 2), round(c[3], 2)) for c in points}) > 4       # different ground points
