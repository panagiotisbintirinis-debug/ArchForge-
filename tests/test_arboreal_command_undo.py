import pytest

from archforge.core.commands import MoveEntities, UpdateEntities, UpdateEntity
from archforge.core.model import Document
from archforge.organic.arboreal import arboreal_branch_geometry, create_arboreal_tree


def _pod_position(doc, pod_id):
    pod = doc.get(pod_id)
    return (pod.params['cx'], pod.params['cy'], pod.params['floor_level'])


def test_update_entity_undo_restores_mounted_pod_with_branch():
    doc = Document()
    tree = create_arboreal_tree(doc)
    item = tree['branches'][0]
    branch_id = item['branch_id']
    pod_id = item['mounted_pod_id']
    before_branch = dict(doc.get(branch_id).params)
    before_pod = _pod_position(doc, pod_id)

    command = UpdateEntity(branch_id, {'length': 7.5, 'azimuth_deg': 42.0, 'slope_deg': 17.0})
    command.do(doc)
    assert _pod_position(doc, pod_id) == pytest.approx(arboreal_branch_geometry(doc, branch_id)['end'])
    assert _pod_position(doc, pod_id) != pytest.approx(before_pod)

    command.undo(doc)

    assert doc.get(branch_id).params == before_branch
    assert _pod_position(doc, pod_id) == pytest.approx(before_pod)
    assert _pod_position(doc, pod_id) == pytest.approx(arboreal_branch_geometry(doc, branch_id)['end'])


def test_move_core_undo_restores_all_mounted_pods():
    doc = Document()
    tree = create_arboreal_tree(doc, cx=1.0, cy=-2.0)
    before = {pod_id: _pod_position(doc, pod_id) for pod_id in tree['pod_ids']}

    command = MoveEntities([tree['core_id']], dx=3.0, dy=-1.5, dz=0.0)
    command.do(doc)
    assert any(_pod_position(doc, pod_id) != pytest.approx(before[pod_id]) for pod_id in tree['pod_ids'])

    command.undo(doc)

    for item in tree['branches']:
        pod_id = item['mounted_pod_id']
        assert _pod_position(doc, pod_id) == pytest.approx(before[pod_id])
        assert _pod_position(doc, pod_id) == pytest.approx(arboreal_branch_geometry(doc, item['branch_id'])['end'])


def test_update_entities_failure_rolls_back_arboreal_side_effects():
    doc = Document()
    tree = create_arboreal_tree(doc)
    core_id = tree['core_id']
    branch_id = tree['branches'][0]['branch_id']
    core_before = dict(doc.get(core_id).params)
    pod_before = {pod_id: _pod_position(doc, pod_id) for pod_id in tree['pod_ids']}

    command = UpdateEntities({
        core_id: {'x': core_before['x'] + 4.0},
        branch_id: {'length': 0.0},
    })

    with pytest.raises(ValueError):
        command.do(doc)

    assert doc.get(core_id).params == core_before
    for item in tree['branches']:
        pod_id = item['mounted_pod_id']
        assert _pod_position(doc, pod_id) == pytest.approx(pod_before[pod_id])
        assert _pod_position(doc, pod_id) == pytest.approx(arboreal_branch_geometry(doc, item['branch_id'])['end'])
