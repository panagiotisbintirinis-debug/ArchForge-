"""Υδραυλικός υπολογισμός θέρμανσης (07/11): το «δίκτυο Υ» της κριτικής ως τεστ αναφοράς, με αριθμούς με το χέρι."""
import pytest

from archforge.core.model import Document, Entity
from archforge.mep.heating_hydraulics import hydraulics, pipe, water


def test_water_at_70_degrees():
    rho, mu, cp = water(70)
    assert (rho, mu, cp) == pytest.approx((977.8, 0.404e-3, 4190))


def test_the_symmetric_y_network_by_hand():
    """2 + 2 kW σε δύο κλάδους Φ16 (εσωτ. 12 mm) 10 m, κεντρικός Φ20 (16 mm) 5 m, 80/60 °C:
    ṁ = 2000 / (4190 · 20) = 85,9 kg/h · v = 0,216 m/s · Re ≈ 6260 · f ≈ 0,0358 · Δp ≈ 679 Pa / κλάδο ·
    κεντρικός 171,8 kg/h, 289 Pa."""
    a, b = pipe(2000, 0.012, 10, 80, 60), pipe(2000, 0.012, 10, 80, 60)
    main = pipe(4000, 0.016, 5, 80, 60)
    assert a == b                                                   # symmetry: exactly the same
    assert a['kg_h'] == pytest.approx(85.92, abs=0.05) and a['v'] == pytest.approx(0.216, abs=0.001)
    assert a['re'] == pytest.approx(6263, rel=0.01) and a['f'] == pytest.approx(0.0358, abs=0.0005)
    assert a['dp_pa'] == pytest.approx(679, rel=0.01)
    assert main['kg_h'] == pytest.approx(a['kg_h'] + b['kg_h'])     # mass conservation
    assert main['dp_pa'] == pytest.approx(289, rel=0.01)


def test_laminar_and_no_flow():
    slow = pipe(50, 0.016, 10, 40, 35)
    assert slow['re'] < 2300 and slow['f'] == pytest.approx(64 / slow['re'])
    assert pipe(0, 0.012, 10, 70, 50)['dp_pa'] == 0
    with pytest.raises(ValueError):
        pipe(1000, 0.012, 10, 50, 50)


def test_the_manifold_carries_the_sum_of_its_circuits():
    doc = Document()
    doc.add(Entity('design_climate', {'heat_theta_int': 20.0, 'heat_theta_ext_winter': 0.0, 'heat_theta_ext_summer': 28.0,
                                      'heat_air_changes': 0.5, 'heat_u_walls': 0.5, 'heat_u_roof': 0.4, 'heat_u_floor': 0.4}))
    for a, b in (((0, 0), (8, 0)), ((8, 0), (8, 4)), ((8, 4), (0, 4)), ((0, 4), (0, 0)), ((4, 0), (4, 4))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 3.0, 'thickness': 0.25}))
    doc.add(Entity('heating_point', {'x': -1.0, 'y': 2.0, 'z': 0.0, 'point_type': 'boiler'}))
    for x in (2.0, 6.0):
        doc.add(Entity('heating_point', {'x': x, 'y': 0.4, 'z': 0.0, 'point_type': 'radiator'}))
    h = hydraulics(doc)
    (m,) = h['manifolds']
    a, b = m['circuits']
    assert a['load_w'] == pytest.approx(b['load_w']) and a['load_w'] > 0           # the two rooms are alike
    assert a['kg_h'] == pytest.approx(b['kg_h'])
    assert m['kg_h'] == pytest.approx(a['kg_h'] + b['kg_h'])
    assert m['index_dp_pa'] == max(a['dp_pa'], b['dp_pa']) > 0
    assert h['temps'] == (70.0, 50.0, 'υπόθεση (DESIGN_DEFAULT)')
    assert 'εξισορρόπηση' in h['not_counted']


def test_from_the_heating_menu_with_the_sources_temperatures_in_one_undo():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from archforge.core.commands import AddEntity
    from archforge.ui.main_window import MainWindow
    w = MainWindow()
    try:
        boiler = Entity('heating_point', {'x': -1.0, 'y': 2.0, 'z': 0.0, 'point_type': 'boiler'})
        w.stack.execute(AddEntity(boiler))
        acts = w.menuBar().actions()
        for name in ('Εγκαταστάσεις', 'Θέρμανση'):
            a = next(x for x in acts if x.text().replace('&', '') == name)
            a.menu().aboutToShow.emit(); acts = a.menu().actions()
        next(x for x in acts if x.text() == 'Υδραυλικός υπολογισμός…').trigger()
        d = w._heating_hydraulics_dialog
        assert 'Δεν υπάρχουν κυκλώματα' in d.text.toPlainText()
        d.supply.setValue(55.0); d.ret.setValue(45.0); d.apply()
        src = w.doc.get(boiler.id).params
        assert (src['flow_temp'], src['return_temp']) == (55.0, 45.0)
        w.stack.undo()
        assert 'flow_temp' not in w.doc.get(boiler.id).params
        d.close()
    finally:
        w._mark_clean(); w.close()
