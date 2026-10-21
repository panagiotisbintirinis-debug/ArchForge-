"""Owner 18/10 «Βήμα 2»: ζωντανός έλεγχος ποιότητας — the scenarios' gate as a panel on the project being drawn,
with «Δείξε μου» and «Διόρθωση»; it must never touch the project, the undo history or the disk."""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.scenarios import live_gate as L
from archforge.scenarios.gate import FAIL


def _window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    return app, MainWindow()


def _box(w):
    for s in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0)]:
        w.stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0.0,
                                                  'height': 2.8, 'thickness': 0.25})))


def test_names_are_matched_as_whole_words():
    from archforge.core.model import Document
    doc = Document()
    k3, k30 = Entity('structural_column', {}, name='Κ3'), Entity('structural_column', {}, name='Κ30')
    doc.entities[k3.id] = k3; doc.entities[k30.id] = k30
    assert L.named_ids(doc, 'Κόμβος Κ3 / X') == (k3.id,)
    assert set(L.named_ids(doc, 'χωρίς στήριξη: Κ3, Κ30')) == {k3.id, k30.id}
    assert L.fix_for('Κολόνες') == 'frame' and L.fix_for('Δάπεδο σε κάθε όροφο') == 'complete' and L.fix_for('Άλλο') is None


def test_live_run_leaves_project_history_and_disk_alone(tmp_path, monkeypatch):
    app, w = _window()
    try:
        _box(w)
        monkeypatch.chdir(tmp_path)
        before = json.dumps(w.doc.to_dict(), sort_keys=True, default=str)
        done, undone = len(w.stack.done), len(w.stack.undone)
        results = L.run(w)
        assert json.dumps(w.doc.to_dict(), sort_keys=True, default=str) == before
        assert (len(w.stack.done), len(w.stack.undone)) == (done, undone) and not os.listdir(tmp_path)
        items = [r.item for r in results]
        assert not any(i.startswith(L.PROGRAM_CHECKS) for i in items)
        cols = next(r for r in results if r.item == 'Κολόνες')
        assert cols.status == FAIL and cols.fix == 'frame'                     # walls, no frame yet
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_panel_from_the_view_menu_shows_and_fixes():
    from archforge.ui import quality_panel as Q
    app, w = _window()
    try:
        assert w._quality_action.text() == 'Έλεγχος ποιότητας' and not w._quality_dock.isVisible()
        _box(w)
        panel = w._quality_panel
        results = panel.refresh()
        assert panel.summary.text().startswith('✖ ')
        rows = [panel.tree.topLevelItem(i).child(j) for i in range(panel.tree.topLevelItemCount())
                for j in range(panel.tree.topLevelItem(i).childCount())]
        assert rows and all(r.text(0).startswith('✖') for r in rows)               # «Μόνο προβλήματα»
        cols = next(r for r in rows if r.text(0) == '✖ Κολόνες')
        panel.tree.setCurrentItem(cols)
        assert panel.fix_button.isEnabled() and panel.fix_button.text() == 'Πρόταση φέροντος'
        before = len(w.stack.done)
        panel._fix(cols)
        assert any(e.kind == 'structural_column' for e in w.doc.entities.values()) and len(w.stack.done) > before
        again = panel.refresh()
        assert next(r for r in again if r.item == 'Κολόνες').status != FAIL
        named = next((r for r in again if r.ids), None)
        if named is not None:                                                    # «Δείξε μου» selects what it names
            assert Q.show_me(w, named.ids) and set(w.doc.selection) == set(named.ids)
        panel.only_problems.setChecked(False)
        assert panel.tree.topLevelItemCount() >= 2
    finally:
        w._mark_clean(); w.close(); app.processEvents()
