"""HANDOFF 22/10: «OLD VILLA πάνω όροφος χωρίς ετικέτες χώρων» — the owner's upper floor plan writes no room
name; the rooms are told by what is drawn in them (beds, toilet, bath, kitchen words, table), never guessed."""
from archforge.project import drawing_contents as C
from archforge.project.drawing_text import Text


def test_blocks_are_told_by_their_size():
    grey = (0.8, 0.8, 0.8)
    assert C.kind_of(2.0, 1.6, True, grey, True, 4) == "bed"            # the double bed
    assert C.kind_of(1.66, 0.6, True, grey, True, 4) == "bed"           # a bunk
    assert C.kind_of(1.4, 1.0, True, grey, True, 4) == "table"
    assert C.kind_of(0.3, 0.6, False, (0, 0, 0), True, 6) == "toilet"   # the bowl, an outline curve
    assert C.kind_of(0.75, 1.8, False, (0, 0, 0), False, 4) == "bath"
    assert C.kind_of(2.0, 1.6, True, (0.4, 0.4, 0.4), True, 4) is None  # a wall's dark fill is not a bed
    assert C.kind_of(0.5, 2.47, True, grey, True, 4) is None            # a worktop
    assert C.kind_of(0.3, 0.6, False, (0, 0, 0), True, 4) is None       # a door leaf's corner, not a bowl


def test_words_kitchen_and_room_height():
    t = lambda s: Text(s, 1.0, 2.0, 5.0, 0.0)
    assert C.words([t("fridge"), t("COOKTOP"), t("H=2.74m"), t("ENTRANCE"), t("+0.34m [F.L.]")]) == [
        ("kitchen", 1.0, 2.0), ("kitchen", 1.0, 2.0), ("height", 1.0, 2.0)]


def _box(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def test_rooms_named_by_what_they_hold():
    faces = [_box(0, 0, 5, 4),        # bedroom with the double bed
             _box(5, 0, 3, 3),        # bunk room
             _box(0, 4, 3, 1.5),      # bathroom: bath + toilet
             _box(3, 4, 1.2, 1.5),    # WC: toilet only, 1,8 m²
             _box(0, 6, 4, 5),        # kitchen
             _box(4, 6, 6, 5),        # living (room height written, nothing else)
             _box(10, 0, 8, 8),       # a terrace: nothing in it — stays unnamed
             _box(8, 0, 0.5, 0.5)]    # a sliver
    items = [("bed", 2.5, 2.0), ("bed", 6.0, 1.0), ("bed", 7.0, 1.0), ("bath", 1.0, 4.7), ("toilet", 2.5, 5.0),
             ("toilet", 3.6, 4.7), ("kitchen", 1.0, 8.0), ("table", 2.5, 8.0), ("height", 3.0, 9.0),
             ("height", 7.0, 8.0), ("height", 2.0, 2.0)]
    assert C.name_rooms(faces, items) == {0: "MASTER BEDROOM", 1: "BEDROOM", 2: "BATHROOM", 3: "WC", 4: "KITCHEN", 5: "LIVING"}
