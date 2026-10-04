import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from archforge.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_simultaneous_2d_3d_shows_both_real_editors_and_can_switch_back():
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    window._simultaneous_action.setChecked(True)
    app.processEvents()
    split = window._mockup_center_split
    assert split is not None
    assert window._central_tabs.currentWidget() is split
    assert split.isVisible()
    assert window.plan_view.isVisible()
    assert window.plan_view.viewport().isVisible()
    assert window._mockup_right_tabs.isVisible()

    window._simultaneous_action.setChecked(False)
    app.processEvents()
    central = window._central_tabs
    assert [central.tabText(i) for i in range(central.count())] == ['2D Σχεδίαση', '3D / Structural']
    assert window.plan_view.isVisible()

    window._simultaneous_action.setChecked(True)
    app.processEvents()
    assert window.plan_view.isVisible()
    assert window._mockup_right_tabs.isVisible()

    window._mark_clean()
    window.close()
    app.processEvents()


def test_structural_tools_stay_in_the_2d_plan_instead_of_jumping_to_structural():
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    for tool in ('structural_column', 'structural_beam'):
        window._set_active_tool(tool)
        assert window._central_tabs.currentIndex() == 0
        assert window.view is window.plan_view
        assert window.plan_view.controller.tool == tool

    window._mark_clean()
    window.close()
    app.processEvents()


def test_committed_2d_edit_redraws_the_visible_3d_view_without_tab_switching():
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity

    app = _app()
    window = MainWindow()
    window.show()
    window._simultaneous_action.setChecked(True)
    app.processEvents()

    calls = []
    original = window.pbr_view.redraw
    window.pbr_view.redraw = lambda *a, **k: (calls.append(k), original(*a, **k))[1]

    wall = Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0,
                           'height': 2.7, 'thickness': 0.2})
    window.stack.execute(AddEntity(wall))
    app.processEvents()
    assert calls, '3D view must refresh after a committed 2D edit'
    # A normal refresh keeps the human's orbit/zoom.
    assert all(not k.get('force_full') for k in calls)

    calls.clear()
    window._undo()
    app.processEvents()
    assert calls

    window._mark_clean()
    window.close()
    app.processEvents()
