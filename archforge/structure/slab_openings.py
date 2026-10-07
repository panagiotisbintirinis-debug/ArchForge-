"""Openings in slabs (stair wells): the reinforcement bands around them.

A stair well cuts the slab's bars.  The rules used here (Greek practice and
EN 1992-1-1 detailing, stated so a structural engineer can check them):

* **Interrupted steel is replaced**: the bars of each direction that the
  opening cuts (opening width ÷ bar spacing) are placed beside the opening,
  half on each side, same Ø, bottom — at least 2Ø12 per side; the same
  number on top (the free edge has negative moments too).  Each bar runs
  past the corners by an anchorage length lb = 40Ø (≥ 0.50 m).
* **Edge band (ζώνη ενίσχυσης / κρυφοδοκός)** on every edge of the opening
  that is not on a wall or beam: b = 0.40 m, slab depth, the band bars
  above held by closed stirrups Ø8/20.
* **Corners**: 2Ø12 diagonal bars at 45°, top and bottom, at every
  re-entrant corner (crack control), length 2·lb.
* **Large openings**: an opening longer than half of the panel's span in
  that direction (or wider than 1/3 of the short span across it) changes how
  the slab carries load — a visible beam around the well is proposed and
  the panel is flagged for the structural engineer.

Pre-design for review by a structural engineer.
"""
from __future__ import annotations

import math

PROVENANCE = ("Ζώνες ενίσχυσης οπών πλάκας: αντικατάσταση διακοπτόμενου οπλισμού εκατέρωθεν (½ ανά πλευρά, ≥ 2Ø12, κάτω και άνω), "
              "κρυφοδοκός b=40 cm με συνδετήρες Ø8/20 στα ελεύθερα άκρα, διαγώνια 2Ø12 στις γωνίες, lb = 40Ø ≥ 0,50 m "
              "(EN 1992-1-1 §9.3, πρακτική λεπτομέρειας) — προς έλεγχο από στατικό μηχανικό")
BAND = 0.40
MIN_BARS, MIN_D = 2, 12
SUPPORT_TOL = 0.20


def _lb(d_mm):
    return max(0.50, 40 * d_mm / 1000)


def stair_openings(doc):
    """``[(stair entity, (x0, y0, x1, y1), slab top z)]`` — the well of every stair in the slab it reaches."""
    from archforge.architecture.stairs import candidate_from_params, stair_opening_polygon
    out = []
    for e in doc.entities.values():
        if e.kind != "stair":
            continue
        try:
            poly = stair_opening_polygon(candidate_from_params(e.params))
        except Exception:
            continue
        if not poly:
            continue
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        out.append((e, (min(xs), min(ys), max(xs), max(ys)), float(e.params.get("upper_floor_z", e.params["upper_z"]))))
    return out


def _supported_edges(doc, box, slab_z):
    """Edges of the opening that sit on a wall or beam (no band needed there): subset of {"x0","x1","y0","y1"}."""
    x0, y0, x1, y1 = box
    out = set()
    for e in doc.entities.values():
        p = e.params
        if e.kind == "wall":
            top = float(p.get("z", 0.0)) + float(p.get("height", 0.0))
            if abs(top - slab_z) > 0.5:
                continue
        elif e.kind == "structural_beam":
            if abs(float(p["z"]) + float(p["height"]) - slab_z) > 0.5:
                continue
        else:
            continue
        ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        half = float(p.get("thickness", p.get("width", 0.2))) / 2 + SUPPORT_TOL
        if abs(ax - bx) < 0.05:                                     # along y
            for side, edge in (("x0", x0), ("x1", x1)):
                if abs(ax - edge) <= half and min(ay, by) <= y0 + 0.1 and max(ay, by) >= y1 - 0.1:
                    out.add(side)
        if abs(ay - by) < 0.05:                                     # along x
            for side, edge in (("y0", y0), ("y1", y1)):
                if abs(ay - edge) <= half and min(ax, bx) <= x0 + 0.1 and max(ax, bx) >= x1 - 0.1:
                    out.add(side)
    return out


def _crosses(p, box, inset=0.10):
    """Does the beam's axis pass through the opening (not just along its edge)?"""
    x0, y0, x1, y1 = box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset
    ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    for i in range(41):
        t = i / 40
        x, y = ax + (bx - ax) * t, ay + (by - ay) * t
        if x0 < x < x1 and y0 < y < y1:
            return True
    return False


