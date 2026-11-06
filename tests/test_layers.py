"""LAY1: layers (visible / locked / dim) and the Αρχιτεκτονικό / Φέρων / Η/Μ environments."""
import os

import pytest

from archforge.core import layers as L
from archforge.core.commands import AddEntity, CommandStack, MoveEntities, UpdateEntity
from archforge.core.model import SCHEMAS, Document, Entity
from archforge.core.plan_scene import build_plan_frame


def _doc():
    doc = Document()
    wall = Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 5.0, 'y2': 0.0, 'thickness': 0.25, 'height': 2.7, 'z': 0.0}, id='w1')
    col = Entity('structural_column', {'x': 0.0, 'y': 0.0, 'z': 0.0, 'width': 0.25, 'depth': 0.25, 'height': 2.7,
                                       'rotation': 0.0, 'role': 'structural', 'construction': 'reinforced_concrete',
                                       'section': 'rectangular', 'base_level': 'Ground', 'top_level': 'Unassigned'}, id='c1')
    stack = CommandStack(doc)
    stack.execute(AddEntity(wall)); stack.execute(AddEntity(col))
    return doc, stack


def _ids(frame):
    return {p.entity_id for p in frame.primitives if p.entity_id}


def test_every_kind_has_a_layer():
    for kind in SCHEMAS:
        assert kind in L.KIND_LAYERS, kind
        assert L.entity_layer(kind, {}) in L.LAYERS
    for key in set(L.KIND_LAYERS.values()) | set(L.ROLE_LAYERS.values()) | set(L.SCENE_LAYERS.values()):
        assert key in L.LAYERS
    for ws in L.WORKSPACES:
        assert set(L._preset(ws)) == set(L.LAYERS)


def test_no_layer_state_means_no_filtering():
    doc, _ = _doc()
    assert not L.layers_active(doc)
    assert {'w1', 'c1'} <= _ids(build_plan_frame(doc))


def test_hidden_layer_gives_no_primitives_and_no_handles():
    doc, _ = _doc()
    L.ensure_view_layers(doc)
    L.set_layer_state(doc, 'structure', visible=False)
    f = build_plan_frame(doc)
    assert 'c1' not in _ids(f) and 'w1' in _ids(f)
    assert all(h.entity_id != 'c1' for h in f.handles)
    assert not L.editable(doc, 'c1')


def test_architectural_environment_column_faint_and_unpickable():
    doc, _ = _doc()
    L.ensure_view_layers(doc)
    f = build_plan_frame(doc)
    cols = [p for p in f.primitives if p.role == 'structural-column']
    assert cols and all(not p.entity_id and dict(p.meta).get('layer_dim') for p in cols)
    assert 'w1' in _ids(f)


def test_locked_layer_refuses_changes_and_unlock_allows():
    doc, stack = _doc()
    L.ensure_view_layers(doc)                       # Αρχιτεκτονικό: structure locked
    with pytest.raises(L.LayerLockedError, match='κλειδωμένο'):
        stack.execute(UpdateEntity('c1', {'width': 0.3}))
    with pytest.raises(L.LayerLockedError):
        stack.execute(MoveEntities(['c1'], 1.0, 0.0))
    assert doc.get('c1').params['width'] == 0.25 and len(stack.done) == 2
    stack.execute(UpdateEntity('w1', {'thickness': 0.3}))      # walls stay free
    L.set_workspace(doc, 'structure')
    stack.execute(UpdateEntity('c1', {'width': 0.3}))
    with pytest.raises(L.LayerLockedError, match='Τοίχοι'):
        stack.execute(UpdateEntity('w1', {'thickness': 0.35}))


def test_switching_environment_does_not_touch_entities_or_undo():
    doc, stack = _doc()
    L.ensure_view_layers(doc)
    before = {eid: (e.params.copy(), e.revision) for eid, e in doc.entities.items()}
    done = len(stack.done)
    for ws in ('structure', 'mep', 'arch', 'structure'):
        L.set_workspace(doc, ws)
    L.set_layer_state(doc, 'walls', dim=False)
    assert {eid: (e.params, e.revision) for eid, e in doc.entities.items()} == before
    assert len(stack.done) == done
    # Undo never flips a layer.
    stack.execute(UpdateEntity('c1', {'width': 0.3}))
    stack.undo()
    assert L.workspace(doc) == 'structure' and L.layer_state(doc, 'walls')['dim'] is False


