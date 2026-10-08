"""Κουφώματα: τύποι πόρτας και παραθύρου ως παράμετροι των οντοτήτων door/window.

Η οντότητα κρατά την πρόθεση (τύπος, φύλλα, μεντεσέδες, φορά, καΐτια,
φεγγίτης, ρολό/παντζούρια, ποδιά, υλικό). Από τις ίδιες παραμέτρους
παράγονται τα 3D κουτιά (κάσα, φύλλο, τζάμι, χερούλι, ρολό/παντζούρι,
ποδιά) και το 2D σύμβολο κάτοψης με τη φορά ανοίγματος.

Χωρίς ``opening_type`` (ή με ``basic``) το κούφωμα μένει ακριβώς όπως πριν
(rendering/fixtures.py), ώστε τα παλιά έργα να ανοίγουν ίδια.

Τοπικό πλαίσιο ανοίγματος: u κατά μήκος του τοίχου από την αρχή του
ανοίγματος (0..W), s κάθετα στον τοίχο με s > 0 προς τα **μέσα** (προς το
κτίριο· σε εσωτερικό τοίχο προς την αριστερή πλευρά της φοράς σχεδίασης),
z από το κάτω μέρος του ανοίγματος (0..H). Μέτρα.

Αριστερά/δεξιά (μεντεσέδες): όπως στην ευρωπαϊκή πρακτική (DIN), κοιτάζοντας
το κούφωμα από την πλευρά προς την οποία ανοίγει το φύλλο. Για συρόμενα,
χωνευτή και φυσαρμόνικα, κοιτάζοντας από μέσα: η πλευρά όπου μαζεύει.
"""
from __future__ import annotations

import math

# --- Τύποι (ονόματα που βλέπει ο χρήστης) ---------------------------------
WINDOW_TYPES = {
    "basic": "Απλό (βασικό)",
    "casement": "Ανοιγόμενο",
    "tilt_turn": "Ανοιγοανακλινόμενο",
    "hopper": "Ανακλινόμενο (φεγγίτης)",
    "sliding": "Συρόμενο επάλληλο",
    "fixed": "Σταθερό",
}
DOOR_TYPES = {
    "basic": "Απλή (βασική)",
    "interior_flush": "Εσωτερική πρεσαριστή",
    "interior_panel": "Εσωτερική ταμπλαδωτή",
    "security": "Εξώπορτα θωρακισμένη",
    "balcony_casement": "Μπαλκονόπορτα ανοιγόμενη",
    "balcony_sliding": "Μπαλκονόπορτα συρόμενη επάλληλη",
    "pocket": "Χωνευτή συρόμενη (μέσα στον τοίχο)",
    "folding": "Φυσαρμόνικα (πτυσσόμενη)",
}
TYPES = {"window": WINDOW_TYPES, "door": DOOR_TYPES}
HINGES = {"left": "Αριστερά", "right": "Δεξιά"}
SWINGS = {"in": "Προς τα μέσα", "out": "Προς τα έξω"}
SHADINGS = {"none": "Χωρίς", "roller": "Ρολό (κουτί πάνω)", "shutters": "Παντζούρια"}
LEDGES = {"none": "Χωρίς", "outside": "Ποδιά έξω", "inside": "Περβάζι μέσα", "both": "Ποδιά και περβάζι"}
# name, colour, roughness, metalness — όψη μόνο, όχι φυσικές ιδιότητες.
FINISHES = {
    "alu_anthracite": ("Αλουμίνιο ανθρακί", "#383e42", 0.45, 0.35),
    "alu_white": ("Αλουμίνιο λευκό", "#eeeeea", 0.40, 0.20),
    "pvc_white": ("PVC λευκό", "#f3f3ef", 0.55, 0.0),
    "wood_oak": ("Ξύλο δρυς", "#b98755", 0.60, 0.0),
    "wood_walnut": ("Ξύλο καρυδιά", "#6b4632", 0.60, 0.0),
    "lacquer_white": ("Λάκα λευκή", "#ecebe6", 0.35, 0.0),
}
ROLES = ("frame", "leaf", "glass", "handle", "shading", "sill")
ROLE_NAMES = {"frame": "Κάσα", "leaf": "Φύλλο", "glass": "Τζάμι", "handle": "Χερούλι",
              "shading": "Ρολό / παντζούρι", "sill": "Ποδιά / περβάζι"}
# Παράμετροι κουφώματος (όλες προαιρετικές· απουσία = προεπιλογή τύπου).
KEYS = ("opening_type", "hinge", "swing", "leaves", "bars_h", "bars_v", "transom", "shading", "ledge", "finish")

SWINGING = {"casement", "tilt_turn", "interior_flush", "interior_panel", "security", "balcony_casement"}
SLIDING = {"sliding", "balcony_sliding"}
GLAZED = {"casement", "tilt_turn", "hopper", "sliding", "fixed", "balcony_casement", "balcony_sliding"}
SHADEABLE = GLAZED
# (ελάχιστα, μέγιστα) φύλλα ανά τύπο.
LEAF_RANGE = {"casement": (1, 3), "tilt_turn": (1, 3), "hopper": (1, 1), "sliding": (2, 4), "fixed": (0, 0),
              "interior_flush": (1, 2), "interior_panel": (1, 2), "security": (1, 1),
              "balcony_casement": (1, 3), "balcony_sliding": (2, 4), "pocket": (1, 1), "folding": (2, 8)}

