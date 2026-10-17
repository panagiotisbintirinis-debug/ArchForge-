"""Semantic plumbing components and drag/drop snap targets.

This catalogue defines what a component *is* and where it may be attached.  It
contains no mandatory quantities, dimensions, prices or regulatory claims.
Those belong to a selected product/assembly or an engineer-reviewed rule.
"""
from __future__ import annotations

import math

from archforge.mep.plumbing import route_plumbing_cached

# key -> (Greek label, allowed host kinds, owner-facing purpose)
COMPONENTS = {
    "angle_stop": ("Γωνιακός διακόπτης", ("point",), "Τοπικό εξάρτημα απομόνωσης σε σύνδεση συσκευής."),
    "isolation_valve": ("Βάνα απομόνωσης", ("point", "pipe", "manifold"), "Απομονώνει το επιλεγμένο τμήμα της εγκατάστασης."),
    "manifold_valve": ("Βάνα συλλέκτη", ("manifold",), "Βάνα που έχει επιλεγεί για είσοδο ή έξοδο συλλέκτη."),
    "union": ("Ρακόρ", ("point", "pipe", "manifold"), "Αποσπώμενη σύνδεση στο επιλεγμένο σημείο."),
    "adapter": ("Αντάπτορας", ("point", "pipe", "manifold"), "Σύνδεση μεταξύ ρητά επιλεγμένων διαφορετικών άκρων."),
    "coupling": ("Σύνδεσμος", ("pipe",), "Σύνδεσμος δύο τμημάτων σωλήνωσης όταν έχει επιλεγεί κατασκευαστικά."),
    "elbow": ("Γωνία", ("pipe",), "Εξάρτημα αλλαγής διεύθυνσης όταν υπάρχει στην επιλεγμένη λύση."),
    "tee": ("Ταφ", ("pipe",), "Εξάρτημα διακλάδωσης όταν υπάρχει στην επιλεγμένη λύση."),
    "flex_connector": ("Εύκαμπτος σύνδεσμος", ("point",), "Εύκαμπτη τελική σύνδεση που έχει επιλεγεί για τη συσκευή."),
    "wall_outlet": ("Έξοδος τοίχου", ("point",), "Τερματικό σύνδεσης εγκατάστασης προς τη συσκευή."),
    "end_cap": ("Τάπα", ("pipe", "manifold"), "Τάπα σε ρητά επιλεγμένο άκρο ή αχρησιμοποίητη έξοδο."),
    "filter": ("Φίλτρο", ("pipe", "point"), "Φίλτρο που έχει επιλεγεί ρητά για το έργο."),
    "check_valve": ("Αντεπίστροφη βαλβίδα", ("pipe", "point"), "Βαλβίδα μονής κατεύθυνσης που έχει επιλεγεί ρητά."),
    "pressure_reducer": ("Μειωτής πίεσης", ("pipe",), "Εξάρτημα ρύθμισης πίεσης που έχει επιλεγεί ρητά."),
    "manifold_cabinet": ("Ερμάριο συλλέκτη", ("manifold",), "Ερμάριο/πίνακας που περιέχει τον επιλεγμένο συλλέκτη."),
    "solar_connector": ("Σύνδεσμος ηλιακού / δοχείου", ("point",), "Σύνδεση προς επιλεγμένο ηλιακό ή δοχείο."),
    "safety_group": ("Ομάδα ασφαλείας", ("point",), "Ομάδα ασφαλείας μόνο όταν προβλέπεται από επιλεγμένη λύση/προϊόν."),
}


def component_label(key: str) -> str:
    return COMPONENTS.get(str(key), (str(key), (), ""))[0]


def component_actions():
    """Library rows: label + action tuple.  No product claims are encoded."""
    return [(label, ("plumbing_component", key)) for key, (label, _hosts, _why) in COMPONENTS.items()]


def _point_distance(x, y, px, py):
    return math.hypot(float(x) - float(px), float(y) - float(py))


def _segment_projection(x, y, a, b):
    ax, ay = float(a[0]), float(a[1]); bx, by = float(b[0]), float(b[1])
    dx, dy = bx - ax, by - ay
    den = dx * dx + dy * dy
    t = 0.0 if den <= 1e-12 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / den))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot(x - qx, y - qy), (qx, qy, float(a[2]) + t * (float(b[2]) - float(a[2])))


def snap_target(doc, component_type: str, x: float, y: float, reach: float = 0.35):
    """Nearest valid plumbing host around plan point; returns a serializable dict.

    Derived pipes/manifolds have no authoritative entity id, so the target stores
    their semantic network/location.  This is attachment metadata, not a new
    engineering rule.
    """
    spec = COMPONENTS.get(str(component_type))
    if spec is None:
        return None
    allowed = set(spec[1])
    candidates = []

    if "point" in allowed:
        for e in doc.entities.values():
            if e.kind != "plumbing_point":
                continue
            p = e.params
            d = _point_distance(x, y, p.get("x", 0), p.get("y", 0))
            if d <= reach:
                candidates.append((d, {
                    "host_kind": "point", "host_id": str(e.id),
                    "x": float(p.get("x", 0)), "y": float(p.get("y", 0)), "z": float(p.get("z", 0)),
                    "point_type": str(p.get("point_type", "")),
                }))

    routed = route_plumbing_cached(doc)
    if "manifold" in allowed:
        for index, m in enumerate(routed.get("manifolds", ())):
            d = _point_distance(x, y, m["x"], m["y"])
            if d <= reach:
                candidates.append((d, {
                    "host_kind": "manifold", "host_id": "",
                    "manifold_index": index, "network": str(m.get("system", "")),
                    "outlets": len(m.get("outlets", ())),
                    "x": float(m["x"]), "y": float(m["y"]), "z": float(m["z"]),
                }))

    if "pipe" in allowed:
        for network in ("cold", "hot"):
            for index, (a, b, dia) in enumerate(routed.get(network, ())):
                d, q = _segment_projection(float(x), float(y), a, b)
                if d <= reach:
                    candidates.append((d, {
                        "host_kind": "pipe", "host_id": "",
                        "network": network, "segment_index": index, "diameter": int(dia),
                        "x": q[0], "y": q[1], "z": q[2],
                    }))

    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def accessory_params(component_type: str, target: dict) -> dict:
    """Authoritative plumbing_accessory params for one drag/drop placement."""
    key = str(component_type)
    label, _hosts, why = COMPONENTS[key]
    return {
        "accessory_type": key,
        "quantity": 1.0,
        "unit": "pcs",
        "x": float(target["x"]), "y": float(target["y"]), "z": float(target["z"]),
        "host_kind": str(target["host_kind"]),
        "host_id": str(target.get("host_id", "")),
        "network": str(target.get("network", "")),
        "diameter": target.get("diameter"),
        "manifold_index": target.get("manifold_index"),
        "segment_index": target.get("segment_index"),
        "source_kind": "professional_selection",
        "rule_status": "MODEL_SELECTED",
        "selection_basis": "visual_drag_drop",
        "owner_explanation": why,
        "display_label": label,
    }
