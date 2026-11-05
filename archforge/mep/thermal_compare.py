"""«Θερμομονώσεις»: η θερμική εικόνα μιας όψης σήμερα και με την πρόταση, στην ίδια κλίμακα (mockup v2, 05/11).

Ιδιοκτήτης 05/11: «αλλάζοντας ή προσθέτοντας υλικό, η διαφορά να φαίνεται οπτικά — ο πελάτης καταλαβαίνει, εμείς
βλέπουμε πού είναι λάθος η μελέτη» · «αυτό είναι πιο αληθοφανές από το να έχουμε απόλυτες τιμές σε ένα τοίχο».

Η εικόνα βγαίνει πάντα από τον υπολογισμό 3Δ αγωγής (``facade_thermal.facade``), ποτέ ένα χρώμα ανά τοίχο ή υλικό.
Η πρόταση δεν αλλάζει τίποτα στο έργο: είναι στρώσεις / Uw που δίνονται στον υπολογισμό.

Παλέτες: iron, rainbow, γκρι, «5 σημείων» (όπως τη έδωσε ο ιδιοκτήτης), Rainbow HC και Arctic **ως προσέγγιση** (ονόματα
FLIR χωρίς δημόσια χρώματα — DESIGN_DEFAULT), και παλέτα ζωνών του χρήστη (ισόθερμες: εύρος → χρώμα) σε °C.
Στην εικόνα γράφεται θερμοκρασία, όχι ποιότητα: «κίτρινο = καλή μόνωση» θα ίσχυε μόνο από μέσα και μόνο για μία κλίμακα.
"""
from __future__ import annotations

import math

import numpy as np

from archforge.mep import facade_thermal as F

MIN_SPAN = 1.0                                  # K: the auto range never narrower than this (as the 3D view)

# name: (label, stops, status). Stops: (t ∈ [0, 1], (r, g, b)).
PALETTES = {
    "iron": ("iron", F.PALETTES["iron"], "DESIGN_DEFAULT"),
    "rainbow": ("rainbow", F.PALETTES["rainbow"], "DESIGN_DEFAULT"),
    "gray": ("γκρι", ((0.0, (0, 0, 0)), (1.0, (255, 255, 255))), "DESIGN_DEFAULT"),
    # Ιδιοκτήτης 05/11, όπως τα έδωσε: #040408 → #0000FF → #D33000 → #F08800 → #FFFF80.
    "five_point": ("5 σημείων", ((0.00, (0x04, 0x04, 0x08)), (0.25, (0x00, 0x00, 0xFF)), (0.50, (0xD3, 0x30, 0x00)),
                                 (0.75, (0xF0, 0x88, 0x00)), (1.00, (0xFF, 0xFF, 0x80))), "OWNER"),
    "rainbow_hc": ("Rainbow HC (προσέγγιση)",
                   ((0.00, (0, 0, 0)), (0.10, (40, 0, 100)), (0.25, (0, 0, 255)), (0.40, (0, 200, 255)),
                    (0.55, (0, 220, 70)), (0.70, (255, 255, 0)), (0.85, (255, 70, 0)), (1.00, (255, 255, 255))),
                   "DESIGN_DEFAULT"),
    "arctic": ("Arctic (προσέγγιση)",
               ((0.00, (8, 10, 60)), (0.30, (30, 60, 200)), (0.50, (110, 170, 235)), (0.62, (215, 195, 130)),
                (0.82, (250, 160, 30)), (1.00, (255, 250, 200))), "DESIGN_DEFAULT"),
}
ZONES = "zones"                                  # the user's zone palette, given separately


def f_to_c(v):
    return (float(v) - 32.0) * 5.0 / 9.0


def zones_in_celsius(zones, unit="C"):
    """``[(lo, hi, (r, g, b))]`` in °C, sorted. ``lo`` / ``hi`` None = open («−11 και κάτω», «105+»). A table in °F
    (the owner's camera and blanket chart) is converted once, on import."""
    out = []
    for lo, hi, rgb in zones:
        if unit.upper() == "F":
            lo = None if lo is None else f_to_c(lo)
            hi = None if hi is None else f_to_c(hi)
        out.append((None if lo is None else float(lo), None if hi is None else float(hi), tuple(int(c) for c in rgb)))
    if not out:
        raise ValueError("η παλέτα ζωνών είναι άδεια")
    return sorted(out, key=lambda z: -np.inf if z[0] is None else z[0])


