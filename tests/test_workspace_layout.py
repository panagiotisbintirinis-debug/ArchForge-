"""UX4: a mouse-first workspace — movable bars, view/style popups, remembered layout, Greek labels, plan rulers."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QToolBar

from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.ui.main_window import MainWindow
from archforge.ui.plan_overlay import hud_text, ruler_step


def _app():
    return QApplication.instance() or QApplication([])


def _window():
    app = _app()
    window = MainWindow()
    window.resize(1400, 900)
    window.show()
    app.processEvents()
    return app, window


def _close(app, window):
    window._mark_clean()
    window.close()
    app.processEvents()


def test_every_bar_and_panel_moves_floats_and_closes_and_the_bottom_strip_is_gone():
    app, window = _window()
    bars = [b for b in window.findChildren(QToolBar) if b.isVisible()]
    assert {b.windowTitle() for b in bars} == {'Εργαλεία σχεδίασης', 'Όροφος', 'Προβολή', 'Κάνναβος & έλξη', 'Περιβάλλον'}
    for bar in bars:
        assert bar.isMovable() and bar.isFloatable() and bar.allowedAreas() == Qt.ToolBarArea.AllToolBarAreas
    names = {d.objectName() for d in window.findChildren(QDockWidget)}
    assert 'approved_views_rendering' not in names
    for dock in window._workspace_panels:
        f = dock.features()
        assert f & QDockWidget.DockWidgetFeature.DockWidgetMovable and f & QDockWidget.DockWidgetFeature.DockWidgetFloatable
        assert f & QDockWidget.DockWidgetFeature.DockWidgetClosable
    # Προβολή → Γραμμές εργαλείων lists every bar; Επαναφορά διάταξης is there.
    assert [a.text() for a in window._toolbars_menu.actions()][:4] == ['Εργαλεία σχεδίασης', 'Όροφος', 'Προβολή', 'Κάνναβος & έλξη']
    assert window._reset_layout_action in window.view_menu.actions()
    # Κλείδωμα θέσης freezes all of them.
    window._toolbars_lock_action.setChecked(True)
    assert not any(b.isMovable() for b in window._workspace_bars)
    window._toolbars_lock_action.setChecked(False)
    _close(app, window)


def test_style_popup_drives_the_real_3d_look():
    app, window = _window()
    labels = [a.text() for a in window._mockup_style_popup.actions()]
    assert labels[0].startswith('Ρεαλιστικό') and any(t.startswith('Γυάλινο') for t in labels)
    window._mockup_style_actions['Βραδινό (δειλινό)']()
    assert window.pbr_view._sun[0] == 19.0 and window.render_technique.currentData() == 'pbr'
    assert window._central_tabs.currentIndex() == 1
    window._mockup_style_actions['Γυάλινο (φαίνονται τα Η/Μ)']()
    assert window.render_technique.currentData() == 'glass' and window.pbr_view._technique == 'glass'
    window._mockup_style_actions['Στούντιο (ουδέτερο φως)']()
    assert window.pbr_view._sun is None and window.pbr_view._technique == 'pbr'
    _close(app, window)


def test_layout_is_remembered_and_can_be_reset(tmp_path):
    from archforge.ui.workspace_layout import restore_layout, save_layout, reset_layout
    settings = QSettings(str(tmp_path / 'layout.ini'), QSettings.Format.IniFormat)
    app, window = _window()
    window.addToolBar(Qt.ToolBarArea.LeftToolBarArea, window._mockup_ribbon)
    window._mockup_snap_bar.hide()
    save_layout(window, settings)
    _close(app, window)
    app, window = _window()
    assert window.toolBarArea(window._mockup_ribbon) == Qt.ToolBarArea.TopToolBarArea
    assert restore_layout(window, settings)
    app.processEvents()
    assert window.toolBarArea(window._mockup_ribbon) == Qt.ToolBarArea.LeftToolBarArea
    assert window._mockup_snap_bar.isHidden()
    reset_layout(window)
    app.processEvents()
    assert window.toolBarArea(window._mockup_ribbon) == Qt.ToolBarArea.TopToolBarArea
    assert not window._mockup_snap_bar.isHidden()
    # Layout is view state only: the Document did not change.
    assert not window.doc.entities
    _close(app, window)


def test_greek_on_screen_while_ids_stay():
    app, window = _window()
    assert window.floor_selector.itemText(0).startswith('Ισόγειο')
    assert window.floor_selector.itemData(0)[0] == 'Ground'
    assert window.form.itemAt(0).widget().text() == 'Καμία επιλογή'
    wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
    window.stack.execute(AddEntity(wall))
    window.doc.select([wall.id]); window.refresh_inspector()
    labels = [window.form.itemAt(i).widget().text() for i in range(window.form.count())
              if window.form.itemAt(i).widget() is not None and hasattr(window.form.itemAt(i).widget(), 'text')]
    assert 'Τύπος' in labels and 'Τοίχος' in labels and 'Type' not in labels
    menus = [a.text() for a in window.menuBar().actions()]
    assert 'Γλυπτική' in menus and 'Βοηθός AI' in menus and 'Sculpt' not in menus and 'AI' not in menus
    _close(app, window)


def test_plan_shows_metres_and_greek_live_measures():
    assert hud_text({'length': 6.0, 'angle_deg': 180.0, 'magnet': 90.0, 'x': 1.0}) == 'Μήκος 6.00 m   Γωνία 180°'
    assert ruler_step(55.0) == 1 and ruler_step(300.0) == 0.2 and ruler_step(5.0) == 10
    app, window = _window()
    plan = window.plan_view
    lines = len(plan.scene().items())
    window._mockup_grid_check.setChecked(False)
    assert len(plan.scene().items()) < lines
    window._mockup_grid_check.setChecked(True)
    window._mockup_snap_size.setCurrentText('0.25 m')
    assert plan.controller.grid == 0.25
    plan.rebind(window.doc, window.stack)
    assert plan.controller.grid == 0.25
    # The overlay paints (empty project hint, rulers, scale bar) without touching the Document.
    plan._cursor_xy = (1.0, 2.0)
    assert not plan.viewport().grab().isNull()
    assert not window.doc.entities
    _close(app, window)
