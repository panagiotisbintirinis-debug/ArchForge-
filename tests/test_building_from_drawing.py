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
