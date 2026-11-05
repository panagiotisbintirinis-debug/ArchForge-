"""Ζωντανές λίστες (κριτική v5 k9): κουφώματα, κέλυφος, χώροι, κυκλώματα — από το ίδιο Document, κάθε γραμμή με τα
αντικείμενά της (αμφίδρομη επιλογή) και «πώς μετρήθηκε».

Κάθε λίστα είναι ``{"title", "columns": [(key, label)], "rows": [...], "check": [str], "editable": {key: kind}}``·
κάθε γραμμή ``{"ids": [...], "how": str, <key>: value}``. Χωρίς Qt: τα ίδια δεδομένα για την καρτέλα, το PDF, το Excel.

«Έλεγχος πληρότητας» (εργολάβος, κριτική v5): ό,τι λείπει για να είναι η λίστα σωστή γράφεται πάνω από αυτήν — π.χ.
«3 χώροι χωρίς χρήση», «32 τοίχοι χωρίς τύπο» — αντί να βγαίνει λάθος ποσότητα σιωπηλά.
"""
from __future__ import annotations

import math
import re

from archforge.core.storey_names import level_name

OPENING_PREFIX = {"window": "Π", "door": "Θ", "opening": "Α"}       # Παράθυρο · Θύρα · Άνοιγμα


def _r(v, d=2):
    return None if v is None else round(float(v), d)


def _storey(doc, z):
    from archforge.core.cameras import storey_name
    name = storey_name(doc, float(z))
    return level_name(name) if name else f"{float(z):+.2f}".replace(".", ",")


def _wall_len(p):
    return math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))


def _wall_type_label(doc, key):
    from archforge.architecture.wall_types import label
    try:
        return label(key, doc)
    except Exception:                               # noqa: BLE001 — a label never breaks a list
        return str(key)


# ------------------------------------------------------------------ Κουφώματα (door / window schedule)