# --- Διαστάσεις προφίλ (άγκυρες) ----------------------------------------
# Αλουμίνιο/PVC με θερμοδιακοπή, συνήθη συστήματα ελληνικής αγοράς:
FRAME = 0.065          # κάσα, όψη 6–7 cm
FRAME_D = 0.07         # βάθος κάσας ανοιγόμενου 6–7 cm
SLIDE_FRAME_D = 0.10   # βάθος κάσας επάλληλου συρόμενου ~10 cm (δύο οδηγοί)
SASH = 0.09            # φύλλο, όψη 8–10 cm
SASH_S = (-0.025, 0.045)  # φύλλο ανοιγόμενου: λίγο προς τα μέσα από την κάσα
DOOR_RAIL = 0.12       # κάτω τραβέρσα φύλλου μπαλκονόπορτας ~12 cm
THRESHOLD = 0.02       # χαμηλό κατωκάσι μπαλκονόπορτας ~2 cm
TRACK = 0.022          # απόσταση οδηγού από τον άξονα της κάσας (συρόμενα)
TRACK_D = 0.036        # βάθος φύλλου συρόμενου
GLASS_D = 0.024        # διπλός υαλοπίνακας 4-16-4 = 24 mm
BAR = 0.025            # καΐτι, όψη ~2,5 cm
TRANSOM_RAIL = 0.07    # τραβέρσα κάτω από τον φεγγίτη
ROLLER_BOX = 0.18      # κουτί ρολού 16,5–20,5 cm (ύψος)
ROLLER_GUIDE = 0.035   # οδηγός ρολού ~3,5 cm
SHUTTER_D = 0.04       # παντζούρι ~4 cm πάχος
SILL_OUT = 0.03        # μαρμάρινη ποδιά 3 cm, προεξοχή 3 cm από την όψη
SILL_IN = 0.02         # εσωτερικό περβάζι 2 cm, προεξοχή 2 cm
JAMB = 0.04            # εσωτερική κάσα ξύλινη, όψη ~4 cm, πλάτος τοίχου
DOOR_LEAF = 0.04       # φύλλο πρεσαριστό/ταμπλαδωτό ~4 cm
SECURITY_FRAME = 0.06  # μεταλλική κάσα θωρακισμένης ~6 cm όψη
SECURITY_LEAF = 0.07   # θωρακισμένο φύλλο 6–7 cm
HANDLE_Z = 1.05        # χερούλι πόρτας ~1,00–1,05 m από το δάπεδο
GAP = 0.004            # αρμός γύρω από το φύλλο
FLOOR_GAP = 0.008      # κενό κάτω από εσωτερικό φύλλο ~1 cm
# Τυπικά μεγέθη (για τα έτοιμα κουφώματα): εσωτερικές 70/80/90×210,
# θωρακισμένη 90×215, μπαλκονόπορτα 140×220 (+ κουτί ρολού), παράθυρο
# 120×140 με ποδιά στα 0,90 m (συνήθης ελληνική πρακτική, προς έλεγχο).


def is_typed(params):
    return str(params.get("opening_type", "basic")) != "basic"


def validate_choice(key, value):
    """Έλεγχος μίας παραμέτρου κουφώματος (καλείται από το SCHEMAS)."""
    options = {"opening_type": set(WINDOW_TYPES) | set(DOOR_TYPES), "hinge": HINGES, "swing": SWINGS,
               "shading": SHADINGS, "ledge": LEDGES, "finish": FINISHES}
    if key in options:
        v = str(value)
        if v not in options[key]:
            raise ValueError(f"{key} must be one of {', '.join(sorted(options[key]))}")
        return v
    if key in ("leaves", "bars_h", "bars_v"):
        v = int(round(float(value)))
        if not 0 <= v <= 8:
            raise ValueError(f"{key} must be between 0 and 8")
        return v
    if key == "transom":
        v = float(value)
        if not math.isfinite(v) or v < 0:
            raise ValueError("transom must be >= 0")
        return v
    raise KeyError(key)


def auto_leaves(kind, opening_type, width):
    """Φύλλα που θα έβαζε ένας κατασκευαστής για αυτό το πλάτος."""
    t = opening_type
    if t in ("casement", "tilt_turn"):
        return 1 if width <= 0.95 else 2          # ανοιγόμενο φύλλο έως ~90 cm
    if t == "balcony_casement":
        return 1 if width <= 1.0 else 2
    if t in SLIDING:
        return 3 if width >= 2.8 else 2
    if t == "folding":
        return max(2, int(math.ceil(width / 0.6 - 1e-9)))   # ~60 cm ανά φύλλο
    if t == "fixed":
        return 0
    return 1


def resolved(kind, params):
    """Όλες οι παράμετροι κουφώματος με τις προεπιλογές του τύπου."""
    p = params
    t = str(p.get("opening_type", "basic"))
    width = float(p.get("width", 1.0))
    leaves = int(p.get("leaves", 0) or 0) or auto_leaves(kind, t, width)
    lo, hi = LEAF_RANGE.get(t, (0, 8))
    leaves = max(lo, min(hi, leaves))
    if t in ("interior_flush", "interior_panel", "folding"):
        finish = "wood_oak"
    elif t == "security":
        finish = "wood_walnut"
    elif t == "pocket":
        finish = "lacquer_white"
    else:
        finish = "alu_anthracite"
    return {
        "opening_type": t,
        "hinge": str(p.get("hinge", "left")),
        "swing": str(p.get("swing", "in")),
        "leaves": leaves,
        "bars_h": int(p.get("bars_h", 0) or 0) if t in GLAZED else 0,
        "bars_v": int(p.get("bars_v", 0) or 0) if t in GLAZED else 0,
        "transom": float(p.get("transom", 0.0) or 0.0) if t in GLAZED and t not in SLIDING else 0.0,
        "shading": str(p.get("shading", "none")) if t in SHADEABLE else "none",
        "ledge": str(p.get("ledge", "both" if kind == "window" else "none")) if kind == "window" else "none",
        "finish": str(p.get("finish", finish)),
    }


