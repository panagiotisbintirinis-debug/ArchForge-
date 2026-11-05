"""Θερμικά στοιχεία κουφώματος — ένα σημείο για τη λίστα, τη θερμική εικόνα, την όψη 3D, τις απώλειες και το κέλυφος.

Ιδιοκτήτης 05/11: «να συνδέεται με τη λίστα των κουφωμάτων· αλλάζει το κούφωμα, αλλάζει και η θερμική απεικόνιση…
κάθε κούφωμα πρέπει να έχει εκτός από τομές και διαστάσεις και θερμικά στοιχεία — θα πάρω στοιχεία από τις εταιρείες»
· «πιο αναλυτικούς πίνακες… και ένα solver σχεδιασμού».

Το Uw ενός κουφώματος, με τη σειρά της ΤΟΤΕΕ 20701-2/2021 §2.2 (`totee_20701_2_2021`):

1. ``u_value``: η πιστοποιημένη τιμή του κατασκευαστή.
2. Σχέση 2.10 (2.17 με κουτί ρολού): Uw = (Uf·Af + Ug·Ag + Ψg·lg [+ Usb·Asb]) / (Af + Ag), με
   Ag = (b − 2·bf)(h' − 2·bf), lg = 2·((b − 2·bf) + (h' − 2·bf)), h' = ύψος χωρίς το κουτί του ρολού.
   Κάθε μέγεθος από τον κατασκευαστή (``uf``, ``ug``, ``psi_g``, ``usb``) ή, όπου λείπει, η ενδεικτική τιμή της ΤΟΤΕΕ για
   ό,τι διάλεξε ο χρήστης (Πίν. 10 υλικό πλαισίου, Πίν. 9 υαλοπίνακας, Πίν. 11α/β αποστάτης, Πίν. 12 κουτί ρολού). Το
   ``frame_width`` (ορατό πλάτος πλαισίου) δίνεται πάντα από τον χρήστη: η ΤΟΤΕΕ δεν το ορίζει. Πλαίσιο με εύρος στον
   Πίν. 10 (μεταλλικό με θερμοδιακοπή 1,0–4,0, PVC πολυθαλαμικό 1,0–2,0) χρειάζεται το Uf του κατασκευαστή.
3. Το Uw κουφωμάτων του έργου, αλλιώς «δεν υπολογίστηκε».

Ρολό / εξώφυλλο κλειστό (σχέσεις 2.18–2.19, Πίν. 13): Uw,rb και Uw,διορθ για τη μελέτη ενεργειακής απόδοσης· ο έλεγχος
επάρκειας γίνεται με το Uw χωρίς αυτά (§2.2.5, Διευκρινίσεις).
"""
from __future__ import annotations

import math

from archforge.mep import totee_20701_2_2021 as T

# key: (label, unit, lo, hi) — the ranges only catch typing errors, they are not product limits.
NUMBERS = {
    "u_value": ("Uw δηλωμένο", "W/m²K", 0.3, 7.0),
    "uf": ("Uf πλαισίου", "W/m²K", 0.3, 8.0),
    "ug": ("Ug υαλοπίνακα", "W/m²K", 0.2, 6.0),
    "psi_g": ("ψg αποστάτη", "W/mK", 0.0, 0.3),
    "frame_width": ("πλάτος πλαισίου", "m", 0.02, 0.3),
    "g_value": ("g υαλοπίνακα", "", 0.05, 0.95),
    "usb": ("Usb κουτιού ρολού", "W/m²K", 0.3, 8.0),
    # Απαίτηση της μελέτης / του προγράμματος (π.χ. «Εξοικονομώ», τεύχος): ο χρήστης τη γράφει, το πρόγραμμα ελέγχει.
    "uw_required": ("Uw απαίτηση ≤", "W/m²K", 0.3, 7.0),
}
SAFETY_GLASS = {"none": "Όχι", "laminated": "Laminated (πολύστρωμο)", "tempered": "Tempered (σκληρυμένο)"}
TEXTS = {"maker": "Κατασκευαστής / σειρά / έγγραφο",
         "glazing_build": "Σύνθεση υάλωσης (π.χ. 4 Clear + 16 Ar + 4 Low-E)"}

FRAME_TYPES = {k: v[1] + (f" (Uf {v[2]:g})" if not isinstance(v[2], tuple) else
                          f" (Uf {v[2][0]:g}–{v[2][1]:g}: του κατασκευαστή)")
               for k, v in T.TABLE_10.items()}
FRAME_TYPES = {k: v.replace(".", ",") for k, v in FRAME_TYPES.items()}
GLAZING_TYPES = dict(T.glazing_choices())
ROLLER_BOXES = {k: (f"{v[0]} (Usb {v[1]:g})" if not isinstance(v[1], tuple) else
                    f"{v[0]} (Usb {v[1][0]:g}–{v[1][1]:g}: του κατασκευαστή)").replace(".", ",")
                for k, v in T.TABLE_12.items()}
