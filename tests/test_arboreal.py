import pytest

from archforge.core.model import Document
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.plan import build_evaluation_plan, fabrication_candidates
from archforge.geometry.preview import PreviewBackend
from archforge.organic.arboreal import ArborealCore, ArborealBranch, create_arboreal_tree


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
