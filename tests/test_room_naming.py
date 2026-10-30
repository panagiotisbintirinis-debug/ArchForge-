"""Owner 30/10: «Χώρος 1, Χώρος 2 — δεν μπορώ να αλλάξω το όνομα· το 2Δ να μου δίνει περιθώριο να ονομάσω το χώρο, και
μετά στο δέντρο να φαίνεται σαν δωμάτιο· αν το επιλέξω να μου δείχνει τους τοίχους και γενικές πληροφορίες»."""
import pytest

from archforge.core.commands import AddEntity
from archforge.core.model import Entity


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 900); w.show(); app.processEvents()
    for a, b in (((0, 0), (5, 0)), ((5, 0), (5, 4)), ((5, 4), (0, 4)), ((0, 4), (0, 0))):
        w.stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 2.7, 'thickness': 0.2})))
    w._redraw_views(all_views=True); w._refresh_project_tree(); app.processEvents()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _room(w):
    return w.doc.active_room_faces()[0].signature


def test_double_click_on_the_room_in_the_plan_names_it_one_undo(window):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    w = window
    w._room_name_prompt = lambda current: 'Σαλόνι μεγάλο' if current == 'Χώρος 1' else None
    w.plan_view.centerOn(2.5, 2.0); w.plan_view.redraw()
    QTest.mouseDClick(w.plan_view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                      w.plan_view.mapFromScene(QPointF(1.0, 1.0)))
    assert w.doc.room_metadata(_room(w))['name'] == 'Σαλόνι μεγάλο'
    labels = [dict(p.meta)['text'] for p in w.plan_view._frame.primitives if p.role == 'derived-room-label']
    assert labels and labels[0].startswith('Σαλόνι μεγάλο')
    w.stack.undo()
    assert not w.doc.room_metadata(_room(w)).get('name')


def test_a_use_as_name_sets_the_use_and_the_tree_shows_the_room(window):
    from archforge.ui.room_panel import rename_room
    w = window
    rename_room(w, _room(w), 'Κουζίνα')
    data = w.doc.room_metadata(_room(w))
    assert data['name'] == 'Κουζίνα' and data['use'] == 'Κουζίνα'
    texts = []

    def walk(item):
        texts.append(item.text(0))
        for i in range(item.childCount()):
            walk(item.child(i))
    for i in range(w.project_tree.topLevelItemCount()):
        walk(w.project_tree.topLevelItem(i))
    assert any(t.startswith('Κουζίνα') for t in texts), texts


def test_choosing_the_room_in_the_tree_selects_its_walls_and_shows_the_room(window):
    from PySide6.QtWidgets import QComboBox, QLineEdit
    w = window
    sig = _room(w)

    def find(item):
        if item.data(0, 256 + 2) == sig:
            return item
        for i in range(item.childCount()):
            hit = find(item.child(i))
            if hit is not None:
                return hit
    node = next(n for n in (find(w.project_tree.topLevelItem(i)) for i in range(w.project_tree.topLevelItemCount())) if n)
    w._project_tree_clicked(node)
    walls = {e.id for e in w.doc.entities.values() if e.kind == 'wall'}
    assert set(w.doc.selection) == walls
    labels = [w.form.itemAt(i, w.form.ItemRole.LabelRole).widget().text() for i in range(w.form.rowCount())
              if w.form.itemAt(i, w.form.ItemRole.LabelRole) and w.form.itemAt(i, w.form.ItemRole.LabelRole).widget()]
    assert {'Όνομα', 'Χρήση', 'Όροφος', 'Εμβαδόν (καθαρό)', 'Περίμετρος', 'Διαστάσεις', 'Τοίχοι'} <= set(labels), labels
    name = w.dock.findChild(QLineEdit, 'roomName')
    name.setText('Υπνοδωμάτιο 1'); name.editingFinished.emit()
    assert w.doc.room_metadata(sig)['name'] == 'Υπνοδωμάτιο 1'
    assert w.dock.findChild(QComboBox, 'roomUse') is not None


def test_commands_on_a_locked_layer_say_so_instead_of_failing_silently(window):
    """menu_smoke 30/10: «Διαγραφή εδάφους» and «Όλα = Υφιστάμενα» raised LayerLockedError with nothing on screen."""
    from archforge.core import layers
    from archforge.site.terrain import default_terrain_params
    w = window
    w.stack.execute(AddEntity(Entity('terrain', default_terrain_params(w.doc), name='Έδαφος')))
    layers.set_workspace(w.doc, 'mep')
    for key in ('walls', 'site', 'terrain'):
        try:
            layers.set_layer_state(w.doc, key, locked=True)
        except (KeyError, ValueError):
            pass
    done = len(w.stack.done)
    w._delete_terrain()
    w._set_phase(list(w.doc.entities), 'existing')
    assert len(w.stack.done) == done
    assert 'δεν' in w.statusBar().currentMessage()
