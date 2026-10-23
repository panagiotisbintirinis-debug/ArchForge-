"""Owner 21/10: «Μηχανικά — kinematics / mechanical_part χωρίς UI».

Η/Μ ▸ Μηχανισμοί: a part with a plan click, a joint between two selected parts with sensible defaults
(hinge on the corner touching the frame, slide by the part's own length), and a «Θέση» slider that moves
the part in the plan; one undo per step."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.model import Document, Entity
from archforge.kinematics import authoring as A


def test_part_is_centred_on_the_click_and_defaults_follow_the_parts():
    frame = Entity('mechanical_part', A.part_params(0.0, 0.0, 0.0, 0.10, 0.10, 2.1))    # door frame post at the origin
    leaf = Entity('mechanical_part', A.part_params(0.50, 0.0, 0.0, 0.80, 0.04, 2.0))    # leaf to its right, 0,10–0,90
    assert A.centre(leaf.params) == pytest.approx((0.50, 0.0))
    hinge = A.default_joint(frame, leaf, 'revolute')
    assert hinge['anchor'][:2] == pytest.approx([0.10, -0.02]) and hinge['axis'] == [0.0, 0.0, 1.0]
    assert (hinge['min_value'], hinge['max_value']) == (0.0, 90.0) and hinge['child_part'] == leaf.id
    slide = A.default_joint(frame, leaf, 'prismatic')
    assert slide['axis'][:2] == pytest.approx([1.0, 0.0]) and slide['max_value'] == pytest.approx(0.80)
    fixed = A.default_joint(frame, leaf, 'fixed')
    assert fixed['max_value'] == 0.0
    with pytest.raises(ValueError):
        A.default_joint(frame, leaf, 'spring')


def test_hinged_leaf_is_drawn_open_in_the_plan():
    from archforge.core.plan_scene import build_plan_frame
    doc = Document()
    frame = Entity('mechanical_part', A.part_params(0, 0, 0, .1, .1, 2.1)); doc.add(frame)
    leaf = Entity('mechanical_part', A.part_params(.5, 0, 0, .8, .04, 2.0)); doc.add(leaf)
    params = A.default_joint(frame, leaf, 'revolute'); params['value'] = 90.0
    doc.add(Entity('mechanical_joint', params))
    poly = next(p for p in build_plan_frame(doc).primitives if p.entity_id == leaf.id)
    xs, ys = [q[0] for q in poly.points], [q[1] for q in poly.points]
    assert max(xs) - min(xs) == pytest.approx(0.04, abs=1e-6) and max(ys) - min(ys) == pytest.approx(0.80, abs=1e-6)


def test_menu_part_joint_and_slider_with_undo():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui import mechanical_tool as M
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        texts = [a.text() for a in w._mechanism_menu.actions()]
        assert texts[0].startswith('Εξάρτημα') and texts[1].startswith('Άρθρωση')
        M.start_part(w, {'width': .1, 'depth': .1, 'height': 2.1, 'z': 0.0})
        assert w.plan_view.controller.tool == 'mech_part_place'
        w.plan_view.sitePointRequested.emit('mech_part_place', 0.0, 0.0)
        frame = next(e for e in w.doc.entities.values() if e.kind == 'mechanical_part')
        leaf = M.place_part(w, .5, 0.0, {'width': .8, 'depth': .04, 'height': 2.0})
        assert M.add_joint(w, 'revolute', ids=[frame.id]) is None                      # needs two parts
        joint = M.add_joint(w, 'revolute', ids=[frame.id, leaf.id])
        assert joint.params['max_value'] == 90.0 and w.doc.selection == [joint.id]
        assert M.add_joint(w, 'prismatic', ids=[frame.id, leaf.id]) is None            # one joint moves a part
        assert w._joint_slider.maximum() == 1000
        before = len(w.stack.done)
        M.set_value(w, joint.id, 120.0)                                                  # clamped to 90°
        assert w.doc.get(joint.id).params['value'] == 90.0 and len(w.stack.done) == before + 1
        w._undo()
        assert w.doc.get(joint.id).params['value'] == 0.0
        w._undo()
        assert joint.id not in w.doc.entities
    finally:
        w._mark_clean(); w.close(); app.processEvents()
