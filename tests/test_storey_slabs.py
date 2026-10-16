"""Storey slabs over the whole plan, slab openings (atrium / inner balcony / void) — SL1.

Owner (screenshot): «Εδώ πλάκα μπαίνει μόνο στο ένα τμήμα» — Room 1 (rectangle)
and Room 2 (slanted wall, a block up-right).  Room 2 had first been drawn as
the block alone; after it was extended its per-room slab went dormant and
the new room had none.
"""
import pytest

from archforge.architecture import storey_slabs as S
from archforge.architecture.rooms import room_slab_geometry
from archforge.architecture.topology import polygon_area
from archforge.core.commands import AddEntity, CommandStack, CreateRoomFloors, CreateRoomRoofs, DeleteEntities, MoveEntities
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.geometry.mesh import MeshPayload, TessellatedPreviewBackend
from archforge.geometry.mesh_validation import validate_mesh
from archforge.geometry.regions import islands_area

T = 0.25


def wall(a, b, z=0.0, h=3.0):
    return Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': z, 'height': h, 'thickness': T})


def chain(st, pts, close=True, z=0.0):
    ids = []
    for i in range(len(pts) if close else len(pts) - 1):
        w = wall(pts[i], pts[(i + 1) % len(pts)], z)
        st.execute(AddEntity(w))
        ids.append(w.id)
    return ids


def owner_plan():
    """Room 1 + the block drawn first as a room of its own (per-room slabs), then Room 2 extended."""
    doc = Document()
    st = CommandStack(doc)
    chain(st, [(0, 0), (4.5, 0), (4.5, 5), (0, 5)])
    block = chain(st, [(4.5, 5), (9.3, 5), (9.3, 6.5), (4.5, 6.5)])
    faces = doc.active_room_faces()
    st.execute(CreateRoomFloors([f.signature for f in faces]))
    st.execute(CreateRoomRoofs([f.signature for f in faces]))
    st.execute(DeleteEntities([block[0]]))
    chain(st, [(2.2, 0), (5.0, -2.8), (9.3, -2.25), (9.3, 5)], close=False)
    return doc, st


def footprint(doc):
    return sum(polygon_area(f.polygon) for f in doc.active_room_faces())


def test_owner_plan_per_room_slabs_leave_room_2_without_slab():
    doc, _st = owner_plan()
    assert len(doc.active_room_faces()) == 2
    covered = sum(polygon_area(g['points']) for e in doc.entities.values() if e.kind == 'room_floor'
                  for g in [room_slab_geometry(doc, e)] if g)
    assert covered < footprint(doc) - 40                     # the bug: only Room 1 (22.5 m² of 68.5)


def test_storey_floor_covers_whole_plan_and_replaces_per_room_slabs_in_one_undo():
    doc, st = owner_plan()
    before = len(doc.entities)
    command, slab = S.storey_slab_command(doc, 'room_floor', 0.0, 'Ground')
    st.execute(command)
    floors = [e for e in doc.entities.values() if e.kind == 'room_floor']
    assert floors == [slab] and slab.name == 'Πλάκα δαπέδου — Ισόγειο'
    g = room_slab_geometry(doc, slab)
    assert len(g['islands']) == 1 and g['area'] == pytest.approx(footprint(doc))
    st.undo()
    assert len(doc.entities) == before
    st.redo()
    assert S.storey_slab_command(doc, 'room_floor', 0.0)[0] is None      # nothing left to do


def test_storey_slab_follows_walls_and_is_marked_dirty():
    doc, st = owner_plan()
    command, slab = S.storey_slab_command(doc, 'room_floor', 0.0)
    st.execute(command)
    area = room_slab_geometry(doc, slab)['area']
    doc.dirty.clear()
    east = next(e for e in doc.entities.values() if e.kind == 'wall' and e.params['x1'] == 9.3 and e.params['x2'] == 9.3
                and e.params['y2'] == 5)
    top = [e for e in doc.entities.values() if e.kind == 'wall' and e.params['x1'] == 9.3 and e.params['y1'] == 5]
    st.execute(MoveEntities([east.id] + [w.id for w in top if w.params['x2'] == 9.3], dx=1.0, dy=0.0))
    for w in doc.entities.values():
        if w.kind == 'wall' and w.params['x2'] == 9.3 and w.params['y2'] in (-2.25, 6.5):
            doc.update(w.id, {'x2': 10.3})
        if w.kind == 'wall' and w.params['x1'] == 9.3 and w.params['y1'] == 6.5:
            doc.update(w.id, {'x1': 10.3})
    assert slab.id in doc.dirty
    assert room_slab_geometry(doc, slab)['area'] > area + 5


