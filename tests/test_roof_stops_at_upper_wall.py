"""U01 (owner 28/10, his file «…111»): a lower storey's tiled roof went through the wall of the storey above — its
frame ran to the FAR face of that wall and its gable rose to ~3,9 m, inside the upper storey's wall. A roof leaning on
a taller wall stops at that wall's face; rooms are not merged into one roof that would run under the upper storey."""
import json
import os

from archforge.core.commands import AddEntity, CommandStack, CreateFloorLevel, SetWorkPlane
from archforge.core.model import Document, Entity


def _wall(stack, a, b, z, t=0.15):
    stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': z,
                                            'height': 2.7, 'thickness': t})))


def _house():
    """Ground 10 × 6 (two rooms, wall at x = 5); upper storey only over x 5..10."""
    import copy
    doc = Document(); stack = CommandStack(doc)
    for a, b in (((0, 0), (10, 0)), ((10, 0), (10, 6)), ((10, 6), (0, 6)), ((0, 6), (0, 0)), ((5, 0), (5, 6))):
        _wall(stack, a, b, 0.0)
    plane = copy.deepcopy(doc.work_plane)
    stack.execute(CreateFloorLevel('Floor 2', 3.0)); stack.execute(SetWorkPlane(plane))
    for a, b in (((5, 0), (10, 0)), ((10, 0), (10, 6)), ((10, 6), (5, 6)), ((5, 6), (5, 0))):
        _wall(stack, a, b, 3.0)
    return doc, stack


def _upper_walls(doc):
    return [e for e in doc.entities.values() if e.kind == 'wall' and float(e.params['z']) >= 2.9]


def _through_upper_wall(doc, roof):
    """A roof frame side past the near face of an upper-storey wall standing over it."""
    x0, y0, x1, y1 = (float(roof[k]) for k in ('x0', 'y0', 'x1', 'y1'))
    bad = []
    for w in _upper_walls(doc):
        p = w.params; half = float(p['thickness']) / 2
        if abs(p['x1'] - p['x2']) < 1e-6 and max(min(p['y1'], p['y2']), y0) < min(max(p['y1'], p['y2']), y1) - 0.3:
            c = float(p['x1'])
            if x0 < c - half - 1e-6 and x1 > c - half + 1e-6 and x1 <= c + half + 0.2:
                bad.append(('x1', x1, c - half))
            if x1 > c + half + 1e-6 and x0 < c + half - 1e-6 and x0 >= c - half - 0.2:
                bad.append(('x0', x0, c + half))
        if abs(p['y1'] - p['y2']) < 1e-6 and max(min(p['x1'], p['x2']), x0) < min(max(p['x1'], p['x2']), x1) - 0.3:
            c = float(p['y1'])
            if y0 < c - half - 1e-6 and y1 > c - half + 1e-6 and y1 <= c + half + 0.2:
                bad.append(('y1', y1, c - half))
            if y1 > c + half + 1e-6 and y0 < c + half - 1e-6 and y0 >= c - half - 0.2:
                bad.append(('y0', y0, c + half))
    return bad


def test_room_roof_on_the_lower_room_stops_at_the_face_of_the_upper_wall():
    from archforge.architecture.roof_choice import room_roof_command
    from archforge.assistant.understanding import read_drawing
    doc, stack = _house()
    ground = next(s for s in read_drawing(doc)['storeys'] if abs(s['z']) < 1e-6)
    west = next(r for r in ground['rooms'] if r['centroid'][0] < 5)
    command, _msg = room_roof_command(doc, west, 'tiled', z=0.0)
    stack.execute(command)
    roof = next(e.params for e in doc.entities.values() if e.kind == 'pitched_roof')
    assert not _through_upper_wall(doc, roof), roof
    assert abs(float(roof['x1']) - (5.0 - 0.075)) < 1e-6          # at the upper wall's outer face
    assert abs(float(roof['x0']) - (0.0 - 0.075)) < 1e-6          # the free side still covers its own wall


def test_lower_rooms_are_not_merged_into_a_roof_running_under_the_upper_storey():
    from archforge.architecture.roof_need import coverage
    from archforge.structure.timber_roof import auto_roofs
    doc, stack = _house()
    for params, _reason in auto_roofs(doc, lower_storeys=True):
        if float(params['eave_z']) > 3.5:
            continue                                                 # the upper storey's own roof
        box = [(params['x0'], params['y0']), (params['x1'], params['y0']), (params['x1'], params['y1']),
               (params['x0'], params['y1'])]
        assert coverage(doc, box, 0.0) < 0.05, params
        assert not _through_upper_wall(doc, params), params


def test_owner_file_roofs_made_again_stay_out_of_the_upper_storey():
    from archforge.architecture.roof_need import coverage
    from archforge.structure.timber_roof import auto_roofs
    path = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')
    with open(path, encoding='utf-8') as f:
        doc = Document.from_dict(json.load(f))
    lower = [p for p, _r in auto_roofs(doc, lower_storeys=True) if float(p['eave_z']) < 3.5]
    assert lower
    for params in lower:
        box = [(params['x0'], params['y0']), (params['x1'], params['y0']), (params['x1'], params['y1']),
               (params['x0'], params['y1'])]
        assert coverage(doc, box, 0.0) < 0.05, params
        assert not _through_upper_wall(doc, params), params


def test_owner_file_lower_roofs_do_not_overlap_each_other():
    from archforge.structure.timber_roof import auto_roofs
    path = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')
    with open(path, encoding='utf-8') as f:
        doc = Document.from_dict(json.load(f))
    lower = [p for p, _r in auto_roofs(doc, lower_storeys=True) if float(p['eave_z']) < 3.5]
    # Frames may share a wall (both reach its outer faces ± half its thickness), never more.
    for i, a in enumerate(lower):
        for b in lower[i + 1:]:
            dx = min(a['x1'], b['x1']) - max(a['x0'], b['x0'])
            dy = min(a['y1'], b['y1']) - max(a['y0'], b['y0'])
            assert dx <= 0.2 or dy <= 0.2, (a, b)


def test_owner_file_lower_roofs_sit_on_the_concrete_beams_not_under_them():
    """Owner 28/10: «στη στέγη φαίνονται τα δοκάρια του μπετού από πάνω» — the ground-floor beams (top 3,00) stood
    30 cm over a roof framed at the walls' top (2,70)."""
    from archforge.structure.timber_roof import auto_roofs, roof_z_at
    path = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')
    with open(path, encoding='utf-8') as f:
        doc = Document.from_dict(json.load(f))
    lower = [p for p, _r in auto_roofs(doc, lower_storeys=True) if float(p['eave_z']) < 3.5]
    beams = [e.params for e in doc.entities.values() if e.kind == 'structural_beam' and e.params.get('level') == 'Ground']
    checked = 0
    for p in lower:
        for b in beams:
            for t in (0.1, 0.5, 0.9):
                x = b['x1'] + (b['x2'] - b['x1']) * t; y = b['y1'] + (b['y2'] - b['y1']) * t
                if p['x0'] + 0.05 < x < p['x1'] - 0.05 and p['y0'] + 0.05 < y < p['y1'] - 0.05:
                    assert roof_z_at(p, x, y) >= float(b['z']) + float(b['height']) - 1e-6, (p, b)
                    checked += 1
    assert checked
