"""UX5: «Διαγραφή (Del)» in the mouse menu of everything the user places (plan + 3D), and
keyboard shortcuts that change (registry, conflicts, settings.json, reset)."""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture import storey_slabs as S
from archforge.construction import drywall as D
from archforge.core.commands import AddEntities, AddEntity, CreateRoomFloors
from archforge.core.model import Entity
from archforge.ui import shortcuts as K


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _walls(window, pts):
    ids = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        e = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': 2.7, 'thickness': 0.2})
        window.stack.execute(AddEntity(e))
        ids.append(e.id)
    return ids


def _everything(window):
    """One entity of every kind the user puts in the drawing: [(kind, id)]."""
    from test_object_ops import _placed
    doc, st = window.doc, window.stack
    walls = _walls(window, [(0, 0), (6, 0), (6, 5), (0, 5)])
    door = Entity('door', {'offset': 2.0, 'width': .9, 'height': 2.1}, parent_id=walls[0])
    win = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.2, 'sill': .9}, parent_id=walls[1])
    st.execute(AddEntities([door, win]))
    st.execute(CreateRoomFloors([f.signature for f in doc.active_room_faces()]))
    st.execute(S.storey_slab_command(doc, 'room_floor', 0.0)[0]) if not any(
        e.kind == 'room_floor' for e in doc.entities.values()) else None
    st.execute(AddEntity(S.opening_entity(doc, points=[(1, 1), (2.5, 1), (2.5, 2.5), (1, 2.5)])))
    st.execute(AddEntity(Entity('drywall_ceiling', D.default_params(points=[[0, 0], [5, 0], [5, 4], [0, 4]]))))
    placed = _placed()
    st.execute(AddEntities(placed))
    return [(e.kind, i) for i, e in doc.entities.items()]


def test_registry_has_no_duplicate_defaults_and_no_reserved_keys():
    assert K.duplicate_defaults() == []
    assert all(not K.reserved_reason(key) for key in K.defaults().values())
    ids = [a[0] for a in K.ACTIONS]
    assert len(ids) == len(set(ids)) and set(K.RUN) | set(K.ADOPT) == set(ids)
    assert K.defaults()['edit.undo'] == 'Ctrl+Z' and K.defaults()['edit.delete'] == 'Del'
    assert K.defaults()['tool.wall'] == 'W' and K.defaults()['file.save'] == 'Ctrl+S'
    # Greek names only.
    assert all(any('Ͱ' <= c <= 'Ͽ' for c in a[1] + a[2]) for a in K.ACTIONS)


def test_every_placed_kind_has_delete_in_the_mouse_menu_and_it_works(window):
    from archforge.ui.marking_menu import build_menu, run
    items = _everything(window)
    kinds = {k for k, _ in items}
    assert {'wall', 'door', 'window', 'room_floor', 'slab_opening', 'drywall_ceiling', 'library_object', 'cabinet',
            'plumbing_point', 'stair', 'ramp', 'railing', 'structural_column', 'structural_beam', 'plant'} <= kinds
    for kind, eid in items:
        for view in ('plan', 'pbr'):
            menu = build_menu(window, view, eid)
            delete = [e for e in menu['entries'] if e['id'] == 'delete']
            assert delete and delete[0]['label'].startswith('Διαγραφή') and '(Del)' in delete[0]['label'], (kind, view)
    # It deletes, one undo brings it back (plan route and 3D route).
    for kind, eid in items:
        if eid not in window.doc.entities:
            continue            # went with its host (door/window in a deleted wall)
        # Columns / beams are worked in the «Φέρων» environment (faint and locked in the others).
        from archforge.ui.layers_panel import set_workspace
        set_workspace(window, 'structure' if kind.startswith('structural') else 'arch', announce=False)
        n = len(window.doc.entities)
        window.doc.select([])
        run(window, 'plan', eid, 'delete')
        assert eid not in window.doc.entities, kind
        window._undo()
        assert eid in window.doc.entities and len(window.doc.entities) == n, kind
        window._handle_object_context_action(eid, 'delete')          # what the 3D menu sends
        assert eid not in window.doc.entities, kind
        window._undo()


def test_delete_on_a_multiple_selection_deletes_all_with_one_undo(window):
    from archforge.ui.marking_menu import build_menu, run
    walls = _walls(window, [(0, 0), (4, 0), (4, 3), (0, 3)])
    window.doc.select(walls[:3])
    menu = build_menu(window, 'plan', walls[1])
    label = next(e['label'] for e in menu['entries'] if e['id'] == 'delete')
    assert label.startswith('Διαγραφή 3 επιλεγμένων')
    run(window, 'plan', walls[1], 'delete')
    assert [w for w in walls if w in window.doc.entities] == [walls[3]]
    window._undo()
    assert all(w in window.doc.entities for w in walls)


