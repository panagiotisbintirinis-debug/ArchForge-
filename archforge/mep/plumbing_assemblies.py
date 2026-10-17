"""Explicit plumbing connection assemblies for fixtures, appliances and sources.

An assembly is NOT inferred from trade habit.  It is stored on a plumbing point
only after a professional/user selects a concrete construction solution or a
manufacturer-backed assembly.  This module converts those explicit components
into grouped BOM quantities and a per-point detail view.

Point parameter contract::

    connection_assembly = {
        "name": "...",
        "source_kind": "professional_selection" | "manufacturer_data" | ...,
        "rule_status": "MODEL_SELECTED" | "MANUFACTURER_DATA" | ...,
        "rule_source": "...",
        "components": [
            {
                "accessory_type": "angle_stop",
                "quantity": 2,
                "unit": "pcs",
                "manufacturer": "...",      # optional
                "product_ref": "...",       # optional
                "description": "...",       # optional override
            },
        ],
    }

No default component quantities live here.  Missing assembly means missing
construction detail, not permission to guess.
"""
from __future__ import annotations

from collections import defaultdict

from archforge.mep.plumbing import POINT_TYPES, plumbing_points
from archforge.mep.plumbing_accessories import ACCESSORY_TYPES
from archforge.mep.trade_costing import QuantityLine


def connection_assembly(point) -> dict:
    raw = point.params.get("connection_assembly") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def connection_assembly_details(doc) -> list[dict]:
    """Return owner/professional detail rows without inventing components."""
    rows: list[dict] = []
    for point in plumbing_points(doc):
        p = point.params
        point_type = str(p.get("point_type", ""))
        label = POINT_TYPES.get(point_type, (point_type,))[0]
        assembly = connection_assembly(point)
        components = assembly.get("components") or []
        base = {
            "point_id": str(point.id),
            "point_type": point_type,
            "point_label": point.name or label,
            "assembly_name": str(assembly.get("name", "")),
            "source_kind": str(assembly.get("source_kind", "")),
            "rule_status": str(assembly.get("rule_status", "UNCONFIGURED" if not assembly else "MODEL_SELECTED")),
            "rule_source": str(assembly.get("rule_source", "")),
        }
        if not components:
            rows.append({**base, "configured": False, "component": None})
            continue
        for component in components:
            if not isinstance(component, dict):
                continue
            accessory_type = str(component.get("accessory_type", "unspecified"))
            default_label, why = ACCESSORY_TYPES.get(
                accessory_type,
                (accessory_type, "Εξάρτημα που έχει δηλωθεί ρητά στη σύνδεση."),
            )
            qty = float(component.get("quantity", 1.0))
            if qty < 0:
                raise ValueError("connection assembly component quantity must be >= 0")
            rows.append({
                **base,
                "configured": True,
                "component": {
                    "accessory_type": accessory_type,
                    "description": str(component.get("description") or default_label),
                    "why": str(component.get("owner_explanation") or why),
                    "quantity": qty,
                    "unit": str(component.get("unit", "pcs")),
                    "manufacturer": str(component.get("manufacturer", "")),
                    "product_ref": str(component.get("product_ref", "")),
                    "source_kind": str(component.get("source_kind", base["source_kind"] or "model")),
                    "rule_status": str(component.get("rule_status", base["rule_status"] or "MODEL_SELECTED")),
                    "rule_source": str(component.get("rule_source", base["rule_source"])),
                },
            })
    return rows


def connection_assembly_quantities(doc) -> list[QuantityLine]:
    """Aggregate selected connection components into purchase-friendly BOM lines."""
    grouped: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    meta: dict[tuple[str, str, str, str, str], dict] = {}

    for row in connection_assembly_details(doc):
        comp = row.get("component")
        if not comp:
            continue
        key = (
            str(comp["accessory_type"]),
            str(comp["unit"]),
            str(comp.get("manufacturer", "")),
            str(comp.get("product_ref", "")),
            str(comp.get("description", "")),
        )
        grouped[key] += float(comp["quantity"])
        meta[key] = {**row, "component": dict(comp)}

    lines: list[QuantityLine] = []
    for key, qty in sorted(grouped.items()):
        accessory_type, unit, manufacturer, product_ref, description = key
        row = meta[key]
        comp = row["component"]
        suffix = ""
        if manufacturer or product_ref:
            suffix = " — " + " / ".join(x for x in (manufacturer, product_ref) if x)
        code_tail = accessory_type + ("." + product_ref.replace(" ", "_") if product_ref else "")
        lines.append(QuantityLine(
            code=f"plumbing.connection_component.{code_tail}",
            description=description + suffix,
            category="Εξαρτήματα συνδέσεων",
            quantity=round(qty, 3),
            unit=unit,
            trade="plumbing",
            source="connection_assembly",
            owner_explanation=str(comp.get("why", "")),
            rule_status=str(comp.get("rule_status", "MODEL_SELECTED")),
            rule_source=str(comp.get("rule_source", "")),
            selection_basis=str(comp.get("source_kind", "model")),
        ))
    return lines
