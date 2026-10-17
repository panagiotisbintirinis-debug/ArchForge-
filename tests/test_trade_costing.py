from archforge.mep.trade_costing import (
    PriceEntry,
    QuantityLine,
    combine_trade_quotes,
    cost_lines,
    owner_quote_view,
    quote_summary,
)


def test_missing_prices_are_not_guessed():
    quantities = [
        QuantityLine("pipe-16", "Pipe Ø16", "cold-water", 25.0, "m", "plumbing"),
    ]
    rows = cost_lines(quantities, {})
    assert rows[0]["material_unit_price"] is None
    assert rows[0]["labour_unit_price"] is None
    assert rows[0]["material_cost"] is None
    assert rows[0]["labour_cost"] is None
    assert rows[0]["total_cost"] is None
    assert rows[0]["price_source"] == "missing"
    summary = quote_summary(rows)
    assert summary["complete"] is False
    assert summary["unpriced_codes"] == ["pipe-16"]
    assert summary["missing_price_codes"] == ["pipe-16"]
    assert summary["partial_price_codes"] == []


def test_material_and_labour_are_separate_and_grouped_by_type():
    quantities = [
        QuantityLine("pipe-16", "Pipe Ø16", "cold-water", 10.0, "m", "plumbing"),
        QuantityLine("pipe-20", "Pipe Ø20", "hot-water", 5.0, "m", "plumbing"),
    ]
    prices = {
        "pipe-16": PriceEntry(material_unit_price=2.0, labour_unit_price=1.5, source="contractor"),
        "pipe-20": PriceEntry(material_unit_price=3.0, labour_unit_price=2.0, source="contractor"),
    }
    rows = cost_lines(quantities, prices)
    assert rows[0]["material_unit_price"] == 2.0
    assert rows[0]["labour_unit_price"] == 1.5
    summary = quote_summary(rows)
    assert summary["material_cost"] == 35.0
    assert summary["labour_cost"] == 25.0
    assert summary["subtotal"] == 60.0
    assert summary["complete_priced_subtotal"] == 60.0
    assert summary["by_category"] == {"cold-water": 35.0, "hot-water": 25.0}
    assert summary["by_trade"] == {"plumbing": 60.0}
    assert summary["complete"] is True


def test_partial_price_is_visible_but_never_marked_complete():
    quantities = [
        QuantityLine("valve", "Valve", "accessories", 2.0, "pcs", "plumbing"),
    ]
    rows = cost_lines(quantities, {
        "valve": PriceEntry(material_unit_price=8.0, source="contractor"),
    })
    assert rows[0]["material_cost"] == 16.0
    assert rows[0]["labour_cost"] is None
    assert rows[0]["total_cost"] == 16.0
    assert rows[0]["partial_price"] is True
    assert rows[0]["complete_price"] is False
    summary = quote_summary(rows)
    assert summary["subtotal"] == 16.0
    assert summary["complete_priced_subtotal"] == 0.0
    assert summary["partial_price_codes"] == ["valve"]
    assert summary["complete"] is False


def test_combined_quote_keeps_one_pricing_path_for_multiple_trades():
    plumbing_rows = cost_lines(
        [QuantityLine("pipe", "Pipe", "pipe", 10.0, "m", "plumbing")],
        {"pipe": PriceEntry(2.0, 1.0, source="contractor")},
    )
    heating_rows = cost_lines(
        [QuantityLine("radiator", "Radiator", "equipment", 2.0, "pcs", "heating")],
        {"radiator": PriceEntry(100.0, 20.0, source="contractor")},
    )
    combined = combine_trade_quotes({
        "plumbing": {"rows": plumbing_rows},
        "heating": {"rows": heating_rows},
    })
    assert combined["summary"]["subtotal"] == 270.0
    assert combined["summary"]["by_trade"] == {"heating": 240.0, "plumbing": 30.0}
    assert combined["by_trade"]["plumbing"]["subtotal"] == 30.0
    assert combined["by_trade"]["heating"]["subtotal"] == 240.0
    assert len(combined["owner_view"]) == 2


def test_owner_view_uses_same_unit_prices_and_costs():
    row = cost_lines(
        [QuantityLine("pipe", "Pipe", "pipe", 3.0, "m", "plumbing", owner_explanation="Model route")],
        {"pipe": PriceEntry(2.5, 1.5, source="contractor")},
    )[0]
    owner = owner_quote_view([row])[0]
    assert owner["material_unit_price"] == 2.5
    assert owner["labour_unit_price"] == 1.5
    assert owner["total_cost"] == 12.0
    assert owner["price_source"] == "contractor"
    assert owner["why"] == "Model route"
