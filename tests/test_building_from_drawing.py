"""Owner 22/10: «το PDF είναι συνολικό σχέδιο … εισαγωγή δύο-τριών PDF … ένα σχέδιο 3Δ που να μπορούμε να
δουλέψουμε· το terrain … πρέπει να αποτυπωθεί»; «η κλίμακα μπορεί να βγει από τις διαστάσεις».

What the drawing writes (scale, levels, rooms, «w: … | h: …»), openings into the wall gaps, the scale from the
dimensions, a masterplan matched with two point pairs, the ground from the written altitudes."""
import math

import pytest

from archforge.architecture.building_from_drawing import host_of, place_openings
from archforge.project import drawing_text as T
from archforge.project import underlay as U


def _t(text, x=0.0, y=0.0, size=6.0, angle=0.0):
    return T.Text(text, x, y, size, angle)


def test_what_the_drawing_writes():
    texts = [_t("SCALE 1:50"), _t("+114.00m [F.L.]", 10, 10), _t("-1.65m [C.L.]", 20, 20), _t("126.00m", 30, 30),
             _t("h:2.42m"), _t("BEDROOM", 100, 106), _t("9.60 sq.m.", 100, 100), _t("w: 0.90 | h: 2.30", 5, 5, angle=90),
             _t("w: 0.60| s: 1.20| h: 1.00", 7, 7)]
    assert T.scale(texts) == 50
    lv = T.levels(texts)
    assert [(l.value, l.ceiling) for l in lv] == [(114.0, False), (-1.65, True), (126.0, False)]   # «h:2.42m» is a height
    (room,) = T.rooms(texts)
    assert (room.name, room.area) == ("BEDROOM", 9.6) and T.greek_room(room.name) == ("Υπνοδωμάτιο", "Υπνοδωμάτιο")
    door, window = T.openings(texts)
    assert (door.kind, door.width, door.height, door.angle) == ("door", 0.9, 2.3, 90)
    assert (window.kind, window.sill, window.height) == ("window", 1.2, 1.0)
    assert T.greek_room("MASTER BEDROOM")[0] == "Κύριο υπνοδωμάτιο" and T.greek_room("w.c.")[1] == "WC"


def test_scale_from_the_dimensions():
    pt_per_m = 1000 / 50 / 25.4 * 72                         # 1:50 → one metre is 56,69 pt on paper
    segs, texts = [], []
    for k, metres in enumerate((6.00, 3.60, 1.60, 12.60)):
        y = 100.0 + 40 * k
        segs.append((0.0, y, metres * pt_per_m, y))
        texts.append(_t(f"{metres:.2f}", metres * pt_per_m / 2, y + 4, size=8.0))
    texts.append(_t("0.30", 999, 999))                       # no line under it: no vote
    assert T.scale_from_dimensions(texts, segs) == (50, 4)
    assert T.scale_from_dimensions(texts[:2], segs) == (None, 2)  # fewer than three agree: ask


def test_openings_go_into_the_gap_their_label_names():
    # One wall line broken at a 0,95 gap (door 0,90 + frame) and at a 1,30 gap (window), 0,30 thick.
    walls = [((0, 0), (2, 0), 0.30), ((2.95, 0), (5, 0), 0.30), ((6.3, 0), (9, 0), 0.30), ((0, 0), (0, 4), 0.30)]
    door = T.OpeningLabel(0.90, 2.30, 2.4, 0.9, 90.0)              # written along the open leaf, beside the gap
    window = T.OpeningLabel(1.30, 1.30, 5.6, -0.6, 0.0, sill=0.90)
    far = T.OpeningLabel(0.80, 2.10, 30.0, 30.0, 0.0)
    merged, placed, missing = place_openings(walls, [door, window, far])
    assert missing == [far] and len(placed) == 2 and len(merged) == 2
    (line,) = [w for w in merged if w[0][1] == w[1][1]]
    assert math.dist(line[0], line[1]) == pytest.approx(9.0)        # the three pieces are one wall now
    by_kind = {o.kind: o for o in placed}
    assert by_kind["door"].centre == pytest.approx((2.475, 0.0)) and by_kind["window"].sill == 0.90
    k, offset = host_of(merged, by_kind["window"].centre)
    assert merged[k] is line and offset == pytest.approx(5.65)


