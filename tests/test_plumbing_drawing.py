from archforge.mep.plumbing_drawing import technical_plan_topology


def test_hot_offset_bend_gets_drawing_bridge_without_changing_route():
    # Logical bend at (1, 0).  The two displayed hot runs are offset in
    # different directions, so their visible endpoints do not coincide.
    routed = {
        "hot": [
            ((0.0, 0.05, 0.05), (1.0, 0.05, 0.05), 20),
            ((0.95, 0.0, 0.05), (0.95, 1.0, 0.05), 20),
        ],
        "cold": [],
        "report": {"system": "multilayer"},
    }
    topology = technical_plan_topology(routed, level_z=0.0, screed=0.05, hot_offset=0.05)
    assert len(topology["bridges"]) == 2
    assert topology["junctions"] == []
    # Helper is presentation-only; the original route is untouched.
    assert routed["hot"][0][1] == (1.0, 0.05, 0.05)


def test_three_runs_at_same_node_produce_explicit_junction():
    routed = {
        "cold": [
            ((0.0, 0.0, 0.05), (1.0, 0.0, 0.05), 20),
            ((1.0, 0.0, 0.05), (2.0, 0.0, 0.05), 16),
            ((1.0, 0.0, 0.05), (1.0, 1.0, 0.05), 16),
        ],
        "hot": [],
        "report": {"system": "multilayer"},
    }
    topology = technical_plan_topology(routed, level_z=0.0, screed=0.05, hot_offset=0.05)
    assert len(topology["junctions"]) == 1
    assert topology["junctions"][0]["network"] == "cold"
    assert topology["junctions"][0]["point"] == (1.0, 0.0)


def test_vertical_segment_crossing_plan_is_reported_as_riser():
    routed = {
        "cold": [((2.0, 3.0, 0.05), (2.0, 3.0, 0.80), 16)],
        "hot": [],
        "report": {"system": "multilayer"},
    }
    topology = technical_plan_topology(routed, level_z=0.0, screed=0.05, hot_offset=0.05)
    assert topology["risers"] == [
        {"network": "cold", "point": (2.0, 3.0), "diameter": 16, "direction": "up"}
    ]


def test_manifold_routes_do_not_guess_bridges_from_display_offsets():
    routed = {
        "cold": [
            ((0.0, 0.00, 0.05), (1.0, 0.00, 0.05), 16),
            ((0.0, 0.04, 0.05), (1.0, 0.04, 0.05), 16),
        ],
        "hot": [],
        "report": {"system": "manifold"},
    }
    topology = technical_plan_topology(routed, level_z=0.0, screed=0.05, hot_offset=0.05)
    assert topology["bridges"] == []
