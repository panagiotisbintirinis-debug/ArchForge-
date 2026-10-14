"""Owner (2026-10-14): a wrong storey ("4ος όροφος −2,50") must be deletable from the project tree."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, DeleteStorey
from archforge.core.model import Document, Entity, WorkPlane
from archforge.ui.project_outline import _levels, storey_entities


def _wall(stack, z, x=0.0):
    w = Entity('wall', {'x1': x, 'y1': 0, 'x2': x + 4, 'y2': 0, 'z': z, 'height': 2.7, 'thickness': 0.2})
    stack.execute(AddEntity(w))
    return w.id


def test_delete_storey_removes_level_and_its_entities_in_one_undo():
    doc = Document()
    doc.levels = {'Υπόγειο': -2.70, '4ος όροφος': -2.50, 'Ισόγειο': 0.0}
    stack = CommandStack(doc)
    keep = _wall(stack, 0.0)
    wrong = _wall(stack, -2.50)
    base = _wall(stack, -2.70)
    doc.work_plane = WorkPlane(name='4ος όροφος', origin=(0.0, 0.0, -2.50))
    ids = storey_entities(doc, '4ος όροφος')
    assert ids == [wrong]
    stack.execute(DeleteStorey('4ος όροφος', ids))
    assert '4ος όροφος' not in doc.levels and wrong not in doc.entities
    assert keep in doc.entities and base in doc.entities
    assert [n for n, _ in _levels(doc)] == ['Υπόγειο', 'Ισόγειο']     # not re-inferred from a leftover wall
    assert doc.work_plane.name == 'Υπόγειο' and doc.work_plane.origin[2] == -2.70
    stack.undo()
    assert doc.levels['4ος όροφος'] == -2.50 and wrong in doc.entities
    assert doc.work_plane.name == '4ος όροφος'
    stack.redo()
    assert '4ος όροφος' not in doc.levels and wrong not in doc.entities


def test_only_storey_cannot_be_deleted():
    doc = Document()
    stack = CommandStack(doc)
    with pytest.raises(ValueError):
        stack.execute(DeleteStorey('Ground', []))
    assert doc.levels == {'Ground': 0.0}


def test_right_click_on_a_storey_offers_delete_storey():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow(); window._no_modal_dialogs = True
    try:
        _wall(window.stack, 0.0)
        window.doc.levels['4ος όροφος'] = -2.5
        window._refresh_project_tree()
        tree = window.project_tree
        root = tree.topLevelItem(0)
        item = next(root.child(i) for i in range(root.childCount())
                    if root.child(i).data(0, 0x0100 + 1) == '4ος όροφος')
        menu = window._project_tree_menu(tree.visualItemRect(item).center())
        assert menu is not None
        action = next(a for a in menu.actions() if a.text().startswith('Διαγραφή ορόφου'))
        action.trigger()
        assert '4ος όροφος' not in window.doc.levels
        assert all(window.floor_selector.itemData(i)[0] != '4ος όροφος' for i in range(window.floor_selector.count()))
        window._undo()
        assert window.doc.levels['4ος όροφος'] == -2.5
    finally:
        window._mark_clean(); window.close(); app.processEvents()
