from archforge.core.commands import CommandStack
from archforge.core.interaction import WallDrawTransaction, MAGNET
from archforge.core.model import Document
from archforge.ui.hud_text import hud_text


def _draw(doc, stack, a, b):
    t = WallDrawTransaction(doc, stack, a, angle_increment=MAGNET)
    t.update(*b)
    return t, t.commit()


def _open_outline():
    doc = Document(); stack = CommandStack(doc)
    # Started at (-5.4, 6.3): the top wall; then right, bottom — the bottom ends at x = -4.5 (0.9 m short).
    _draw(doc, stack, (-5.4, 6.3), (5.0, 6.3))
    _draw(doc, stack, (5.0, 6.3), (5.0, -6.0))
    _draw(doc, stack, (5.0, -6.0), (-4.5, -6.0))
    return doc, stack


def test_the_open_start_of_the_outline_closes_at_a_right_angle():
    # Owner 24/10: «κρατώντας τη γωνία των 90 μοιρών πήγα να πατήσω στον πρώτο, αλλά αντί να μεγαλώσει εμφανίστηκε
    # ένας καινούριος και μάλιστα σε κλίση» — the right angle is kept, the first wall meets it (was: swung onto it).
    doc, stack = _open_outline()
    top = next(e for e in doc.entities.values() if e.params['y1'] == 6.3 and e.params['y2'] == 6.3)
    t = WallDrawTransaction(doc, stack, (-4.5, -6.0), angle_increment=MAGNET)
    t.outline_start = (-5.4, 6.3)                         # the controller's chain: where this outline began
    t.snap_tol = 0.25                                     # zoomed out (14 px ≈ 25 cm)
    t.update(-4.54, 6.27)                                 # pointer straight up, 0.86 m from the open corner
    assert abs(t.end[0] + 4.5) < 1e-9 and abs(t.end[1] - 6.3) < 1e-9 and t.last_snap.kind == 'endpoint'
    assert t.guide == ((-5.4, 6.3), t.end)
    t.commit()
    assert abs(doc.get(top.id).params['x1'] + 4.5) < 1e-9   # the first wall is shortened to the corner
    assert t.moved_end == ((-5.4, 6.3), t.end)
    stack.undo()
    assert doc.get(top.id).params['x1'] == -5.4           # one undo restores both


def test_aiming_at_the_first_corner_a_few_degrees_off_still_closes_square():
    doc, stack = _open_outline()
    top = next(e for e in doc.entities.values() if e.params['y1'] == 6.3 and e.params['y2'] == 6.3)
    t = WallDrawTransaction(doc, stack, (-4.5, -6.0), angle_increment=MAGNET)
    t.outline_start = (-5.4, 6.3); t.snap_tol = 0.25
    t.update(-5.4, 6.3)                                   # clicked right on the first corner: 4° off the vertical
    assert abs(t.end[0] + 4.5) < 1e-9 and abs(t.end[1] - 6.3) < 1e-9
    t.commit()
    assert abs(doc.get(top.id).params['x1'] + 4.5) < 1e-9


def test_the_first_wall_is_lengthened_to_meet_a_right_angle():
    doc = Document(); stack = CommandStack(doc)
    _draw(doc, stack, (1.2, -1.25), (-5.0, -1.25))        # first wall, drawn short of where the room ends
    _draw(doc, stack, (-5.0, -1.25), (-5.0, 3.0))
    _draw(doc, stack, (-5.0, 3.0), (1.75, 3.0))
    first = next(e for e in doc.entities.values() if e.params['x1'] == 1.2)
    t = WallDrawTransaction(doc, stack, (1.75, 3.0), angle_increment=MAGNET)
    t.outline_start = (1.2, -1.25)
    t.update(1.25, -1.3)                                  # «πήγα να πατήσω στον πρώτο»
    assert abs(t.end[0] - 1.75) < 1e-9 and abs(t.end[1] + 1.25) < 1e-9
    t.commit()
    assert abs(doc.get(first.id).params['x1'] - 1.75) < 1e-9
    assert sum(1 for e in doc.entities.values() if e.kind == 'wall') == 4   # no extra slanted wall


def test_shift_still_closes_onto_the_corner_itself():
    doc, stack = _open_outline()
    t = WallDrawTransaction(doc, stack, (-4.5, -6.0), angle_increment=MAGNET)
    t.outline_start = (-5.4, 6.3); t.angle_enabled = False
    t.update(-4.54, 6.27)
    assert t.end == (-5.4, 6.3)


def test_alignment_guide_shows_where_to_stop_for_right_angles():
    # Owner 24/10 (Home Designer): a guide to the wall opposite shows where to stop for square walls.
    doc = Document(); stack = CommandStack(doc)
    _draw(doc, stack, (-3.3, -1.25), (-5.0, -1.25))
    _draw(doc, stack, (-5.0, -1.25), (-5.0, 3.0))
    _draw(doc, stack, (-5.0, 3.0), (1.75, 3.0))
    first = next(e for e in doc.entities.values() if e.params['x1'] == -3.3)
    t = WallDrawTransaction(doc, stack, (1.75, 3.0), angle_increment=MAGNET)
    t.outline_start = (-3.3, -1.25)
    t.update(1.77, -1.1)                                  # 5 m from the first corner, 15 cm short of its line
    assert t.last_snap.kind == 'alignment' and abs(t.end[1] + 1.25) < 1e-9
    assert t.guide == ((-3.3, -1.25), t.end)
    t.commit()
    assert abs(doc.get(first.id).params['x1'] - 1.75) < 1e-9   # the first wall runs on to the corner
    stack.undo()
    assert doc.get(first.id).params['x1'] == -3.3


