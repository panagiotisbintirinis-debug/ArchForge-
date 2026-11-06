"""Άνεμος της περιοχής (ΤΟΤΕΕ 20701-3) και έκθεση μπαλκονιών / όψεων (ιδιοκτήτης 06/11)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntities, AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep import totee_20701_3_site as TS
from archforge.site import solar_study as SS
from archforge.site import wind as W


def test_the_official_tables_spot_checked():
    """Δείγματα ελεγμένα στο PDF της ΤΟΤΕΕ 20701-3/2010 (Πίν. 1.1, 3.11, Α.1)."""
    assert TS.STATIONS['Ηράκλειο'][:3] == (pytest.approx(35 + 20 / 60, abs=1e-3), pytest.approx(25 + 11 / 60, abs=1e-3), 39.3)
    assert TS.STATIONS['Αθήνα (Ν. Φιλαδέλφεια)'][:2] == (pytest.approx(38.05, abs=1e-3), pytest.approx(23 + 40 / 60, abs=1e-3))
    assert TS.WIND_SPEED['Νάξος'] == (7.9, 8.1, 7.6, 5.9, 4.9, 5.0, 6.6, 6.9, 7.0, 7.4, 6.7, 7.5)
    assert TS.WIND_SPEED['Αθήνα (Ελληνικό)'][0] == 3.9
    assert TS.APPENDIX_A['Ηράκλειο']['months'][7] == ('ΒΔ', 2.9, 12.5, 21.7, 28.8, 43.6)
    assert TS.APPENDIX_A['Ηράκλειο']['months'][1][:2] == ('Ν', 2.9)
    assert TS.APPENDIX_A['Αθήνα (Ν. Φιλαδέλφεια)']['months'][7][:2] == ('ΒΑ', 2.2)      # not the shifted «Δ»
    assert TS.APPENDIX_A['Σέρρες']['months'][7][3] == 17.0                               # «17» without decimals in the PDF
    assert len(TS.APPENDIX_A) == 30 and all(len(v['months']) == 4 for v in TS.APPENDIX_A.values())
    assert all(m[0] in TS.DIRECTIONS for v in TS.APPENDIX_A.values() for m in v['months'].values())


def test_exposure_sectors():
    assert W.exposure(0, 'Β') == 'εκτεθειμένη' and W.exposure(45, 'Β') == 'εκτεθειμένη'
    assert W.exposure(90, 'Β') == 'πλάγια' and W.exposure(180, 'Β') == 'υπήνεμη' and W.exposure(200, 'ΒΑ') == 'υπήνεμη'


def _house_with_balconies():
    from archforge.architecture.balcony import balcony_entities
    doc = Document(); st = CommandStack(doc)
    for a, b in (((0, 0), (8, 0)), ((8, 0), (8, 6)), ((8, 6), (0, 6)), ((0, 6), (0, 0))):
        for z in (0.0, 3.0):
            st.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': z, 'height': 3.0,
                                                 'thickness': 0.25})))
    north = balcony_entities(doc, [(2, 6.125), (6, 6.125), (6, 7.6), (2, 7.6)], 3.0)
    south = balcony_entities(doc, [(2, -1.5), (6, -1.5), (6, -0.125), (2, -0.125)], 3.0)
    st.execute(AddEntities(north)); st.execute(AddEntities(south))
    return doc, st, north[0], south[0]


def test_balconies_facing_the_wind_or_sheltered_with_sun_and_temperatures():
    doc, st, north, south = _house_with_balconies()
    st.execute(W.set_command(doc, winter='Β', summer='Ν'))           # the user's own directions
    res = W.balcony_study(doc)
    rows = {(r['id'], r['month']): r for r in res['rows']}
    assert rows[(north.id, 1)]['exposure'] == 'εκτεθειμένο' and rows[(north.id, 1)]['wind']['from'] == 'δική σας'
    assert rows[(south.id, 1)]['exposure'] == 'προστατευμένο από το κτίριο'           # the house is upwind of it
    assert rows[(south.id, 7)]['exposure'] == 'εκτεθειμένο' and rows[(north.id, 7)]['exposure'] == 'προστατευμένο από το κτίριο'
    assert rows[(south.id, 1)]['sun_h'] > rows[(north.id, 1)]['sun_h'] + 3                # the winter sun on the south one
    assert rows[(north.id, 1)]['wind']['mean_max'] is not None                            # temperatures of the month (Αθήνα)
    st.undo()
    back = W.climate(doc)['months'][1]
    assert back['dir'] == 'ΒΑ' and 'Παρ. Α' in back['from']                               # ΤΟΤΕΕ again
    with pytest.raises(ValueError):
        W.set_command(doc, winter='ΒΒΑ')


def test_latitude_from_the_station_and_notes_without_one():
    doc = Document(); st = CommandStack(doc)
    s = SS.site(doc)
    assert s['latitude'] == pytest.approx(38.05, abs=1e-3) and 'σταθμός' in s['latitude_from']
    from archforge.mep.design_climate import set_command
    st.execute(set_command(doc, {'preset': 'totee:Ηράκλειο'}))
    assert SS.site(doc)['latitude'] == pytest.approx(35.333, abs=1e-3)
    assert W.climate(doc)['months'][7]['dir'] == 'ΒΔ'
    st.execute(set_command(doc, {'preset': 'totee:Βόλος'}))
    if W.station(doc) == 'Βόλος':
        assert W.climate(doc)['notes'] and W.climate(doc)['months'][1]['dir'] is None
    note = W.facade_note(doc, (0, 1))
    assert note == '' or 'Rse' in note


def test_the_dialog_shows_the_wind_the_compass_and_the_balconies():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); app.processEvents()
    try:
        doc, st, north, south = _house_with_balconies()
        for e in doc.entities.values():
            w.stack.execute(AddEntity(Entity(e.kind, dict(e.params), parent_id=e.parent_id, name=e.name, id=e.id)))
        w._solar_action.trigger(); app.processEvents()
        dlg = w._solar_dialog
        assert dlg.tabs.count() == 3 and dlg.wind_table.rowCount() == 4
        assert dlg.wind_table.item(0, 1).text() == 'ΒΑ' and 'Ν. Φιλαδέλφεια' in dlg.station.text()
        dlg.winter_dir.setCurrentIndex(dlg.winter_dir.findData('Β')); dlg.save_wind()
        assert dlg.wind_table.item(0, 1).text() == 'Β' and dlg.compass.winter == 'Β'
        res = dlg.run_balconies()
        assert dlg.balcony_table.rowCount() == len(res['rows']) == 8
        dlg.compass.grab()                                                   # paints
        w.stack.undo()
        assert W.climate(w.doc)['months'][1]['dir'] == 'ΒΑ'
        dlg.close()
    finally:
        w._mark_clean(); w.close(); app.processEvents()
