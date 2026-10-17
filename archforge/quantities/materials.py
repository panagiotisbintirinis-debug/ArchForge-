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


def pool_list(doc):
    """Pools: earthworks, concrete, waterproofing, mosaic, coping / overflow channel, pipes, equipment (site/pool.py)."""
    from archforge.site.pool import analyse, pools
    return [row for e in pools(doc) for row in analyse(doc, e)["rows"]]


def heating_list(doc):
    """Heating: equipment, pipes by the owner's Ø, loops, manifolds and every fitting of the derived layout."""
    if not any(e.kind == "heating_point" for e in doc.entities.values()):
        return []
    from archforge.mep.heating import heating_quantities
    units = {"pcs": "τεμ.", "m": "m", "m2": "m²"}
    return [(q.description, units.get(q.unit, q.unit), q.quantity) for q in heating_quantities(doc) if q.quantity > 0]


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
    if any(e.kind == "cabinet" and e.params.get("run_id") for e in doc.entities.values()):
        # Derived parts of the cabinet runs (kitchen/cabinet_run.py): worktop, cut-outs, plinth, cornice.
        from archforge.kitchen.cabinet_run import run_geometry, worktop_length
        from archforge.rendering.materials import MATERIAL_PRESETS
        for (mid, thick), metres in worktop_length(doc).items():
            name = MATERIAL_PRESETS.get(mid, {}).get("name", mid or "")
            add(f"Πάγκος κουζίνας — {name}, πάχος {thick * 100:.0f} cm", "m", metres)
        g = run_geometry(doc)
        add("Κοπή πάγκου για νεροχύτη", "τεμ.", len(g["sinks"]))
        add("Κοπή πάγκου για εστία", "τεμ.", len(g["hobs"]))
        add("Μπάζα ντουλαπιών (με τα γυρίσματα)", "m", sum(max(q[2] - q[1], q[4] - q[3]) for q in g["plinths"]))
        add("Κορνίζα κρεμαστών", "m", sum(q[2] - q[1] for q in g["cornices"]))
    return [(desc, unit, round(q, 2) if unit == "m" else q) for (desc, unit), q in sorted(counts.items()) if q]


def finishes_list(doc):
    """Finishes as the order list reads them: «Μελαμίνη δρυς — κωδ. 1234 (Προμηθευτής)».

    One row per material + supplier code.  A wall face counts its gross area
    (length x height, openings not subtracted); any other element counts as
    one piece, since its finished area is not measured here.
    """
    from archforge.rendering.materials import material_name
    from archforge.rendering.user_materials import assignments, code_for, label

    totals = {}

    def add(desc, unit, qty):
        totals[(desc, unit)] = totals.get((desc, unit), 0.0) + qty

    def text(e, role, material_id):
        code = code_for(e, role, material_id, doc)
        return label(material_name(material_id, doc), code["code"], code["supplier"])

    for e in doc.entities.values():
        p = e.params
        if e.kind == "wall":
            surface = p.get("surface_materials") or {}
            length = ((float(p["x2"]) - float(p["x1"])) ** 2 + (float(p["y2"]) - float(p["y1"])) ** 2) ** 0.5
            for face in ("exterior", "interior"):
                material_id = surface.get(face) or p.get("material_id")
                if material_id:
                    add(text(e, face, material_id) + " — όψη τοίχου (μικτό)", "m²", length * float(p.get("height", 0.0)))
            continue
        for role, material_id in assignments(doc, e):
            add(text(e, role, material_id), "τεμ.", 1)
    return [(desc, unit, round(q, 2) if unit == "m²" else int(q)) for (desc, unit), q in sorted(totals.items()) if q]


