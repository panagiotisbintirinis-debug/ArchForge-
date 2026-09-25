import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from archforge.architecture.rooms import room_slab_geometry
from archforge.core.commands import CommandStack, CreateRoomRoofs
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.selection import BrushSpec, SurfaceHit
from archforge.geometry.sculpt import SculptedPreviewBackend
from archforge.geometry.sculpt_transaction import SculptTransaction
from archforge.ui.main_window import MainWindow
from archforge.ui.viewport_3d import Viewport3D


def _closed_room(height=3.0):
    doc = Document()
    walls = [
        Entity('wall', {'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':height,'thickness':.2}),
        Entity('wall', {'x1':4,'y1':0,'x2':4,'y2':3,'z':0,'height':height,'thickness':.2}),
        Entity('wall', {'x1':4,'y1':3,'x2':0,'y2':3,'z':0,'height':height,'thickness':.2}),
        Entity('wall', {'x1':0,'y1':3,'x2':0,'y2':0,'z':0,'height':height,'thickness':.2}),
    ]
    for wall in walls:
        doc.add(wall)
    return doc, walls


def _polygon_snapshot(view, entity_id):
    items = view._render_cache[entity_id].mesh_items
    return tuple(
        tuple((point.x(), point.y()) for point in item.polygon())
        for item in items
        if item.isVisible()
    )


def test_flat_roof_sits_on_common_wall_top_and_is_undoable():
    doc, walls = _closed_room(height=3.0)
    stack = CommandStack(doc)
    faces = doc.active_room_faces()
    assert len(faces) == 1

    command = CreateRoomRoofs([faces[0].signature], thickness=.20)
    stack.execute(command)

    roofs = [e for e in doc.entities.values() if e.kind == 'room_roof']
    assert len(roofs) == 1
    roof = roofs[0]
    assert roof.params['roof_type'] == 'flat'

    geom = room_slab_geometry(doc, roof)
    assert geom is not None
    assert geom['z'] == pytest.approx(3.0)
    assert geom['thickness'] == pytest.approx(.20)

    mesh = TessellatedPreviewBackend().evaluate(doc).body(roof.id).payload
    assert min(v[2] for v in mesh.vertices) == pytest.approx(3.0)
    assert max(v[2] for v in mesh.vertices) == pytest.approx(3.20)

    frame = build_plan_frame(doc)
    roof_primitives = [
        p for p in frame.primitives
        if p.entity_id == roof.id and p.role == 'room-roof'
    ]
    assert len(roof_primitives) == 1

    stack.undo()
    assert roof.id not in doc.entities
    stack.redo()
    assert roof.id in doc.entities


def test_flat_roof_rejects_non_level_boundary_without_partial_creation():
    doc, walls = _closed_room(height=3.0)
    doc.update(walls[1].id, {'height': 3.5})
    stack = CommandStack(doc)
    face = doc.active_room_faces()[0]

    with pytest.raises(ValueError, match='common top elevation'):
        stack.execute(CreateRoomRoofs([face.signature]))

    assert not any(e.kind == 'room_roof' for e in doc.entities.values())
    assert stack.done == []


def test_sculpt_live_preview_changes_visible_viewport_before_commit():
    app = QApplication.instance() or QApplication([])
    doc = Document()
    wall = Entity(
        'wall',
        {'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2},
        id='sculpt-wall',
    )
    doc.add(wall)
    stack = CommandStack(doc)
    view = Viewport3D(doc, stack)
    view.resize(800, 600)
    view.show()
    app.processEvents()
    try:
        view.redraw(force_full=True)
        before = _polygon_snapshot(view, wall.id)

        tx = SculptTransaction(
            doc,
            stack,
            SurfaceHit(wall.id, 'exterior', (2.0, .1, 1.5), (0.0, 1.0, 0.0)),
            BrushSpec(.35, 1.0, 'smooth'),
            'pull',
            .30,
        )
        view._sculpt_tx = tx
        view.redraw(force_full=True)
        during = _polygon_snapshot(view, wall.id)

        assert during != before
        assert doc.surface_modifiers == {}
        assert stack.done == []

        tx.commit()
        view._sculpt_tx = None
        view.redraw(force_full=True)

        assert len(doc.surface_modifiers) == 1
        assert len(stack.done) == 1
        committed = _polygon_snapshot(view, wall.id)
        assert committed == during
    finally:
        view.close()
        app.processEvents()


def test_sculpt_dense_preview_moves_only_local_wall_vertices():
    doc = Document()
    wall = Entity(
        'wall',
        {'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2},
        id='local-wall',
    )
    doc.add(wall)
    stack = CommandStack(doc)

    dense_base = SculptedPreviewBackend(
        dense_entity_ids={wall.id},
        wall_target_step=.15,
    ).evaluate(doc).body(wall.id).payload

    tx = SculptTransaction(
        doc,
        stack,
        SurfaceHit(wall.id, 'exterior', (2.0, .1, 1.5), (0.0, 1.0, 0.0)),
        BrushSpec(.35, 1.0, 'smooth'),
        'pull',
        .30,
    )
    preview = tx.preview_mesh()

    assert len(preview.vertices) == len(dense_base.vertices)
    moved = []
    unchanged = []
    for before, after in zip(dense_base.vertices, preview.vertices):
        delta = sum((after[i] - before[i]) ** 2 for i in range(3)) ** .5
        distance = sum((before[i] - (2.0, .1, 1.5)[i]) ** 2 for i in range(3)) ** .5
        if delta > 1e-9:
            moved.append((distance, delta))
        else:
            unchanged.append(distance)

    assert moved
    assert unchanged
    assert max(distance for distance, _delta in moved) < .35 + 1e-9
    assert any(distance > 1.0 for distance in unchanged)


def test_sculpt_toolbar_controls_real_viewport_brush_and_flat_roof_action():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.sculpt_operation.setCurrentText('push')
        window.sculpt_radius.setValue(.40)

        assert window.view_3d.sculpt_op == 'push'
        assert window.view_3d.sculpt_brush.radius == pytest.approx(.40)
        assert window.view_3d.sculpt_brush.strength == pytest.approx(1.0)

        walls = [
            Entity('wall', {'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2}),
            Entity('wall', {'x1':4,'y1':0,'x2':4,'y2':3,'z':0,'height':3,'thickness':.2}),
            Entity('wall', {'x1':4,'y1':3,'x2':0,'y2':3,'z':0,'height':3,'thickness':.2}),
            Entity('wall', {'x1':0,'y1':3,'x2':0,'y2':0,'z':0,'height':3,'thickness':.2}),
        ]
        for wall in walls:
            window.doc.add(wall)

        window._create_flat_roofs()
        assert any(e.kind == 'room_roof' for e in window.doc.entities.values())
    finally:
        window.view_3d.close()
        window.close()
        app.processEvents()
