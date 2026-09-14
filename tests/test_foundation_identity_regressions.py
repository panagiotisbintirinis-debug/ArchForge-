from archforge.architecture.intent import infer_architecture
from archforge.architecture.room_identity import _polygon_matches, room_id_for_signature
from archforge.architecture.topology import room_faces
from archforge.core.commands import CommandStack, MoveEntities
from archforge.core.model import Document, Entity
from archforge.core.modifiers import SurfaceModifier, SurfaceRef
from archforge.geometry.plan import build_evaluation_plan
from archforge.geometry.selection import BrushSpec, SurfaceHit, sculpt_modifier_from_hit
from archforge.geometry.sculpt import SculptedPreviewBackend
from archforge.kinematics.integration import ensure_mount_cavity


def _closed_house():
    doc = Document()
    walls = []
    for a, b in [((0, 0), (5, 0)), ((5, 0), (5, 4)), ((5, 4), (0, 4)), ((0, 4), (0, 0))]:
        wall = Entity(
            'wall',
            {
                'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1],
                'z': 0, 'height': 2.8, 'thickness': 0.2,
            },
        )
        doc.add(wall)
        walls.append(wall.id)
    return doc, walls


def test_room_identity_survives_identical_boundary_wall_redraw():
    doc, walls = _closed_house()
    before = doc.active_room_faces()
    assert len(before) == 1
    old_signature = before[0].signature
    old_room_id = room_id_for_signature(doc, old_signature)
    assert old_room_id is not None
    doc.set_room_metadata(old_signature, name='Living Room', use='living')
    infer_architecture(doc)
    old_derived_ids = {e.id for e in doc.entities.values() if e.kind.startswith('room_')}

    old = doc.get(walls[0]).clone()
    doc.remove(old.id)
    replacement = Entity('wall', dict(old.params))
    doc.add(replacement)

    after = doc.active_room_faces()
    assert len(after) == 1
    new_signature = after[0].signature
    new_room_id = room_id_for_signature(doc, new_signature)

    assert new_signature != old_signature
    assert new_room_id == old_room_id
    assert doc.room_metadata(new_signature) == {'name': 'Living Room', 'use': 'living'}

    infer_architecture(doc)
    new_derived_ids = {e.id for e in doc.entities.values() if e.kind.startswith('room_')}
    assert new_derived_ids == old_derived_ids
    assert all(e.params.get('room_id') == old_room_id for e in doc.entities.values() if e.kind.startswith('room_'))


def test_room_binding_becomes_unclosed_then_recovers_same_id_after_redraw():
    doc, walls = _closed_house()
    face = doc.active_room_faces()[0]
    room_id = room_id_for_signature(doc, face.signature)
    old = doc.get(walls[0]).clone()
    doc.remove(old.id)
    assert doc.active_room_faces() == []
    assert doc.room_bindings[room_id]['status'] == 'unclosed'
    replacement = Entity('wall', dict(old.params));doc.add(replacement)
    restored = doc.active_room_faces()[0]
    assert room_id_for_signature(doc, restored.signature) == room_id
    assert doc.room_bindings[room_id]['status'] == 'enclosed'


def test_room_binding_metadata_and_derived_ids_survive_save_load_roundtrip():
    doc, _ = _closed_house()
    face = doc.active_room_faces()[0]
    room_id = room_id_for_signature(doc, face.signature)
    doc.set_room_metadata(face.signature, name='Kitchen', use='cooking')
    infer_architecture(doc)
    derived = {e.id for e in doc.entities.values() if e.kind.startswith('room_')}

    loaded = Document.from_dict(doc.to_dict())
    loaded_face = loaded.active_room_faces()[0]
    assert room_id_for_signature(loaded, loaded_face.signature) == room_id
    assert loaded.room_metadata(loaded_face.signature) == {'name': 'Kitchen', 'use': 'cooking'}
    assert {e.id for e in loaded.entities.values() if e.kind.startswith('room_')} == derived
    assert all(e.params.get('room_id') == room_id for e in loaded.entities.values() if e.kind.startswith('room_'))