def openings(doc):
    """Πίνακας κουφωμάτων: κωδικός (Π1, Θ1… or the user's own), είδος, όροφος, χώρος, πλάτος × ύψος, ποδιά, m²."""
    from archforge.assistant.understanding import read_drawing
    room_of = {}
    try:
        for storey in read_drawing(doc)["storeys"]:
            for r in storey["rooms"]:
                for oid in r["windows"] + r["doors"]:
                    room_of.setdefault(oid, []).append(r["name"])
    except Exception:                               # noqa: BLE001 — rooms only add a column
        pass
    items = []
    for e in doc.entities.values():
        if e.kind not in OPENING_PREFIX or not e.visible:
            continue
        host = doc.entities.get(e.parent_id) if e.parent_id else None
        z = float(host.params.get("z", 0.0)) if host is not None and host.kind == "wall" else float(e.params.get("z", 0.0))
        items.append((z, e.kind, str(e.params.get("mark", "")), e))
    # Automatic marks per kind, by storey then the stored order: a mark the user typed is never renumbered.
    items.sort(key=lambda t: (t[0], list(OPENING_PREFIX).index(t[1])))
    taken = {m for _z, _k, m, _e in items if m}
    counters = {k: 0 for k in OPENING_PREFIX}
    rows, no_mark, no_room = [], 0, 0
    for z, kind, mark, e in items:
        p = e.params
        if not mark:
            no_mark += 1
            while True:
                counters[kind] += 1
                mark = f"{OPENING_PREFIX[kind]}{counters[kind]}"
                if mark not in taken:
                    break
            auto = True
        else:
            auto = False
        w, h = float(p.get("width", 0.0)), float(p.get("height", 0.0))
        sill = float(p.get("sill", 0.0)) if kind == "window" else 0.0
        rooms = room_of.get(e.id, [])
        if not rooms:
            no_room += 1
        from archforge.ui.project_outline import KIND_LABELS
        rows.append({"ids": [e.id], "mark": mark, "auto_mark": auto, "kind": KIND_LABELS.get(kind, kind),
                     "storey": _storey(doc, z), "rooms": " / ".join(rooms) or "—",
                     "width": _r(w), "height": _r(h), "sill": _r(sill) if kind == "window" else None,
                     "area": _r(w * h), "type": str(p.get("opening_type", "") or ""),
                     "uw": _r(p.get("u_value"), 2) if kind != "opening" else None,
                     **_opening_thermal_cells(doc, e),
                     "how": f"πλάτος {w:.2f} × ύψος {h:.2f} = {w * h:.2f} m² (διαστάσεις ανοίγματος)".replace(".", ",")
                     + (" · κωδικός αυτόματος — γράψτε δικό σας για να μείνει" if auto else "")})
    check = []
    if no_mark:
        check.append(f"{no_mark} κουφώματα με αυτόματο κωδικό (αλλάζει αν μπει νέο πριν από αυτά — γράψτε δικό σας)")
    if no_room:
        check.append(f"{no_room} κουφώματα χωρίς χώρο (ο τοίχος δεν κλείνει χώρο)")
    total = sum(r["area"] for r in rows)
    no_u = sum(1 for r in rows if r["uw"] is None and not r["kind"].startswith("Άνοιγμα"))
    if no_u:
        check.append(f"{no_u} κουφώματα χωρίς Uw (από τον κατασκευαστή· γράψτε το στη στήλη «Uw»)")
    for r in rows:
        for note in r.get("range_notes") or ():
            check.append(f"{r['mark']}: {note}")
    no_maker = sum(1 for r in rows if r.get("uw_from", "").startswith("του κουφώματος") and not r.get("maker"))
    if no_maker:
        check.append(f"{no_maker} κουφώματα με θερμικά στοιχεία χωρίς πηγή (γράψτε κατασκευαστή / σειρά / έγγραφο)")
    return {"title": "Κουφώματα", "rows": rows, "check": check,
            "editable": {"mark": "text", "uw": "number", "uf": "number", "ug": "number", "psi_g": "number",
                         "frame_width": "number", "g_value": "number", "maker": "text",
                         "frame_material": ("choice", _choices("frame_material")),
                         "glazing": ("choice", _choices("glazing"))},
            "columns": [("mark", "Κωδικός"), ("kind", "Είδος"), ("storey", "Όροφος"), ("rooms", "Χώρος"),
                        ("width", "Πλάτος m"), ("height", "Ύψος m"), ("sill", "Ποδιά m"), ("area", "m²"),
                        ("frame_material", "Υλικό πλαισίου"), ("glazing", "Υαλοπίνακας"),
                        ("uw", "Uw δηλωμένο W/m²K"), ("uf", "Uf W/m²K"), ("ug", "Ug W/m²K"), ("psi_g", "ψg W/mK"),
                        ("frame_width", "Πλαίσιο cm"), ("g_value", "g"), ("uw_used", "Uw που ισχύει"),
                        ("uw_from", "Uw από"), ("maker", "Κατασκευαστής / έγγραφο"), ("how", "Πώς μετρήθηκε")],
            "total": f"{len(rows)} κουφώματα · {total:.2f} m²".replace(".", ",")}


def _choices(key):
    from archforge.mep.opening_thermal import CHOICES
    return [(k, v[0]) for k, v in CHOICES[key][1].items()]


def _opening_thermal_cells(doc, e):
    """The thermal data of a door / window from its maker (``mep.opening_thermal``) and the Uw that applies."""
    if e.kind not in ("door", "window"):
        return {}
    from archforge.mep import opening_thermal as FT
    p = e.params
    used, source = FT.uw(doc, e)
    fw = p.get("frame_width")
    return {"uf": _r(p.get("uf"), 2), "ug": _r(p.get("ug"), 2), "psi_g": _r(p.get("psi_g"), 3),
            "frame_width": None if fw in (None, "") else _r(float(fw) * 100, 1), "g_value": _r(p.get("g_value"), 2),
            "uw_used": _r(used, 2), "uw_from": source or "δεν δόθηκε", "maker": p.get("maker") or None,
            "frame_material": FT.FRAME_TYPES[p["frame_material"]][0] if p.get("frame_material") in FT.FRAME_TYPES else None,
            "glazing": FT.GLAZING_TYPES[p["glazing"]][0] if p.get("glazing") in FT.GLAZING_TYPES else None,
            "range_notes": FT.range_notes(p)}


