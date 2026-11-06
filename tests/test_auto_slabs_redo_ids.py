"""Bots 06/11: «Επίπεδη στέγη (αυτόματα)» made new room_roof ids on every redo (its memory was keyed by the room id,
which can be renumbered after an undo) — what pointed at them (materials, selection) lost its target."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, CreateRoomFloors, CreateRoomRoofs
from archforge.core.model import Document, Entity


def _room():
    doc = Document(); stack = CommandStack(doc)
    for a, b in (((0, 0), (5, 0)), ((5, 0), (5, 4)), ((5, 4), (0, 4)), ((0, 4), (0, 0))):
        stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0,
                                                'height': 2.7, 'thickness': 0.2})))
    return doc, stack


@pytest.mark.parametrize('command,kind', [(CreateRoomRoofs, 'room_roof'), (CreateRoomFloors, 'room_floor')])
def test_redo_brings_back_the_same_slabs_even_when_room_ids_change(monkeypatch, command, kind):
    doc, stack = _room()
    sigs = [f.signature for f in doc.active_room_faces()]
    stack.execute(command(sigs))
    first = {e.id for e in doc.entities.values() if e.kind == kind}
    assert first
    stack.undo()
    from archforge.architecture import room_identity
    real = room_identity.room_id_for_signature
    monkeypatch.setattr(room_identity, 'room_id_for_signature',
                        lambda d, s, z=None: (real(d, s, z=z) or 'room') + '-renumbered')
    stack.redo()
    assert {e.id for e in doc.entities.values() if e.kind == kind} == first
