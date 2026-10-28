"""Λίστα εργασιών Α3 Β (εισαγωγή): unreadable lines of a DXF / points file are counted and said once per file."""
from archforge.core import notices
from archforge.project.underlay import parse_dxf_segments
from archforge.site.survey import parse_dxf, parse_points

LINE = ["0", "SECTION", "2", "ENTITIES", "0", "LINE", "8", "WALLS", "10", "0.0", "20", "0.0", "11", "5.0", "21", "0.0",
        "0", "ENDSEC", "0", "EOF"]


def test_a_valid_dxf_says_nothing():
    with notices.collecting() as found:
        assert parse_dxf_segments("\n".join(LINE))["segments"]
        parse_dxf("\n".join(LINE))
    assert found == []


def test_damaged_dxf_lines_are_counted_and_said():
    damaged = LINE[:8] + ["1O", "0.0", "20", "abc"] + LINE[12:]       # a letter O in a code, text in a coordinate
    with notices.collecting() as found:
        parse_dxf_segments("\n".join(damaged))
    assert [i.code for i in found] == ["dxf.underlay"]
    assert "2 γραμμές δεν διαβάστηκαν" in found[0].message


def test_points_file_header_is_fine_a_damaged_line_is_said():
    text = "Όνομα X Y Z\nP1 100,0 200,0 15,2\nP2 101,5 20x,0 15,4\nP3 102,0 201,0 15,6\n"
    with notices.collecting() as found:
        pts = parse_points(text)
    assert len(pts) == 2
    assert [i.code for i in found] == ["survey.points"] and "γραμμή 3" in found[0].message


def test_rooms_unreadable_are_said_by_walls_doors_and_dimensions(monkeypatch):
    from archforge.architecture import dimension_reference, dimensions, joinery
    from archforge.core.model import Document, Entity
    doc = Document()
    wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 0, 'z': 0, 'height': 2.8, 'thickness': .25,
                           'reference': 'exterior'})
    doc.add(wall)
    door = Entity('door', {'offset': 2.0, 'width': .9, 'height': 2.1, 'sill': 0.0}, parent_id=wall.id)
    doc.add(door)

    def broken(self, z=None, tolerance=1e-5):
        raise ValueError('topology')
    monkeypatch.setattr(Document, 'active_room_faces', broken)
    with notices.collecting() as found:
        dimension_reference.plan(doc, 0.0)
        dimensions.interior(doc, 0.0)
        joinery._served_side(doc, wall, door, 0.0, 1.0, 0.125)    # the interior-door branch of inside_sign
    assert {i.code for i in found} == {'walls.reference', 'dims.rooms', 'joinery.side'}


def test_mep_says_unreadable_rooms_instead_of_none(monkeypatch):
    from archforge.core.model import Document
    from archforge.mep import heating_layout

    def broken(self, z=None, tolerance=1e-5):
        raise ValueError('topology')
    monkeypatch.setattr(Document, 'active_room_faces', broken)
    with notices.collecting() as found:
        assert heating_layout.heated_rooms(Document(), 0.0) == []
    assert [i.code for i in found] == ['heating.rooms']