def test_legacy_signature_keyed_room_metadata_migrates_on_reconciliation():
    doc, _ = _closed_house()
    signature = room_faces(doc)[0].signature
    doc.room_data[signature] = {'name': 'Legacy Room'}
    assert not doc.room_bindings

    doc.active_room_faces()
    room_id = room_id_for_signature(doc, signature)
    assert room_id is not None
    assert signature not in doc.room_data
    assert doc.room_data[room_id] == {'name': 'Legacy Room'}
    assert doc.room_metadata(signature) == {'name': 'Legacy Room'}


def test_polygon_rematching_uses_distance_tolerance_not_rounding_cells():
    a=((0,0),(1,0),(1,1),(0,1))
    b=((0,6e-6),(1,6e-6),(1,1+6e-6),(0,1+6e-6))
    assert _polygon_matches(a,b,1e-5)
    assert not _polygon_matches(a,b,1e-6)
    assert _polygon_matches(a,tuple(reversed(b)),1e-5)


def _wall_sculpt_profile(doc, wall_id):
    body = SculptedPreviewBackend().evaluate(doc).body(wall_id)
    ys = [v[1] for v in body.payload.vertices]
    return min(ys), max(ys)


def test_sculpt_attachment_moves_with_host_wall_without_mutating_persistent_world_state():
    doc = Document()
    wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 0, 'z': 0, 'height': 2.8, 'thickness': 0.2})
    doc.add(wall)
    modifier = sculpt_modifier_from_hit(doc, SurfaceHit(wall.id, 'exterior', (2.5, 0.1, 1.4), (0, 1, 0)), BrushSpec(1.25), 'pull', 0.25)
    mid=doc.add_surface_modifier(modifier)
    region=doc.surface_modifiers[mid].target.subregion
    assert region['uv_center']==[0.5,0.5]
    assert 'world_center' not in region
    hint=list(region['world_hint'])

    before = _wall_sculpt_profile(doc, wall.id)
    MoveEntities([wall.id], dx=10.0, dy=3.0, dz=0.0).do(doc)
    after = _wall_sculpt_profile(doc, wall.id)

    assert abs((after[0] - before[0]) - 3.0) < 1e-9
    assert abs((after[1] - before[1]) - 3.0) < 1e-9
    assert doc.surface_modifiers[mid].target.subregion['uv_center']==[0.5,0.5]
    assert doc.surface_modifiers[mid].target.subregion['world_hint']==hint
    assert 'world_center' not in doc.surface_modifiers[mid].target.subregion


def test_legacy_world_only_sculpt_moves_and_undoes_as_compatibility_path():
    doc=Document();stack=CommandStack(doc)
    wall=Entity('wall',{'x1':0,'y1':0,'x2':5,'y2':0,'z':0,'height':2.8,'thickness':.2});doc.add(wall)
    legacy=SurfaceModifier(SurfaceRef(wall.id,'exterior',{
        'world_center':[2.5,.1,1.4],'radius':1.0,'strength':1.0,'falloff':'smooth'
    }),'pull',{'amount':.2})
    mid=doc.add_surface_modifier(legacy)
    stack.execute(MoveEntities([wall.id],2,3,1))
    assert doc.surface_modifiers[mid].target.subregion['world_center']==[4.5,3.1,2.4]
    stack.undo()
    assert doc.surface_modifiers[mid].target.subregion['world_center']==[2.5,.1,1.4]
    stack.redo()
    assert doc.surface_modifiers[mid].target.subregion['world_center']==[4.5,3.1,2.4]


def test_move_entities_supports_mechanical_part_with_undo_redo():
    doc=Document();stack=CommandStack(doc)
    part=Entity('mechanical_part',{'x':1,'y':2,'z':3,'width':1,'depth':1,'height':1,'rotation':0});doc.add(part)
    stack.execute(MoveEntities([part.id],4,-1,2))
    assert (part.params['x'],part.params['y'],part.params['z'])==(5,1,5)
    stack.undo();assert (part.params['x'],part.params['y'],part.params['z'])==(1,2,3)
    stack.redo();assert (part.params['x'],part.params['y'],part.params['z'])==(5,1,5)


