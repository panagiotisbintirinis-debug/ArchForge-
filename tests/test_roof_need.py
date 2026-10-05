"""Roofs only where nothing is built above; the assistant spots and removes a roof under a storey."""
import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.architecture.roof_need import coverage, roof_needed
from archforge.core.commands import AddEntity, CommandStack, CreateRoomRoofs
from archforge.core.model import Document, Entity


def _two_storeys():
    """Ground 10×6 (two rooms), upper storey only over the left room 0..5."""
    doc = Document(); st = CommandStack(doc)
    doc.levels['Floor 2'] = 2.7
    for s in [(0, 0, 10, 0), (10, 0, 10, 6), (10, 6, 0, 6), (0, 6, 0, 0), (5, 0, 5, 6)]:
        st.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0, 'height': 2.7, 'thickness': 0.2})))
    for s in [(0, 0, 5, 0), (5, 0, 5, 6), (5, 6, 0, 6), (0, 6, 0, 0)]:
        st.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 2.7, 'height': 2.7, 'thickness': 0.2})))
    faces = sorted(doc.active_room_faces(z=0.0), key=lambda f: min(p[0] for p in f.polygon))
    return doc, st, faces


def test_only_the_uncovered_room_needs_a_roof():
    doc, _st, (left, right) = _two_storeys()
    assert coverage(doc, left.polygon, 0.0) > 0.95 and roof_needed(doc, left.signature)[0] is False
    assert coverage(doc, right.polygon, 0.0) == 0.0 and roof_needed(doc, right.signature)[0] is True
    upper = doc.active_room_faces(z=2.7)[0]
    assert roof_needed(doc, upper.signature)[0] is True                 # top storey: nothing above


def test_auto_roof_skips_rooms_under_the_upper_storey():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        doc, _st, (left, right) = _two_storeys()
        w.doc.levels.update(doc.levels)
        for e in doc.entities.values():
            w.stack.execute(AddEntity(Entity(e.kind, dict(e.params))))
        w._create_flat_roofs()
        roofs = [e for e in w.doc.entities.values() if e.kind == 'room_roof']
        from archforge.architecture.roof_need import room_face_of
        assert len(roofs) == 1
        face, _z = room_face_of(w.doc, roofs[0])
        assert min(p[0] for p in face.polygon) >= 4.9                    # the right room (nothing above it)
        assert 'παραλείφθηκαν 1' in w.statusBar().currentMessage()
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_assistant_flags_a_roof_under_a_storey_and_removes_it_when_pointed_at():
    from archforge.assistant.suggestions import Proposal, apply, propose
    from archforge.assistant.target import actions_for, match, target_of_entity
    doc, st, (left, right) = _two_storeys()
    st.execute(CreateRoomRoofs([left.signature, right.signature]))
    roofs = {e.params['room_signature']: e.id for e in doc.entities.values() if e.kind == 'room_roof'}
    flags = [p for p in propose(doc) if p.key.startswith('R-1')]
    assert [p.targets for p in flags] == [(roofs[left.signature],)]          # only the covered one
    # Pointing at the roof (e.g. picked in 3D) gives its place and a delete action.
    t = target_of_entity(doc, roofs[left.signature])
    assert 2.0 < t.x < 3.0 and t.label.startswith('Στέγη')
    actions = actions_for(doc, t)
    assert not any(a.key in ('fan', 'hood', 'joists') for a in actions)
    remove = match('αφαίρεσε αυτή τη στέγη', actions)
    assert remove is not None and 'δεν χρειάζεται' in remove.info
    apply(st, Proposal(remove.key, 'hint', remove.label, '', '', (), remove.build))
    assert roofs[left.signature] not in doc.entities and roofs[right.signature] in doc.entities
    st.undo()
    assert roofs[left.signature] in doc.entities


def _window_with(doc):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.doc.levels.update(doc.levels)
    for e in doc.entities.values():
        if e.kind == 'wall':
            w.stack.execute(AddEntity(Entity('wall', dict(e.params))))
    return app, w


