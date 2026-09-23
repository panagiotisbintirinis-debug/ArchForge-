import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_OPENGL', 'software')

from PySide6.QtWidgets import QApplication

from archforge.core.commands import ApplyStructuralFrame, CommandStack
from archforge.core.model import (
    Document,
    Entity,
    LAYER_ALL,
    LAYER_ARCHITECTURE,
    LAYER_STRUCTURAL,
)
from archforge.core.plan_scene import build_plan_frame
from archforge.ui.main_window import MainWindow


def _architecture_box():
    return Entity(
        'box',
        {
            'x': 4.0,
            'y': 4.0,
            'z': 0.0,
            'width': 1.0,
            'depth': 1.0,
            'height': 1.0,
            'rotation': 0.0,
        },
        id='architecture-box',
    )


def _structural_command():
    return ApplyStructuralFrame(
        columns=[
            {
                'id': 'column-c1',
                'cx': 0.0,
                'cy': 0.0,
                'base_z': 0.0,
                'width': 0.30,
                'depth': 0.30,
                'height': 3.0,
            }
        ],
        beams=[
            {
                'id': 'beam-b1',
                'x1': 0.0,
                'y1': 0.0,
                'x2': 4.0,
                'y2': 0.0,
                'z': 2.5,
                'depth': 0.50,
                'thickness': 0.30,
            }
        ],
        slabs=[
            {
                'id': 'slab-s1',
                'contour_vertices': [
                    [0.0, 0.0],
                    [4.0, 0.0],
                    [4.0, 3.0],
                    [0.0, 3.0],
                ],
                'thickness': 0.20,
                'z': 3.0,
            }
        ],
        footings=[
            {
                'id': 'footing-f1',
                'cx': 0.0,
                'cy': 0.0,
                'base_z': -0.50,
                'width': 1.20,
                'depth': 1.20,
                'thickness': 0.50,
            }
        ],
    )


def test_structural_frame_rejects_invalid_dimensions_without_partial_commit():
    doc = Document()
    stack = CommandStack(doc)
    command = ApplyStructuralFrame(
        columns=[
            {
                'id': 'bad-column',
                'cx': 0.0,
                'cy': 0.0,
                'base_z': 0.0,
                'width': 0.0,
                'depth': 0.30,
                'height': 3.0,
            }
        ]
    )

    with pytest.raises(ValueError, match='dimension must be > 0'):
        stack.execute(command)

    assert 'bad-column' not in doc.entities
    assert stack.done == []


def test_structural_frame_bakes_all_components_as_authoritative_structural_meshes():
    doc = Document()
    stack = CommandStack(doc)
    command = _structural_command()
    stack.execute(command)

    assert set(command.ids) == {
        'column-c1', 'beam-b1', 'slab-s1', 'footing-f1'
    }

    for entity_id in command.ids:
        entity = doc.get(entity_id)
        assert entity.kind == 'mesh'
        assert entity.layer_id == LAYER_STRUCTURAL
        assert entity.params['vertices']
        assert entity.params['faces']
        assert entity.params['metadata']['engineering_verified'] is False
        assert entity.params['metadata']['structural_kind'] in {
            'column', 'beam', 'slab', 'footing'
        }

    assert len(doc.get('column-c1').params['vertices']) == 8
    assert len(doc.get('beam-b1').params['vertices']) == 8
    assert len(doc.get('footing-f1').params['vertices']) == 8
    assert len(doc.get('slab-s1').params['vertices']) == 8

    stack.undo()
    assert all(entity_id not in doc.entities for entity_id in command.ids)
    stack.redo()
    assert all(doc.get(entity_id).kind == 'mesh' for entity_id in command.ids)


def test_structural_layer_mask_isolates_structural_meshes_in_plan_and_serialization():
    doc = Document()
    doc.add(_architecture_box())
    CommandStack(doc).execute(_structural_command())

    assert doc.get('architecture-box').layer_id == LAYER_ARCHITECTURE
    assert doc.visible_layers_mask == LAYER_ALL

    doc.set_visible_layers_mask(LAYER_STRUCTURAL)
    assert not doc.entity_is_visible('architecture-box')
    assert doc.entity_is_visible('column-c1')
    assert doc.entity_is_visible('slab-s1')

    frame = build_plan_frame(doc)
    rendered_ids = {
        primitive.entity_id
        for primitive in frame.primitives
        if primitive.entity_id
    }
    assert 'architecture-box' not in rendered_ids
    assert {'column-c1', 'beam-b1', 'slab-s1', 'footing-f1'} <= rendered_ids

    restored = Document.from_dict(doc.to_dict())
    assert restored.visible_layers_mask == LAYER_STRUCTURAL
    assert restored.get('column-c1').layer_id == LAYER_STRUCTURAL
    assert not restored.entity_is_visible('architecture-box')


def test_main_window_structural_checkbox_applies_shared_layer_mask():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.doc.add(_architecture_box())
        window.stack.execute(_structural_command())

        window.structural_only_checkbox.setChecked(True)
        app.processEvents()

        assert window.doc.visible_layers_mask == LAYER_STRUCTURAL
        assert window.doc.entity_is_visible('column-c1')
        assert not window.doc.entity_is_visible('architecture-box')
        assert 'architecture-box' not in window.view_3d._render_cache

        window.structural_only_checkbox.setChecked(False)
        app.processEvents()
        assert window.doc.visible_layers_mask == LAYER_ALL
        assert window.doc.entity_is_visible('architecture-box')
    finally:
        window.view_3d.thread_pool.waitForDone(5000)
        window.close()
        app.processEvents()
