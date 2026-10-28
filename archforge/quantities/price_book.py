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
    from archforge.project.persistence import UserDataError, read_user_json
    try:
        return _prices(read_user_json(path()))   # a damaged book is kept aside first, never overwritten blind (Α3)
    except UserDataError:
        return {}


def _prices(raw):
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
    """Merge ``prices`` (``{code: {"material", "labour"}}``) into the book; returns how many codes were written.

    ``UserDataError`` (nothing written) when the book exists but can neither be read nor kept aside."""
    from archforge.project.persistence import atomic_write_text, read_user_json
    book = _prices(read_user_json(path()))
    n = 0
    for code, v in prices.items():
        entry = {"material": v.get("material"), "labour": v.get("labour")}
        if entry["material"] is None and entry["labour"] is None:
            continue
        book[str(code)] = {k: (None if x is None else float(x)) for k, x in entry.items()}
        n += 1
    # Old file or new one, never half of it (a cut file used to cost the whole book on the next save).
    atomic_write_text(path(), json.dumps({"updated": datetime.date.today().isoformat(), "trade_prices": book},
                                         ensure_ascii=False, indent=1, sort_keys=True))
    return n


def save_project_prices(doc):
    """«Στον κοινό τιμοκατάλογο»: the project's own prices go to the book (the project keeps them too)."""
    from archforge.quantities.quote import project_prices
    return save(project_prices(doc))
