"""CAM1 — owner: «ΠΡΕΠΕΙ ΟΠΩΣΔΗΠΟΤΕ ΝΑ ΒΑΛΟΥΜΕ ΚΑΜΕΡΑ ΜΕ ΚΑΤΕΥΘΥΝΣΗ ΟΥΤΩΣ ΩΣΤΕ ΝΑ ΕΠΙΛΕΓΩ ΤΙ ΘΑ ΔΩ ΟΠΟΤΕ ΘΕΛΩ».

A camera is a Document entity (undoable, saved, on a storey, on its own layer) that never counts as
building; the plan places / moves / turns it with the mouse, the list sends the 3D view to it.
"""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from archforge.core import cameras
from archforge.core.commands import AddEntity, CommandStack, CreateRoomFloors
from archforge.core.model import Document, Entity


def _walls(doc, st, z=0.0):
    for a, b in (((0, 0), (6, 0)), ((6, 0), (6, 4)), ((6, 4), (0, 4)), ((0, 4), (0, 0))):
        st.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': z,
                                             'height': 2.8, 'thickness': 0.2})))


def test_camera_creation_is_undoable_and_named_in_order():
    doc = Document(); st = CommandStack(doc)
    cmd, cam = cameras.add_camera_command(doc, 1.0, 2.0, 30.0)
    st.execute(cmd)
    assert cam.name == 'Κάμερα 1' and doc.get(cam.id).kind == 'camera'
    p = doc.get(cam.id).params
    assert p['height'] == pytest.approx(1.60) and p['fov'] == pytest.approx(60.0) and p['level_z'] == 0.0
    assert cameras.next_camera_name(doc) == 'Κάμερα 2'
    st.undo()
    assert cam.id not in doc.entities
    st.redo()
    assert cam.id in doc.entities


def test_camera_params_are_validated():
    with pytest.raises(ValueError):
        Document().add(Entity('camera', cameras.make_params(0, 0, 0, fov=170.0)))
    with pytest.raises(ValueError):
        Document().add(Entity('camera', cameras.make_params(0, 0, 0, pitch=95.0)))


def test_save_and_load_round_trip(tmp_path):
    doc = Document(); st = CommandStack(doc)
    doc.levels['Floor 2'] = 3.0
    cmd, cam = cameras.add_camera_command(doc, 2.5, 1.5, 135.0, level_z=3.0, height=1.7, fov=75.0, pitch=-10.0)
    st.execute(cmd)
    path = tmp_path / 'cam.json'
    doc.save(str(path))
    back = Document.load(str(path))
    e = back.get(cam.id)
    assert e.kind == 'camera' and e.name == 'Κάμερα 1'
    assert e.params == pytest.approx({'x': 2.5, 'y': 1.5, 'level_z': 3.0, 'height': 1.7, 'heading': 135.0,
                                      'pitch': -10.0, 'fov': 75.0})


def test_camera_is_not_building_quantities_rooms_or_mesh():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.quantities.takeoff import take_off
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); st = CommandStack(doc)
    _walls(doc, st)
    before_rooms = [f.signature for f in doc.active_room_faces()]
    before_q = take_off(doc)
    before_ids = {o.get('id') for o in build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), doc=doc)['objects']}
    cmd, cam = cameras.add_camera_command(doc, 3.0, 2.0, 0.0)
    st.execute(cmd)
    # Rooms, slabs and the take-off are the same with or without the camera.
    assert [f.signature for f in doc.active_room_faces()] == before_rooms
    assert repr(take_off(doc)) == repr(before_q)
    st.execute(CreateRoomFloors([f.signature for f in doc.active_room_faces()]))
    assert not any(e.kind != 'camera' and cam.id in repr(e.params) for e in doc.entities.values())
    assert cam.id not in repr(take_off(doc))
    # No 3D geometry: a relationship node, no mesh, nothing in the 3D payload.
    from archforge.geometry.plan import build_evaluation_plan
    plan = build_evaluation_plan(doc)
    assert cam.id not in {n.entity_id for n in plan.geometry_nodes()}
    payload = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), doc=doc)
    ids = {o.get('id') for o in payload['objects']}
    assert cam.id not in ids and before_ids <= ids


