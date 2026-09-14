import copy
import pytest

from archforge.core.model import Document, Entity, WorkPlane
from archforge.core.commands import (
    CommandStack,
    SetWorkPlane,
    SetLevel,
    RemoveLevel,
    SetMaterial,
    SetConstruction,
    AssignConstruction,
)
from archforge.architecture.intent import (
    infer_architecture,
    infer_building_architecture,
    ArchitectureDefaults,
)


def _two_storey_walls():
    doc = Document()
    doc.levels['Level 1'] = 3.0

    # Ground floor room at z=0 (4 walls)
    for a, b in [((0, 0), (6, 0)), ((6, 0), (6, 5)), ((6, 5), (0, 5)), ((0, 5), (0, 0))]:
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': a[1], 'z': 0.0, 'height': 3.0, 'thickness': 0.2}))

    # Correct the two vertical edges after constructing them explicitly above.
    ground = [e for e in doc.entities.values() if e.kind == 'wall' and e.params['z'] == 0.0]
    ground[1].params['y2'] = 5.0
    ground[2].params['y1'] = 5.0
    ground[2].params['y2'] = 5.0
    ground[3].params['y1'] = 5.0
    ground[3].params['y2'] = 0.0

    # First floor room at z=3.0 directly above (4 walls)
    for a, b in [((0, 0), (6, 0)), ((6, 0), (6, 5)), ((6, 5), (0, 5)), ((0, 5), (0, 0))]:
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 3.0, 'height': 2.8, 'thickness': 0.2}))

    return doc


def _binding_z(doc, entity):
    room_id = entity.params.get('room_id')
    return float(doc.room_bindings[room_id]['z'])


def test_infer_building_architecture_two_storeys_uses_building_envelope_semantics():
    doc = _two_storey_walls()
    result = infer_building_architecture(doc)

    assert len(result.room_signatures) == 2

    foundations = [e for e in doc.entities.values() if e.kind == 'room_foundation']
    floors = [e for e in doc.entities.values() if e.kind == 'room_floor']
    ceilings = [e for e in doc.entities.values() if e.kind == 'room_ceiling']
    roofs = [e for e in doc.entities.values() if e.kind == 'room_roof']

    # Building envelope, not four independent slabs per storey:
    # one bottom foundation + a floor/ceiling pair per storey + one top roof.
    assert len(result.created_ids) == 6
    assert len(foundations) == 1
    assert len(floors) == 2
    assert len(ceilings) == 2
    assert len(roofs) == 1
    assert _binding_z(doc, foundations[0]) == pytest.approx(0.0)
    assert _binding_z(doc, roofs[0]) == pytest.approx(3.0)

    # Idempotence across multi-storey buildings.
    result_repeat = infer_building_architecture(doc)
    assert len(result_repeat.room_signatures) == 2
    assert result_repeat.created_ids == ()
    assert len([e for e in doc.entities.values() if e.kind == 'room_foundation']) == 1
    assert len([e for e in doc.entities.values() if e.kind == 'room_roof']) == 1


def test_building_inference_prunes_legacy_internal_foundations_and_roofs():
    doc = _two_storey_walls()

    # Simulate the previous behavior: each level inferred independently and therefore
    # receives both a foundation and a roof.
    infer_architecture(doc, z=0.0)
    infer_architecture(doc, z=3.0)
    assert len([e for e in doc.entities.values() if e.kind == 'room_foundation']) == 2
    assert len([e for e in doc.entities.values() if e.kind == 'room_roof']) == 2

    infer_building_architecture(doc)

    foundations = [e for e in doc.entities.values() if e.kind == 'room_foundation']
    roofs = [e for e in doc.entities.values() if e.kind == 'room_roof']
    assert len(foundations) == 1
    assert len(roofs) == 1
    assert _binding_z(doc, foundations[0]) == pytest.approx(0.0)
    assert _binding_z(doc, roofs[0]) == pytest.approx(3.0)


