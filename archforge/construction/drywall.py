"""Plasterboard (γυψοσανίδα): suspended ceilings and stud walls, with their material take-off.

Owner: «Εργαλείο για ταβάνια γυψοσανίδας» — «τοποθετήσεις γυψοσανίδας σε
τοίχους ή ταβάνια (ψευδοροφές) με τα υλικά που χρειάζονται … σανίδες,
ορθοστάτες/οδηγοί CW/UW ή CD/UD, αναρτήσεις, βίδες, ταινίες, στόκος, μόνωση —
στη λίστα υλικών με τιμές».

A ``drywall_ceiling`` is one suspended ceiling: the whole room (``room_id``,
it follows the room's walls, net of half their thickness) or a drawn outline
(``points``), on storey ``level_z``.  It hangs ``drop`` below the underside of
the slab, i.e. the room height (lowest bounding wall) less ``drop``; boards
(``board``: standard / moisture resistant for bathrooms and kitchens / fire
resistant), one or two layers, optional mineral wool (``insulation`` m, 0 =
none) and an optional perimeter step with a hidden light slot (``cove``: the
band ``cove_width`` wide stays low, the field is ``cove_depth`` higher).

Take-off rules — the usual two-level CD/UD grid of the published ceiling
system sheets (e.g. Knauf D112; stated here so they can be checked):

* Main CD 60/27 at ``MAIN_SPACING`` 1.00 m, secondary CD 60/27 across them at
  ``SECONDARY_SPACING`` 0.50 m (12.5 mm boards fixed across the secondary
  profiles), hangers along the main profiles at ``HANGER_SPACING`` ≤ 0.90 m;
  the lines are clipped to the real outline (an L-shaped room counts right).
* Direct hangers up to ``DIRECT_HANGER_MAX`` 12.5 cm of suspension, nonius /
  rod hangers above; one ceiling anchor per hanger.
* One cross connector per main × secondary crossing; extension pieces where a
  line is longer than one ``PROFILE_LENGTH`` 4.00 m bar.
* UD 28/27 along the perimeter, fixed every ``EDGE_FIXING`` 0.625 m.
* Boards: area × layers × (1 + 10 %), sheets of 1.20 × 2.00 m.  Screws
  TN 3.5×25 17 / m² for one layer; for two, the first layer at a third of the
  density and TN 3.5×35 17 / m² for the second.  Joint tape 1.4 m / m² of the
  visible layer (1/1.20 + 1/2.00 of the sheet), separating tape round the
  edge, joint compound 0.30 kg / m² visible layer (+ 0.20 kg / m² inner one).
* Mineral wool m² = area × 1.05.  Cove: vertical board strip (inner perimeter ×
  step) and corner beads on both edges of the step.

Stud walls (wall types ``drywall_100`` / ``drywall_double_125``, CW/UW 75):
CW studs at 0.625 m (+2 at the jambs of every opening) × height, UW top and
bottom (less door widths), boards on both faces × layers × 1.10, screws 15 /
m² face for the outer layer and 7 for the inner one, joint tape 0.85 m / m²
face, compound as above, mineral wool m² = net area × 1.05.

Proposed values, to be confirmed with the data sheet of the system used
(ceiling system sheets of the large plasterboard makers, ``SOURCES``).
Pre-design take-off, for review.
"""
from __future__ import annotations

import math

MAIN_SPACING, SECONDARY_SPACING, HANGER_SPACING = 1.00, 0.50, 0.90
DIRECT_HANGER_MAX = 0.125
PROFILE_LENGTH = 4.00
EDGE_FIXING = 0.625
SHEET = (1.20, 2.00)
BOARD_WASTE, PROFILE_WASTE, WOOL_WASTE = 0.10, 0.05, 0.05
SCREWS_PER_M2 = 17
JOINT_TAPE_PER_M2 = round(1 / SHEET[0] + 1 / SHEET[1], 2) + 0.07    # 1.40 with the cut ends
COMPOUND_OUTER, COMPOUND_INNER = 0.30, 0.20
BOARD_THICKNESS = 0.0125
STUD_SPACING = 0.625
WALL_SCREWS_OUTER, WALL_SCREWS_INNER, WALL_TAPE = 15, 7, 0.85
DEFAULT_DROP = 0.20
MIN_DROP, MAX_DROP = 0.05, 1.50

