"""Heating/HVAC foundation for ArchForge.

This module deliberately does not perform heat-loss calculations, emitter
sizing, pipe sizing or pump selection. Those require verified methods and
project/manufacturer inputs. It provides authoritative project entities and
model-derived quantities so the same professional workflow can later support:

points/zones -> verified calculations -> materials -> labour -> quote -> site plan.

Trust status for all sizing in this initial module: ENGINEER_REVIEW.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping

from archforge.mep.trade_costing import PriceEntry, QuantityLine, cost_lines, quote_summary

RULE_STATUS = "ENGINEER_REVIEW"
PROVENANCE = (
    "Heating/HVAC inventory only: no automatic heat-load, hydraulic balancing, "
    "emitter sizing, pipe sizing or heat-source sizing is asserted by this module."
)

# These are semantic entity types, not engineering defaults.
POINT_TYPES = {
    "heat_source": "Πηγή θέρμανσης",
    "heat_pump": "Αντλία θερμότητας",
    "boiler": "Λέβητας",
    "manifold": "Συλλέκτης θέρμανσης",
    "radiator": "Θερμαντικό σώμα",
    "fan_coil": "Fan coil",
    "thermostat": "Θερμοστάτης",
}

ZONE_TYPES = {
    "underfloor": "Ενδοδαπέδια θέρμανση",
    "radiator_zone": "Ζώνη σωμάτων",
    "fan_coil_zone": "Ζώνη fan coil",
}


def heating_points(doc):
    return [e for e in doc.entities.values() if e.kind == "heating_point"]


def heating_zones(doc):
    return [e for e in doc.entities.values() if e.kind == "heating_zone"]


def heating_quantities(doc) -> list[QuantityLine]:
    """Count only model-authored heating equipment/zones and entered pipe lengths."""
    lines: list[QuantityLine] = []

    by_point: dict[str, int] = defaultdict(int)
    for entity in heating_points(doc):
        point_type = str(entity.params.get("point_type", ""))
        by_point[point_type] += 1
    for point_type, count in sorted(by_point.items()):
        lines.append(QuantityLine(
            code=f"heating.point.{point_type}",
            description=POINT_TYPES.get(point_type, point_type),
            category="Εξοπλισμός",
            quantity=float(count),
            unit="pcs",
            trade="heating",
            source="heating_point",
        ))

    by_zone: dict[str, int] = defaultdict(int)
    for entity in heating_zones(doc):
        zone_type = str(entity.params.get("zone_type", ""))
        by_zone[zone_type] += 1
    for zone_type, count in sorted(by_zone.items()):
        lines.append(QuantityLine(
            code=f"heating.zone.{zone_type}",
            description=ZONE_TYPES.get(zone_type, zone_type),
            category="Ζώνες",
            quantity=float(count),
            unit="pcs",
            trade="heating",
            source="heating_zone",
        ))

    # Pipe length is accepted only when the model/user has explicitly authored it.
    # No diameter or flow is inferred here.
    by_pipe: dict[str, float] = defaultdict(float)
    for entity in heating_points(doc):
        length = entity.params.get("pipe_length_m")
        if length is None:
            continue
        circuit = str(entity.params.get("pipe_type", "unspecified"))
        by_pipe[circuit] += float(length)
    for pipe_type, metres in sorted(by_pipe.items()):
        lines.append(QuantityLine(
            code=f"heating.pipe.{pipe_type}",
            description=f"Σωληνώσεις θέρμανσης — {pipe_type}",
            category="Σωληνώσεις",
            quantity=round(metres, 2),
            unit="m",
            trade="heating",
            source="model_entered_length",
        ))

    return lines


def heating_review(doc) -> dict:
    """Expose what exists and what is intentionally not yet auto-calculated."""
    return {
        "status": RULE_STATUS,
        "provenance": PROVENANCE,
        "points": len(heating_points(doc)),
        "zones": len(heating_zones(doc)),
        "automatic_calculations": {
            "heat_loss": False,
            "emitter_sizing": False,
            "pipe_sizing": False,
            "pump_selection": False,
            "hydraulic_balancing": False,
        },
    }


def heating_quote(doc, prices: Mapping[str, PriceEntry]) -> dict:
    quantities = heating_quantities(doc)
    rows = cost_lines(quantities, prices)
    return {
        "quantities": quantities,
        "rows": rows,
        "summary": quote_summary(rows),
        "review": heating_review(doc),
    }
