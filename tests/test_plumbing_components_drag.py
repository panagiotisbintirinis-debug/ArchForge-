from types import SimpleNamespace

from archforge.mep.plumbing_components import accessory_params, component_actions, snap_target
from archforge.mep.plumbing_economy import least_pipe_length_candidate


def _entity(eid, kind, params):
    return SimpleNamespace(id=eid, kind=kind, params=params, visible=True, name="")


def test_component_catalog_exposes_drag_actions():
    actions = dict(component_actions())
    assert actions["Γωνιακός διακόπτης"] == ("plumbing_component", "angle_stop")
    assert actions["Ρακόρ"] == ("plumbing_component", "union")
    assert actions["Ερμάριο συλλέκτη"] == ("plumbing_component", "manifold_cabinet")


def test_point_only_component_snaps_to_plumbing_point(monkeypatch):
    point = _entity("p1", "plumbing_point", {"x": 1.0, "y": 2.0, "z": 0.0, "point_type": "basin"})
    doc = SimpleNamespace(entities={"p1": point})
    monkeypatch.setattr("archforge.mep.plumbing_components.route_plumbing_cached", lambda _doc: {"cold": [], "hot": [], "manifolds": []})
    target = snap_target(doc, "angle_stop", 1.05, 2.02)
    assert target["host_kind"] == "point"
    assert target["host_id"] == "p1"
    params = accessory_params("angle_stop", target)
    assert params["selection_basis"] == "visual_drag_drop"
    assert params["rule_status"] == "MODEL_SELECTED"


def test_pipe_component_snaps_to_nearest_route_segment(monkeypatch):
    doc = SimpleNamespace(entities={})
    monkeypatch.setattr(
        "archforge.mep.plumbing_components.route_plumbing_cached",
        lambda _doc: {
            "cold": [((0.0, 0.0, 0.05), (2.0, 0.0, 0.05), 16)],
            "hot": [], "manifolds": [],
        },
    )
    target = snap_target(doc, "coupling", 0.8, 0.1)
    assert target["host_kind"] == "pipe"
    assert target["network"] == "cold"
    assert target["diameter"] == 16
    assert abs(target["x"] - 0.8) < 1e-9
    assert abs(target["y"]) < 1e-9


def test_invalid_host_does_not_place_component(monkeypatch):
    doc = SimpleNamespace(entities={})
    monkeypatch.setattr("archforge.mep.plumbing_components.route_plumbing_cached", lambda _doc: {"cold": [], "hot": [], "manifolds": []})
    assert snap_target(doc, "angle_stop", 0.0, 0.0) is None


def test_least_pipe_candidate_is_only_a_comparison(monkeypatch):
    rows = [
        {"system": "a", "pipe_m": 20.0, "unserved": 0},
        {"system": "b", "pipe_m": 15.0, "unserved": 0},
        {"system": "c", "pipe_m": 10.0, "unserved": 1},
    ]
    monkeypatch.setattr("archforge.mep.plumbing_economy.compare_systems", lambda _doc: rows)
    assert least_pipe_length_candidate(object())["system"] == "b"