# board: label (EN 520 type), plan/3D colour
BOARDS = {
    "standard": ("Απλή γυψοσανίδα 12,5 mm (τύπος A)", "#f1efea"),
    "moisture": ("Ανθυγρή γυψοσανίδα 12,5 mm (τύπος H2, πράσινη)", "#cfe3cf"),
    "fire": ("Πυράντοχη γυψοσανίδα 12,5 mm (τύπος F, ροζ)", "#f0d3d6"),
}
WET_USES = ("bathroom", "wc", "kitchen")
WALL_TYPES = {"drywall_100": 1, "drywall_double_125": 2}       # wall type: boards per face
SOURCES = ("Knauf, φύλλο συστήματος D11/D112 «Ψευδοροφές γυψοσανίδας με μεταλλικό σκελετό CD 60/27» "
           "(αποστάσεις a/b/c, ανάρτηση, βίδες TN 17 τεμ./m²) · Knauf W11/W111–W112 (τοίχοι CW/UW, 625 mm) · "
           "deutschland-rechner.de «Abgehängte Decke Rechner» (φύρα 10 %, απευθείας αναρτήρας ως 12,5 cm)")
NOTE = "προτεινόμενο, προς επιβεβαίωση με το φυλλάδιο του συστήματος"
PROVENANCE = ("Ψευδοροφή CD/UD: κύριοι CD ανά 1,00 m, δευτερεύοντες ανά 0,50 m, αναρτήσεις ανά ≤0,90 m, UD περιμετρικά, "
              f"σανίδες με φύρα {BOARD_WASTE:.0%}, βίδες {SCREWS_PER_M2}/m² ανά στρώση, ταινία {JOINT_TAPE_PER_M2:.2f} m/m², "
              f"στόκος {COMPOUND_OUTER:.2f} kg/m² — {NOTE}. Προμελέτη, προς έλεγχο")


# --- schema ---------------------------------------------------------------------------------------

def validate(p):
    if not p.get("points") and not p.get("room_id"):
        raise ValueError("drywall ceiling needs a room or an outline")
    if "board" in p and str(p["board"]) not in BOARDS:
        raise ValueError(f"board must be one of {', '.join(BOARDS)}")
    if "layers" in p and int(p["layers"]) not in (1, 2):
        raise ValueError("layers must be 1 or 2")
    drop = float(p.get("drop", DEFAULT_DROP))
    if not MIN_DROP <= drop <= MAX_DROP:
        raise ValueError(f"drop must be between {MIN_DROP} and {MAX_DROP} m")
    if int(p.get("cove", 0)):
        if float(p.get("cove_depth", 0.10)) > drop - 0.03:
            raise ValueError("the cove step must stay below the slab (step < drop)")
    if float(p.get("insulation", 0.0)) > drop:
        raise ValueError("insulation thicker than the void")


def default_params(points=None, room_id=None, level_z=0.0, board="standard"):
    p = {"level_z": float(level_z), "drop": DEFAULT_DROP, "board": board, "layers": 1, "insulation": 0.0,
         "cove": 0, "cove_width": 0.30, "cove_depth": 0.10}
    if room_id:
        p["room_id"] = str(room_id)
    else:
        p["points"] = [[round(float(x), 4), round(float(y), 4)] for x, y in points]
    return p


# --- geometry -------------------------------------------------------------------------------------

def _area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2.0


