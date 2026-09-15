import pytest
from archforge.core.model import Document
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
