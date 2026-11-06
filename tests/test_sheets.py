"""Φύλλα σχεδίων (κενό 4 της αποτύπωσης, 06/11): κατόψεις, τομές, λίστες, σημειώσεις σε A4…A0 με πινακίδα, PDF."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.output import sheets as SH

OWNER = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')


@pytest.fixture(scope='module')
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _owner():
    from archforge.project.persistence import load_project
    r = load_project(OWNER)
    return r[0] if isinstance(r, tuple) else getattr(r, 'doc', r)


def test_params_are_checked():
    doc = Document()
    s = SH.new_sheet(doc, 'Κατόψεις', 'A2', 'portrait', [{'type': 'plan', 'ref': 0}, {'type': 'list', 'ref': 'openings'}])
    assert s.params['number'] == 'Α-01' and SH.paper_mm(s.params) == (420.0, 594.0)
    for bad in ({'paper': 'B5'}, {'orientation': 'diagonal'}, {'views': [{'type': 'photo'}]},
                {'views': [{'type': 'plan', 'ref': 0, 'scale': 75}]}, {'views': [{'type': 'note', 'text': ' '}]}):
        with pytest.raises(ValueError):
            SH.validate({'paper': 'A3', **bad})


def test_one_scale_for_every_plan_that_fits_and_what_does_not_is_said(app):
    doc = _owner()
    views = [{'type': 'plan', 'ref': 0.0}, {'type': 'plan', 'ref': 3.0}, {'type': 'list', 'ref': 'openings'},
             {'type': 'note', 'text': 'Διαστάσεις σε μέτρα.'}]
    big = SH.layout(doc, SH.validate({'paper': 'A1', 'views': views}))
    small = SH.layout(doc, SH.validate({'paper': 'A3', 'views': views}))
    assert not big['problems'] and not small['problems']
    assert {m['scale'] for v, m, _ in big['placed'] if v['type'] == 'plan'} == {big['scale']}
    assert big['scale'] < small['scale']                                  # A1 draws larger (1:50) than A3
    fixed = SH.layout(doc, SH.validate({'paper': 'A4', 'views': [{'type': 'plan', 'ref': 0.0, 'scale': 20}]}))
    assert fixed['problems'] and 'δεν χωρά' in fixed['problems'][0][1]
    gone = SH.layout(doc, SH.validate({'paper': 'A3', 'views': [{'type': 'section', 'ref': 'nope'}]}))
    assert gone['problems'][0][1] == 'η τομή δεν υπάρχει πια'
    # the list on a sheet carries its main columns only
    m = next(m for v, m, _ in big['placed'] if v['type'] == 'list')
    assert m['data'][0][0] == 'Κωδικός' and len(m['data'][0]) == len(SH.SHEET_COLUMNS['openings'])


def test_pdf_pages_at_their_paper_size_with_a_section(app, tmp_path):
    from pypdf import PdfReader
    doc = _owner(); st = CommandStack(doc)
    sec = Entity('section_line', {'x1': -2.0, 'y1': 5.0, 'x2': 15.0, 'y2': 5.0, 'flip': 0}, name='Τομή Α-Α')
    st.execute(AddEntity(sec))
    st.execute(AddEntity(SH.new_sheet(doc, 'Κατόψεις', 'A1', views=[{'type': 'plan', 'ref': 0.0}, {'type': 'plan', 'ref': 3.0}])))
    st.execute(AddEntity(SH.new_sheet(doc, 'Τομή', 'A3', views=[{'type': 'section', 'ref': sec.id}])))
    lay = SH.layout(doc, SH.sheets_of(doc)[1].params)
    assert lay['placed'] and not lay['problems']
    path = tmp_path / 's.pdf'
    r = SH.export_sheets(doc, str(path))
    assert r['pages'] == 2 and not r['problems']
    pages = PdfReader(str(path)).pages
    mm = lambda v: float(v) / 72 * 25.4
    assert (round(mm(pages[0].mediabox.width)), round(mm(pages[0].mediabox.height))) == (841, 594)
    assert (round(mm(pages[1].mediabox.width)), round(mm(pages[1].mediabox.height))) == (420, 297)
    text = ' '.join(pages[0].extract_text().split())
    assert 'Φύλλο Α-01' in text and 'ΚΑΤΟΨΗ ΙΣΟΓΕΙΟ' in text                 # capitals without accents
    assert SH.greek_upper('Κάτοψη Ισογείου · Προϊόν') == 'ΚΑΤΟΨΗ ΙΣΟΓΕΙΟΥ · ΠΡΟΪΟΝ'
    with pytest.raises(ValueError):
        SH.export_sheets(Document(), str(tmp_path / 'none.pdf'))


def test_the_dialog_builds_a_sheet_with_one_undo_per_change(app, tmp_path):
    from archforge.ui.main_window import MainWindow
    from archforge.ui import sheets_dialog
    w = MainWindow(); w.show(); app.processEvents()
    try:
        w._no_modal_dialogs = True
        w._open_checked(OWNER); app.processEvents()
        n0 = len(w.stack.done)
        dlg = sheets_dialog.show(w)
        dlg.add_sheet()
        dlg.add_plan(0.0); dlg.add_plan(3.0); dlg.add_list('openings'); dlg.add_note('Σημείωση')
        sheet = SH.sheets_of(w.doc)[0]
        assert [v['type'] for v in sheet.params['views']] == ['plan', 'plan', 'list', 'note']
        assert dlg.preview.pixmap() is not None and dlg.views.rowCount() == 4
        dlg.set_param('paper', 'A1')
        dlg.set_view(0, 'scale', 100)
        assert SH.sheets_of(w.doc)[0].params['views'][0]['scale'] == 100
        dlg.views.selectRow(3); dlg.move_view(-1)
        assert SH.sheets_of(w.doc)[0].params['views'][2]['type'] == 'note'
        assert len(w.stack.done) == n0 + 8                                 # sheet, 4 views, paper, scale, move: one each
        w.stack.undo()
        assert SH.sheets_of(w.doc)[0].params['views'][2]['type'] == 'list'
        r = dlg.export(str(tmp_path / 'f.pdf'))
        assert r['pages'] == 1
        assert w._sheets_action is not None
        dlg.close()
    finally:
        w._mark_clean(); w.close(); app.processEvents()
