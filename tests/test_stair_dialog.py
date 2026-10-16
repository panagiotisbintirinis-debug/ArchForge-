"""Owner (2026-10-14): «κάνε ένα παρόμοιο μενού» (stair window) · structure options (slab, timber, steel,
cantilever steps from the wall) with space underneath · railing that follows the stair · materials per part."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture import stair_options as SO
from archforge.architecture.stairs import solve_stair_candidates
from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.geometry.mesh import _stair_mesh


def _params(layout='straight'):
    return next(c for c in solve_stair_candidates(0.0, 2.72, (1.0, 1.0), (6.0, 1.0)) if c.layout == layout).to_params()


@pytest.mark.parametrize('layout', ['straight', 'l', 'u'])
def test_every_structure_but_solid_leaves_the_space_under_the_stair_free(layout):
    p = _params(layout)
    probe_z = 0.6                                    # a cupboard height, under the middle of the first flight

    def blocks(mesh):
        # any triangle reaching down to <= probe_z under the first flight's middle third?
        return any(min(mesh.vertices[i][2] for i in tri) <= probe_z < max(mesh.vertices[i][2] for i in tri)
                   for tri in mesh.triangles)
    assert blocks(_stair_mesh(dict(p, structure='solid')))
    for kind in ('slab', 'timber', 'steel', 'cantilever'):
        m = _stair_mesh(dict(p, structure=kind))
        high = [v for v in m.vertices if v[2] > 1.2]
        low_under_top = [v for v in m.vertices if 0.05 < v[2] < 0.5 and v[0] > p['x'] + 2.0]
        assert high and not low_under_top, kind      # nothing low except near the start of the flight


def test_cantilever_steps_go_into_the_wall_side():
    p = _params()
    left = _stair_mesh(dict(p, structure='cantilever', cantilever_side='left'))
    right = _stair_mesh(dict(p, structure='cantilever', cantilever_side='right'))
    assert max(v[1] for v in left.vertices) == pytest.approx(p['y'] + p['width'] / 2 + SO.EMBED)
    assert min(v[1] for v in right.vertices) == pytest.approx(p['y'] - p['width'] / 2 - SO.EMBED)
    assert set(left.triangle_surfaces) == {'tread'}


def test_materials_per_part_default_from_the_structure_and_the_humans_choice_wins():
    p = dict(_params(), structure='steel')
    assert SO.role_material_id(p, 'stringer') == 'steel_black' and SO.role_material_id(p, 'tread') == 'wood_oak'
    p['surface_materials'] = {'tread': 'wood_walnut'}
    assert SO.role_material_id(p, 'tread') == 'wood_walnut'


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def test_window_changes_structure_risers_railing_and_material_in_one_undo(window):
    from archforge.ui.marking_menu import build_menu
    from archforge.ui.stair_dialog import open_stair_dialog
    stair = Entity('stair', _params(), name='Stair'); window.stack.execute(AddEntity(stair))
    assert build_menu(window, 'plan', stair.id)['entries'][0]['id'] == 'mm:stairdlg:open'
    d = open_stair_dialog(window, stair.id)
    d.kind.setCurrentIndex(d.kind.findData('timber'))
    d.risers.setValue(17)
    d.left.setChecked(True); d.right.setChecked(True)
    d.sections.setCurrentRow(3)
    combo = d.material_form.itemAt(0, d.material_form.ItemRole.FieldRole).widget()
    combo.setCurrentIndex(combo.findData('wood_walnut'))
    before = len(window.stack.done)
    d.apply()
    p = window.doc.get(stair.id).params
    assert p['structure'] == 'timber' and p['riser_count'] == 17
    assert p['riser_count'] * p['riser_height'] == pytest.approx(p['upper_z'] - p['lower_z'])
    assert SO.railing_choice(window.doc, stair.id) == 'both'
    assert 'wood_walnut' in (p.get('surface_materials') or {}).values()
    assert len(window.stack.done) == before + 1
    window._undo()
    p = window.doc.get(stair.id).params
    assert SO.structure(p) == 'solid' and SO.railing_choice(window.doc, stair.id) == 'none'


def test_inspector_shows_a_summary_not_raw_numbers(window):
    from PySide6.QtWidgets import QDoubleSpinBox
    stair = Entity('stair', _params(), name='Stair'); window.stack.execute(AddEntity(stair))
    window.doc.select([stair.id]); window.refresh_inspector()
    spins = [w for w in window.form.parentWidget().findChildren(QDoubleSpinBox) if w.isVisibleTo(window.form.parentWidget())]
    assert not any(abs(w.value() - stair.params['riser_height']) < 1e-9 for w in spins)


def test_cantilever_without_a_wall_beside_it_is_flagged():
    from archforge.core.commands import CommandStack
    from archforge.core.model import Document
    from archforge.architecture.railings import stair_railing_lines
    doc = Document(); stack = CommandStack(doc)
    p = dict(_params(), structure='cantilever')
    assert not SO.cantilever_has_wall(doc, p)
    y = stair_railing_lines(p, 'left')[0][0][1]
    stack.execute(AddEntity(Entity('wall', {'x1': 0.0, 'y1': y + 0.12, 'x2': 9.0, 'y2': y + 0.12, 'z': 0.0,
                                            'height': 2.7, 'thickness': 0.2})))
    assert SO.cantilever_side(doc, p) == 'left' and SO.cantilever_has_wall(doc, p)


def test_cupboards_under_the_stair_follow_its_slope_and_face_the_open_side():
    from archforge.core.commands import CommandStack
    from archforge.core.model import Document
    doc = Document(); stack = CommandStack(doc)
    stair = Entity('stair', dict(_params(), structure='slab')); stack.execute(AddEntity(stair))
    command, new = SO.under_stair_command(doc, stair.id); stack.execute(command)
    hs = [e.params['height'] for e in new]
    assert len(new) >= 3 and hs == sorted(hs) and min(hs) >= SO.UNDER_MIN - 1e-9 and max(hs) <= SO.UNDER_MAX
    p = stair.params; pitch = p['riser_height'] / p['tread_depth']
    for e in new:                                   # the top follows the slope, just under the underside
        q = e.params
        s0, s1 = q['x'] - q['width'] / 2 - p['x'], q['x'] + q['width'] / 2 - p['x']
        for s, hh in ((s0, q['height']), (s1, q['height_end'])):
            under = s * pitch + SO.underside_offset(p)
            assert hh <= under + 1e-6 and (hh >= under - SO.UNDER_GAP - 0.01 or hh == SO.UNDER_MAX)
    from archforge.kitchen.cabinets import cabinet_mesh
    v = cabinet_mesh(new[1].params)[0]
    tops = sorted(v, key=lambda q: -q[2])[:4]
    assert max(q[2] for q in tops) - min(q[2] for q in v if q[2] > 0.3 and abs(q[0] - min(t[0] for t in v)) < 1e-6) > 0.2
    stack.execute(__import__('archforge.core.commands', fromlist=['DeleteEntities']).DeleteEntities([stair.id]))
    assert not any(e.kind == 'cabinet' for e in doc.entities.values())          # they go with the stair
    with pytest.raises(ValueError):
        SO.under_stair_cabinets(doc, Entity('stair', _params()))                 # solid: no space


def test_window_adds_cupboards_with_the_structure_change_in_one_undo(window):
    from archforge.ui.stair_dialog import open_stair_dialog
    stair = Entity('stair', _params(), name='Stair'); window.stack.execute(AddEntity(stair))
    d = open_stair_dialog(window, stair.id)
    d.kind.setCurrentIndex(d.kind.findData('timber')); d.cabinets.setChecked(True)
    before = len(window.stack.done)
    d.apply()
    assert SO.has_under_stair_cabinets(window.doc, stair.id) and len(window.stack.done) == before + 1
    window._undo()
    assert not SO.has_under_stair_cabinets(window.doc, stair.id) and SO.structure(window.doc.get(stair.id).params) == 'solid'