def test_two_point_match_scales_turns_and_places():
    p = U.dxf_params("site.dxf", "\n".join(["0", "SECTION", "2", "ENTITIES", "0", "LINE", "8", "0", "10", "0", "20", "0",
                                             "11", "10", "21", "0", "0", "ENDSEC", "0", "EOF", ""]), "m")
    a, b = U.to_model(p, 0, 0), U.to_model(p, 10, 0)
    p.update(U.aligned(p, a, (5.0, 5.0), b, (5.0, 25.0)))       # twice as long, turned 90°, starting at (5, 5)
    assert U.to_model(p, 0, 0) == pytest.approx((5.0, 5.0)) and U.to_model(p, 10, 0) == pytest.approx((5.0, 25.0))
    assert p["rotation"] == pytest.approx(90.0) and p["m_per_unit"] == pytest.approx(2.0)


def test_ground_from_written_altitudes_in_place():
    from archforge.core.model import Document
    from archforge.site.survey import terrain_from_survey
    from archforge.site.terrain import terrain_height
    from archforge.ui.building_from_underlay import ground_points
    levels = [T.Level(v, False, x, y) for v, x, y in ((114.0, 0, 0), (120.0, 0, 30), (126.0, 0, 60), (114.0, 20, 0))]
    levels += [T.Level(-1.2, False, 5, 5), T.Level(137.0, True, 9, 9)]   # a building's relative level, a ceiling
    pts = ground_points(levels)
    assert len(pts) == 4
    params = terrain_from_survey(Document(), pts, in_place=True, altitude_ref=114.0)
    assert params["altitude_ref"] == 114.0
    assert terrain_height(params, 0, 0) == pytest.approx(0.0, abs=0.3)    # ±0,00 = +114,00 where it is written
    assert terrain_height(params, 0, 60) == pytest.approx(12.0, abs=0.5)  # the slope stays where the drawing puts it


def test_patterned_core_beats_the_nearest_lining_line():
    from archforge.architecture.walls_from_lines import find_walls
    # Concrete 0,30 (faces y = 0 and 0,30, aggregate dots between) with a lining line 0,10 inside (y = −0,10).
    segs = [(0, 0.0, 5, 0.0), (0, 0.30, 5, 0.30), (0, -0.10, 5, -0.10)]
    segs += [(0.1 + 0.015 * i, 0.05 + 0.04 * (i % 6), 0.1 + 0.015 * i + 0.01, 0.05 + 0.04 * (i % 6)) for i in range(300)]
    (wall,) = [w for w in find_walls(segs) if w[2] > 0.2]
    assert wall[2] == pytest.approx(0.30) and wall[0][1] == pytest.approx(0.15)          # the core's axis
    without = find_walls(segs[:3])                                                         # no pattern: nearest pair
    assert min(w[2] for w in without) == pytest.approx(0.10)


def test_tidy_closes_rooms_drawn_in_pieces():
    """Owner 22/10 «συνέχισε μέχρι να κλείνουν και οι 8 χώροι»: a concrete wall read as overlapping pieces, a door
    between a wall's end and the wall across, a furniture outline on its own — tidied, the two rooms close."""
    from archforge.architecture.building_from_drawing import tidy
    from archforge.architecture.topology import room_faces
    from archforge.core.commands import AddEntities, CommandStack
    from archforge.core.model import Document, Entity
    walls = [((0, 0), (8, 0), 0.30), ((8, 0), (8, 5), 0.30), ((0, 5), (8, 5), 0.30), ((0, 0), (0, 5), 0.30),
             ((0, 5.06), (5, 5.06), 0.36),                      # the same wall again, 6 cm off: one body
             ((4, 0), (4, 4.0), 0.10),                          # partition stopping 0,85 short of the top wall: a door
             ((1.5, 1.5), (2.5, 1.5), 0.20), ((2.5, 1.5), (2.5, 2.2), 0.20), ((2.5, 2.2), (1.5, 2.2), 0.20)]   # a sofa
    door = T.OpeningLabel(0.80, 2.10, 4.3, 4.4, 90.0)
    out, openings, missing = tidy(walls, [door])
    assert not missing and [o.kind for o in openings].count("door") == 1
    assert not any(abs(a[0] - 1.5) < 1e-6 or abs(b[0] - 1.5) < 1e-6 for a, b, _t in out)        # the sofa is gone
    doc = Document(); st = CommandStack(doc)
    st.execute(AddEntities([Entity("wall", {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1], "z": 0.0, "height": 3.0,
                                            "thickness": t}) for a, b, t in out]))
    assert len(room_faces(doc, z=0.0)) == 2