def hex_rgb(text):
    t = str(text).strip().lstrip("#")
    if len(t) != 6:
        raise ValueError(f"χρώμα «{text}»: χρειάζεται #RRGGBB")
    return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))


def parse_zones(text):
    """Lines «lo; hi; #RRGGBB» (κενό = ανοιχτό άκρο), e.g. «; -11; #1A237E» or «105; ; #B71C1C»."""
    zones = []
    for n, line in enumerate(str(text).splitlines(), 1):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.replace(",", ".").split(";")] if ";" in line else line.split()
        if len(parts) != 3:
            raise ValueError(f"γραμμή {n}: χρειάζεται «από; έως; #χρώμα»")
        lo = float(parts[0]) if parts[0] else None
        hi = float(parts[1]) if parts[1] else None
        zones.append((lo, hi, hex_rgb(parts[2])))
    return zones


def _zone_rgb(theta, zones):
    th = np.asarray(theta, dtype=float)
    out = np.zeros(th.shape + (3,), dtype=np.uint8)
    out[...] = (78, 80, 86)                                    # outside every zone: «δεν ορίστηκε», never guessed
    for lo, hi, rgb in zones:
        m = np.ones(th.shape, dtype=bool)
        if lo is not None:
            m &= th >= lo
        if hi is not None:
            m &= th < hi
        out[m] = rgb
    return out


def to_rgb(theta, lo, hi, palette="iron", zones=None):
    """``(rows, cols, 3)`` uint8. ``palette`` = a key of ``PALETTES`` or ``ZONES`` (with ``zones`` in °C)."""
    if palette == ZONES:
        return _zone_rgb(theta, zones or [])
    stops = PALETTES[palette][1]
    t = np.clip((np.asarray(theta, dtype=float) - lo) / max(1e-9, hi - lo), 0.0, 1.0)
    out = np.zeros(t.shape + (3,), dtype=float)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        m = (t >= t0) & (t <= t1)
        f = (t[m] - t0) / max(1e-9, t1 - t0)
        for ch in range(3):
            out[..., ch][m] = c0[ch] + (c1[ch] - c0[ch]) * f
    return out.round().astype(np.uint8)


def colour_at(value, lo, hi, palette="iron", zones=None):
    rgb = to_rgb(np.array([[value]]), lo, hi, palette, zones)[0, 0]
    return "#%02X%02X%02X" % tuple(int(c) for c in rgb)


KIND_LABEL = {0: "Τοιχοποιία", 1: "Κολόνες / δοκοί", 2: "Κουφώματα"}


def _u_of(result, kind):
    u = result["u"]
    if kind == 0:
        return u.get("masonry")
    if kind == 1:
        return u.get("column", u.get("beam"))
    vals = [u[k] for k in ("window", "door") if k in u]
    return sum(vals) / len(vals) if vals else None


def _field(result, side):
    return result["theta"] if side == "exterior" else result["theta_inside"]


def compare(doc, wall_id, layers=None, opening_u=None, side="exterior", scale=None, palette="iron", zones=None):
    """Today and the proposal of one façade, on one scale.

    ``layers`` (``[(material id, d, λ, role)]`` exterior first) / ``opening_u`` = the proposal; both None → no proposal.
    ``scale`` = ``(lo, hi)`` °C («ίδια με φωτογραφία»), None = automatic over both pictures.
    Returns ``{"today", "proposal", "lo", "hi", "rows", "watts": (today, proposal), "reduction", "u_max"}``."""
    if side not in ("exterior", "interior"):
        raise ValueError("πλευρά: «exterior» (από έξω) ή «interior» (από μέσα)")
    today = F.facade(doc, wall_id)
    proposal = None
    if layers is not None or opening_u is not None:
        proposal = F.facade(doc, wall_id, layers=layers, opening_u=opening_u)
    fields = [_field(today, side)] + ([_field(proposal, side)] if proposal else [])
    if scale is not None:
        lo, hi = float(scale[0]), float(scale[1])
        if hi <= lo:
            raise ValueError("κλίμακα: το max πρέπει να είναι πάνω από το min")
    else:
        lo = min(float(f.min()) for f in fields)
        hi = max(float(f.max()) for f in fields)
        if hi - lo < MIN_SPAN:
            mid = (hi + lo) / 2
            lo, hi = mid - MIN_SPAN / 2, mid + MIN_SPAN / 2

    def pos(v):
        return max(0.0, min(1.0, (v - lo) / (hi - lo)))
    rows = []
    for kind in (0, 1, 2):
        mask = today["kind"] == kind
        if not mask.any():
            continue
        t_now = float(_field(today, side)[mask].mean())
        row = {"kind": kind, "label": KIND_LABEL[kind], "u": _u_of(today, kind), "theta": t_now, "pos": pos(t_now),
               "colour": colour_at(t_now, lo, hi, palette, zones)}
        if proposal is not None:
            t_p = float(_field(proposal, side)[mask].mean())
            row.update({"u_proposal": _u_of(proposal, kind), "theta_proposal": t_p, "pos_proposal": pos(t_p),
                        "colour_proposal": colour_at(t_p, lo, hi, palette, zones)})
        rows.append(row)
    w_now = today["watts"]
    w_p = proposal["watts"] if proposal else None
    from archforge.mep.design_climate import zone
    from archforge.mep.totee_20701_2 import u_max
    z = zone(doc)
    return {"today": today, "proposal": proposal, "lo": lo, "hi": hi, "side": side, "palette": palette, "rows": rows,
            "watts": (w_now, w_p), "reduction": (None if w_p is None or w_now <= 0 else (w_p - w_now) / w_now),
            "zone": z, "u_max": u_max("wall_exterior", z) if z else None}