def set_u_command(doc, eid, text):
    """Uw of one door / window from its maker (empty = the project's value) — one undo."""
    from archforge.core.commands import UpdateEntity
    text = str(text or "").strip().replace(",", ".")
    if text in ("", "—"):
        return UpdateEntity(eid, {"u_value": None})
    value = float(text)
    if value <= 0 or value > 10:
        raise ValueError(f"Uw {text} W/m²K — ελέγξτε την τιμή του κατασκευαστή")
    return UpdateEntity(eid, {"u_value": value})


def set_mark_command(doc, eid, mark):
    """The user's own code of an opening (empty = automatic again) — one undo."""
    from archforge.core.commands import UpdateEntity
    mark = str(mark or "").strip()
    if mark and any(e.id != eid and str(e.params.get("mark", "")) == mark for e in doc.entities.values()
                    if e.kind in OPENING_PREFIX):
        raise ValueError(f"ο κωδικός {mark} υπάρχει ήδη")
    return UpdateEntity(eid, {"mark": mark})


# ------------------------------------------------------------------ Κέλυφος (A, U, U·A, Ψ·l)

def envelope(doc):
    """Δομικά στοιχεία κελύφους (ενεργειακός, κριτική v5): ανά εξωτερικό τοίχο A καθαρό, U, U·A· θερμογέφυρες Ψ·l."""
    from archforge.architecture.wall_types import indicative_u
    from archforge.mep.thermal_bridges import summary as bridges
    from archforge.mep.ventilation import exterior_walls
    from archforge.mep.heat_load import assumptions
    project_u = assumptions(doc)["heat_u_openings"]
    rows, no_u, h_walls = [], 0, 0.0
    opening_rows, no_u_openings, h_openings = [], 0, 0.0
    storeys = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values()
                      if e.kind == "wall" and e.visible})
    for z in storeys:
        try:
            outer = exterior_walls(doc, z)
        except Exception:                           # noqa: BLE001
            continue
        for w, _n in outer:
            p = w.params
            L, H = _wall_len(p), float(p["height"])
            holes = [o for o in doc.entities.values() if o.kind in OPENING_PREFIX and o.parent_id == w.id]
            minus = sum(float(o.params.get("width", 0)) * float(o.params.get("height", 0)) for o in holes)
            area = max(0.0, L * H - minus)
            u = indicative_u(p.get("wall_type", "generic"), doc)
            if u is None:
                no_u += 1
            else:
                h_walls += u * area
            how = (f"{L:.2f} × {H:.2f} − {len(holes)} ανοίγματα {minus:.2f} = {area:.2f} m²"
                   + (f" · U από τις στρώσεις (EN ISO 6946)" if u is not None else " · χωρίς σύνθεση: χωρίς U"))
            for o in holes:
                if o.kind == "opening":
                    continue
                ao = float(o.params.get("width", 0)) * float(o.params.get("height", 0))
                from archforge.mep.opening_thermal import uw as _uw
                uo, uo_from = _uw(doc, o)
                if uo is None:
                    no_u_openings += 1
                else:
                    h_openings += float(uo) * ao
                opening_rows.append({"ids": [o.id], "element": "Κούφωμα", "storey": _storey(doc, z),
                                     "type": str(o.params.get("mark", "")) or ("Πόρτα" if o.kind == "door" else "Παράθυρο"),
                                     "quantity": _r(ao), "unit": "m²", "u": _r(uo, 2),
                                     "loss": _r(None if uo is None else float(uo) * ao, 2),
                                     "how": (f"{float(o.params.get('width', 0)):.2f} × {float(o.params.get('height', 0)):.2f} · Uw "
                                             + (uo_from or "δεν δόθηκε")).replace(".", ",")})
            rows.append({"ids": [w.id], "element": "Εξωτερικός τοίχος", "storey": _storey(doc, z),
                         "type": _wall_type_label(doc, p.get("wall_type", "generic")),
                         "quantity": _r(area), "unit": "m²", "u": _r(u, 3), "loss": _r(None if u is None else u * area, 2),
                         "how": how.replace(".", ",")})
    rows += opening_rows
    tb = bridges(doc)
    for r in tb["rows"]:
        rows.append({"ids": r["ids"], "element": "Θερμογέφυρα", "storey": "", "type": r["label"],
                     "quantity": r["length_m"], "unit": "m", "u": r["psi"], "loss": r["psi_l"],
                     "how": (f"{r['count']} θέσεις από τη γεωμετρία · ψ " + (f"{r['psi']:g} ({r['source'] or 'χωρίς πηγή'})"
                             if r["psi"] is not None else "δεν δόθηκε")).replace(".", ",")})
    check = []
    if no_u:
        check.append(f"{no_u} εξωτερικοί τοίχοι χωρίς σύνθεση — χωρίς U (δώστε τύπο τοίχου)")
    if tb["missing_n"]:
        check.append(f"θερμογέφυρες: {tb['missing_n']} θέσεις, {tb['missing_m']:.1f} m χωρίς ψ (Θέρμανση › Θερμογέφυρες…)"
                     .replace(".", ","))
    if no_u_openings:
        check.append(f"{no_u_openings} κουφώματα χωρίς Uw (Λίστες › Κουφώματα, στήλη «Uw»)")
    # Μέγιστο U της ζώνης (ΤΟΤΕΕ 20701-2 Πίν. 6): every wall / opening against its limit, the zone said.
    from archforge.mep.design_climate import zone as project_zone
    from archforge.mep.totee_20701_2 import TABLE_6_SOURCE, u_max
    z = project_zone(doc)
    over = 0
    for r in rows:
        element = {"Εξωτερικός τοίχος": "wall_exterior", "Κούφωμα": "opening"}.get(r["element"])
        limit = u_max(element, z) if element else None
        r["umax"] = limit
        if limit is not None and r["u"] is not None and r["u"] > limit + 1e-9:
            r["ok"] = f"⚠ > {limit:g}".replace(".", ",")
            over += 1
        else:
            r["ok"] = "ναι" if limit is not None and r["u"] is not None else ""
    if z is None:
        check.append("χωρίς κλιματική ζώνη: τα όρια U δεν ελέγχονται (Θέρμανση › Θερμοκρασίες σχεδιασμού…)")
    elif over:
        check.append(f"{over} στοιχεία πάνω από το μέγιστο U της ζώνης {z} ({TABLE_6_SOURCE})")
    check.append("δεν μετρώνται ακόμη: οροφή/στέγη, δάπεδο/έδαφος")
    h_t = h_walls + h_openings + tb["h_tb"]
    return {"title": "Κέλυφος", "rows": rows, "check": check, "editable": {}, "zone": z,
            "columns": [("element", "Στοιχείο"), ("storey", "Όροφος"), ("type", "Τύπος / είδος"),
                        ("quantity", "Ποσότητα"), ("unit", "Μον."), ("u", "U / ψ"), ("loss", "U·A / Ψ·l W/K"),
                        ("umax", f"Umax ζώνης {z or '—'}"), ("ok", "Εντός ορίου"), ("how", "Πώς μετρήθηκε")],
            "total": (f"H_T (μετρημένα) = {h_t:.1f} W/K: τοίχοι {h_walls:.1f} + κουφώματα {h_openings:.1f} + "
                      f"θερμογέφυρες {tb['h_tb']:.1f}").replace(".", ",")}