def test_locked_layer_is_respected(window):
    from archforge.core import layers as L
    from archforge.ui.marking_menu import run
    walls = _walls(window, [(0, 0), (4, 0), (4, 3), (0, 3)])
    L.set_workspace(window.doc, 'arch')
    L.set_layer_state(window.doc, 'walls', locked=True)
    window.doc.select([walls[0]])
    run(window, 'plan', walls[0], 'delete')
    assert walls[0] in window.doc.entities
    assert 'κλειδωμένο' in window.statusBar().currentMessage()


def test_wall_drawing_menu_deletes_the_last_wall(window):
    from archforge.ui.marking_menu import build_menu, run
    walls = _walls(window, [(0, 0), (4, 0), (4, 3)])
    window._set_active_tool('wall')
    menu = build_menu(window, 'plan')
    entry = [e for e in menu['entries'] if e['id'] == 'mm:wall:delete_last']
    assert entry and entry[0]['placement'] == 'panel'
    run(window, 'plan', None, 'mm:wall:delete_last')
    assert walls[-1] not in window.doc.entities and walls[0] in window.doc.entities


def test_change_shortcut_activates_new_and_frees_old_and_persists(window, tmp_path):
    m = window.shortcuts
    wall = m.actions['tool.wall']
    assert wall.shortcut().toString() == 'W'
    assert m.assign('tool.wall', 'Shift+W') is None
    assert wall.shortcut().toString() == 'Shift+W'
    # The old key is free, nothing else answers to it.
    assert K.owner_of(m.mapping(), 'W') is None
    assert all(a.shortcut().toString() != 'W' for a in window.findChildren(type(wall))
               if a.shortcutContext().name == 'WindowShortcut')
    # The key really runs the command.
    window.show()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    window.activateWindow(); QTest.qWaitForWindowActive(window, 2000)
    window.plan_view.setFocus()
    QTest.keyClick(window.plan_view, Qt.Key.Key_W, Qt.KeyboardModifier.ShiftModifier)
    assert window.plan_view.controller.tool == 'wall'
    window._set_active_tool('select')
    QTest.keyClick(window.plan_view, Qt.Key.Key_W)
    assert window.plan_view.controller.tool == 'select'
    # Stored in settings.json of the user data folder, not in the project.
    data = json.loads((tmp_path / 'data' / 'settings.json').read_text(encoding='utf8'))
    assert data['shortcuts'] == {'tool.wall': 'Shift+W'}
    assert 'shortcuts' not in json.dumps(window.doc.to_dict())
    # A new window loads it.
    again = K.ShortcutManager(window, overrides=K.load_overrides())
    assert again.key('tool.wall') == 'Shift+W'
    # Menus show the key next to the command; tooltips too.
    assert window.undo_action.text() == 'Αναίρεση' and window.save_action.shortcut().toString() == 'Ctrl+S'


def test_conflict_is_detected_and_reset_restores_defaults(window):
    m = window.shortcuts
    assert m.conflict('tool.wall', 'Ctrl+D') == 'Διπλασιασμός'
    assert m.assign('tool.wall', 'Ctrl+D') == 'edit.duplicate'          # refused, nothing changed
    assert m.key('tool.wall') == 'W' and m.key('edit.duplicate') == 'Ctrl+D'
    assert m.assign('tool.wall', 'Ctrl+D', steal=True) is None
    assert m.key('tool.wall') == 'Ctrl+D' and m.key('edit.duplicate') == ''
    with pytest.raises(ValueError):
        m.assign('tool.door', 'Esc')
    assert 'R στρίβει' in m.conflict('edit.rotate', 'R')
    m.reset()
    assert m.mapping() == K.defaults() and K.load_overrides() == {}


def test_dialog_search_conflict_message_and_export_import(window, tmp_path):
    d = K.open_dialog(window)
    d.search.setText('τοίχ')
    names = {d.table.item(r, 1).text() for r in range(d.table.rowCount())}
    assert names == {'Τοίχος'}
    assert d.select('tool.wall')
    assert not d.set_key('D', ask=False)
    assert 'Το D χρησιμοποιείται ήδη από «Πόρτα»' in d.message.text()
    assert d.set_key('Shift+W')
    assert d.table.item(0, 2).text() == 'Shift+W'
    path = tmp_path / 'keys.json'
    window.shortcuts.export(str(path))
    window.shortcuts.reset()
    window.shortcuts.import_(str(path))
    assert window.shortcuts.key('tool.wall') == 'Shift+W'
    d._reset()
    assert window.shortcuts.key('tool.wall') == 'W'
    d.close()