def validate_joinery(kind, params, wall_length=None):
    """Ο τύπος ανήκει στο είδος (πόρτα/παράθυρο) και χωρά στο άνοιγμα (και η θήκη της χωνευτής στον τοίχο)."""
    t = str(params.get("opening_type", "basic"))
    if t not in TYPES.get(kind, {}):
        raise ValueError(f"{kind} type must be one of {', '.join(TYPES.get(kind, {}))}")
    if t == "basic":
        return True
    leaves = int(params.get("leaves", 0) or 0)
    lo, hi = LEAF_RANGE[t]
    if leaves and not lo <= leaves <= hi:
        raise ValueError(f"{t} takes {lo}–{hi} leaves")
    r = resolved(kind, params)
    height = float(params["height"])
    usable = height - (ROLLER_BOX if r["shading"] == "roller" else 0.0)
    if r["transom"] and not 0.15 <= r["transom"] <= usable - 0.40:
        raise ValueError("transom must leave at least 40 cm for the main leaves")
    if usable < 0.30:
        raise ValueError("opening too low for its roller box")
    if r["opening_type"] == "pocket" and wall_length is not None:
        # Η θήκη χρειάζεται τοίχο ίσο με το φύλλο δίπλα στο άνοιγμα. Εδώ: τουλάχιστον από
        # μία πλευρά· η σωστή πλευρά ελέγχεται με pocket_fits (Ιδιότητες), γιατί θέλει το έργο.
        width, offset = float(params["width"]), float(params["offset"])
        if max(offset - width / 2, wall_length - offset - width / 2) < width - 2 * JAMB:
            raise ValueError("pocket door needs wall beside the opening for its pocket")
    return True


# --- Πλευρές ------------------------------------------------------------
def inside_sign(doc, wall):
    """+1 αν το «μέσα» είναι η +n πλευρά του τοίχου (n = αριστερά της φοράς σχεδίασης), αλλιώς -1.

    Εξωτερικός τοίχος (ελεύθερος χώρος από τη μία μόνο πλευρά): μέσα = προς το
    κτίριο. Εσωτερικός ή μόνος τοίχος: +n.
    """
    from archforge.mep.ventilation import _ray_hits, _walls
    p = wall.params
    x1, y1, x2, y2, t = (float(p[k]) for k in ("x1", "y1", "x2", "y2", "thickness"))
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-9:
        return 1
    nx, ny = -(y2 - y1) / L, (x2 - x1) / L
    walls = _walls(doc, float(p.get("z", 0.0)))
    free = []
    for sign in (1.0, -1.0):
        if any(not _ray_hits(walls, wall.id, x1 + (x2 - x1) * f + sign * nx * (t / 2 + 0.01),
                             y1 + (y2 - y1) * f + sign * ny * (t / 2 + 0.01), sign * nx, sign * ny)
               for f in (0.25, 0.5, 0.75)):
            free.append(sign)
    if len(free) == 1:
        return -int(free[0])
    return 1


def pocket_fits(doc, opening):
    """Χωνευτή: χωρά η θήκη στον τοίχο, στην πλευρά που μαζεύει το φύλλο;"""
    p = opening.params
    if str(p.get("opening_type")) != "pocket" or opening.parent_id not in doc.entities:
        return True
    wall = doc.get(opening.parent_id)
    w = wall.params
    L = math.hypot(float(w["x2"]) - float(w["x1"]), float(w["y2"]) - float(w["y1"]))
    width, offset = float(p["width"]), float(p["offset"])
    need = width - 2 * JAMB
    at_w = _at_end(resolved(opening.kind, p)["hinge"], 1, inside_sign(doc, wall))
    free = L - offset - width / 2 if at_w else offset - width / 2
    return free >= need - 1e-9


def _at_end(hinge, viewer_s, sign_in):
    """True αν η πλευρά ``hinge`` (για θεατή στην πλευρά viewer_s) είναι στο u = W."""
    # Θεατής στην +n πλευρά κοιτάζει τον τοίχο: αριστερά του είναι η +u.
    return (hinge == "left") == (viewer_s * sign_in > 0)


# --- 3D -------------------------------------------------------------------
def _box(out, role, u0, u1, s0, s1, z0, z1):
    u0, u1 = sorted((u0, u1)); s0, s1 = sorted((s0, s1)); z0, z1 = sorted((z0, z1))
    if u1 - u0 > 1e-6 and s1 - s0 > 1e-6 and z1 - z0 > 1e-6:
        out.append((role, (u0, s0, z0), (u1, s1, z1)))


def _glass(out, u0, u1, z0, z1, sc, bars_h, bars_v):
    _box(out, "glass", u0, u1, sc - GLASS_D / 2, sc + GLASS_D / 2, z0, z1)
    bd = GLASS_D / 2 + 0.006
    for k in range(1, bars_v + 1):
        uc = u0 + (u1 - u0) * k / (bars_v + 1)
        _box(out, "leaf", uc - BAR / 2, uc + BAR / 2, sc - bd, sc + bd, z0, z1)
    for k in range(1, bars_h + 1):
        zc = z0 + (z1 - z0) * k / (bars_h + 1)
        _box(out, "leaf", u0, u1, sc - bd, sc + bd, zc - BAR / 2, zc + BAR / 2)


