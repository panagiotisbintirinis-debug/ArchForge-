"""Common price book (owner 17/10): the professional's own prices, kept once and read by every project.

``{code: {"material": €/unit | None, "labour": €/unit | None}}`` in the user's data folder
(``price_book.json``).  A project's own price list overrides it code by code.  Nothing here ever invents a
price: the book starts empty and holds only what the user saved into it; a missing price stays missing.
"""
from __future__ import annotations

import datetime
import json

FILE = "price_book.json"


def path():
    from archforge.library.assets import data_dir
    return data_dir() / FILE


def load():
    """The saved prices, or {} when there is no book (or it cannot be read)."""
    try:
        raw = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for code, v in (raw.get("trade_prices") or {}).items():
        if not isinstance(v, dict):
            continue
        m, lab = v.get("material"), v.get("labour")
        entry = {"material": None if m is None else float(m), "labour": None if lab is None else float(lab)}
        if entry["material"] is not None or entry["labour"] is not None:
            out[str(code)] = entry
    return out


def save(prices):
    """Merge ``prices`` (``{code: {"material", "labour"}}``) into the book; returns how many codes were written."""
    book = load()
    n = 0
    for code, v in prices.items():
        entry = {"material": v.get("material"), "labour": v.get("labour")}
        if entry["material"] is None and entry["labour"] is None:
            continue
        book[str(code)] = {k: (None if x is None else float(x)) for k, x in entry.items()}
        n += 1
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"updated": datetime.date.today().isoformat(), "trade_prices": book},
                            ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return n


def save_project_prices(doc):
    """«Στον κοινό τιμοκατάλογο»: the project's own prices go to the book (the project keeps them too)."""
    from archforge.quantities.quote import price_entity
    e = price_entity(doc)
    return save(dict((e.params.get("trade_prices") or {}) if e else {}))
