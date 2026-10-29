"""PDF output: cover, plans with dimensions, take-off and the client quote; prices kept in the Document."""
import os
import shutil
import subprocess

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.quantities.quote import money, quote


def _house(stack):
    ws = []
    for a in [(0, 0, 10, 0), (10, 0, 10, 8), (10, 8, 0, 8), (0, 8, 0, 0), (6, 0, 6, 8)]:
        w = Entity('wall', dict(x1=a[0], y1=a[1], x2=a[2], y2=a[3], z=0.0, height=3.0, thickness=.3 if a[0] != 6 else .12))
        stack.execute(AddEntity(w)); ws.append(w)
    stack.execute(AddEntity(Entity('window', {'offset': 3.0, 'width': 1.6, 'height': 1.4, 'sill': .9}, parent_id=ws[0].id)))
    stack.execute(AddEntity(Entity('door', {'offset': 8.0, 'width': 1.0, 'height': 2.1}, parent_id=ws[0].id)))
    return ws


def test_money_is_greek_formatted():
    assert money(1234.5) == '1.234,50 €' and money(None) == '—' and money(0) == '0,00 €'


def test_quote_prices_items_adds_vat_and_counts_missing_prices():
    doc = Document(); st = CommandStack(doc); _house(st)
    q0 = quote(doc)
    assert q0['subtotal'] == 0 and q0['missing'] > 0
    paint = next(it for _t, items in q0['sections'] for it in items if it['description'] == 'Βαφή τοίχων')
    st.execute(AddEntity(Entity('price_list', {'prices': {'Βαφή τοίχων': 6.5}, 'client': 'Πελάτης', 'vat': 24})))
    q = quote(doc)
    assert q['subtotal'] == pytest.approx(round(paint['quantity'] * 6.5, 2))
    assert q['vat_amount'] == pytest.approx(round(q['subtotal'] * .24, 2)) and q['total'] == pytest.approx(q['subtotal'] + q['vat_amount'])
    assert q['missing'] == q0['missing'] - 1 and q['client'] == 'Πελάτης'
    with pytest.raises(ValueError):
        doc.add(Entity('price_list', {'vat': -5}))


