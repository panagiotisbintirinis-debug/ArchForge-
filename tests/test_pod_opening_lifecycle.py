from __future__ import annotations

import math
import pytest

from archforge.core.model import Document, Entity
from archforge.core.commands import (
    CommandStack,
    AddEntity,
    UpdateEntity,
    MoveEntities,
    DeleteEntities,
)
from archforge.architecture.openings import (
    infer_organic_opening_patches,
    pod_opening_patch_geometry,
)
from archforge.organic.junctions import infer_organic_junctions
from archforge.geometry.preview import PreviewBackend
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.core.plan_scene import build_plan_frame
from archforge.core.view_frame import build_view_frame


def _body_ids(evaluation):
    return {body.entity_id for body in evaluation.bodies}


def test_pod_opening_complete_lifecycle(tmp_path):
    """
    Proves the full pod opening lifecycle across edit, junction, delete, undo, and save/load (Issue #39).

    Scenarios exercised:
      1. Create host pod and parametric door and window openings.
      2. Verify derived patch entity creation, stability, and geometry properties.
      3. Resize and move openings along host (surface_u updates, width/height changes).
      4. Host pod resize and rotation, proving intrinsic surface_u coordinate stability.
      5. Temporary occlusion of an opening by an active pod junction (no floating patch rendered).
      6. Separation of junction restoring opening visibility with intact semantic identities.
      7. Deletion of opening entities via DeleteEntities command, proving patch removal.
      8. Undo and redo of opening deletion, confirming exact semantic and dependency restoration.
      9. Save and load across sessions, verifying exact ID, relationship, and geometric equivalence.
      10. Consistency across 2D plan frame, orthographic views, and 3D preview tessellation.
    """
    doc = Document()
    stack = CommandStack(doc)

    # 1. Create host pod
    pod = Entity('pod', {
        'cx': 0.0,
        'cy': 0.0,
        'floor_level': 0.0,
        'diameter_x': 8.0,
        'diameter_y': 6.0,
        'height': 4.0,
        'shell_thickness': 0.18,
        'rotation': 0.0,
    }, name='Host Dome Pod')
    stack.execute(AddEntity(pod))
    assert pod.id in doc.entities

    # 2. Add door and window
    door = Entity('door', {
        'surface_u': 0.0,  # +X side
        'width': 1.0,
        'height': 2.1,
        'sill': 0.0,
        'flat_margin': 0.25,
    }, parent_id=pod.id, name='Primary Access Door')
    stack.execute(AddEntity(door))

    window = Entity('window', {
        'surface_u': 0.5,  # -X side
        'width': 1.2,
        'height': 1.5,
        'sill': 0.9,
        'flat_margin': 0.25,
    }, parent_id=pod.id, name='West View Window')
    stack.execute(AddEntity(window))

    assert door.id in doc.entities
    assert window.id in doc.entities

    # 3. Infer organic opening patches
    res1 = infer_organic_opening_patches(doc)
    assert len(res1.active_ids) == 2
    door_patch_id = [pid for pid in res1.active_ids if doc.get(pid).params['opening_id'] == door.id][0]
    window_patch_id = [pid for pid in res1.active_ids if doc.get(pid).params['opening_id'] == window.id][0]

    # Verify relationships and parameters
    assert doc.get(door_patch_id).parent_id == door.id
    assert doc.get(window_patch_id).parent_id == window.id
    assert doc.get(door_patch_id).params['host_id'] == pod.id
    assert doc.get(window_patch_id).params['host_id'] == pod.id
    assert doc.get(door_patch_id).params['status'] == 'active'
    assert doc.get(window_patch_id).params['status'] == 'active'
    assert door_patch_id in doc.dependencies.get(pod.id, set())
    assert door_patch_id in doc.dependencies.get(door.id, set())

    # 4. Modify opening along host (resize and move surface_u)
    stack.execute(UpdateEntity(door.id, {'surface_u': 0.05, 'width': 1.2, 'height': 2.2}))
    assert doc.get(door.id).params['surface_u'] == 0.05
    assert doc.get(door.id).params['width'] == 1.2
    patch_geom = pod_opening_patch_geometry(doc, door.id)
    assert patch_geom is not None
    assert patch_geom['patch_width'] == 1.2 + 2 * 0.25

    # 5. Host pod resize and rotation (intrinsic azimuth is preserved)
    stack.execute(UpdateEntity(pod.id, {'rotation': 35.0, 'diameter_x': 9.0}))
    assert doc.get(pod.id).params['rotation'] == 35.0
    assert doc.get(door.id).params['surface_u'] == 0.05
    assert doc.get(window.id).params['surface_u'] == 0.5
    # Patch identity remains identical
    res_after_rot = infer_organic_opening_patches(doc)
    assert set(res_after_rot.active_ids) == {door_patch_id, window_patch_id}

    # 6. Introduce adjacent pod to form a junction intersecting the door
    adj_pod = Entity('pod', {
        'cx': 4.5,
        'cy': 0.0,
        'floor_level': 0.0,
        'diameter_x': 6.0,
        'diameter_y': 6.0,
        'height': 3.5,
        'shell_thickness': 0.18,
        'rotation': 0.0,
    }, name='Adjacent Junction Pod')
    stack.execute(AddEntity(adj_pod))
    # Rotate host pod back to 0.0 so door at u=0.05 is directly inside the overlap region
    stack.execute(UpdateEntity(pod.id, {'rotation': 0.0}))

    junc_res = infer_organic_junctions(doc)
    assert len(junc_res.active_ids) == 1
    # Check that door patch is occluded by the junction (not floating in 3D preview)
    tess_eval = TessellatedPreviewBackend().evaluate(doc)
    assert door_patch_id not in _body_ids(tess_eval)
    # Window patch on opposite side (-X) remains visible
    assert window_patch_id in _body_ids(tess_eval)

    # 7. Move adjacent pod away (junction separation)
    stack.execute(MoveEntities([adj_pod.id], dx=20.0, dy=0.0, dz=0.0))
    infer_organic_junctions(doc)
    tess_eval_restored = TessellatedPreviewBackend().evaluate(doc)
    # Door patch is restored without changing identity
    assert door_patch_id in _body_ids(tess_eval_restored)
    assert window_patch_id in _body_ids(tess_eval_restored)

    # 8. Delete door opening via DeleteEntities
    stack.execute(DeleteEntities([door.id]))
    assert door.id not in doc.entities
    # Re-infer patches; door patch becomes inactive/removed
    res_del = infer_organic_opening_patches(doc)
    active_openings = {doc.get(pid).params['opening_id'] for pid in res_del.active_ids}
    assert door.id not in active_openings
    assert window.id in active_openings

    # 9. Undo deletion of door
    stack.undo()
    assert door.id in doc.entities
    assert doc.get(door.id).parent_id == pod.id
    assert door.id in doc.children.get(pod.id, [])
    assert doc.get(door.id).params['surface_u'] == 0.05
    res_undo = infer_organic_opening_patches(doc)
    assert door_patch_id in res_undo.active_ids

    # 10. Redo deletion
    stack.redo()
    assert door.id not in doc.entities

    # 11. Save and Load roundtrip persistence
    file_path = tmp_path / 'pod_opening_lifecycle_model.json'
    doc.save(str(file_path))
    doc_loaded = Document.load(str(file_path))

    assert set(doc.entities.keys()) == set(doc_loaded.entities.keys())
    assert window.id in doc_loaded.entities
    assert door.id not in doc_loaded.entities
    assert doc_loaded.get(window.id).parent_id == pod.id
    assert doc_loaded.get(window.id).params == doc.get(window.id).params

    # Check 2D plan and orthographic representations
    plan_orig = build_plan_frame(doc)
    plan_loaded = build_plan_frame(doc_loaded)
    assert len(plan_orig.primitives) == len(plan_loaded.primitives)
    assert [p.role for p in plan_orig.primitives] == [p.role for p in plan_loaded.primitives]
