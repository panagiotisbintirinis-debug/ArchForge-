"""Ζωντανές λίστες (κριτική v5 k9): καρτέλα, όχι modal· αμφίδρομη επιλογή· «πώς μετρήθηκε»· έλεγχος πληρότητας."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.quantities import schedules as S

OWNER = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')


def _house(doc, st):
    ids = {}
    for name, (a, b) in {'s': ((0, 0), (6, 0)), 'e': ((6, 0), (6, 5)), 'n': ((6, 5), (0, 5)), 'w': ((0, 5), (0, 0)),
                         'mid': ((3, 0), (3, 5))}.items():
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 2.7, 'thickness': 0.25})
        st.execute(AddEntity(e)); ids[name] = e.id
    for key, kind, host, off, w, h in (('w1', 'window', 's', 1.0, 1.2, 1.2), ('w2', 'window', 'n', 1.0, 0.8, 1.0),
                                        ('d1', 'door', 'mid', 1.5, 0.9, 2.1)):
        p = {'offset': off, 'width': w, 'height': h}
        if kind == 'window':
            p['sill'] = 0.9
        e = Entity(kind, p, parent_id=ids[host]); st.execute(AddEntity(e)); ids[key] = e.id
    return ids


def test_openings_get_codes_rooms_sizes_and_how_they_were_measured():
    doc = Document(); st = CommandStack(doc); ids = _house(doc, st)
    d = S.openings(doc)
    by_id = {r['ids'][0]: r for r in d['rows']}
    assert {by_id[ids['w1']]['mark'], by_id[ids['w2']]['mark']} == {'Π1', 'Π2'} and by_id[ids['d1']]['mark'] == 'Θ1'
    assert by_id[ids['w1']]['area'] == pytest.approx(1.44) and by_id[ids['w1']]['storey'] == 'Ισόγειο'
    assert '1,20 × ύψος 1,20' in by_id[ids['w1']]['how']
    assert by_id[ids['d1']]['rooms'].count('/') == 1                    # a door between two rooms names both
    assert any('αυτόματο κωδικό' in c for c in d['check'])
    # The user's own code stays; automatic codes skip it.
    st.execute(S.set_mark_command(doc, ids['w2'], 'Π1'))
    d = S.openings(doc)
    marks = {r['ids'][0]: r['mark'] for r in d['rows']}
    assert marks[ids['w2']] == 'Π1' and marks[ids['w1']] == 'Π2'
    with pytest.raises(ValueError):
        S.set_mark_command(doc, ids['w1'], 'Π1')                         # a code is used once
    st.undo()
    assert S.openings(doc)['rows'][0]['auto_mark']


def test_rooms_list_says_what_is_missing_and_a_name_gives_the_use():
    doc = Document(); st = CommandStack(doc); _house(doc, st)
    d = S.rooms(doc)
    assert len(d['rows']) == 2 and any('χωρίς χρήση' in c for c in d['check'])
    assert any('χωρίς τύπο' in c for c in d['check'])
    sig = d['rows'][0]['signature']
    st.execute(S.rename_room_command(doc, sig, 'Μπάνιο'))
    row = next(r for r in S.rooms(doc)['rows'] if r['signature'] == sig)
    assert row['name'] == 'Μπάνιο' and row['use'] == 'Μπάνιο' and row['wall_tiles'] > 0   # tiles appear with the use
    st.undo()
    assert next(r for r in S.rooms(doc)['rows'] if r['signature'] == sig)['wall_tiles'] == 0


def test_envelope_and_circuits_on_the_owner_project():
    from archforge.project.persistence import load_project
    doc = load_project(OWNER).doc
    env = S.envelope(doc)
    walls = [r for r in env['rows'] if r['element'] == 'Εξωτερικός τοίχος']
    assert walls and all('m²' in r['how'] for r in walls)
    assert any(r['element'] == 'Θερμογέφυρα' for r in env['rows'])
    assert any('χωρίς σύνθεση' in c for c in env['check'])               # owner_111 walls are «Γενικός»
    cir = S.circuits(doc)
    assert cir['rows'] and all(r['ids'] for r in cir['rows'])
    assert any('δεν είναι κρατημένη' in c for c in cir['check'])


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1300, 900); w.show(); app.processEvents()
    yield w, app
    w._mark_clean(); w.close(); app.processEvents()


def test_the_tab_is_live_and_selection_goes_both_ways(window):
    from archforge.ui import live_lists
    w, app = window
    ids = _house(w.doc, w.stack)
    tab = live_lists.show(w, 'openings') and w._lists_tab
    assert w._central_tabs.currentWidget() is tab and tab.key == 'openings'
    assert tab.table.rowCount() == 3
    # Row → drawing.
    row = next(r for r, d in enumerate(tab.data['rows']) if d['ids'] == [ids['d1']])
    tab.table.selectRow(row); app.processEvents()
    assert w.doc.selection == [ids['d1']]
    # Drawing → row.
    w.doc.select([ids['w1']]); w.plan_view.selectionChangedByView.emit(); app.processEvents()
    chosen = {i.row() for i in tab.table.selectedItems()}
    assert chosen == {next(r for r, d in enumerate(tab.data['rows']) if d['ids'] == [ids['w1']])}
    # Live: a change in the drawing, then undo.
    w.stack.execute(UpdateEntity(ids['w1'], {'width': 1.5})); tab._timer.timeout.emit()
    assert any(d['width'] == 1.5 for d in tab.data['rows'])
    w.stack.undo(); tab._timer.timeout.emit()
    assert not any(d['width'] == 1.5 for d in tab.data['rows'])
    # Edit in place: the code, one undo.
    col = [k for k, _l in tab.data['columns']].index('mark')
    tab.table.item(row, col).setText('Θ-εισόδου'); app.processEvents()
    assert w.doc.get(ids['d1']).params['mark'] == 'Θ-εισόδου'
    w.stack.undo(); tab.refresh()
    assert not w.doc.get(ids['d1']).params.get('mark')
    # Other lists from the same bar.
    for key in ('envelope', 'rooms', 'circuits'):
        assert tab.show_list(key) is not None and tab.key == key
    assert w._lists_action.text().startswith('Λίστες')


def test_lists_go_to_pdf_and_excel_as_shown(window, tmp_path):
    import zipfile
    from archforge.ui import live_lists
    w, app = window
    ids = _house(w.doc, w.stack)
    w.stack.execute(S.set_mark_command(w.doc, ids['d1'], 'Θ-εισόδου'))
    tab = w._lists_tab
    live_lists.show(w, 'openings')
    pdf = tab.export_pdf(str(tmp_path / 'one'), keys=['openings'])
    assert pdf.endswith('.pdf') and open(pdf, 'rb').read(5) == b'%PDF-' and os.path.getsize(pdf) > 2000
    html = S.html(w.doc, ['openings'])
    assert 'Θ-εισόδου' in html and 'Πώς μετρήθηκε' in html and 'αυτόματο κωδικό' in html
    assert all(S.LISTS[k](w.doc)['title'] in S.html(w.doc) for k in S.LISTS)
    xlsx = tab.export_xlsx(str(tmp_path / 'all'))
    with zipfile.ZipFile(xlsx) as z:
        book = z.read('xl/workbook.xml').decode()
        assert all(f'name="{t}"' in book for t in ('Κουφώματα', 'Κέλυφος', 'Χώροι', 'Κυκλώματα'))
        sheet = z.read('xl/worksheets/sheet1.xml').decode()
        assert 'Θ-εισόδου' in sheet and '<v>1.2</v>' in sheet            # numbers stay numbers
    try:
        import openpyxl
    except ImportError:
        return
    ws = openpyxl.load_workbook(xlsx)['Κουφώματα']
    assert any(row[0] == 'Θ-εισόδου' for row in ws.iter_rows(values_only=True))


def test_each_window_carries_its_own_uw_into_the_envelope_and_the_heating_power():
    from archforge.mep.heat_load import heat_load
    doc = Document(); st = CommandStack(doc); ids = _house(doc, st)
    before = heat_load(doc)
    assert dict(before['parts'])['Κουφώματα'] == 0 and any(n.startswith('κουφώματα ') for n in before['not_counted'])
    assert any('χωρίς Uw' in c for c in S.openings(doc)['check'])
    st.execute(S.set_u_command(doc, ids['w1'], '1,4'))                 # the maker's figure, typed
    after = heat_load(doc)
    assert dict(after['parts'])['Κουφώματα'] == pytest.approx(1.2 * 1.2 * 1.4 * after['delta_t'], abs=1)
    row = next(r for r in S.envelope(doc)['rows'] if r['ids'] == [ids['w1']])
    assert row['element'] == 'Κούφωμα' and row['loss'] == pytest.approx(1.2 * 1.2 * 1.4, abs=0.01)
    assert 'του κουφώματος' in row['how']
    with pytest.raises(ValueError):
        S.set_u_command(doc, ids['w2'], '0')
    st.execute(S.set_u_command(doc, ids['w1'], ''))                     # empty: the project's value again
    assert doc.get(ids['w1']).params.get('u_value') is None
    st.undo(); st.undo()
    assert doc.get(ids['w1']).params.get('u_value') is None