def test_closing_onto_the_axis_cuts_the_loose_tail():
    doc, stack = _open_outline()
    top = next(e for e in doc.entities.values() if e.params['y1'] == 6.3 and e.params['y2'] == 6.3)
    t = WallDrawTransaction(doc, stack, (-4.5, -6.0), angle_increment=MAGNET)
    t.FREE_END_CAPTURE = 0.30                             # as if the pointer stayed far from the corner
    t.outline_start = (-5.4, 6.3)                         # closing this outline: the tail is its own open start
    t.update(-4.5, 6.2)
    assert t.last_snap.kind == 'wall_on_axis' and abs(t.end[1] - 6.3) < 1e-9
    t.commit()
    assert abs(doc.get(top.id).params['x1'] + 4.5) < 1e-9   # the 0.9 m tail is cut: a clean corner
    stack.undo()
    assert doc.get(top.id).params['x1'] == -5.4           # one undo restores both


def test_a_connected_end_is_never_cut():
    doc, stack = _open_outline()
    _draw(doc, stack, (-5.4, 6.3), (-5.4, 8.0))           # something continues from the top wall's end
    top = next(e for e in doc.entities.values() if e.params['y1'] == 6.3 and e.params['y2'] == 6.3)
    t = WallDrawTransaction(doc, stack, (-4.5, -6.0), angle_increment=MAGNET)
    t.FREE_END_CAPTURE = 0.30
    t.update(-4.5, 6.2); t.commit()
    assert doc.get(top.id).params['x1'] == -5.4


def test_hud_is_greek():
    text = hud_text({'length': 11.187, 'angle_deg': 90.0, 'x': -4.542, 'y': 6.266, 'z': 0.0, 'angle_locked': 1.0, 'magnet': 90.0})
    assert text.startswith('Μήκος 11,19 m') and 'Γωνία 90,0°' in text and 'μαγνήτης 90°' in text
    assert 'angle' not in text and 'length' not in text


def test_ctrl_turns_the_corner_autosnap_off():
    doc, stack = _open_outline()
    t = WallDrawTransaction(doc, stack, (-4.5, -6.0), angle_increment=MAGNET)
    t.corner_enabled = False                               # what Ctrl sets while moving
    t.update(-4.54, 4.0)
    assert t.last_snap is None or t.last_snap.kind != 'endpoint'
    assert abs(t.end[0] + 4.5) < 1e-9                      # still straight up (magnet 90°)


def test_zoomed_in_a_wall_15_cm_off_the_other_stays_where_it_is_drawn():
    """Owner 24/10: «είναι πολύ συχνό να υπάρχουν τοίχοι με μικρές διαφορές 10, 15, 20 πόντους — δεν είναι όλα σε μία
    ευθεία». The magnets follow the zoom (screen pixels): zoomed in, a 15 cm step is kept; Ctrl keeps it at any zoom."""
    doc = Document(); stack = CommandStack(doc)
    _draw(doc, stack, (0.0, 0.0), (6.0, 0.0))             # a wall whose end is at x = 6
    t = WallDrawTransaction(doc, stack, (6.15, 4.0), angle_increment=MAGNET)
    t.snap_tol = 0.035                                    # zoomed in: 14 px ≈ 3,5 cm
    t.update(6.15, 1.0)                                   # straight down, 15 cm right of that end
    assert abs(t.end[0] - 6.15) < 1e-9 and abs(t.end[1] - 1.0) < 1e-9 and t.last_snap is None
    t.snap_tol = 0.25                                     # zoomed out it lines up (the guide shows it) …
    t.update(6.15, 0.1)
    assert t.last_snap is not None
    t.corner_enabled = False                              # … and Ctrl keeps it where the hand is
    t.update(6.15, 0.1)
    assert abs(t.end[0] - 6.15) < 1e-9 and abs(t.end[1] - 0.1) < 1e-9


def test_another_outlines_free_end_is_never_cut():
    """Owner 25/10 (screenshot, two «Π»): a wall drawn from the outer outline up onto the inner one's bottom wall,
    about 1 m in from its free end — «έκοψε πάνω από ένα μέτρο τοίχο για να ενώσει». Only the open start of the
    outline being drawn may change to close it; any other wall keeps its length (a T, not a corner)."""
    doc = Document(); stack = CommandStack(doc)
    _draw(doc, stack, (3.5, 3.5), (8.8, 3.5))             # inner «Π»: its bottom wall, free end at x = 3.5
    _draw(doc, stack, (8.8, 3.5), (8.8, 7.1))
    _draw(doc, stack, (10.0, 8.5), (10.0, 2.4))           # outer «Π»
    _draw(doc, stack, (10.0, 2.4), (4.5, 2.4))
    inner = next(e for e in doc.entities.values() if e.params['y1'] == 3.5 and e.params['y2'] == 3.5)
    t = WallDrawTransaction(doc, stack, (4.5, 2.4), angle_increment=MAGNET)
    t.outline_start = (10.0, 8.5)                         # this chain began on the outer «Π»
    t.FREE_END_CAPTURE = 0.30
    t.update(4.5, 3.45)                                   # straight up onto the inner wall's axis
    t.commit()
    assert doc.get(inner.id).params['x1'] == 3.5          # nothing cut
