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

from archforge.mep.trade_costing import (
    PriceEntry,
    QuantityLine,
    cost_lines,
    owner_quote_view,
    quote_summary,
)

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

POINT_EXPLANATIONS = {
    "heat_source": "Η πηγή θέρμανσης που έχει δηλωθεί για το έργο.",
    "heat_pump": "Αντλία θερμότητας που έχει επιλεγεί ή τοποθετηθεί στο έργο· η ισχύς της δεν υπολογίζεται εδώ.",
    "boiler": "Λέβητας που έχει επιλεγεί ή τοποθετηθεί στο έργο· η ισχύς του δεν υπολογίζεται εδώ.",
    "manifold": "Συλλέκτης θέρμανσης που έχει τοποθετηθεί στο σχέδιο για τη διανομή των δηλωμένων κυκλωμάτων.",
    "radiator": "Θερμαντικό σώμα που υπάρχει στο σχέδιο· η απαιτούμενη ισχύς του παραμένει προς verified sizing.",
    "fan_coil": "Fan coil που υπάρχει στο σχέδιο· η απαιτούμενη ισχύς του παραμένει προς verified sizing.",
    "thermostat": "Θερμοστάτης που έχει δηλωθεί για έλεγχο συγκεκριμένης ζώνης ή χώρου.",
}

ZONE_TYPES = {
    "underfloor": "Ενδοδαπέδια θέρμανση",
    "radiator_zone": "Ζώνη σωμάτων",
    "fan_coil_zone": "Ζώνη fan coil",
}

ZONE_EXPLANATIONS = {
    "underfloor": "Ζώνη ενδοδαπέδιας θέρμανσης που έχει οριστεί στο μοντέλο· βρόχοι, αποστάσεις και παροχές δεν επινοούνται από αυτό το module.",
    "radiator_zone": "Ζώνη θέρμανσης με σώματα που έχει οριστεί στο μοντέλο.",
    "fan_coil_zone": "Ζώνη fan coil που έχει οριστεί στο μοντέλο.",
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
            owner_explanation=POINT_EXPLANATIONS.get(point_type, "Εξοπλισμός θέρμανσης που έχει δηλωθεί ρητά στο έργο."),
            rule_status="MODEL_QUANTITY_ENGINEER_REVIEW",
            rule_source=PROVENANCE,
            selection_basis="placed_heating_point",
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
            owner_explanation=ZONE_EXPLANATIONS.get(zone_type, "Ζώνη θέρμανσης που έχει δηλωθεί στο έργο."),
            rule_status="MODEL_QUANTITY_ENGINEER_REVIEW",
            rule_source=PROVENANCE,
            selection_basis="authored_zone",
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
            owner_explanation="Μήκος σωλήνωσης που έχει δηλωθεί ρητά στο μοντέλο· δεν έχει γίνει αυτόματη επιλογή διαμέτρου ή παροχής.",
            rule_status="MODEL_ENTERED_ENGINEER_REVIEW",
            rule_source=PROVENANCE,
            selection_basis="explicit_model_value",
        ))

    return lines


def heating_review(doc) -> dict:
    """Expose inventory, verified metadata and still-unimplemented calculations."""
    from archforge.mep.heating_rules import heating_rule_audit, has_verified_automatic_sizing

    return {
        "status": RULE_STATUS,
        "provenance": PROVENANCE,
        "points": len(heating_points(doc)),
        "zones": len(heating_zones(doc)),
        "rule_audit": heating_rule_audit(),
        "verified_automatic_sizing": has_verified_automatic_sizing(),
        "automatic_calculations": {
            "heat_loss": False,
            "emitter_sizing": False,
            "pipe_sizing": False,
            "pump_selection": False,
            "hydraulic_balancing": False,
        },
    }


def heating_quote(doc, prices: Mapping[str, PriceEntry] | None = None) -> dict:
    """Price heating inventory through the same project price book as other trades."""
    if prices is None:
        from archforge.mep.project_pricebook import project_prices
        prices = project_prices(doc)
    quantities = heating_quantities(doc)
    rows = cost_lines(quantities, prices)
    return {
        "quantities": quantities,
        "rows": rows,
        "summary": quote_summary(rows),
        "owner_view": owner_quote_view(rows),
        "review": heating_review(doc),
    }