def junction_profile(result, side="exterior", reach=0.35):
    """The surface temperature across the first column / beam edge at its mid-height (mid-length for a beam):
    ``{"label", "s": [m from the start of the profile], "theta": [°C], "edge": m}`` or None without a frame."""
    frames = [r for r in result["regions"] if r["kind"] in ("column", "beam")]
    if not frames:
        return None
    fr = frames[0]
    th = _field(result, side)
    nz, nx = th.shape
    height = result["extent"][1]
    if fr["kind"] == "column":
        s0, s1 = fr["s"]
        z = (fr["z"][0] + fr["z"][1]) / 2
        row = min(nz - 1, max(0, int((height - z) / F.H)))
        half = min(reach, (s1 - s0) / 2)
        if s0 - reach >= 0:                     # from inside the frame across its left edge, leftwards
            start, end, edge_s = s0 + half, s0 - reach, s0
        else:                                   # the frame at the wall's start: across its right edge
            start, end, edge_s = s1 - half, s1 + reach, s1
        a, b = int(round(start / F.H)), int(round(end / F.H))
        step = -1 if b < a else 1
        cols = [c for c in range(a, b + step, step) if 0 <= c < nx]
        return {"label": "σύνδεση κολόνας – τοιχοποιίας", "s": [abs(c - a) * F.H for c in cols],
                "theta": [float(th[row, c]) for c in cols], "edge": abs(round(edge_s / F.H) - a) * F.H}
    za, zb = fr["z"]
    col = min(nx - 1, max(0, int(((fr["s"][0] + fr["s"][1]) / 2) / F.H)))
    top_row = int(round((height - zb) / F.H))
    bot_row = int(round((height - za) / F.H))
    a = max(0, top_row + (bot_row - top_row) // 2)
    b = min(nz - 1, bot_row + int(reach / F.H))
    rows = list(range(a, b + 1))
    return {"label": "σύνδεση δοκού – τοιχοποιίας", "s": [(r - a) * F.H for r in rows],
            "theta": [float(th[r, col]) for r in rows], "edge": (bot_row - a) * F.H}


def facades(doc):
    """``[(wall id, label)]``: every exterior wall with a build-up, every storey — the choice of «Όψη»."""
    from archforge.architecture.wall_assemblies import layer_specs
    from archforge.core.cameras import storey_name
    from archforge.mep.ventilation import exterior_walls
    out = []
    storeys = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values()
                      if e.kind == "wall" and e.visible})
    for z in storeys:
        name = storey_name(doc, z) or f"{z:+.2f}"
        for w, (nx, ny) in exterior_walls(doc, z):
            p = w.params
            if not layer_specs(doc, p.get("wall_type", "generic")):
                continue
            length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
            side = (("+x" if nx > 0 else "−x") if abs(nx) >= abs(ny) else ("+y" if ny > 0 else "−y"))
            out.append((w.id, f"{name} · {w.name or 'τοίχος'} · όψη προς {side} · " + f"{length:.2f} m".replace(".", ",")))
    return out
