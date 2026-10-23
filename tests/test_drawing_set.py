"""Owner 22/10: «να βρεις τις συσχετίσεις ανά τα PDF … πάνω από δύο PDF σε σειρά … να συγχωνευτούν παραμετρικά».

Sheets are classified from title / file name and related by what they write in the same place (levels, section
marks) — scale, turn and place at once — or, same building and scale, by their walls."""
import math

import pytest

from archforge.project import drawing_set as D
from archforge.project.drawing_text import Text


def test_sheets_are_told_apart_by_title_and_file_name():
    t = lambda s, size=16.0: Text(s, 0, 0, size, 0)
    assert D.classify("x/GROUND.pdf", [t("GROUND FLOOR PLAN NEW VILLA/"), t("6.00", 8)])[1:] == ("plan", "NEW VILLA", "ground")
    assert D.classify("x/df09_NEW_VILLA_SECTION_-comments.pdf", [t("SECTION NEW VILLA")])[1:3] == ("section", "NEW VILLA")
    assert D.classify("x/c9d6904f-OLD_VILLA_PLAN_LOWER_-comments.pdf", [t("LOWER FLOOR PLAN")])[1:] == ("plan", "OLD VILLA", "lower")
    assert D.classify("x/MASTERPLAN_-comments.pdf", [t("MASTERPLAN")])[1] == "site"


def _turned(points, scale, turn, shift):
    c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
    return [(k, scale * (c * x - s * y) + shift[0], scale * (s * x + c * y) + shift[1]) for k, x, y in points]


def test_shared_levels_give_scale_turn_and_place():
    plan = [("L+114.00", 2, 3), ("L+114.00", 9, 3), ("L+113.30", 4, -6), ("L+112.80", 1, -9), ("MT.01", 6, 12), ("L+120.00", 30, 30)]
    site = _turned(plan[:5], 0.5, 90.0, (100.0, 40.0)) + [("L+114.00", 0.0, 0.0), ("L+137.10", 5, 5)]   # decoys
    sim = D.relate_by_anchors(plan, site)
    assert sim.scale == pytest.approx(0.5) and sim.turn == pytest.approx(90.0) and sim.inliers == 5
    assert sim.apply((2, 3)) == pytest.approx((98.5, 41.0))
    assert D.relate_by_anchors(plan, site, same_scale=True) is None          # a known scale is not overruled
    assert D.relate_by_anchors(plan[:2], site) is None                      # fewer than three: no guess


def test_same_building_floors_by_their_walls():
    outline = [(0, 0, 12, 0), (12, 0, 12, 8), (12, 8, 0, 8), (0, 8, 0, 0), (5, 0, 5, 8), (0, 4, 5, 4)]
    lower = [(a + 3.25, b - 1.5, c + 3.25, d - 1.5) for a, b, c, d in outline] + [(40, 40, 41, 40)]
    sim = D.relate_by_walls(outline, lower, min_votes=6)
    assert sim.shift == pytest.approx((3.25, -1.5))


def test_the_whole_set_lands_in_the_site_frame():
    site = D.Sheet("site.pdf", kind="site", scale=100, anchors=[("L+114.00", 50, 20), ("L+113.30", 52, 15), ("L+112.80", 49, 12),
                                                                 ("L+137.10", 10, 80), ("L+137.60", 18, 82), ("L+132.00", 12, 70)])
    new = D.Sheet("new.pdf", kind="plan", building="NEW VILLA", scale=50,
                  anchors=[("L+114.00", 5, 5), ("L+113.30", 7, 0), ("L+112.80", 4, -3)])
    old = D.Sheet("old.pdf", kind="plan", building="OLD VILLA", scale=50,
                  anchors=[("L+137.10", 0, 10), ("L+137.60", 8, 12), ("L+132.00", 2, 0)])
    section = D.Sheet("s.pdf", kind="section", building="NEW VILLA", scale=50)
    placed = D.relate([new, site, old, section])
    assert placed[1][1] == "αναφορά" and 3 not in placed
    assert placed[0][0].apply((5, 5)) == pytest.approx((50, 20)) and placed[2][0].apply((2, 0)) == pytest.approx((12, 70))


