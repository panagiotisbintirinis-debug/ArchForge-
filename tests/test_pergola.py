"""Pergola dragged as a rectangle: posts, beams and rafters; fixed to a wall where it runs along one."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.pergola import attached_sides, pergola_entities
from archforge.core.commands import AddEntities, AddEntity, CommandStack
from archforge.core.model import Document, Entity


def _house(stack):
    for s in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0)]:
        stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0.0, 'height': 2.7, 'thickness': 0.3})))


def test_free_standing_pergola_has_posts_at_corners_and_every_3m_and_rafters_every_50cm():
    doc = Document()
    ents, rep = pergola_entities(doc, 10, 0, 16.5, 4)                     # 6.5 × 4 m in the garden
    posts = [e for e in ents if e.kind == 'structural_column']
    assert rep['posts'] == len(posts) == 10                               # 3 bays on 6.5 m, 2 on 4 m
    assert all(e.params['role'] == 'pergola' and e.params['construction'] == 'timber' for e in ents)
    rafters = [e for e in ents if e.name == 'Τεγίδα πέργκολας']
    assert len(rafters) == rep['rafters'] == 12 and all(abs(e.params['x1'] - e.params['x2']) < 1e-9 for e in rafters)
    with pytest.raises(ValueError):
        pergola_entities(doc, 0, 0, .5, 3)


def test_side_along_a_wall_is_fixed_to_it_without_posts():
    doc = Document(); st = CommandStack(doc); _house(st)
    assert attached_sides(doc, 1, 6.2, 7, 9.5, 0.0) == {'S'}
    ents, rep = pergola_entities(doc, 1, 6.2, 7, 9.5, material='aluminium')
    posts = [e for e in ents if e.kind == 'structural_column']
    assert rep['fixed'] == ['S'] and all(e.params['y'] > 6.3 for e in posts)
    assert any('στον τοίχο' in e.name for e in ents) and ents[0].params['construction'] == 'aluminium'
    st.execute(AddEntities(ents))
    from archforge.structure.analysis.building import read_members
    members, _ex = read_members(doc)
    assert not any(doc.get(i).params['role'] == 'pergola' for i in members)   # not part of the frame analysis


def test_menu_tool_drags_a_pergola_in_one_undo_and_roofs_are_in_the_ribbon_menus():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        _house(window.stack)
        assert [a.text() for a in window._mockup_pergola_menu.actions()] == ['Ξύλινη', 'Αλουμινίου']
        assert window._roof_menu.menuAction() in window._mockup_auto_menu.actions()
        assert window._roof_menu.menuAction() in window._mockup_elements_menu.actions()
        window._mockup_pergola_menu.actions()[0].trigger()
        assert window.plan_view.controller.tool == 'pergola_timber'
        window.plan_view.siteLineRequested.emit('pergola_timber', 1.0, 6.2, 7.0, 9.5)
        n = sum(e.params.get('role') == 'pergola' for e in window.doc.entities.values())
        assert n > 10
        window.stack.undo()
        assert not any(e.params.get('role') == 'pergola' for e in window.doc.entities.values())
    finally:
        window._mark_clean(); window.close(); app.processEvents()