# ------------------------------------------------------------------ Χώροι

def rooms(doc):
    """Χώροι με όνομα και χρήση (χωρίς χρήση τα πλακάκια τοίχου βγαίνουν 0): δάπεδο, περίμετρος, ύψος, τοίχοι."""
    from archforge.assistant.understanding import read_drawing
    from archforge.quantities.takeoff import take_off
    measured = {}
    try:
        for r in take_off(doc)["rooms"]:
            measured[(r["storey"], r["name"])] = r
    except Exception:                               # noqa: BLE001
        pass
    from archforge.assistant.understanding import USE_LABELS
    rows, no_use, unnamed = [], 0, 0
    for storey in read_drawing(doc)["storeys"]:
        human = level_name(storey["name"])
        for r in storey["rooms"]:
            m = measured.get((human, r["name"]), {})
            meta = doc.room_metadata(r["signature"]) or {}
            if not r["use"]:
                no_use += 1
            if not meta.get("name"):
                unnamed += 1
            floor_ids = [e.id for e in doc.entities.values() if e.kind == "room_floor"
                         and str(e.params.get("room_signature")) == str(r["signature"])]
            rows.append({"ids": floor_ids + r["doors"] + r["windows"], "signature": r["signature"],
                         "storey": human, "name": r["name"],
                         "use": USE_LABELS.get(r["use"], "—") if r["use"] else "—",
                         "floor": m.get("floor_m2"), "perimeter": m.get("perimeter_m"), "height": m.get("height_m"),
                         "walls": m.get("walls_m2"), "wall_tiles": m.get("wall_tiles_m2"),
                         "how": ("καθαρό: άξονες τοίχων μείον μισό πάχος · ύψος = χαμηλότερος τοίχος · τοίχοι μείον "
                                 "ανοίγματα" + ("" if r["use"] else " · χωρίς χρήση: δεν μπαίνουν πλακάκια τοίχου")
                                 + (f" · χρήση από {r['use_source']}" if r["use"] and r.get("use_source") else ""))})
    check = []
    if no_use:
        check.append(f"{no_use} χώροι χωρίς χρήση — γράψτε όνομα (π.χ. «Μπάνιο») στη στήλη «Χώρος»")
    if unnamed:
        check.append(f"{unnamed} χώροι με αυτόματο όνομα («Χώρος N»)")
    walls = [e for e in doc.entities.values() if e.kind == "wall" and e.visible]
    generic = sum(1 for e in walls if str(e.params.get("wall_type", "generic")) == "generic")
    if generic:
        check.append(f"{generic} από {len(walls)} τοίχους χωρίς τύπο (Γενικός)")
    total = sum(r["floor"] or 0.0 for r in rows)
    return {"title": "Χώροι", "rows": rows, "check": check, "editable": {"name": "room"},
            "columns": [("storey", "Όροφος"), ("name", "Χώρος"), ("use", "Χρήση"), ("floor", "Δάπεδο m²"),
                        ("perimeter", "Περίμετρος m"), ("height", "Ύψος m"), ("walls", "Τοίχοι m²"),
                        ("wall_tiles", "Πλακάκια τοίχου m²"), ("how", "Πώς μετρήθηκε")],
            "total": f"{len(rows)} χώροι · {total:.2f} m² δάπεδο".replace(".", ",")}