def test_storeys_from_the_levels_each_building_writes():
    from archforge.ui.drawing_set_import import default_reference, plan_storeys
    upper = D.Sheet("old_upper.pdf", kind="plan", building="OLD VILLA", floor="upper", scale=50,
                    anchors=[("L+0.00", 10, 10), ("L+131.80", 10.4, 10.2), ("L+0.00", 12, 9), ("L+137.10", 30, 30), ("L+137.10", 31, 30)])
    lower = D.Sheet("old_lower.pdf", kind="plan", building="OLD VILLA", floor="lower", scale=50,
                    anchors=[("L-2.80", 1, 1), ("L-2.80", 3, 1), ("L-3.45", 5, 5)])
    ground = D.Sheet("new.pdf", kind="plan", building="NEW VILLA", floor="ground", scale=50,
                     anchors=[("L+114.00", 1, 1), ("L+114.00", 2, 2), ("L+113.30", 9, 9)])
    pool = D.Sheet("pool.pdf", kind="plan", building="NEW VILLA", scale=50, anchors=[("L+114.00", 1, 1)])
    sheets = [upper, lower, ground, pool]
    assert D.building_zero(sheets[:2]) == 131.8                     # «+131.80» written 45 cm from «±0.00»
    assert D.floor_altitude(lower, 131.8) == 129.0 and D.floor_altitude(ground) == 114.0
    placed = {i: None for i in range(4)}
    probe = plan_storeys(sheets, placed, 0.0)
    assert default_reference(sheets, probe) == 114.0                # ±0,00 = the ground floor
    st = plan_storeys(sheets, placed, 114.0)
    assert st[2][1] == 0.0 and st[0][1] == pytest.approx(17.8) and st[1][1] == pytest.approx(15.0)
    assert st[3][0] == st[2][0]                                     # the pool sheet shares the ground storey


def test_a_floor_with_only_relative_levels_lands_by_its_walls_on_the_site_plan():
    """OLD VILLA lower floor without its upper floor sheet: only «−2.80 / −3.45» (relative) — one shared value
    with the masterplan, too few for anchors; its walls are on the masterplan and the shared level confirms
    the shift.  The ±0,00 comes from the masterplan's «−2.80» written beside «+129.00»."""
    from archforge.ui.drawing_set_import import plan_storeys
    outline = [(0, 0, 12, 0), (12, 0, 12, 8), (12, 8, 0, 8), (0, 8, 0, 0), (5, 0, 5, 8), (0, 4, 5, 4), (5, 6, 12, 6),
               (8.3, 0, 8.3, 6), (1.7, 4, 1.7, 8), (5, 2.2, 8.3, 2.2), (9.4, 6, 9.4, 8)]
    shift = (20.0, 60.0)
    clutter = [(x, 0, x, 50) for x in range(0, 60, 7)] + [(0, y, 60, y) for y in range(0, 90, 9)]
    on_site = [(a + shift[0], b + shift[1], c + shift[0], d + shift[1]) for a, b, c, d in outline]
    lower = D.Sheet("old_lower.pdf", kind="plan", building="OLD VILLA", floor="lower", scale=50, segments=outline,
                    anchors=[("L-2.80", 2, 2), ("L-3.45", 9, 3)])
    site = D.Sheet("site.pdf", kind="site", scale=100, segments=clutter + on_site * 3,
                   anchors=[("L-2.80", 22.4, 62.3), ("L+129.00", 22.3, 62.0), ("L+114.00", 50, 20),
                            ("L+113.30", 52, 15), ("L+112.80", 49, 12)])
    placed = D.relate([site, lower])
    assert placed[1][0].shift == pytest.approx(shift) and "γενική" in placed[1][1]
    assert plan_storeys([site, lower], placed, 114.0)[1][1:] == (15.0, 129.0)
    # Without a level to confirm it, the strongest shift is not taken on trust.
    lower.anchors = [("L-3.45", 9, 3)]
    assert 1 not in D.relate([site, lower])


def _rooms(doc, stack, z, height=3.0):
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    ids = []
    for s in [(0, 0, 10, 0), (10, 0, 10, 8), (10, 8, 0, 8), (0, 8, 0, 0), (5, 0, 5, 8)]:
        e = Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': z, 'height': height, 'thickness': 0.25})
        stack.execute(AddEntity(e)); ids.append(e.id)
    return ids


def test_roof_slabs_from_the_section_and_from_the_buildings_zero():
    """NEW VILLA: the section says underside 3,40 and 20 cm — walls go up to it, the slab sits there.  OLD VILLA
    lower floor (+129,00) under its ±0,00 (+131,80): closed by 20 cm whose top is ±0,00 — but a wall never
    goes lower than the door in it."""
    from types import SimpleNamespace
    from archforge.core.commands import AddEntity, CommandStack
    from archforge.core.model import Document, Entity
    from archforge.ui.drawing_set_import import add_roof_slabs
    doc = Document(); stack = CommandStack(doc)
    doc.levels.update({"New": 0.0, "Old": 15.0})
    new = _rooms(doc, stack, 0.0)
    old = _rooms(doc, stack, 15.0)
    stack.execute(AddEntity(Entity('door', {'offset': 2.0, 'width': 0.9, 'height': 2.7, 'sill': 0.0}, parent_id=old[0])))
    sheets = [D.Sheet("new.pdf", building="NEW VILLA"), D.Sheet("old.pdf", building="OLD VILLA")]
    storeys = {0: ("New", 0.0, 114.0), 1: ("Old", 15.0, 129.0)}
    sections = {9: {"building": "NEW VILLA", "slab": {"bottom": 3.4, "top": 3.6, "thickness": 0.2, "ceiling": 2.9}}}
    made = add_roof_slabs(SimpleNamespace(doc=doc, stack=stack), sheets, storeys, sections,
                          {"NEW VILLA": None, "OLD VILLA": 131.8}, 114.0)
    assert [(n, how) for n, _id, how in made] == [("New", "τομή"), ("Old", "±0,00 του κτιρίου")]
    roofs = {e.params["level_z"]: e.params for e in doc.entities.values() if e.kind == "room_roof"}
    assert roofs[0.0]["offset_z"] == pytest.approx(3.4) and roofs[0.0]["thickness"] == 0.2
    assert roofs[15.0]["offset_z"] + roofs[15.0]["thickness"] == pytest.approx(2.8)
    assert {doc.get(i).params["height"] for i in new} == {3.4}
    assert doc.get(old[0]).params["height"] == pytest.approx(2.7)                  # the door's head
    assert [doc.get(i).params["height"] for i in old[1:]] == pytest.approx([2.6] * 4)
    assert len(stack.done) >= 1


