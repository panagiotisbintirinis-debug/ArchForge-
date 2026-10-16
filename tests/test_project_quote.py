from types import SimpleNamespace

from archforge.mep.project_quote import project_quote


def _entity(kind, **params):
    return SimpleNamespace(kind=kind, params=params)


def _doc(*entities):
    return SimpleNamespace(entities={str(i): e for i, e in enumerate(entities)})


def test_project_quote_uses_one_price_book_for_heating_trade():
    doc = _doc(
        _entity("heating_point", point_type="radiator"),
        _entity("heating_point", point_type="radiator"),
        _entity(
            "price_list",
            vat=24.0,
            currency="EUR",
            entries={
                "heating.point.radiator": {
                    "material_unit_price": 100.0,
                    "labour_unit_price": 25.0,
                    "source": "contractor",
                }
            },
        ),
    )
    quote = project_quote(doc, trades=("heating",))
    assert quote["summary"]["subtotal"] == 250.0
    assert quote["vat_pct"] == 24.0
    assert quote["vat_amount"] == 60.0
    assert quote["gross_total"] == 310.0
    assert quote["pricing_complete"] is True
    assert quote["summary"]["by_trade"] == {"heating": 250.0}


def test_project_quote_labels_partial_total_when_price_component_missing():
    doc = _doc(
        _entity("heating_point", point_type="radiator"),
        _entity(
            "price_list",
            vat=0.0,
            entries={
                "heating.point.radiator": {
                    "material_unit_price": 100.0,
                    "labour_unit_price": None,
                    "source": "contractor",
                }
            },
        ),
    )
    quote = project_quote(doc, trades=("heating",))
    assert quote["summary"]["subtotal"] == 100.0
    assert quote["pricing_complete"] is False
    assert "Partial priced total" in quote["commercial_note"]
    assert quote["summary"]["partial_price_codes"] == ["heating.point.radiator"]
