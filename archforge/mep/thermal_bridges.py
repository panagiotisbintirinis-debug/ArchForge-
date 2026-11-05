"""Θερμογέφυρες: θέσεις και μήκη από το σχέδιο, ψ από τον κατάλογο του έργου (κριτική v5 k7, μηχανικός ενεργειακής).

«Κατάλογος ψ = πίνακας με κωδικό λεπτομέρειας της ΤΟΤΕΕ 20701-1 … ψ, πηγή — συμπληρώνει ο ιδιοκτήτης, ποτέ το
πρόγραμμα. Η γεωμετρία βρίσκει και μετρά μήκη.»  Χωρίς μήκος δεν υπάρχει Ψ·l.

Τι βρίσκει η γεωμετρία (ανά όροφο, από τους εξωτερικούς τοίχους του ``mep/ventilation.exterior_walls``):

* εξωτερική γωνία / εσωτερική (εισέχουσα) γωνία δύο εξωτερικών τοίχων — μήκος = ύψος τοίχου·
* σύνδεση εσωτερικού τοίχου με εξωτερικό — μήκος = ύψος του εσωτερικού τοίχου·
* τοίχος–δάπεδο στο κατώτερο επίπεδο, ενδιάμεση πλάκα (βάση τοίχου ανώτερου ορόφου), τοίχος–δώμα/στέγη (το μέρος της
  κορυφής του τοίχου που δεν σκεπάζεται από εξωτερικό τοίχο του από πάνω ορόφου) — μήκος = μήκος τοίχου·
* ανά κούφωμα εξωτερικού τοίχου: πρέκι (πλάτος), ποδιά ή κατωκάσι (πλάτος), λαμπάδες (2 × ύψος) — τρεις χωριστές
  θερμογέφυρες με διαφορετικό ψ·
* κολόνα μέσα στον εξωτερικό τοίχο — μήκος = ύψος κολόνας.

Δεν βρίσκονται ακόμη από τη γεωμετρία (λέγεται στο αποτέλεσμα): πρόβολοι εξωστών, δοκοί στο περίγραμμα.

Το ψ [W/(m·K)] κάθε είδους, ο κωδικός λεπτομέρειας και η πηγή του γράφονται από τον χρήστη στο έργο (μία αναίρεση).
Είδος χωρίς ψ δεν μετράει στις απώλειες και λέγεται· καμία τιμή δεν μπαίνει από μνήμης.
"""
from __future__ import annotations

import math

KIND = "thermal_bridge_psi"
TOL = 0.03

# key → label (the order of the list)
TYPES = {
    "corner_out": "Εξωτερική γωνία τοίχων",
    "corner_in": "Εσωτερική (εισέχουσα) γωνία τοίχων",
    "partition": "Σύνδεση εσωτερικού με εξωτερικό τοίχο",
    "floor_ground": "Τοίχος – δάπεδο κατώτερου επιπέδου",
    "floor_mid": "Τοίχος – ενδιάμεση πλάκα",
    "roof": "Τοίχος – δώμα / στέγη",
    "lintel": "Πρέκι κουφώματος",
    "sill": "Ποδιά παραθύρου",
    "threshold": "Κατωκάσι πόρτας",
    "jamb": "Λαμπάδες κουφώματος",
    "column": "Κολόνα στον εξωτερικό τοίχο",
}
NOT_FOUND = "πρόβολοι εξωστών, δοκοί στο περίγραμμα"


def _len(p):
    return math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))


def _storeys(doc):
    return sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall" and e.visible})


def _ends(p):
    return (float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"]))


def _on_axis(p, x, y):
    """``(distance from the axis, t along it 0…1)`` of a point to a wall."""
    (x1, y1), (x2, y2) = _ends(p)
    L = math.hypot(x2 - x1, y2 - y1) or 1.0
    t = ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / (L * L)
    d = abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)) / L
    return d, t


