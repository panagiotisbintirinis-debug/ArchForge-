"""Έργο αναφοράς «κουτί ελέγχου» (07/11): ένας χώρος 4 × 5 m, ύψος 3 m, ένα νότιο παράθυρο 2 × 1,5 m, ΔT = 20 K.

Τα νούμερα εδώ βγαίνουν **με το χέρι** από τους τύπους (ΤΟΤΕΕ 20701-2: U = 1 / (Rsi + Σ d/λ + Rse), Rsi = 0,13,
Rse = 0,04 για τοίχο· απώλεια = A·U·ΔT· αερισμός 0,34·n·V·ΔT) και τα δεδομένα (στρώσεις, λ) — όχι από τον κώδικα
του προγράμματος.  Αν αλλάξει ένας πίνακας ή μια παραδοχή, το τεστ το λέει.
"""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.model import Document, Entity  # noqa: E402

L, W, H, T = 5.0, 4.0, 3.0, 0.25
WIN_W, WIN_H, UW = 2.0, 1.5, 1.8
DT, N_AIR = 20.0, 0.5


def _box():
    d = Document()
    d.add(Entity('design_climate', {'heat_theta_int': 20.0, 'heat_theta_ext_winter': 0.0,
                                    'heat_theta_ext_summer': 28.0, 'heat_air_changes': N_AIR}))
    pts = [(0, 0), (L, 0), (L, W), (0, W)]                  # axes: 5 × 4 m (y = 0 is south)
    walls = []
    for a, b in zip(pts, pts[1:] + pts[:1]):
        w = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': H,
                            'thickness': T, 'wall_type': 'brick_double_insulated'})
        d.add(w); walls.append(w)
    d.add(Entity('window', {'offset': L / 2, 'width': WIN_W, 'height': WIN_H, 'sill': 0.9, 'u_value': UW},
                 parent_id=walls[0].id))
    return d


def _u_by_hand(doc):
    from archforge.architecture.wall_types import layers
    rows = layers('brick_double_insulated', doc)
    return 1.0 / (0.13 + sum(d / lam for _n, d, lam, *_ in rows) + 0.04)


def test_the_box_by_hand():
    from archforge.mep.heat_load import heat_load
    doc = _box()
    u = _u_by_hand(doc)
    wall_area = 2 * (L + W) * H - WIN_W * WIN_H              # 54 − 3 = 51 m² (axis dimensions, as the program says)
    walls_w = wall_area * u * DT
    window_w = WIN_W * WIN_H * UW * DT                        # 3 × 1,8 × 20 = 108 W
    vent_w = 0.34 * N_AIR * (L * W * H) * DT                  # 0,34 × 0,5 × 60 × 20 = 204 W
    r = heat_load(doc)
    parts = dict(r['parts'])
    assert r['delta_t'] == DT
    assert r['volume_m3'] == L * W * H
    assert math.isclose(parts['Εξωτερικοί τοίχοι'], walls_w, abs_tol=1)
    assert parts['Κουφώματα'] == round(window_w) == 108
    assert parts['Αερισμός'] == round(vent_w) == 204
    assert parts['Θερμογέφυρες'] == 0                         # no ψ in the project: said, not guessed
    assert any('θερμογέφυρες' in x for x in r['not_counted'])
    assert math.isclose(r['watts'], walls_w + window_w + vent_w, abs_tol=2)


def test_the_box_quantities():
    from archforge.quantities.takeoff import take_off
    rooms = take_off(_box())['rooms']
    assert len(rooms) == 1
    r = rooms[0]
    # Net floor inside the walls: (5 − 0,25) × (4 − 0,25); walls = net perimeter × height − the window.
    assert math.isclose(r['floor_m2'], (L - T) * (W - T), abs_tol=0.01)
    assert math.isclose(r['perimeter_m'], 2 * ((L - T) + (W - T)), abs_tol=0.01)
    assert math.isclose(r['walls_m2'], 2 * ((L - T) + (W - T)) * H - WIN_W * WIN_H, abs_tol=0.01)


