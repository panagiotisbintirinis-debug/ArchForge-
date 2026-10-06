import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QMessageBox, QToolButton

from archforge.core.viewport import PointerEvent
from archforge.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def _window():
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()
    return app, window


def _close(app, window):
    window._mark_clean()
    window.close()
    app.processEvents()


def test_ribbon_groups_doors_windows_openings_stairs_kitchen_and_structure_in_one_menu():
    app, window = _window()
    buttons = [b for b in window.findChildren(QToolButton) if b.text() == 'Στοιχεία' and b.isVisible()]
    assert len(buttons) == 1
    menu = buttons[0].menu()
    labels = [a.text() for a in menu.actions()]
    assert labels[:3] == ['Πόρτα', 'Παράθυρο', 'Άνοιγμα']
    subs = {a.text(): a.menu() for a in menu.actions() if a.menu()}
    assert set(subs) == {'Σκάλα / Ράμπα', 'Κουζίνα', 'Δομικά: κολόνες, δοκάρια, βάσεις'}
    stair = [a.text() for a in subs['Σκάλα / Ράμπα'].actions()]
    assert stair[:2] == ['Σκάλα', 'Ράμπα'] and 'Τύπος σκάλας' in stair
    window._fill_kitchen_menu()
    assert 'Κάτω ντουλάπι' in [a.text() for a in subs['Κουζίνα'].actions()]
    structure = [a.text() for a in subs['Δομικά: κολόνες, δοκάρια, βάσεις'].actions()]
    assert structure[:2] == ['Κολώνα', 'Δοκός'] and any(t.startswith('Βάσεις') for t in structure)
    # Same submenu at the top of the Δομικά menu.
    assert window._structure_menu.actions()[0].menu() is subs['Δομικά: κολόνες, δοκάρια, βάσεις']
    # Toolbars can be moved and hidden, and brought back from Προβολή → Γραμμές εργαλείων.
    assert window._mockup_ribbon.isMovable()
    toggle = window._toolbars_menu.actions()[0]
    toggle.trigger(); assert window._mockup_ribbon.isHidden()
    toggle.trigger(); assert not window._mockup_ribbon.isHidden()
    window._toolbars_lock_action.setChecked(True); assert not window._mockup_ribbon.isMovable()
    _close(app, window)


def test_stair_without_upper_floor_offers_to_create_it_and_then_places(monkeypatch):
    app, window = _window()
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    window._set_active_tool('stair')

    assert window.doc.levels.get('Floor 2') == 2.70
    # The human keeps drawing from the storey they were on.
    assert abs(float(window.doc.work_plane.origin[2])) < 1e-9
    assert window.plan_view.controller.tool == 'stair'

    controller = window.plan_view.controller
    controller.pointer_down(PointerEvent(1.0, 1.0))
    controller.pointer_move(PointerEvent(5.0, 1.0))
    result = controller.pointer_up(PointerEvent(5.0, 1.0))
    stair = window.doc.get(result.entity_id)
    assert stair.kind == 'stair'
    assert stair.params['upper_z'] >= 2.70 - 1e-9
    _close(app, window)


def test_ramp_without_upper_floor_can_be_declined(monkeypatch):
    app, window = _window()
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.No)
    window._set_active_tool('ramp')
    assert set(window.doc.levels) == {'Ground'}
    assert window.plan_view.controller.tool != 'ramp'
    _close(app, window)


def test_ribbon_stair_type_menu_places_the_chosen_layout():
    app, window = _window()
    window.doc.levels['Floor 2'] = 2.70
    window._refresh_floor_selector()
    types = window._mockup_stair_type_menu
    assert [a.text() for a in types.actions()] == ['Αυτόματη', 'Ευθεία', 'Γ (L)', 'Π (U)', 'Σπιράλ']
    next(a for a in types.actions() if a.text() == 'Σπιράλ').trigger()

    controller = window.plan_view.controller
    assert controller.tool == 'stair'
    controller.pointer_down(PointerEvent(1.0, 1.0))
    controller.pointer_move(PointerEvent(6.0, 1.0))
    result = controller.pointer_up(PointerEvent(6.0, 1.0))
    assert window.doc.get(result.entity_id).params['layout'] == 'spiral'
    _close(app, window)


def test_stair_to_a_roof_terrace_does_not_ask_for_a_new_floor(monkeypatch):
    from archforge.core.commands import AddEntity, CreateRoomRoofs
    from archforge.core.model import Entity

    app, window = _window()
    for a, b in (((0, 0), (4, 0)), ((4, 0), (4, 3)), ((4, 3), (0, 3)), ((0, 3), (0, 0))):
        window.stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1],
                                                       'z': 0.0, 'height': 2.7, 'thickness': 0.2})))
    window.stack.execute(CreateRoomRoofs([window.doc.active_room_faces()[0].signature]))
    asked = []
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: asked.append(a) or QMessageBox.StandardButton.No)
    window._set_active_tool('stair')
    assert not asked
    assert window.plan_view.controller.tool == 'stair'
    assert set(window.doc.levels) == {'Ground'}
    _close(app, window)


def test_roof_overhang_is_editable_in_properties_even_for_older_roofs():
    from PySide6.QtWidgets import QDoubleSpinBox
    from archforge.core.commands import AddEntity, CreateRoomRoofs
    from archforge.core.model import Entity

    app, window = _window()
    for a, b in (((0, 0), (4, 0)), ((4, 0), (4, 3)), ((4, 3), (0, 3)), ((0, 3), (0, 0))):
        window.stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1],
                                                       'z': 0.0, 'height': 2.7, 'thickness': 0.2})))
    window.stack.execute(CreateRoomRoofs([window.doc.active_room_faces()[0].signature]))
    roof = next(e for e in window.doc.entities.values() if e.kind == 'room_roof')
    roof.params.pop('overhang')  # as saved by an older build
    window.doc.select([roof.id])
    window.refresh_inspector()
    labels = [window.form.itemAt(i, window.form.ItemRole.LabelRole) for i in range(window.form.rowCount())]
    names = [w.widget().text() for w in labels if w is not None and w.widget() is not None]
    assert 'overhang' in names
    window._commit_property(roof.id, 'overhang', 0.4)
    assert window.doc.get(roof.id).params['overhang'] == 0.4
    _close(app, window)


def test_escape_cancels_a_stair_in_progress_in_2d_and_3d():
    from archforge.core.commands import AddEntity, CreateRoomRoofs
    from archforge.core.model import Entity

    app, window = _window()
    window.doc.levels['Floor 2'] = 2.70
    window._refresh_floor_selector()
    window._set_active_tool('stair')
    controller = window.plan_view.controller
    controller.pointer_down(PointerEvent(1.0, 1.0))
    controller.pointer_move(PointerEvent(4.0, 1.0))
    assert controller.active is not None
    window.pbr_view._begin_stair_from_web(6.0, 6.0)
    assert window.pbr_view._stair_tx is not None

    window._escape_shortcut.activated.emit()
    assert controller.active is None
    assert window.pbr_view._stair_tx is None
    assert not [e for e in window.doc.entities.values() if e.kind == 'stair']
    _close(app, window)


def test_plan_redraw_does_not_wipe_a_3d_stair_preview():
    app, window = _window()
    window.doc.levels['Floor 2'] = 2.70
    window.pbr_view._begin_stair_from_web(1.0, 1.0)
    window.pbr_view._update_stair_from_web(5.0, 1.0)
    calls = []
    window.pbr_view._set_stair_candidate_params = lambda *a, **k: calls.append(a)
    window.plan_view.redraw()          # emits an empty plan preview
    assert calls == []
    _close(app, window)
