from __future__ import annotations

import copy
import json
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
from archforge.core.modifiers import SurfaceModifier, SurfaceRef
from archforge.geometry.preview import PreviewBackend
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.core.plan_scene import build_plan_frame
from archforge.core.view_frame import build_view_frame


def _extract_mesh_fingerprint(evaluation):
    """Extract deterministic geometric payload signature for all evaluated bodies."""
    fingerprints = {}
    for body in sorted(evaluation.bodies, key=lambda b: b.entity_id):
        payload = body.payload
        if hasattr(payload, 'vertices') and hasattr(payload, 'triangles'):
            fingerprints[body.entity_id] = {
                'vertices': payload.vertices,
                'triangles': payload.triangles,
                'quality': body.quality,
                'surface_keys': sorted(body.surface_keys),
                'watertight': body.watertight,
                'manifold': body.manifold,
            }
        elif hasattr(payload, 'points'):
            fingerprints[body.entity_id] = {
                'points': payload.points,
                'quality': body.quality,
            }
    return fingerprints


def test_pod_designer_save_load_determinism_full_lifecycle(tmp_path):
    """
    Proves Issue #40: Save/load deterministic roundtrip for Pod Designer semantic state.

    Required coverage & assertions:
      1. Construct a nontrivial project with multiple pods (3 pods in varied configuration).
      2. Active planar junction between Pod A and Pod B with internal shell occlusion.
      3. Dormant junction transition: Pod C intersects Pod B, then moves away, establishing
         dormant organic junction state before save.
      4. Pod openings (door and window) hosted on pods with auto-inferred persistent patches.
      5. Parent/child relationships and dependency graph thoroughly populated.
      6. Attached non-destructive surface modifiers on pod shells.
      7. Serialize to JSON file, reload via Document.load().
      8. Assert exact preservation of:
         - Entity IDs, count, and kinds.
         - Parent IDs and exact children relationships.
         - Complete dependency graph (dirty propagation structure).
         - Exact entity parameters without normalization drift or precision loss.
         - Dormant vs active status on junctions.
         - Surface modifiers order, IDs, parameters, and targets.
      9. Assert re-evaluated geometry equivalence across all supported backends:
         - 2D Plan frame primitives (roles, points, counts).
         - Orthographic View frame primitives ('XZ' elevation).
         - Fast 3D Preview representation.
         - Full Tessellated 3D Preview (exact mesh vertices, triangles, and body metadata).
      10. Assert that calling inference routines (infer_organic_junctions,
          infer_organic_opening_patches) on the loaded document produces zero duplicate
          entities and maintains stable IDs.
      11. Assert that moving Pod C back into contact with Pod B in the loaded document
          reactivates the exact original dormant junction entity ID without recreating it.
    """
    doc = Document()
    stack = CommandStack(doc)

    # 1. Construct multi-pod assembly
    pod_a = Entity('pod', {
        'cx': 0.0,
        'cy': 0.0,
        'floor_level': 0.0,
        'diameter_x': 8.0,
        'diameter_y': 6.0,
        'height': 4.0,
        'shell_thickness': 0.18,
        'rotation': 10.0,
    }, name='Alpha Pod')
    stack.execute(AddEntity(pod_a))

    pod_b = Entity('pod', {
        'cx': 5.5,
        'cy': 0.0,
        'floor_level': 0.0,
        'diameter_x': 7.0,
        'diameter_y': 7.0,
        'height': 3.8,
        'shell_thickness': 0.18,
        'rotation': 0.0,
    }, name='Beta Pod')
    stack.execute(AddEntity(pod_b))

    pod_c = Entity('pod', {
        'cx': 15.0,
        'cy': 0.0,
        'floor_level': 0.0,
        'diameter_x': 5.0,
        'diameter_y': 5.0,
        'height': 3.2,
        'shell_thickness': 0.18,
        'rotation': 0.0,
    }, name='Gamma Pod')
    stack.execute(AddEntity(pod_c))

    # 2. Add pod openings
    door_a = Entity('door', {
        'surface_u': 0.5,
        'width': 1.1,
        'height': 2.2,
        'sill': 0.0,
        'flat_margin': 0.25,
    }, parent_id=pod_a.id, name='Alpha Entry Door')
    stack.execute(AddEntity(door_a))

    win_b = Entity('window', {
        'surface_u': 0.25,
        'width': 1.4,
        'height': 1.6,
        'sill': 0.8,
        'flat_margin': 0.25,
    }, parent_id=pod_b.id, name='Beta Observation Window')
    stack.execute(AddEntity(win_b))

    # 3. Infer active junctions (Alpha <-> Beta) and opening patches
    res_junc_initial = infer_organic_junctions(doc)
    assert len(res_junc_initial.active_ids) == 1
    active_junc_id = res_junc_initial.active_ids[0]
    assert doc.get(active_junc_id).params['status'] == 'active'

    res_patch_initial = infer_organic_opening_patches(doc)
    assert len(res_patch_initial.active_ids) == 2
    door_patch_id = [pid for pid in res_patch_initial.active_ids if doc.get(pid).params['opening_id'] == door_a.id][0]
    win_patch_id = [pid for pid in res_patch_initial.active_ids if doc.get(pid).params['opening_id'] == win_b.id][0]

    # 4. Create dormant junction transition:
    # Temporarily move Pod C into intersection with Pod B, infer junction, then move away
    stack.execute(MoveEntities([pod_c.id], dx=-4.5, dy=0.0, dz=0.0))  # cx becomes 10.5, overlaps with Beta (cx=5.5, r=3.5)
    res_junc_step2 = infer_organic_junctions(doc)
    assert len(res_junc_step2.active_ids) == 2
    dormant_target_id = [jid for jid in res_junc_step2.active_ids if jid != active_junc_id][0]

    # Move Pod C back to separation distance -> junction becomes dormant
    stack.execute(MoveEntities([pod_c.id], dx=7.0, dy=0.0, dz=0.0))  # cx becomes 17.5
    res_junc_step3 = infer_organic_junctions(doc)
    assert active_junc_id in res_junc_step3.active_ids
    assert dormant_target_id in res_junc_step3.dormant_ids
    assert doc.get(dormant_target_id).params['status'] == 'dormant'

    # 5. Attach surface modifier to Alpha Pod shell
    mod_a = SurfaceModifier(
        target=SurfaceRef(pod_a.id, 'pod_shell'),
        operation='pull',
        params={'amount': 0.15, 'radius': 1.0},
        name='Aero Bulge',
        order=10
    )
    doc.add_surface_modifier(mod_a)

    # 6. Pre-save baseline evaluation across representations
    plan_pre = build_plan_frame(doc)
    view_xz_pre = build_view_frame(doc, 'XZ')
    preview_pre = PreviewBackend().evaluate(doc)
    tess_pre = TessellatedPreviewBackend().evaluate(doc)
    tess_fingerprints_pre = _extract_mesh_fingerprint(tess_pre)

    # Capture complete pre-save snapshot
    pre_dict = copy.deepcopy(doc.to_dict())

    # 7. Serialize to file and reload into fresh document
    save_file = tmp_path / 'pod_designer_roundtrip_test.archforge'
    doc.save(str(save_file))

    loaded_doc = Document.load(str(save_file))

    # 8. Assertions: Semantic and Relational Parity
    assert len(loaded_doc.entities) == len(doc.entities)
    assert set(loaded_doc.entities.keys()) == set(doc.entities.keys())

    # Check each entity's parameters and properties
    for eid, orig_e in doc.entities.items():
        loaded_e = loaded_doc.get(eid)
        assert loaded_e.id == orig_e.id
        assert loaded_e.kind == orig_e.kind
        assert loaded_e.name == orig_e.name
        assert loaded_e.parent_id == orig_e.parent_id
        assert loaded_e.visible == orig_e.visible
        assert loaded_e.locked == orig_e.locked
        assert loaded_e.params == orig_e.params

    # Check parent/child tree
    assert set(loaded_doc.children.keys()) == set(doc.children.keys())
    for pid, orig_children in doc.children.items():
        assert set(loaded_doc.children[pid]) == set(orig_children)

    # Check dependency graph
    assert set(loaded_doc.dependencies.keys()) == set(doc.dependencies.keys())
    for src, orig_deps in doc.dependencies.items():
        assert loaded_doc.dependencies[src] == orig_deps

    # Check surface modifiers
    assert len(loaded_doc.surface_modifiers) == len(doc.surface_modifiers)
    for mid, orig_m in doc.surface_modifiers.items():
        loaded_m = loaded_doc.surface_modifiers[mid]
        assert loaded_m.id == orig_m.id
        assert loaded_m.name == orig_m.name
        assert loaded_m.operation == orig_m.operation
        assert loaded_m.params == orig_m.params
        assert loaded_m.order == orig_m.order
        assert loaded_m.target.owner_id == orig_m.target.owner_id
        assert loaded_m.target.surface_role == orig_m.target.surface_role

    # Check exact dictionary serialization equality
    post_dict = loaded_doc.to_dict()
    pre_entities_by_id = {e['id']: e for e in pre_dict['entities']}
    post_entities_by_id = {e['id']: e for e in post_dict['entities']}
    assert post_entities_by_id == pre_entities_by_id
    assert post_dict['dependencies'] == pre_dict['dependencies']
    assert post_dict['surface_modifiers'] == pre_dict['surface_modifiers']

    # 9. Assertions: Geometry Evaluation Determinism
    plan_post = build_plan_frame(loaded_doc)
    assert len(plan_post.primitives) == len(plan_pre.primitives)
    plan_pre_by_key = {
        (p.entity_id, p.role, p.kind): (p.points, p.radius_x, p.radius_y, p.rotation, p.meta)
        for p in plan_pre.primitives
    }
    plan_post_by_key = {
        (p.entity_id, p.role, p.kind): (p.points, p.radius_x, p.radius_y, p.rotation, p.meta)
        for p in plan_post.primitives
    }
    assert plan_post_by_key == plan_pre_by_key

    view_xz_post = build_view_frame(loaded_doc, 'XZ')
    assert len(view_xz_post.primitives) == len(view_xz_pre.primitives)
    view_pre_by_key = {
        (v.entity_id, v.role, v.kind): v.points
        for v in view_xz_pre.primitives
    }
    view_post_by_key = {
        (v.entity_id, v.role, v.kind): v.points
        for v in view_xz_post.primitives
    }
    assert view_post_by_key == view_pre_by_key

    preview_post = PreviewBackend().evaluate(loaded_doc)
    assert len(preview_post.bodies) == len(preview_pre.bodies)
    assert {b.entity_id for b in preview_post.bodies} == {b.entity_id for b in preview_pre.bodies}

    tess_post = TessellatedPreviewBackend().evaluate(loaded_doc)
    tess_fingerprints_post = _extract_mesh_fingerprint(tess_post)
    assert len(tess_fingerprints_post) == len(tess_fingerprints_pre)
    assert set(tess_fingerprints_post.keys()) == set(tess_fingerprints_pre.keys())

    for eid in tess_fingerprints_pre:
        assert tess_fingerprints_post[eid] == tess_fingerprints_pre[eid]

    # 10. Assertions: Idempotent Re-Inference on Loaded State
    re_junc = infer_organic_junctions(loaded_doc)
    assert len(re_junc.created_ids) == 0, "No duplicate organic junctions created on re-inference"
    assert set(re_junc.active_ids) == {active_junc_id}
    assert set(re_junc.dormant_ids) == {dormant_target_id}

    re_patches = infer_organic_opening_patches(loaded_doc)
    assert len(re_patches.created_ids) == 0, "No duplicate organic opening patches created on re-inference"
    assert set(re_patches.active_ids) == {door_patch_id, win_patch_id}

    # 11. Assertions: Reactivation of Dormant Junction Preserves Original ID
    # Move Pod C back to overlap with Pod B (cx=17.5 -> 10.5)
    loaded_stack = CommandStack(loaded_doc)
    loaded_stack.execute(MoveEntities([pod_c.id], dx=-7.0, dy=0.0, dz=0.0))

    reconnect_res = infer_organic_junctions(loaded_doc)
    assert dormant_target_id in reconnect_res.active_ids
    assert len(reconnect_res.created_ids) == 0
    assert loaded_doc.get(dormant_target_id).params['status'] == 'active'
