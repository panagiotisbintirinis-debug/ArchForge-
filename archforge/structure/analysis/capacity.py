"""Strong column – weak beam at the RC frame joints: ΣMRc / ΣMRb per joint and direction.

* ΣMRb: the design moments of resistance of the beams framing into the joint
  in that plan direction, from the bars the design chose (``top`` / ``bottom``
  MRd).  Under a sway the beam on one side hogs and the other sags; both senses
  are taken and the larger sum governs.
* ΣMRc: the columns above and below, the MRd about the axis bending in that
  plane, from the same N–M strain-compatibility routine as the column design,
  at the axial force of every seismic combination at that end — the smallest
  (the most onerous) is used.
* The required factor (``FACTOR``) has only the owner's sample study (15/10)
  behind it, so it is UNVERIFIED: the ratio is reported and flagged, never used
  to fail or resize a member (``structure.capacity_joints``).  Exemptions in
  the code text (e.g. the top storey) are not applied — for the engineer.
"""
from __future__ import annotations

import math

import numpy as np

from archforge.structure.analysis.rc import column_capacity
from archforge.core.provenance import ENGINEER_REVIEW, rule
import archforge.structure.rules  # registers the source/status of this comparison

FACTOR = 1.30
_AXES = {"X": np.array([1.0, 0.0, 0.0]), "Y": np.array([0.0, 1.0, 0.0])}


def _positions(model, member):
    """{node: position along the member (m)} for every analytical node on it."""
    seq = [model.elements[member.elements[0]].n1] + [model.elements[k].n2 for k in member.elements]
    pos, s = {seq[0]: 0.0}, 0.0
    for a, b in zip(seq, seq[1:]):
        s += math.dist(model.nodes[a], model.nodes[b])
        pos[b] = s
    return seq, pos


def _column_mrd(entry, member, rows, at, axis, cls):
    """Smallest MRd of the column end at position ``at`` about the axis bending in plane ``axis``."""
    bars = entry.get("bars")
    if not bars:
        return None
    width_along = np.asarray(member.y_dir, float)
    # Bending in the X-Z plane is resisted with the lever along X: along b → Mz, else My.
    use_z = abs(float(width_along @ _AXES[axis])) > 0.7
    best = None
    for r in rows:
        if not r[7] or abs(r[1] - at) > 1e-6:
            continue
        N = max(-float(r[2]), 0.0)
        My, Mz, _NRd, _n = column_capacity(member.b, member.h, bars["nb"], bars["nh"], bars["d"], N, cls)
        m = Mz if use_z else My
        best = m if best is None else min(best, m)
    return best


def joint_checks(model, members, designs, settings):
    comparison_rule = rule("structure.capacity_joints")
    cls = settings["concrete"]
    cols = [m for m in model.members.values() if m.kind == "column" and m.material == "rc"]
    beams = [m for m in model.members.values() if m.kind == "beam" and m.material == "rc"]
    col_at, beam_at = {}, {}
    for m in cols:
        seq, pos = _positions(model, m)
        for end, n in (("bottom", seq[0]), ("top", seq[-1])):
            col_at.setdefault(n, []).append((m, end, pos[n]))
    for m in beams:
        seq, pos = _positions(model, m)
        d = np.asarray(m.p2, float) - np.asarray(m.p1, float)
        d /= np.linalg.norm(d)
        axis = next((a for a, v in _AXES.items() if abs(float(d @ v)) > 0.9), None)
        if axis is None:
            continue
        sign = 1.0 if float(d @ _AXES[axis]) > 0 else -1.0
        for i, n in enumerate(seq):
            sides = ([-sign] if i > 0 else []) + ([sign] if i < len(seq) - 1 else [])   # where the beam goes from n
            for side in sides:
                beam_at.setdefault((n, axis), []).append((m, side))
    out = []
    for n in sorted(col_at):
        if n in model.supports:
            continue
        for axis in ("X", "Y"):
            framing = beam_at.get((n, axis), [])
            if not framing:
                continue
            mrc, names = 0.0, []
            for m, end, at in col_at[n]:
                v = _column_mrd(members.get(m.id, {}), m, designs.get(m.id, []), at, axis, cls)
                if v is None:
                    mrc = None
                    break
                mrc += v
                names.append(m.name)
            if not mrc:
                continue
            sums = []
            for hog_side in (1.0, -1.0):
                total = 0.0
                for m, side in framing:
                    e = members.get(m.id, {})
                    key = "top" if side == hog_side else "bottom"
                    total += float(e.get(key, {}).get("MRd", 0.0))
                sums.append(total)
            mrb = max(sums)
            if mrb <= 0:
                continue
            below = [m for m, end, _ in col_at[n] if end == "top"]
            ratio = mrc / mrb
            out.append({"node": n, "axis": axis, "x": round(model.nodes[n][0], 2), "y": round(model.nodes[n][1], 2),
                        "z": round(model.nodes[n][2], 2), "joint": (below[0] if below else col_at[n][0][0]).name,
                        "columns": names, "beams": sorted({m.name for m, _ in framing}),
                        "sum_MRc": round(mrc, 1), "sum_MRb": round(mrb, 1), "ratio": round(ratio, 2),
                        "top": not any(end == "bottom" for _m, end, _ in col_at[n]), "meets": ratio >= FACTOR - 1e-9,
                        "rule_id": comparison_rule.id, "rule_status": comparison_rule.status,
                        "rule_source": comparison_rule.source, "rule_note": comparison_rule.note,
                        "factor": FACTOR, "applicability": ENGINEER_REVIEW})
    return out


def joint_review_warnings(joints):
    """Expose raw comparison flags without asserting failure or applying exemptions.

    ``meets`` remains the existing numerical comparison. Neither it nor a top
    node proves that the regulatory check applies (or that an exemption does).
    No member capacity or design input is changed by this diagnostic.
    """
    return [
        f"Κόμβος {j['joint']} / {j['axis']} (z={j['z']:.2f} m"
        f"{', κορυφή' if j['top'] else ''}): ΣMRc/ΣMRb={j['ratio']:.2f} "
        f"< {j['factor']:.2f} — μη επαληθευμένο κριτήριο· "
        "η εφαρμογή του και τυχόν εξαιρέσεις θέλουν έλεγχο μηχανικού. "
        "Δεν αποτελεί επιβεβαιωμένη αστοχία ή εντολή αλλαγής διατομών."
        for j in joints if j.get("meets") is False
    ]