def _sash(out, u0, u1, z0, z1, s0, s1, bars_h, bars_v, bottom=SASH, face=SASH):
    """Φύλλο με τζάμι: ορθοστάτες, τραβέρσες, υαλοπίνακας και καΐτια."""
    face = min(face, (u1 - u0) / 3)
    bottom = min(bottom, (z1 - z0) / 3)
    _box(out, "leaf", u0, u0 + face, s0, s1, z0, z1)
    _box(out, "leaf", u1 - face, u1, s0, s1, z0, z1)
    _box(out, "leaf", u0 + face, u1 - face, s0, s1, z1 - face, z1)
    _box(out, "leaf", u0 + face, u1 - face, s0, s1, z0, z0 + bottom)
    _glass(out, u0 + face, u1 - face, z0 + bottom, z1 - face, (s0 + s1) / 2, bars_h, bars_v)


def _lever(out, uc, s_face, d, zh, toward):
    """Χερούλι: ροζέτα + μοχλός. d = φορά της όψης (±1)· toward = (du, dz) του μοχλού."""
    _box(out, "handle", uc - 0.015, uc + 0.015, s_face, s_face + d * 0.012, zh - 0.035, zh + 0.035)
    du, dz = toward
    s1, s2 = s_face + d * 0.012, s_face + d * 0.032
    if dz:
        _box(out, "handle", uc - 0.008, uc + 0.008, s1, s2, zh, zh + dz * 0.12)
    else:
        _box(out, "handle", uc, uc + du * 0.13, s1, s2, zh - 0.009, zh + 0.009)


def _shutter_leaf(out, u0, u1, s0, s1, z0, z1):
    """Παντζούρι με περσίδες: πλαίσιο + οριζόντιες περσίδες ανά ~4,5 cm."""
    st, rail = 0.06, 0.09
    _box(out, "shading", u0, u0 + st, s0, s1, z0, z1)
    _box(out, "shading", u1 - st, u1, s0, s1, z0, z1)
    _box(out, "shading", u0 + st, u1 - st, s0, s1, z0, z0 + rail)
    _box(out, "shading", u0 + st, u1 - st, s0, s1, z1 - rail, z1)
    zm = (z0 + z1) / 2
    _box(out, "shading", u0 + st, u1 - st, s0, s1, zm - 0.03, zm + 0.03)
    sm0, sm1 = s0 + (s1 - s0) * 0.2, s1 - (s1 - s0) * 0.2
    for a, b in ((z0 + rail, zm - 0.03), (zm + 0.03, z1 - rail)):
        n = max(1, int((b - a) / 0.045))
        for k in range(n):
            zc = a + (b - a) * (k + 0.5) / n
            _box(out, "shading", u0 + st, u1 - st, sm0, sm1, zc - 0.006, zc + 0.006)