def test_pools_from_water_fills_finest_sheet_and_no_glass():
    from archforge.project import drawing_set as D
    rect = lambda cx, cy, L, W: [(cx - L / 2, cy - W / 2), (cx + L / 2, cy - W / 2), (cx + L / 2, cy + W / 2), (cx - L / 2, cy + W / 2)]
    pool_sheet = D.Sheet("pool.pdf", kind="plan", building="NEW VILLA", scale=50, water=[rect(10, 5, 8.0, 3.0)])
    plan = D.Sheet("plan.pdf", kind="plan", building="NEW VILLA", scale=50,
                   water=[rect(10, 5.3, 8.0, 3.6), rect(10, 15, 9.0, 0.05)])           # pool with its channel; glazing
    site = D.Sheet("site.pdf", kind="site", scale=100, water=[rect(10.05, 5.0, 8.1, 3.1)])
    same = D.Similarity(1.0, 0.0, (0.0, 0.0), 0, 0.0)
    found = D.pools([pool_sheet, plan, site], {0: (same, ""), 1: (same, ""), 2: (same, "")})
    (cx, cy, length, width, _rot, idx, shape), = found
    assert shape is None                                                   # a rectangle stays a rectangle
    assert (length, width) == pytest.approx((8.0, 3.0)) and (cx, cy) == pytest.approx((10, 5)) and idx == [0, 1, 2]
    assert D.platform([(0, 0), (4, 0), (4, 2), (0, 2)], grow=0.5) is not None


def test_bands_made_by_reaching_are_merged_too(monkeypatch):
    """OLD VILLA upper floor: the kitchen's wall came out of «reach from free ends» as two bands 18 cm apart
    (72,08 / 72,26) — side by side they never meet in the room graph and the kitchen stayed open."""
    from archforge.architecture import building_from_drawing as B
    band = [((8.27, 72.08), (15.66, 72.08), 0.319), ((14.64, 72.26), (24.11, 72.26), 0.501)]
    monkeypatch.setattr(B, "reach_from_free_ends", lambda walls: (band, []))
    walls, _openings, _missing = B.tidy([((0, 0), (1, 0), 0.3)], [])
    assert len(walls) == 1
    (a, b, t), = walls
    assert min(a[0], b[0]) == pytest.approx(8.27) and max(a[0], b[0]) == pytest.approx(24.11) and t == pytest.approx(0.59)


