import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QInputDialog, QToolBar

from archforge.core.commands import CreateFloorLevel
from archforge.core.model import Document, Entity, WorkPlane
from archforge.core.plan_scene import build_plan_frame
from archforge.core.viewport import PointerEvent
from archforge.ui.main_window import MainWindow
from archforge.ui.object_context_menu import object_context_actions


_APP = QApplication.instance() or QApplication([])


def _wall(entity_id, z):
    return Entity(
        'wall',
        {
            'x1': 0.0,
            'y1': 0.0,
            'x2': 4.0,
            'y2': 0.0,
            'z': float(z),
            'height': 2.7,
            'thickness': 0.15,
        },
        id=entity_id,
    )


def _closed_room(doc, prefix, z):
    walls = [
        (0, 0, 4, 0),
        (4, 0, 4, 3),
        (4, 3, 0, 3),
        (0, 3, 0, 0),
    ]
    for index, (x1, y1, x2, y2) in enumerate(walls):
        doc.add(Entity(
            'wall',
            {
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                'z': float(z), 'height': 2.7, 'thickness': 0.15,
            },
            id=f'{prefix}-{index}',
        ))


def test_ui_removes_redundant_front_elevation_tab_but_keeps_pbr_front_camera():
    window = MainWindow()
    labels = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert labels == ['FLOOR PLAN', '3D STUDIO']

    action_labels = {
        action.text()
        for toolbar in window.findChildren(QToolBar)
        for action in toolbar.actions()
    }
    assert 'Front' in action_labels
    window.close()


