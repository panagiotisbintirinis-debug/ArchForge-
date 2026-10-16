"""Spreadsheet-style BOM projection for every ArchForge trade.

This module is presentation/export only.  It never derives quantities or costs;
it projects the authoritative rows produced by ``trade_costing.cost_lines``.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, TextIO


BOM_COLUMNS = (
    ("code", "Κωδικός"),
    ("description", "Περιγραφή"),
    ("trade", "Επάγγελμα"),
    ("category", "Κατηγορία"),
    ("quantity", "Ποσότητα"),
    ("unit", "Μονάδα"),
    ("material_unit_price", "Υλικό / μον."),
    ("labour_unit_price", "Εργασία / μον."),
    ("material_cost", "Υλικό"),
    ("labour_cost", "Εργασία"),
    ("total_cost", "Σύνολο"),
    ("currency", "Νόμισμα"),
    ("pricing_status", "Τιμολόγηση"),
    ("price_source", "Πηγή τιμής"),
    ("rule_status", "Κατάσταση κανόνα"),
    ("rule_source", "Πηγή κανόνα"),
)


def pricing_status(row: dict) -> str:
    if row.get("complete_price"):
        return "complete"
    if row.get("partial_price"):
        return "partial"
    return "missing"


def bom_rows(rows: Iterable[dict]) -> list[dict]:
    """Return spreadsheet rows from already-priced authoritative quote rows."""
    out = []
    for source in rows:
        row = dict(source)
        projected = {key: row.get(key) for key, _label in BOM_COLUMNS if key != "pricing_status"}
        projected["pricing_status"] = pricing_status(row)
        # Keep column order deterministic for UI/export consumers.
        out.append({key: projected.get(key) for key, _label in BOM_COLUMNS})
    return out


def _write_csv_stream(rows: Iterable[dict], stream: TextIO) -> None:
    rows = bom_rows(rows)
    keys = [key for key, _label in BOM_COLUMNS]
    labels = [label for _key, label in BOM_COLUMNS]
    writer = csv.writer(stream)
    writer.writerow(labels)
    for row in rows:
        writer.writerow(["" if row.get(key) is None else row.get(key) for key in keys])


def export_bom_csv(rows: Iterable[dict], target) -> None:
    """Export BOM rows to UTF-8 CSV suitable for spreadsheet applications.

    ``target`` may be a writable text stream or a filesystem path.  Missing
    values stay blank; no zero/default is substituted for a missing price.
    """
    if hasattr(target, "write"):
        _write_csv_stream(rows, target)
        return
    path = Path(target)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        _write_csv_stream(rows, stream)
