"""Shared trade costing primitives for ArchForge MEP modules.

This module intentionally contains **no catalogue prices and no engineering
constants**. Geometry/MEP modules provide quantities; the professional enters
unit prices and labour rates. The same calculation path can therefore be used
by plumbing, heating/HVAC, electrical and later construction trades.

Trust rule: quantities may come from the authoritative model, but a missing
price is never guessed. Missing prices stay missing and are reported.

A quantity line is also explainable: it can carry a plain-language reason,
rule status and provenance. That lets the same project data serve both the
professional and the owner without maintaining a second quote model.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Mapping


@dataclass(frozen=True)
class QuantityLine:
    code: str
    description: str
    category: str
    quantity: float
    unit: str
    trade: str
    source: str = "model"
    owner_explanation: str = ""
    rule_status: str = "MODEL_QUANTITY"
    rule_source: str = ""
    selection_basis: str = "model"


@dataclass(frozen=True)
class PriceEntry:
    material_unit_price: float | None = None
    labour_unit_price: float | None = None
    currency: str = "EUR"
    source: str = "user"


def _non_negative(value: float, label: str) -> float:
    value = float(value)
    if value < 0:
        raise ValueError(f"{label} must be >= 0")
    return value


def cost_lines(
    quantities: Iterable[QuantityLine],
    prices: Mapping[str, PriceEntry],
) -> list[dict]:
    """Price model-derived quantities without inventing missing unit prices.

    Each returned row carries the unit prices as well as extended costs.  This
    keeps the spreadsheet/BOM, professional quote and owner view on the exact
    same authoritative priced row instead of maintaining parallel tables.
    """
    out: list[dict] = []
    for q in quantities:
        qty = _non_negative(q.quantity, "quantity")
        p = prices.get(q.code)
        material_unit = None
        labour_unit = None
        material = None
        labour = None
        currency = "EUR"
        price_source = "missing"
        if p is not None:
            currency = p.currency
            price_source = p.source
            if p.material_unit_price is not None:
                material_unit = _non_negative(p.material_unit_price, "material_unit_price")
                material = qty * material_unit
            if p.labour_unit_price is not None:
                labour_unit = _non_negative(p.labour_unit_price, "labour_unit_price")
                labour = qty * labour_unit
        total = None if material is None and labour is None else (material or 0.0) + (labour or 0.0)
        fully_priced = bool(p is not None and material_unit is not None and labour_unit is not None)
        partially_priced = bool(total is not None and not fully_priced)
        row = asdict(q)
        row.update(
            material_unit_price=None if material_unit is None else round(material_unit, 4),
            labour_unit_price=None if labour_unit is None else round(labour_unit, 4),
            material_cost=None if material is None else round(material, 2),
            labour_cost=None if labour is None else round(labour, 2),
            total_cost=None if total is None else round(total, 2),
            currency=currency,
            price_source=price_source,
            complete_price=fully_priced,
            partial_price=partially_priced,
        )
        out.append(row)
    return out


def quote_summary(rows: Iterable[dict]) -> dict:
    """Return totals while explicitly distinguishing complete/partial pricing."""
    rows = list(rows)
    currencies = {str(r.get("currency", "EUR")) for r in rows if r.get("total_cost") is not None}
    if len(currencies) > 1:
        raise ValueError("quote contains more than one currency")
    currency = next(iter(currencies), "EUR")
    material = sum(float(r["material_cost"]) for r in rows if r.get("material_cost") is not None)
    labour = sum(float(r["labour_cost"]) for r in rows if r.get("labour_cost") is not None)
    unpriced = [r["code"] for r in rows if not r.get("complete_price", False)]
    missing = [r["code"] for r in rows if r.get("total_cost") is None]
    partial = [r["code"] for r in rows if r.get("partial_price", False)]
    complete_rows = [r for r in rows if r.get("complete_price", False)]
    complete_subtotal = sum(float(r.get("total_cost") or 0.0) for r in complete_rows)
    by_category: dict[str, float] = {}
    by_trade: dict[str, float] = {}
    for r in rows:
        if r.get("total_cost") is not None:
            category = str(r.get("category", "Other"))
            trade = str(r.get("trade", "other"))
            by_category[category] = by_category.get(category, 0.0) + float(r["total_cost"])
            by_trade[trade] = by_trade.get(trade, 0.0) + float(r["total_cost"])
    return {
        "currency": currency,
        "material_cost": round(material, 2),
        "labour_cost": round(labour, 2),
        "subtotal": round(material + labour, 2),
        "complete_priced_subtotal": round(complete_subtotal, 2),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items())},
        "by_trade": {k: round(v, 2) for k, v in sorted(by_trade.items())},
        "unpriced_codes": unpriced,
        "missing_price_codes": missing,
        "partial_price_codes": partial,
        "complete": not unpriced,
    }


def combine_trade_quotes(quotes: Mapping[str, dict]) -> dict:
    """Combine trade quotes without recalculating or changing their priced rows.

    ``quotes`` may contain plumbing, heating, electrical and later trades.  The
    returned rows are the original shared-costing rows; therefore there is one
    commercial calculation path for professional and owner views.
    """
    rows = []
    per_trade = {}
    for trade, quote in quotes.items():
        trade_rows = list(quote.get("rows", ()))
        rows.extend(trade_rows)
        per_trade[str(trade)] = quote_summary(trade_rows)
    return {
        "rows": rows,
        "summary": quote_summary(rows),
        "by_trade": per_trade,
        "owner_view": owner_quote_view(rows),
    }


def owner_quote_view(rows: Iterable[dict]) -> list[dict]:
    """Compact owner-facing view from the exact same priced rows.

    No technical data or price is recalculated here; this is only a different
    presentation of the authoritative quote rows.
    """
    view = []
    for row in rows:
        view.append({
            "code": row.get("code", ""),
            "item": row.get("description", ""),
            "why": row.get("owner_explanation", ""),
            "quantity": row.get("quantity"),
            "unit": row.get("unit", ""),
            "material_unit_price": row.get("material_unit_price"),
            "labour_unit_price": row.get("labour_unit_price"),
            "material_cost": row.get("material_cost"),
            "labour_cost": row.get("labour_cost"),
            "total_cost": row.get("total_cost"),
            "currency": row.get("currency", "EUR"),
            "price_source": row.get("price_source", "missing"),
            "rule_status": row.get("rule_status", ""),
            "rule_source": row.get("rule_source", ""),
            "selection_basis": row.get("selection_basis", ""),
            "priced": bool(row.get("complete_price", False)),
            "partial_price": bool(row.get("partial_price", False)),
        })
    return view
