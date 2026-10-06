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
    path = tmp_path / 'ergo.pdf'
    r = export_pdf(doc, path)
    assert r['pages'] == 4 and r['scales'] == [100]
    data = path.read_bytes()
    assert data[:5] == b'%PDF-' and len(data) > 5000
    if shutil.which('pdftotext'):
        text = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, text=True).stdout
        for s in ('Κατοικία', 'Κάτοψη — Ισόγειο', '1:100', '10.30', 'Επιμέτρηση', 'Προσφορά', 'ΦΠΑ 24%', 'Γ. Παπαδόπουλος'):
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