def test_a_pool_drawn_as_a_rectangle_and_a_fan_keeps_its_shape():
    """OLD VILLA upper floor: the pool's water is a rectangle and a spa with a round end drawn as a fan of thin
    triangles — each thinner than a glazing line, so it must be taken whole for the shape."""
    import math
    from archforge.project import drawing_set as D
    rect = [(0, 0), (7.3, 0), (7.3, 3.9), (0, 3.9)]
    tab = [(5.4, 3.9), (7.3, 3.9), (7.3, 5.0), (5.4, 5.0)]
    fan = [[(6.35, 5.0), (6.35 + 0.95 * math.cos(math.radians(a)), 5.0 + 0.95 * math.sin(math.radians(a))),
            (6.35 + 0.95 * math.cos(math.radians(a + 6)), 5.0 + 0.95 * math.sin(math.radians(a + 6)))] for a in range(0, 180, 6)]
    sheet = D.Sheet("upper.pdf", kind="plan", building="OLD VILLA", scale=50, water=[rect, tab] + fan)
    same = D.Similarity(1.0, 0.0, (0.0, 0.0), 0, 0.0)
    (cx, cy, length, width, _rot, _idx, shape), = D.pools([sheet], {0: (same, "")})
    assert {round(length, 2), round(width, 2)} == {7.3, 5.95}                  # rectangle + spa with its round end
    assert shape and 8 <= len(shape) <= 30                                     # the arc kept within 2 cm, not 30 slivers
    area = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(shape, shape[1:] + shape[:1]))) / 2
    assert area == pytest.approx(7.3 * 3.9 + 1.9 * 1.1 + math.pi * 0.95 ** 2 / 2, rel=0.01)


def test_glass_on_a_wall_is_cut_out_and_told_by_what_is_beside_it():
    """Owner 23/10: «τα γυάλινα κάγκελα στη βεράντα είναι τοίχοι, και μπροστά και στην πλαϊνή».  A wall the drawing
    joined with the glass beside it is cut where the glass is; glass by a room is glazing, glass between two
    outdoor grounds is a railing; the rest stays wall."""
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from archforge.architecture.building_from_drawing import glass_spans
    strips = [((2.0, 0.0), (8.0, 0.0)), ((8.2, 0.0), (9.0, 0.0)), ((0.0, 5.0), (3.0, 5.0)), ((5, 5.5), (5, 9))]  # last: across
    assert glass_spans((0.0, 0.0), (12.0, 0.0), 0.3, strips) == [(2.0, 9.0)]              # a post between panes is glass
    assert glass_spans((0.0, 2.0), (12.0, 2.0), 0.3, strips) == []                          # 2 m away: not on it

    from PySide6.QtWidgets import QApplication
    from archforge.core.commands import AddEntities
    from archforge.core.model import Entity
    from archforge.ui.main_window import MainWindow
    from archforge.ui.building_from_underlay import glass_walls
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        # A room 0–6 × 0–4 (bedroom); a veranda wall in front of it along y = −3 from x = −2 to 10, glass from 0 to 6.
        walls = [Entity('wall', {'x1': a, 'y1': b, 'x2': c, 'y2': d, 'z': 0.0, 'height': 3.0, 'thickness': 0.2})
                 for a, b, c, d in [(0, 0, 6, 0), (6, 0, 6, 4), (6, 4, 0, 4), (0, 4, 0, 0), (-2, -3, 10, -3)]]
        w.stack.execute(AddEntities(walls))
        face = next(f for f in w.doc.active_room_faces(z=0.0))
        w.doc.set_room_metadata(face.signature, name='Υπνοδωμάτιο', use='Υπνοδωμάτιο')
        glass = [((0.0, -3.0), (6.0, -3.0)), ((1.0, 4.0), (5.0, 4.0))]                     # railing; glazing of the room
        glazed, rails = glass_walls(w, walls, glass, 0.0)
        assert len(rails) == 1 and len(glazed) == 1
        rail = w.doc.get(rails[0])
        assert rail.params['railing_type'] == 'glass_channel' and rail.params['points'] == [[0.0, -3.0], [6.0, -3.0]]
        front = sorted(round(min(e.params['x1'], e.params['x2']), 2) for e in w.doc.entities.values()
                       if e.kind == 'wall' and abs(e.params['y1'] + 3) < 1e-6)
        assert front == [-2.0, 6.0]                                                        # the masonry either side stays
        pane = next(e for e in w.doc.entities.values() if e.kind == 'window')
        assert w.doc.get(pane.parent_id).params['y1'] == 4.0 and pane.params['width'] == pytest.approx(3.9)
        assert len(w.doc.active_room_faces(z=0.0)) == 1                                    # the room still closes
    finally:
        w._mark_clean(); w.close(); app.processEvents()