def test_storey_inference_does_not_flatten_universal_xyz_or_organic_geometry():
    doc = _two_storey_walls()
    pod = Entity('pod', {
        'cx': 11.0, 'cy': -2.0, 'floor_level': 1.35,
        'diameter_x': 7.0, 'diameter_y': 5.0, 'height': 4.2,
        'shell_thickness': 0.18, 'rotation': 23.0,
    })
    doc.add(pod)
    pod_before = copy.deepcopy(pod.params)

    sculpt_plane = WorkPlane(
        name='Free3D',
        origin=(1.0, 2.0, 1.4),
        u=(1.0, 0.0, 0.0),
        v=(0.0, 0.8, 0.6),
    )
    doc.work_plane = copy.deepcopy(sculpt_plane)

    result = infer_building_architecture(doc)

    assert len(result.room_signatures) == 2
    assert doc.work_plane == sculpt_plane
    assert doc.get(pod.id).params == pod_before
    assert pod.id in doc.entities


def test_level_commands_undo_redo():
    doc = Document()
    stack = CommandStack(doc)

    assert doc.levels == {'Ground': 0.0}

    # Add Level 1
    stack.execute(SetLevel('Level 1', 3.2))
    assert doc.levels['Level 1'] == 3.2

    # Update Level 1
    stack.execute(SetLevel('Level 1', 3.5))
    assert doc.levels['Level 1'] == 3.5

    # Undo update
    stack.undo()
    assert doc.levels['Level 1'] == 3.2

    # Undo addition
    stack.undo()
    assert 'Level 1' not in doc.levels

    # Redo addition
    stack.redo()
    assert doc.levels['Level 1'] == 3.2

    # Remove Level 1
    stack.execute(RemoveLevel('Level 1'))
    assert 'Level 1' not in doc.levels

    # Undo removal
    stack.undo()
    assert doc.levels['Level 1'] == 3.2


def test_work_plane_command_undo_redo():
    doc = Document()
    stack = CommandStack(doc)
    assert doc.work_plane.name == 'XY'

    new_wp = WorkPlane(name='RoofSlope', origin=(0, 0, 3.0), u=(1, 0, 0), v=(0, 0.7071, 0.7071))
    stack.execute(SetWorkPlane(new_wp))
    assert doc.work_plane.name == 'RoofSlope'
    assert doc.work_plane.origin == (0, 0, 3.0)

    stack.undo()
    assert doc.work_plane.name == 'XY'
    assert doc.work_plane.origin == (0, 0, 0)

    stack.redo()
    assert doc.work_plane.name == 'RoofSlope'


def test_material_and_construction_commands_undo_redo():
    doc = Document()
    stack = CommandStack(doc)

    wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 0, 'z': 0, 'height': 2.8, 'thickness': 0.2})
    doc.add(wall)

    # Set material
    stack.execute(SetMaterial('timber_cladding', {'density': 550, 'color': '#c28854'}))
    assert doc.materials['timber_cladding']['density'] == 550

    # Set construction (Spectre system)
    stack.execute(SetConstruction('spectre_wall_01', {
        'system': 'Bio-Spectre',
        'layers': [{'material': 'timber_cladding', 'thickness': 0.02}],
        'u_value': 0.18,
    }))
    assert doc.constructions['spectre_wall_01']['system'] == 'Bio-Spectre'

    # Assign construction to entity
    stack.execute(AssignConstruction(wall.id, construction_id='spectre_wall_01', material_id='timber_cladding'))
    assert doc.get(wall.id).params['construction_id'] == 'spectre_wall_01'
    assert doc.get(wall.id).params['material_id'] == 'timber_cladding'

    # Undo assignment
    stack.undo()
    assert 'construction_id' not in doc.get(wall.id).params
    assert 'material_id' not in doc.get(wall.id).params

    # Redo assignment
    stack.redo()
    assert doc.get(wall.id).params['construction_id'] == 'spectre_wall_01'

    # Undo construction definition
    stack.undo()  # unassign
    stack.undo()  # set construction
    assert 'spectre_wall_01' not in doc.constructions
