"""Provenance registry for plumbing rules used by ArchForge.

This module deliberately separates *what the program currently does* from
*what has been verified as an engineering requirement*.

NO UNSOURCED ENGINEERING CONSTANTS.

A value may exist in the routing/pre-design implementation while still being
classified as DESIGN_DEFAULT or ENGINEER_REVIEW.  Only rules whose actual
requirement has been checked against an authoritative source may be marked
VERIFIED_STANDARD.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


VERIFIED_STANDARD = "VERIFIED_STANDARD"
DESIGN_DEFAULT = "DESIGN_DEFAULT"
MANUFACTURER_DATA = "MANUFACTURER_DATA"
ENGINEER_REVIEW = "ENGINEER_REVIEW"
CALCULATED = "CALCULATED"


@dataclass(frozen=True)
class PlumbingRule:
    key: str
    label: str
    status: str
    value: object = None
    unit: Optional[str] = None
    source: Optional[str] = None
    note: str = ""


# Authoritative metadata verified against ELOT catalogue entries.
# These entries verify scope/version only; they do NOT imply that ArchForge
# has implemented every requirement of the cited standard.
STANDARD_REFERENCES = {
    "backflow_protection": PlumbingRule(
        key="backflow_protection",
        label="Protection of potable water against pollution by backflow",
        status=VERIFIED_STANDARD,
        source="ELOT EN 1717:2025+A1:2026",
        note=(
            "Verified scope/version from ELOT catalogue. ArchForge does not yet "
            "claim compliance or auto-select a protection device."
        ),
    ),
    "multilayer_fittings": PlumbingRule(
        key="multilayer_fittings",
        label="Fittings for multilayer hot/cold-water piping systems",
        status=VERIFIED_STANDARD,
        source="ELOT EN ISO 21003-3:2008 + A1:2022",
        note=(
            "Verified product-standard scope/version from ELOT catalogue. "
            "No pipe diameter or hydraulic sizing rule is inferred from it."
        ),
    ),
}


# Current implementation values.  These are intentionally classified as
# design/pre-design assumptions unless and until an authoritative requirement
# for the exact value is verified.
IMPLEMENTATION_RULES = {
    "routing_grid": PlumbingRule(
        key="routing_grid",
        label="Routing grid spacing",
        status=DESIGN_DEFAULT,
        value=0.20,
        unit="m",
        note="ArchForge routing discretisation; not presented as a regulation.",
    ),
    "screed_route_height": PlumbingRule(
        key="screed_route_height",
        label="Derived pipe route elevation above floor",
        status=DESIGN_DEFAULT,
        value=0.05,
        unit="m",
        note="Pre-design visual/routing default; requires project-specific review.",
    ),
    "hot_pipe_plan_offset": PlumbingRule(
        key="hot_pipe_plan_offset",
        label="Hot-pipe drawing offset",
        status=DESIGN_DEFAULT,
        value=0.05,
        unit="m",
        note="Drawing legibility offset only; not a physical installation requirement.",
    ),
    "home_run_plan_gap": PlumbingRule(
        key="home_run_plan_gap",
        label="Parallel home-run drawing gap",
        status=DESIGN_DEFAULT,
        value=0.04,
        unit="m",
        note="Plan-graphics spacing; not an installation requirement.",
    ),
    "multilayer_outlet_count_sizing": PlumbingRule(
        key="multilayer_outlet_count_sizing",
        label="Multilayer diameter selection by downstream outlet count",
        status=ENGINEER_REVIEW,
        value=(16, 20, 26),
        unit="mm",
        note=(
            "Current rule-of-thumb pre-design sizing. Not a hydraulic calculation; "
            "must not be labelled standards-compliant."
        ),
    ),
    "copper_outlet_count_sizing": PlumbingRule(
        key="copper_outlet_count_sizing",
        label="Copper diameter selection by downstream outlet count",
        status=ENGINEER_REVIEW,
        value=(15, 18, 22),
        unit="mm",
        note=(
            "Current rule-of-thumb pre-design sizing. Material/product standard "
            "references do not by themselves validate this sizing rule."
        ),
    ),
    "manifold_outlet_count_sizing": PlumbingRule(
        key="manifold_outlet_count_sizing",
        label="Manifold-system diameter selection by outlet count",
        status=ENGINEER_REVIEW,
        value=(16, 20, 26),
        unit="mm",
        note="Pre-design assumption pending verified hydraulic sizing method.",
    ),
}


# Connection heights presently embedded in plumbing.py.  Until project,
# manufacturer, or verified design-source data is attached, they remain
# engineering-review values rather than normative requirements.
CONNECTION_HEIGHT_RULES = {
    "water_supply": PlumbingRule("connection_height.water_supply", "Water supply connection height", ENGINEER_REVIEW, 0.30, "m"),
    "solar_heater": PlumbingRule("connection_height.solar_heater", "Solar heater connection height", ENGINEER_REVIEW, 0.00, "m"),
    "water_heater": PlumbingRule("connection_height.water_heater", "Water heater connection height", ENGINEER_REVIEW, 1.60, "m"),
    "basin": PlumbingRule("connection_height.basin", "Basin connection height", ENGINEER_REVIEW, 0.55, "m"),
    "wc": PlumbingRule("connection_height.wc", "WC connection height", ENGINEER_REVIEW, 0.15, "m"),
    "shower": PlumbingRule("connection_height.shower", "Shower connection height", ENGINEER_REVIEW, 1.05, "m"),
    "bathtub": PlumbingRule("connection_height.bathtub", "Bathtub connection height", ENGINEER_REVIEW, 0.70, "m"),
    "kitchen_sink": PlumbingRule("connection_height.kitchen_sink", "Kitchen sink connection height", ENGINEER_REVIEW, 0.55, "m"),
    "dishwasher": PlumbingRule("connection_height.dishwasher", "Dishwasher connection height", ENGINEER_REVIEW, 0.45, "m"),
    "washing_machine": PlumbingRule("connection_height.washing_machine", "Washing machine connection height", ENGINEER_REVIEW, 0.80, "m"),
}


def plumbing_rule_audit():
    """Return all current plumbing rules grouped by verification status."""
    rules = list(STANDARD_REFERENCES.values()) + list(IMPLEMENTATION_RULES.values()) + list(CONNECTION_HEIGHT_RULES.values())
    grouped = {}
    for rule in rules:
        grouped.setdefault(rule.status, []).append(rule)
    return grouped


def unverified_engineering_rules():
    """Rules that must not be presented to users as verified requirements."""
    return [
        rule
        for rule in list(IMPLEMENTATION_RULES.values()) + list(CONNECTION_HEIGHT_RULES.values())
        if rule.status in {DESIGN_DEFAULT, ENGINEER_REVIEW}
    ]
