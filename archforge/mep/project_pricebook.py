"""One project price book shared by every ArchForge trade.

The authoritative project model already supports a ``price_list`` entity. This
module defines the commercial contract stored in that entity without adding any
market/default prices:

    entries[item_code] = {
        material_unit_price: number | None,
        labour_unit_price: number | None,
        currency: "EUR",
        source: "contractor" | ...,
    }

Plumbing, heating, electrical and later trades must resolve prices through this
same code-keyed mapping. Missing prices remain missing. Mutations go through the
normal CommandStack so undo/redo and save/load remain authoritative.
"""
from __future__ import annotations

from typing import Iterable, Mapping

from archforge.mep.trade_costing import PriceEntry, QuantityLine


_UNSET = object()


def price_list_entities(doc):
    """Return project price-list entities without creating or mutating anything."""
    return [entity for entity in doc.entities.values() if entity.kind == "price_list"]


def project_price_list(doc):
    """Return the single project price-list entity, or None.

    Multiple price-list entities would create competing sources of truth and are
    therefore rejected instead of silently choosing one.
    """
    found = price_list_entities(doc)
    if len(found) > 1:
        raise ValueError("project contains more than one price_list entity")
    return found[0] if found else None


def _optional_non_negative(value, label):
    if value is None:
        return None
    value = float(value)
    if value < 0:
        raise ValueError(f"{label} must be >= 0")
    return value


def price_entry_from_dict(raw: Mapping, default_currency="EUR") -> PriceEntry:
    """Validate a serialized price-book entry and turn it into PriceEntry."""
    raw = dict(raw or {})
    currency = str(raw.get("currency", default_currency) or default_currency)
    source = str(raw.get("source", "project_price_list") or "project_price_list")
    return PriceEntry(
        material_unit_price=_optional_non_negative(raw.get("material_unit_price"), "material_unit_price"),
        labour_unit_price=_optional_non_negative(raw.get("labour_unit_price"), "labour_unit_price"),
        currency=currency,
        source=source,
    )


def project_prices(doc) -> dict[str, PriceEntry]:
    """Read the one project price book as code -> PriceEntry.

    No line is synthesized for missing codes. A missing project price list
    simply returns an empty mapping, which keeps all quote rows visibly unpriced.
    """
    entity = project_price_list(doc)
    if entity is None:
        return {}
    params = entity.params
    default_currency = str(params.get("currency", "EUR") or "EUR")
    raw_entries = params.get("entries", {}) or {}
    if not isinstance(raw_entries, Mapping):
        raise ValueError("price_list entries must be a mapping keyed by item code")
    entries = {
        str(code): price_entry_from_dict(raw, default_currency)
        for code, raw in raw_entries.items()
    }
    # The «Υλικά & τιμές» tab and the Prices dialog write ``trade_prices`` (and older projects ``prices``,
    # description -> material price): the same book, read here so every trade sees one set of prices.
    # ``entries`` win for a code present in both.
    legacy = {"desc:" + str(d): {"material": v, "labour": None} for d, v in (params.get("prices") or {}).items()}
    legacy.update(params.get("trade_prices") or {})
    for code, raw in legacy.items():
        if not isinstance(raw, Mapping):
            continue
        price = price_entry_from_dict({"material_unit_price": raw.get("material"), "labour_unit_price": raw.get("labour"),
                                       "currency": default_currency, "source": "project_price_list"}, default_currency)
        existing = entries.get(str(code))
        if existing is not None:
            # Two different prices for one code: reported, never silently picked (Codex's rule, kept on merge).
            if (existing.material_unit_price, existing.labour_unit_price) != (price.material_unit_price, price.labour_unit_price):
                raise ValueError(f"conflicting project price entries for {code}")
            continue
        if price.material_unit_price is not None or price.labour_unit_price is not None:
            entries[str(code)] = price
    return entries


def effective_prices(doc) -> dict[str, PriceEntry]:
    """Prices used to cost the project: the user's common price book (``quantities.price_book``, kept once for
    every project) overridden code by code by this project's own book.  Nothing is invented."""
    from archforge.quantities.price_book import load
    out = {code: PriceEntry(material_unit_price=v["material"], labour_unit_price=v["labour"], source="price_book")
           for code, v in load().items()}
    out.update(project_prices(doc))
    return out


def serialize_prices(prices: Mapping[str, PriceEntry]) -> dict[str, dict]:
    """Serialize price entries for the project ``price_list.entries`` field."""
    out = {}
    for code, price in prices.items():
        if not str(code):
            raise ValueError("price-book code must not be empty")
        material = _optional_non_negative(price.material_unit_price, "material_unit_price")
        labour = _optional_non_negative(price.labour_unit_price, "labour_unit_price")
        out[str(code)] = {
            "material_unit_price": material,
            "labour_unit_price": labour,
            "currency": str(price.currency or "EUR"),
            "source": str(price.source or "user"),
        }
    return out


def price_list_params(prices: Mapping[str, PriceEntry], vat=0.0, currency="EUR") -> dict:
    """Build validated params for creating/updating the project's price_list."""
    vat = float(vat)
    if vat < 0:
        raise ValueError("vat must be >= 0")
    return {
        "vat": vat,
        "currency": str(currency or "EUR"),
        "entries": serialize_prices(prices),
    }


