"""KNX (EN 50090) as a project option: the client's choice, the default stays conventional On/Off (owner 15/10).

With ``control_system = 'knx'`` on the panel point:

* wall switches / dimmers become KNX push buttons on the green bus — no 230 V
  switch legs; the bus runs from the panel from device to device (a tree,
  never a loop: here a nearest-neighbour chain, so it cannot close a loop);
* luminaires set to DALI-2 get the two DALI conductors (DA+, DA−) with L/N/PE
  and are counted as DALI addresses on KNX-DALI gateways; the others are
  On/Off channels of C-Load switch actuators;
* the panel gets the KNX power supply and IP interface (sizes from the study).

Every number taken from the owner's 15/10 summaries is registered as
ENGINEER_REVIEW; the bus-length limits also agree with Siemens / Ekinex
documents but not yet with the KNX Association text.
"""
from __future__ import annotations

import math

from archforge.core.provenance import DESIGN_DEFAULT, ENGINEER_REVIEW, Rule, register

SUMMARY = "Σύνοψη ιδιοκτήτη 15/10 (KNX / DALI-2) — όχι το κείμενο της KNX Association / IEC 62386"
BUS_LIMIT_TOTAL = 1000.0      # m per line
BUS_LIMIT_SUPPLY = 350.0      # m from the supply to the farthest device
DALI_ADDRESSES = 64           # per DALI line / gateway
DA_MM2 = 1.5
CONTROL_SYSTEMS = {"conventional": "Συμβατικό (διακόπτες 230 V)", "knx": "KNX (μπουτόν στο bus)"}

register(
    Rule("knx.default", "Σύστημα ελέγχου: συμβατικό με On/Off εκτός αν ο πελάτης επιλέξει KNX· ρύθμιση έντασης On/Off "
         "εκτός αν οριστεί DALI-2 / phase-cut / 0-10 V", DESIGN_DEFAULT, source="Απόφαση ιδιοκτήτη 15/10",
         note="«η απόφαση είναι βάσει κρίσης του πελάτη, το default είναι On/Off»"),
    Rule("knx.bus_limits", "Bus KNX ανά γραμμή: ≤ 1000 m συνολικά, ≤ 350 m από το τροφοδοτικό στην πιο μακρινή συσκευή",
         ENGINEER_REVIEW, source=SUMMARY + " · συμφωνούν έγγραφα Siemens (RL 125/23) και Ekinex (STEKAH1TP)",
         note="Μήκος bus εδώ: αλυσίδα από τον πίνακα προς την πλησιέστερη συσκευή κάθε φορά (κάτοψη + κάθοδοι)"),
    Rule("knx.dali_gateway", "KNX-DALI gateway: ως 64 διευθύνσεις DALI ανά γραμμή· καλώδιο 5×1,5 (L, N, PE, DA+, DA−)",
         ENGINEER_REVIEW, source=SUMMARY),
    Rule("knx.c_load", "Ρελέ KNX για LED: τύπου C-Load (ρεύμα εκκίνησης τροφοδοτικών)", ENGINEER_REVIEW, source=SUMMARY,
         note="Η προδιαγραφή του ρελέ από το φύλλο του κατασκευαστή"),
)


def control_system(doc_or_conf):
    conf = doc_or_conf if isinstance(doc_or_conf, dict) else None
    if conf is None:
        from archforge.mep.electrical_board import settings
        conf = settings(doc_or_conf)
    return conf.get("control_system", "conventional")


def dimming_of(params):
    """Owner 15/10: On/Off unless the point says otherwise."""
    return params.get("dimming") or "onoff"


def bus_chain(doc, panel, devices):
    """Bus route from the panel through every KNX wall device: ``(order, segments [(a, b)], length, farthest)``."""
    from archforge.mep.electrical import WALL_RUN_Z, _floor_of, mount_z
    if panel is None or not devices:
        return [], [], 0.0, 0.0

    def at(e):
        return (float(e.params["x"]), float(e.params["y"]), mount_z(doc, e.params))

    def run_z(p):
        from archforge.mep.low_voltage import LV_RUN_RISE
        return _floor_of(doc, p[2]) + WALL_RUN_Z + LV_RUN_RISE

    current, left, order, segments = at(panel), list(devices), [], []
    total = farthest = 0.0
    while left:
        nxt = min(left, key=lambda e: (abs(at(e)[0] - current[0]) + abs(at(e)[1] - current[1]) + abs(at(e)[2] - current[2]), e.id))
        left.remove(nxt)
        p = at(nxt)
        # Up to the wall run, along it (two legs), down to the device's box.
        z0, z1 = run_z(current), run_z(p)
        legs = [(current, (current[0], current[1], z0)), ((current[0], current[1], z0), (p[0], current[1], z0)),
                ((p[0], current[1], z0), (p[0], p[1], z1)), ((p[0], p[1], z1), p)]
        legs = [(a, b) for a, b in legs if math.dist(a, b) > 1e-6]
        segments += legs
        total += sum(math.dist(a, b) for a, b in legs)
        farthest = max(farthest, total)
        order.append(nxt.id)
        current = p
    return order, segments, round(total, 2), round(farthest, 2)


def knx_summary(doc, wiring, points):
    """Panel equipment and bus figures for KNX (quantities; sizes of PSU/actuators from the study)."""
    from archforge.mep.electrical import SWITCH_TYPES
    from archforge.mep.lighting import is_luminaire
    panel = next((e for e in points.values() if e.params["point_type"] == "panel"), None)
    buttons = [e for e in points.values() if e.params["point_type"] in SWITCH_TYPES]
    order, segments, length, farthest = bus_chain(doc, panel, buttons)
    lights = [e for e in points.values() if is_luminaire(e)]
    dali = [e for e in lights if dimming_of(e.params) == "dali2"]
    groups = [l for l in wiring["switch_links"] if any(dimming_of(points[i].params) != "dali2" for i in l["lights"] if i in points)]
    warnings = []
    if length > BUS_LIMIT_TOTAL:
        warnings.append(f"Bus KNX {length:.0f} m > {BUS_LIMIT_TOTAL:.0f} m ανά γραμμή — δεύτερη γραμμή/συζεύκτης [προς έλεγχο]")
    if farthest > BUS_LIMIT_SUPPLY:
        warnings.append(f"Bus KNX: {farthest:.0f} m από το τροφοδοτικό > {BUS_LIMIT_SUPPLY:.0f} m [προς έλεγχο]")
    return {"buttons": len(buttons), "bus_m": length, "bus_farthest_m": farthest, "bus_segments": segments,
            "bus_order": order, "dali_addresses": len(dali), "dali_gateways": math.ceil(len(dali) / DALI_ADDRESSES) if dali else 0,
            "onoff_channels": len(groups), "warnings": warnings}
