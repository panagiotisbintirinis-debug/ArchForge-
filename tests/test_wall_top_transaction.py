import pytest

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.core.wall_top_transaction import WallTopEndpointTransaction


def _wall_doc():
    doc = Document()
    wall = Entity('wall', {
        'x1': 1.0, 'y1': 2.0, 'z': 0.5,
        'x2': 4.0, 'y2': 6.0,
        'height': 3.0, 'thickness': 0.2,
    })
    doc.add(wall)
    return doc, wall.id


def test_3d_transaction_preview_does_not_mutate_authoritative_wall():
    doc, wall_id = _wall_doc()
    stack = CommandStack(doc)
    tx = WallTopEndpointTransaction(doc, stack, wall_id, 'start')
    before = dict(doc.get(wall_id).params)

    height = tx.update_from_ray((8.0, 2.0, 5.0), (-1.0, 0.0, -0.25))

    assert height > 0.0
    assert doc.get(wall_id).params == before
    assert not stack.can_undo
    assert tx.preview_world_point()[:2] == pytest.approx((1.0, 2.0))


def test_3d_transaction_commit_uses_shared_endpoint_command_and_undo():
    doc, wall_id = _wall_doc()
    stack = CommandStack(doc)
    tx = WallTopEndpointTransaction(doc, stack, wall_id, 'end')
    height = tx.update_from_ray((8.0, 6.0, 5.0), (-1.0, 0.0, -0.25))

    tx.commit()
    assert doc.get(wall_id).params['end_height'] == pytest.approx(height)
    assert 'start_height' not in doc.get(wall_id).params

    stack.undo()
    assert 'end_height' not in doc.get(wall_id).params
    assert doc.get(wall_id).params['height'] == pytest.approx(3.0)


def test_3d_transaction_cancel_leaves_document_and_history_untouched():
    doc, wall_id = _wall_doc()
    stack = CommandStack(doc)
    tx = WallTopEndpointTransaction(doc, stack, wall_id, 'start')
    before = dict(doc.get(wall_id).params)
    tx.update_from_ray((8.0, 2.0, 5.0), (-1.0, 0.0, -0.25))

    tx.cancel()
    assert doc.get(wall_id).params == before
    assert not stack.can_undo
