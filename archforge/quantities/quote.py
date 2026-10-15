"""The client quote: every measured item with the contractor's unit price, VAT and totals.

Prices, the client, VAT and notes live in the Document (one ``price_list``
entity, undoable, saved with the project) — keyed by the item's description,
so a price typed once stays when the quantities change.  Items without a
price are listed but not counted (the quote says how many are missing).
"""
from __future__ import annotations

DEFAULT_VAT = 24.0


def price_entity(doc):
    return next((e for e in doc.entities.values() if e.kind == "price_list"), None)


def settings(doc):
    e = price_entity(doc)
    p = dict(e.params) if e else {}
    return {"prices": dict(p.get("prices") or {}), "client": str(p.get("client", "")), "project": str(p.get("project", "")),
            "vat": float(p.get("vat", DEFAULT_VAT)), "notes": str(p.get("notes", "")),
            "validity_days": int(p.get("validity_days", 30))}


def quote(doc):
    """``{"sections": [(name, [row…])], "subtotal", "vat", "vat_amount", "total", "missing", …}``."""
    from archforge.quantities.materials import all_lists
    s = settings(doc)
    sections, subtotal, missing = [], 0.0, 0
    for name, title, rows, _notes in all_lists(doc):
        out = []
        for desc, unit, qty in rows:
            price = s["prices"].get(desc)
            amount = round(float(qty) * float(price), 2) if (qty is not None and price is not None) else None
            if amount is None:
                missing += 1
            else:
                subtotal += amount
            out.append({"description": desc, "unit": unit, "quantity": qty, "price": price, "amount": amount})
        sections.append((title, out))
    subtotal = round(subtotal, 2)
    vat_amount = round(subtotal * s["vat"] / 100, 2)
    return {"sections": sections, "subtotal": subtotal, "vat": s["vat"], "vat_amount": vat_amount,
            "total": round(subtotal + vat_amount, 2), "missing": missing, "client": s["client"], "project": s["project"],
            "notes": s["notes"], "validity_days": s["validity_days"]}


def money(v):
    """1234.5 → '1.234,50 €' (Greek format)."""
    if v is None:
        return "—"
    whole, frac = f"{float(v):,.2f}".split(".")
    return whole.replace(",", ".") + "," + frac + " €"


def priced(doc, rows):
    """Cost of ``[(description, unit, quantity)]`` with the project's prices: ``{"total", "missing", "priced"}``.

    Only the user's prices; an item with no price or no quantity is counted in ``missing`` (never guessed).
    """
    prices = settings(doc)["prices"]
    total, missing, done = 0.0, [], 0
    for desc, _unit, qty in rows:
        price = prices.get(desc)
        if qty is None or price is None:
            missing.append(desc)
        else:
            total += float(qty) * float(price)
            done += 1
    return {"total": round(total, 2), "missing": missing, "priced": done}
