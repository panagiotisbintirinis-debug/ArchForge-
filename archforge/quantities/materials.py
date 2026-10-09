"""Priced material lists: every quantity the program measures, with a price column the user fills in.

Each list is ``[(description, unit, quantity)]`` (quantity None = from another
study, e.g. reinforcement from the structural design).  Isotex has its own
list, and so do ICF and plasterboard (ceilings, stud walls).  ``write_workbook`` writes them as sheets of one .xlsx whose totals are
Excel formulas (quantity × unit price, SUM).
"""
from __future__ import annotations

from archforge.quantities.xlsx import write_priced_workbook


def isotex_list(doc):
    from archforge.construction.isotex import BLOCKS, take_off_isotex
    r = take_off_isotex(doc)
    if not r["walls"]:
        return []
    rows = [(f"Τεμάχιο {BLOCKS[c][0]} — 50×25×{BLOCKS[c][1] * 100:.0f} cm", "τεμ.", v["blocks"]) for c, v in r["by_code"].items()]
    t = r["totals"]
    rows += [("Σκυρόδεμα πλήρωσης τεμαχίων" + (" (μέρος κατ' εκτίμηση)" if r["estimated"] else ""), "m³", t["concrete_m3"]),
             ("Οπλισμός τοιχωμάτων (κατακόρυφος/οριζόντιος) — από τη στατική μελέτη", "kg", None),
             ("Πρέκια / σενάζ — από τη στατική μελέτη", "m", None),
             ("Εργασία τοποθέτησης τεμαχίων Isotex", "m²", t["net_m2"]),
             ("Εργασία σκυροδέτησης πλήρωσης", "m³", t["concrete_m3"])]
    return rows


def takeoff_list(doc):
    from archforge.quantities.takeoff import take_off
    r = take_off(doc)
    t, d = r["totals"], r["demolition"]
    rows = [("Βαφή τοίχων", "m²", t["paint_walls_m2"]), ("Βαφή οροφών", "m²", t["paint_ceiling_m2"]),
            ("Πλακάκια δαπέδου", "m²", t["floor_tiles_m2"]), ("Πλακάκια τοίχου (υγρά)", "m²", t["wall_tiles_m2"]),
            ("Ξύλινο δάπεδο", "m²", t["wood_floor_m2"]), ("Σοβατεπί", "m", t["skirting_m"]),
            ("Καθαίρεση τοίχων", "m³", d["walls_m3"]), ("Διάνοιξη ανοιγμάτων σε υφιστάμενους τοίχους", "τεμ.", d["openings_to_cut"])]
    return [row for row in rows if row[2]]


def drainage_list(doc):
    if not any(e.kind == "plumbing_point" for e in doc.entities.values()):
        return []
    from archforge.mep.drainage import route_drainage_cached
    route = route_drainage_cached(doc)
    rows = [(f"Σωλήνας αποχέτευσης PVC Φ{dn}", "m", round(m, 2)) for dn, m in sorted(route["report"]["length_by_dn"].items()) if m > 0]
    for kind, label in (("floor_drain", "Σιφώνι δαπέδου"), ("stack", "Στήλη αποχέτευσης — αερισμός/καπέλο"), ("manhole", "Φρεάτιο")):
        n = sum(1 for x in route["nodes"] if x["kind"] == kind)
        if n:
            rows.append((label, "τεμ.", n))
    return rows


def structure_list(doc):
    """Concrete of the frame and foundation from the up-to-date analysis (reinforcement weight: from the study)."""
    from archforge.structure.analysis import fresh_result
    r = fresh_result(doc)
    if not r or r.get("error"):
        return []
    cols = beams = 0.0
    for mid, m in r["members"].items():
        e = doc.entities.get(mid)
        if e is None or m["material"] != "rc":
            continue
        p = e.params
        if e.kind == "structural_column":
            cols += float(p["width"]) * float(p["depth"]) * float(p["height"])
        else:
            L = ((float(p["x2"]) - float(p["x1"])) ** 2 + (float(p["y2"]) - float(p["y1"])) ** 2) ** 0.5
            beams += float(p["width"]) * float(p["height"]) * L
    fd = r.get("foundation") or {}
    rows = [("Σκυρόδεμα κολονών", "m³", round(cols, 2)), ("Σκυρόδεμα δοκαριών", "m³", round(beams, 2)),
            ("Σκυρόδεμα πεδίλων", "m³", round(sum(f["concrete_m3"] for f in fd.get("footings", ())), 2)),
            ("Σκυρόδεμα συνδετήριων δοκών", "m³", round(sum(t["concrete_m3"] for t in fd.get("ties", ())), 2)),
            ("Σκυρόδεμα πεδιλοδοκών", "m³", round(sum(s["concrete_m3"] for s in fd.get("strips", ())), 2)),
            ("Οπλισμός B500C (φέρων και θεμελίωση) — από τη στατική μελέτη", "kg", None),
            ("Καλούπια (ξυλότυποι)", "m²", None)]
    return [row for row in rows if row[2] is None or row[2] > 0]


