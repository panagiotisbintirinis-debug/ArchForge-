"""Βοηθός: full reading of the Document, live proposals, joist solver — all through shared commands."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.assistant.suggestions import apply, joists_entity, propose
from archforge.assistant.understanding import describe, read_drawing
from archforge.core.commands import AddEntity, CommandStack, MoveEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.structure.joists import check_section, positions, size_joists


def _house(stack):
    """8×6 m, partition at x=5: living/kitchen 5×6 and bathroom 3×6."""
    for x1, y1, x2, y2 in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0), (5, 0, 5, 6)]:
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': 2.7, 'thickness': 0.2})))


def _plumb(stack, kind, x, y):
    stack.execute(AddEntity(Entity('plumbing_point', {'x': x, 'y': y, 'z': 0.0, 'point_type': kind})))


def _room(reading, x):
    return next(r for r in reading['storeys'][0]['rooms'] if r['polygon'][0][0] == x or min(p[0] for p in r['polygon']) == x)


def test_reading_sees_rooms_sizes_uses_and_equipment():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _plumb(stack, 'shower', 7.5, 5.5); _plumb(stack, 'wc', 6.0, 5.6); _plumb(stack, 'kitchen_sink', 1.0, 5.6)
    reading = read_drawing(doc)
    storey = reading['storeys'][0]
    assert storey['walls'] == 5 and storey['wall_length_m'] == pytest.approx(34.0) and len(storey['exterior_walls']) == 4
    bath, kitchen = _room(reading, 5.0), _room(reading, 0.0)
    assert bath['area_m2'] == pytest.approx(18.0) and bath['size_m'] == (3.0, 6.0)
    assert bath['use'] == 'bathroom' and bath['use_source'] == 'εξοπλισμός' and len(bath['plumbing']) == 2
    assert kitchen['use'] == 'kitchen'
    text = describe(reading)
    assert '3.00×6.00 m, 18.00 m²' in text and 'Μπάνιο' in text and 'Κουζίνα' in text


def test_room_name_overrides_inference():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    sig = _room(read_drawing(doc), 5.0)['signature']
    doc.set_room_metadata(sig, name='WC ξενώνα')
    assert _room(read_drawing(doc), 5.0)['use'] == 'wc'


def test_wet_room_without_extract_gets_a_fan_proposal_applied_as_one_undo_step():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _plumb(stack, 'shower', 7.5, 5.5); _plumb(stack, 'wc', 6.0, 5.6)
    props = propose(doc)
    fan = next(p for p in props if p.key.startswith('V-1'))
    assert fan.severity == 'warning' and 'χωρίς απαγωγή' in fan.title and fan.actionable   # no window → warning
    apply(stack, fan)
    vents = [e for e in doc.entities.values() if e.kind == 'ventilation_point']
    assert len(vents) == 1 and vents[0].params['point_type'] == 'bath_fan'
    assert (vents[0].params['x'], vents[0].params['y']) == (7.5, 5.5)       # over the shower
    assert not any(p.key.startswith('V-1') for p in propose(doc))
    stack.undo()
    assert not any(e.kind == 'ventilation_point' for e in doc.entities.values())


def test_kitchen_hood_proposal_goes_over_the_cooker():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _plumb(stack, 'kitchen_sink', 1.0, 5.6)
    stack.execute(AddEntity(Entity('electrical_point', {'x': 2.5, 'y': 5.6, 'z': 0.0, 'point_type': 'cooker', 'power_w': 6000})))
    hood = next(p for p in propose(doc) if p.key.startswith('V-2'))
    apply(stack, hood)
    v = next(e for e in doc.entities.values() if e.kind == 'ventilation_point')
    assert v.params['point_type'] == 'hood' and (v.params['x'], v.params['y']) == (2.5, 5.6)


def test_joist_solver_divides_spans_the_short_way_and_sizes_c24():
    params = joists_entity([(0, 0), (5, 0), (5, 4), (0, 4)], 0.0).params
    rep = size_joists(params)
    assert rep['direction'] == 'y' and rep['span_m'] == pytest.approx(4.0)        # spans the 4 m side
    lines = positions(params)
    xs = [a[0] for a, _b in lines]
    assert xs[0] == pytest.approx(0.05) and xs[-1] == pytest.approx(4.95)
    assert rep['spacing_m'] <= 0.50 and len(lines) == rep['count'] == 11
    assert all(a[1] == pytest.approx(0.0) and b[1] == pytest.approx(4.0) for a, b in lines)
    sec = rep['section']
    assert sec['ok'] and sec['deflection_mm'] <= sec['deflection_limit_mm'] and sec['sigma_mpa'] <= sec['f_md_mpa']
    # The chosen section is the smallest that passes: the one before it fails.
    from archforge.structure.joists import SECTIONS
    k = SECTIONS.index((sec['b'], sec['h']))
    assert k == 0 or not check_section(*SECTIONS[k - 1], 4.0, rep['spacing_m'], 'ceiling')['ok']
    floor = size_joists(dict(params, usage='floor'))
    assert floor['section']['h'] > sec['h']                                          # heavier use, deeper joist
    assert 'στατικό' in rep['provenance']


def test_too_long_span_gives_technical_proposals_and_a_fix_when_one_exists():
    doc = Document(); stack = CommandStack(doc)
    j = joists_entity([(0, 0), (10, 0), (10, 9), (0, 9)], 0.0, usage='floor')
    stack.execute(AddEntity(j))
    rep = size_joists(doc.get(j.id).params)
    assert not rep['ok'] and any('Ενδιάμεση δοκός' in p for p in rep['proposals'])
    warn = next(p for p in propose(doc) if p.key == f'J-2:{j.id}')
    assert warn.severity == 'warning'


def test_room_under_pitched_roof_gets_joists_and_they_follow_commands():
    from archforge.structure.timber_roof import default_params
    doc = Document(); stack = CommandStack(doc); _house(stack)
    stack.execute(AddEntity(Entity('pitched_roof', default_params(doc))))
    props = [p for p in propose(doc) if p.key.startswith('J-1')]
    assert len(props) == 2
    apply(stack, props[0])
    j = next(e for e in doc.entities.values() if e.kind == 'ceiling_joists')
    before = positions(doc.get(j.id).params)
    stack.execute(UpdateEntity(j.id, {'spacing': 0.30}))
    assert len(positions(doc.get(j.id).params)) > len(before)
    stack.execute(MoveEntities([j.id], 1.0, 0.0))
    assert positions(doc.get(j.id).params)[0][0][0] == pytest.approx(before[0][0][0] + 1.0, abs=0.2)
    roles = [p.role for p in build_plan_frame(doc).primitives]
    assert 'joist' in roles and 'joists-label' in roles


def test_joists_render_in_3d_under_the_wall_tops():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); stack = CommandStack(doc); _house(stack)
    j = joists_entity([(0, 0), (5, 0), (5, 6), (0, 6)], 0.0)
    stack.execute(AddEntity(j))
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    mine = [o for o in objs if o.get('id') == j.id]
    assert mine
    zs = [v[2] for o in mine for v in o['vertices']]
    assert max(zs) == pytest.approx(2.7)


def test_panel_lists_proposals_applies_and_joist_tool_works():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        _house(window.stack)
        _plumb(window.stack, 'wc', 6.0, 5.6)
        window._refresh_assistant()
        titles = [window.assistant_list.item(i).text() for i in range(window.assistant_list.count())]
        assert any('χωρίς απαγωγή' in t for t in titles)
        assert 'WC' in window.assistant_reading.text()
        row = next(i for i, p in enumerate(window._assistant_proposals) if p.key.startswith('V-1'))
        window.assistant_list.setCurrentRow(row)
        assert window.assistant_apply.isEnabled()
        window._apply_assistant_proposal()
        assert any(e.kind == 'ventilation_point' for e in window.doc.entities.values())
        window._start_site_tool('assist_joists', '')
        window.plan_view.sitePointRequested.emit('assist_joists', 2.0, 3.0)
        assert sum(e.kind == 'ceiling_joists' for e in window.doc.entities.values()) == 1
        window.plan_view.sitePointRequested.emit('assist_joists', 2.0, 3.0)          # same room: not twice
        assert sum(e.kind == 'ceiling_joists' for e in window.doc.entities.values()) == 1
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_fixtures_without_a_source_are_one_grouped_proposal():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _plumb(stack, 'shower', 7.5, 5.5); _plumb(stack, 'basin', 6.0, 5.6)
    grouped = [p for p in propose(doc) if p.key.startswith('M-1')]
    assert len(grouped) == 1 and '4 συνδέσεις' in grouped[0].title
