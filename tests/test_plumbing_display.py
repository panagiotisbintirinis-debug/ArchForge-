from types import SimpleNamespace

from archforge.core.plan_scene import PlanFrame, Primitive2D
from archforge.ui.plumbing_display import PlumbingDisplayState, apply_display_state, pipe_label, state_for


def _pipe(role="pipe-cold", dia=16, a=(0.0, 0.0), b=(3.0, 4.0)):
    return Primitive2D("polyline", (a, b), role=role, meta=(("diameter", dia),))


def test_default_plumbing_display_keeps_plan_clean():
    doc = SimpleNamespace()
    state = state_for(doc)
    assert state.show_network is True
    assert state.show_points is True
    assert state.show_manifolds is True
    assert state.show_diameters is False
    assert state.show_lengths is False

    frame = PlanFrame(primitives=[_pipe()])
    apply_display_state(doc, frame)
    assert [p.role for p in frame.primitives] == ["pipe-cold"]


def test_pipe_label_only_contains_user_requested_fields():
    pipe = _pipe()
    assert pipe_label(pipe, PlumbingDisplayState()) == ""
    assert pipe_label(pipe, PlumbingDisplayState(show_diameters=True)) == "Ø16"
    assert pipe_label(pipe, PlumbingDisplayState(show_lengths=True)) == "5,00 m"
    assert pipe_label(pipe, PlumbingDisplayState(show_diameters=True, show_lengths=True)) == "Ø16 · 5,00 m"


def test_network_visibility_is_view_only_filtering():
    doc = SimpleNamespace()
    state_for(doc).show_network = False
    original = _pipe()
    other = Primitive2D("line", ((0.0, 0.0), (1.0, 0.0)), role="model")
    frame = PlanFrame(primitives=[original, other])
    apply_display_state(doc, frame)
    assert frame.primitives == [other]
    # The source primitive was not mutated; display state only changed the frame.
    assert original.meta == (("diameter", 16),)