def joinery_boxes(kind, params, t, sign_in=1):
    """Κουτιά ``[(role, lo, hi)]`` στο τοπικό πλαίσιο (u, s, z) του ανοίγματος.

    ``sign_in``: +1 αν το «μέσα» είναι η +n πλευρά του τοίχου (βλ. inside_sign)·
    χρειάζεται για να βγαίνουν σωστά αριστερά/δεξιά.
    """
    r = resolved(kind, params)
    r["_sign_in"] = sign_in
    W, H = float(params["width"]), float(params["height"])
    typ, n = r["opening_type"], r["leaves"]
    out = []
    half = t / 2
    if typ in ("interior_flush", "interior_panel", "security", "pocket", "folding"):
        return _door_boxes(out, r, W, H, t)
    door = kind == "door"
    sliding = typ in SLIDING
    fd = min(SLIDE_FRAME_D if sliding else FRAME_D, t)
    # Ποδιά (έξω) / περβάζι (μέσα): πάνω τους πατά η κάσα.
    z0 = 0.0
    if r["ledge"] in ("outside", "both"):
        _box(out, "sill", 0.0, W, -half - SILL_OUT, -fd / 2, 0.0, SILL_OUT)
        z0 = SILL_OUT
    if r["ledge"] in ("inside", "both"):
        _box(out, "sill", 0.0, W, fd / 2, half + SILL_IN, 0.0, SILL_IN)
        z0 = max(z0, SILL_IN) if r["ledge"] == "inside" else z0
    zt = H
    if r["shading"] == "roller":
        # Κουτί ρολού στο πάνω μέρος του ανοίγματος, στην εξωτερική παρειά (ορατό στην όψη).
        zt = H - ROLLER_BOX
        rd = min(0.18, max(0.6 * t, 0.08), t)
        _box(out, "shading", 0.0, W, -half, -half + rd, zt, H)
        g = min(0.03, t / 4)
        _box(out, "shading", 0.0, ROLLER_GUIDE, -half, -half + g, z0, zt)
        _box(out, "shading", W - ROLLER_GUIDE, W, -half, -half + g, z0, zt)
    fb = THRESHOLD if door else FRAME
    _box(out, "frame", 0.0, FRAME, -fd / 2, fd / 2, z0, zt)
    _box(out, "frame", W - FRAME, W, -fd / 2, fd / 2, z0, zt)
    _box(out, "frame", FRAME, W - FRAME, -fd / 2, fd / 2, zt - FRAME, zt)
    _box(out, "frame", FRAME, W - FRAME, -fd / 2, fd / 2, z0, z0 + fb)
    ui0, ui1, zi0, zi1 = FRAME, W - FRAME, z0 + fb, zt - FRAME
    if r["transom"]:
        # Φεγγίτης πάνω: ανακλινόμενο φύλλο πάνω από την τραβέρσα.
        zr = zi1 - r["transom"]
        _box(out, "frame", ui0, ui1, -fd / 2, fd / 2, zr - TRANSOM_RAIL, zr)
        _sash(out, ui0, ui1, zr, zi1, SASH_S[0], SASH_S[1], 0, r["bars_v"], bottom=0.07, face=0.07)
        _lever(out, (ui0 + ui1) / 2, SASH_S[1], 1, zi1 - 0.035, (0, -1))
        zi1 = zr - TRANSOM_RAIL
    sw = 1 if r["swing"] == "in" else -1
    bottom = DOOR_RAIL if door else SASH
    zh = min(HANDLE_Z, (zi0 + zi1) / 2) if door else (zi0 + zi1) / 2
    if typ == "fixed":
        _glass(out, ui0, ui1, zi0, zi1, 0.0, r["bars_h"], r["bars_v"])
    elif typ == "hopper":
        _sash(out, ui0, ui1, zi0, zi1, SASH_S[0], SASH_S[1], r["bars_h"], r["bars_v"])
        _lever(out, (ui0 + ui1) / 2, SASH_S[1], 1, zi1 - SASH / 2, (0, -1))
    elif typ in ("casement", "tilt_turn", "balcony_casement"):
        s0, s1 = (SASH_S if sw > 0 else (-SASH_S[1], -SASH_S[0]))
        lw = (ui1 - ui0) / n
        active = _active_leaf(r, n, sw)
        for k in range(n):
            # Αρμός ~4 mm ανάμεσα στα φύλλα που συναντιούνται.
            a = ui0 + k * lw + (GAP / 2 if k else 0.0)
            b = ui0 + (k + 1) * lw - (GAP / 2 if k < n - 1 else 0.0)
            _sash(out, a, b, zi0, zi1, s0, s1, r["bars_h"], r["bars_v"], bottom=bottom)
            if k == active:
                at_w = _hinge_at_w(r, n, k)
                uc = a + SASH / 2 if at_w else b - SASH / 2
                # Χερούλι στον ορθοστάτη κλεισίματος, από την πλευρά που ανοίγει (μέσα).
                face_s = s1 if sw > 0 else s0
                _lever(out, uc, face_s, sw, zh, (0, -1) if not door else ((1, 0) if at_w else (-1, 0)))
    elif sliding:
        ov = SASH  # επικάλυψη στα σημεία συνάντησης
        lw = (ui1 - ui0 + (n - 1) * ov) / n
        for k in range(n):
            a = ui0 + k * (lw - ov)
            sc = -TRACK if k % 2 == 0 else TRACK
            _sash(out, a, a + lw, zi0, zi1, sc - TRACK_D / 2, sc + TRACK_D / 2, r["bars_h"], r["bars_v"],
                  bottom=bottom)
            # Χούφτα στον ορθοστάτη προς την κάσα (ακραία φύλλα), αλλιώς στον αριστερό.
            uc = a + lw - SASH / 2 if k == n - 1 else a + SASH / 2
            _box(out, "handle", uc - 0.012, uc + 0.012, sc + TRACK_D / 2, sc + TRACK_D / 2 + 0.018,
                 zh - 0.10, zh + 0.10)
    if r["shading"] == "shutters":
        # Ανοιχτά εξωτερικά παντζούρια, διπλωμένα πάνω στην όψη δίπλα στο άνοιγμα.
        ns = 1 if W <= 0.8 else 2
        ws = W / ns
        sides = (_at_end(r["hinge"], -1, sign_in),) if ns == 1 else (False, True)
        for at_w in sides:
            a, b = (W, W + ws) if at_w else (-ws, 0.0)
            _shutter_leaf(out, a, b, -half - SHUTTER_D, -half, z0, zt)
    return out


def _hinge_at_w(r, n, k):
    """Για φύλλο k από n: μεντεσέδες στο u = W; (σε δίφυλλα στις εξωτερικές κάσες)."""
    if n == 1:
        return r["_at_w"]
    if k == 0:
        return False
    if k == n - 1:
        return True
    return r["_at_w"]


def _active_leaf(r, n, sw):
    """Το κύριο φύλλο (με χερούλι): στο μονόφυλλο το μοναδικό· στο δίφυλλο η πλευρά ``hinge``."""
    r["_at_w"] = _at_end(r["hinge"], sw, r.get("_sign_in", 1))
    if n == 1:
        return 0
    return n - 1 if r["_at_w"] else 0


