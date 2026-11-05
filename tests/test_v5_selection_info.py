"""Κριτική v5 (04/11), k3/k4: πληροφορία με μηδέν κλικ, επιλογή όμοιων / εξωτερικών, τύπος σε πολλούς τοίχους μαζί με μία
αναίρεση, U ζωντανά στο εργαλείο +/− των στρώσεων. Πάνω στο πραγματικό έργο του ιδιοκτήτη (owner_111)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

OWNER = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')


@pytest.fixture
def window():
    QApplication.instance() or QApplication([])
    from archforge.ui.main_window import MainWindow
    w = MainWindow()
    w._open_checked(OWNER)
    QApplication.processEvents()
    yield w
    w._mark_clean(); w.close()


def _walls(doc):
    return [e for e in doc.entities.values() if e.kind == 'wall']


def test_a_wall_says_type_storey_and_u_without_opening_anything(window):
    from archforge.ui.indication import describe
    walls = _walls(window.doc)
    ground = next(e for e in walls if float(e.params.get('z', 0)) == 0.0)
    upper = next(e for e in walls if float(e.params.get('z', 0)) > 0.0)
    assert 'Γενικός (χωρίς σύνθεση)' in describe(window.doc, ground.id)
    assert 'Ισόγειο' in describe(window.doc, ground.id)          # the storey by name, not «Στάθμη (z) 0.0000»
    assert '1ος όροφος' in describe(window.doc, upper.id)


def test_select_exterior_then_one_type_for_all_with_one_undo(window):
    from archforge.ui import select_similar as S
    from archforge.ui.multi_wall_rows import set_type_all
    ids = S.select_exterior(window)
    assert len(ids) == 24 and set(window.doc.selection) == set(ids)   # 17 ground + 7 upper (05/11: η εσοχή του Γ)
    n = set_type_all(window, ids, 'brick_double_insulated')
    assert n == 24
    assert all(window.doc.get(i).params['wall_type'] == 'brick_double_insulated' for i in ids)
    assert all(abs(window.doc.get(i).params['thickness'] - 0.27) < 1e-9 for i in ids)
    interior = [e for e in _walls(window.doc) if e.id not in ids]
    assert interior and all(e.params.get('wall_type', 'generic') == 'generic' for e in interior)   # untouched
    window.stack.undo()                                               # one undo for all 24
    assert all(window.doc.get(i).params.get('wall_type', 'generic') == 'generic' for i in ids)


def test_select_similar_takes_kind_and_type(window):
    from archforge.ui import select_similar as S
    from archforge.ui.multi_wall_rows import set_type_all
    ext = S.exterior_wall_ids(window.doc)
    set_type_all(window, ext[:3], 'concrete_etics')
    window.doc.select([ext[0]])
    ids = S.select_similar(window)
    assert sorted(ids) == sorted(ext[:3])
    window.doc.select([])
    assert S.select_similar(window) == [] and 'επίλεξε πρώτα' in window.statusBar().currentMessage()


def test_properties_with_several_walls_show_totals_and_one_type_field(window):
    from PySide6.QtWidgets import QComboBox, QLabel
    from archforge.ui import select_similar as S
    S.select_exterior(window)
    texts = [w.text() for w in window.form.parentWidget().findChildren(QLabel)]
    assert any('24 τοίχοι επιλεγμένοι' in t for t in texts)
    combo = next(c for c in window.form.parentWidget().findChildren(QComboBox) if c.findData('brick_double_insulated') >= 0)
    combo.setCurrentIndex(combo.findData('brick_double_insulated'))
    QApplication.processEvents()
    assert sum(1 for e in _walls(window.doc) if e.params.get('wall_type') == 'brick_double_insulated') == 24


def test_layers_tool_shows_u_live(window):
    from archforge.ui.wall_details_dialog import WallDetailsDialog
    d = WallDetailsDialog(window, 'brick_double_insulated')
    assert 'U 0,48 W/m²K' in d.total_label.text() and 'προς επαλήθευση' in d.total_label.text()
    ins = next(r for r in d._layer_widgets if r['material'].currentData() == 'xps')
    ins['thickness'].setValue(10.0)                                    # 5 → 10 cm of XPS
    assert 'U 0,28 W/m²K' in d.total_label.text()
    d.close()


def test_thermal_view_colours_walls_by_u_from_the_view_menu(window):
    from archforge.ui import select_similar as S
    from archforge.ui.multi_wall_rows import set_type_all
    from archforge.ui import thermal_view as T
    found = [a for a in window.findChildren(type(window._thermal_view_action)) if a is window._thermal_view_action]
    assert found and window._thermal_view_action.isCheckable()
    window._thermal_view_action.setChecked(True)
    assert window.plan_view._thermal_counts == {'known': 0, 'unknown': 25}       # owner_111 ground: no build-ups yet
    assert 'χωρίς σύνθεση' in window.statusBar().currentMessage()
    set_type_all(window, S.exterior_wall_ids(window.doc), 'brick_double_insulated')
    window.plan_view.redraw()
    assert window.plan_view._thermal_counts == {'known': 17, 'unknown': 8}        # 17 exterior walls of the ground floor (05/11)
    assert T.colour(0.2).name() != T.colour(2.0).name()                          # good insulation ≠ losses
    window._thermal_view_action.setChecked(False)
    assert not window.plan_view.color_by_u


def test_the_status_line_follows_a_type_change_of_the_indicated_wall(window):
    """Σ6: after «Τύπος τοίχου» the status line kept «× 0,15» of the old type."""
    from archforge.core.commands import UpdateEntity
    w = window
    wall = _walls(w.doc)[0]
    said = []
    w.plan_view.statusChanged.connect(said.append)
    w.plan_view.indicate(wall.id)
    old = said[-1]
    new_thickness = float(wall.params['thickness']) + 0.1
    w.stack.execute(UpdateEntity(wall.id, {'thickness': new_thickness}))
    QApplication.processEvents()
    assert said[-1] != old and f'{new_thickness:.2f}'.replace('.', ',') in said[-1]
