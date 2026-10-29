"""The section line as the owner uses it — menu, mouse drag, back to the plan, a click a few pixels off the line,
the Delete key (owner 29/10: «δεν μπορούσα να την επιλέξω»; rule: a user's task is checked the user's way only).

Zoomed out, the 3,5 cm line was under one pixel and only a click exactly on it picked it."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def _menu_action(window, text):
    def walk(menu):
        for a in menu.actions():
            if a.menu() is not None:
                found = walk(a.menu())
                if found is not None:
                    return found
            elif a.text().replace('&', '').startswith(text):
                return a
        return None
    for top in window.menuBar().actions():
        if top.menu() is not None:
            found = walk(top.menu())
            if found is not None:
                return found
    return None


def test_section_line_is_drawn_picked_and_deleted_with_the_mouse():
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w._no_modal_dialogs = True; w.resize(1400, 900); w.show(); app.processEvents()
    try:
        pv = w.plan_view
        pv.fitInView(-30, -20, 60, 40); app.processEvents()           # zoomed out: the line is under one pixel
        at = lambda x, y: pv.mapFromScene(QPointF(x, y))
        action = _menu_action(w, 'Τομή')
        assert action is not None, 'Προβολή ▸ Τομή'
        action.trigger(); app.processEvents()
        # Drag the cut line across the plan.
        QTest.mousePress(pv.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(-10, 2))
        for x in range(-9, 11, 2):
            QTest.mouseMove(pv.viewport(), at(x, 2)); app.processEvents()
        QTest.mouseRelease(pv.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(10, 2))
        app.processEvents()
        sections = [e for e in w.doc.entities.values() if e.kind == 'section_line']
        assert len(sections) == 1
        # Back to the plan by its tab, nothing selected (as after clicking elsewhere).
        tabs = w._central_tabs
        QTest.mouseClick(tabs.tabBar(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         tabs.tabBar().tabRect(0).center()); app.processEvents()
        w.doc.select([]); w._redraw_views(all_views=True); app.processEvents()
        # A click 4 px beside the line (a hand, not a coordinate) picks it; Delete removes it.
        QTest.mouseClick(pv.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(3, 2) + QPoint(0, 4))
        app.processEvents()
        assert w.doc.selection == [sections[0].id]
        QTest.keyClick(pv.viewport(), Qt.Key.Key_Delete); app.processEvents()
        assert not [e for e in w.doc.entities.values() if e.kind == 'section_line']
    finally:
        w._mark_clean(); w.close(); app.processEvents()