def electrical_list(doc, result=None):
    """Electrical take-off as list rows ``(description, unit, quantity, meta)`` — meta: code, why, status, source.

    One line per item with material and labour priced on it by the professional (the socket and fitting it,
    the conduit and laying it, the breaker and connecting its circuit).  Quantities only: no price in the code.
    Items whose number comes from the study (RCDs, panel enclosure, drivers) have quantity None.
    """
    pts = [e for e in doc.entities.values() if e.kind == "electrical_point"]
    if not pts:
        return []
    from archforge.core.provenance import rule
    from archforge.mep.electrical import POINT_TYPES, strip_length
    from archforge.mep.electrical_board import analyse
    from archforge.mep.luminaire_catalog import entry
    r = result if result is not None else analyse(doc)
    knx = r.get("knx")
    circuits_status = rule("electrical.socket_circuit").status

    def meta(code, why, status="MODEL_QUANTITY", source="mep/electrical.py"):
        return {"code": code, "why": why, "status": status, "source": source}

    rows = [(f"Καλώδιο αγωγός {p['mm2']:g} mm² (H07V-U ή ισοδύναμο, ανά αγωγό)".replace(".", ","), "m", p["with_waste"],
             meta(f"electrical.cable.{p['mm2']:g}mm2", "Μέτρα αγωγών από τις διαδρομές στο σχέδιο (φάση, ουδέτερος, γείωση, "
                  "επιστροφές), με τη φύρα που όρισες.", circuits_status)) for p in r["purchase"]]
    conduit = round(sum(w["conduit_m"] for w in r["walls"]), 1)
    if conduit:
        rows.append(("Σωλήνας ηλεκτρολογικός (σπιράλ) και σωλήνωση — όλες οι διαδρομές", "m", conduit,
                     meta("electrical.conduit", "Οι διαδρομές μέσα σε τοίχους, οροφή και δάπεδο, όπως τις χάραξε το πρόγραμμα.")))
    for kind, label, why in (("junction", "Κουτί διακλάδωσης", "Πάνω από κάθε πρίζα/διακόπτη στη γραμμή όδευσης."),
                             ("floor", "Κουτί δαπέδου", "Για σημεία μακριά από τοίχο (π.χ. νησίδα κουζίνας)."),
                             ("pull", "Κουτί διέλευσης", "Σε μεγάλες ευθείες ή μετά από καμπύλες, για να τραβιούνται τα καλώδια.")):
        n = r["boxes"].get(kind, 0)
        if n:
            rows.append((label, "τεμ.", n, meta(f"electrical.box.{kind}", why, rule("electrical.pull_boxes").status
                                                if kind == "pull" else "MODEL_QUANTITY")))
    breakers = {}
    for c in r["circuits"]:
        breakers[c["breaker_a"]] = breakers.get(c["breaker_a"], 0) + 1
    rows += [(f"Μικροαυτόματος {a} A και σύνδεση κυκλώματος στον πίνακα", "τεμ.", n,
              meta(f"electrical.breaker.{a}A", "Ένας ανά κύκλωμα· το μέγεθος από τους κανόνες κυκλωμάτων (προς έλεγχο ηλεκτρολόγου).",
                   circuits_status)) for a, n in sorted(breakers.items())]
    if r["circuits"]:
        rows += [("Διαφορικοί διακόπτες 30 mA — πλήθος/τύπος από τη μελέτη", "τεμ.", None,
                  meta("electrical.rcd", "Προστασία από ηλεκτροπληξία· πλήθος και τύπος τα ορίζει ο ηλεκτρολόγος.",
                       rule("electrical.rcd_30ma").status)),
                 ("Ηλεκτρικός πίνακας (κουτί, ράγες, κλέμες) — μέγεθος από τη μελέτη", "τεμ.", None,
                  meta("electrical.panel_enclosure", "Το κουτί του πίνακα· το μέγεθος από τα στοιχεία που θα μπουν.",
                       "ENGINEER_REVIEW"))]
    counts, strips = {}, {}
    for e in pts:
        t = e.params["point_type"]
        if t == "panel" or POINT_TYPES[t][1] == "low_voltage":
            continue
        cid = e.params.get("catalog_id") or ""
        if t == "led_strip":
            strips[cid] = strips.get(cid, 0.0) + strip_length(e.params)
            continue
        if knx and t in ("switch", "dimmer"):
            key = ("Μπουτόν KNX τοίχου και τοποθέτηση", "electrical.knx.button", "Μπουτόν στο bus KNX (επιλογή του πελάτη).")
        else:
            key = (POINT_TYPES[t][0] + (f" — {entry(cid).label}" if cid else "") + " και τοποθέτηση",
                   f"electrical.point.{t}" + (f".{cid}" if cid else ""), "Σημείο που υπάρχει στο σχέδιο.")
        counts[key] = counts.get(key, 0) + 1
    rows += [(label, "τεμ.", n, meta(code, why)) for (label, code, why), n in sorted(counts.items())]
    from archforge.mep.low_voltage import lv_material_rows
    rows += lv_material_rows(doc, meta)
    for cid, m in sorted(strips.items()):
        rows.append((POINT_TYPES["led_strip"][0] + (f" — {entry(cid).label}" if cid else "") + " και τοποθέτηση (με προφίλ)",
                     "m", round(m, 2), meta("electrical.strip" + (f".{cid}" if cid else ""),
                                            "Μήκος ταινίας όπως σχεδιάστηκε (π.χ. στην εσοχή της ψευδοροφής).")))
    if strips:
        rows.append(("Τροφοδοτικά ταινιών LED — από το φύλλο του κατασκευαστή", "τεμ.", None,
                     meta("electrical.led_driver", "Ισχύς και πλήθος από το φύλλο της ταινίας.", "MANUFACTURER_DATA")))
    if knx:
        import math
        waste = 1 + float(r.get("waste_pct", 0.0)) / 100.0
        lines = max(1, math.ceil(knx["bus_m"] / 1000.0))
        bus = rule("knx.bus_limits").status
        rows += [("Καλώδιο KNX bus TP (J-Y(St)Y 2×2×0,8)", "m", round(knx["bus_m"] * waste, 1),
                  meta("knx.bus_cable", "Το πράσινο καλώδιο εντολών από τον πίνακα σε κάθε μπουτόν.", bus)),
                 ("Σωλήνας για το bus KNX (χωριστός από τα 230 V) και σωλήνωση", "m", round(knx["bus_m"], 1),
                  meta("knx.bus_conduit", "Χωριστή διαδρομή για το bus.", bus)),
                 ("Τροφοδοτικό KNX με πηνίο (ανά γραμμή) — ένταση από τη μελέτη", "τεμ.", lines,
                  meta("knx.psu", "Ένα ανά γραμμή bus.", bus)),
                 ("KNX IP interface / router", "τεμ.", 1,
                  meta("knx.ip_interface", "Σύνδεση του KNX με το δίκτυο και την εφαρμογή στο κινητό.", "DESIGN_DEFAULT"))]
        if knx["onoff_channels"]:
            rows.append(("Ρελέ KNX C-Load — κανάλια On/Off", "κανάλι", knx["onoff_channels"],
                         meta("knx.actuator_channel", "Ένα κανάλι ανά ομάδα φώτων που ανάβει/σβήνει.", rule("knx.c_load").status)))
        if knx["dali_gateways"]:
            rows.append(("KNX-DALI gateway (ως 64 διευθύνσεις)", "τεμ.", knx["dali_gateways"],
                         meta("knx.dali_gateway", "Ελέγχει τα φωτιστικά με ρύθμιση έντασης DALI-2.", rule("knx.dali_gateway").status)))
        rows.append(("Προγραμματισμός KNX (ETS) και παράδοση αρχείου έργου", "τεμ.", 1,
                     meta("knx.ets_programming", "Ρύθμιση του συστήματος· το αρχείο του έργου παραδίδεται στον πελάτη.")))
    return rows