def _door_boxes(out, r, W, H, t):
    typ, n = r["opening_type"], r["leaves"]
    half = t / 2
    sw = 1 if r["swing"] == "in" else -1
    sign_in = r.get("_sign_in", 1)
    if typ == "security":
        jf, jd, lt = SECURITY_FRAME, min(t, 0.14), SECURITY_LEAF
    elif typ == "folding":
        jf, jd, lt = 0.05, min(t, 0.10), 0.03
    else:
        jf, jd, lt = JAMB, t, DOOR_LEAF            # κάσα πλάτους τοίχου
    _box(out, "frame", 0.0, jf, -jd / 2, jd / 2, 0.0, H)
    _box(out, "frame", W - jf, W, -jd / 2, jd / 2, 0.0, H)
    _box(out, "frame", jf, W - jf, -jd / 2, jd / 2, H - jf, H)
    ui0, ui1, ztop = jf + GAP, W - jf - GAP, H - jf - GAP
    zb = FLOOR_GAP
    if typ == "pocket":
        at_w = _at_end(r["hinge"], 1, sign_in)
        s0, s1 = -lt / 2, lt / 2
        _box(out, "leaf", ui0, ui1, s0, s1, zb, ztop)
        uc = ui0 + 0.05 if at_w else ui1 - 0.05      # χούφτα στο ελεύθερο άκρο
        for f, d in ((s1, 1), (s0, -1)):
            _box(out, "handle", uc - 0.0125, uc + 0.0125, f, f + d * 0.004, HANDLE_Z - 0.075, HANDLE_Z + 0.075)
        return out
    if typ == "folding":
        at_w = _at_end(r["hinge"], 1, sign_in)
        pw = (ui1 - ui0) / n
        for k in range(n):
            a = ui0 + k * pw
            _box(out, "leaf", a + GAP / 2, a + pw - GAP / 2, -lt / 2, lt / 2, zb, ztop)
        k_free = 0 if at_w else n - 1
        uc = ui0 + k_free * pw + (0.05 if at_w else pw - 0.05)
        for f, d in ((lt / 2, 1), (-lt / 2, -1)):
            _box(out, "handle", uc - 0.0125, uc + 0.0125, f, f + d * 0.01, HANDLE_Z - 0.06, HANDLE_Z + 0.06)
        return out
    # Ανοιγόμενη: το φύλλο στην παρειά της κάσας προς την πλευρά που ανοίγει.
    face = sw * jd / 2
    s0, s1 = sorted((face, face - sw * lt))
    lw = (ui1 - ui0) / n
    at_w = _at_end(r["hinge"], sw, sign_in)
    active = (n - 1 if at_w else 0) if n > 1 else 0
    for k in range(n):
        a, b = ui0 + k * lw + (GAP / 2 if k else 0), ui0 + (k + 1) * lw - (GAP / 2 if k < n - 1 else 0)
        _box(out, "leaf", a, b, s0, s1, zb, ztop)
        if typ == "interior_panel":
            # Δύο ταμπλάδες ανά όψη (κάτω μεγαλύτερος), εσοχή 12 cm από τα άκρα.
            zm = zb + (ztop - zb) * 0.45
            for za, zc in ((zb + 0.20, zm - 0.08), (zm + 0.08, ztop - 0.12)):
                _box(out, "leaf", a + 0.12, b - 0.12, s1, s1 + 0.008, za, zc)
                _box(out, "leaf", a + 0.12, b - 0.12, s0 - 0.008, s0, za, zc)
        if typ == "security":
            # Επένδυση εξωτερικής όψης: οριζόντιες ραβδώσεις.
            out_face, d = (s0, -1) if sw > 0 else (s1, 1)
            for j in range(1, 6):
                zc = zb + (ztop - zb) * j / 6
                _box(out, "leaf", a + 0.10, b - 0.10, out_face, out_face + d * 0.005, zc - 0.006, zc + 0.006)
        if k == active:
            hinge_here = at_w if n == 1 else (k == n - 1)
            uc = a + 0.065 if hinge_here else b - 0.065
            toward = (1, 0) if hinge_here else (-1, 0)
            _lever(out, uc, s1, 1, HANDLE_Z, toward)
            _lever(out, uc, s0, -1, HANDLE_Z, toward)
    return out


def leaf_count(kind, params):
    """Πλήθος φύλλων του κύριου τμήματος (χωρίς φεγγίτη και παντζούρια)."""
    return resolved(kind, params)["leaves"]


def material_look(params, kind, role):
    """Χρώμα ανά ρόλο από το υλικό κουφώματος (όταν ο χρήστης δεν έχει βάψει τον ρόλο)."""
    r = resolved(kind, params)
    _name, color, rough, metal = FINISHES.get(r["finish"], FINISHES["alu_anthracite"])
    if role in ("frame", "leaf", "shading"):
        if r["opening_type"] == "security" and role == "frame":
            return {"color": "#3b3b3b", "roughness": 0.5, "metalness": 0.4}
        return {"color": color, "roughness": rough, "metalness": metal}
    if role == "handle":
        return {"color": "#b8bcc0", "roughness": 0.3, "metalness": 0.85}
    if role == "sill":
        return {"color": "#e6e2da", "roughness": 0.3, "metalness": 0.0}
    return {}


# --- 2D σύμβολο κάτοψης ---------------------------------------------------
def _arc(cx, cy, r, a0, a1, steps=16):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / steps), cy + r * math.sin(a0 + (a1 - a0) * i / steps))
            for i in range(steps + 1)]


def _arrow(out, u0, u1, s):
    """Βέλος κίνησης από u0 προς u1 στο ύψος s."""
    d = 1 if u1 > u0 else -1
    out.append(("thin", [(u0, s), (u1, s)]))
    out.append(("thin", [(u1 - d * 0.06, s - 0.035), (u1, s), (u1 - d * 0.06, s + 0.035)]))


def _swing(out, hinge_u, face_s, lw, toward_u, d, style="solid"):
    """Φύλλο ανοιχτό 90° + τόξο έως τη θέση κλεισίματος (ανοιγόμενα)."""
    tip = (hinge_u, face_s + d * lw)
    out.append((style, [(hinge_u, face_s), tip]))
    a_open = math.atan2(d, 0.0)
    a_closed = 0.0 if toward_u > 0 else math.pi
    out.append(("thin", _arc(hinge_u, face_s, lw, a_open, a_closed if abs(a_closed - a_open) <= math.pi
                             else a_closed - 2 * math.pi)))


