import pytest

from archforge.core.model import Document
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.plan import build_evaluation_plan, fabrication_candidates
from archforge.geometry.preview import PreviewBackend
from archforge.geometry.surfaces import surface_catalog, surface_roles
from archforge.organic.arboreal import ArborealCore, ArborealBranch, arboreal_branch_geometry, create_arboreal_tree


def test_arboreal_branch_tip_computation():
    core = ArborealCore(core_id="core_1", cx=0.0, cy=0.0, base_z=0.0, radius=2.0, height=12.0)
    branch = ArborealBranch(
        branch_id="b1",
        core_id=core.core_id,
        elevation_z=4.0,
        azimuth_deg=0.0,  # East (+X)
        length=6.0,
        slope_deg=0.0  # Horizontal
    )
    tip_x, tip_y, tip_z = branch.compute_tip_coordinate(core.cx, core.cy)
    assert abs(tip_x - 6.0) < 1e-4
    assert abs(tip_y - 0.0) < 1e-4
    assert abs(tip_z - 4.0) < 1e-4


def test_create_arboreal_tree_entities():
    doc = Document()
    tree = create_arboreal_tree(doc, cx=0.0, cy=0.0, core_radius=2.0, core_height=15.0)
    assert tree['is_arboreal_tree'] is True
    assert tree['core_id'] in doc.entities
    assert len(tree['branches']) == 3
    assert len(tree['pod_ids']) == 3

    # Check that mounted pods exist in document at proper elevations
    for pod_id in tree['pod_ids']:
        assert pod_id in doc.entities
        pod = doc.entities[pod_id]
        assert pod.kind == 'pod'
        assert pod.params['floor_level'] > 0.0


def test_arboreal_branches_are_persistent_geometry_between_core_and_pods():
    doc = Document()
    tree = create_arboreal_tree(doc, cx=1.0, cy=-2.0, core_radius=2.0, core_height=15.0)

    branch_ids = [item['branch_id'] for item in tree['branches']]
    assert len(branch_ids) == 3
    assert all(branch_id in doc.entities for branch_id in branch_ids)

    for item in tree['branches']:
        branch = doc.get(item['branch_id'])
        pod = doc.get(item['mounted_pod_id'])
        assert branch.kind == 'arboreal_branch'
        assert branch.parent_id == tree['core_id']
        assert pod.parent_id == branch.id

    evaluation = TessellatedPreviewBackend().evaluate(doc)
    for branch_id in branch_ids:
        body = evaluation.body(branch_id)
        assert body.semantic_kind == 'arboreal_branch'
        assert body.payload.triangles
        assert 'branch_shell' in set(body.payload.triangle_surfaces)


def test_arboreal_branch_preview_is_not_fabrication_evidence():
    doc = Document()
    tree = create_arboreal_tree(doc)
    branch_ids = {item['branch_id'] for item in tree['branches']}

    plan = build_evaluation_plan(doc)
    candidate_ids = {node.entity_id for node in fabrication_candidates(plan)}
    assert branch_ids
    assert branch_ids.isdisjoint(candidate_ids)


def test_fast_preview_supports_persistent_arboreal_branches_without_errors():
    doc = Document()
    tree = create_arboreal_tree(doc, cx=0.5, cy=1.5)
    branch_ids = {item['branch_id'] for item in tree['branches']}

    evaluation = PreviewBackend().evaluate(doc)
    assert evaluation.ok
    assert not [issue for issue in evaluation.issues if issue.entity_id in branch_ids and issue.severity == 'error']
    for branch_id in branch_ids:
        body = evaluation.body(branch_id)
        assert body.semantic_kind == 'arboreal_branch'
        assert body.payload.primitive == 'arboreal_branch'


def test_mounted_pod_follows_branch_tip_when_branch_geometry_changes():
    doc = Document()
    tree = create_arboreal_tree(doc)
    item = tree['branches'][0]
    branch_id = item['branch_id']
    pod_id = item['mounted_pod_id']

    doc.update(branch_id, {'azimuth_deg': 55.0, 'length': 7.25, 'slope_deg': 18.0, 'elevation_z': 4.4})
    expected = arboreal_branch_geometry(doc, branch_id)['end']
    pod = doc.get(pod_id)

    assert pod.id == pod_id
    assert (pod.params['cx'], pod.params['cy'], pod.params['floor_level']) == pytest.approx(expected)


def test_mounted_pods_follow_when_arboreal_core_moves():
    doc = Document()
    tree = create_arboreal_tree(doc, cx=1.0, cy=-2.0)
    core_id = tree['core_id']
    pod_ids = tuple(tree['pod_ids'])

    core = doc.get(core_id)
    doc.update(core_id, {'x': core.params['x'] + 2.5, 'y': core.params['y'] - 1.25})

    for item, pod_id in zip(tree['branches'], pod_ids):
        expected = arboreal_branch_geometry(doc, item['branch_id'])['end']
        pod = doc.get(pod_id)
        assert pod.id == pod_id
        assert (pod.params['cx'], pod.params['cy'], pod.params['floor_level']) == pytest.approx(expected)


def test_arboreal_branch_projects_in_plan_and_ortho_views():
    from archforge.core.plan_scene import build_plan_frame
    from archforge.core.view_frame import build_view_frame

    doc = Document()
    tree = create_arboreal_tree(doc, cx=0.0, cy=0.0)
    branch_id = tree['branches'][0]['branch_id']
    doc.selection = [branch_id]

    plan = build_plan_frame(doc)
    branch_prims = [p for p in plan.primitives if p.entity_id == branch_id]
    assert len(branch_prims) == 1
    assert branch_prims[0].role == 'arboreal-branch'
    assert dict(branch_prims[0].meta).get('engineering_verified') is False

    # Selection handles in 2D plan
    handles = [h for h in plan.handles if h.entity_id == branch_id]
    assert len(handles) == 2

    # Orthographic view frame
    for axis in ('XY', 'XZ', 'YZ'):
        view = build_view_frame(doc, axis)
        v_prims = [p for p in view.primitives if p.entity_id == branch_id]
        assert len(v_prims) == 1
        assert v_prims[0].role == 'arboreal-branch'


def test_arboreal_mesh_roles_are_registered_nonfabrication_surfaces():
    doc = Document()
    tree = create_arboreal_tree(doc)
    branch_id = tree['branches'][0]['branch_id']

    evaluation = TessellatedPreviewBackend().evaluate(doc)
    body = evaluation.body(branch_id)
    payload_roles = set(body.payload.triangle_surfaces)
    registered_roles = set(surface_roles(doc, branch_id))

    assert {'branch_shell', 'branch_root', 'branch_tip'} <= payload_roles
    assert payload_roles <= registered_roles
    descriptors = surface_catalog(doc, branch_id)
    assert descriptors
    assert all(not surface.fabrication_surface for surface in descriptors)
    assert set(body.surface_keys) == {surface.key for surface in descriptors}
