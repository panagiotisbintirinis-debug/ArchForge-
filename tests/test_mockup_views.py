import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def _window():
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()
    for a, b in (((0, 0), (4, 0)), ((4, 0), (4, 3)), ((4, 3), (0, 3)), ((0, 3), (0, 0))):
        window.stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1],
                                                       'z': 0.0, 'height': 2.7, 'thickness': 0.2})))
    return app, window


def _close(app, window):
    window._mark_clean()
    window.close()
    app.processEvents()


def test_views_strip_and_menu_offer_every_view():
    app, window = _window()
    labels = ['3D Προοπτική', 'Top', 'Front', 'Side', 'Doll House', 'Ορθογραφική',
              'Τομή', 'Εσωτερική Όψη', 'Render (PBR)', 'Walkthrough']
    assert list(window._mockup_view_actions) == labels
    assert [a.text() for a in window._mockup_views_menu.actions()] == labels
    _close(app, window)


@pytest.mark.parametrize('label,preset', [('Doll House', 'dollhouse'), ('Ορθογραφική', 'ortho'),
                                          ('Top', 'top'), ('Walkthrough', 'eye')])
def test_preset_views_switch_to_the_3d_scene(label, preset):
    app, window = _window()
    window._mockup_view_actions[label]()
    assert window.pbr_view._camera_preset == preset
    assert window._central_tabs.currentIndex() == 1
    assert window.tabs.currentWidget() is window.pbr_view
    _close(app, window)


@pytest.mark.parametrize('label,kind', [('Τομή', 'section'), ('Εσωτερική Όψη', 'camera')])
def test_line_views_are_dragged_in_the_plan_and_shown_in_3d(label, kind):
    app, window = _window()
    window._mockup_view_actions[label]()
    assert window._central_tabs.currentIndex() == 0
    plan = window.plan_view
    plan.begin_view_line(2.0, -1.0)
    plan.move_view_line(2.0, 1.0)
    plan.end_view_line(2.0, 4.0)
    line = window.pbr_view._view_line
    assert line['kind'] == kind
    assert (line['x1'], line['y1'], line['x2'], line['y2']) == (2.0, -1.0, 2.0, 4.0)
    assert window._central_tabs.currentIndex() == 1
    # A normal preset afterwards leaves the section/camera.
    window._mockup_view_actions['3D Προοπτική']()
    assert window.pbr_view._view_line is None
    _close(app, window)


def test_a_click_without_drag_does_not_change_the_view():
    app, window = _window()
    window._mockup_view_actions['Τομή']()
    window.plan_view.begin_view_line(1.0, 1.0)
    window.plan_view.end_view_line(1.0, 1.01)
    assert window.pbr_view._view_line is None
    _close(app, window)


@pytest.mark.parametrize('tool', ['door', 'window', 'opening_rect'])
def test_door_and_window_work_directly_in_the_3d_scene(tool):
    app, window = _window()
    window._set_pbr_camera('orbit')
    assert window._central_tabs.currentIndex() == 1
    window._set_active_tool(tool)
    assert window._central_tabs.currentIndex() == 1
    assert window.view is window.pbr_view
    assert window.pbr_view.active_tool == tool
    _close(app, window)


def test_wall_tool_from_3d_returns_to_the_2d_plan():
    app, window = _window()
    window._set_pbr_camera('orbit')
    window._set_active_tool('wall')
    assert window._central_tabs.currentIndex() == 0
    assert window.view is window.plan_view
    assert window.plan_view.controller.tool == 'wall'
    _close(app, window)


def test_door_placed_from_the_3d_scene_cuts_its_wall():
    import json
    app, window = _window()
    window._set_pbr_camera('orbit')
    window._set_active_tool('door')
    wall = next(e for e in window.doc.entities.values() if e.kind == 'wall' and e.params['y1'] == 0 and e.params['y2'] == 0)
    window.pbr_view._place_opening_from_web('door', json.dumps({'entity_id': wall.id, 'point': [2.0, 0.0, 1.0]}))
    doors = [e for e in window.doc.entities.values() if e.kind == 'door']
    assert len(doors) == 1 and doors[0].parent_id == wall.id
    _close(app, window)


def test_rendering_menu_toggles_ambient_occlusion():
    app, window = _window()
    assert window._mockup_ao_action.isChecked()
    window._mockup_ao_action.setChecked(False)
    assert window.pbr_view._ambient_occlusion is False
    window._mockup_ao_action.setChecked(True)
    assert window.pbr_view._ambient_occlusion is True
    _close(app, window)