SHUTTER_SLATS = {k: v[0] for k, v in T.TABLE_13.items()}
AIRTIGHTNESS = {"low": "Χαμηλή", "medium": "Μέση", "high": "Υψηλή"}
# key: (label, {choice key: label})
CHOICES = {"frame_material": ("Υλικό πλαισίου (ΤΟΤΕΕ Πίν. 10)", FRAME_TYPES),
           "glazing": ("Υαλοπίνακας (ΤΟΤΕΕ Πίν. 9)", GLAZING_TYPES),
           "spacer": ("Αποστάτης (ΤΟΤΕΕ Πίν. 11)", T.SPACERS),
           "roller_box": ("Κουτί ρολού (ΤΟΤΕΕ Πίν. 12)", ROLLER_BOXES),
           "shutter_slats": ("Περσίδα ρολού / εξώφυλλου (ΤΟΤΕΕ Πίν. 13)", SHUTTER_SLATS),
           "shutter_airtightness": ("Αεροστεγανότητα ρολού / εξώφυλλου", AIRTIGHTNESS),
           "safety_glass": ("Γυαλί ασφαλείας", SAFETY_GLASS)}

SOURCE_DECLARED = "του κουφώματος, δηλωμένο από τον κατασκευαστή"
SOURCE_10077 = "του κουφώματος, EN ISO 10077-1 από Uf, Ug, ψg, πλαίσιο"
SOURCE_TABLES = "του κουφώματος, ΤΟΤΕΕ 20701-2/2021 σχ. 2.10"
SOURCE_PROJECT = "του έργου"


def uw_10077(width, height, frame_width, uf, ug, psi_g, usb=0.0, box=0.0):
    """Uw of one door / window (σχέση 2.10, or 2.17 with a roller box of height ``box`` m inside the opening)."""
    w, h, bf = float(width), float(height) - float(box), float(frame_width)
    gw, gh = w - 2 * bf, h - 2 * bf
    if gw <= 0 or gh <= 0:
        raise ValueError(f"πλαίσιο {bf * 100:.1f} cm: δεν μένει τζάμι σε {w:.2f} × {h:.2f} m")
    ag = gw * gh
    return T.uw(w * h - ag, ag, 2 * (gw + gh), float(uf), float(ug), float(psi_g), float(usb), w * float(box))


def has_parts(params):
    return all(params.get(k) not in (None, "") for k in ("uf", "ug", "psi_g", "frame_width"))


def _box(opening):
    """``(Usb, box height m, from table)`` when the opening has a roller with a known box, else ``(0, 0, False)``."""
    from archforge.architecture import joinery as J
    p = opening.params
    if J.resolved(opening.kind, p)["shading"] != "roller":
        return 0.0, 0.0, False
    if p.get("usb"):
        return float(p["usb"]), J.ROLLER_BOX, False
    row = T.TABLE_12.get(p.get("roller_box"))
    if row and not isinstance(row[1], tuple):
        return float(row[1]), J.ROLLER_BOX, True
    return 0.0, 0.0, False


def components(opening):
    """``{"uf", "ug", "psi_g", "frame_width", "usb", "box", "from_tables": [...], "missing": [...]}`` — each value from
    the maker or, where missing, the ΤΟΤΕΕ table for what the user chose; ``missing`` names what neither gives."""
    p = opening.params
    out = {"from_tables": [], "missing": []}
    frame = T.TABLE_10.get(p.get("frame_material"))
    glz = T.glazing(p.get("glazing"))
    if p.get("uf"):
        out["uf"] = float(p["uf"])
    elif frame and not isinstance(frame[2], tuple):
        out["uf"] = frame[2]; out["from_tables"].append("Uf Πίν. 10")
    else:
        out["missing"].append("Uf" + (" (ο Πίν. 10 δίνει εύρος)" if frame else ""))
    if p.get("ug"):
        out["ug"] = float(p["ug"])
    elif glz:
        out["ug"] = glz[2]; out["from_tables"].append("Ug Πίν. 9")
    else:
        out["missing"].append("Ug")
    if p.get("psi_g") not in (None, ""):
        out["psi_g"] = float(p["psi_g"])
    elif frame and glz:
        spacer = p.get("spacer") or "standard"
        out["psi_g"] = T.psi_g(p["frame_material"], glz[0], spacer)
        out["from_tables"].append("Ψg Πίν. " + ("11β" if spacer == "warm" else "11α"))
    else:
        out["missing"].append("Ψg")
    if p.get("frame_width"):
        out["frame_width"] = float(p["frame_width"])
    else:
        out["missing"].append("πλάτος πλαισίου")
    usb, box, table = _box(opening)
    out["usb"], out["box"] = usb, box
    if table:
        out["from_tables"].append("Usb Πίν. 12")
    return out


