"""Material-economy comparison for plumbing layouts.

This is a DESIGN COMPARISON, not an engineering or regulatory sizing rule.
ArchForge reports directly measurable material indicators instead of inventing
one opaque weighted score: pipe metres, derived manifolds and explicit selected
accessory quantities.  It never auto-switches the user's system.
"""
from __future__ import annotations

import copy
import math

from archforge.mep.plumbing import PIPE_SYSTEMS, plumbing_points, route_plumbing
from archforge.mep.plumbing_accessories import accessory_quantities
from archforge.mep.plumbing_assemblies import connection_assembly_quantities, manifold_assembly_quantities


def _pipe_metres(route):
    by_diameter = {}
    total = 0.0
    for network in ("cold", "hot"):
        for a, b, diameter in route.get(network, ()):
            length = math.dist(a, b)
            total += length
            key = (network, int(diameter))
            by_diameter[key] = by_diameter.get(key, 0.0) + length
    return total, by_diameter


def _selected_component_count(doc):
    lines = []
    lines.extend(connection_assembly_quantities(doc))
    lines.extend(manifold_assembly_quantities(doc))
    lines.extend(accessory_quantities(doc))
    return sum(float(line.quantity) for line in lines if str(line.unit) == "pcs")


def compare_systems(doc) -> list[dict]:
    """Compare supported systems using the same project geometry.

    Results are informational only.  Pipe diameters remain ENGINEER_REVIEW in
    the current pre-design router; this function does not make them compliant.
    """
    supply = next((e for e in plumbing_points(doc) if e.params.get("point_type") == "water_supply"), None)
    if supply is None:
        return []
    current = str(supply.params.get("pipe_system", "multilayer"))
    out = []
    for key, (label, _sizes) in PIPE_SYSTEMS.items():
        trial = copy.deepcopy(doc)
        trial_supply = next(e for e in plumbing_points(trial) if e.params.get("point_type") == "water_supply")
        trial_supply.params["pipe_system"] = key
        route = route_plumbing(trial)
        metres, by_diameter = _pipe_metres(route)
        out.append({
            "system": key,
            "label": label,
            "current": key == current,
            "pipe_m": round(metres, 2),
            "pipe_by_diameter": {f"{net}.dn{dia}": round(m, 2) for (net, dia), m in sorted(by_diameter.items())},
            "manifolds": len(route.get("manifolds", ())),
            "selected_components": _selected_component_count(trial),
            "unserved": len(route.get("report", {}).get("unserved", ())),
            "status": "DESIGN_COMPARISON_ENGINEER_REVIEW",
        })
    return out


def least_pipe_length_candidate(doc):
    """Return the comparison row with least pipe metres, never apply it."""
    rows = [r for r in compare_systems(doc) if not r["unserved"]]
    return min(rows, key=lambda r: r["pipe_m"]) if rows else None
