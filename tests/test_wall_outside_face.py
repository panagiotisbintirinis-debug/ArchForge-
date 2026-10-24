"""Owner 23/10: «όταν βάζουμε υλικά σε τοίχο μέσα / έξω είναι ανάποδα — το εξωτερικό αλλάζει από μέσα».

A wall's side A ('exterior' surface role) is the left of the way it was drawn; a room drawn anticlockwise has it
inside. «Εξωτερική» in the material choices, the assembly's exterior layer (ETICS) in the plan and its finishing
colour in 3D now go to the face that really looks out."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.architecture.wall_face import outside_sign, side_roles
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity


def _room(clockwise):
    doc = Document(); st = CommandStack(doc)
    pts = [(0, 0), (6, 0), (6, 5), (0, 5)]
    if clockwise:
        pts = pts[::-1]
    ids = []
    for a, b in zip(pts, pts[1:] + pts[:1]):
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 2.7,
                            'thickness': 0.38, 'wall_type': 'concrete_etics'})
        st.execute(AddEntity(e)); ids.append(e.id)
    return doc, ids


def test_the_face_that_looks_out_is_the_exterior_whichever_way_the_room_was_drawn():
    for clockwise, sign in ((True, 1), (False, -1)):
        doc, ids = _room(clockwise)
        # Anticlockwise: side A (left of x1→x2) is inside.
        assert {outside_sign(doc, i) for i in ids} == {sign}
        assert {side_roles(doc, i) for i in ids} == {('exterior', 'interior') if sign > 0 else ('interior', 'exterior')}


def test_etics_is_drawn_on_the_outside_and_coloured_outside_in_3d():
    from archforge.architecture.wall_types import face_colors, layer_lines, layers
    doc, ids = _room(clockwise=False)
    w = doc.get(ids[0]).params                                    # (0,0)→(6,0): side A = +y = inside the room
    lines = layer_lines(w, 'concrete_etics', outside_sign(doc, ids[0]))
    insulation_y = [pts[0][1] for pts, ins in lines if ins]
    assert insulation_y and all(y < 0 for y in insulation_y)      # the EPS on the outside (−y), not inside the room
    out_colour = layers('concrete_etics')[0][3]
    assert face_colors('concrete_etics', -1)[1] == out_colour     # side B (outside) gets the exterior plaster


def test_material_choices_say_exterior_for_the_outside_face():
    from archforge.ui.material_library import _targets
    doc, ids = _room(clockwise=False)
    t = {x.label: x.key for x in _targets(doc.get(ids[0]), doc)}
    assert t['Εξωτερική πλευρά (προς τα έξω)'] == 'interior' and t['Εσωτερική πλευρά'] == 'exterior'
    doc, ids = _room(clockwise=True)
    t = {x.label: x.key for x in _targets(doc.get(ids[0]), doc)}
    assert t['Εξωτερική πλευρά (προς τα έξω)'] == 'exterior'
