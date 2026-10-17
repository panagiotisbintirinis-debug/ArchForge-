"""The quote: every measured item with the professional's unit prices (material + labour), VAT and totals.

One costing path for every trade (owner 15/10: «την καλύτερη λύση … που καλύπτει πελάτη και τεχνίτη»):
the quantity lists of ``quantities.materials`` become ``mep.trade_costing.QuantityLine`` rows, priced with
the project's price book by ``cost_lines`` — material and labour per unit, missing prices never guessed —
and shown two ways from the same rows: the professional's lines and the owner's view (why each line exists,
the status of the rule behind it).

Prices, the client, VAT and notes live in the Document (one ``price_list`` entity, undoable, saved with the
project).  ``trade_prices`` = ``{code: {"material": €/unit, "labour": €/unit}}``; codes come from the trade
modules (e.g. ``electrical.breaker.16A``) or, for lists without codes yet, ``desc:<description>``.  Older
projects' ``prices`` (description → unit price) are read as the material price of ``desc:<description>``.
"""
from __future__ import annotations

DEFAULT_VAT = 24.0


def price_entity(doc):
    return next((e for e in doc.entities.values() if e.kind == "price_list"), None)


def row_meta(row):
    """``(description, unit, quantity, meta)`` for a list row of 3 or 4 items; meta has code / why / status / source."""
    desc, unit, qty = row[0], row[1], row[2]
    meta = dict(row[3]) if len(row) > 3 and row[3] else {}
    meta.setdefault("code", "desc:" + str(desc))
    return desc, unit, qty, meta


def trade_prices(doc):
    """``{code: {"material": x|None, "labour": y|None}}`` — legacy description prices included as material."""
    from archforge.mep.project_pricebook import project_prices
    return {code: {'material': price.material_unit_price, 'labour': price.labour_unit_price}
            for code, price in project_prices(doc).items()}


def settings(doc):
    e = price_entity(doc)
    p = dict(e.params) if e else {}
    book = trade_prices(doc)
    # Description view (Excel price column, older callers): material + labour per unit of desc-coded items.
    prices = {code[5:]: (v["material"] or 0.0) + (v["labour"] or 0.0) for code, v in book.items()
              if code.startswith("desc:") and (v["material"] is not None or v["labour"] is not None)}
    return {"prices": prices, "trade_prices": book, "client": str(p.get("client", "")), "project": str(p.get("project", "")),
            "vat": float(p.get("vat", DEFAULT_VAT)), "notes": str(p.get("notes", "")),
            "validity_days": int(p.get("validity_days", 30))}


def _price_entries(doc):
    from archforge.mep.project_pricebook import project_prices
    return project_prices(doc)


def costed(doc, name, rows):
    """Rows of one list priced through ``trade_costing``: dicts with description, unit, quantity, code, why, status,
    price (material + labour per unit), material, labour, amount; quantity None = from the study, never priced."""
    from archforge.mep.trade_costing import QuantityLine, cost_lines
    entries = _price_entries(doc)
    out = []
    for row in rows:
        desc, unit, qty, meta = row_meta(row)
        base = {"description": desc, "unit": unit, "quantity": qty, "code": meta["code"], "why": meta.get("why", ""),
                "status": meta.get("status", "MODEL_QUANTITY"), "source": meta.get("source", "")}
        if qty is None:
            out.append({**base, "price": None, "material": None, "labour": None, "amount": None, "complete": False})
            continue
        line = QuantityLine(code=meta["code"], description=str(desc), category=name, quantity=float(qty), unit=str(unit),
                            trade=name, owner_explanation=base["why"], rule_status=base["status"], rule_source=base["source"])
        c = cost_lines([line], entries)[0]
        e = entries.get(meta["code"])
        unit_price = None
        if e is not None and (e.material_unit_price is not None or e.labour_unit_price is not None):
            unit_price = (e.material_unit_price or 0.0) + (e.labour_unit_price or 0.0)
        out.append({**base, "price": unit_price, "material": c["material_cost"], "labour": c["labour_cost"],
                    "amount": c["total_cost"], "complete": c["complete_price"]})
    return out


def quote(doc, only=None):
    """``{"sections": [(title, [row…])], "subtotal", "material", "labour", "vat", "total", "missing", "owner_view", …}``.

    ``only``: sheet names to quote (e.g. ``("Ηλεκτρολογικά",)`` for the electrician's quote); None = everything.
    """
    from archforge.quantities.materials import all_lists
    s = settings(doc)
    sections, owner = [], []
    for name, title, rows, _notes in all_lists(doc):
        if only is not None and name not in only:
            continue
        out = costed(doc, name, rows)
        sections.append((title, out))
        owner += [{"trade": name, "item": r["description"], "why": r["why"], "quantity": r["quantity"], "unit": r["unit"],
                   "total": r["amount"], "status": r["status"], "priced": r["amount"] is not None} for r in out]
    rows = [r for _t, sec in sections for r in sec]
    subtotal = round(sum(r["amount"] for r in rows if r["amount"] is not None), 2)
    material = round(sum(r["material"] for r in rows if r["material"] is not None), 2)
    labour = round(sum(r["labour"] for r in rows if r["labour"] is not None), 2)
    missing = sum(1 for r in rows if r["amount"] is None)
    vat_amount = round(subtotal * s["vat"] / 100, 2)
    return {"sections": sections, "subtotal": subtotal, "material": material, "labour": labour, "vat": s["vat"],
            "vat_amount": vat_amount, "total": round(subtotal + vat_amount, 2), "missing": missing,
            "incomplete": sum(1 for r in rows if r["amount"] is not None and not r["complete"]),
            "owner_view": owner, "client": s["client"], "project": s["project"], "notes": s["notes"],
            "validity_days": s["validity_days"]}


def money(v):
    """1234.5 → '1.234,50 €' (Greek format)."""
    if v is None:
        return "—"
    whole, frac = f"{float(v):,.2f}".split(".")
    return whole.replace(",", ".") + "," + frac + " €"


def priced(doc, rows, name=""):
    """Cost of list rows with the project's prices: ``{"total", "material", "labour", "missing", "priced"}``.

    Only the user's prices; an item with no price or no quantity is in ``missing`` (never guessed).
    """
    out = costed(doc, name, rows)
    done = [r for r in out if r["amount"] is not None]
    return {"total": round(sum(r["amount"] for r in done), 2),
            "material": round(sum(r["material"] or 0.0 for r in done), 2),
            "labour": round(sum(r["labour"] or 0.0 for r in done), 2),
            "missing": [r["description"] for r in out if r["amount"] is None], "priced": len(done)}
