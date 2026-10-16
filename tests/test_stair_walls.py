"""Owner (2026-10-14): «δεν είναι οπτικά εύκολο να τοποθετήσεις τη σκάλα σε ένα κτίριο που έχει τοίχους».

Walk-through: a drag in a 4 × 2.5 m hall gave a 2.9 m spiral centred on the click, through three walls,
drawn as a plain green square with no warning.  The placement now knows the walls: a candidate that
crosses one is moved into the room it starts in when it fits there, otherwise it is shown red with a
message; the preview shows the steps, not only a box.
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.stairs import (candidate_from_params, stair_wall_conflicts)
from archforge.core.commands import AddEntity, CommandStack, CreateFloorLevel, SetWorkPlane
from archforge.core.interaction import StairPlaceTransaction
from archforge.core.model import Document, Entity


def _wall(stack, x1, y1, x2, y2, z=0.0):
    w = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z, 'height': 2.7, 'thickness': 0.2})
    stack.execute(AddEntity(w))
    return w.id


def _house():
    """10 × 8 ground floor; a 4 × 2.5 hall at x 6–10, y 3–5.5; storey above at +3.00."""
    doc = Document(); stack = CommandStack(doc)
    for a, b in (((0, 0), (10, 0)), ((10, 0), (10, 8)), ((10, 8), (0, 8)), ((0, 8), (0, 0)),
                 ((6, 0), (6, 8)), ((6, 3), (10, 3)), ((6, 5.5), (10, 5.5))):
        _wall(stack, *a, *b)
    import copy
    plane = copy.deepcopy(doc.work_plane)
    stack.execute(CreateFloorLevel('Floor 2', 3.0))
    stack.execute(SetWorkPlane(plane))
    return doc, stack


def _inside(fp, lo, hi):
    return all(lo[0] - 1e-6 <= x <= hi[0] + 1e-6 and lo[1] - 1e-6 <= y <= hi[1] + 1e-6 for x, y in fp)


def test_a_candidate_through_a_wall_is_reported():
    doc, _ = _house()
    tx = StairPlaceTransaction(doc, CommandStack(doc), (1.0, 4.0))
    tx.update(5.5, 4.0)
    c = candidate_from_params(dict(tx.active_candidate.to_params(), x=5.0, y=4.0, layout='straight', angle_deg=0.0))
    assert stair_wall_conflicts(doc, c)              # starts at x=5, runs east through the wall at x=6


def test_drag_in_the_hall_snaps_the_stair_inside_its_walls_or_says_it_does_not_fit():
    from archforge.architecture.stairs import stair_footprint
    doc, stack = _house()
    tx = StairPlaceTransaction(doc, stack, (6.6, 4.25))
    tx.update(9.6, 4.25)
    pv = tx.preview
    c = tx.active_candidate
    if pv['fits']:
        assert not stair_wall_conflicts(doc, c)
        assert _inside(stair_footprint(c), (6.1, 3.1), (9.9, 5.4))
    else:
        assert any('τοίχο' in s for s in pv['suggestions'])


def test_in_a_big_room_the_chosen_stair_is_moved_off_the_wall_it_was_started_against():
    from archforge.architecture.stairs import stair_footprint
    doc, stack = _house()
    tx = StairPlaceTransaction(doc, stack, (0.3, 4.0), layout='spiral')      # click 30 cm from the west wall
    tx.update(3.0, 4.0)
    c = tx.active_candidate
    assert c.layout == 'spiral' and tx.preview['fits']
    assert not stair_wall_conflicts(doc, c)
    assert _inside(stair_footprint(c), (0.1, 0.1), (5.9, 7.9))


def test_a_stair_that_cannot_fit_is_red_with_a_message():
    doc, stack = _house()
    _wall(stack, 6, 4.0, 10, 4.0)                    # hall cut to 1 m deep: nothing fits there
    tx = StairPlaceTransaction(doc, stack, (6.6, 3.5), layout='straight')
    tx.update(9.6, 3.5)
    assert tx.preview['fits'] is False
    assert any('τοίχο' in s for s in tx.preview['suggestions'])


def test_preview_in_the_plan_shows_the_steps_and_is_red_when_it_does_not_fit():
    from archforge.core.plan_scene import build_plan_frame
    from archforge.core.viewport import PreviewState
    doc, stack = _house()
    tx = StairPlaceTransaction(doc, stack, (1.0, 4.0), layout='straight')
    tx.update(5.0, 4.0)
    prims = build_plan_frame(doc, PreviewState('stair', tx.preview, {}, None)).primitives
    roles = [p.role for p in prims if p.role == 'preview']
    assert len(roles) > 2                            # outline + treads / walking line, not only a box
    box = next(p for p in prims if p.role == 'preview' and dict(p.meta).get('semantic') == 'stair-preview')
    assert dict(box.meta)['fits'] is tx.preview['fits']


def test_label_next_to_the_mouse_names_the_stair_and_warns_in_red():
    from archforge.core.viewport import PreviewState
    from archforge.ui.plan_overlay import stair_text
    doc, stack = _house()
    _wall(stack, 6, 4.0, 10, 4.0)
    tx = StairPlaceTransaction(doc, stack, (6.6, 3.5), layout='straight')
    tx.update(9.6, 3.5)
    text, fits = stair_text(PreviewState('stair', tx.preview, {}, None))
    assert not fits and text.startswith('⚠') and 'Ευθεία' in text and 'πάτημα' in text
    tx = StairPlaceTransaction(doc, stack, (1.0, 4.0))          # automatic: the first offered one fits
    tx.update(5.0, 4.0)
    text, fits = stair_text(PreviewState('stair', tx.preview, {}, None))
    assert fits and '⚠' not in text


def test_an_upper_wall_over_the_low_steps_is_fine_over_the_opening_it_is_not():
    """Owner 14/10: the slab stays where there is headroom, and the upper storey uses that space."""
    from archforge.architecture.stairs import stair_opening_polygons
    doc, stack = _house()
    tx = StairPlaceTransaction(doc, stack, (3.0, 0.8), layout='straight')        # along the 8 m of the living room
    tx.update(3.0, 6.5)
    c = tx.active_candidate
    assert not stair_wall_conflicts(doc, c)
    ys = [q[1] for poly in stair_opening_polygons(c) for q in poly]
    start, top = c.origin[1], min(ys)                  # the opening begins at «top»
    low = _wall(stack, 1.0, (start + top) / 2, 5.0, (start + top) / 2, z=3.0)       # over the low steps
    assert low not in stair_wall_conflicts(doc, c)
    high = _wall(stack, 1.0, max(ys) - 0.3, 5.0, max(ys) - 0.3, z=3.0)              # over the opening
    assert high in stair_wall_conflicts(doc, c)


def test_message_after_placing_says_whether_it_crosses_a_wall():
    from archforge.core.viewport import PointerController, PointerEvent
    doc, stack = _house()
    c = PointerController(doc, stack); c.set_tool('stair')
    c.pointer_down(PointerEvent(3.0, 0.8)); c.pointer_move(PointerEvent(3.0, 6.5)); c.pointer_up(PointerEvent(3.0, 6.5))
    assert c.last_warning.startswith('Σκάλα: μπήκε μέσα στους τοίχους')
    _wall(stack, 6, 4.0, 10, 4.0)
    c.stair_layout = 'straight'
    c.pointer_down(PointerEvent(6.6, 3.5)); c.pointer_move(PointerEvent(9.6, 3.5)); c.pointer_up(PointerEvent(9.6, 3.5))
    assert c.last_warning.startswith('⚠')
