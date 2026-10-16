from types import SimpleNamespace

import pytest

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.mep.project_pricebook import (
    migrate_description_prices,
    price_book_audit,
    price_list_params,
    project_prices,
    set_project_price,
    update_project_price,
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


def test_price_book_survives_document_save_load_roundtrip():
    original = Document()
    params = price_list_params({
        "heating.point.radiator": PriceEntry(
            material_unit_price=120.0,
            labour_unit_price=35.0,
            source="contractor",
        )
    }, vat=24.0)
    original.add(Entity("price_list", params, name="Project prices"))

    restored = Document.from_dict(original.to_dict())
    prices = project_prices(restored)
    assert prices["heating.point.radiator"].material_unit_price == 120.0
    assert prices["heating.point.radiator"].labour_unit_price == 35.0
    entity = next(e for e in restored.entities.values() if e.kind == "price_list")
    assert entity.params["vat"] == 24.0
    assert entity.params["entries"]["heating.point.radiator"]["source"] == "contractor"


def test_project_price_edits_are_commandstack_undoable_and_redoable():
    doc = Document()
    stack = CommandStack(doc)
    set_project_price(
        stack,
        doc,
        "plumbing.pipe.cold.dn16",
        PriceEntry(material_unit_price=2.4, labour_unit_price=1.6, source="contractor"),
    )
    assert project_prices(doc)["plumbing.pipe.cold.dn16"].material_unit_price == 2.4
    assert stack.can_undo is True

    stack.undo()
    assert project_prices(doc) == {}
    assert stack.can_redo is True

    stack.redo()
    assert project_prices(doc)["plumbing.pipe.cold.dn16"].labour_unit_price == 1.6

    set_project_price(
        stack,
        doc,
        "heating.point.radiator",
        PriceEntry(material_unit_price=120.0, labour_unit_price=35.0, source="contractor"),
    )
    prices = project_prices(doc)
    assert set(prices) == {"plumbing.pipe.cold.dn16", "heating.point.radiator"}


def test_cell_level_price_edit_preserves_other_component_and_is_undoable():
    doc = Document()
    stack = CommandStack(doc)
    set_project_price(
        stack,
        doc,
        "valve",
        PriceEntry(material_unit_price=8.0, labour_unit_price=3.0, source="contractor"),
    )
    update_project_price(stack, doc, "valve", material_unit_price=9.5)
    edited = project_prices(doc)["valve"]
    assert edited.material_unit_price == 9.5
    assert edited.labour_unit_price == 3.0
    assert edited.source == "contractor"

    stack.undo()
    restored = project_prices(doc)["valve"]
    assert restored.material_unit_price == 8.0
    assert restored.labour_unit_price == 3.0


def test_price_book_audit_reports_missing_partial_unused_and_currency_conflict():
    quantities = [
        QuantityLine("pipe", "Pipe", "pipes", 2.0, "m", "plumbing"),
        QuantityLine("valve", "Valve", "accessories", 1.0, "pcs", "plumbing"),
        QuantityLine("radiator", "Radiator", "equipment", 1.0, "pcs", "heating"),
    ]
    prices = {
        "pipe": PriceEntry(2.0, 1.0, "EUR", "contractor"),
        "valve": PriceEntry(8.0, None, "EUR", "contractor"),
        "old-item": PriceEntry(99.0, 10.0, "USD", "legacy"),
    }
    audit = price_book_audit(quantities, prices)
    assert audit["missing_codes"] == ["radiator"]
    assert audit["partial_codes"] == ["valve"]
    assert audit["unused_codes"] == ["old-item"]
    assert audit["currencies"] == ["EUR"]
    assert audit["complete"] is False


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