def test_manual_changes_are_remembered_per_environment():
    doc, _ = _doc()
    L.ensure_view_layers(doc)
    L.set_layer_state(doc, 'plumbing', visible=True)
    L.set_workspace(doc, 'structure')
    assert L.layer_state(doc, 'plumbing')['visible'] is False
    L.set_workspace(doc, 'arch')
    assert L.layer_state(doc, 'plumbing')['visible'] is True
    L.reset_workspace(doc)
    assert L.layer_state(doc, 'plumbing')['visible'] is False


def test_solo_layer():
    doc, _ = _doc()
    L.ensure_view_layers(doc)
    L.solo_layer(doc, 'structure')
    states = L.layer_states(doc)
    assert states['structure'] == {'visible': True, 'locked': False, 'dim': False}
    assert not any(s['visible'] for k, s in states.items() if k != 'structure')
    assert _ids(build_plan_frame(doc)) == {'c1'}


def test_save_load_round_trip_and_old_project_defaults(tmp_path):
    doc, _ = _doc()
    L.ensure_view_layers(doc)
    L.set_workspace(doc, 'mep'); L.set_layer_state(doc, 'walls', dim=False)
    path = tmp_path / 'p.json'
    doc.save(path)
    again = Document.load(path)
    assert again.view_layers == doc.view_layers
    old = doc.to_dict(); old.pop('view_layers')
    legacy = Document.from_dict(old)
    assert legacy.view_layers == {}
    L.ensure_view_layers(legacy)
    assert L.workspace(legacy) == 'arch'
    assert Document.from_dict({**doc.to_dict(), 'view_layers': {'workspace': 'nope'}}).view_layers == {}


def test_scene_objects_follow_layers():
    doc, _ = _doc()
    L.ensure_view_layers(doc)
    objects = [{'id': 'w1', 'kind': 'wall', 'material': {}}, {'id': 'c1', 'kind': 'structural_column', 'material': {}},
               {'id': '', 'kind': 'foundation', 'layer': 'foundation'}, {'id': '', 'kind': 'elec_box', 'layer': 'elec'}]
    out = L.apply_to_scene_objects(doc, objects)
    assert [o['kind'] for o in out] == ['wall', 'structural_column']
    assert out[1]['id'] == '' and out[1]['material']['opacity'] <= 0.25 and out[0]['id'] == 'w1'


def test_window_environment_switch_and_locked_inspector():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from archforge.ui.main_window import MainWindow
    window = MainWindow()
    try:
        assert L.workspace(window.doc) == 'arch' and not window._is_dirty()
        doc = window.doc
        doc.add(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 5.0, 'y2': 0.0, 'thickness': 0.25, 'height': 2.7, 'z': 0.0}, id='w1'))
        done = len(window.stack.done)
        window._set_active_tool('structural_column')
        assert L.workspace(doc) == 'structure' and window._workspace_actions['structure'].isChecked()
        assert len(window.stack.done) == done
        doc.select(['w1']); window.refresh_inspector()
        assert not window.dock.widget().isEnabled()
        assert 'κλειδωμένο' in window.statusBar().currentMessage()
        window._set_active_tool('wall')
        assert L.workspace(doc) == 'arch'
        assert window._workspace_menu.actions() and window._layers_dock.objectName() == 'layers_panel'
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_site_tools_take_the_user_to_an_environment_where_the_site_is_editable():
    """Bots 06/11: right after Η/Μ work (environment «Η/Μ», site locked) «Οικόπεδο: σχεδίαση ορίων» refused with
    «layer κλειδωμένο» — the site tools switch environment as the wall / MEP / structure tools already do."""
    from PySide6.QtWidgets import QApplication
    from archforge.core import layers as L
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        w._set_workspace('mep'); app.processEvents()
        assert L.layer_state(w.doc, 'site')['locked']
        w._start_site_tool('plot_point', 'Κλικ σε κάθε κορυφή του οικοπέδου')
        assert not L.layer_state(w.doc, 'site')['locked'] and L.workspace(w.doc) == 'arch'
    finally:
        w._mark_clean(); w.close()


def test_escape_cancels_an_open_plot_outline_so_the_project_can_be_saved():
    """Bots 06/11: the plot outline stayed open after Esc («Esc ακύρωση» in its message) and blocked every save."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); app.processEvents()
    try:
        w._start_site_tool('plot_point', 'Κλικ σε κάθε κορυφή του οικοπέδου')
        w._plot_vertex(0.0, 0.0); w._plot_vertex(10.0, 0.0)
        assert w._has_unfinished_editor_work()
        QTest.keyClick(w.plan_view.viewport(), Qt.Key.Key_Escape); app.processEvents()
        assert not w.plan_view.plot_draft and not w._has_unfinished_editor_work()
    finally:
        w._mark_clean(); w.close()