def test_add_floor_activates_storey_and_new_wall_uses_that_elevation(monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(QInputDialog, 'getDouble', lambda *args, **kwargs: (2.7, True))

    window._add_floor_level()

    assert window.doc.levels['Floor 2'] == 2.7
    assert window.doc.work_plane.name == 'Floor 2'
    assert window.doc.work_plane.origin[2] == 2.7

    controller = window.plan_view.controller
    controller.set_tool('wall')
    controller.pointer_down(PointerEvent(0.0, 0.0))
    controller.pointer_move(PointerEvent(4.0, 0.0))
    controller.pointer_up(PointerEvent(4.0, 0.0))

    walls = [e for e in window.doc.entities.values() if e.kind == 'wall']
    assert len(walls) == 1
    assert walls[0].params['z'] == 2.7
    window.close()


def test_floor_plan_only_shows_active_storey_walls():
    doc = Document()
    doc.add(_wall('ground-wall', 0.0))
    doc.add(_wall('upper-wall', 2.7))
    doc.levels['Floor 2'] = 2.7
    doc.work_plane = WorkPlane(name='Floor 2', origin=(0.0, 0.0, 2.7))

    frame = build_plan_frame(doc)
    wall_ids = {
        primitive.entity_id
        for primitive in frame.primitives
        if primitive.entity_id and doc.get(primitive.entity_id).kind == 'wall'
    }
    assert wall_ids == {'upper-wall'}


def test_auto_floor_uses_active_second_storey_room():
    window = MainWindow()
    _closed_room(window.doc, 'ground', 0.0)
    _closed_room(window.doc, 'upper', 2.7)
    window.stack.execute(CreateFloorLevel('Floor 2', 2.7))
    window._refresh_floor_selector()

    window._create_auto_floors()

    floors = [e for e in window.doc.entities.values() if e.kind == 'room_floor']
    assert len(floors) == 1
    from archforge.architecture.rooms import room_slab_geometry
    geometry = room_slab_geometry(window.doc, floors[0])
    assert geometry is not None
    assert geometry['z'] == 2.7
    window.close()


def test_delete_selected_object_is_reversible():
    window = MainWindow()
    wall = _wall('delete-me', 0.0)
    window.doc.add(wall)
    window.doc.select([wall.id])

    window._delete_selection()
    assert wall.id not in window.doc.entities

    window._undo()
    assert wall.id in window.doc.entities
    window.close()


def test_pbr_select_then_general_delete_removes_one_wall_and_undo_restores_it():
    window = MainWindow()
    wall_a = _wall('wall-a', 0.0)
    wall_b = Entity(
        'wall',
        {
            'x1': 0.0, 'y1': 2.0, 'x2': 4.0, 'y2': 2.0,
            'z': 0.0, 'height': 2.7, 'thickness': 0.15,
        },
        id='wall-b',
    )
    window.doc.add(wall_a)
    window.doc.add(wall_b)
    window.pbr_view.active_tool = 'select'

    window.pbr_view._select_entity_from_web('wall-a')
    assert window.doc.selection == ['wall-a']

    window._delete_selection()
    assert 'wall-a' not in window.doc.entities
    assert 'wall-b' in window.doc.entities

    window._undo()
    assert 'wall-a' in window.doc.entities
    assert 'wall-b' in window.doc.entities
    window.close()



def test_context_menu_registry_is_editable_and_view_aware():
    plan_wall = object_context_actions('wall', 'plan')
    pbr_wall = object_context_actions('wall', 'pbr')

    assert [entry['id'] if entry else None for entry in plan_wall] == [
        'properties', 'move', 'stretch', 'rotate', None, 'delete'
    ]
    assert [entry['id'] if entry else None for entry in pbr_wall] == [
        'properties', 'move', 'rotate', None, 'delete'
    ]
    placements = {
        entry['id']: entry['placement']
        for entry in pbr_wall
        if entry is not None
    }
    assert placements['properties'] == 'radial'
    assert placements['delete'] == 'radial'


def test_context_menu_properties_and_plan_tool_actions_use_selected_entity():
    window = MainWindow()
    wall = _wall('menu-wall', 0.0)
    window.doc.add(wall)

    window._handle_object_context_action(wall.id, 'properties')
    assert window.doc.selection == [wall.id]
    assert window.dock.isVisible() or not window.isVisible()

    window._handle_object_context_action(wall.id, 'rotate')
    assert window.doc.selection == [wall.id]
    assert window.view is window.plan_view
    assert window.plan_view.controller.tool == 'rotate'
    assert window.plan_view.controller.active_entity == wall.id
    window.close()



def test_wall_dimension_properties_update_authoritative_geometry_and_undo():
    window = MainWindow()
    wall = _wall('properties-wall', 0.0)
    window.doc.add(wall)

    window._apply_object_properties(
        wall.id,
        {'length': 6.0, 'height': 3.2, 'thickness': 0.25},
    )

    updated = window.doc.get(wall.id)
    assert updated.params['x2'] == 6.0
    assert updated.params['y2'] == 0.0
    assert updated.params['height'] == 3.2
    assert updated.params['thickness'] == 0.25

    window._undo()
    restored = window.doc.get(wall.id)
    assert restored.params['x2'] == 4.0
    assert restored.params['height'] == 2.7
    assert restored.params['thickness'] == 0.15
    window.close()


def test_window_dimension_properties_are_editable_and_validated_by_host():
    window = MainWindow()
    wall = _wall('host-wall', 0.0)
    window.doc.add(wall)
    opening = Entity(
        'window',
        {
            'offset': 2.0,
            'surface_u': 0.0,
            'width': 1.0,
            'height': 1.0,
            'sill': 0.8,
            'flat_margin': 0.25,
        },
        id='window-properties',
        parent_id=wall.id,
    )
    window.doc.add(opening)

    window._apply_object_properties(
        opening.id,
        {'width': 1.4, 'height': 1.2, 'sill': 0.9},
    )

    updated = window.doc.get(opening.id)
    assert updated.params['width'] == 1.4
    assert updated.params['height'] == 1.2
    assert updated.params['sill'] == 0.9

    window._undo()
    restored = window.doc.get(opening.id)
    assert restored.params['width'] == 1.0
    assert restored.params['height'] == 1.0
    assert restored.params['sill'] == 0.8
    window.close()



def test_pbr_context_move_stays_in_3d_for_supported_entity():
    window = MainWindow()
    wall = _wall('pbr-move-wall', 0.0)
    window.doc.add(wall)
    window.tabs.setCurrentWidget(window.pbr_view)
    window.view = window.pbr_view

    window._handle_object_context_action(wall.id, 'move')

    assert window.doc.selection == [wall.id]
    assert window.view is window.pbr_view
    assert window.pbr_view.active_tool == 'move'
    window.close()


def test_pbr_context_rotate_stays_in_3d_for_supported_entity():
    window = MainWindow()
    wall = _wall('pbr-rotate-wall', 0.0)
    window.doc.add(wall)
    window.tabs.setCurrentWidget(window.pbr_view)
    window.view = window.pbr_view

    window._handle_object_context_action(wall.id, 'rotate')

    assert window.doc.selection == [wall.id]
    assert window.view is window.pbr_view
    assert window.pbr_view.active_tool == 'rotate'
    window.close()