def railing_list(doc):
    """Railings in running metres per type and height (along the slope on a flight)."""
    from archforge.architecture.railings import HANDRAILS, TYPES, length
    by = {}
    for e in doc.entities.values():
        if e.kind != "railing":
            continue
        p = e.params
        dz = [float(q[2]) if len(q) > 2 else 0.0 for q in p["points"]]
        sloped = max(dz) - min(dz) > 1e-6
        key = (TYPES[p["railing_type"]]["label"], float(p["height"]), sloped, HANDRAILS.get(p.get("handrail"), ""))
        by[key] = by.get(key, 0.0) + length(p)
    rows = []
    for (label, height, sloped, handrail), metres in sorted(by.items()):
        where = "σκάλας" if sloped else "οριζόντιο"
        rail = f", κουπαστή {handrail.lower()}" if handrail and handrail != "Χωρίς" else ""
        rows.append((f"Κάγκελο {label.lower()} {where}, ύψος {height * 100:.0f} cm{rail}", "m", round(metres, 2)))
    return rows


def kitchen_list(doc):
    """Cabinets by type and size, their mechanisms and handles (pieces; gola/edge profiles in metres)."""
    from archforge.kitchen.cabinets import FRONT_STYLES, MECHANISMS, TYPES, cabinet_boxes, mechanism
    counts = {}

    def add(desc, unit, qty):
        counts[(desc, unit)] = counts.get((desc, unit), 0) + qty

    for e in doc.entities.values():
        if e.kind != "cabinet":
            continue
        p = e.params
        kind, style, handle = p["cabinet_type"], p.get("front_style", "flat"), p.get("handle", "bar")
        size = f"{float(p['width']) * 100:.0f}×{float(p['depth']) * 100:.0f}×{float(p['height']) * 100:.0f} cm"
        add(f"{TYPES[kind][0]} {size} — πρόσοψη {FRONT_STYLES[style].lower()}", "τεμ.", 1)
        mech = mechanism(p)
        if mech != "none":
            add(f"Μηχανισμός: {MECHANISMS[mech][0]}", "τεμ.", 1)
        bars = [max(hi[i] - lo[i] for i in range(3)) for role, lo, hi in cabinet_boxes(p) if role == "handle"]
        if style == "gola":
            add("Προφίλ gola αλουμινίου", "m", sum(bars))
        elif handle == "edge":
            add("Προφίλ ακμής (χερούλι)", "m", sum(bars))
        elif handle in ("bar", "knob"):
            add("Χερούλι " + ("μπάρα" if handle == "bar" else "πόμολο"), "τεμ.", len(bars))
    return [(desc, unit, round(q, 2) if unit == "m" else q) for (desc, unit), q in sorted(counts.items()) if q]


def all_lists(doc):
    """``[(sheet name, title, rows, notes)]`` for the lists that have quantities."""
    from archforge.construction.drywall import PROVENANCE as DRYWALL, SOURCES as DRYWALL_SOURCES, drywall_list
    from archforge.construction.icf import PROVENANCE as ICF, icf_list
    from archforge.construction.isotex import PROVENANCE as ISOTEX
    out = []
    for name, title, rows, notes in (
            ("Isotex", "Λίστα Isotex — τεμάχια, σκυρόδεμα, εργασίες", isotex_list(doc), (ISOTEX,)),
            ("ICF", "Λίστα ICF — ευθέα και γωνιακά τεμάχια, σκυρόδεμα, εργασίες", icf_list(doc), (ICF,)),
            ("Γυψοσανίδες", "Γυψοσανίδες — ψευδοροφές CD/UD και τοίχοι CW/UW", drywall_list(doc),
             (DRYWALL, "Πηγές: " + DRYWALL_SOURCES)),
            ("Επιμέτρηση", "Επιμέτρηση εργασιών (σύνολα έργου)", takeoff_list(doc), ("Ανά χώρο: Κατασκευή → Επιμέτρηση εργασιών.",)),
            ("Αποχέτευση", "Αποχέτευση — σωλήνες και εξαρτήματα", drainage_list(doc), ("Προμελέτη — προς έλεγχο μηχανολόγου.",)),
            ("Φέρων", "Φέρων οργανισμός και θεμελίωση", structure_list(doc), ("Προμελέτη — προς έλεγχο στατικού μηχανικού.",)),
            ("Κάγκελα", "Κάγκελα — τρέχοντα μέτρα ανά τύπο", railing_list(doc),
             ("Τιμή ανά τρέχον μέτρο από τον προμηθευτή (με ορθοστάτες, στερέωση, τοποθέτηση).",)),
            ("Κουζίνα", "Ντουλάπια κουζίνας — κουφάρια, μηχανισμοί, χερούλια", kitchen_list(doc),
             ("Ενδεικτικές διαστάσεις ευρωπαϊκής πρακτικής, γενικοί τύποι χωρίς μάρκα.",))):
        if rows:
            out.append((name, title, rows, ("Συμπλήρωσε τις κίτρινες στήλες (τιμή μονάδας και ό,τι ποσότητα λείπει)· "
                                            "τα σύνολα βγαίνουν αυτόματα.",) + tuple(notes)))
    return out


def write_workbook(doc, path, only=None):
    sheets = [s for s in all_lists(doc) if only is None or s[0] in only]
    if not sheets:
        return None
    from archforge.quantities.quote import settings
    return write_priced_workbook(path, sheets, settings(doc)['prices'])