def rename_room_command(doc, signature, name):
    """Name (and the use read from it: «Μπάνιο 2» → μπάνιο) of a room — one undo, as the plan's «Χρήση χώρου»."""
    from archforge.core.commands import SetRoomMetadata
    name = str(name or "").strip()
    if not name:
        raise ValueError("δώστε όνομα χώρου")
    return SetRoomMetadata(signature, {"name": name, "use": re.sub(r"\s*\d+$", "", name)})


# ------------------------------------------------------------------ Κυκλώματα

def circuits(doc):
    """Κυκλώματα (Η/Μ): αριθμός, είδος, ασφάλεια, καλώδιο, σημεία, φορτίο — κλικ = τα σημεία του στο σχέδιο."""
    from archforge.mep.electrical import design_circuits
    d = design_circuits(doc)
    rows = [{"ids": list(c["points"]), "id": c["id"], "label": c["label"], "breaker": c["breaker_a"],
             "cable": c["cable_mm2"], "count": len(c["points"]), "load": c["load_w"], "current": c["current_a"],
             "ok": "ναι" if c["ok"] else "⚠ όχι",
             "how": f"Σ ισχύος σημείων {c['load_w']} W / 230 V = {c['current_a']} A".replace(".", ",")}
            for c in d["circuits"]]
    check = list(d["report"]["warnings"])
    if rows and not d["report"].get("numbers_kept"):
        check.insert(0, "η αρίθμηση δεν είναι κρατημένη: νέο σημείο μπορεί να αλλάξει αριθμούς "
                        "(Ηλεκτρολογικά › Κράτα την αρίθμηση κυκλωμάτων)")
    return {"title": "Κυκλώματα", "rows": rows, "check": check, "editable": {},
            "columns": [("id", "Κύκλωμα"), ("label", "Είδος"), ("breaker", "Ασφάλεια A"), ("cable", "Καλώδιο mm²"),
                        ("count", "Σημεία"), ("load", "Φορτίο W"), ("current", "Ρεύμα A"), ("ok", "Εντός ορίου"),
                        ("how", "Πώς μετρήθηκε")],
            "total": f"{len(rows)} κυκλώματα · {sum(r['load'] for r in rows)} W"}


