"""Pointing the assistant at one thing: marker → target → actions; typed requests matched to them."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.assistant.suggestions import Proposal, apply
from archforge.assistant.target import actions_for, match, target_at
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity


def _house(stack):
    for x1, y1, x2, y2 in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0), (5, 0, 5, 6)]:
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': 2.7, 'thickness': 0.2})))


def _run(stack, action):
    return apply(stack, Proposal(action.key, 'hint', action.label, '', '', (), action.build, run=action.run))


def test_marker_resolves_the_most_specific_thing_under_the_point():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    wc = Entity('plumbing_point', {'x': 6.0, 'y': 5.6, 'z': 0.0, 'point_type': 'wc'}, name='Λεκάνη WC')
    stack.execute(AddEntity(wc))
    assert target_at(doc, 6.05, 5.55).entity_id == wc.id                 # the point beats the room around it
    wall = target_at(doc, 5.03, 3.0)
    assert wall.kind == 'wall' and 'Τοίχος' in wall.label
    room = target_at(doc, 6.5, 2.0)
    assert room.kind == 'room' and room.room['use'] == 'wc' and '3.00×6.00 m' in room.label
    assert target_at(doc, 20.0, 20.0).kind == 'empty'


def test_typed_request_runs_the_matching_action_at_the_marker():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    t = target_at(doc, 6.5, 2.0)
    actions = actions_for(doc, t)
    fan = match('Βάλε εξαερισμό εδώ', actions)
    assert fan is not None and fan.key == 'fan'
    _run(stack, fan)
    v = next(e for e in doc.entities.values() if e.kind == 'ventilation_point')
    assert (v.params['x'], v.params['y']) == (6.5, 2.0)                     # exactly where the user pointed
    assert match('φτιάξε μου ένα σαλόνι', actions) is None                  # unknown → no guessing
    joists = match('μοίρασε δοκίδες στο ταβάνι', actions_for(doc, target_at(doc, 2.0, 3.0)))
    _run(stack, joists)
    assert any(e.kind == 'ceiling_joists' for e in doc.entities.values())
    stack.undo()
    assert not any(e.kind == 'ceiling_joists' for e in doc.entities.values())


def test_structural_member_target_offers_analysis_then_the_section_fix():
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from test_structural_analysis import _building
    doc, st = _building(storeys=1, beam=(0.20, 0.30), span_x=7.0)
    beam = next(e for e in doc.entities.values() if e.kind == 'structural_beam' and e.params['y1'] == 4.0)
    t = target_at(doc, 3.0, 4.0, z=0.0)
    assert t.entity_id == beam.id and t.label.startswith('Δ')
    actions = actions_for(doc, t)
    assert [a.key for a in actions] == ['analyze', 'delete']               # every pointed object can be removed
    _run(st, match('κάνε στατική ανάλυση', actions))
    actions = actions_for(doc, t)
    resize = match('μεγάλωσε τη δοκό', actions)
    assert resize is not None and 'Διατομή' in resize.label
    h0 = doc.get(beam.id).params['height']
    _run(st, resize)
    assert doc.get(beam.id).params['height'] > h0


def test_panel_marker_and_text_in_the_app():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        _house(window.stack)
        window._start_site_tool('assist_point', '')
        window.plan_view.sitePointRequested.emit('assist_point', 6.5, 2.0)
        assert window.plan_view.assistant_marker == (6.5, 2.0)
        assert 'Room' in window.assistant_target_label.text() and window.assistant_actions.count() >= 2
        window.assistant_text.setText('ανεμιστήρα απαγωγής')
        window._assistant_ask()
        assert any(e.kind == 'ventilation_point' for e in window.doc.entities.values())
        assert window.assistant_reply.text().startswith('✓')
        window.assistant_text.setText('κάτι άσχετο')
        window._assistant_ask()
        assert 'Εδώ μπορώ' in window.assistant_reply.text()
        # Target from a selection (works the same for an object picked in 3D).
        fan = next(e.id for e in window.doc.entities.values() if e.kind == 'ventilation_point')
        window.doc.select([fan])
        window._assistant_target_from_selection()
        assert {window.assistant_actions.item(i).text() for i in range(window.assistant_actions.count())} >= {
            '▶ Έξοδος από εξωτερικό τοίχο', '▶ Έξοδος από τη στέγη'}
        window.stack.undo()                                  # the fan disappears → so does the target
        window._refresh_assistant()
        assert window._assistant_target is None and window.plan_view.assistant_marker is None
    finally:
        window._mark_clean(); window.close(); app.processEvents()