def test_slab_over_a_storey_is_one_plate_under_terrace_and_upper_storey_alike():
    """Owner: «πάλι μέρη της πλάκας εξαφανίζονται» — the roof slab skipped the part under the next storey."""
    doc = Document()
    st = CommandStack(doc)
    doc.levels['Floor 2'] = 3.0
    chain(st, [(0, 0), (10, 0), (10, 6), (0, 6)])
    st.execute(AddEntity(wall((5, 0), (5, 6))))
    chain(st, [(0, 0), (5, 0), (5, 6), (0, 6)], z=3.0)
    command, roof = S.storey_slab_command(doc, 'room_roof', 0.0)
    st.execute(command)
    g = room_slab_geometry(doc, roof)
    xs = [p[0] for p in g['points']]
    # Both rooms, the one under the upper storey too, to the outer wall faces.
    assert min(xs) == pytest.approx(-T / 2) and max(xs) == pytest.approx(10 + T / 2)
    assert g['z'] == pytest.approx(3.0)
    # The upper storey stands on that plate: its own floor slab adds nothing (no double slab, no double m²).
    command, upper_floor = S.storey_slab_command(doc, 'room_floor', 3.0, 'Floor 2')
    st.execute(command)
    assert room_slab_geometry(doc, upper_floor) is None
    from archforge.architecture.roof_need import roof_plan
    assert roof_plan(doc)['add'] == [f.signature for f in doc.active_room_faces(z=3.0)]


def test_upper_floor_slab_keeps_only_what_overhangs_the_storey_below():
    doc = Document()
    st = CommandStack(doc)
    doc.levels['Floor 2'] = 3.0
    chain(st, [(0, 0), (5, 0), (5, 6), (0, 6)])
    chain(st, [(0, 0), (7, 0), (7, 6), (0, 6)], z=3.0)               # 2 m cantilever / balcony
    st.execute(S.storey_slab_command(doc, 'room_roof', 0.0)[0])
    command, upper_floor = S.storey_slab_command(doc, 'room_floor', 3.0, 'Floor 2')
    st.execute(command)
    g = room_slab_geometry(doc, upper_floor)
    xs = [p[0] for p in g['points']]
    assert min(xs) == pytest.approx(5 + T / 2, abs=1e-3) and max(xs) == pytest.approx(7.0, abs=1e-3)


def test_drawn_opening_cuts_floor_mesh_plan_and_takeoff():
    doc, st = owner_plan()
    command, slab = S.storey_slab_command(doc, 'room_floor', 0.0)
    st.execute(command)
    hole = S.opening_entity(doc, points=[(5.5, 1), (7.5, 1), (7.5, 3), (5.5, 3)], use='inner_balcony')
    assert hole.params['cuts'] == 'floor' and hole.name == 'Εσωτερικό μπαλκόνι / κενό διπλού ύψους'
    doc.dirty.clear()
    st.execute(AddEntity(hole))
    assert slab.id in doc.dirty
    g = room_slab_geometry(doc, slab)
    assert g['area'] == pytest.approx(footprint(doc) - 4.0) and len(g['holes']) == 1
    body = TessellatedPreviewBackend().evaluate(doc).body(slab.id)
    report = validate_mesh(MeshPayload(body.payload.vertices, body.payload.triangles, body.payload.triangle_surfaces))
    assert report.watertight, report.findings[:3]
    prims = build_plan_frame(doc).primitives
    slab_prim = next(p for p in prims if p.entity_id == slab.id)
    assert dict(slab_prim.meta)['islands'][0][1]                         # hole drawn empty
    assert len([p for p in prims if p.entity_id == hole.id and p.role == 'slab-opening-cross']) == 2
    from archforge.quantities.takeoff import take_off
    q = take_off(doc)
    assert sum(r['floor_m2'] for r in q['rooms']) < sum(r['ceiling_m2'] for r in q['rooms']) - 3.9
    assert any(s['openings_m2'] == pytest.approx(4.0) for s in q['slabs'])
    # Move (one undo), then delete.
    st.execute(MoveEntities([hole.id], dx=0.5, dy=0.0))
    assert doc.get(hole.id).params['points'][0][0] == pytest.approx(6.0)
    st.undo()
    assert doc.get(hole.id).params['points'][0][0] == pytest.approx(5.5)
    st.execute(DeleteEntities([hole.id]))
    assert room_slab_geometry(doc, slab)['area'] == pytest.approx(footprint(doc))


