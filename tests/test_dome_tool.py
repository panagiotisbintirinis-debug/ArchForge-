"""Owner 21/10: «Θόλοι Bio-Spectre — η μηχανή υπάρχει, κανένα εργαλείο στο UI».

Κατασκευή ▸ Θόλοι Bio-Spectre: a dome / a dome on top / the canonical cluster with a plan click, one undo
each; where two domes overlap their shells become one flat shared partition, which follows later moves."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.organic import domes as D


def _active(doc):
    return {e.params['junction_key']: e.id for e in doc.entities.values()
            if e.kind == 'organic_junction' and e.params.get('status') == 'active'}


def test_shell_height_and_a_dome_resting_on_it():
    p = D.dome_params(0.0, 0.0, 0.0, diameter=8.0, height=4.0)
    assert D.shell_height_at(p, 0.0, 0.0) == pytest.approx(4.0)
    assert D.shell_height_at(p, 2.0, 0.0) == pytest.approx(4.0 * math.sqrt(1 - 0.25))     # ellipsoid: z = h·√(1 − (d/R)²)
    assert D.shell_height_at(p, 4.5, 0.0) is None
    doc = Document(); doc.add(Entity('pod', p))
    assert D.resting_level(doc, 0.0, 0.0) == pytest.approx(4.0)
    assert D.resting_level(doc, 10.0, 0.0) == 0.0                                           # nothing below → the storey


def test_sync_is_undoable_and_redo_keeps_the_same_junction():
    doc = Document(); stack = CommandStack(doc)
    a = Entity('pod', D.dome_params(0, 0, 0, 6, 3)); b = Entity('pod', D.dome_params(5, 0, 0, 6, 3))
    stack.execute(AddEntity(a)); stack.execute(AddEntity(b))
    assert D.junctions_out_of_date(doc) and not _active(doc)
    stack.execute(D.SyncOrganicJunctions())
    first = _active(doc)
    assert len(first) == 1 and not D.junctions_out_of_date(doc)
    stack.undo()
    assert not _active(doc)
    stack.redo()
    assert _active(doc) == first


def _window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    return app, MainWindow()


def test_menu_place_two_domes_partition_follows_a_move():
    from archforge.core.commands import MoveEntities
    from archforge.ui import dome_tool
    app, w = _window()
    try:
        assert [a.text() for a in w._dome_menu.actions()][0].startswith('Θόλος')
        walls = next(a.menu() for a in w._build_menu.actions() if a.text().startswith('Τοίχοι'))
        assert w._dome_menu.menuAction() in walls.actions()
        spec = {'kind': 'dome', 'diameter': 6.0, 'depth': 6.0, 'height': 3.2, 'shell': 0.018}
        dome_tool.start(w, 'dome', spec)
        assert w.plan_view.controller.tool == 'dome_place'
        w.plan_view.sitePointRequested.emit('dome_place', 0.0, 0.0)
        before = len(w.stack.done)
        second = dome_tool.place(w, 5.0, 0.0)
        assert len(w.stack.done) == before + 1                              # dome + its partition = one undo
        assert len(_active(w.doc)) == 1
        # Moving the second dome away: the partition goes dormant in the same undo step as the move.
        w.stack.execute(MoveEntities([second[0].id], 6.0, 0.0))
        assert not _active(w.doc) and len(w.stack.done) == before + 2
        w._undo()
        assert len(_active(w.doc)) == 1
        w._undo()
        assert sum(1 for e in w.doc.entities.values() if e.kind == 'pod') == 1 and not _active(w.doc)
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_upper_dome_sits_on_the_shell_and_the_cluster_joins():
    from archforge.ui import dome_tool
    app, w = _window()
    try:
        assert dome_tool.place(w, 20.0, 20.0, {'kind': 'upper', 'diameter': 4.0, 'height': 3.0}) == []   # nothing below
        pods = dome_tool.place(w, 0.0, 0.0, {'kind': 'cluster', 'upper': True})
        assert len(pods) == 5 and pods[0].name.startswith('Κεντρικός')
        assert len(_active(w.doc)) >= 3                                     # every peripheral dome shares a flat wall
        expected = max(D.shell_height_at(p.params, 0.0, 0.0) or 0.0 for p in pods)
        top = dome_tool.place(w, 0.0, 0.0, {'kind': 'upper', 'diameter': 4.0, 'height': 3.0})
        assert top[0].params['floor_level'] == pytest.approx(expected) and expected >= 4.5   # on the highest shell
        w._undo(); w._undo()
        assert not any(e.kind == 'pod' for e in w.doc.entities.values()) and not _active(w.doc)
    finally:
        w._mark_clean(); w.close(); app.processEvents()