def test_doubling_only_the_walls_u_doubles_only_the_walls_part():
    """Προδιαγραφή 07/11 (απομόνωση): διπλάσιο U τοίχων → μόνο ο όρος των τοίχων διπλάσιος, οι άλλοι ίδιοι."""
    from archforge.mep.heat_load import heat_load
    doc = _box()
    for e in doc.entities.values():
        if e.kind == 'wall':
            e.params['wall_type'] = 'generic'            # no build-up: the project's one U for walls
    climate = next(e for e in doc.entities.values() if e.kind == 'design_climate')
    climate.params['heat_u_walls'] = 0.5
    from archforge.mep import heat_load as hl
    real = hl.assumptions

    def with_u(u):
        hl.assumptions = lambda d: {**real(d), 'heat_u_walls': u}
        try:
            return dict(heat_load(doc)['parts'])
        finally:
            hl.assumptions = real
    a, b = with_u(0.5), with_u(1.0)
    assert a['Εξωτερικοί τοίχοι'] == round(51.0 * 0.5 * DT) == 510      # 51 m² × 0,5 × 20
    assert b['Εξωτερικοί τοίχοι'] == 2 * a['Εξωτερικοί τοίχοι']
    assert all(b[k] == a[k] for k in a if k != 'Εξωτερικοί τοίχοι')


def test_the_box_of_the_review_with_roof_and_floor():
    """Το «λυσάρι» της κριτικής 07/11: U τοίχων 0,50, δαπέδου και οροφής 0,40, παραθύρου 2,00, n = 0,5, ΔT 20 K →
    τοίχοι 510 + δάπεδο/οροφή 320 + παράθυρο 120 + αερισμός 204 = 1154 W· διπλάσιο U τοίχων → 1664 W."""
    from archforge.mep.heat_load import heat_load
    doc = _box()
    for e in doc.entities.values():
        if e.kind == 'wall':
            e.params['wall_type'] = 'generic'
        if e.kind == 'window':
            e.params['u_value'] = 2.0
        if e.kind == 'design_climate':
            e.params.update(heat_u_walls=0.5, heat_u_roof=0.4, heat_u_floor=0.4)
    r = heat_load(doc)
    parts = dict(r['parts'])
    assert (r['roof_m2'], r['floor_m2']) == (20.0, 20.0)
    assert parts['Εξωτερικοί τοίχοι'] == 510 and parts['Οροφή / δώμα'] == 160 and parts['Δάπεδο'] == 160
    assert parts['Κουφώματα'] == 120 and parts['Αερισμός'] == 204
    assert r['watts'] == 1154
    next(e for e in doc.entities.values() if e.kind == 'design_climate').params['heat_u_walls'] = 1.0
    assert heat_load(doc)['watts'] == 1664


def test_a_storey_over_another_loses_only_where_it_overhangs():
    from archforge.mep.heat_load import heat_load
    doc = _box()
    next(e for e in doc.entities.values() if e.kind == 'design_climate').params.update(heat_u_roof=0.4, heat_u_floor=0.4)
    pts = [(0, 0), (L, 0), (L, W), (0, W)]
    for a, b in zip(pts, pts[1:] + pts[:1]):                 # the same box again, one storey up
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': H, 'height': H,
                                'thickness': T, 'wall_type': 'brick_double_insulated'}))
    r = heat_load(doc)
    assert (r['roof_m2'], r['floor_m2']) == (20.0, 20.0)       # only the top roof and the bottom floor


def test_without_u_the_roof_and_floor_are_said_not_guessed():
    from archforge.mep.heat_load import heat_load
    r = heat_load(_box())
    parts = dict(r['parts'])
    assert parts['Οροφή / δώμα'] == 0 and parts['Δάπεδο'] == 0
    assert any(x.startswith('οροφή / δώμα 20,0 m²') for x in r['not_counted'])
    assert any(x.startswith('δάπεδο 20,0 m²') for x in r['not_counted'])
