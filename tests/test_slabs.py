"""Slab reinforcement per room panel (Marcus), for load-bearing masonry and frames."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.structure.slabs import design_slabs


def _house(stack):
    for s in [(0, 0, 12, 0), (12, 0, 12, 6), (12, 6, 0, 6), (0, 6, 0, 0), (5, 0, 5, 6)]:
        stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0, 'height': 2.7, 'thickness': 0.2})))


def test_marcus_two_way_panel_matches_hand_calculation():
    doc = Document(); st = CommandStack(doc); _house(st)
    p = next(p for p in design_slabs(doc)['panels'] if p['lx'] == 5.0)
    # Roof slab 18 cm: g = 4.5 + 2.0, q = 2.0 → pd = 11.78; ε = 1.2 → κx = 0.675, ν = 0.61
    assert p['pd'] == pytest.approx(11.78, abs=0.01) and p['kind'].startswith('δύο')
    kx = 1.2 ** 4 / (1 + 1.2 ** 4); nu = 1 - 5 / 6 * 1.44 / (1 + 1.2 ** 4)
    assert p['M_short'] == pytest.approx(kx * 11.775 * 25 / 14.2 * nu, abs=0.02)   # one continuous edge (x = 5)
    assert p['M_support'] == pytest.approx(kx * 11.775 * 25 / 8, abs=0.05)
    assert p['bottom_short'].startswith('Ø') and p['top_support'] != '—' and p['ok']


def test_one_way_strip_and_thin_slab_warning():
    doc = Document(); st = CommandStack(doc)
    for s in [(0, 0, 9, 0), (9, 0, 9, 3), (9, 3, 0, 3), (0, 3, 0, 0)]:
        st.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0, 'height': 2.7, 'thickness': 0.2})))
    p = design_slabs(doc)['panels'][0]
    assert p['kind'] == 'μιας διεύθυνσης' and p['M_long'] == 0.0
    assert p['M_short'] == pytest.approx(p['pd'] * 9 / 8, abs=0.02)                 # simply supported 3 m
    st.execute(AddEntity(Entity('structural_design', {'slab_thickness': 0.10})))
    big = Document(); s2 = CommandStack(big)
    for s in [(0, 0, 7, 0), (7, 0, 7, 7), (7, 7, 0, 7), (0, 7, 0, 0)]:
        s2.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0, 'height': 2.7, 'thickness': 0.2})))
    s2.execute(AddEntity(Entity('structural_design', {'slab_thickness': 0.12})))
    thin = design_slabs(big)['panels'][0]
    assert not thin['ok'] and thin['h_required'] > 0.12 and '⚠' in thin['text']


def test_timber_floors_have_no_slab_and_stone_house_gets_slab_proposal():
    from archforge.assistant.suggestions import propose
    doc = Document(); st = CommandStack(doc); _house(st)
    st.execute(AddEntity(Entity('project_brief', {'project_type': 'new', 'wall_system': 'stone_bearing',
                                                  'measure': 'exterior', 'floor_system': 'rc_slab'})))
    s4 = next(p for p in propose(doc) if p.key == 'S-4')
    assert s4.run == 'slabs' and s4.actionable
    brief = next(e for e in doc.entities.values() if e.kind == 'project_brief')
    from archforge.core.commands import UpdateEntity
    st.execute(UpdateEntity(brief.id, {'floor_system': 'timber'}))
    assert design_slabs(doc)['panels'] == []
    assert next(p for p in propose(doc) if p.key == 'S-4').run is None


def test_menu_and_report():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        assert any(a.text() == 'Οπλισμός πλακών…' for a in w._structure_menu.actions())
        _house(w.stack)
        w._no_modal_dialogs = True
        r = w._show_slabs()
        assert len(r['panels']) == 2 and 'Πλάκες (οπλισμός ανά φάτνωμα)' in w._slabs_view.toHtml()
    finally:
        w._mark_clean(); w.close(); app.processEvents()
