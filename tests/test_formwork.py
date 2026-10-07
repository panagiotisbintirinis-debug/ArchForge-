import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntities, CommandStack, RenameEntities
from archforge.core.model import Document, Entity
from archforge.structure.analysis.building import read_members
from archforge.structure.layout import propose_frame
from archforge.structure.marks import renumber


def _house(doc, z=0.0, level='Ground'):
    for a, b in (((0, 0), (10, 0)), ((10, 0), (10, 8)), ((10, 8), (0, 8)), ((0, 8), (0, 0)), ((5, 0), (5, 8))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'thickness': .25, 'height': 3, 'z': z, 'level': level}))


def _framed():
    doc = Document(); _house(doc)
    entities, _report = propose_frame(doc)
    CommandStack(doc).execute(AddEntities(entities))
    return doc


def test_every_member_has_its_own_mark_shared_with_the_analysis():
    doc = _framed()
    cols = [e for e in doc.entities.values() if e.kind == 'structural_column']
    beams = [e for e in doc.entities.values() if e.kind == 'structural_beam']
    assert cols and beams
    assert sorted(int(c.name[1:]) for c in cols) == list(range(1, len(cols) + 1))
    assert all(c.name.startswith('Κ') for c in cols) and all(b.name.startswith('Δ') for b in beams)
    # Κ1 is top-left in plan (reading order).
    k1 = next(c for c in cols if c.name == 'Κ1')
    assert float(k1.params['y']) == max(float(c.params['y']) for c in cols)
    members, _ = read_members(doc)
    assert {m.name for m in members.values()} == {e.name for e in cols + beams}


def test_a_column_drawn_by_hand_gets_the_next_mark_and_user_names_stay():
    doc = _framed()
    n = sum(e.kind == 'structural_column' for e in doc.entities.values())
    extra = Entity('structural_column', {'x': 2.5, 'y': 4, 'z': 0, 'width': .3, 'depth': .3, 'height': 3, 'rotation': 0,
                                         'role': 'structural', 'construction': 'reinforced_concrete', 'section': 'rectangular',
                                         'base_level': 'Ground', 'top_level': 'Unassigned'}, name='Column')
    doc.add(extra)
    assert extra.name == f'Κ{n + 1}'
    stack = CommandStack(doc)
    stack.execute(RenameEntities({extra.id: 'Κ-γωνία'}))
    assert doc.get(extra.id).name == 'Κ-γωνία'
    assert extra.id not in renumber(doc)                  # the user's name is kept
    members, _ = read_members(doc)
    assert members[extra.id].name == 'Κ-γωνία'
    stack.undo()
    assert doc.get(extra.id).name == f'Κ{n + 1}'


def test_renumber_closes_gaps_in_reading_order():
    doc = _framed()
    first = next(e for e in doc.entities.values() if e.name == 'Κ1')
    del doc.entities[first.id]
    names = renumber(doc)
    CommandStack(doc).execute(RenameEntities(names))
    cols = [e for e in doc.entities.values() if e.kind == 'structural_column']
    assert sorted(int(c.name[1:]) for c in cols) == list(range(1, len(cols) + 1))


def test_formwork_sheet_per_storey(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.output.formwork import export_formwork_pdf, storey_frames
    app = QApplication.instance() or QApplication([])
    doc = _framed()
    frames = storey_frames(doc)
    assert len(frames) == 1
    f = frames[0]
    assert f['columns'] and f['beams']
    assert all(b.name.startswith('Δ') for b in f['beams'])
    r = export_formwork_pdf(doc, tmp_path / 'xt.pdf')
    assert r['pages'] == 1 and (tmp_path / 'xt.pdf').stat().st_size > 2000


def test_formwork_needs_a_frame(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.output.formwork import export_formwork_pdf
    app = QApplication.instance() or QApplication([])
    doc = Document(); _house(doc)
    try:
        export_formwork_pdf(doc, tmp_path / 'x.pdf')
        assert False
    except ValueError as exc:
        assert 'Πρόταση φέροντος' in str(exc)


def test_name_is_edited_in_properties_and_menu_has_formwork(tmp_path):
    from PySide6.QtWidgets import QApplication, QLineEdit
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    _house(window.doc)
    window._no_modal_dialogs = True
    entities, _ = propose_frame(window.doc)
    window.stack.execute(AddEntities(entities))
    k1 = next(e for e in window.doc.entities.values() if e.name == 'Κ1')
    window.doc.select([k1.id]); window.refresh_inspector()
    edit = next(window.form.itemAt(i, window.form.ItemRole.FieldRole).widget() for i in range(window.form.rowCount())
                if isinstance(window.form.itemAt(i, window.form.ItemRole.FieldRole).widget(), QLineEdit))
    assert edit.text() == 'Κ1'
    window._rename_entity(k1.id, 'Κ2')                     # taken: refused
    assert window.doc.get(k1.id).name == 'Κ1'
    window._rename_entity(k1.id, 'ΚΓ1')
    assert window.doc.get(k1.id).name == 'ΚΓ1'
    labels = [a.text() for a in window._structure_menu.actions()]
    assert 'Φύλλο ξυλοτύπου (PDF)…' in labels and 'Αρίθμηση κολονών / δοκών (Κ1, Δ1 …)' in labels
    r = window._export_formwork(str(tmp_path / 'x'))
    assert r['pages'] == 1 and (tmp_path / 'x.pdf').exists()
    window._mark_clean(); window.close(); app.processEvents()
