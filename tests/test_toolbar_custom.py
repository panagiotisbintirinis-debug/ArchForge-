"""Owner 15/10: «μικρά εικονίδια ή δώσε μου τη δυνατότητα να τροποποιώ εγώ το μενού κατά βούληση — επιλέγω το
μέγεθος και να προσθέτω ή αφαιρώ εργαλεία ανά κουμπί»."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QSettings, QSize, Qt


def _window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1536, 1000); w.show(); app.processEvents()
    return app, w


def _close(app, w):
    w._mark_clean(); w.close(); app.processEvents()


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / 'layout.ini'), QSettings.Format.IniFormat)


def test_icons_are_smaller_by_default_and_the_size_is_chosen(settings):
    from archforge.ui import toolbar_custom as tc
    app, w = _window()
    try:
        wall = next(b for l, b in w._tool_groups['build'].labelled_buttons() if l == 'Τοίχος')
        assert wall.iconSize() == QSize(20, 20)
        tc.set_icon_size(w, 16, settings)
        assert wall.iconSize() == QSize(16, 16)
        assert all(b.iconSize() == QSize(16, 16) for b in w._common_palette.buttons.values())
        tc.set_text(w, False, settings)
        assert wall.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        sizes = [a.text() for a in w._icon_size_menu.actions() if a.text()]
        assert sizes[:3] == ['Μικρά', 'Μεσαία', 'Μεγάλα']                # Προβολή ▸ Μέγεθος εικονιδίων
    finally:
        _close(app, w)


def test_add_any_menu_command_hide_a_button_remembered_and_reset(settings):
    from archforge.ui import toolbar_custom as tc
    app, w = _window()
    try:
        build = w._tool_groups['build']
        path = 'Κατασκευή / Κάγκελα & μπαλκόνια / Μπαλκόνι (σχεδίαση)'
        assert path in tc.catalog(w)
        tc.add_tool(w, build, path, settings)
        b = build.custom_buttons[path]
        assert b.defaultAction() is tc.catalog(w)[path]                     # the very same command
        assert not b.icon().isNull()
        tc.set_shown(w, build, 'Στέγη', False, settings)
        roof = next(x for l, x in build.labelled_buttons() if l == 'Στέγη')
        assert roof.isHidden()
        tc.add_tool(w, w._common_palette, 'Επεξεργασία / Διπλασιασμός', settings)
        tc.set_icon_size(w, 26, settings)
        # The right-click menu of a group lists its buttons, «Πρόσθεσε εργαλείο» and the sizes.
        menu = tc.customize_menu(w, build)
        texts = [a.text() for a in menu.actions()]
        assert 'Πρόσθεσε εργαλείο' in texts and 'Μέγεθος εικονιδίων' in texts and 'Μπαλκόνι (σχεδίαση)' in texts
    finally:
        _close(app, w)
    app, w = _window()
    try:
        tc.load(w, settings)                                              # next start: the same arrangement
        build = w._tool_groups['build']
        assert path in build.custom_buttons and 'Επεξεργασία / Διπλασιασμός' in w._common_palette.custom_buttons
        assert next(x for l, x in build.labelled_buttons() if l == 'Στέγη').isHidden()
        assert next(x for l, x in build.labelled_buttons() if l == 'Τοίχος').iconSize() == QSize(26, 26)
        # Removing an added button, then «Επαναφορά».
        tc.remove_tool(w, build, path, settings)
        assert path not in build.custom_buttons
        tc.reset(w, settings)
        assert not w._common_palette.custom_buttons
        assert not next(x for l, x in build.labelled_buttons() if l == 'Στέγη').isHidden()
        assert next(x for l, x in build.labelled_buttons() if l == 'Τοίχος').iconSize() == QSize(20, 20)
    finally:
        _close(app, w)


def test_frames_shrink_with_the_icons_and_take_any_direction(settings):
    """Owner 15/10: «έκανα τα εικονίδια μικρά, το πλαίσιο είναι ακόμα τεράστιο … μου δίνει το περιθώριο να τα
    μεγαλώσω αλλά μόνο προς μία κατεύθυνση»."""
    from PySide6.QtWidgets import QApplication
    from archforge.ui import toolbar_custom as tc
    app, w = _window()
    try:
        build, palette = w._tool_groups['build'], w._common_palette
        tc.set_icon_size(w, 26, settings); app.processEvents()
        big = (build.sizeHint(), palette.sizeHint())
        tc.set_icon_size(w, 16, settings); app.processEvents()
        small = (build.sizeHint(), palette.sizeHint())
        assert small[0].width() < big[0].width() and small[0].height() < big[0].height()
        assert small[1].width() < big[1].width() and small[1].height() < big[1].height()
        tc.set_text(w, False, settings); app.processEvents()
        assert build.sizeHint().height() <= 46 and palette.sizeHint().width() <= 200
        # «Κοινά» as one upright column.
        tc.set_palette_cols(w, 1, settings); app.processEvents()
        assert palette.sizeHint().height() > palette.sizeHint().width()
        # A group dragged to the left edge stacks its buttons top to bottom.
        w.addToolBar(Qt.ToolBarArea.LeftToolBarArea, build); app.processEvents()
        assert build.sizeHint().height() > build.sizeHint().width()
    finally:
        _close(app, w)
