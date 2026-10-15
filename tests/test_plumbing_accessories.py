from types import SimpleNamespace

from archforge.mep.plumbing_accessories import accessory_quantities
from archforge.mep.trade_costing import PriceEntry, cost_lines, owner_quote_view


def _doc(*entities):
    return SimpleNamespace(entities={e.id: e for e in entities})


def test_explicit_valves_and_manifold_cabinet_become_bom_lines():
    valve = SimpleNamespace(
        id="a1",
        kind="plumbing_accessory",
        params={
            "accessory_type": "isolation_valve",
            "quantity": 2,
            "unit": "pcs",
            "rule_status": "MODEL_SELECTED",
            "selection_basis": "professional_selection",
        },
    )
    cabinet = SimpleNamespace(
        id="a2",
        kind="plumbing_accessory",
        params={
            "accessory_type": "manifold_cabinet",
            "quantity": 1,
            "unit": "pcs",
            "manufacturer": "Example",
            "product_ref": "CAB-01",
            "source_kind": "manufacturer_data",
            "rule_status": "MANUFACTURER_DATA",
            "rule_source": "selected product data sheet",
        },
    )

    lines = accessory_quantities(_doc(valve, cabinet))
    by_code = {line.code: line for line in lines}

    assert by_code["plumbing.accessory.isolation_valve"].quantity == 2
    assert by_code["plumbing.accessory.isolation_valve"].description == "Βάνα απομόνωσης"
    cabinet_line = by_code["plumbing.accessory.manifold_cabinet.CAB-01"]
    assert cabinet_line.quantity == 1
    assert "Πίνακας / ερμάριο υδροληψίας" in cabinet_line.description
    assert cabinet_line.rule_status == "MANUFACTURER_DATA"
    assert cabinet_line.rule_source == "selected product data sheet"


def test_accessories_are_not_invented_when_model_has_none():
    socket_like = SimpleNamespace(id="x", kind="plumbing_point", params={})
    assert accessory_quantities(_doc(socket_like)) == []


def test_owner_view_uses_same_priced_row_and_explains_why():
    valve = SimpleNamespace(
        id="a1",
        kind="plumbing_accessory",
        params={"accessory_type": "isolation_valve", "quantity": 1, "unit": "pcs"},
    )
    line = accessory_quantities(_doc(valve))[0]
    rows = cost_lines(
        [line],
        {line.code: PriceEntry(material_unit_price=12.5, labour_unit_price=7.5)},
    )
    owner = owner_quote_view(rows)[0]

    assert owner["item"] == "Βάνα απομόνωσης"
    assert owner["why"]
    assert owner["material_cost"] == 12.5
    assert owner["labour_cost"] == 7.5
    assert owner["total_cost"] == 20.0
    assert owner["priced"] is True
