from archforge.mep.trade_costing import PriceEntry, QuantityLine, cost_lines, quote_summary


def test_missing_prices_are_not_guessed():
    quantities = [
        QuantityLine("pipe-16", "Pipe Ø16", "cold-water", 25.0, "m", "plumbing"),
    ]
    rows = cost_lines(quantities, {})
    assert rows[0]["material_cost"] is None
    assert rows[0]["labour_cost"] is None
    assert rows[0]["total_cost"] is None
    assert rows[0]["price_source"] == "missing"
    summary = quote_summary(rows)
    assert summary["complete"] is False
    assert summary["unpriced_codes"] == ["pipe-16"]


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
    summary = quote_summary(rows)
    assert summary["material_cost"] == 35.0
    assert summary["labour_cost"] == 25.0
    assert summary["subtotal"] == 60.0
    assert summary["by_category"] == {"cold-water": 35.0, "hot-water": 25.0}
    assert summary["complete"] is True