def uw(doc, opening):
    """``(Uw, source)`` of a door / window, or ``(None, None)`` — the one answer of the list, the image and the loads."""
    p = opening.params
    if p.get("u_value"):
        return float(p["u_value"]), SOURCE_DECLARED
    c = components(opening)
    if not c["missing"]:
        try:
            value = uw_10077(p.get("width", 1.0), p.get("height", 1.0), c["frame_width"], c["uf"], c["ug"], c["psi_g"],
                             c["usb"], c["box"])
        except ValueError:
            value = None
        if value is not None:
            if not c["from_tables"] and not c["box"]:
                return value, SOURCE_10077
            return value, SOURCE_TABLES + (f" · ενδεικτικά: {', '.join(c['from_tables'])}" if c["from_tables"] else
                                           " από Uf, Ug, ψg, Usb του κατασκευαστή")
    from archforge.mep.heat_load import assumptions
    project = assumptions(doc)["heat_u_openings"]
    return (float(project), SOURCE_PROJECT) if project else (None, None)


def uw_with_shutters(doc, opening):
    """``(Uw,rb, Uw,διορθ)`` (σχέσεις 2.18–2.19, Πίν. 13) for an opening with a roller / shutters and known slats and
    air tightness, else None. Για τη μελέτη ενεργειακής απόδοσης — όχι για τον έλεγχο επάρκειας."""
    from archforge.architecture import joinery as J
    p = opening.params
    if J.resolved(opening.kind, p)["shading"] == "none":
        return None
    row = T.TABLE_13.get(p.get("shutter_slats"))
    tight = p.get("shutter_airtightness")
    used, _src = uw(doc, opening)
    if row is None or tight not in T.AIRTIGHTNESS or used is None:
        return None
    rrb = row[1][T.AIRTIGHTNESS.index(tight)]
    return T.with_shutter(used, rrb), T.corrected(used, rrb)


def requirement_notes(doc, opening):
    """«Uw 2,10 > απαίτηση 1,80» and «Uw 3,20 > Umax 2,60 ζώνης Β, ΤΟΤΕΕ 20701-2/2021 Πίν. 5α» for one door / window."""
    used, _src = uw(doc, opening)
    if used is None:
        return []
    out = []
    req = opening.params.get("uw_required")
    if req and used > float(req) + 1e-9:
        out.append(f"Uw {used:.2f} > απαίτηση {float(req):.2f}".replace(".", ","))
    limit, source = T.u_max_project(doc, "opening")
    if limit is not None and used > limit + 1e-9:
        out.append(f"Uw {used:.2f} > Umax {limit:.2f}".replace(".", ",") + f" {source}")
    return out


def range_notes(params):
    """Uf with a frame whose Πίν. 10 value is a range: «Uf 4,5 έξω από 1–4 του Πίν. 10 για …» or «χρειάζεται το Uf»."""
    row = T.TABLE_10.get(params.get("frame_material"))
    if not row or not isinstance(row[2], tuple):
        return []
    lo, hi = row[2]
    num = lambda x: f"{x:g}".replace(".", ",")
    if params.get("uf") in (None, ""):
        return [f"«{row[1]}»: ο Πίν. 10 δίνει Uf {num(lo)}–{num(hi)} — γράψτε το Uf του κατασκευαστή"]
    v = float(params["uf"])
    if not lo <= v <= hi:
        return [f"Uf {num(v)} έξω από το {num(lo)}–{num(hi)} του Πίν. 10 για «{row[1]}» — ελέγξτε το φύλλο του "
                "κατασκευαστή"]
    return []


def parse(key, text):
    """A typed value (comma or dot; empty = remove) checked against ``NUMBERS``; ``frame_width`` is typed in cm."""
    if key in TEXTS:
        return str(text or "").strip() or None
    if key in CHOICES:
        t = str(text or "").strip()
        if t in ("", "—"):
            return None
        for k, label in CHOICES[key][1].items():
            if t == k or t.casefold() == label.casefold():
                return k
        raise ValueError(f"{CHOICES[key][0]} «{t}»: διαλέξτε από τη λίστα")
    if key not in NUMBERS:
        raise KeyError(key)
    t = str(text or "").strip().replace(",", ".")
    if t in ("", "—"):
        return None
    v = float(t)
    if key == "frame_width":
        v /= 100.0
    label, unit, lo, hi = NUMBERS[key]
    if not math.isfinite(v) or not lo <= v <= hi:
        shown = f"{v * 100:g} cm" if key == "frame_width" else f"{t} {unit}".strip()
        raise ValueError(f"{label} {shown}: έξω από τα λογικά όρια — ελέγξτε το φύλλο του κατασκευαστή")
    return v


