from io import StringIO

from archforge.mep.trade_bom import BOM_COLUMNS, bom_rows, export_bom_csv
from archforge.mep.trade_costing import PriceEntry, QuantityLine, cost_lines


def test_bom_rows_are_projection_of_shared_cost_rows():
    source = cost_lines(
        [QuantityLine("pipe", "Pipe", "pipes", 2.0, "m", "plumbing", rule_status="ENGINEER_REVIEW")],
        {"pipe": PriceEntry(material_unit_price=3.0, labour_unit_price=1.0, source="contractor")},
    )[0]
    row = bom_rows([source])[0]
    assert list(row) == [key for key, _label in BOM_COLUMNS]
    assert row["code"] == "pipe"
    assert row["quantity"] == 2.0
    assert row["material_unit_price"] == 3.0
    assert row["labour_unit_price"] == 1.0
    assert row["total_cost"] == 8.0
    assert row["pricing_status"] == "complete"
    assert row["price_source"] == "contractor"
    assert row["rule_status"] == "ENGINEER_REVIEW"


def test_missing_prices_stay_blank_in_csv_not_zero():
    rows = cost_lines(
        [QuantityLine("valve", "Valve", "accessories", 1.0, "pcs", "plumbing")],
        {},
    )
    stream = StringIO()
    export_bom_csv(rows, stream)
    text = stream.getvalue()
    assert "Κωδικός" in text
    assert "valve" in text
    assert "missing" in text
    # There must be no invented 0.0 unit/material/labour price.
    assert ",0.0," not in text