def _overlap(p, q):
    """Length of wall ``q`` lying on the line of wall ``p`` (0 when not collinear)."""
    (x1, y1), (x2, y2) = _ends(p)
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-9:
        return 0.0
    ends = _ends(q)
    if any(_on_axis(p, x, y)[0] > TOL for x, y in ends):
        return 0.0
    ts = sorted(max(0.0, min(1.0, _on_axis(p, x, y)[1])) for x, y in ends)
    return (ts[1] - ts[0]) * L


def find(doc):
    """``[{"type", "label", "length_m", "ids", "storey", "at"}]`` — every thermal bridge the drawing shows, measured."""
    from archforge.core.notices import not_computed
    from archforge.mep.ventilation import exterior_walls
    out = []

    def add(kind, length, ids, z, at):
        if length > 1e-6:
            out.append({"type": kind, "label": TYPES[kind], "length_m": round(length, 3), "ids": list(ids),
                        "storey": z, "at": (round(at[0], 3), round(at[1], 3))})

    storeys = _storeys(doc)
    outer_by = {}
    for z in storeys:
        try:
            outer_by[z] = exterior_walls(doc, z)
        except Exception as exc:                        # said, never guessed
            not_computed("thermal_bridges.exterior", f"Θερμογέφυρες: δεν βρέθηκαν οι εξωτερικοί τοίχοι {z:+.2f}", exc=exc)
            outer_by[z] = []
    for i, z in enumerate(storeys):
        outer = outer_by[z]
        ext = {w.id: (w, n) for w, n in outer}
        walls = [e for e in doc.entities.values() if e.kind == "wall" and e.visible
                 and abs(float(e.params.get("z", 0.0)) - z) < 0.05]
        # Corners of two exterior walls: outside (convex) or re-entrant.
        pairs = [(a, b) for k, a in enumerate(outer) for b in outer[k + 1:]]
        for (wa, na), (wb, _nb) in pairs:
            ends_a = _ends(wa.params)
            for k_a, pa in enumerate(ends_a):
                far_b = next((q for pb, q in (_ends(wb.params), _ends(wb.params)[::-1]) if math.dist(pa, pb) <= TOL), None)
                if far_b is None:
                    continue
                L = math.dist(pa, far_b) or 1.0
                db = ((far_b[0] - pa[0]) / L, (far_b[1] - pa[1]) / L)
                far_a = ends_a[1 - k_a]
                La = math.dist(pa, far_a) or 1.0
                da = ((far_a[0] - pa[0]) / La, (far_a[1] - pa[1]) / La)
                if abs(da[0] * db[1] - da[1] * db[0]) < 0.17:      # < ~10°: one straight wall split in two, no corner
                    continue
                kind = "corner_out" if db[0] * na[0] + db[1] * na[1] < 0 else "corner_in"
                h = min(float(wa.params["height"]), float(wb.params["height"]))
                add(kind, h, (wa.id, wb.id), z, pa)
        # A partition ending on an exterior wall.
        for w in walls:
            if w.id in ext:
                continue
            for x, y in _ends(w.params):
                for wx, _n in outer:
                    d, t = _on_axis(wx.params, x, y)
                    if d <= float(wx.params["thickness"]) / 2 + TOL and 0.0 < t < 1.0:
                        add("partition", float(w.params["height"]), (w.id, wx.id), z, (x, y))
                        break
        # Slabs along the exterior walls.
        above = [(s, ow) for s in storeys[i + 1:] for ow, _n in outer_by[s]]
        for w, _n in outer:
            p = w.params
            L = _len(p)
            mid = ((float(p["x1"]) + float(p["x2"])) / 2, (float(p["y1"]) + float(p["y2"])) / 2)
            add("floor_ground" if i == 0 else "floor_mid", L, (w.id,), z, mid)
            top = z + float(p["height"])
            covered = sum(_overlap(p, ow.params) for s, ow in above if abs(s - top) < 0.25)
            add("roof", max(0.0, L - covered), (w.id,), z, mid)
        # Openings of the exterior walls: three bridges each.
        for o in doc.entities.values():
            if o.kind not in ("door", "window", "opening") or o.parent_id not in ext:
                continue
            host = ext[o.parent_id][0].params
            width, height = float(o.params.get("width", 0.0)), float(o.params.get("height", 0.0))
            off = float(o.params.get("offset", 0.0)) + width / 2
            (x1, y1), (x2, y2) = _ends(host)
            L = _len(host) or 1.0
            at = (x1 + (x2 - x1) * off / L, y1 + (y2 - y1) * off / L)
            add("lintel", width, (o.id,), z, at)
            add("threshold" if o.kind == "door" else "sill", width, (o.id,), z, at)
            add("jamb", 2 * height, (o.id,), z, at)
        # Columns inside an exterior wall.
        for c in doc.entities.values():
            if c.kind != "structural_column" or abs(float(c.params.get("z", 0.0)) - z) > 0.05:
                continue
            x, y = float(c.params["x"]), float(c.params["y"])
            for wx, _n in outer:
                d, t = _on_axis(wx.params, x, y)
                if d <= float(wx.params["thickness"]) / 2 + TOL and -0.01 <= t <= 1.01:
                    add("column", float(c.params.get("height", wx.params["height"])), (c.id, wx.id), z, (x, y))
                    break
    return out