def test_pdf_has_cover_plan_per_storey_takeoff_and_quote(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.output.pdf import export_pdf, level_name, wall_pieces
    app = QApplication.instance() or QApplication([])
    doc = Document(); st = CommandStack(doc); ws = _house(st)
    st.execute(AddEntity(Entity('price_list', {'prices': {'Βαφή τοίχων': 6.5}, 'client': 'Γ. Παπαδόπουλος', 'project': 'Κατοικία'})))
    pieces, holes = wall_pieces(doc, ws[0], ws)
    assert len(pieces) == 3 and len(holes) == 2                       # the front wall cut by a window and a door
    assert level_name('Ground') == 'Ισόγειο' and level_name('Floor 2') == '1ος όροφος'
    from archforge.architecture.dimensions import set_auto
    st.execute(set_auto(doc, 0.0, exterior=True))
    path = tmp_path / 'ergo.pdf'
    r = export_pdf(doc, path)
    assert r['pages'] == 4 and r['scales'] == [100]
    data = path.read_bytes()
    assert data[:5] == b'%PDF-' and len(data) > 5000
    if shutil.which('pdftotext'):
        proc = subprocess.run(['pdftotext', '-enc', 'UTF-8', '-layout', str(path), '-'],
                              capture_output=True, text=True, encoding='utf-8', check=True)
        text = proc.stdout
        for s in ('Κατοικία', 'Κάτοψη — Ισόγειο', '1:100', '10,30', 'Επιμέτρηση', 'Προσφορά', 'ΦΠΑ 24%', 'Γ. Παπαδόπουλος'):
            assert s in text, s


def test_price_dialog_saves_prices_in_one_undo_and_the_menu_exports(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.quantities.quote import settings
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow(); window._no_modal_dialogs = True
    try:
        _house(window.stack)
        dialog, table, client, project, vat, validity, notes = (None,) * 7
        window._edit_prices()
        dialog, table, client, *_ = window._prices_dialog
        rows = {table.item(i, 0).text(): i for i in range(table.rowCount())}
        assert 'Βαφή τοίχων' in rows
        table.item(rows['Βαφή τοίχων'], 3).setText('7,5')
        client.setText('Πελάτης Α')
        window._apply_prices_dialog()
        s = settings(window.doc)
        assert s['prices']['Βαφή τοίχων'] == 7.5 and s['client'] == 'Πελάτης Α'
        window.stack.undo()
        assert not settings(window.doc)['prices']
        r = window._export_pdf(str(tmp_path / 'x'))
        assert r['pages'] >= 3 and (tmp_path / 'x.pdf').exists()
        assert window._pdf_action.text().startswith('Εξαγωγή PDF')
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_the_pdf_plan_is_the_plan_view_drawing():
    """One drawing (owner 28/10): the PDF prints the plan view's frame — minus only the screen aids — so what the
    plan switches off or hides is not printed either."""
    from archforge.architecture import dimensions as D
    from archforge.core.model import WorkPlane
    from archforge.core.plan_scene import build_plan_frame
    from archforge.output.pdf import plan_frame
    doc = Document(); st = CommandStack(doc); ws = _house(st)
    roles = lambda: [p.role for p, _k in plan_frame(doc, 0.0)]
    assert 'wall-poche' in roles() and 'opening-symbol' in roles() and 'derived-room-label' in roles()
    assert not {'opening', 'preview', 'floor-underlay'} & set(roles())
    assert not any(p.kind == 'line' and k == 'wall' for p, k in plan_frame(doc, 0.0))     # axis pick lines
    # Every printed primitive is one the plan view draws.
    screen = build_plan_frame(doc).primitives
    assert all(p in screen for p, _k in plan_frame(doc, 0.0))
    # Dimensions: only when the plan shows them, exactly as switched there.
    assert 'dimension' not in roles()
    st.execute(D.set_auto(doc, 0.0, exterior=True))
    assert 'dimension' in roles()
    st.execute(D.set_auto(doc, 0.0, exterior=False))
    assert 'dimension' not in roles()
    # Hidden: a hidden wall leaves the cut region; selection does not change the print.
    poche = lambda: [p for p, _k in plan_frame(doc, 0.0) if p.role == 'wall-poche']
    before = poche()
    doc.selection = [ws[4].id]
    assert poche() == before and doc.selection == [ws[4].id]
    doc.get(ws[4].id).visible = False
    assert poche() != before
    # The storey being worked on is left as it was.
    doc.work_plane = WorkPlane(name='x', origin=(0, 0, 3.0))
    plan_frame(doc, 0.0)
    assert doc.work_plane.origin[2] == 3.0


def test_pdf_leaves_off_what_the_plan_view_hides():
    """A hidden wall is not printed; a hidden window still cuts its wall but draws no symbol — as in the plan view."""
    from archforge.output.pdf import _storey_walls, wall_pieces
    doc = Document(); st = CommandStack(doc); ws = _house(st)
    ids = lambda: {w.id for w in _storey_walls(doc, 0.0)}
    assert ws[4].id in ids()
    doc.get(ws[4].id).visible = False
    assert ws[4].id not in ids() and len(ids()) == 4
    window = next(e for e in doc.entities.values() if e.kind == 'window')
    window.visible = False
    pieces, holes = wall_pieces(doc, doc.get(ws[0].id), _storey_walls(doc, 0.0))
    assert len(pieces) == 3 and any(e.id == window.id for _a, _b, e, _f in holes)


def test_a_storey_without_dimensions_is_reported_before_printing(tmp_path):
    """Owner 29/10: «ένα σχέδιο χωρίς διαστάσεις δεν είναι σχέδιο» — the export says which storeys have none and can
    add their exterior dimensions with the CAD ▸ Διαστάσεις command (one undo) before printing."""
    from PySide6.QtWidgets import QApplication
    from archforge.output.pdf import add_exterior_dimensions, export_pdf, undimensioned_storeys
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    doc = Document(); st = CommandStack(doc); _house(st)
    assert [s['z'] for s in undimensioned_storeys(doc)] == [0.0]
    assert export_pdf(doc, tmp_path / 'a.pdf', include=('plans',))['undimensioned'] == ['Ισόγειο']

    class Window:                                   # the export path of MainWindow, without its window
        _no_modal_dialogs = True
        def __init__(self):
            self.doc, self.stack, self.messages = doc, st, []
        def statusBar(self):
            return self
        def showMessage(self, text, _ms=0):
            self.messages.append(text)
        def _redraw_views(self, all_views=False):
            pass
    w = Window()
    assert MainWindow._export_pdf(w, str(tmp_path / 'b'), missing_dimensions='cancel') is None
    assert not (tmp_path / 'b.pdf').exists() and 'ακυρώθηκε' in w.messages[-1]
    r = MainWindow._export_pdf(w, str(tmp_path / 'c'))                      # no dialogs: prints, and says so
    assert r['undimensioned'] == ['Ισόγειο'] and 'χωρίς διαστάσεις: Ισόγειο' in w.messages[-1]
    r = MainWindow._export_pdf(w, str(tmp_path / 'd'), missing_dimensions='add')
    assert r['undimensioned'] == [] and not undimensioned_storeys(doc) and (tmp_path / 'd.pdf').exists()
    st.undo()                                                               # one undo takes them away again
    assert undimensioned_storeys(doc)
    st.execute(add_exterior_dimensions(doc, undimensioned_storeys(doc)))
    assert not undimensioned_storeys(doc)


def test_each_expression_of_the_plan_gets_its_own_sheet():
    """Owner 29/10: «κάθε layer έχει δική του έκφραση· αν τα βάλουμε όλα μαζί δεν θα βλέπεις τίποτα» — the plan
    and every MEP trade on sheets of their own (the structure: the formwork), through the plan view's environments (core/layers.py);
    a sheet only when the storey has something of its own."""
    from archforge.core.layers import primitive_layer
    from archforge.output.pdf import plan_storeys, storey_sheets
    from archforge.project.persistence import load_project
    doc = load_project('tests/residential_scenarios/S10_full_system_family_residence.archforge').doc
    ground = plan_storeys(doc)[0]
    sheets = dict(storey_sheets(doc, float(ground['z']))[0])
    assert list(sheets) == ['arch', 'plumbing', 'electrical']             # the structure: the formwork sheets
    assert {'plumbing', 'drainage'} <= {primitive_layer(doc, p) for p, _k in sheets['plumbing']}  # «Υδραυλικά»: both
    layers = lambda key, dim=None: {primitive_layer(doc, p) for p, _k in sheets[key]
                                    if dim is None or bool(dict(p.meta).get('layer_dim')) == dim}
    mep = {'electrical', 'low_voltage', 'plumbing', 'drainage', 'heating', 'ventilation'}
    assert not layers('arch') & mep                                       # the plan: no networks
    assert layers('electrical') & mep == {'electrical'}                   # one network per sheet …
    poche = lambda key: [dict(p.meta).get('layer_dim', False) for p, _k in sheets[key] if p.role == 'wall-poche']
    assert poche('electrical') and all(poche('electrical'))               # … over a faint plan
    assert poche('arch') and not any(poche('arch'))                       # the plan itself is not faint
    # No heating on this storey → no heating sheet; a house without MEP prints only its plan.
    assert 'heating' not in sheets
    plain = Document(); _house(CommandStack(plain))
    assert [k for k, _i in storey_sheets(plain, 0.0)[0]] == ['arch']