def _earth(doc):
    from archforge.construction.earthworks import earthworks
    return earthworks(doc)


def _shell(name, doc):
    from archforge.construction import shell
    return getattr(shell, name)(doc)


def insulation_list(doc):
    from archforge.construction.insulation import quantity_rows
    return quantity_rows(doc)


def plumbing_list(doc):
    """Water supply from the shared trade costing (``mep.plumbing_costing``): rows with code / why / status."""
    if not any(e.kind == "plumbing_point" for e in doc.entities.values()):
        return []
    from archforge.mep.plumbing_costing import plumbing_quantities
    return [(q.description, q.unit, q.quantity, {"code": q.code, "why": q.owner_explanation, "status": q.rule_status,
                                                 "source": q.rule_source}) for q in plumbing_quantities(doc)]


def compare_control_options(doc):
    """Cost of each control system with the project's prices — for the client's decision (owner 15/10)."""
    from archforge.mep.electrical_board import analyse
    from archforge.mep.knx import CONTROL_SYSTEMS
    from archforge.quantities.quote import priced
    out = {}
    for key, label in CONTROL_SYSTEMS.items():
        rows = electrical_list(doc, analyse(doc, {"control_system": key}))
        out[key] = {"label": label, "rows": rows, **priced(doc, rows, "Ηλεκτρολογικά")}
    return out