# ------------------------------------------------------------------ the project's ψ catalogue

def entity(doc):
    return next((e for e in doc.entities.values() if e.kind == KIND), None)


def catalogue(doc):
    """``{type: {"psi": float|None, "code": str, "source": str}}`` — what the user wrote for this project."""
    own = dict((entity(doc).params.get("values") if entity(doc) is not None else None) or {})
    out = {}
    for key in TYPES:
        v = dict(own.get(key) or {})
        psi = v.get("psi")
        out[key] = {"psi": None if psi in (None, "") else float(psi), "code": str(v.get("code", "")),
                    "source": str(v.get("source", ""))}
    return out


def set_command(doc, key, psi=None, code="", source=""):
    """One undo: the ψ, detail code and source of one kind (``psi=None`` clears it)."""
    from archforge.core.commands import AddEntity, UpdateEntity
    from archforge.core.model import Entity
    if key not in TYPES:
        raise ValueError(f"άγνωστο είδος θερμογέφυρας {key}")
    values = {k: dict(v) for k, v in ((entity(doc).params.get("values") if entity(doc) else None) or {}).items()}
    if psi is None and not code and not source:
        values.pop(key, None)
    else:
        values[key] = {"psi": None if psi is None else float(psi), "code": str(code), "source": str(source)}
    e = entity(doc)
    if e is None:
        return AddEntity(Entity(KIND, {"values": values}, name="Θερμογέφυρες: ψ του έργου"))
    return UpdateEntity(e.id, {"values": values})


def summary(doc, found=None):
    """``{"rows": [...], "h_tb": W/K, "missing_m": m, "missing_n": count, "not_found": str}`` — one row per kind:
    count, total length, ψ, code, source, Ψ·l (None without ψ), ids (for «Δείξε»)."""
    found = find(doc) if found is None else found
    cat = catalogue(doc)
    rows, h_tb, missing_m, missing_n = [], 0.0, 0.0, 0
    for key, label in TYPES.items():
        items = [f for f in found if f["type"] == key]
        if not items:
            continue
        length = sum(f["length_m"] for f in items)
        psi = cat[key]["psi"]
        psi_l = None if psi is None else psi * length
        if psi_l is None:
            missing_m += length
            missing_n += len(items)
        else:
            h_tb += psi_l
        rows.append({"type": key, "label": label, "count": len(items), "length_m": round(length, 2), "psi": psi,
                     "code": cat[key]["code"], "source": cat[key]["source"],
                     "psi_l": None if psi_l is None else round(psi_l, 3),
                     "ids": sorted({i for f in items for i in f["ids"]})})
    return {"rows": rows, "h_tb": round(h_tb, 3), "missing_m": round(missing_m, 2), "missing_n": missing_n,
            "not_found": NOT_FOUND}