def test_roof_menu_auto_and_fix_roofs_in_one_undo():
    from archforge.architecture.roof_need import room_face_of, roof_plan
    doc, _st, _faces = _two_storeys()
    app, w = _window_with(doc)
    try:
        texts = [a.text() for a in w._roof_menu.actions() if a.text()]
        assert texts[:3] == ['Με κεραμίδια (ξύλινη στέγη)', 'Χωρίς κεραμίδια (επίπεδη / δώμα)', 'Οροφή σοφίτας κάτω από κεραμοσκεπή']
        assert 'Διόρθωση στεγών' in texts and 'Διαγραφή όλων των στεγών' in texts
        assert [a.text() for a in w._roof_tiled_menu.actions()] == ['Δίρριχτη', 'Τετράρριχτη', 'Μονόρριχτη']
        # A wrong roof under the upper storey (as the old Flat Roof made) …
        left = min(w.doc.active_room_faces(z=0.0), key=lambda f: min(p[0] for p in f.polygon))
        w.stack.execute(CreateRoomRoofs([left.signature]))
        plan = roof_plan(w.doc)
        assert len(plan['remove']) == 1 and len(plan['add']) == 2      # right ground room + the upper storey
        w._fix_roofs()

        def roofs():
            out = []
            for e in w.doc.entities.values():
                if e.kind == 'room_roof':
                    face, z = room_face_of(w.doc, e)
                    out.append((round(z, 1), round(min(p[0] for p in face.polygon))))
            return sorted(out)
        assert roofs() == [(0.0, 5), (2.7, 0)]
        assert roof_plan(w.doc) == {'remove': [], 'add': []}
        w.stack.undo()                                                    # one step back to the wrong roof
        assert roofs() == [(0.0, 0)]
        w.stack.undo()
        assert w._auto_roofs() == 2 and roofs() == [(0.0, 5), (2.7, 0)]
        assert w._delete_all_roofs() == 2 and roofs() == []
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_room_under_a_timber_roof_gets_no_flat_roof():
    from archforge.architecture.roof_need import roof_plan
    from archforge.structure.timber_roof import default_params
    doc = Document(); st = CommandStack(doc)
    for s in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0)]:
        st.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0, 'height': 2.7, 'thickness': 0.2})))
    assert len(roof_plan(doc)['add']) == 1
    st.execute(AddEntity(Entity('pitched_roof', default_params(doc))))
    assert roof_plan(doc)['add'] == []


def test_room_under_timber_roof_can_take_a_flat_attic_ceiling():
    """Owner: the space under a tiled roof must be able to take a flat ceiling, like an attic."""
    from archforge.architecture.roof_need import attic_ceiling_entities, attic_rooms
    from archforge.assistant.target import actions_for, match, target_at
    from archforge.core.commands import AddEntities
    from archforge.structure.timber_roof import default_params
    doc = Document(); st = CommandStack(doc)
    for s in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0)]:
        st.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0, 'height': 2.7, 'thickness': 0.2})))
    assert attic_rooms(doc) == []                                        # no timber roof yet
    st.execute(AddEntity(Entity('pitched_roof', default_params(doc))))
    assert len(attic_rooms(doc)) == 1
    slab = attic_ceiling_entities(doc, 'slab')
    assert slab[0].kind == 'room_ceiling' and slab[0].params['offset_z'] == pytest.approx(2.7 - 0.15)
    joists = attic_ceiling_entities(doc, 'joists')
    assert joists[0].kind == 'ceiling_joists'
    action = match('βάλε επίπεδη οροφή σοφίτας', actions_for(doc, target_at(doc, 4.0, 3.0)))
    assert action is not None and action.key == 'attic_slab'
    st.execute(AddEntities(slab))
    assert attic_rooms(doc) == []                                        # done → not offered again
    st.undo()
    assert len(attic_rooms(doc)) == 1


def test_tiled_roof_goes_over_the_top_storey_even_from_the_ground_floor():
    doc, _st, _faces = _two_storeys()
    app, w = _window_with(doc)
    try:
        w._activate_level_by_name('Ground')
        roof = w._create_pitched_roof('hip')
        assert roof.params['roof_form'] == 'hip' and roof.params['eave_z'] == pytest.approx(2.7 + 2.7)
        assert roof.params['x1'] < 5.5                                     # over the upper storey only
    finally:
        w._mark_clean(); w.close(); app.processEvents()