def test_camera_layer_mapping_and_workspaces():
    from archforge.core import layers
    from archforge.core.plan_scene import build_plan_frame
    assert layers.entity_layer('camera') == 'cameras' and layers.LAYERS['cameras'] == 'Κάμερες'
    doc = Document(); st = CommandStack(doc)
    layers.ensure_view_layers(doc)
    cmd, cam = cameras.add_camera_command(doc, 1.0, 1.0, 90.0)
    st.execute(cmd)
    roles = {p.role for p in build_plan_frame(doc).primitives}
    assert {'camera', 'camera-cone', 'camera-label'} <= roles               # visible in Αρχιτεκτονικό
    for p in build_plan_frame(doc).primitives:
        if p.role.startswith('camera'):
            assert layers.primitive_layer(doc, p) == 'cameras'
    layers.set_workspace(doc, 'structure')
    assert not any(p.role.startswith('camera') for p in build_plan_frame(doc).primitives)
    layers.set_workspace(doc, 'arch')
    layers.set_layer_state(doc, 'cameras', visible=False)
    assert not any(p.role.startswith('camera') for p in build_plan_frame(doc).primitives)


def test_camera_belongs_to_its_storey_in_the_plan():
    from archforge.core.plan_scene import build_plan_frame
    from archforge.core.model import WorkPlane
    doc = Document(); st = CommandStack(doc)
    doc.levels['Floor 2'] = 3.0
    cmd, cam = cameras.add_camera_command(doc, 1.0, 1.0, 0.0, level_z=3.0)
    st.execute(cmd)
    assert not any(p.entity_id == cam.id for p in build_plan_frame(doc).primitives)
    doc.work_plane = WorkPlane(origin=(0.0, 0.0, 3.0))
    assert any(p.entity_id == cam.id and p.role == 'camera' for p in build_plan_frame(doc).primitives)


def test_cone_shows_the_horizontal_angle_and_handles():
    p = cameras.make_params(0, 0, 90.0, fov=60.0)
    pts = cameras.cone(p)
    assert pts[0] == (0.0, 0.0)
    left = math.degrees(math.atan2(pts[1][1], pts[1][0]))
    right = math.degrees(math.atan2(pts[-1][1], pts[-1][0]))
    assert left == pytest.approx(60.0) and right == pytest.approx(120.0)
    assert cameras.aim_point(p) == pytest.approx((0.0, cameras.CONE_LENGTH))
    from archforge.core.plan_scene import selection_handles
    doc = Document(); st = CommandStack(doc)
    cmd, cam = cameras.add_camera_command(doc, 1.0, 1.0, 0.0)
    st.execute(cmd)
    doc.select([cam.id])
    hs = {h.handle: (h.x, h.y) for h in selection_handles(doc)}
    assert hs['camera_move'] == (1.0, 1.0) and hs['camera_aim'] == pytest.approx((1.0 + cameras.CONE_LENGTH, 1.0))


def test_move_and_rotate_commands_are_one_undo_each():
    doc = Document(); st = CommandStack(doc)
    cmd, cam = cameras.add_camera_command(doc, 1.0, 1.0, 0.0)
    st.execute(cmd)
    st.execute(cameras.move_command(doc, cam.id, 2.0, -0.5))
    assert (doc.get(cam.id).params['x'], doc.get(cam.id).params['y']) == (3.0, 0.5)
    st.execute(cameras.aim_command(doc, cam.id, 3.0, 5.0))                 # look north
    assert doc.get(cam.id).params['heading'] == pytest.approx(90.0)
    st.execute(cameras.rotate_command(doc, cam.id, 300.0))
    assert doc.get(cam.id).params['heading'] == pytest.approx(30.0)
    assert cameras.aim_command(doc, cam.id, 3.0, 0.5) is None                  # on the eye: no direction
    st.undo(); assert doc.get(cam.id).params['heading'] == pytest.approx(90.0)
    st.undo(); assert doc.get(cam.id).params['heading'] == pytest.approx(0.0)
    st.undo(); assert (doc.get(cam.id).params['x'], doc.get(cam.id).params['y']) == (1.0, 1.0)