def _perimeter(poly):
    return sum(math.dist(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def _ccw(poly):
    pts = [(float(q[0]), float(q[1])) for q in poly]
    return pts if _area(pts) > 0 else pts[::-1]


def _room_face(doc, room_id):
    from archforge.architecture.rooms import find_room_face_by_id
    return find_room_face_by_id(doc, room_id)


def outline(doc, entity_or_params):
    """Live outline (CCW): the room's net interior (follows its walls) or the drawn points; None when lost."""
    p = getattr(entity_or_params, "params", entity_or_params)
    if p.get("room_id"):
        found = _room_face(doc, p["room_id"])
        if not found:
            return None
        from archforge.quantities.takeoff import net_polygon
        face, z = found
        return _ccw(net_polygon(doc, face.polygon, z))
    return _ccw(p["points"])


def room_height(doc, p, poly=None):
    """Floor-to-slab height: the room's lowest bounding wall, else the lowest wall of the storey (2.70 without)."""
    z = float(p["level_z"])
    if p.get("room_id"):
        found = _room_face(doc, p["room_id"])
        if found:
            from archforge.quantities.takeoff import _room_height
            return _room_height(doc, found[0].polygon, found[1])
    hs = [float(w.params["height"]) for w in doc.entities.values()
          if w.kind == "wall" and abs(float(w.params.get("z", 0.0)) - z) < 0.05]
    return min(hs) if hs else 2.70


def ceiling_level(doc, p):
    """Height of the finished ceiling above the storey floor («Ψ/Ο +2,60»)."""
    return round(room_height(doc, p) - float(p.get("drop", DEFAULT_DROP)), 3)


def room_use(doc, p):
    """'bathroom' / 'wc' / 'kitchen' / None for the room of a ceiling (by its name or use)."""
    from archforge.assistant.understanding import _use_from_text
    from archforge.geometry.regions import point_in_polygon
    z = float(p["level_z"])
    pts = outline(doc, p)
    if not pts:
        return None
    cx, cy = sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)
    for face in doc.active_room_faces(z=z):
        if point_in_polygon(cx, cy, face.polygon):
            meta = doc.room_metadata(face.signature)
            return _use_from_text(meta.get("use")) or _use_from_text(meta.get("name"))
    return None


def suggested_board(doc, p):
    return "moisture" if room_use(doc, p) in WET_USES else "standard"


def inner_outline(poly, width):
    """The field of a cove ceiling: the outline pushed in by ``width`` (same corners), or None."""
    from archforge.geometry.regions import offset_loop
    try:
        inner = offset_loop(poly, [-float(width)] * len(poly))
    except (ValueError, ZeroDivisionError):
        return None
    if len(inner) != len(poly) or _area(inner) <= 0.05:
        return None
    return [tuple(q) for q in inner]


def _prism(points, z0, z1, verts, tris, roles, role="board"):
    from archforge.geometry.mesh import _triangulate
    n, base = len(points), len(verts)
    verts += [(x, y, z0) for x, y in points] + [(x, y, z1) for x, y in points]
    for a, b, c in _triangulate(points):
        tris += [(base + a + n, base + b + n, base + c + n), (base + c, base + b, base + a)]
        roles += [role, role]
    for i in range(n):
        j = (i + 1) % n
        tris += [(base + i, base + j, base + j + n), (base + i, base + j + n, base + i + n)]
        roles += [role, role]


def _ring(outer, inner, z0, z1, verts, tris, roles, role="board"):
    """Closed band between two loops with the same corners (outer CCW)."""
    n, base = len(outer), len(verts)
    for loop in (outer, inner):
        verts += [(x, y, z0) for x, y in loop] + [(x, y, z1) for x, y in loop]
    ob, ot, ib, it = base, base + n, base + 2 * n, base + 3 * n
    for i in range(n):
        j = (i + 1) % n
        tris += [(ot + i, ot + j, it + j), (ot + i, it + j, it + i)]           # top
        tris += [(ob + i, ib + j, ob + j), (ob + i, ib + i, ib + j)]           # bottom
        tris += [(ob + i, ob + j, ot + j), (ob + i, ot + j, ot + i)]           # outer side
        tris += [(ib + i, it + j, ib + j), (ib + i, it + i, it + j)]           # inner side
        roles += [role] * 8


def ceiling_mesh(doc, p):
    """Board layer(s) at the ceiling level; with a cove: low band, upstand, raised field."""
    poly = outline(doc, p)
    if not poly or len(poly) < 3:
        raise ValueError("drywall ceiling has no outline")
    t = BOARD_THICKNESS * int(p.get("layers", 1))
    e = float(p["level_z"]) + ceiling_level(doc, p)
    verts, tris, roles = [], [], []
    inner = inner_outline(poly, float(p.get("cove_width", 0.30))) if int(p.get("cove", 0)) else None
    if inner is None:
        _prism(poly, e, e + t, verts, tris, roles)
    else:
        step = float(p.get("cove_depth", 0.10))
        field = inner_outline(inner, t) or inner
        _ring(poly, inner, e, e + t, verts, tris, roles, "band")
        if field is not inner:
            _ring(inner, field, e + t, e + step + t, verts, tris, roles, "band")
        _prism(field, e + step, e + step + t, verts, tris, roles)
    return tuple(verts), tuple(tris), tuple(roles)


# --- take-off -------------------------------------------------------------------------------------

def _frame(poly):
    """Unit vectors (u along the longest edge, v across) for the grid."""
    i = max(range(len(poly)), key=lambda k: math.dist(poly[k], poly[(k + 1) % len(poly)]))
    a, b = poly[i], poly[(i + 1) % len(poly)]
    L = math.dist(a, b)
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    return u, (-u[1], u[0])


def _lines(poly, axis, across, spacing):
    """Grid lines along ``axis``, spaced ≤ ``spacing`` across: ``[(offset, [(s0, s1), ...])]`` clipped to the outline."""
    pa = [(q[0] * axis[0] + q[1] * axis[1], q[0] * across[0] + q[1] * across[1]) for q in poly]
    lo, hi = min(q[1] for q in pa), max(q[1] for q in pa)
    n = max(1, math.ceil((hi - lo) / spacing - 1e-9))
    out = []
    for k in range(n):
        v = lo + (k + 0.5) * (hi - lo) / n
        xs = []
        for i in range(len(pa)):
            (x0, y0), (x1, y1) = pa[i], pa[(i + 1) % len(pa)]
            if (y0 <= v < y1) or (y1 <= v < y0):
                xs.append(x0 + (v - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        out.append((v, [(xs[j], xs[j + 1]) for j in range(0, len(xs) - 1, 2)]))
    return out


def count_ceiling(doc, entity):
    """Materials of one suspended ceiling, or None when its outline is lost."""
    p = entity.params
    poly = outline(doc, entity)
    if not poly:
        return None
    area, perim = abs(_area(poly)), _perimeter(poly)
    layers = int(p.get("layers", 1))
    u, v = _frame(poly)
    mains = _lines(poly, u, v, MAIN_SPACING)              # main CD along u, spaced across
    seconds = _lines(poly, v, u, SECONDARY_SPACING)       # secondary CD along v, spaced along u
    main_m = sum(s1 - s0 for _o, segs in mains for s0, s1 in segs)
    second_m = sum(s1 - s0 for _o, segs in seconds for s0, s1 in segs)
    hangers = sum(max(1, math.ceil((s1 - s0) / HANGER_SPACING - 1e-9)) for _o, segs in mains for s0, s1 in segs)
    # crossings: the secondary at u = w meets the main at v = o when both segments hold the point (w, o)
    crossings = 0
    for o, segs in mains:
        for w, ssegs in seconds:
            if any(s0 <= w <= s1 for s0, s1 in segs) and any(t0 <= o <= t1 for t0, t1 in ssegs):
                crossings += 1
    extensions = sum(max(0, math.ceil((s1 - s0) / PROFILE_LENGTH - 1e-9) - 1)
                     for lines in (mains, seconds) for _o, segs in lines for s0, s1 in segs)
    cd_m = (main_m + second_m) * (1 + PROFILE_WASTE)
    ud_m = perim * (1 + PROFILE_WASTE)
    cove = bool(int(p.get("cove", 0)))
    inner = inner_outline(poly, float(p.get("cove_width", 0.30))) if cove else None
    step_m2 = _perimeter(inner) * float(p.get("cove_depth", 0.10)) if inner else 0.0
    board_m2 = (area + step_m2) * layers * (1 + BOARD_WASTE)
    drop = float(p.get("drop", DEFAULT_DROP))
    wool = float(p.get("insulation", 0.0))
    screws25 = math.ceil((area + step_m2) * SCREWS_PER_M2 * ((1 / 3) if layers == 2 else 1) * (1 + BOARD_WASTE) - 1e-6)
    screws35 = math.ceil((area + step_m2) * SCREWS_PER_M2 * (1 + BOARD_WASTE) - 1e-6) if layers == 2 else 0
    return {"ceiling": entity.id, "name": entity.name or "Ψευδοροφή", "z": round(float(p["level_z"]), 2),
            "board": str(p.get("board", "standard")), "layers": layers, "area_m2": round(area, 2),
            "perimeter_m": round(perim, 2), "level_m": ceiling_level(doc, p), "drop_m": drop,
            "main_lines": len(mains), "secondary_lines": len(seconds),
            "cd_m": round(cd_m, 2), "cd_bars": math.ceil(cd_m / PROFILE_LENGTH - 1e-9),
            "ud_m": round(ud_m, 2), "ud_bars": math.ceil(ud_m / PROFILE_LENGTH - 1e-9),
            "ud_fixings": math.ceil(perim / EDGE_FIXING - 1e-9),
            "hangers": hangers, "hanger_type": "direct" if drop <= DIRECT_HANGER_MAX + 1e-9 else "nonius",
            "anchors": hangers, "cross_connectors": crossings, "extensions": extensions,
            "board_m2": round(board_m2, 2), "sheets": math.ceil(board_m2 / (SHEET[0] * SHEET[1]) - 1e-9),
            "screws_25": screws25, "screws_35": screws35,
            "joint_tape_m": round((area + step_m2) * JOINT_TAPE_PER_M2, 1), "edge_tape_m": round(perim, 1),
            "compound_kg": round((area + step_m2) * (COMPOUND_OUTER + (COMPOUND_INNER if layers == 2 else 0.0)), 1),
            "insulation_m": wool, "insulation_m2": round(area * (1 + WOOL_WASTE), 2) if wool > 0 else 0.0,
            "cove": cove, "cove_m": round(_perimeter(inner), 2) if inner else 0.0, "cove_board_m2": round(step_m2, 2)}


def _wall_openings(doc, wall):
    from archforge.construction.isotex import _wall_openings as openings
    return openings(doc, wall)


def count_wall(doc, wall):
    """Stud-wall materials (both faces) of one plasterboard wall, or None for other walls."""
    per_face = WALL_TYPES.get(str(wall.params.get("wall_type")))
    if per_face is None:
        return None
    p = wall.params
    length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
    height = float(p["height"])
    ops = _wall_openings(doc, wall)
    doors = [w for e in doc.entities.values() if e.kind == "door" and e.parent_id == wall.id
             for w in [float(e.params.get("width", 0.0))]]
    net = max(0.0, length * height - sum(w * h for w, h, _s in ops))
    studs = math.ceil(length / STUD_SPACING - 1e-9) + 1 + 2 * len(ops)
    cw_m = studs * height * (1 + PROFILE_WASTE)
    uw_m = max(0.0, 2 * length - sum(doors)) * (1 + PROFILE_WASTE)
    faces = 2 * net
    board_m2 = faces * per_face * (1 + BOARD_WASTE)
    return {"wall": wall.id, "name": wall.name or wall.id[:6], "z": round(float(p.get("z", 0.0)), 2),
            "wall_type": str(p["wall_type"]), "per_face": per_face, "length_m": round(length, 2), "height_m": round(height, 2),
            "net_m2": round(net, 2), "studs": studs, "cw_m": round(cw_m, 2), "cw_bars": math.ceil(cw_m / PROFILE_LENGTH - 1e-9),
            "uw_m": round(uw_m, 2), "uw_bars": math.ceil(uw_m / PROFILE_LENGTH - 1e-9),
            "uw_fixings": math.ceil(2 * length / EDGE_FIXING - 1e-9),
            "board_m2": round(board_m2, 2), "sheets": math.ceil(board_m2 / (SHEET[0] * 2.60) - 1e-9),
            "screws_25": math.ceil(faces * (WALL_SCREWS_INNER if per_face == 2 else WALL_SCREWS_OUTER) - 1e-6),
            "screws_35": math.ceil(faces * WALL_SCREWS_OUTER - 1e-6) if per_face == 2 else 0,
            "joint_tape_m": round(faces * WALL_TAPE, 1),
            "compound_kg": round(faces * (COMPOUND_OUTER + (COMPOUND_INNER if per_face == 2 else 0.0)), 1),
            "insulation_m2": round(net * (1 + WOOL_WASTE), 2)}


def take_off_drywall(doc):
    """``{"ceilings": [...], "walls": [...], "totals": {...}, "provenance", "source"}``."""
    ceilings = [r for e in sorted(doc.entities.values(), key=lambda e: e.id) if e.kind == "drywall_ceiling"
                for r in [count_ceiling(doc, e)] if r is not None]
    walls = [r for e in sorted(doc.entities.values(), key=lambda e: (float(e.params.get("z", 0.0)), e.id))
             if e.kind == "wall" and str(e.params.get("phase", "new")) != "demolish"
             for r in [count_wall(doc, e)] if r is not None]
    keys = ("area_m2", "board_m2", "sheets", "cd_m", "ud_m", "hangers", "cross_connectors", "extensions",
            "screws_25", "screws_35", "joint_tape_m", "compound_kg", "insulation_m2")
    totals = {k: round(sum(r.get(k, 0) for r in ceilings), 2) for k in keys}
    totals["wall_m2"] = round(sum(r["net_m2"] for r in walls), 2)
    return {"ceilings": ceilings, "walls": walls, "totals": totals, "provenance": PROVENANCE, "source": SOURCES}


def drywall_list(doc):
    """Priced-list rows (description, unit, quantity) for the «Γυψοσανίδες» sheet."""
    r = take_off_drywall(doc)
    counts = {}

    def add(desc, unit, qty):
        if qty:
            counts[(desc, unit)] = counts.get((desc, unit), 0) + qty

    for c in r["ceilings"]:
        add(f"Ψευδοροφή — {BOARDS[c['board']][0]}", "m²", c["board_m2"])
        add("Προφίλ CD 60/27 (κύριοι + δευτερεύοντες)", "m", c["cd_m"])
        add("Προφίλ UD 28/27 (περιμετρικός οδηγός)", "m", c["ud_m"])
        add("Βύσμα/στήριγμα UD στον τοίχο", "τεμ.", c["ud_fixings"])
        add("Αναρτήρας " + ("απευθείας (ως 12,5 cm)" if c["hanger_type"] == "direct" else "ρυθμιζόμενος (nonius/ράβδος)"),
            "τεμ.", c["hangers"])
        add("Βύσμα οροφής για αναρτήρα", "τεμ.", c["anchors"])
        add("Σύνδεσμος διασταύρωσης CD", "τεμ.", c["cross_connectors"])
        add("Σύνδεσμος προέκτασης CD", "τεμ.", c["extensions"])
        add("Βίδες γυψοσανίδας 3,5×25", "τεμ.", c["screws_25"])
        add("Βίδες γυψοσανίδας 3,5×35", "τεμ.", c["screws_35"])
        add("Ταινία αρμών", "m", c["joint_tape_m"])
        add("Ταινία διαχωρισμού περιμετρικά", "m", c["edge_tape_m"])
        add("Στόκος αρμών", "kg", c["compound_kg"])
        if c["insulation_m2"]:
            add(f"Ορυκτοβάμβακας {c['insulation_m'] * 100:.0f} cm (ψευδοροφή)", "m²", c["insulation_m2"])
        if c["cove"]:
            add("Γωνιόκρανο ακμών σκαλιού", "m", round(2 * c["cove_m"], 2))
            add("Ταινία LED κρυφού φωτισμού (προαιρετικό)", "m", c["cove_m"])
        add("Εργασία ψευδοροφής γυψοσανίδας", "m²", c["area_m2"])
    for w in r["walls"]:
        add("Τοίχος γυψοσανίδας — " + ("απλή σανίδα ανά όψη" if w["per_face"] == 1 else "διπλή σανίδα ανά όψη")
            + " (γυψοσανίδα 12,5 mm)", "m²", w["board_m2"])
        add("Ορθοστάτης CW 75", "m", w["cw_m"])
        add("Οδηγός UW 75", "m", w["uw_m"])
        add("Βύσμα στερέωσης UW (δάπεδο/οροφή)", "τεμ.", w["uw_fixings"])
        add("Βίδες γυψοσανίδας 3,5×25", "τεμ.", w["screws_25"])
        add("Βίδες γυψοσανίδας 3,5×35", "τεμ.", w["screws_35"])
        add("Ταινία αρμών", "m", w["joint_tape_m"])
        add("Στόκος αρμών", "kg", w["compound_kg"])
        add("Ορυκτοβάμβακας 7,5 cm (τοίχοι)", "m²", w["insulation_m2"])
        add("Εργασία τοίχου γυψοσανίδας", "m²", w["net_m2"])
    return [(d, u, round(q, 2) if isinstance(q, float) else q) for (d, u), q in counts.items()]


def drywall_html(result):
    if not result["ceilings"] and not result["walls"]:
        return ("<h2>Γυψοσανίδες</h2><p>Δεν υπάρχουν ψευδοροφές ή τοίχοι γυψοσανίδας. Κατασκευή → Ψευδοροφή γυψοσανίδας "
                "(κλικ σε χώρο ή σχεδίαση), ή τύπος τοίχου «Γυψοσανίδα».</p>")
    rows = "".join(
        f"<tr><td>{c['name']}</td><td>+{c['z']:.2f}</td><td>{BOARDS[c['board']][0]}{' ×2' if c['layers'] == 2 else ''}</td>"
        f"<td>{c['area_m2']}</td><td>Ψ/Ο +{c['level_m']:.2f}</td><td>{c['cd_m']}</td><td>{c['ud_m']}</td>"
        f"<td>{c['hangers']}</td><td>{c['cross_connectors']}</td><td>{c['sheets']}</td><td>{c['screws_25'] + c['screws_35']}</td></tr>"
        for c in result["ceilings"])
    walls = "".join(
        f"<tr><td>{w['name']}</td><td>+{w['z']:.2f}</td><td>{w['length_m']}×{w['height_m']}</td><td>{w['net_m2']}</td>"
        f"<td>{w['studs']}</td><td>{w['cw_m']}</td><td>{w['uw_m']}</td><td>{w['board_m2']}</td></tr>" for w in result["walls"])
    out = "<h2>Γυψοσανίδες — αναγωγή υλικών</h2>"
    if rows:
        out += ("<h3>Ψευδοροφές</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Ψευδοροφή</th><th>Στάθμη</th>"
                "<th>Σανίδα</th><th>m²</th><th>Ύψος</th><th>CD m</th><th>UD m</th><th>Αναρτήσεις</th><th>Διασταυρώσεις</th>"
                "<th>Φύλλα 1,20×2,00</th><th>Βίδες</th></tr>" + rows + "</table>")
    if walls:
        out += ("<h3>Τοίχοι γυψοσανίδας (CW/UW 75)</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Τοίχος</th>"
                "<th>Στάθμη</th><th>Μήκος×Ύψος</th><th>Καθαρό m²</th><th>Ορθοστάτες</th><th>CW m</th><th>UW m</th>"
                "<th>Σανίδα m²</th></tr>" + walls + "</table>")
    return out + f"<p><i>{PROVENANCE}<br>Πηγές: {SOURCES}</i></p>"