def set_command(doc, eid, key, text):
    """One undoable change of one thermal datum of a door / window."""
    from archforge.core.commands import UpdateEntity
    e = doc.get(eid)
    if e is None or e.kind not in ("door", "window"):
        raise ValueError("θερμικά στοιχεία έχουν μόνο πόρτες και παράθυρα")
    value = parse(key, text)
    if key == "frame_width" and value is not None:
        uw_10077(e.params.get("width", 1.0), e.params.get("height", 1.0), value, 1.0, 1.0, 0.0)   # glass must remain
    return UpdateEntity(eid, {key: value})


# ------------------------------------------------------------------ solver σχεδιασμού

def design(width, height, frame_width, target, frames=None, gases=("air", "argon", "krypton"), spacers=("standard", "warm"),
           box=0.0, usb=0.0):
    """Every combination of ΤΟΤΕΕ Πίν. 10 frame × Πίν. 9 glazing × Πίν. 11 spacer for a ``width`` × ``height`` opening
    with a ``frame_width`` frame: ``[{"frame", "glazing", "spacer", "uw", "ok", "uf_needed"}]``.

    Frames whose Πίν. 10 value is a range get ``uw`` = None and ``uf_needed`` = the largest Uf that still meets
    ``target`` (to ask the maker for). Sorted: those that meet the target first, closest to it (the simplest that
    passes) first; then the rest by Uw."""
    from archforge.mep.totee_20701_2_2021 import TABLE_9, TABLE_10, psi_g as table_psi
    w, h, bf = float(width), float(height) - float(box), float(frame_width)
    gw, gh = w - 2 * bf, h - 2 * bf
    if gw <= 0 or gh <= 0:
        raise ValueError(f"πλαίσιο {bf * 100:.1f} cm: δεν μένει τζάμι σε {w:.2f} × {h:.2f} m")
    ag, lg = gw * gh, 2 * (gw + gh)
    af = w * h - ag
    out = []
    for fk, (_group, _label, uf) in TABLE_10.items():
        if frames and fk not in frames:
            continue
        for row, (_d, _e, _dims, ugs) in TABLE_9.items():
            for gas in gases:
                ug = ugs[gas]
                for sp in spacers:
                    psi = table_psi(fk, row, sp)
                    rest = ug * ag + psi * lg + usb * w * box
                    item = {"frame": fk, "glazing": T.glazing_key(row, gas), "spacer": sp, "ug": ug, "psi_g": psi}
                    if isinstance(uf, tuple):
                        need = (float(target) * (af + ag) - rest) / af
                        item.update(uw=None, uf=None, uf_needed=need, ok=need >= uf[0])
                    else:
                        value = (uf * af + rest) / (af + ag)
                        item.update(uw=value, uf=uf, uf_needed=None, ok=value <= float(target) + 1e-9)
                    out.append(item)
    def order(i):
        if i["ok"] and i["uw"] is not None:
            return (0, complexity(i), -i["uw"])    # passes with a table Uf: the most usual build-up, then the margin
        if i["ok"]:
            return (1, complexity(i), -i["uf_needed"])   # range frame: usual glazing, the easiest Uf to ask for
        return (2, 0, i["uw"] if i["uw"] is not None else -i["uf_needed"])
    out.sort(key=order)
    return out


def complexity(item):
    """How unusual a build-up is (DESIGN_DEFAULT, for ordering only — not a price): triple glazing 3, krypton 3, argon 1,
    low-e coating 0,5, warm-edge spacer 0,5. «Ο απλούστερος που αρκεί» = the lowest, then the smallest margin."""
    n, coating, _dims, gas = item["glazing"].split("|")
    return ((3 if n == "3" else 0) + {"air": 0, "argon": 1, "krypton": 3}[gas] + (0 if coating == "none" else 0.5)
            + (0.5 if item["spacer"] == "warm" else 0))


def required_ug(width, height, frame_width, uf, psi, target, box=0.0, usb=0.0):
    """The largest Ug that meets ``target`` with this frame (σχέση 2.10 λυμένη ως προς Ug)."""
    w, h, bf = float(width), float(height) - float(box), float(frame_width)
    gw, gh = w - 2 * bf, h - 2 * bf
    if gw <= 0 or gh <= 0:
        raise ValueError("δεν μένει τζάμι")
    ag, lg = gw * gh, 2 * (gw + gh)
    return (float(target) * w * h - float(uf) * (w * h - ag) - float(psi) * lg - float(usb) * w * float(box)) / ag
