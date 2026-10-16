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


def test_the_open_start_of_the_outline_pulls_the_last_wall_to_it():
    doc, stack = _open_outline()
    t = WallDrawTransaction(doc, stack, (-4.5, -6.0), angle_increment=MAGNET)
    t.update(-4.54, 6.27)                                 # pointer straight up, 0.86 m from the open corner
    assert t.end == (-5.4, 6.3) and t.last_snap.kind == 'endpoint'


def test_closing_onto_the_axis_cuts_the_loose_tail():
    doc, stack = _open_outline()
    top = next(e for e in doc.entities.values() if e.params['y1'] == 6.3 and e.params['y2'] == 6.3)
    t = WallDrawTransaction(doc, stack, (-4.5, -6.0), angle_increment=MAGNET)
    t.FREE_END_CAPTURE = 0.30                             # as if the pointer stayed far from the corner
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
