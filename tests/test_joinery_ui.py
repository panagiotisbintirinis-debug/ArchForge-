"""Κουφώματα στις Ιδιότητες (ελληνικά, ένα undo) και στη Βιβλιοθήκη (έτοιμοι τύποι)."""
from archforge.core.commands import AddEntity
from archforge.core.model import Entity


def _labels(window):
    out = []
    for i in range(window.form.rowCount()):
        item = window.form.itemAt(i, window.form.ItemRole.LabelRole)
        if item is not None and item.widget() is not None:
            out.append(item.widget().text())
    return out


def _field(window, label):
    from PySide6.QtWidgets import QComboBox
    for i in range(window.form.rowCount()):
        item = window.form.itemAt(i, window.form.ItemRole.LabelRole)
        if item is not None and item.widget() is not None and item.widget().text() == label:
            return window.form.itemAt(i, window.form.ItemRole.FieldRole).widget()
    raise AssertionError(label)


def test_inspector_type_combo_is_greek_and_one_undo():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': 0.25})
        window.stack.execute(AddEntity(wall))
        win = Entity('window', {'offset': 3.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=wall.id)
        window.stack.execute(AddEntity(win))
        window.doc.select([win.id]); window.refresh_inspector()
        combo = _field(window, 'Τύπος κουφώματος')
        assert combo.currentData() == 'basic'
        assert 'Ανοιγοανακλινόμενο' in [combo.itemText(i) for i in range(combo.count())]
        combo.setCurrentIndex(combo.findData('tilt_turn'))
        assert window.doc.get(win.id).params['opening_type'] == 'tilt_turn'
        window.refresh_inspector()
        labels = _labels(window)
        assert {'Φύλλα', 'Μεντεσέδες', 'Φορά ανοίγματος', 'Ρολό / παντζούρια', 'Υλικό κουφώματος'} <= set(labels)
        assert 'leaves' not in labels and 'opening_type' not in labels
        shading = _field(window, 'Ρολό / παντζούρια')
        shading.setCurrentIndex(shading.findData('shutters'))
        assert window.doc.get(win.id).params['shading'] == 'shutters'
        window.stack.undo()
        assert 'shading' not in window.doc.get(win.id).params
        window.stack.undo()
        assert 'opening_type' not in window.doc.get(win.id).params
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_library_has_joinery_presets_that_start_the_tool():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        tree = window._library_tree
        tops = {tree.topLevelItem(i).text(0).split(' (')[0]: tree.topLevelItem(i) for i in range(tree.topLevelItemCount())}
        assert 'Κουφώματα' in tops
        top = tops['Κουφώματα']
        subs = {top.child(i).text(0).split(' (')[0]: top.child(i) for i in range(top.childCount())}
        assert set(subs) == {'Παράθυρα', 'Πόρτες'}
        doors = subs['Πόρτες']
        leaf = next(doors.child(i) for i in range(doors.childCount()) if doors.child(i).text(0).startswith('Εξώπορτα'))
        preset = window._library_tree_action(leaf)
        assert preset['params']['opening_type'] == 'security'
        assert window.plan_view.controller.tool == 'door'
        assert window.plan_view.controller.opening_preset['width'] == 0.9
    finally:
        window._mark_clean(); window.close(); app.processEvents()