LISTS = {"openings": openings, "envelope": envelope, "rooms": rooms, "circuits": circuits}


# ------------------------------------------------------------------ export: PDF (HTML) and Excel, the same lists

def table(data):
    """``(header, rows)`` of a list as plain values (None stays empty) — the same columns the tab shows."""
    keys = [k for k, _l in data["columns"]]
    return [label for _k, label in data["columns"]], [[row.get(k) for k in keys] for row in data["rows"]]


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",")
    return str(v)


def html(doc, keys=None, project=""):
    """One HTML document with the chosen lists (all by default): title, completeness check, table, total."""
    from html import escape
    import datetime
    parts = [f"<h2>Λίστες{(' — ' + escape(project)) if project else ''}</h2>"
             f"<p><small>{datetime.date.today():%d/%m/%Y} · από το σχέδιο, προς έλεγχο πριν από χρήση</small></p>"]
    for key in (keys or LISTS):
        d = LISTS[key](doc)
        header, rows = table(d)
        parts.append(f"<h3>{escape(d['title'])}</h3>")
        if d["check"]:
            parts.append("<p style='color:#b45309'>" + "<br>".join(escape(c) for c in d["check"]) + "</p>")
        parts.append("<table border=1 cellspacing=0 cellpadding=3 width=100%><tr>"
                     + "".join(f"<th>{escape(h)}</th>" for h in header) + "</tr>"
                     + "".join("<tr>" + "".join(f"<td>{escape(_fmt(v))}</td>" for v in row) + "</tr>" for row in rows)
                     + "</table>")
        if d.get("total"):
            parts.append(f"<p><b>{escape(d['total'])}</b></p>")
    return "".join(parts)


def write_xlsx(doc, path, keys=None):
    """The chosen lists (all by default) to .xlsx, one sheet each, with the check and the total under the title."""
    from archforge.quantities.xlsx import write_table_workbook
    sheets = []
    for key in (keys or LISTS):
        d = LISTS[key](doc)
        header, rows = table(d)
        notes = list(d["check"]) + ([d["total"]] if d.get("total") else [])
        sheets.append((d["title"], d["title"], header, rows, notes))
    return write_table_workbook(path, sheets)