def plan_symbol(kind, params, t, sign_in=1):
    """Σύμβολο κάτοψης ``[(style, [(u, s), ...])]``· style: solid / thin / dashed.

    Συνήθης ελληνική σχεδιαστική πρακτική (1:50): παρειές και κάσα· στα
    ανοιγόμενα φύλλο ανοιχτό 90° με τόξο προς την πλευρά που ανοίγει· στα
    συρόμενα τα φύλλα στους οδηγούς τους με βέλη· στη χωνευτή η θήκη μέσα
    στον τοίχο διακεκομμένη· ό,τι είναι πάνω από το επίπεδο τομής (κουτί
    ρολού, ανακλινόμενο) διακεκομμένο.
    """
    r = resolved(kind, params)
    r["_sign_in"] = sign_in
    W = float(params["width"])
    typ, n = r["opening_type"], r["leaves"]
    half = t / 2
    sw = 1 if r["swing"] == "in" else -1
    out = []
    # Παρειές του ανοίγματος (κλείνουν την τομή του τοίχου).
    out.append(("solid", [(0.0, -half), (0.0, half)]))
    out.append(("solid", [(W, -half), (W, half)]))
    if typ in ("interior_flush", "interior_panel", "security"):
        jd = min(t, 0.14) if typ == "security" else t
        jf = SECURITY_FRAME if typ == "security" else JAMB
        lw = (W - 2 * jf) / n
        at_w = _at_end(r["hinge"], sw, sign_in)
        face = sw * jd / 2
        if n == 1:
            hu = W - jf if at_w else jf
            _swing(out, hu, face, lw, -1 if at_w else 1, sw)
        else:
            _swing(out, jf, face, lw, 1, sw)
            _swing(out, W - jf, face, lw, -1, sw)
        return out
    if typ == "pocket":
        at_w = _at_end(r["hinge"], 1, sign_in)
        out.append(("solid", [(JAMB, -DOOR_LEAF / 2), (W - JAMB, -DOOR_LEAF / 2)]))
        out.append(("solid", [(JAMB, DOOR_LEAF / 2), (W - JAMB, DOOR_LEAF / 2)]))
        L = W - 2 * JAMB
        a, b = (W, W + L) if at_w else (-L, 0.0)
        # Θήκη (κάσα χωνευτής) μέσα στον τοίχο.
        for s in (-0.03, 0.03):
            out.append(("dashed", [(a, s), (b, s)]))
        out.append(("dashed", [(b if at_w else a, -0.03), (b if at_w else a, 0.03)]))
        c = W / 2
        _arrow(out, c - 0.15 if at_w else c + 0.15, c + 0.15 if at_w else c - 0.15, half + 0.12)
        return out
    if typ == "folding":
        at_w = _at_end(r["hinge"], 1, sign_in)
        pw = (W - 0.10) / n
        ang = math.radians(30)          # σχεδιάζεται μισοανοιγμένη
        u = W - 0.05 if at_w else 0.05
        d_u = -1 if at_w else 1
        pts = [(u, 0.0)]
        for k in range(n):
            u += d_u * pw * math.cos(ang)
            pts.append((u, (pw * math.sin(ang)) * sw if k % 2 == 0 else 0.0))
        out.append(("solid", pts))
        # Βέλος ανοίγματος: τα φύλλα μαζεύουν προς την πλευρά ``hinge``.
        c, d = W / 2, -d_u
        _arrow(out, c - d * 0.15, c + d * 0.15, sw * (pw * math.sin(ang) + 0.10))
        return out
    door = kind == "door"
    sliding = typ in SLIDING
    fd = min(SLIDE_FRAME_D if sliding else FRAME_D, t)
    # Κάσα και τζάμι.
    out.append(("solid", [(0.0, -fd / 2), (W, -fd / 2)]))
    out.append(("solid", [(0.0, fd / 2), (W, fd / 2)]))
    ui0, ui1 = FRAME, W - FRAME
    if typ == "fixed":
        out.append(("thin", [(ui0, 0.0), (ui1, 0.0)]))
    elif typ == "hopper":
        out.append(("thin", [(ui0, 0.0), (ui1, 0.0)]))
        k = 0.12                       # προβολή του ανακλινόμενου φύλλου (πάνω από την τομή)
        out.append(("dashed", [(ui0, fd / 2), (ui0, fd / 2 + k), (ui1, fd / 2 + k), (ui1, fd / 2)]))
    elif typ in ("casement", "tilt_turn", "balcony_casement"):
        out.append(("thin", [(ui0, 0.0), (ui1, 0.0)]))
        lw = (ui1 - ui0) / n
        face = sw * fd / 2
        _active_leaf(r, n, sw)
        for k in range(n):
            at_w = _hinge_at_w(r, n, k)
            a, b = ui0 + k * lw, ui0 + (k + 1) * lw
            _swing(out, b if at_w else a, face, lw, -1 if at_w else 1, sw, style="thin")
    elif sliding:
        ov = SASH
        lw = (ui1 - ui0 + (n - 1) * ov) / n
        for k in range(n):
            a = ui0 + k * (lw - ov)
            sc = -TRACK if k % 2 == 0 else TRACK
            out.append(("solid", [(a, sc), (a + lw, sc)]))
            c = a + lw / 2
            d = 1 if k < n / 2 else -1         # τα φύλλα κινούνται το ένα πάνω στο άλλο
            if n % 2 and k == n // 2:
                d = 1 if r["hinge"] == "left" else -1
            _arrow(out, c - d * 0.15, c + d * 0.15, sc + (0.06 if sc > 0 else -0.06))
    if r["shading"] == "roller":
        rd = min(0.18, max(0.6 * t, 0.08), t)
        out.append(("dashed", [(0.0, -half + rd), (W, -half + rd)]))
    elif r["shading"] == "shutters":
        ns = 1 if W <= 0.8 else 2
        ws = W / ns
        sides = (_at_end(r["hinge"], -1, sign_in),) if ns == 1 else (False, True)
        for at_w in sides:
            hu = W if at_w else 0.0
            tip = hu + ws if at_w else hu - ws
            out.append(("solid", [(hu, -half - SHUTTER_D / 2), (tip, -half - SHUTTER_D / 2)]))
            # Ημικύκλιο από έξω: από κλειστό (πάνω στο άνοιγμα) σε ανοιχτό (πάνω στην όψη).
            a0, a1 = (math.pi, 2 * math.pi) if at_w else (0.0, -math.pi)
            out.append(("dashed", _arc(hu, -half, ws, a0, a1, 16)))
    if r["ledge"] in ("outside", "both"):
        out.append(("thin", [(0.0, -half), (0.0, -half - SILL_OUT), (W, -half - SILL_OUT), (W, -half)]))
    if r["ledge"] in ("inside", "both"):
        out.append(("thin", [(0.0, half), (0.0, half + SILL_IN), (W, half + SILL_IN), (W, half)]))
    return out


