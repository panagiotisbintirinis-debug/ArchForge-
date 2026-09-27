import pytest

from archforge.core.model import Document
from archforge.core.wall_top_handles import wall_top_handle_payload


def _wall_doc():
    doc = Document()
    wall_id = doc.create_entity('wall', {
        'x1': 1.0, 'y1': 2.0,
        'x2': 5.0, 'y2': 6.0,
        'z': 0.4,
        'height': 2.8,
        'start_height': 3.1,
        'end_height': 4.2,
        'thickness': 0.2,
    })
    return doc, wall_id


def test_3d_handle_payload_preserves_semantic_endpoint_identity_on_rotated_wall():
    doc, wall_id = _wall_doc()

    handles = wall_top_handle_payload(doc, [wall_id])

    assert handles == [
        {
            'entity_id': wall_id,
            'endpoint': 'start',
            'position': [1.0, 2.0, 3.5],
            'preview': False,
        },
        {
            'entity_id': wall_id,
            'endpoint': 'end',
            'position': [5.0, 6.0, 4.6],
            'preview': False,
        },
    ]


def test_3d_handle_preview_changes_only_active_endpoint_z_without_document_mutation():
    doc, wall_id = _wall_doc()
    before = doc.to_dict()

    handles = wall_top_handle_payload(
        doc,
        [wall_id],
        preview_endpoint='start',
        preview_height=5.0,
    )

    assert handles[0]['position'] == [1.0, 2.0, 5.4]
    assert handles[0]['preview'] is True
    assert handles[1]['position'] == [5.0, 6.0, 4.6]
    assert handles[1]['preview'] is False
    assert doc.to_dict() == before


def test_3d_handle_payload_is_selection_scoped_and_wall_only():
    doc, wall_id = _wall_doc()
    floor_id = doc.create_entity('room_floor', {
        'room_signature': 'room-a',
        'z': 0.0,
        'thickness': 0.2,
    })

    assert wall_top_handle_payload(doc, []) == []
    assert wall_top_handle_payload(doc, [wall_id, floor_id]) == []
    assert wall_top_handle_payload(doc, [floor_id]) == []
    assert wall_top_handle_payload(doc, ['missing']) == []


def test_3d_handle_preview_rejects_invalid_semantics():
    doc, wall_id = _wall_doc()

    with pytest.raises(ValueError, match='preview_endpoint'):
        wall_top_handle_payload(doc, [wall_id], preview_endpoint='middle')
    with pytest.raises(ValueError, match='requires preview_endpoint'):
        wall_top_handle_payload(doc, [wall_id], preview_height=3.0)
    with pytest.raises(ValueError, match='above base'):
        wall_top_handle_payload(
            doc,
            [wall_id],
            preview_endpoint='end',
            preview_height=0.0,
        )
