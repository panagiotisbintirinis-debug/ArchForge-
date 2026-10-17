from types import SimpleNamespace

from archforge.mep.heating import heating_quantities, heating_quote, heating_review
from archforge.mep.heating_rules import ENGINEER_REVIEW, VERIFIED_STANDARD
from archforge.mep.trade_costing import PriceEntry


def _entity(kind, **params):
    return SimpleNamespace(kind=kind, params=params)


def _doc(*entities):
    return SimpleNamespace(entities={str(i): e for i, e in enumerate(entities)})


def test_heating_counts_only_authored_equipment_and_zones():
    doc = _doc(
        _entity("heating_point", point_type="heat_pump"),
        _entity("heating_point", point_type="radiator"),
        _entity("heating_point", point_type="radiator"),
        _entity("heating_zone", zone_type="radiator_zone"),
    )
    quantities = {q.code: q for q in heating_quantities(doc)}
    assert quantities["heating.point.heat_pump"].quantity == 1.0
    assert quantities["heating.point.radiator"].quantity == 2.0
    assert quantities["heating.zone.radiator_zone"].quantity == 1.0
    assert all(q.rule_status.endswith("ENGINEER_REVIEW") for q in quantities.values())


def test_heating_never_invents_pipe_length_or_diameter():
    doc = _doc(
        _entity("heating_point", point_type="radiator"),
        _entity("heating_zone", zone_type="radiator_zone"),
    )
    codes = {q.code for q in heating_quantities(doc)}
    assert not any(code.startswith("heating.pipe.") for code in codes)
    review = heating_review(doc)
    assert review["automatic_calculations"] == {
        "heat_loss": False,
        "emitter_sizing": False,
        "pipe_sizing": False,
        "pump_selection": False,
        "hydraulic_balancing": False,
    }
    assert review["verified_automatic_sizing"] is False
    assert VERIFIED_STANDARD in review["rule_audit"]
    assert ENGINEER_REVIEW in review["rule_audit"]


def test_explicit_heating_pipe_length_is_counted_without_sizing_claim():
    doc = _doc(
        _entity("heating_point", point_type="radiator", pipe_type="supply_return", pipe_length_m=12.5),
        _entity("heating_point", point_type="radiator", pipe_type="supply_return", pipe_length_m=7.5),
    )
    quantities = {q.code: q for q in heating_quantities(doc)}
    pipe = quantities["heating.pipe.supply_return"]
    assert pipe.quantity == 20.0
    assert pipe.unit == "m"
    assert pipe.selection_basis == "explicit_model_value"
    assert "diameter" not in pipe.description.lower()


def test_heating_quote_uses_shared_material_and_labour_engine():
    doc = _doc(
        _entity("heating_point", point_type="radiator"),
        _entity("heating_point", point_type="radiator"),
    )
    quote = heating_quote(doc, {
        "heating.point.radiator": PriceEntry(
            material_unit_price=120.0,
            labour_unit_price=35.0,
            source="contractor",
        )
    })
    row = next(r for r in quote["rows"] if r["code"] == "heating.point.radiator")
    assert row["quantity"] == 2.0
    assert row["material_unit_price"] == 120.0
    assert row["labour_unit_price"] == 35.0
    assert row["material_cost"] == 240.0
    assert row["labour_cost"] == 70.0
    assert row["total_cost"] == 310.0
    assert quote["summary"]["complete"] is True
    owner = quote["owner_view"][0]
    assert owner["total_cost"] == 310.0
    assert owner["price_source"] == "contractor"
