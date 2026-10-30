"""Owner 15/10: the mouse menu as each one wants it, per task — a «Ποντίκι» editor with the ring in view,
drag commands in, drag them out, the size follows how many («αυτό είναι η λύση»)."""
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
    w = MainWindow(); w.resize(1400, 900); w.show(); app.processEvents()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _wall(w):
    e = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
    w.stack.execute(AddEntity(e))
    return e.id


def test_tasks_follow_the_right_click(window):
    from archforge.ui.mouse_menus import task_of
    assert task_of(window, 'plan') == 'empty'
    wid = _wall(window)
    assert task_of(window, 'plan', wid) == 'object:wall'
    window._set_active_tool('wall')
    assert task_of(window, 'plan') == 'wall_draw'
    window._set_active_tool('select')
    window.sculpt_action.setChecked(True)
    assert task_of(window, 'plan') == 'sculpt'
    window.sculpt_action.setChecked(False)


def test_my_menu_replaces_the_built_in_one_and_its_commands_run(window):
    from archforge.ui.marking_menu import build_menu, run
    from archforge.ui.mouse_menus import item_of_path, set_task, _find_action
    path = 'Επεξεργασία / Διπλασιασμός'
    set_task(window, 'empty', [{'id': 'mm:tool:wall', 'label': 'Τοίχος', 'icon': 'wall'},
                               item_of_path(path, _find_action(window, path)),
                               item_of_path('Κατασκευή / Στέγη', _find_action(window, 'Κατασκευή / Στέγη'))])
    menu = build_menu(window, 'plan')
    assert menu.get('custom') and [e['id'] for e in menu['entries']][:2] == ['mm:tool:wall', 'menu:' + path]
    roof = menu['entries'][2]
    assert roof['children'] and any(c['label'].startswith('Με κεραμίδια') for c in roof['children'])  # a submenu
    run(window, 'plan', None, 'mm:tool:wall')
    assert window.plan_view.controller.tool == 'wall'
    window._set_active_tool('select')
    fired = []
    _find_action(window, path).triggered.connect(lambda *_: fired.append(1))
    run(window, 'plan', None, 'menu:' + path)
    assert fired                                               # the very same menu command
    # Other tasks keep their built-in menu.
    wid = _wall(window)
    assert not build_menu(window, 'plan', wid).get('custom')


def test_more_than_eight_become_two_rings(window):
    from PySide6.QtCore import QPoint
    from archforge.ui.mouse_menus import catalog_items_for_test, set_task
    items = catalog_items_for_test(window, 12)
    set_task(window, 'empty', items)
    menu = window.plan_view.show_marking_menu(QPoint(400, 400))
    assert len(menu.buttons) == 12 and menu._disc[2] > menu.RADIUS * 1.5      # outer ring, bigger disc


def test_editor_drag_in_drag_out_reset(window):
    from archforge.ui.mouse_menus import MouseMenuEditor, item_of_path, saved, _find_action
    d = MouseMenuEditor(window, 'object:wall')
    d.show()
    n = len(d.preview.items)
    assert n >= 5 and saved(window).get('object:wall') is None                 # starts from the built-in menu
    path = 'Επεξεργασία / Διπλασιασμός'
    assert d.preview.add(item_of_path(path, _find_action(window, path)), 0)
    assert saved(window)['object:wall'][0]['id'] == 'menu:' + path               # saved at once
    d.preview.remove(1)
    assert len(saved(window)['object:wall']) == n
    # The ring of the right click uses it.
    from archforge.ui.marking_menu import build_menu
    wid = _wall(window)
    assert build_menu(window, 'plan', wid)['entries'][0]['id'] == 'menu:' + path
    d._reset()
    assert saved(window).get('object:wall') is None and len(d.preview.items) == n
    d.close()


def test_saved_with_the_layout_and_kept_by_the_button_reset(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from archforge.ui import toolbar_custom as tc
    from archforge.ui.main_window import MainWindow
    from archforge.ui.mouse_menus import saved, set_task
    settings = QSettings(str(tmp_path / 'layout.ini'), QSettings.Format.IniFormat)
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        set_task(w, 'empty', [{'id': 'mm:tool:wall', 'label': 'Τοίχος'}])
        tc.save(w, settings)
    finally:
        w._mark_clean(); w.close()
    w = MainWindow()
    try:
        tc.load(w, settings)
        assert saved(w)['empty'][0]['id'] == 'mm:tool:wall'
        tc.reset(w, settings)                                   # «Επαναφορά κουμπιών» keeps the mouse menus
        assert saved(w)['empty'][0]['id'] == 'mm:tool:wall'
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_menu_entry_opens_the_editor(window, monkeypatch):
    from archforge.ui import mouse_menus
    opened = []
    monkeypatch.setattr(mouse_menus.MouseMenuEditor, 'exec', lambda self: opened.append(self.task()) or 0)
    assert window._mouse_menu_action in window._work_sections[('⚙ Ρυθμίσεις', 'Περιβάλλον')].actions()   # mockup v4
    window._mouse_menu_action.trigger()
    assert opened == ['empty']


def test_a_menu_command_in_my_menu_runs_from_the_3d_view_too(window):
    """Owner 29–30/10: «Πισίνα δεν δουλεύει στο ποντίκι» — the pool put in the mouse menu did nothing when chosen in
    the 3D view (the page sends the choice as a context action; only ``mm:`` ids were carried out, ``menu:`` lost)."""
    from archforge.ui.mouse_menus import _find_action, item_of_path, set_task
    path = 'Κατασκευή / Έδαφος & περιβάλλον / Πισίνα'
    assert _find_action(window, path) is not None
    set_task(window, 'empty', [item_of_path(path, _find_action(window, path))])
    window.pbr_view.contextActionRequested.emit('', 'menu:' + path)   # as the 3D page's bridge.contextAction does
    assert window.plan_view.controller.tool == 'pool_place'
    window._place_site_point('pool_place', 3.0, 3.0)
    assert [e.kind for e in window.doc.entities.values()].count('pool') == 1