def test_room_atrium_roof_keeps_walls_covered_and_structure_flags_reinforcement():
    doc = Document()
    st = CommandStack(doc)
    # 9 × 9 house with a 3 × 3 courtyard room in the middle (four rooms round it).
    chain(st, [(0, 0), (9, 0), (9, 9), (0, 9)])
    chain(st, [(3, 3), (6, 3), (6, 6), (3, 6)])
    for a, b in (((3, 0), (3, 3)), ((6, 6), (6, 9)), ((0, 6), (3, 6)), ((6, 3), (9, 3))):
        st.execute(AddEntity(wall(a, b)))
    st.execute(S.storey_slab_command(doc, 'room_roof', 0.0)[0])
    roof = next(e for e in doc.entities.values() if e.kind == 'room_roof')
    atrium = S.room_opening_entity(doc, 4.5, 4.5, 'atrium')
    assert atrium.params['cuts'] == 'both' and atrium.name == 'Αίθριο'
    st.execute(AddEntity(atrium))
    assert S.room_opening_entity(doc, 4.5, 4.5) is None                  # already an atrium
    g = room_slab_geometry(doc, roof)
    (hole,) = g['holes']
    assert polygon_area(hole) == pytest.approx((3 - T) ** 2)              # roof up to the inner wall face
    assert g['area'] == pytest.approx((9 + T) ** 2 - (3 - T) ** 2)
    from archforge.structure.slabs import REINFORCEMENT_NOTE, design_slabs
    panels = design_slabs(doc)['panels']
    assert len(panels) == len(doc.active_room_faces()) - 1                # no slab panel over the atrium
    railing = S.railing_points(doc, atrium)
    assert len(railing) == 4 and min(p[0] for p in railing) == pytest.approx(2.95)
    # A void that covers part of a room is flagged for the engineer.
    st.execute(AddEntity(S.opening_entity(doc, points=[(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5)], cuts='roof')))
    flagged = [p for p in design_slabs(doc)['panels'] if p['opening_m2']]
    assert len(flagged) == 1 and REINFORCEMENT_NOTE in flagged[0]['text'] and flagged[0]['opening_m2'] == pytest.approx(1.0)


@pytest.mark.parametrize('params', [
    {'level_z': 0.0, 'use': 'void', 'cuts': 'floor'},                                          # no outline, no room
    {'level_z': 0.0, 'points': [[0, 0], [0.1, 0], [0.1, 1], [0, 1]], 'use': 'void', 'cuts': 'floor'},  # 10 cm
    {'level_z': 0.0, 'points': [[0, 0], [1, 0], [1, 1]], 'use': 'pool', 'cuts': 'floor'},
    {'level_z': 0.0, 'points': [[0, 0], [1, 0], [1, 1]], 'use': 'void', 'cuts': 'walls'},
    {'points': [[0, 0], [1, 0], [1, 1]], 'use': 'void', 'cuts': 'floor'},                     # no storey
])
def test_slab_opening_schema_rejects(params):
    with pytest.raises(ValueError):
        Document().add(Entity('slab_opening', params))


def test_storey_slab_schema_and_save_load_round_trip(tmp_path):
    with pytest.raises(ValueError):
        Document().add(Entity('room_floor', {'scope': 'storey', 'thickness': .15, 'offset_z': 0.0}))
    with pytest.raises(ValueError):
        Document().add(Entity('room_floor', {'scope': 'house', 'level_z': 0.0, 'thickness': .15, 'offset_z': 0.0}))
    doc, st = owner_plan()
    st.execute(S.storey_slab_command(doc, 'room_floor', 0.0)[0])
    st.execute(AddEntity(S.opening_entity(doc, points=[(5.5, 1), (7.5, 1), (7.5, 3), (5.5, 3)])))
    path = tmp_path / 'slab.json'
    doc.save(str(path))
    loaded = Document.load(str(path))
    a = [room_slab_geometry(doc, e)['area'] for e in doc.entities.values() if e.kind == 'room_floor']
    b = [room_slab_geometry(loaded, e)['area'] for e in loaded.entities.values() if e.kind == 'room_floor']
    assert a == pytest.approx(b) and islands_area(room_slab_geometry(loaded, next(
        e for e in loaded.entities.values() if e.kind == 'room_floor'))['islands']) == pytest.approx(a[0])