def set_project_prices(stack, doc, prices: Mapping[str, PriceEntry], *, vat=None, currency=None):
    """Create/update the single project price list through CommandStack.

    The first edit creates one ``price_list`` entity. Later edits update that
    same entity, so there is never a hidden second price source. Returns its id.
    """
    from archforge.core.commands import AddEntity, UpdateEntity
    from archforge.core.model import Entity

    existing = project_price_list(doc)
    if existing is None:
        params = price_list_params(
            prices,
            vat=0.0 if vat is None else vat,
            currency="EUR" if currency is None else currency,
        )
        entity = Entity("price_list", params, name="Project prices")
        stack.execute(AddEntity(entity))
        return entity.id

    current_vat = float(existing.params.get("vat", 0.0))
    current_currency = str(existing.params.get("currency", "EUR") or "EUR")
    params = price_list_params(
        prices,
        vat=current_vat if vat is None else vat,
        currency=current_currency if currency is None else currency,
    )
    # Migrate on edit, keeping a single active representation. Undo restores
    # the complete original params, including old-format books.
    params.update(trade_prices={}, prices={})
    stack.execute(UpdateEntity(existing.id, params))
    return existing.id


def set_project_price(stack, doc, code: str, price: PriceEntry, *, vat=None):
    """Set one code-keyed project price, preserving all other project entries."""
    code = str(code)
    if not code:
        raise ValueError("price-book code must not be empty")
    prices = project_prices(doc)
    prices[code] = price
    existing = project_price_list(doc)
    currency = (
        str(existing.params.get("currency", "EUR") or "EUR")
        if existing is not None
        else str(price.currency or "EUR")
    )
    return set_project_prices(stack, doc, prices, vat=vat, currency=currency)


def update_project_price(
    stack,
    doc,
    code: str,
    *,
    material_unit_price=_UNSET,
    labour_unit_price=_UNSET,
    currency=_UNSET,
    source=_UNSET,
):
    """Edit selected fields of one price-book row without overwriting others.

    This is the safe backend for future spreadsheet-cell editing.  Passing
    ``None`` explicitly clears a component price; omitting a parameter preserves
    the existing value.
    """
    code = str(code)
    if not code:
        raise ValueError("price-book code must not be empty")
    prices = project_prices(doc)
    old = prices.get(code, PriceEntry())
    new = PriceEntry(
        material_unit_price=(
            old.material_unit_price
            if material_unit_price is _UNSET
            else _optional_non_negative(material_unit_price, "material_unit_price")
        ),
        labour_unit_price=(
            old.labour_unit_price
            if labour_unit_price is _UNSET
            else _optional_non_negative(labour_unit_price, "labour_unit_price")
        ),
        currency=old.currency if currency is _UNSET else str(currency or "EUR"),
        source=old.source if source is _UNSET else str(source or "user"),
    )
    return set_project_price(stack, doc, code, new)


def remove_project_price(stack, doc, code: str):
    """Remove one price entry through CommandStack; missing codes are a no-op."""
    code = str(code)
    prices = project_prices(doc)
    if code not in prices:
        return False
    prices.pop(code)
    set_project_prices(stack, doc, prices)
    return True


def price_book_audit(quantities: Iterable[QuantityLine], prices: Mapping[str, PriceEntry]) -> dict:
    """Compare current model requirements with the project price book.

    This flags missing, partial and unused price entries without inventing a
    replacement.  It is useful both for the professional spreadsheet and for a
    pre-offer completeness check.
    """
    quantities = list(quantities)
    required = {str(q.code) for q in quantities}
    available = {str(code) for code in prices}
    missing = sorted(required - available)
    unused = sorted(available - required)
    partial = sorted(
        code
        for code in required & available
        if prices[code].material_unit_price is None or prices[code].labour_unit_price is None
    )
    currencies = sorted({str(prices[code].currency or "EUR") for code in required & available})
    return {
        "required_codes": sorted(required),
        "missing_codes": missing,
        "partial_codes": partial,
        "unused_codes": unused,
        "currencies": currencies,
        "complete": not missing and not partial and len(currencies) <= 1,
    }


def migrate_description_prices(
    quantities: Iterable[QuantityLine],
    legacy_prices: Mapping[str, float],
    *,
    component="material",
    currency="EUR",
    source="legacy_project_price",
) -> dict[str, PriceEntry]:
    """Convert old description-keyed unit prices to code-keyed entries.

    Migration is conservative: a legacy description is used only when exactly
    one current item code has that description. Ambiguous descriptions are
    skipped rather than guessed. ``component`` selects whether the old price
    represented material or labour.
    """
    if component not in {"material", "labour"}:
        raise ValueError("component must be material or labour")
    by_description: dict[str, list[str]] = {}
    for q in quantities:
        by_description.setdefault(str(q.description), []).append(str(q.code))
    out = {}
    for description, raw_price in legacy_prices.items():
        codes = sorted(set(by_description.get(str(description), ())))
        if len(codes) != 1:
            continue
        value = _optional_non_negative(raw_price, "legacy unit price")
        kwargs = {
            "material_unit_price": value if component == "material" else None,
            "labour_unit_price": value if component == "labour" else None,
            "currency": currency,
            "source": source,
        }
        out[codes[0]] = PriceEntry(**kwargs)
    return out
