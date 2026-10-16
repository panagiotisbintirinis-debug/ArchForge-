from types import SimpleNamespace

import pytest

from archforge.mep.project_pricebook import (
    migrate_description_prices,
    price_list_params,
    project_prices,
)
from archforge.mep.trade_costing import PriceEntry, QuantityLine


def _doc(*entities):
    return SimpleNamespace(entities={str(i): e for i, e in enumerate(entities)})


def _price_list(**params):
    return SimpleNamespace(kind="price_list", params=params)


def test_missing_project_price_list_means_no_prices_not_defaults():
    assert project_prices(_doc()) == {}


def test_project_price_list_is_code_keyed_and_preserves_material_labour_split():
    doc = _doc(_price_list(
        vat=0.0,
        currency="EUR",
        entries={
            "plumbing.pipe.cold.dn16": {
                "material_unit_price": 2.4,
                "labour_unit_price": 1.6,
                "source": "contractor",
            }
        },
    ))
    prices = project_prices(doc)
    entry = prices["plumbing.pipe.cold.dn16"]
    assert entry.material_unit_price == 2.4
    assert entry.labour_unit_price == 1.6
    assert entry.currency == "EUR"
    assert entry.source == "contractor"


def test_two_project_price_lists_are_rejected_as_competing_sources_of_truth():
    doc = _doc(_price_list(entries={}), _price_list(entries={}))
    with pytest.raises(ValueError, match="more than one price_list"):
        project_prices(doc)


def test_price_list_params_never_invents_missing_component_price():
    params = price_list_params({
        "valve": PriceEntry(material_unit_price=8.0, labour_unit_price=None, source="contractor"),
    })
    saved = params["entries"]["valve"]
    assert saved["material_unit_price"] == 8.0
    assert saved["labour_unit_price"] is None


def test_legacy_description_migration_only_maps_unambiguous_items():
    quantities = [
        QuantityLine("a", "Pipe Ø16", "pipes", 1, "m", "plumbing"),
        QuantityLine("b", "Pipe Ø20", "pipes", 1, "m", "plumbing"),
        QuantityLine("c", "Duplicate", "other", 1, "pcs", "plumbing"),
        QuantityLine("d", "Duplicate", "other", 1, "pcs", "plumbing"),
    ]
    migrated = migrate_description_prices(
        quantities,
        {"Pipe Ø16": 2.5, "Duplicate": 99.0, "Unknown": 12.0},
        component="material",
    )
    assert set(migrated) == {"a"}
    assert migrated["a"].material_unit_price == 2.5
    assert migrated["a"].labour_unit_price is None
