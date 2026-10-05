"""One mouse menu for every task (Inventor-style marking menu), in the plan and in 3D."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity
from archforge.core.model import Entity


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _ids(menu, placement='radial'):
    return [e['id'] for e in menu['entries'] if e['placement'] == placement]


def test_menu_content_follows_the_task(window):
    from archforge.ui.marking_menu import build_menu
    empty = build_menu(window, 'plan')
    assert empty['center'] == 'Σχεδίαση' and 'mm:tool:wall' in _ids(empty) and len(_ids(empty)) <= 8
    assert 'mm:assist:point' in _ids(empty, 'panel')
    window._set_active_tool('wall')
    wall = build_menu(window, 'plan')
    assert _ids(wall)[0] == 'mm:tool:select'                     # north = finish the task
    assert {'mm:angle:90', 'mm:angle:45', 'mm:angle:15', 'mm:angle:free'} <= set(_ids(wall))
    assert not any('undo' in i or 'delete' in i for i in _ids(wall))   # no noise
    window._set_active_tool('select')
    window.sculpt_action.setChecked(True)
    sculpt = build_menu(window, 'plan')
    assert sculpt['wheel'] == 'brush' and _ids(sculpt)[0] == 'mm:sculpt:exit'
    assert {'mm:sculpt:pull', 'mm:sculpt:smooth'} <= set(_ids(sculpt)) and 'βούρτσα' in sculpt['center']
    window.sculpt_action.setChecked(False)
    w = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': 0.2})
    window.stack.execute(AddEntity(w))
    obj = build_menu(window, 'plan', w.id)
    assert _ids(obj)[0] == 'properties' and 'delete' in _ids(obj) and obj['center'].startswith('Τοίχος')
    assert 'mm:assist:entity' in _ids(obj, 'panel')


def test_wheel_sets_brush_and_wall_angle_and_choices_run(window):
    from archforge.ui.marking_menu import run, wheel
    window.sculpt_action.setChecked(True)
    r0 = window.sculpt_radius.value()
    text = wheel(window, 'brush', +2)
    assert window.sculpt_radius.value() == pytest.approx(r0 + 0.10) and f'{r0 + 0.10:.2f}' in text
    run(window, 'plan', None, 'mm:sculpt:smooth')
    assert window.sculpt_operation.currentText() == 'smooth'
    run(window, 'plan', None, 'mm:sculpt:exit')
    assert not window.sculpt_action.isChecked()
    window._set_active_tool('wall')
    window.plan_view.set_wall_angle_increment(90.0)
    wheel(window, 'angle', +1)
    assert window.plan_view.controller.wall_angle_increment == pytest.approx(45.0)
    run(window, 'plan', None, 'mm:angle:free')
    assert window.plan_view.controller.wall_angle_increment is None
    run(window, 'plan', None, 'mm:tool:select')
    assert window.plan_view.controller.tool == 'select'


def test_right_click_in_the_plan_opens_it_and_a_choice_acts(window):
    from PySide6.QtCore import QPoint
    window.resize(1280, 900); window.show()
    plan = window.plan_view
    menu = plan.show_marking_menu(QPoint(200, 200))
    assert menu.isVisible() and 'mm:tool:wall' in menu.buttons
    menu.buttons['mm:tool:wall'].click()
    assert plan.controller.tool == 'wall' and plan._marking_menu is None
    menu = plan.show_marking_menu(QPoint(200, 200))
    assert set(menu.buttons) >= {'mm:angle:90', 'mm:angle:free'} and 'βούρτσα' not in menu.center.text()


def test_3d_view_gets_the_same_menu_and_routes_its_actions(window):
    window.sculpt_action.setChecked(True)
    window.pbr_view._show_context_menu('', 100.0, 100.0)
    menu = window.pbr_view.last_marking_menu
    assert menu['wheel'] == 'brush' and 'mm:sculpt:pull' in _ids(menu)
    window._handle_object_context_action('', 'mm:sculpt:recess')     # what the web overlay sends back
    assert window.sculpt_operation.currentText() == 'recess'
    window.pbr_view._marking_wheel(-1)
    window._handle_object_context_action('', 'mm:sculpt:exit')
    assert not window.sculpt_action.isChecked()


def test_half_placed_stair_in_3d_is_dropped_when_the_tool_changes(window):
    """Reported: the SPIRAL hint stayed on screen and clicks no longer selected anything."""
    window.doc.levels['Floor 2'] = 2.7
    window.pbr_view.set_tool('stair')
    window.pbr_view._begin_stair_from_web(1.0, 1.0)
    assert window.pbr_view._stair_tx is not None
    window.pbr_view.set_tool('select')
    assert window.pbr_view._stair_tx is None
    assert not any(e.kind == 'stair' for e in window.doc.entities.values())


def test_stair_menu_while_placing(window):
    from archforge.ui.marking_menu import build_menu, run
    window.doc.levels['Floor 2'] = 2.7
    window.pbr_view.set_tool('stair')
    window.pbr_view._begin_stair_from_web(1.0, 1.0)
    menu = build_menu(window, 'pbr')
    assert _ids(menu)[0] == 'mm:stair:cancel' and 'mm:stair:spiral' in _ids(menu) and menu['wheel'] == 'stair'
    run(window, 'pbr', None, 'mm:stair:cancel')
    assert window.pbr_view._stair_tx is None and window.plan_view.controller.tool == 'select'
    run(window, 'plan', None, 'mm:stair:straight')
    assert window._stair_layout == 'straight' and window.plan_view.controller.tool == 'stair'


def test_tree_labels_say_something_instead_of_generic_names(window):
    from archforge.ui.project_outline import project_outline
    w = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 8, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': 0.15}, name='Wall')
    window.stack.execute(AddEntity(w))
    labels = []

    def walk(n):
        labels.append(n['label'])
        for c in n['children']:
            walk(c)
    walk(project_outline(window.doc))
    assert 'Τοίχος 8.00 m · 15 cm' in labels and not any(l.startswith('Wall') for l in labels)


def test_3d_picking_rules_walls_inactive_in_glass_and_while_working_a_stair():
    """Reported: in Glass the mouse caught the walls instead of the stair."""
    import re
    import shutil
    import subprocess
    import tempfile
    from archforge.ui.pbr_viewport import _PBR_HTML as html
    body = html[html.index('function pickForSelection'):]
    body = body[:body.index('\n}\n')]
    assert 'activeTechnique === "glass"' in body and 'activeTool === "stair"' in body and 'CONTAINER_KINDS' in body
    start = html[html.index('function placementPoint'):]
    assert 'pickModel' not in start[:start.index('\n}\n')]                 # stair/ramp start on the storey floor
    dbl = html[html.index('addEventListener("dblclick"'):]
    assert 'pickForSelection(event)' in dbl[:600]
    menu = html[html.index('addEventListener("contextmenu"'):]
    assert 'pickForSelection(event)' in menu[:menu.index('bridge.showContextMenu')]
    if shutil.which('node'):
        code = max(re.findall(r'<script[^>]*>(.*?)</script>', html, re.S), key=len)
        with tempfile.NamedTemporaryFile('w', suffix='.mjs', delete=False) as f:
            f.write(code)
        assert subprocess.run(['node', '--check', f.name]).returncode == 0