def _band_bars(open_width, bars):
    """Bars per side replacing those cut over ``open_width`` (bars = (Ø mm, spacing m))."""
    d, s = bars
    cut = math.ceil(open_width / s - 1e-9)
    need = max(cut / 2 * math.pi * (d / 1000) ** 2 / 4, MIN_BARS * math.pi * (MIN_D / 1000) ** 2 / 4)
    # Same steel area in a few heavier bars (Ø12–Ø16), at least 2Ø12.
    for dia in (12, 14, 16):
        n = max(MIN_BARS, math.ceil(need / (math.pi * (dia / 1000) ** 2 / 4) - 1e-9))
        if n <= 5 or dia == 16:
            return n, dia
    return n, 16


def openings_in_slabs(doc, panels, h):
    """The well of each stair, the slab panel it is in and its reinforcement bands."""
    out = []
    for stair, box, z in stair_openings(doc):
        x0, y0, x1, y1 = box
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hosts = [p for p in panels if p.get("bbox") and p["storey_z"] < z - 1.0
                 and p["bbox"][0] - .05 <= cx <= p["bbox"][2] + .05 and p["bbox"][1] - .05 <= cy <= p["bbox"][3] + .05]
        if not hosts:
            continue
        p = max(hosts, key=lambda q: q["storey_z"])
        bars_x = p["main_bars"] if p["short_dir"] == "x" else p["dist_bars"]          # bars running along x
        bars_y = p["dist_bars"] if p["short_dir"] == "x" else p["main_bars"]
        wx, wy = x1 - x0, y1 - y0
        supported = _supported_edges(doc, box, z)
        bands = []
        # Bars along x are cut over the opening's y-size; they go beside the edges y0 / y1.
        nx_, dx_ = _band_bars(wy, bars_x)
        ny_, dy_ = _band_bars(wx, bars_y)
        for side, n, d, along, length in (("y0", nx_, dx_, "x", wx), ("y1", nx_, dx_, "x", wx),
                                          ("x0", ny_, dy_, "y", wy), ("x1", ny_, dy_, "y", wy)):
            if side in supported:
                continue
            L = length + 2 * _lb(d)
            bands.append({"side": side, "along": along, "bottom": f"{n}Ø{d}", "top": f"{n}Ø{d}", "n": n, "d": d,
                          "length_m": round(L, 2), "width_m": BAND, "stirrups": "Ø8/20",
                          "text": f"{ {'y0': 'Νότια', 'y1': 'Βόρεια', 'x0': 'Δυτική', 'x1': 'Ανατολική'}[side]} πλευρά: ζώνη {BAND * 100:.0f}×{h * 100:.0f}, "
                                  f"{n}Ø{d} κάτω + {n}Ø{d} άνω, L={L:.2f} m, συνδ. Ø8/20"})
        free = [b["side"] for b in bands]
        corners = sum(1 for c in (("x0", "y0"), ("x1", "y0"), ("x1", "y1"), ("x0", "y1")) if c[0] in free or c[1] in free)
        bx0, by0, bx1, by1 = p["bbox"]
        span_x, span_y = bx1 - bx0, by1 - by0
        short = min(span_x, span_y)
        large = wx > 0.5 * span_x or wy > 0.5 * span_y or (wx if span_x <= span_y else wy) > short / 3 + 1e-9 and min(wx, wy) > 1.0
        warnings = []
        if large:
            warnings.append("Μεγάλο άνοιγμα για την πλάκα: προτείνεται εμφανής δοκός περιμετρικά της οπής — έλεγχος στατικού")
        crossing = [b.name or "δοκός" for b in doc.entities.values() if b.kind == "structural_beam"
                    and abs(float(b.params["z"]) + float(b.params["height"]) - z) < 0.5 and _crosses(b.params, box)]
        if crossing:
            warnings.append(f"Η δοκός {', '.join(crossing)} περνά μέσα από την οπή της σκάλας — μετακίνηση δοκού ή σκάλας")
        warning = " · ".join(warnings)
        out.append({"slab": p["mark"], "stair": stair.name or "Σκάλα", "stair_id": stair.id, "box": (x0, y0, x1, y1),
                    "size": (round(wx, 2), round(wy, 2)), "bands": bands, "supported": sorted(supported),
                    "corners": corners, "corner_bars": f"2Ø12 διαγώνια άνω και κάτω × {corners} γωνίες" if corners else "",
                    "warning": warning,
                    "text": f"Οπή σκάλας {wx:.2f}×{wy:.2f} στην {p['mark']}: " + ("; ".join(b["text"] for b in bands) or "όλα τα άκρα σε τοίχο/δοκό")
                            + (f"; γωνίες 2Ø12 διαγώνια άνω/κάτω ({corners})" if corners else "") + (f" ⚠ {warning}" if warning else "")})
    return out
