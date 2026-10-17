"""Explicit plumbing connection and manifold assemblies.

Assemblies are NEVER inferred from trade habit. They exist only after a
professional/user selects a concrete construction solution or a
manufacturer-backed assembly. This module converts those explicit components
into grouped BOM quantities and detailed owner/professional rows.

Point parameter contract::

    connection_assembly = {
        "name": "...",
        "source_kind": "professional_selection" | "manufacturer_data" | ...,
        "rule_status": "MODEL_SELECTED" | "MANUFACTURER_DATA" | ...,
        "rule_source": "...",
        "components": [{"accessory_type": "angle_stop", "quantity": 2, ...}],
    }

Derived manifold assemblies are stored on the cold-water supply point because
manifolds themselves are derived geometry, not independent authoritative
entities::

    manifold_assemblies = {
        "cold:<room-key>": { ... same assembly shape ... },
        "hot:<room-key>":  { ... },
    }

No default component quantities live here. Missing assembly means missing
construction detail, not permission to guess.
"""
from __future__ import annotations

from collections import defaultdict

from archforge.mep.plumbing import POINT_TYPES, plumbing_points, route_plumbing
from archforge.mep.plumbing_accessories import ACCESSORY_TYPES
from archforge.mep.trade_costing import QuantityLine


def connection_assembly(point) -> dict:
    raw = point.params.get("connection_assembly") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def _component_row(base: dict, component: dict) -> dict:
    accessory_type = str(component.get("accessory_type", "unspecified"))
    default_label, why = ACCESSORY_TYPES.get(
        accessory_type,
        (accessory_type, "Εξάρτημα που έχει δηλωθεί ρητά στη σύνδεση."),
    )
    qty = float(component.get("quantity", 1.0))
    if qty < 0:
        raise ValueError("plumbing assembly component quantity must be >= 0")
    return {
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
            "source_kind": str(component.get("source_kind", base.get("source_kind") or "model")),
            "rule_status": str(component.get("rule_status", base.get("rule_status") or "MODEL_SELECTED")),
            "rule_source": str(component.get("rule_source", base.get("rule_source") or "")),
        },
    }


def connection_assembly_details(doc) -> list[dict]:
    """Return owner/professional point-connection rows without guessing parts."""
    rows: list[dict] = []
    for point in plumbing_points(doc):
        p = point.params
        point_type = str(p.get("point_type", ""))
        label = POINT_TYPES.get(point_type, (point_type,))[0]
        assembly = connection_assembly(point)
        components = assembly.get("components") or []
        base = {
            "scope": "point",
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
            if isinstance(component, dict):
                rows.append(_component_row(base, component))
    return rows


def manifold_key(manifold: dict) -> str:
    """Stable-enough key for the derived manifold within the selected layout."""
    return f"{str(manifold.get('system', 'cold'))}:{str(manifold.get('room', ''))}"


def _water_supply(doc):
    return next(
        (e for e in plumbing_points(doc) if str(e.params.get("point_type", "")) == "water_supply"),
        None,
    )


def manifold_assembly_details(doc) -> list[dict]:
    """Return one row set per derived manifold and its explicitly selected parts."""
    routed = route_plumbing(doc)
    supply = _water_supply(doc)
    store = {}
    if supply is not None and isinstance(supply.params.get("manifold_assemblies"), dict):
        store = supply.params.get("manifold_assemblies") or {}

    rows: list[dict] = []
    for manifold in routed.get("manifolds", ()):
        key = manifold_key(manifold)
        raw = store.get(key) or {}
        assembly = dict(raw) if isinstance(raw, dict) else {}
        components = assembly.get("components") or []
        system = str(manifold.get("system", "cold"))
        outlets = list(manifold.get("outlets", ()))
        label = f"Συλλέκτης {'κρύου' if system == 'cold' else 'ζεστού'} — {len(outlets)} εξόδων"
        base = {
            "scope": "manifold",
            "manifold_key": key,
            "supply_id": str(supply.id) if supply is not None else "",
            "system": system,
            "outlet_ids": outlets,
            "point_label": label,
            "assembly_name": str(assembly.get("name", "")),
            "source_kind": str(assembly.get("source_kind", "")),
            "rule_status": str(assembly.get("rule_status", "UNCONFIGURED" if not assembly else "MODEL_SELECTED")),
            "rule_source": str(assembly.get("rule_source", "")),
        }
        if not components:
            rows.append({**base, "configured": False, "component": None})
            continue
        for component in components:
            if isinstance(component, dict):
                rows.append(_component_row(base, component))
    return rows


def _aggregate_component_rows(rows: list[dict], code_prefix: str, category: str, source: str) -> list[QuantityLine]:
    grouped: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    meta: dict[tuple[str, str, str, str, str], dict] = {}

    for row in rows:
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
            code=f"{code_prefix}.{code_tail}",
            description=description + suffix,
            category=category,
            quantity=round(qty, 3),
            unit=unit,
            trade="plumbing",
            source=source,
            owner_explanation=str(comp.get("why", "")),
            rule_status=str(comp.get("rule_status", "MODEL_SELECTED")),
            rule_source=str(comp.get("rule_source", "")),
            selection_basis=str(comp.get("source_kind", "model")),
        ))
    return lines


def connection_assembly_quantities(doc) -> list[QuantityLine]:
    """Aggregate selected point-connection parts into purchase-friendly BOM lines."""
    return _aggregate_component_rows(
        connection_assembly_details(doc),
        "plumbing.connection_component",
        "Εξαρτήματα συνδέσεων",
        "connection_assembly",
    )


def manifold_assembly_quantities(doc) -> list[QuantityLine]:
    """Aggregate selected collector cabinet/valve/union parts into BOM lines."""
    return _aggregate_component_rows(
        manifold_assembly_details(doc),
        "plumbing.manifold_component",
        "Εξαρτήματα συλλεκτών",
        "manifold_assembly",
    )
