"""Σ2 (κριτική v5, Η/Μ): «έβαλα 3 πρίζες και το πλυντήριο πήγε από Κ6 σε Κ7, ενώ το Κ5 άλλαξε σύνθεση».

«Κράτα την αρίθμηση» writes each point's circuit into the Document (one undo); new points get new numbers only,
the kept circuits keep their number and their points.  «Επαναρίθμηση» groups and numbers everything afresh.
"""
from archforge.core.commands import CommandStack
from archforge.core.model import Document
from archforge.mep.electrical import design_circuits, keep_circuit_numbers

from test_electrical import _house, _pt


def _plan(doc):
    return {c["id"]: sorted(c["points"]) for c in design_circuits(doc)["circuits"]}


def _setup():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    for x, y in [(0.3, 1), (0.3, 5), (2, 5.8), (6, 0.3), (7.7, 2)]:
        _pt(stack, 'socket', x, y)
    for x, y in [(2, 3), (6, 3)]:
        _pt(stack, 'light', x, y)
    washer = _pt(stack, 'washing_machine', 7.7, 5)
    return doc, stack, washer


def _id_of(doc, pid):
    return next(c["id"] for c in design_circuits(doc)["circuits"] if pid in c["points"])


def test_kept_numbers_stay_and_new_points_take_new_numbers_or_join_their_room():
    doc, stack, washer = _setup()
    stack.execute(keep_circuit_numbers(doc))
    kept = _plan(doc)
    assert design_circuits(doc)["report"]["numbers_kept"]
    assert keep_circuit_numbers(doc) is None                   # nothing to write twice
    new = [_pt(stack, 'socket', x, y) for x, y in [(1, 0.3), (2, 0.3), (3, 0.3), (3.7, 1)]]
    now = _plan(doc)
    for cid, pts in kept.items():
        assert set(pts) <= set(now[cid])                         # every kept circuit: same number, same points
    assert _id_of(doc, washer.id) == next(c for c, p in kept.items() if washer.id in p)
    added = {_id_of(doc, s.id) for s in new}
    top = max(int(c[1:]) for c in kept)
    assert all(c in kept or int(c[1:]) > top for c in added)    # into a kept circuit of the room, or after the last
    assert sorted(i for p in now.values() for i in p) == sorted([i for p in kept.values() for i in p] + [s.id for s in new])
    # One undo takes the kept numbers away.
    for _ in range(5):
        stack.undo()
    assert not design_circuits(doc)["report"]["numbers_kept"]


def test_renumber_counts_afresh_from_k1():
    doc, stack, washer = _setup()
    stack.execute(keep_circuit_numbers(doc))
    for x, y in [(1, 0.3), (2, 0.3), (3, 0.3), (3.7, 1)]:
        _pt(stack, 'socket', x, y)
    stack.execute(keep_circuit_numbers(doc, renumber=True))
    ids = [c["id"] for c in design_circuits(doc)["circuits"]]
    assert ids == [f"Κ{i}" for i in range(1, len(ids) + 1)]
    assert _plan(doc) == {c["id"]: sorted(c["points"]) for c in design_circuits(doc, keep_numbers=False)["circuits"]}


def test_menu_commands_keep_and_renumber_with_one_undo():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); app.processEvents()
    try:
        _house(w.stack); _pt(w.stack, 'panel', 0.3, 3.0)
        s = _pt(w.stack, 'socket', 0.3, 1); _pt(w.stack, 'washing_machine', 7.7, 5)
        acts = w._circuit_number_actions
        assert acts['keep'] in w._mockup_electrical_menu.actions()
        acts['keep'].trigger(); app.processEvents()
        assert w.doc.get(s.id).params['circuit'] == _id_of(w.doc, s.id)
        acts['renumber'].trigger(); app.processEvents()             # already 1…n: nothing to write
        w.stack.undo()
        assert 'circuit' not in w.doc.get(s.id).params or not w.doc.get(s.id).params['circuit']
    finally:
        w._mark_clean(); w.close(); app.processEvents()
