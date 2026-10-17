from types import SimpleNamespace

from archforge.core.plan_scene import PlanFrame, Primitive2D
from archforge.ui.plumbing_display import apply_display_state


def _pipe(role="pipe-cold", dia=16, a=(0.0, 0.0), b=(3.0, 4.0)):
    return Primitive2D("polyline", (a, b), role=role, meta=(("diameter", dia),))


def test_plumbing_plan_keeps_only_pipe_runs_from_plumbing_layer():
    doc = SimpleNamespace()
    cold = _pipe("pipe-cold")
    hot = _pipe("pipe-hot")
    point = Primitive2D("ellipse", ((1.0, 1.0),), role="plumbing-point")
    manifold = Primitive2D("polyline", ((0.0, 0.0), (1.0, 0.0)), role="manifold")
    legacy_label = Primitive2D("label", ((0.5, 0.0),), role="plumbing-overlay-label", meta=(("text", "Ø16"),))
    wall = Primitive2D("line", ((0.0, 0.0), (5.0, 0.0)), role="model")

    frame = PlanFrame(primitives=[cold, hot, point, manifold, legacy_label, wall])
    apply_display_state(doc, frame)

    assert frame.primitives == [cold, hot, wall]


def test_pipe_metadata_is_preserved_for_details_tab_even_when_not_drawn_as_text():
    doc = SimpleNamespace()
    pipe = _pipe(dia=20)
    frame = PlanFrame(primitives=[pipe])
    apply_display_state(doc, frame)

    assert frame.primitives == [pipe]
    assert dict(pipe.meta)["diameter"] == 20
    assert all(p.kind != "label" for p in frame.primitives)


def test_non_plumbing_plan_content_is_not_filtered():
    doc = SimpleNamespace()
    room = Primitive2D("polygon", ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0)), role="room")
    electrical = Primitive2D("ellipse", ((1.0, 1.0),), role="electrical-point")
    frame = PlanFrame(primitives=[room, electrical])

    apply_display_state(doc, frame)

    assert frame.primitives == [room, electrical]