def furniture_list(doc):
    """Library objects placed in the drawing (furniture, sanitary ware, appliances): pieces per item.

    Code ``asset:<id>`` — the same item in every project, so one price in the price list serves them all.
    """
    from archforge.core.layers import entity_layer
    groups = {}
    for e in doc.entities.values():
        if e.kind != "library_object":
            continue
        asset = str(e.params.get("asset", ""))
        key = (e.name or "Αντικείμενο", asset)
        layer = entity_layer(e.kind, e.params)
        groups.setdefault(key, [0, layer])[0] += 1
    rows = []
    for (name, asset), (n, layer) in sorted(groups.items(), key=lambda kv: (kv[1][1], kv[0][0])):
        why = {"sanitary": "Είδος υγιεινής", "kitchen": "Συσκευή κουζίνας"}.get(layer, "Έπιπλο / αντικείμενο")
        rows.append((name, "τεμ.", n, {"code": f"asset:{asset}" if asset else f"desc:{name}",
                                         "why": f"{why} τοποθετημένο στο σχέδιο (Βιβλιοθήκη)", "status": "MODEL_QUANTITY"}))
    return rows


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
            ("Ύδρευση", "Ύδρευση — σωληνώσεις, συλλέκτες, σημεία", plumbing_list(doc), ("Προμελέτη — προς έλεγχο μηχανολόγου.",)),
            ("Αποχέτευση", "Αποχέτευση — σωλήνες και εξαρτήματα", drainage_list(doc), ("Προμελέτη — προς έλεγχο μηχανολόγου.",)),
            ("Ηλεκτρολογικά", "Ηλεκτρολογικά — καλώδια, σωλήνες, κουτιά, ασφάλειες, σημεία, φωτιστικά", electrical_list(doc),
             ("Προμελέτη — προς έλεγχο ηλεκτρολόγου· κανόνες με την κατάστασή τους στην καρτέλα «Ηλεκτρ. πίνακας».",
              "Καλώδιο: μέτρα ανά αγωγό με τη φύρα που όρισες.")),
            ("Θέρμανση", "Θέρμανση — πηγή, σώματα / βρόχοι, σωλήνες, συλλέκτες, υδρονομείς, βάνες", heating_list(doc),
             ("Προμελέτη: διατομές από κανόνα ιδιοκτήτη, μήκη από τη χάραξη· θερμικά φορτία, ισχύς σωμάτων, "
              "κυκλοφορητής και εξισορρόπηση από μηχανολόγο.",)),
            ("Πισίνα", "Πισίνα — εκσκαφή, σκυρόδεμα, στεγάνωση, ψηφίδα, στέψη / κανάλι, σωλήνες, εξοπλισμός", pool_list(doc),
             ("Ποσότητες από το σχέδιο· αντλία, φίλτρο, χημεία, στατική λεκάνης και ηλεκτρολογική μελέτη από μηχανικούς· "
              "εξοπλισμός όπως δηλώθηκε στις Ιδιότητες της πισίνας.",)),
            ("Φέρων", "Φέρων οργανισμός και θεμελίωση", structure_list(doc), ("Προμελέτη — προς έλεγχο στατικού μηχανικού.",)),
            ("Χωματουργικά", "Χωματουργικά — εκσκαφές από ό,τι δίνει το σχέδιο", _earth(doc)["rows"],
             tuple(_earth(doc)["basis"]) + tuple("Δεν μετρήθηκε — " + m for m in _earth(doc)["missing"])
             + ("Χωρίς χώρο εργασίας/πρανή, αφράτευση, επιχώσεις (από τον εργολάβο).",)),
            ("Τοιχοποιίες", "Τοιχοποιίες — m² ανά τύπο τοίχου (μείον ανοίγματα)", _shell("masonry_list", doc),
             ("Τεμάχια (τούβλα) μόνο με τα τεμ./m² του προϊόντος που θα εισαγάγεις — όχι τυπική τιμή.",)),
            ("Πλάκες", "Σκυρόδεμα πλακών — εμβαδόν × πάχος του μοντέλου", _shell("slab_concrete_list", doc),
             ("Οπλισμός και καλούπια από τη στατική μελέτη.",)),
            ("Σοβατίσματα", "Σοβάδες εσωτερικοί και εξωτερικοί", _shell("plaster_list", doc), ()),
            ("Κεραμοσκεπή", "Κεραμοσκεπή — επιφάνεια κλίσης ανά τύπο κεραμιδιού", _shell("roof_list", doc),
             ("Κεραμίδια σε τεμάχια μόνο με τα τεμ./m² του προϊόντος.",)),
            ("Κουφώματα", "Κουφώματα — ανά τύπο, φινίρισμα και μέγεθος", _shell("joinery_list", doc), ()),
            ("Μονώσεις", "Θερμομονώσεις και στεγανώσεις ανά επιφάνεια", insulation_list(doc),
             ("Εμβαδά από το σχέδιο· υλικό, πάχος και σύστημα όπως επιλέχθηκαν (καρτέλα «Μονώσεις»)· "
              "ενεργειακή μελέτη από μηχανικό.",)),
            ("Κάγκελα", "Κάγκελα — τρέχοντα μέτρα ανά τύπο", railing_list(doc),
             ("Τιμή ανά τρέχον μέτρο από τον προμηθευτή (με ορθοστάτες, στερέωση, τοποθέτηση).",)),
            ("Κουζίνα", "Ντουλάπια κουζίνας — κουφάρια, μηχανισμοί, χερούλια", kitchen_list(doc),
             ("Ενδεικτικές διαστάσεις ευρωπαϊκής πρακτικής, γενικοί τύποι χωρίς μάρκα.",)),
            ("Έπιπλα", "Έπιπλα, είδη υγιεινής και συσκευές (Βιβλιοθήκη)", furniture_list(doc),
             ("Ένα τεμάχιο ανά αντικείμενο του σχεδίου· τιμή από τον προμηθευτή — ίδιος κωδικός σε κάθε έργο.",)),
            ("Υλικά", "Υλικά και κωδικοί προμηθευτή (μελαμίνες, πάγκοι, τελειώματα)", finishes_list(doc),
             ("Ο κωδικός και ο προμηθευτής είναι όσα έγραψες στα «Υλικά / επιφάνειες».",
              "Τοίχοι: μικτό εμβαδόν όψης (χωρίς αφαίρεση ανοιγμάτων)· άλλα στοιχεία: πλήθος."))):
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
