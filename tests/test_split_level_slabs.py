"""Owner (2026-10-14, CHANDLER): split level + basement got a pitched roof where a slab belongs,
and the half level / basement were left without floor and ceiling slabs."""
from archforge.architecture.roof_need import COVERED, coverage, roof_plan
from archforge.architecture.storey_slabs import (missing_storey_slabs, missing_storey_slabs_command,
                                                 storey_slab_command, storey_slab_geometry)
from archforge.assistant.suggestions import propose as suggestions
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.structure.timber_roof import auto_roofs


def _box(stack, x0, x1, z, h):
    pts = [(x0, 0), (x1, 0), (x1, 4), (x0, 4)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        stack.execute(AddEntity(Entity('wall', {'x1': ax, 'y1': ay, 'x2': bx, 'y2': by, 'z': z,
                                                'height': h, 'thickness': 0.25})))


def _house():
    doc = Document()
    doc.levels = {'Υπόγειο': -2.70, 'Ground': 0.0, '1ος όροφος': 1.40}
    stack = CommandStack(doc)
    _box(stack, 0, 5, 0.0, 2.80)        # ground floor
    _box(stack, 5, 10, 1.40, 2.80)      # half level beside it
    _box(stack, 5, 10, -2.70, 2.70)     # basement under the half level
    return doc, stack


def test_basement_under_the_half_level_is_covered_not_roofed():
    doc, _stack = _house()
    [base] = doc.active_room_faces(z=-2.70)
    assert coverage(doc, base.polygon, -2.70) >= COVERED
    [ground] = doc.active_room_faces(z=0.0)
    assert coverage(doc, ground.polygon, 0.0) < 0.5           # the ground floor is open above
    add = set(roof_plan(doc)['add'])
    assert base.signature not in add and ground.signature in add
    # No tiled roof is proposed over the basement, even for the lower storeys.
    for params, _reason in auto_roofs(doc, lower_storeys=True):
        assert float(params['eave_z']) > 0.0


def test_every_storey_gets_its_floor_and_ceiling_slabs_in_one_undo():
    doc, stack = _house()
    command, _e = storey_slab_command(doc, 'room_floor', 0.0, 'Ground')
    stack.execute(command)                                      # the human started with the ground floor
    missing = missing_storey_slabs(doc)
    assert ('room_floor', -2.7, 'Υπόγειο') in missing and ('room_roof', -2.7, 'Υπόγειο') in missing
    assert ('room_floor', 1.4, '1ος όροφος') in missing and ('room_roof', 0.0, 'Ground') in missing
    proposal = next(p for p in suggestions(doc) if p.key == 'S-1')
    stack.execute(proposal.build(doc))
    assert missing_storey_slabs(doc) == []
    slabs = [e for e in doc.entities.values() if e.kind in ('room_floor', 'room_roof') and e.params.get('scope') == 'storey']
    assert len(slabs) == 6
    for e in slabs:
        assert storey_slab_geometry(doc, e) is not None, (e.kind, e.params['level_z'])
    basement_roof = next(e for e in slabs if e.kind == 'room_roof' and e.params['level_z'] == -2.7)
    assert abs(storey_slab_geometry(doc, basement_roof)['z'] - 0.0) < 1e-9     # on top of the basement walls
    assert not any(p.key == 'S-1' for p in suggestions(doc))
    stack.undo()
    assert len(missing_storey_slabs(doc)) == 5
    assert missing_storey_slabs_command(doc) is not None
