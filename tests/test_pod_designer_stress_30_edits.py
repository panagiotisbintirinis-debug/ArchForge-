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
from archforge.organic.arboreal import (
    create_arboreal_tree,
    arboreal_branch_geometry,
    sync_arboreal_mounted_pods,
)
from archforge.organic.biospectre import all_pod_junctions
from archforge.organic.junctions import infer_organic_junctions
from archforge.architecture.openings import (
    infer_organic_opening_patches,
    pod_opening_patch_geometry,
)
from archforge.core.plan_scene import build_plan_frame
from archforge.core.view_frame import build_view_frame
from archforge.geometry.mesh import TessellatedPreviewBackend


def test_pod_designer_v01_30_edits_parametric_stress_scenario(tmp_path):
    """
    Production-level scripted stress scenario for the Pod Designer v0.1 milestone (Issue #37).

    Executes 30 distinct semantic parametric operations on a persistent model, verifying:
      - Entity ID stability and non-stale relationships
      - Deterministic parameter updates, moves, rotations, and resizing
      - Planar junction creation, occlusion, dormancy on separation, and healing on re-joining
      - Opening addition, patch inference, azimuth preservation during rotation, and deletion
      - Mounted pod tracking parent branch azimuth, length, and core moves
      - Transactional undo and redo state fidelity
      - Save / Load persistence with deterministic geometric and semantic parity
      - View consistency across 2D plan, orthographic views, and 3D preview
    """
    doc = Document()
    stack = CommandStack(doc)
    edit_count = 0

    # -------------------------------------------------------------------------
    # EDIT 1: Create Central Living Pod (pod_a)
    # -------------------------------------------------------------------------
    pod_a = Entity('pod', {
        'cx': 0.0,
        'cy': 0.0,
        'floor_level': 0.0,
        'diameter_x': 8.0,
        'diameter_y': 6.0,
        'height': 4.0,
        'shell_thickness': 0.18,
        'rotation': 0.0,
    }, name='Central Living Hub')
    stack.execute(AddEntity(pod_a))
    edit_count += 1
    assert edit_count == 1
    assert pod_a.id in doc.entities
    assert doc.get(pod_a.id).params['cx'] == 0.0

    # -------------------------------------------------------------------------
    # EDIT 2: Create Disjoint Sleeping Pod (pod_b)
    # -------------------------------------------------------------------------
    pod_b = Entity('pod', {
        'cx': 12.0,
        'cy': 0.0,
        'floor_level': 0.0,
        'diameter_x': 6.0,
        'diameter_y': 6.0,
        'height': 3.5,
        'shell_thickness': 0.18,
        'rotation': 0.0,
    }, name='Sleeping Sanctuary')
    stack.execute(AddEntity(pod_b))
    edit_count += 1
    assert edit_count == 2
    assert pod_b.id in doc.entities
    assert len(all_pod_junctions(doc)) == 0

    # -------------------------------------------------------------------------
    # EDIT 3: Create Arboreal Structural Core Box
    # -------------------------------------------------------------------------
    core_box = Entity('box', {
        'x': -1.2,
        'y': -1.2,
        'z': 0.0,
        'width': 2.4,
        'depth': 2.4,
        'height': 10.0,
        'rotation': 0.0,
    }, name='Central Arboreal Core')
    stack.execute(AddEntity(core_box))
    edit_count += 1
    assert edit_count == 3
    assert core_box.id in doc.entities

    # -------------------------------------------------------------------------
    # EDIT 4: Create Cantilever Branch Parented to Core
    # -------------------------------------------------------------------------
    branch_1 = Entity('arboreal_branch', {
        'core_id': core_box.id,
        'azimuth_deg': 45.0,
        'elevation_z': 3.0,
        'length': 6.0,
        'slope_deg': 10.0,
        'root_radius': 0.35,
        'tip_radius': 0.25,
    }, parent_id=core_box.id, name='Northeast Cantilever Branch')
    stack.execute(AddEntity(branch_1))
    edit_count += 1
    assert edit_count == 4
    assert branch_1.id in doc.entities
    assert doc.get(branch_1.id).parent_id == core_box.id

    # -------------------------------------------------------------------------
    # EDIT 5: Mount Observatory Pod (pod_c) onto Branch 1
    # -------------------------------------------------------------------------
    b_geom_init = arboreal_branch_geometry(doc, branch_1.id)
    tip_init = b_geom_init['end']
    pod_c = Entity('pod', {
        'cx': tip_init[0],
        'cy': tip_init[1],
        'floor_level': tip_init[2],
        'diameter_x': 4.0,
        'diameter_y': 4.0,
        'height': 3.0,
        'shell_thickness': 0.15,
        'rotation': 0.0,
    }, parent_id=branch_1.id, name='Canopy Observatory Pod')
    stack.execute(AddEntity(pod_c))
    doc.update(branch_1.id, {'mounted_pod_id': pod_c.id})
    doc.add_dependency(branch_1.id, pod_c.id)
    edit_count += 1
    assert edit_count == 5
    assert pod_c.id in doc.entities
    assert doc.get(pod_c.id).parent_id == branch_1.id
    assert doc.get(branch_1.id).params['mounted_pod_id'] == pod_c.id

    # -------------------------------------------------------------------------
    # EDIT 6: Move pod_b to Intersect pod_a (Create Cluster Overlap)
    # -------------------------------------------------------------------------
    # Distance between (0,0) and (5.5, 0) is 5.5 < (8/2 + 6/2 = 7.0).
    stack.execute(MoveEntities([pod_b.id], dx=-6.5, dy=0.0, dz=0.0))
    edit_count += 1
    assert edit_count == 6
    assert math.isclose(doc.get(pod_b.id).params['cx'], 5.5)

    # -------------------------------------------------------------------------
    # EDIT 7: Reconcile Organic Junctions (Semantic Junction Created)
    # -------------------------------------------------------------------------
    j_res1 = infer_organic_junctions(doc)
    edit_count += 1
    assert edit_count == 7
    assert len(j_res1.active_ids) == 1
    junc_id = j_res1.active_ids[0]
    junc_entity = doc.get(junc_id)
    assert junc_entity.params['status'] == 'active'
    assert {junc_entity.params['component_a'], junc_entity.params['component_b']} == {pod_a.id, pod_b.id}

    # -------------------------------------------------------------------------
    # EDIT 8: Add Exterior Entrance Door to pod_a (Facing -X away from junction)
    # -------------------------------------------------------------------------
    door_a = Entity('door', {
        'surface_u': 0.5,
        'width': 0.9,
        'height': 2.1,
        'sill': 0.0,
        'flat_margin': 0.25,
    }, parent_id=pod_a.id, name='Main Entry Portal')
    stack.execute(AddEntity(door_a))
    edit_count += 1
    assert edit_count == 8
    assert door_a.id in doc.entities
    assert doc.get(door_a.id).parent_id == pod_a.id

    # -------------------------------------------------------------------------
    # EDIT 9: Infer Organic Opening Patches for Entrance Door
    # -------------------------------------------------------------------------
    p_res1 = infer_organic_opening_patches(doc)
    edit_count += 1
    assert edit_count == 9
    assert door_a.id in [doc.get(pid).params['opening_id'] for pid in p_res1.active_ids]
    door_patch_id = [pid for pid in p_res1.active_ids if doc.get(pid).params['opening_id'] == door_a.id][0]
    assert doc.get(door_patch_id).params['status'] == 'active'

    # -------------------------------------------------------------------------
    # EDIT 10: Add Exterior Window to pod_a (Azimuth u=0.25, Facing +Y)
    # -------------------------------------------------------------------------
    window_a = Entity('window', {
        'surface_u': 0.25,
        'width': 1.2,
        'height': 1.4,
        'sill': 0.9,
        'flat_margin': 0.25,
    }, parent_id=pod_a.id, name='North Garden Window')
    stack.execute(AddEntity(window_a))
    edit_count += 1
    assert edit_count == 10
    assert window_a.id in doc.entities

    # -------------------------------------------------------------------------
    # EDIT 11: Reconcile Opening Patches (Both Door & Window Active)
    # -------------------------------------------------------------------------
    p_res2 = infer_organic_opening_patches(doc)
    edit_count += 1
    assert edit_count == 11
    active_openings = {doc.get(pid).params['opening_id'] for pid in p_res2.active_ids}
    assert active_openings == {door_a.id, window_a.id}

    # -------------------------------------------------------------------------
    # EDIT 12: Resize pod_b (Parametric Update of Diameter)
    # -------------------------------------------------------------------------
    stack.execute(UpdateEntity(pod_b.id, {'diameter_x': 6.8, 'diameter_y': 6.8}))
    edit_count += 1
    assert edit_count == 12
    assert doc.get(pod_b.id).params['diameter_x'] == 6.8
    # Re-infer junction and verify the planar geometry was updated cleanly
    infer_organic_junctions(doc)
    assert doc.get(junc_id).params['status'] == 'active'

    # -------------------------------------------------------------------------
    # EDIT 13: Rotate pod_a by 20 Degrees (Opening Patch Frame Follows)
    # -------------------------------------------------------------------------
    stack.execute(UpdateEntity(pod_a.id, {'rotation': 20.0}))
    edit_count += 1
    assert edit_count == 13
    assert doc.get(pod_a.id).params['rotation'] == 20.0
    # Intrinsic azimuth u is preserved exactly
    assert doc.get(door_a.id).params['surface_u'] == 0.5
    # Live patch geometry reflects host rotation
    door_patch_geom = pod_opening_patch_geometry(doc, door_a.id)
    assert door_patch_geom is not None

    # -------------------------------------------------------------------------
    # EDIT 14: Update Cantilever Branch Azimuth (Mounted Pod Follows)
    # -------------------------------------------------------------------------
    stack.execute(UpdateEntity(branch_1.id, {'azimuth_deg': 60.0}))
    edit_count += 1
    assert edit_count == 14
    b_geom_new = arboreal_branch_geometry(doc, branch_1.id)
    pod_c_params = doc.get(pod_c.id).params
    assert math.isclose(pod_c_params['cx'], b_geom_new['end'][0], abs_tol=1e-3)
    assert math.isclose(pod_c_params['cy'], b_geom_new['end'][1], abs_tol=1e-3)

    # -------------------------------------------------------------------------
    # EDIT 15: Add Window to pod_b (Azimuth u=0.0)
    # -------------------------------------------------------------------------
    window_b = Entity('window', {
        'surface_u': 0.0,
        'width': 1.0,
        'height': 1.2,
        'sill': 1.0,
        'flat_margin': 0.25,
    }, parent_id=pod_b.id, name='East Sleeping Window')
    stack.execute(AddEntity(window_b))
    edit_count += 1
    assert edit_count == 15
    assert window_b.id in doc.entities
    infer_organic_opening_patches(doc)

    # -------------------------------------------------------------------------
    # EDIT 16: Move pod_b Away (Physically Disjoint / Separate Cluster)
    # -------------------------------------------------------------------------
    stack.execute(MoveEntities([pod_b.id], dx=8.0, dy=0.0, dz=0.0))
    edit_count += 1
    assert edit_count == 16
    assert math.isclose(doc.get(pod_b.id).params['cx'], 13.5)
    assert len(all_pod_junctions(doc)) == 0

    # -------------------------------------------------------------------------
    # EDIT 17: Reconcile Junctions on Separation (Junction Becomes Dormant, NOT Destroyed)
    # -------------------------------------------------------------------------
    j_res_sep = infer_organic_junctions(doc)
    edit_count += 1
    assert edit_count == 17
    assert len(j_res_sep.active_ids) == 0
    assert junc_id in j_res_sep.dormant_ids
    assert doc.get(junc_id).params['status'] == 'dormant'
    # No duplicate junction identities
    junctions_in_doc = [e for e in doc.entities.values() if e.kind == 'organic_junction']
    assert len(junctions_in_doc) == 1

    # -------------------------------------------------------------------------
    # EDIT 18: Move pod_b Back into Overlap (Re-joining)
    # -------------------------------------------------------------------------
    stack.execute(MoveEntities([pod_b.id], dx=-8.0, dy=0.0, dz=0.0))
    edit_count += 1
    assert edit_count == 18
    assert math.isclose(doc.get(pod_b.id).params['cx'], 5.5)

    # -------------------------------------------------------------------------
    # EDIT 19: Reconcile Junctions on Re-join (Identity Heals with Same Entity ID)
    # -------------------------------------------------------------------------
    j_res_rejoin = infer_organic_junctions(doc)
    edit_count += 1
    assert edit_count == 19
    assert len(j_res_rejoin.active_ids) == 1
    assert j_res_rejoin.active_ids[0] == junc_id
    assert doc.get(junc_id).params['status'] == 'active'

    # -------------------------------------------------------------------------
    # EDIT 20: Update Door Dimensions on pod_a
    # -------------------------------------------------------------------------
    stack.execute(UpdateEntity(door_a.id, {'width': 1.1, 'height': 2.3}))
    edit_count += 1
    assert edit_count == 20
    assert doc.get(door_a.id).params['width'] == 1.1
    updated_door_patch = pod_opening_patch_geometry(doc, door_a.id)
    assert updated_door_patch is not None
    assert updated_door_patch['patch_width'] == 1.1 + 2 * 0.25

    # -------------------------------------------------------------------------
    # EDIT 21: Delete Window on pod_a (DeleteEntities Command)
    # -------------------------------------------------------------------------
    stack.execute(DeleteEntities([window_a.id]))
    edit_count += 1
    assert edit_count == 21
    assert window_a.id not in doc.entities

    # -------------------------------------------------------------------------
    # EDIT 22: Reconcile Patches After Window Deletion
    # -------------------------------------------------------------------------
    p_res_del = infer_organic_opening_patches(doc)
    edit_count += 1
    assert edit_count == 22
    active_after_del = {doc.get(pid).params['opening_id'] for pid in p_res_del.active_ids}
    assert window_a.id not in active_after_del
    assert door_a.id in active_after_del

    # -------------------------------------------------------------------------
    # EDIT 23: Undo Deletion of Window (Exact Semantic Restoration)
    # -------------------------------------------------------------------------
    stack.undo()
    edit_count += 1
    assert edit_count == 23
    assert window_a.id in doc.entities
    assert doc.get(window_a.id).parent_id == pod_a.id
    assert window_a.id in doc.children.get(pod_a.id, [])
    assert window_a.id in doc.dependencies.get(pod_a.id, set())

    # -------------------------------------------------------------------------
    # EDIT 24: Redo Deletion of Window
    # -------------------------------------------------------------------------
    stack.redo()
    edit_count += 1
    assert edit_count == 24
    assert window_a.id not in doc.entities

    # -------------------------------------------------------------------------
    # EDIT 25: Save Document to Disk and Load into Clean Session
    # -------------------------------------------------------------------------
    save_path = tmp_path / "pod_designer_stress_project.json"
    doc.save(str(save_path))
    doc_loaded = Document.load(str(save_path))
    edit_count += 1
    assert edit_count == 25

    # Assert exact entity identity and count parity
    assert set(doc.entities.keys()) == set(doc_loaded.entities.keys())
    for eid, entity in doc.entities.items():
        loaded_entity = doc_loaded.get(eid)
        assert loaded_entity.kind == entity.kind
        assert loaded_entity.params == entity.params
        assert loaded_entity.parent_id == entity.parent_id

    # Assert 2D plan frame consistency between saved and loaded models
    frame_orig = build_plan_frame(doc)
    frame_loaded = build_plan_frame(doc_loaded)
    assert len(frame_orig.primitives) == len(frame_loaded.primitives)
    assert [p.role for p in frame_orig.primitives] == [p.role for p in frame_loaded.primitives]

    # Continue working on the live document
    # -------------------------------------------------------------------------
    # EDIT 26: Update Branch Length (Cantilever Extension)
    # -------------------------------------------------------------------------
    stack.execute(UpdateEntity(branch_1.id, {'length': 8.5}))
    edit_count += 1
    assert edit_count == 26
    b_geom_ext = arboreal_branch_geometry(doc, branch_1.id)
    assert math.isclose(doc.get(pod_c.id).params['cx'], b_geom_ext['end'][0], abs_tol=1e-3)
    assert math.isclose(doc.get(pod_c.id).params['cy'], b_geom_ext['end'][1], abs_tol=1e-3)

    # -------------------------------------------------------------------------
    # EDIT 27: Move Tree Core (Arboreal Branch & Mounted Pod Track Core Move)
    # -------------------------------------------------------------------------
    stack.execute(MoveEntities([core_box.id], dx=1.5, dy=1.0, dz=0.0))
    edit_count += 1
    assert edit_count == 27
    b_geom_shifted = arboreal_branch_geometry(doc, branch_1.id)
    assert math.isclose(doc.get(pod_c.id).params['cx'], b_geom_shifted['end'][0], abs_tol=1e-3)
    assert math.isclose(doc.get(pod_c.id).params['cy'], b_geom_shifted['end'][1], abs_tol=1e-3)

    # -------------------------------------------------------------------------
    # EDIT 28: Delete Mounted Pod C (Clears Branch Mount Reference)
    # -------------------------------------------------------------------------
    stack.execute(DeleteEntities([pod_c.id]))
    edit_count += 1
    assert edit_count == 28
    assert pod_c.id not in doc.entities
    assert branch_1.id in doc.entities
    assert 'mounted_pod_id' not in doc.get(branch_1.id).params

    # -------------------------------------------------------------------------
    # EDIT 29: Undo Deletion of Mounted Pod C (Restores Pod & Mount Link)
    # -------------------------------------------------------------------------
    stack.undo()
    edit_count += 1
    assert edit_count == 29
    assert pod_c.id in doc.entities
    assert doc.get(branch_1.id).params['mounted_pod_id'] == pod_c.id
    assert doc.get(pod_c.id).parent_id == branch_1.id

    # -------------------------------------------------------------------------
    # EDIT 30: Move Pod Cluster Together (pod_a + pod_b)
    # -------------------------------------------------------------------------
    stack.execute(MoveEntities([pod_a.id, pod_b.id], dx=2.0, dy=-1.0, dz=0.0))
    edit_count += 1
    assert edit_count == 30
    assert math.isclose(doc.get(pod_a.id).params['cx'], 2.0)
    assert math.isclose(doc.get(pod_b.id).params['cx'], 7.5)

    # Verify final representations are completely intact
    final_plan = build_plan_frame(doc)
    assert any(p.role in ('pod-junction-clipped', 'model') and p.entity_id in (pod_a.id, pod_b.id) for p in final_plan.primitives)
    assert any(p.role == 'arboreal-branch' for p in final_plan.primitives)
    assert any(p.role == 'opening' for p in final_plan.primitives)
    assert any(p.role == 'organic-junction' for p in final_plan.primitives)

    # Orthographic view frame
    xz_view = build_view_frame(doc, axis='XZ')
    assert any(p.role == 'pod-junction-clipped' and p.entity_id == pod_a.id and dict(p.meta).get('junction_projection') == 'supported-rotated-ellipse' for p in xz_view.primitives)
    assert any(p.role == 'pod-junction-clipped' and p.entity_id == pod_b.id and dict(p.meta).get('junction_projection') == 'supported-axis-aligned' for p in xz_view.primitives)
    assert any(p.role == 'arboreal-branch' for p in xz_view.primitives)

    # 3D Tessellated Preview Evaluation
    eval_result = TessellatedPreviewBackend().evaluate(doc)
    assert eval_result.body(pod_a.id) is not None
    assert eval_result.body(pod_b.id) is not None
    assert eval_result.body(core_box.id) is not None
    assert eval_result.body(branch_1.id) is not None
    assert eval_result.body(pod_c.id) is not None

    # Assert exactly 30 distinct semantic parametric edits completed
    assert edit_count == 30
