"""Trust/provenance registry for Heating/HVAC design rules.

This registry intentionally starts conservative.  ArchForge currently has no
verified automatic heat-loss, emitter sizing, hydronic pipe sizing, underfloor
loop design, pump selection or balancing method encoded here.  Those workflows
must move through Source -> Rule -> Implementation -> Test -> Engineer review
before they may be presented as verified requirements.
"""
from __future__ import annotations

from dataclasses import dataclass

VERIFIED_STANDARD = "VERIFIED_STANDARD"
DESIGN_DEFAULT = "DESIGN_DEFAULT"
MANUFACTURER_DATA = "MANUFACTURER_DATA"
ENGINEER_REVIEW = "ENGINEER_REVIEW"
CALCULATED = "CALCULATED"


@dataclass(frozen=True)
class HeatingRule:
    key: str
    label: str
    status: str
    value: object = None
    unit: str | None = None
    source: str | None = None
    note: str = ""


# Deliberately no VERIFIED_STANDARD entries yet.  Adding a standard title to a
# list is not enough: the exact clause/method/applicability must be checked
# before ArchForge implements or claims the technical requirement.
STANDARD_REFERENCES: dict[str, HeatingRule] = {}


DESIGN_RULES = {
    "heat_loss_method": HeatingRule(
        "heat_loss_method",
        "Heat-loss calculation method",
        ENGINEER_REVIEW,
        note="No automatic heat-loss method is implemented or asserted yet.",
    ),
    "design_temperatures": HeatingRule(
        "design_temperatures",
        "Indoor/outdoor design temperatures",
        ENGINEER_REVIEW,
        note="Project/climate inputs and their authoritative source are required; no hidden defaults.",
    ),
    "emitter_sizing": HeatingRule(
        "emitter_sizing",
        "Radiator / fan-coil sizing",
        ENGINEER_REVIEW,
        note="Requires verified loads plus manufacturer performance data; no automatic selection yet.",
    ),
    "underfloor_loop_spacing": HeatingRule(
        "underfloor_loop_spacing",
        "Underfloor-heating loop spacing",
        ENGINEER_REVIEW,
        note="No universal spacing is assumed; design method and product-system data must be sourced.",
    ),
    "underfloor_loop_length": HeatingRule(
        "underfloor_loop_length",
        "Underfloor-heating loop length limits",
        ENGINEER_REVIEW,
        note="No maximum loop length is encoded without verified design/manufacturer criteria.",
    ),
    "hydronic_flow": HeatingRule(
        "hydronic_flow",
        "Circuit design flow",
        ENGINEER_REVIEW,
        note="No flow is inferred from equipment count or floor area.",
    ),
    "pipe_sizing": HeatingRule(
        "pipe_sizing",
        "Heating pipe sizing",
        ENGINEER_REVIEW,
        note="No diameter is selected until a verified hydraulic method and project inputs exist.",
    ),
    "pump_selection": HeatingRule(
        "pump_selection",
        "Circulation pump selection",
        ENGINEER_REVIEW,
        note="No pump head/flow is guessed; hydraulic calculation is required.",
    ),
    "hydraulic_balancing": HeatingRule(
        "hydraulic_balancing",
        "Hydraulic balancing",
        ENGINEER_REVIEW,
        note="No automatic valve/preset recommendation is made yet.",
    ),
    "heat_source_sizing": HeatingRule(
        "heat_source_sizing",
        "Heat-source sizing",
        ENGINEER_REVIEW,
        note="Heat pump/boiler capacity is never inferred from inventory alone.",
    ),
}


def heating_rule_audit():
    rules = list(STANDARD_REFERENCES.values()) + list(DESIGN_RULES.values())
    grouped = {}
    for rule in rules:
        grouped.setdefault(rule.status, []).append(rule)
    return grouped


def unverified_heating_rules():
    return [rule for rule in DESIGN_RULES.values() if rule.status != VERIFIED_STANDARD]


def has_verified_automatic_sizing():
    """Explicit capability gate used by tests/UI before claiming auto sizing."""
    required = {
        "heat_loss_method",
        "emitter_sizing",
        "hydronic_flow",
        "pipe_sizing",
        "pump_selection",
        "hydraulic_balancing",
        "heat_source_sizing",
    }
    return all(DESIGN_RULES[key].status == VERIFIED_STANDARD for key in required)
