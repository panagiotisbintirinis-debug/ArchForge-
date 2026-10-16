from archforge.core.commands import AddEntity
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.site.survey import (contours, parse_dxf, parse_points, plot_boundary, read_survey_file,
                                   terrain_from_survey, with_boundary)
from archforge.site.terrain import default_terrain_params, terrain_height

DXF = """0\nSECTION\n2\nENTITIES\n0\nPOINT\n8\nPTS\n10\n450100\n20\n4200200\n30\n50.5\n0\nLWPOLYLINE\n8\nΟΡΙΟ\n70\n1
10\n450090\n20\n4200190\n10\n450120\n20\n4200190\n10\n450120\n20\n4200215\n10\n450090\n20\n4200215
0\nLWPOLYLINE\n8\nCONTOURS\n38\n51.0\n70\n0\n10\n450092\n20\n4200205\n10\n450118\n20\n4200207
0\nTEXT\n8\nH\n10\n450110\n20\n4200210\n1\n51,20\n0\nENDSEC\n0\nEOF\n"""


def test_points_files_with_labels_and_greek_decimals():
    pts = parse_points("Σ1 450123,50 4201000,25 102,30\n2;450130.5;4201010;103.1\nX Y Z\n450140,4201000,101.9\n")
    assert pts == [(450123.5, 4201000.25, 102.3), (450130.5, 4201010.0, 103.1), (450140.0, 4201000.0, 101.9)]


def test_dxf_points_contours_heights_and_boundary():
    data = parse_dxf(DXF)
    zs = sorted(p[2] for p in data["points"])
    assert zs == [50.5, 51.0, 51.0, 51.2]
    assert plot_boundary(data["polylines"]) == [(450090, 4200190), (450120, 4200190), (450120, 4200215), (450090, 4200215)]


def _house(doc):
    for a, b in (((0, 0), (10, 0)), ((10, 0), (10, 8)), ((10, 8), (0, 8)), ((0, 8), (0, 0))):
        doc.add(Entity("wall", {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1], "thickness": .25, "height": 3, "level": "Ground"}))


def test_survey_is_placed_around_the_building_and_keeps_absolute_altitude():
    doc = Document(); _house(doc)
    data = parse_dxf(DXF)
    pts = data["points"] + [(450095, 4200195, 50.0), (450115, 4200195, 50.8)]
    p = terrain_from_survey(doc, pts, plot_boundary(data["polylines"]))
    # Plot centred on the building (5, 4); 30 x 25 m with its area intact.
    xs = [q[0] for q in p["boundary"]]; ys = [q[1] for q in p["boundary"]]
    assert (min(xs) + max(xs)) / 2 == 5 and (min(ys) + max(ys)) / 2 == 4
    assert max(xs) - min(xs) == 30 and max(ys) - min(ys) == 25
    # ±0.00 is 15 cm over the ground at the building; absolute = local + altitude_ref.
    assert abs(terrain_height(p, 5, 4) + .15) < 1e-6
    x, y, z = p["points"][0]
    assert any(abs(x + p["geo_origin"][0] - q[0]) < 1e-6 and abs(z + p["altitude_ref"] - q[2]) < 1e-6 for q in pts)
    # Every survey point is honoured exactly.
    for x, y, z in p["points"]:
        assert abs(terrain_height(p, x, y) - z) < 1e-6
    doc.add(Entity("terrain", p, name="Έδαφος"))           # passes validation
    roles = [q.role for q in build_plan_frame(doc).primitives]
    assert "plot-boundary" in roles and "plot-label" in roles and "contour" in roles


def test_contours_of_a_plane_are_straight_and_stepped():
    p = dict(default_terrain_params(Document()), x0=0, y0=0, x1=10, y1=10, elevation=0, slope_x=10, slope_y=0)
    lines = contours(p, step=.25)
    assert sorted({z for z, _ in lines}) == [.25, .5, .75]
    for z, ((ax, _), (bx, _)) in lines:
        assert abs(ax - z * 10) < 1e-6 and abs(bx - z * 10) < 1e-6


def test_hand_drawn_boundary_extends_the_ground():
    doc = Document()
    p = with_boundary(default_terrain_params(doc), [(-40, -5), (30, -5), (30, 20), (-40, 20)])
    assert p["x0"] <= -42 and p["x1"] >= 32
    doc.add(Entity("terrain", p))                           # schema accepts it
    try:
        doc.add(Entity("terrain", dict(p, boundary=[[0, 0], [1, 1]])))
        assert False, "two corners are not a plot"
    except ValueError:
        pass


def test_read_survey_file_dxf_and_csv(tmp_path):
    d = tmp_path / "plot.dxf"; d.write_text(DXF, encoding="utf-8")
    pts, bnd = read_survey_file(str(d))
    assert len(pts) == 4 and len(bnd) == 4
    c = tmp_path / "pts.csv"; c.write_bytes("1;100,0;200,0;10,5\n2;110;200;11\n3;105;210;10\n".encode("cp1253"))
    pts, bnd = read_survey_file(str(c))
    assert pts[0] == (100.0, 200.0, 10.5) and bnd is None
