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
    """Price model-derived quantities without inventing missing unit prices."""
    out: list[dict] = []
    for q in quantities:
        qty = _non_negative(q.quantity, "quantity")
        p = prices.get(q.code)
        material = None
        labour = None
        currency = "EUR"
        price_source = "missing"
        if p is not None:
            currency = p.currency
            price_source = p.source
            if p.material_unit_price is not None:
                material = qty * _non_negative(p.material_unit_price, "material_unit_price")
            if p.labour_unit_price is not None:
                labour = qty * _non_negative(p.labour_unit_price, "labour_unit_price")
        total = None if material is None and labour is None else (material or 0.0) + (labour or 0.0)
        row = asdict(q)
        row.update(
            material_cost=None if material is None else round(material, 2),
            labour_cost=None if labour is None else round(labour, 2),
            total_cost=None if total is None else round(total, 2),
            currency=currency,
            price_source=price_source,
            complete_price=bool(p is not None and p.material_unit_price is not None and p.labour_unit_price is not None),
        )
        out.append(row)
    return out


def quote_summary(rows: Iterable[dict]) -> dict:
    """Return material/labour totals and explicitly list unpriced lines."""
    rows = list(rows)
    currencies = {str(r.get("currency", "EUR")) for r in rows if r.get("total_cost") is not None}
    if len(currencies) > 1:
        raise ValueError("quote contains more than one currency")
    currency = next(iter(currencies), "EUR")
    material = sum(float(r["material_cost"]) for r in rows if r.get("material_cost") is not None)
    labour = sum(float(r["labour_cost"]) for r in rows if r.get("labour_cost") is not None)
    unpriced = [r["code"] for r in rows if not r.get("complete_price", False)]
    by_category: dict[str, float] = {}
    for r in rows:
        if r.get("total_cost") is not None:
            key = str(r.get("category", "Other"))
            by_category[key] = by_category.get(key, 0.0) + float(r["total_cost"])
    return {
        "currency": currency,
        "material_cost": round(material, 2),
        "labour_cost": round(labour, 2),
        "subtotal": round(material + labour, 2),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items())},
        "unpriced_codes": unpriced,
        "complete": not unpriced,
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
            "material_cost": row.get("material_cost"),
            "labour_cost": row.get("labour_cost"),
            "total_cost": row.get("total_cost"),
            "currency": row.get("currency", "EUR"),
            "rule_status": row.get("rule_status", ""),
            "rule_source": row.get("rule_source", ""),
            "selection_basis": row.get("selection_basis", ""),
            "priced": bool(row.get("complete_price", False)),
        })
    return view
