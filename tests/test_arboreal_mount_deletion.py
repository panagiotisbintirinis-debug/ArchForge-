from archforge.core.commands import DeleteEntities
from archforge.core.model import Document
from archforge.organic.arboreal import create_arboreal_tree


def test_deleting_mounted_pod_clears_branch_mount_and_undo_restores_it():
    doc = Document()
    tree = create_arboreal_tree(doc)
    item = tree['branches'][0]
    branch_id = item['branch_id']
    pod_id = item['mounted_pod_id']

    command = DeleteEntities([pod_id])
    command.do(doc)

    assert pod_id not in doc.entities
    assert branch_id in doc.entities
    assert 'mounted_pod_id' not in doc.get(branch_id).params
    assert pod_id not in doc.dependencies.get(branch_id, set())

    command.undo(doc)

    assert pod_id in doc.entities
    assert doc.get(branch_id).params['mounted_pod_id'] == pod_id
    assert doc.get(pod_id).parent_id == branch_id
    assert pod_id in doc.dependencies.get(branch_id, set())

    command.do(doc)
    assert pod_id not in doc.entities
    assert 'mounted_pod_id' not in doc.get(branch_id).params