def test_view_payload_and_saving_a_view():
    doc = Document()
    doc.levels['Floor 2'] = 3.0
    cam = cameras.make_camera(doc, 2.0, 1.0, 90.0, level_z=3.0, height=1.5, fov=70.0, pitch=-5.0)
    v = cameras.view_payload(cam)
    assert v['kind'] == 'camera' and v['camera_id'] == cam.id and v['eye'] == pytest.approx(4.5)
    assert (v['x1'], v['y1']) == (2.0, 1.0) and v['x2'] == pytest.approx(2.0) and v['y2'] == pytest.approx(2.0)
    assert v['hfov'] == 70.0 and v['pitch'] == -5.0 and v['z'] == 3.0
    p = cameras.params_from_view(doc, {'position': [1.0, 2.0, 4.7], 'target': [1.0, 4.0, 4.7], 'hfov': 72.3})
    assert p['level_z'] == 3.0 and p['height'] == pytest.approx(1.7) and p['heading'] == pytest.approx(90.0)
    assert p['pitch'] == pytest.approx(0.0) and p['fov'] == pytest.approx(72.3)
    p = cameras.params_from_view(doc, {'position': [0, 0, 1.6], 'target': [1, 0, 0.6], 'hfov': 200})
    assert p['level_z'] == 0.0 and p['pitch'] == pytest.approx(-45.0) and p['fov'] == 120.0


# --- the window: tool, list, 3D payload ------------------------------------------------------------

def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window():
    from archforge.ui.main_window import MainWindow
    app = _app()
    w = MainWindow()
    w.show()
    app.processEvents()
    _walls(w.doc, w.stack)
    yield w
    w._mark_clean()
    w.close()
    app.processEvents()


class _Ev:
    """Minimal mouse event for the plan's camera hook (position in viewport pixels)."""

    def __init__(self, view, x, y, button=Qt.MouseButton.LeftButton, mods=Qt.KeyboardModifier.NoModifier):
        self._pos = QPointF(view.mapFromScene(QPointF(x, y)))
        self._button = button
        self._mods = mods

    def position(self):
        return self._pos

    def button(self):
        return self._button

    def modifiers(self):
        return self._mods


def test_tool_click_move_click_places_a_camera_and_jumps_the_3d(window):
    from archforge.ui.camera_tool import start_place
    plan = window.plan_view
    start_place(window)
    assert plan.controller.tool == 'camera'
    tool = plan.camera_tool
    assert tool.handle(plan, 'press', _Ev(plan, 1.0, 1.0))
    assert tool.handle(plan, 'release', _Ev(plan, 1.0, 1.0))
    assert tool.placing is not None                                        # a click: the eye is set, now aim
    tool.handle(plan, 'move', _Ev(plan, 4.0, 1.0))
    assert tool.placing['heading'] == pytest.approx(0.0, abs=1.0)
    tool.handle(plan, 'press', _Ev(plan, 4.0, 4.0))                        # second click = done, looking NE
    cams = cameras.cameras(window.doc)
    assert len(cams) == 1 and cams[0].name == 'Κάμερα 1'
    p = cams[0].params
    assert p['x'] == pytest.approx(1.0, abs=.05) and p['heading'] == pytest.approx(45.0, abs=1.5)
    assert plan.controller.tool == 'select' and window.doc.selection == [cams[0].id]
    line = window.pbr_view._view_line
    assert line['kind'] == 'camera' and line['camera_id'] == cams[0].id and line['eye'] == pytest.approx(1.6)
    assert window._central_tabs.currentIndex() == 1
    window._undo()
    assert not cameras.cameras(window.doc)


def test_dragging_the_body_moves_and_the_cone_tip_turns(window):
    cmd, cam = cameras.add_camera_command(window.doc, 1.0, 1.0, 0.0)
    window.stack.execute(cmd)
    plan = window.plan_view
    window._central_tabs.setCurrentIndex(0)
    plan.resize(900, 700)
    plan.centerOn(3.0, 2.0)
    plan.redraw()
    tool = plan.camera_tool
    # Press on the body (just behind the eye), drag, release: one move.
    assert tool.handle(plan, 'press', _Ev(plan, 0.85, 1.0))
    tool.handle(plan, 'move', _Ev(plan, 2.85, 2.0))
    tool.handle(plan, 'release', _Ev(plan, 2.85, 2.0))
    p = window.doc.get(cam.id).params
    assert (p['x'], p['y']) == pytest.approx((3.0, 2.0), abs=.03) and p['heading'] == 0.0
    # The handle at the tip of the cone turns it.
    plan.redraw()
    ax, ay = cameras.aim_point(p)
    assert tool.handle(plan, 'press', _Ev(plan, ax, ay))
    assert tool.drag['mode'] == 'aim'
    tool.handle(plan, 'move', _Ev(plan, 3.0, 5.0))
    tool.handle(plan, 'release', _Ev(plan, 3.0, 5.0))
    assert window.doc.get(cam.id).params['heading'] == pytest.approx(90.0, abs=1.0)
    window._undo()
    assert window.doc.get(cam.id).params['heading'] == 0.0
    window._undo()
    assert window.doc.get(cam.id).params['x'] == 1.0