def test_a_floor_of_the_same_building_places_it_before_the_site_plans_walls():
    """With the OLD VILLA upper floor in the set, the lower floor lands on the upper floor's walls (exact), not
    on the masterplan's (0,4 m off at 1:100)."""
    outline = [(0, 0, 12, 0), (12, 0, 12, 8), (12, 8, 0, 8), (0, 8, 0, 0), (5, 0, 5, 8), (0, 4, 5, 4), (5, 6, 12, 6),
               (8.3, 0, 8.3, 6), (1.7, 4, 1.7, 8), (5, 2.2, 8.3, 2.2), (9.4, 6, 9.4, 8)]
    move = lambda segs, dx, dy: [(a + dx, b + dy, c + dx, d + dy) for a, b, c, d in segs]
    site = D.Sheet("site.pdf", kind="site", scale=100, segments=move(outline, 20.4, 60.0) * 3,
                   anchors=[("L-2.80", 22.4, 62.3), ("L+129.00", 22.3, 62.0), ("L+137.10", 10, 80),
                            ("L+137.60", 18, 82), ("L+132.00", 12, 70)])
    upper = D.Sheet("old_upper.pdf", kind="plan", building="OLD VILLA", floor="upper", scale=50,
                    segments=move(outline, 3.0, 1.0),
                    anchors=[("L+137.10", 0, 10), ("L+137.60", 8, 12), ("L+132.00", 2, 0)])
    lower = D.Sheet("old_lower.pdf", kind="plan", building="OLD VILLA", floor="lower", scale=50, segments=outline,
                    anchors=[("L-2.80", 2, 2)])
    placed = D.relate([site, lower, upper])
    assert placed[1][1].startswith("τοίχοι (")                              # on the upper floor's walls
    assert placed[1][0].apply((0, 0)) == pytest.approx((13.0, 71.0))       # upper (3, 1) → site (13, 71)


def test_terrace_levels_of_the_set_relative_ones_by_the_buildings_zero():
    """The F.L. the set writes outdoors become terrain levels; «−1.20m» near the OLD VILLA counts as +130,60 (its
    ±0,00 +131,80); a ceiling level does not count; the same level on two sheets counts once."""
    from archforge.core.model import Document
    from archforge.ui.drawing_set_import import site_levels
    same = D.Similarity(1.0, 0.0, (0.0, 0.0), 0, 0.0)
    site = D.Sheet("site.pdf", kind="site", scale=100,
                   anchors=[("L+137.10", 10, 80), ("L-1.20", 12, 70), ("L-0.95C", 14, 70), ("L+114.00", 50, 20)])
    upper = D.Sheet("old_upper.pdf", kind="plan", building="OLD VILLA", scale=50,
                    anchors=[("L+137.10", 10.2, 80.1), ("L+132.00", 12, 72)])
    levels = site_levels(Document(), [site, upper], {0: (same, ""), 1: (same, "")}, 114.0, {"OLD VILLA": 131.8})
    assert sorted(z for _x, _y, z in levels) == pytest.approx([0.0, 16.6, 18.0, 23.1])


def test_a_pool_rim_from_the_levels_written_inside_it():
    """Owner 23/10: the OLD VILLA pool hung 2,55 m low (at the terrace's +129,10 beside it).  Inside it the drawing
    writes its bottom «−1.65m [C.L.]» and «pool's depth 1.50m»: the rim is −0,15 = +131,65."""
    from archforge.ui.drawing_set_import import rim_level
    same = D.Similarity(1.0, 0.0, (0.0, 0.0), 0, 0.0)
    upper = D.Sheet("old_upper.pdf", kind="plan", building="OLD VILLA", scale=50,
                    anchors=[("L-1.65C", 2.0, 1.0), ("L-1.05", 4.0, 2.5), ("L+129.10", 3.0, -2.0)])   # last: outside
    outline = [(0, 0), (5, 0), (5, 3), (0, 3)]
    assert rim_level([upper], {0: (same, "")}, [0], outline, {"OLD VILLA": 131.8}, 1.5) == pytest.approx(131.65)
    assert rim_level([upper], {0: (same, "")}, [0], outline, {}, 1.5) is None              # ±0,00 unknown: no guess