def test_uv_sculpt_follows_box_rotation_without_command_rewriting_modifier():
    doc=Document()
    box=Entity('box',{'x':0,'y':0,'z':0,'width':2,'depth':2,'height':2,'rotation':0});doc.add(box)
    mid=doc.add_surface_modifier(sculpt_modifier_from_hit(doc,SurfaceHit(box.id,'top',(2,0,2),(0,0,1)),BrushSpec(.3),'pull',.3))
    before=SculptedPreviewBackend().evaluate(doc).body(box.id)
    raised_before=[v for v in before.payload.vertices if v[2]>2.1]
    assert len(raised_before)==1 and abs(raised_before[0][0]-2)<1e-9 and abs(raised_before[0][1])<1e-9
    stored_before=dict(doc.surface_modifiers[mid].target.subregion)

    doc.update(box.id,{'rotation':90})
    after=SculptedPreviewBackend().evaluate(doc).body(box.id)
    raised_after=[v for v in after.payload.vertices if v[2]>2.1]
    assert len(raised_after)==1 and abs(raised_after[0][0])<1e-9 and abs(raised_after[0][1]-2)<1e-9
    assert doc.surface_modifiers[mid].target.subregion==stored_before


def test_sculpt_attachment_follows_kinematic_part_transform():
    doc = Document()
    root = Entity('mechanical_part', {'x': 0, 'y': 0, 'z': 0, 'width': .2, 'depth': .2, 'height': .2, 'rotation': 0})
    child = Entity('mechanical_part', {'x': 1, 'y': 0, 'z': 0, 'width': .4, 'depth': .2, 'height': .2, 'rotation': 0})
    doc.add(root);doc.add(child)
    joint = Entity('mechanical_joint', {
        'joint_type': 'prismatic', 'parent_part': root.id, 'child_part': child.id,
        'anchor': [0, 0, 0], 'axis': [0, 1, 0], 'min_value': 0, 'max_value': 1, 'value': 0,
    })
    doc.add(joint)
    mod = sculpt_modifier_from_hit(doc, SurfaceHit(child.id, 'top', (1.2, .1, .2), (0, 0, 1)), BrushSpec(.3), 'pull', .1)
    doc.add_surface_modifier(mod)

    rest = SculptedPreviewBackend().evaluate(doc, {joint.id: 0}).body(child.id)
    moved = SculptedPreviewBackend().evaluate(doc, {joint.id: .5}).body(child.id)
    rest_y = (min(v[1] for v in rest.payload.vertices), max(v[1] for v in rest.payload.vertices))
    moved_y = (min(v[1] for v in moved.payload.vertices), max(v[1] for v in moved.payload.vertices))
    assert abs((moved_y[0] - rest_y[0]) - .5) < 1e-9
    assert abs((moved_y[1] - rest_y[1]) - .5) < 1e-9
    assert abs(max(v[2] for v in moved.payload.vertices) - max(v[2] for v in rest.payload.vertices)) < 1e-9
    assert moved.modifiers_applied is True


def test_mechanism_cavity_envelope_is_refreshed_from_mount_semantics_in_evaluation_plan():
    doc=Document()
    host=Entity('wall',{'x1':0,'y1':0,'x2':8,'y2':0,'z':0,'height':3,'thickness':.3});doc.add(host)
    part=Entity('mechanical_part',{'x':1,'y':0,'z':1,'width':.5,'depth':.2,'height':.5,'rotation':0});doc.add(part)
    mount=Entity('mechanical_mount',{
        'host_id':host.id,'part_id':part.id,'surface_role':'interior','clearance':.02,'embed_depth':.18,
    });doc.add(mount)
    mid=ensure_mount_cavity(doc,mount.id)
    cached_before=list(doc.surface_modifiers[mid].target.subregion['envelope_min'])
    plan_before=build_evaluation_plan(doc)
    raw_before=next(m for m in plan_before.node(host.id).modifiers if m['id']==mid)

    MoveEntities([part.id],2,0,0).do(doc)
    assert doc.surface_modifiers[mid].target.subregion['envelope_min']==cached_before
    plan_after=build_evaluation_plan(doc)
    raw_after=next(m for m in plan_after.node(host.id).modifiers if m['id']==mid)
    assert abs((raw_after['target']['subregion']['envelope_min'][0]-raw_before['target']['subregion']['envelope_min'][0])-2.0)<1e-9