def plan_symbol_world(doc, opening):
    """Σύμβολο κάτοψης σε συντεταγμένες κόσμου ``[(style, [(x, y), ...])]`` ή [] (βασικό κούφωμα)."""
    if opening.kind not in ("door", "window") or not is_typed(opening.params):
        return []
    if opening.parent_id not in doc.entities or doc.get(opening.parent_id).kind != "wall":
        return []
    wall = doc.get(opening.parent_id)
    w = wall.params
    x1, y1, x2, y2 = (float(w[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-9:
        return []
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    sign_in = inside_sign(doc, wall)
    nx, ny = -uy * sign_in, ux * sign_in
    start = float(opening.params["offset"]) - float(opening.params["width"]) / 2
    out = []
    for style, pts in plan_symbol(opening.kind, opening.params, float(w["thickness"]), sign_in):
        out.append((style, [(x1 + ux * (start + u) + nx * s, y1 + uy * (start + u) + ny * s) for u, s in pts]))
    return out


# --- Έτοιμα κουφώματα (Βιβλιοθήκη → Κουφώματα) -----------------------------
# (κλειδί, είδος, όνομα, πλάτος, ύψος ανοίγματος, ποδιά/στάθμη, παράμετροι)
PRESETS = (
    ("w_casement_1", "window", "Παράθυρο ανοιγόμενο μονόφυλλο 60×60 (WC)", 0.60, 0.60, 1.50,
     {"opening_type": "casement", "leaves": 1}),
    ("w_casement_2", "window", "Παράθυρο ανοιγόμενο δίφυλλο 120×140", 1.20, 1.40, 0.90,
     {"opening_type": "casement", "leaves": 2}),
    ("w_tilt_1", "window", "Ανοιγοανακλινόμενο μονόφυλλο 80×120", 0.80, 1.20, 0.90,
     {"opening_type": "tilt_turn", "leaves": 1}),
    ("w_tilt_2_roller", "window", "Ανοιγοανακλινόμενο δίφυλλο 120×140 με ρολό", 1.20, 1.58, 0.90,
     {"opening_type": "tilt_turn", "leaves": 2, "shading": "roller"}),
    ("w_hopper", "window", "Ανακλινόμενο (φεγγίτης) 80×50", 0.80, 0.50, 1.60,
     {"opening_type": "hopper"}),
    ("w_sliding_2", "window", "Συρόμενο επάλληλο δίφυλλο 160×120 με ρολό", 1.60, 1.38, 0.90,
     {"opening_type": "sliding", "leaves": 2, "shading": "roller"}),
    ("w_sliding_3", "window", "Συρόμενο επάλληλο τρίφυλλο 240×120", 2.40, 1.20, 0.90,
     {"opening_type": "sliding", "leaves": 3}),
    ("w_fixed", "window", "Σταθερό 100×100", 1.00, 1.00, 1.00, {"opening_type": "fixed"}),
    ("w_transom", "window", "Ανοιγόμενο δίφυλλο με φεγγίτη 120×180", 1.20, 1.80, 0.60,
     {"opening_type": "casement", "leaves": 2, "transom": 0.40}),
    ("w_shutters", "window", "Δίφυλλο με παντζούρια και καΐτια 110×140", 1.10, 1.40, 0.90,
     {"opening_type": "casement", "leaves": 2, "shading": "shutters", "bars_h": 2, "finish": "wood_oak"}),
    ("d_flush_80", "door", "Εσωτερική πρεσαριστή 80×210", 0.80, 2.10, 0.0, {"opening_type": "interior_flush"}),
    ("d_flush_90", "door", "Εσωτερική πρεσαριστή 90×210", 0.90, 2.10, 0.0, {"opening_type": "interior_flush"}),
    ("d_flush_70", "door", "Εσωτερική πρεσαριστή 70×210 (WC)", 0.70, 2.10, 0.0, {"opening_type": "interior_flush"}),
    ("d_panel_80", "door", "Εσωτερική ταμπλαδωτή 80×210", 0.80, 2.10, 0.0, {"opening_type": "interior_panel"}),
    ("d_security", "door", "Εξώπορτα θωρακισμένη 90×215", 0.90, 2.15, 0.0, {"opening_type": "security"}),
    ("d_balcony_2", "door", "Μπαλκονόπορτα ανοιγόμενη δίφυλλη 140×220 με ρολό", 1.40, 2.38, 0.0,
     {"opening_type": "balcony_casement", "leaves": 2, "shading": "roller"}),
    ("d_balcony_slide", "door", "Μπαλκονόπορτα συρόμενη επάλληλη 200×220 με ρολό", 2.00, 2.38, 0.0,
     {"opening_type": "balcony_sliding", "leaves": 2, "shading": "roller"}),
    ("d_pocket", "door", "Χωνευτή συρόμενη 80×210", 0.80, 2.10, 0.0, {"opening_type": "pocket"}),
    ("d_folding", "door", "Φυσαρμόνικα 120×210", 1.20, 2.10, 0.0, {"opening_type": "folding"}),
)


def preset(key):
    for k, kind, name, w, h, sill, params in PRESETS:
        if k == key:
            return {"kind": kind, "name": name, "width": w, "height": h, "sill": sill, "params": dict(params)}
    raise KeyError(key)
