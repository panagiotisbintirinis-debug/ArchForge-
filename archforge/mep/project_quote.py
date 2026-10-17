"""Project-wide commercial quote assembled from the shared trade-costing rows.

There is deliberately no second pricing calculation here. Each trade produces
``QuantityLine`` objects and uses the common ``trade_costing`` engine with the
one project price book. This module only gathers those already-priced rows.
"""
from __future__ import annotations

from collections.abc import Iterable

from archforge.mep.project_pricebook import effective_prices, price_book_audit, project_price_list, project_prices
from archforge.mep.trade_costing import combine_trade_quotes


TRADE_PROVIDERS = {
    "plumbing": "archforge.mep.plumbing_costing:plumbing_quote",
    "heating": "archforge.mep.heating:heating_quote",
}


def _provider(name):
    if name == "plumbing":
        from archforge.mep.plumbing_costing import plumbing_quote
        return plumbing_quote
    if name == "heating":
        from archforge.mep.heating import heating_quote
        return heating_quote
    raise KeyError(f"unsupported project quote trade: {name}")


def project_quote(doc, trades: Iterable[str] = ("plumbing", "heating")) -> dict:
    """Return one project quote for the requested supported trades.

    Prices are resolved once from the single project ``price_list`` and passed
    to every trade. Missing entries remain missing; no trade can fall back to a
    private/default price source through this path.
    """
    prices = effective_prices(doc)
    trade_quotes = {}
    all_quantities = []
    for trade in trades:
        trade = str(trade)
        quote = _provider(trade)(doc, prices)
        trade_quotes[trade] = quote
        all_quantities.extend(quote.get("quantities", ()))

    combined = combine_trade_quotes(trade_quotes)
    audit = price_book_audit(all_quantities, prices)
    price_entity = project_price_list(doc)
    vat = float(price_entity.params.get("vat", 0.0)) if price_entity is not None else 0.0
    if vat < 0:
        raise ValueError("project price-list VAT must be >= 0")
    net = float(combined["summary"]["subtotal"])
    vat_amount = round(net * vat / 100.0, 2)
    gross = round(net + vat_amount, 2)
    pricing_complete = bool(combined["summary"]["complete"] and audit["complete"])
    combined.update({
        "trades": trade_quotes,
        "price_book_audit": audit,
        "vat_pct": vat,
        "vat_amount": vat_amount,
        "gross_total": gross,
        "pricing_complete": pricing_complete,
        "commercial_note": (
            "Complete quote" if pricing_complete
            else "Partial priced total: one or more project price-book entries are missing or incomplete"
        ),
    })
    return combined
