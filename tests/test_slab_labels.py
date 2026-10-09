"""Owner: «Auto Roof, Auto Floor — ποιου δωματίου; Ποιες διαστάσεις; Αυτές είναι πλάκες.»

Every slab in the project tree and in the Properties says what it is and where, from the live
geometry: «Πλάκα δαπέδου — Χώρος 1 · 5,00×8,00 m · 40,0 m² · 15 cm».  A slab whose room is gone
says so and the assistant offers to remove it.  Stored names/kinds are not touched.
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity, CommandStack, CreateRoomFloors, CreateRoomRoofs, DeleteEntities
from archforge.core.model import Document, Entity
from archforge.ui.project_outline import entity_level, project_outline, slab_label, slab_rows


def _house():
    """Ground 10×8: left room 5×8, right part split in two; upper storey 10×8 in two rooms."""
    doc = Document(); st = CommandStack(doc)
    doc.levels['Floor 2'] = 3.0
    walls = []
    for z in (0.0, 3.0):
        for s in [(0, 0, 10, 0), (10, 0, 10, 8), (10, 8, 0, 8), (0, 8, 0, 0), (5, 0, 5, 8)] + ([(5, 4, 10, 4)] if z == 0 else []):
            e = Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': z, 'height': 2.8, 'thickness': 0.25})
            st.execute(AddEntity(e)); walls.append(e.id)
    st.execute(CreateRoomFloors([f.signature for z in (0.0, 3.0) for f in doc.active_room_faces(z=z)]))
    st.execute(CreateRoomRoofs([f.signature for f in doc.active_room_faces(z=3.0)]))
    return doc, st, walls


def _slabs(doc, kind):
    return [e for e in doc.entities.values() if e.kind == kind]


def _labels(node):
    out = [node['label']]
    for c in node['children']:
        out += _labels(c)
    return out


def test_every_slab_says_what_and_where_with_live_sizes():
    doc, _st, _w = _house()
    floors = _slabs(doc, 'room_floor')
    labels = sorted(slab_label(doc, e) for e in floors)
    assert len(labels) == 5 and all(l.startswith('Πλάκα δαπέδου — Χώρος ') for l in labels)
    big = [l for l in labels if '5,00×8,00 m' in l]
    assert big and all('m²' in l and '15 cm' in l for l in labels)
    assert all('room-' not in l and 'Auto' not in l for l in labels)
    roofs = [slab_label(doc, e) for e in _slabs(doc, 'room_roof')]
    assert roofs and all(l.startswith('Πλάκα δώματος — Χώρος ') for l in roofs)
    # Stored names stay as they were (only the display changes).
    assert {e.name for e in floors} == {'Auto Floor'}
    # Properties rows: Greek, room by name, sizes; never the signature.
    rows = dict(slab_rows(doc, floors[0]))
    assert rows['Τι είναι'] == 'Πλάκα δαπέδου' and rows['Χώρος'].startswith('Χώρος ')
    assert 'Διαστάσεις' in rows and rows['Εμβαδόν'].endswith('m²')


def test_room_name_given_by_the_user_shows():
    doc, _st, _w = _house()
    floor = _slabs(doc, 'room_floor')[0]
    from archforge.ui.project_outline import _slab_face
    face, _z = _slab_face(doc, floor)
    doc.set_room_metadata(face.signature, name='Σαλόνι')
    assert '(Σαλόνι)' in slab_label(doc, floor)


def test_tree_puts_slabs_under_their_storey():
    doc, _st, _w = _house()
    levels = {e.id: entity_level(doc, e) for e in _slabs(doc, 'room_floor')}
    assert sorted(levels.values()) == ['Floor 2', 'Floor 2', 'Ground', 'Ground', 'Ground']
    labels = _labels(project_outline(doc))
    assert sum(l.startswith('Πλάκα δαπέδου — Χώρος') for l in labels) == 5
    assert not any(l in ('Δάπεδο (αυτόματο)', 'Δώμα', 'Auto Floor', 'Flat Roof') for l in labels)


def test_orphan_slab_is_flagged_and_the_assistant_cleans_it():
    doc, st, walls = _house()
    st.execute(DeleteEntities([walls[5]]))              # the ground partition goes: two rooms become one
    orphans = [e for e in _slabs(doc, 'room_floor') if slab_label(doc, e).startswith('⚠')]
    assert orphans and all('χωρίς χώρο' in slab_label(doc, e) for e in orphans)
    assert dict(slab_rows(doc, orphans[0]))['Χώρος'].startswith('⚠')
    from archforge.assistant.suggestions import apply, propose
    hit = [p for p in propose(doc) if p.key == 'S-0']
    assert hit and set(hit[0].targets) == {e.id for e in orphans}
    apply(st, hit[0])
    assert not any(e.id in doc.entities for e in orphans)
    st.undo()                                            # one undo brings them back
    assert all(e.id in doc.entities for e in orphans)
