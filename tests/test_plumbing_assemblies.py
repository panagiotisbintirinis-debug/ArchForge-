from types import SimpleNamespace

from archforge.mep.plumbing_assemblies import (
    connection_assembly_details,
    connection_assembly_quantities,
)


def _point(pid, point_type, assembly=None, name=""):
    params = {"point_type": point_type, "x": 0.0, "y": 0.0, "z": 0.0}
    if assembly is not None:
        params["connection_assembly"] = assembly
    return SimpleNamespace(id=pid, kind="plumbing_point", params=params, name=name)


def _doc(*entities):
    return SimpleNamespace(entities={e.id: e for e in entities})


def test_unconfigured_point_is_visible_but_does_not_invent_parts():
    doc = _doc(_point("b1", "basin", name="Νιπτήρας μπάνιου"))
    details = connection_assembly_details(doc)
    assert len(details) == 1
    assert details[0]["configured"] is False
    assert details[0]["rule_status"] == "UNCONFIGURED"
    assert connection_assembly_quantities(doc) == []


def test_selected_connection_components_are_grouped_for_purchase_bom():
    assembly = {
        "name": "Επιλεγμένη σύνδεση νιπτήρα",
        "source_kind": "professional_selection",
        "rule_status": "MODEL_SELECTED",
        "components": [
            {"accessory_type": "angle_stop", "quantity": 2, "unit": "pcs"},
            {"accessory_type": "union", "quantity": 2, "unit": "pcs", "product_ref": "U16"},
        ],
    }
    doc = _doc(
        _point("b1", "basin", assembly, "Νιπτήρας 1"),
        _point("b2", "basin", assembly, "Νιπτήρας 2"),
    )
    lines = {line.code: line for line in connection_assembly_quantities(doc)}
    assert lines["plumbing.connection_component.angle_stop"].quantity == 4
    assert lines["plumbing.connection_component.union.U16"].quantity == 4
    assert lines["plumbing.connection_component.angle_stop"].category == "Εξαρτήματα συνδέσεων"


def test_source_equipment_can_have_explicit_parts_without_defaults():
    solar = _point(
        "s1",
        "solar_heater",
        {
            "name": "Selected solar connection",
            "source_kind": "manufacturer_data",
            "rule_status": "MANUFACTURER_DATA",
            "rule_source": "selected product data sheet",
            "components": [
                {"accessory_type": "solar_connector", "quantity": 2, "unit": "pcs"},
                {"accessory_type": "safety_group", "quantity": 1, "unit": "pcs"},
            ],
        },
        "Ηλιακός",
    )
    lines = {line.code: line for line in connection_assembly_quantities(_doc(solar))}
    assert lines["plumbing.connection_component.solar_connector"].quantity == 2
    assert lines["plumbing.connection_component.safety_group"].quantity == 1
    assert all(line.rule_status == "MANUFACTURER_DATA" for line in lines.values())


def test_pipe_bom_aggregates_route_segments(monkeypatch):
    import archforge.mep.plumbing_costing as costing

    routed = {
        "cold": [
            ((0, 0, 0), (1, 0, 0), 16),
            ((1, 0, 0), (3, 0, 0), 16),
            ((0, 1, 0), (1, 1, 0), 20),
        ],
        "hot": [((0, 2, 0), (2, 2, 0), 16)],
        "manifolds": [],
        "report": {"provenance": "test"},
    }
    monkeypatch.setattr(costing, "route_plumbing", lambda doc: routed)
    doc = _doc()
    lines = costing.plumbing_quantities(doc)
    pipes = [line for line in lines if line.category == "Σωληνώσεις"]
    by_code = {line.code: line for line in pipes}
    assert len(pipes) == 3
    assert by_code["plumbing.pipe.cold.dn16"].quantity == 3.0
    assert by_code["plumbing.pipe.cold.dn20"].quantity == 1.0
    assert by_code["plumbing.pipe.hot.dn16"].quantity == 2.0


def test_manifold_is_separate_3d_costable_object(monkeypatch):
    import archforge.mep.plumbing_visuals as visuals

    monkeypatch.setattr(
        visuals,
        "route_plumbing_cached",
        lambda doc: {
            "manifolds": [{
                "x": 1.0,
                "y": 2.0,
                "z": 0.0,
                "system": "cold",
                "outlets": ["a", "b", "c", "d"],
                "feed_mm": 20,
            }]
        },
    )
    objects = visuals.manifold_scene_objects(object())
    assert len(objects) == 1
    obj = objects[0]
    assert obj["kind"] == "mep_manifold"
    assert obj["layer"] == "mep"
    assert obj["plumbing_meta"]["outlet_count"] == 4
    assert obj["plumbing_meta"]["bom_code"] == "plumbing.manifold.cold.4way"
    assert obj["plumbing_meta"]["presentation_only"] is True