def test_list_click_sets_the_3d_view_and_rename(window):
    m = window._cameras
    a = cameras.make_camera(window.doc, 1.0, 1.0, 0.0)
    window.stack.execute(AddEntity(a))
    b = cameras.make_camera(window.doc, 5.0, 3.0, 225.0, fov=80.0)
    window.stack.execute(AddEntity(b))
    assert [m.list.item(i).text() for i in range(m.list.count())] == ['Κάμερα 1', 'Κάμερα 2']
    m.list.itemClicked.emit(m.list.item(1))
    line = window.pbr_view._view_line
    assert line['camera_id'] == b.id and line['hfov'] == 80.0 and line['eye'] == pytest.approx(1.6)
    assert (line['x1'], line['y1']) == (5.0, 3.0)
    assert math.degrees(math.atan2(line['y2'] - line['y1'], line['x2'] - line['x1'])) % 360 == pytest.approx(225.0)
    assert m.active_id == b.id and window.tabs.currentWidget() is window.pbr_view
    # Editing the active camera moves the 3D live.
    window.stack.execute(cameras.move_command(window.doc, b.id, -1.0, 0.0))
    assert window.pbr_view._view_line['x1'] == 4.0 and window.pbr_view._view_line['smooth'] is False
    # Another preset, then «Επιστροφή στην κάμερα».
    window._set_pbr_camera('orbit')
    assert window.pbr_view._view_line is None
    m.back()
    assert window.pbr_view._view_line['camera_id'] == b.id
    # Double-click renames (one undo).
    item = m.list.item(0)
    item.setText('Σαλόνι')
    assert window.doc.get(a.id).name == 'Σαλόνι'
    window._undo()
    assert window.doc.get(a.id).name == 'Κάμερα 1'
    # The «Κάμερες ▾» popup lists them too.
    m.fill_menu(window._cameras_popup)
    texts = [x.text() for x in window._cameras_popup.actions()]
    assert texts[:2] == ['Κάμερα 1', 'Κάμερα 2'] and 'Από εδώ που κοιτάζω τώρα' in texts and 'Επιστροφή στην κάμερα' in texts


def test_save_current_view_as_a_camera(window, monkeypatch):
    state = {'position': [2.0, 1.0, 1.75], 'target': [2.0, 3.0, 1.75], 'hfov': 66.0}
    monkeypatch.setattr(window.pbr_view, 'request_camera_state', lambda cb: cb(state))
    window._cameras.save_current()
    cams = cameras.cameras(window.doc)
    assert len(cams) == 1
    p = cams[0].params
    assert p['heading'] == pytest.approx(90.0) and p['height'] == pytest.approx(1.75) and p['fov'] == pytest.approx(66.0)
    assert window.pbr_view._view_line['camera_id'] == cams[0].id
    window._undo()
    assert not cameras.cameras(window.doc)


def test_delete_and_properties(window):
    cam = cameras.make_camera(window.doc, 1.0, 1.0, 0.0)
    window.stack.execute(AddEntity(cam))
    window.doc.select([cam.id])
    window.refresh_inspector()
    labels = [window.form.itemAt(i, window.form.ItemRole.LabelRole).widget().text()
              for i in range(window.form.rowCount())
              if window.form.itemAt(i, window.form.ItemRole.LabelRole) is not None]
    assert {'Ύψος ματιού', 'Γωνία θέασης', 'Κατεύθυνση', 'Όροφος'} <= set(labels)
    window._cameras.update(cam.id, height=1.2, fov=90.0)
    assert window.doc.get(cam.id).params['height'] == 1.2 and window.doc.get(cam.id).params['fov'] == 90.0
    from archforge.ui.marking_menu import build_menu
    entries = [e['id'] for e in build_menu(window, 'plan', cam.id)['entries']]
    assert 'delete' in entries and 'mm:camera:view' in entries
    window.doc.select([cam.id])
    window._delete_selection()
    assert cam.id not in window.doc.entities
    window._undo()
    assert cam.id in window.doc.entities
