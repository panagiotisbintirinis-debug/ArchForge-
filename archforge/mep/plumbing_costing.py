"""Plumbing quantities -> shared trade costing.

No prices and no guessed fittings are created here. Quantities come only from
``route_plumbing`` and authoritative plumbing entities. Diameter labels reflect
the current model output; they are not asserted here as hydraulically verified.

Explicit accessories (valves, manifold cabinets, unions, adapters, fittings,
supports, insulation, fixture connectors, etc.) are included only when they
exist in the model or later come from an explicitly selected sourced assembly.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Mapping

from archforge.mep.plumbing import POINT_TYPES, plumbing_points, route_plumbing
from archforge.mep.plumbing_accessories import accessory_quantities
from archforge.mep.trade_costing import (
    PriceEntry,
    QuantityLine,
    cost_lines,
    owner_quote_view,
    quote_summary,
)


def _length(a, b) -> float:
    return math.dist(tuple(float(v) for v in a), tuple(float(v) for v in b))


def plumbing_quantities(doc) -> list[QuantityLine]:
    """Return measurable plumbing quantities, grouped by network and diameter."""
    routed = route_plumbing(doc)
    lines: list[QuantityLine] = []

    by_pipe: dict[tuple[str, int], float] = defaultdict(float)
    for network in ("cold", "hot"):
        for a, b, diameter_mm in routed.get(network, []):
            by_pipe[(network, int(diameter_mm))] += _length(a, b)

    network_label = {"cold": "Κρύο νερό", "hot": "Ζεστό νερό"}
    for (network, diameter), metres in sorted(by_pipe.items()):
        lines.append(QuantityLine(
            code=f"plumbing.pipe.{network}.dn{diameter}",
            description=f"{network_label[network]} — σωλήνωση Ø{diameter}",
            category="Σωληνώσεις",
            quantity=round(metres, 2),
            unit="m",
            trade="plumbing",
            source="route_plumbing",
            owner_explanation="Μήκος σωλήνωσης που προκύπτει από τη διαδρομή του συγκεκριμένου δικτύου στο σχέδιο.",
            rule_status="MODEL_QUANTITY_ENGINEER_REVIEW",
            rule_source=str(routed.get("report", {}).get("provenance", "")),
            selection_basis="derived_route",
        ))

    manifolds = routed.get("manifolds", [])
    by_manifold: dict[tuple[str, int], int] = defaultdict(int)
    for manifold in manifolds:
        by_manifold[(str(manifold.get("system", "")), len(manifold.get("outlets", [])))] += 1
    for (network, outlets), count in sorted(by_manifold.items()):
        lines.append(QuantityLine(
            code=f"plumbing.manifold.{network}.{outlets}way",
            description=f"Συλλέκτης {network_label.get(network, network)} — {outlets} εξόδων",
            category="Συλλέκτες",
            quantity=float(count),
            unit="pcs",
            trade="plumbing",
            source="route_plumbing",
            owner_explanation="Συλλέκτης που εξυπηρετεί τις δηλωμένες γραμμές του συγκεκριμένου δικτύου.",
            rule_status="MODEL_DERIVED_ENGINEER_REVIEW",
            rule_source=str(routed.get("report", {}).get("provenance", "")),
            selection_basis="derived_from_selected_system",
        ))

    by_point: dict[str, int] = defaultdict(int)
    for entity in plumbing_points(doc):
        point_type = str(entity.params.get("point_type", ""))
        if point_type in {"water_supply", "solar_heater", "water_heater"}:
            continue
        by_point[point_type] += 1
    for point_type, count in sorted(by_point.items()):
        label = POINT_TYPES.get(point_type, (point_type,))[0]
        lines.append(QuantityLine(
            code=f"plumbing.point.{point_type}",
            description=f"Σύνδεση σημείου — {label}",
            category="Σημεία",
            quantity=float(count),
            unit="pcs",
            trade="plumbing",
            source="plumbing_point",
            owner_explanation="Εργασία και υλικά σύνδεσης για το συγκεκριμένο σημείο που υπάρχει στο σχέδιο.",
            rule_status="MODEL_QUANTITY",
            selection_basis="placed_fixture_point",
        ))

    # First-class accessories: counted only when explicitly present/selected.
    lines.extend(accessory_quantities(doc))
    return lines


def plumbing_quote(doc, prices: Mapping[str, PriceEntry]) -> dict:
    """Price current plumbing quantities with user/professional price entries."""
    quantities = plumbing_quantities(doc)
    rows = cost_lines(quantities, prices)
    return {
        "quantities": quantities,
        "rows": rows,
        "summary": quote_summary(rows),
        "owner_view": owner_quote_view(rows),
    }
