"""«Γραμμή ντουλαπιών»: a wall (or a stretch of it) filled with standard cabinets.

The user points at a wall face with the mouse (one click + double click =
the whole face, or two clicks = the stretch between them).  The run is cut
at doors, at windows lower than the worktop and at whatever already stands
there, then each piece is filled with base cabinets of standard widths; the
few centimetres a set of standard widths cannot cover go into ONE filler
strip (συμπλήρωμα) at the corner end, never an empty or random gap.  Sink
and hob go where the user says (default: sink under the window), wall units
go over the base run except in front of windows, over the hob and across
doors.  At a corner with an existing run the corner is solved with a blind
corner unit (or a 90×90 L unit), so no cabinet is ever left without access.

What is stored (the Document) are only ordinary ``cabinet`` entities, each
carrying plain parameters so the run can be recognised and re-flowed:

* ``run_id``   — the run it belongs to;
* ``run_seg``  — the straight piece it fills: frame (``a``, ``u``, ``n``:
  start, direction, into the room), ``lo``/``hi`` along the face, ``layer``
  (base / wall), the filler end and its minimum;
* ``run_spec`` — the user's choices (wall units, cornice, worktop, corner,
  sink/hob positions) and the picked stretch, to plan it again;
* ``run_role`` — cabinet / filler / sink / hob / corner.

Worktop (πάγκος) with its cut-outs, plinth (μπάζα), top cornice (κορνίζα),
sink bowl, hob plate and hood are DERIVED from those cabinets
(``run_geometry``) for the plan and the 3D, exactly like the water pipes:
move, resize or delete a cabinet and they follow; nothing to keep in sync.

Typical values — προς έλεγχο (common European kitchen practice, not a code
requirement): EN 1116 (co-ordinating sizes of kitchen furniture), Neufert
«Bauentwurfslehre» (κεφ. Κουζίνα), NKBA Kitchen Planning Guidelines:

* standard widths 30/40/45/50/60/80/90 cm (5 cm module);
* base units 60 cm deep, carcass 72 cm on a 14 cm plinth + 4 cm worktop
  → worktop at 90 cm; worktop overhang 2 cm at the front;
* wall units 35 cm deep, 72 cm high, from 145 cm above the floor
  (≈ 55 cm over the worktop);
* filler ≥ 3 cm against a wall, ≥ 5 cm against another run (doors and
  handles clear);
* hob ≥ 40 cm of worktop from a wall/corner/end, sink ≥ 30 cm; ≥ 40 cm of
  worktop between sink and hob; hood 65 cm above the hob;
* cut-outs ≥ 5 cm from the wall and from the front edge.
"""
from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List

STANDARD_WIDTHS = (0.30, 0.40, 0.45, 0.50, 0.60, 0.80, 0.90)
MODULE = 0.05
BASE_DEPTH, BASE_HEIGHT, PLINTH = 0.60, 0.86, 0.14     # carcass 72 + plinth 14 → 86, + worktop 4 → 90
WALL_DEPTH, WALL_HEIGHT, WALL_Z = 0.35, 0.72, 1.45
WORKTOP_THICK, WORKTOP_OVERHANG = 0.04, 0.02
WALL_FILLER, RUN_FILLER = 0.03, 0.05
SINK_W, SINK_SMALL, HOB_W = 0.80, 0.60, 0.60
SINK_LANDING, HOB_LANDING, SINK_HOB = 0.30, 0.40, 0.40
CUT_MARGIN = 0.05
HOOD_ABOVE = 0.65
CORNICE_H, CORNICE_PROJ = 0.05, 0.02
PLINTH_BOARD = 0.016
BRIDGE = 0.65            # a gap up to this (appliance space, a deleted cabinet) keeps the worktop continuous
LOW_SILL = 0.92          # a window lower than this stops the base run
BLIND_W, CORNER_W = 1.10, 0.90
DOOR_MARGIN = 0.05

SOURCE = ("Τυπικές τιμές προς έλεγχο — EN 1116 (συντονισμένες διαστάσεις επίπλων κουζίνας), "
          "Neufert (Κουζίνα), οδηγίες NKBA· όχι κανονιστική απαίτηση")
RULES = (
    "Πλάτη ντουλαπιών 30/40/45/50/60/80/90 cm· ό,τι περισσεύει κλείνει με συμπλήρωμα στη γωνία",
    "Κάτω ντουλάπια 60 cm βάθος, 72 cm κουφάρι + 14 cm μπάζα· πάγκος 4 cm στα 90 cm",
    "Κρεμαστά 35 cm βάθος, 72 cm ύψος, από 145 cm· όχι μπροστά από παράθυρο ούτε πάνω από την εστία",
    "Εστία ≥ 40 cm από γωνία/άκρη, νεροχύτης ≥ 30 cm· ≥ 40 cm πάγκος ανάμεσά τους",
)
CORNERS = {"blind": "Τυφλό γωνιακό", "L": "Γωνιακό Γ 90×90"}
DEFAULTS = {"wall_units": True, "cornice": False, "sink": "auto", "hob": "auto", "corner": "blind",
            "worktop_material": "marble_thassos", "worktop_thick": WORKTOP_THICK,
            "overhang": WORKTOP_OVERHANG, "front_material": ""}
WORKTOP_MATERIALS = ("marble_thassos", "marble_dionysos", "marble_grey", "marble_black", "wood_oak", "steel_brushed")
FRONT_MATERIALS = ("", "melamine_white", "lacquer_white", "wood_oak", "wood_oak_light", "wood_walnut", "paint_aegean_blue")


def fmt_cm(v):
    return f"{v * 100:.0f}"


def fmt_m(v):
    return f"{v:.2f}".replace(".", ",") + " m"


# ------------------------------------------------------------------ the frame of a straight piece
def frame_point(frame, s, d=0.0):
    a, u, n = frame["a"], frame["u"], frame["n"]
    return (a[0] + u[0] * s + n[0] * d, a[1] + u[1] * s + n[1] * d)


def frame_coords(frame, x, y):
    a, u, n = frame["a"], frame["u"], frame["n"]
    dx, dy = x - a[0], y - a[1]
    return dx * u[0] + dy * u[1], dx * n[0] + dy * n[1]


def frame_rotation(frame):
    """Rotation (degrees) of a cabinet whose back is on the frame's face."""
    n = frame["n"]
    return math.degrees(math.atan2(n[0], -n[1])) % 360.0


def _frame_of(run):
    return {"a": [float(run.a[0]), float(run.a[1])], "u": [float(run.u[0]), float(run.u[1])],
            "n": [float(run.n[0]), float(run.n[1])]}


def _frame_key(frame):
    return tuple(round(float(v), 3) for v in (*frame["a"], *frame["u"], *frame["n"]))


# ------------------------------------------------------------------ standard widths
@lru_cache(maxsize=8)
def _combos(widths=STANDARD_WIDTHS, units=400):
    """``best[k]`` = cheapest list of standard widths summing exactly k modules (5 cm), or None.

    A 60 is the carpenter's default; every other width costs a little more,
    and every extra piece costs one, so 3,60 m becomes 6 × 60 and not 12 × 30.
    """
    cost = {w: 1.0 + abs(w - 0.60) * 3.0 for w in widths}
    steps = {w: int(round(w / MODULE)) for w in widths}
    best = [None] * (units + 1)
    best[0] = (0.0, ())
    for k in range(1, units + 1):
        pick = None
        for w in widths:
            j = k - steps[w]
            if j < 0 or best[j] is None:
                continue
            c = best[j][0] + cost[w]
            if pick is None or c < pick[0] - 1e-9:
                pick = (c, best[j][1] + (w,))
        best[k] = pick
    return best


def exact_widths(length):
    """Standard widths that fill ``length`` exactly (on the 5 cm module), or None."""
    k = int(round(length / MODULE))
    if abs(k * MODULE - length) > 1e-4 or k < 0:
        return None
    best = _combos()
    if k >= len(best) or best[k] is None:
        return None
    return sorted(best[k][1], key=lambda w: (-(w == 0.60), -w))


def fill_widths(length, min_filler=0.0):
    """``(widths, filler)``: standard widths covering as much of ``length`` as possible, the rest a filler.

    The filler is at least ``min_filler`` (when there is room for it) and
    always narrower than the smallest cabinet plus that minimum.
    """
    best = _combos()
    room = length - min_filler
    k = min(int(math.floor(room / MODULE + 1e-6)), len(best) - 1)
    while k > 0 and best[k] is None:
        k -= 1
    if k <= 0:
        return [], max(0.0, length)
    widths = sorted(best[k][1], key=lambda w: (-(w == 0.60), -w))
    return widths, max(0.0, length - k * MODULE)


def _representable(k):
    best = _combos()
    return 0 <= k < len(best) and best[k] is not None


# ------------------------------------------------------------------ packing one straight piece
@dataclass
class Piece:
    s0: float
    width: float
    role: str                       # cabinet | filler | sink | hob | corner | blind
    extra: dict = field(default_factory=dict)


def pack(lo, hi, filler_end, min_filler, fixed=(), end_pieces=None):
    """Pieces filling [lo, hi]: ``fixed`` items ``[(s_center, width, role)]`` stay close to where asked.

    Packing runs from the end opposite the filler: every gap before a fixed
    item is filled exactly with standard widths (so the fixed item moves by
    less than 5 cm), the last stretch takes the filler.  ``end_pieces``
    ``{'lo'|'hi': (role, width)}`` are corner units sitting at those ends.
    """
    end_pieces = dict(end_pieces or {})
    pieces = []
    for end, (role, w) in end_pieces.items():
        if hi - lo < w + 0.02:
            continue
        if end == "lo":
            pieces.append(Piece(lo, w, role, {"end": "lo"}))
            lo += w
        else:
            pieces.append(Piece(hi - w, w, role, {"end": "hi"}))
            hi -= w
    length = hi - lo
    if length <= 1e-6:
        return pieces

    def to_s(t, w):
        return lo + t if filler_end == "hi" else hi - t - w

    def to_t(s_center, w):
        return (s_center - w / 2 - lo) if filler_end == "hi" else (hi - s_center - w / 2)

    items = sorted(((to_t(c, w), w, role) for c, w, role in fixed), key=lambda it: it[0])
    t = 0.0
    for i, (want, w, role) in enumerate(items):
        rest = sum(x[1] for x in items[i + 1:])
        landing = SINK_LANDING if role == "sink" else HOB_LANDING
        later_landing = max([SINK_LANDING if r == "sink" else HOB_LANDING for _t, _w, r in items[i + 1:]] or [0.0])
        start_end = "lo" if filler_end == "hi" else "hi"
        lo_t = t + (landing if i == 0 and start_end not in end_pieces else 0.0)
        hi_t = length - w - rest - max(landing, later_landing) - (SINK_HOB if rest else 0.0)
        if hi_t < t - 1e-9:
            continue                                      # does not fit: left out (the caller reports it)
        best = None
        k = 0
        while t + k * MODULE <= hi_t + 1e-9:
            a = t + k * MODULE
            if a >= lo_t - 1e-9 and _representable(k) and (i == 0 or k * MODULE >= SINK_HOB - 1e-9):
                d = abs(a - want)
                if best is None or d < best[0] - 1e-9:
                    best = (d, k)
            k += 1
        if best is None:
            continue
        k = best[1]
        for wd in exact_widths(k * MODULE) or ():
            pieces.append(Piece(to_s(t, wd), wd, "cabinet"))
            t += wd
        pieces.append(Piece(to_s(t, w), w, role))
        t += w
    widths, filler = fill_widths(length - t, min_filler)
    for wd in widths:
        pieces.append(Piece(to_s(t, wd), wd, "cabinet"))
        t += wd
    if filler > 0.002:
        pieces.append(Piece(to_s(t, filler), filler, "filler"))
    return sorted(pieces, key=lambda p: p.s0)


# ------------------------------------------------------------------ what is on the wall
def _obstacle_intervals(doc, run, level, ignore, z_lo, z_hi, depth):
    """Along-run intervals ``[(s0, s1, dd_min, entity)]`` of things standing between ``z_lo`` and ``z_hi``."""
    from archforge.assistant.room_layout import footprint_of
    out = []
    for e in doc.entities.values():
        if e.id in ignore or e.kind not in ("cabinet", "library_object", "box", "structural_column"):
            continue
        p = e.params
        z = float(p.get("z", 0.0)) - level
        h = float(p.get("height", 0.86))
        if z >= z_hi or z + h <= z_lo or z < -0.05 or z > 2.6:
            continue
        poly = footprint_of(e)
        if not poly:
            continue
        ss = [(x - run.a[0]) * run.u[0] + (y - run.a[1]) * run.u[1] for x, y in poly]
        dd = [(x - run.a[0]) * run.n[0] + (y - run.a[1]) * run.n[1] for x, y in poly]
        if min(dd) >= depth or max(dd) <= 0.0 or max(ss) <= 0.0 or min(ss) >= run.length:
            continue
        out.append((min(ss), max(ss), min(dd), e))
    return out


def _subtract(lo, hi, cuts, min_len=0.0):
    from archforge.assistant.room_layout import subtract
    return subtract([(lo, hi)], cuts, min_len)


def _end_kind(s, run, cuts_typed):
    """What stops a piece at ``s``: 'wall' (a corner of the room), 'run' (other cabinets) or 'free'."""
    if s <= 0.005 or s >= run.length - 0.005:
        return "wall"
    for c0, c1, kind in cuts_typed:
        if abs(s - c0) < 0.005 or abs(s - c1) < 0.005:
            return kind
    return "free"


def _filler_end(lo_kind, hi_kind):
    """The filler goes to the end against other cabinets, else against a wall, else the far end."""
    for kind in ("run", "wall"):
        if hi_kind == kind:
            return "hi"
        if lo_kind == kind:
            return "lo"
    return "hi"


def _min_filler(kind):
    return {"run": RUN_FILLER, "wall": WALL_FILLER}.get(kind, 0.0)


# ------------------------------------------------------------------ picking a wall
def runs_at(doc, x, y, z=None):
    """``(runs, room)`` of the room under (x, y), or of the single wall face near it (no room)."""
    from archforge.assistant.room_walls import room_runs
    from archforge.assistant.suggestions import room_at
    level = float(doc.work_plane.origin[2]) if z is None else float(z)
    room = room_at(doc, x, y, level)
    if room is not None:
        return room_runs(doc, room, level), room
    wall = wall_run(doc, x, y, level)
    return ([wall] if wall else []), None


def wall_run(doc, x, y, level, tolerance=0.6):
    """A run on the face of the wall nearest (x, y), on the side of the point (open plans, no room)."""
    from archforge.assistant.room_walls import Run, _openings
    best = None
    for e in doc.entities.values():
        if e.kind != "wall" or abs(float(e.params.get("z", 0.0)) - level) > 0.05:
            continue
        p = e.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 0.3:
            continue
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        t = max(0.0, min(L, (x - x1) * ux + (y - y1) * uy))
        d = (x - x1) * -uy + (y - y1) * ux
        dist = math.hypot(x - (x1 + ux * t), y - (y1 + uy * t))
        if dist > tolerance + float(p.get("thickness", 0.2)) / 2 or (best and dist >= best[0]):
            continue
        best = (dist, e, x1, y1, x2, y2, ux, uy, L, 1.0 if d >= 0 else -1.0)
    if best is None:
        return None
    _d, e, x1, y1, x2, y2, ux, uy, L, side = best
    half = float(e.params.get("thickness", 0.2)) / 2
    nx, ny = -uy * side, ux * side
    if side > 0:
        a, u = (x1 + nx * half, y1 + ny * half), (ux, uy)
    else:
        # Keep the room on the left of u (n = left normal): walk the face the other way.
        a, u = (x2 + nx * half, y2 + ny * half), (-ux, -uy)
    run = Run(0, a, (a[0] + u[0] * L, a[1] + u[1] * L), u, (nx, ny), L, 2 * half, (e.id,))
    run.openings = _openings(doc, run)
    return run


def snap(runs, x, y):
    """``(run index, s, (px, py))`` of the face point under the cursor, or None."""
    from archforge.assistant.room_walls import snap_point
    return snap_point(runs, x, y)


# ------------------------------------------------------------------ the proposal
@dataclass
class RunProposal:
    entities: list
    label: str
    notes: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)
    replace_ids: List[str] = field(default_factory=list)   # a neighbouring run planned again (blind corner)
    run_id: str = ""
    spec: dict = field(default_factory=dict)
    segments: list = field(default_factory=list)            # [(frame, lo, hi, layer)] for the ghost

    def command(self):
        from archforge.core.commands import AddEntities, CompositeCommand, DeleteEntities
        add = AddEntities([e.clone() for e in self.entities])
        if self.replace_ids:
            return CompositeCommand([DeleteEntities(list(self.replace_ids)), add], label="Γραμμή ντουλαπιών")
        return CompositeCommand([add], label="Γραμμή ντουλαπιών")


def _cabinet(frame, piece, depth, level, z, cabinet_type, role, run_id, seg, spec, name=None, **extra):
    from archforge.core.model import Entity
    from archforge.kitchen.cabinets import TYPES, auto_doors, default_params
    p = default_params(cabinet_type, width=piece.width)
    p.update(depth=depth, own_plinth=0, worktop=0.0)
    if cabinet_type == "wall":
        p.update(height=WALL_HEIGHT, plinth=0.0)
    elif cabinet_type != "corner":
        p.update(height=BASE_HEIGHT, plinth=PLINTH)
    else:
        p.update(height=BASE_HEIGHT, plinth=PLINTH, own_plinth=1)
    if cabinet_type == "filler":
        p.update(height=WALL_HEIGHT if seg["layer"] == "wall" else BASE_HEIGHT,
                 plinth=0.0 if seg["layer"] == "wall" else PLINTH)
    p.update(extra)
    if p.get("doors"):
        p["doors"] = auto_doors(cabinet_type, piece.width)
    if cabinet_type == "corner":
        # Its back leg runs along this face, the side leg along the next wall (local -X = the run's end).
        x, y = frame_point(frame, piece.s0 + piece.width / 2, float(p["depth"]) / 2)
    else:
        x, y = frame_point(frame, piece.s0 + piece.width / 2, depth / 2)
    p.update(x=x, y=y, z=float(level) + float(z), rotation=frame_rotation(frame),
             run_id=run_id, run_seg=copy.deepcopy(seg), run_spec=copy.deepcopy(spec), run_role=role,
             layout_role={"sink": "sink", "hob": "hob_base"}.get(role, "base" if seg["layer"] == "base" else "wall"))
    if spec.get("front_material"):
        p["surface_materials"] = {"front": spec["front_material"]}
    return Entity("cabinet", p, name=name or TYPES[cabinet_type][0])


def _neighbour_corner(doc, runs, run, end, level, ignore):
    """Other cabinets at the corner at ``end`` ('lo' / 'hi') of ``run``: ``(dd_min, entity)`` or None."""
    s_end = 0.0 if end == "lo" else run.length
    found = None
    for s0, s1, dd, e in _obstacle_intervals(doc, run, level, ignore, 0.05, 1.0, 1.4):
        # The neighbour stands along the OTHER wall: its back is on that wall's face (our end).
        near = s0 <= s_end + 0.05 if end == "lo" else s1 >= s_end - 0.05
        if not near or e.kind != "cabinet":
            continue
        turn = (float(e.params.get("rotation", 0.0)) - run.rotation + 180.0) % 360.0 - 180.0
        if abs(turn) < 1.0:
            continue                                          # on this same wall
        if found is None or dd < found[0]:
            found = (dd, e)
    return found


def plan_run(doc, x0, y0, x1=None, y1=None, options=None, *, run_id=None, ignore=(), z=None):
    """Proposal for the run picked at (x0, y0) [→ (x1, y1) on the same face]; None for both = whole face."""
    level = float(doc.work_plane.origin[2]) if z is None else float(z)
    runs, room = runs_at(doc, x0, y0, level)
    hit = snap(runs, x0, y0) if runs else None
    if hit is None:
        return RunProposal([], "Γραμμή ντουλαπιών — δεν βρέθηκε τοίχος",
                           problems=["Κλικ πάνω στην εσωτερική παρειά ενός τοίχου"])
    i, s_a, _xy = hit
    run = runs[i]
    lo, hi = 0.0, run.length
    if x1 is not None:
        hit2 = snap([r if r.index == i else _NoRun for r in runs], x1, y1)
        if hit2 and hit2[0] == i and abs(hit2[1] - s_a) >= 0.30:
            lo, hi = sorted((s_a, hit2[1]))
    return _plan(doc, runs, room, i, lo, hi, options, run_id=run_id, ignore=ignore, level=level)


def _has_role(doc, room, level, role, ignore):
    """A sink / hob already in this room (another run or the assistant's kitchen)."""
    from archforge.assistant.understanding import inside
    roles = {"sink": ("sink",), "hob": ("hob", "hob_base")}[role]
    for e in doc.entities.values():
        p = e.params
        if e.id in ignore or e.kind != "cabinet" or abs(float(p.get("z", 0.0)) - level) > 0.3:
            continue
        if p.get("run_role") in roles or p.get("layout_role") in roles:
            if room is None or inside(room["polygon"], float(p["x"]), float(p["y"])):
                return True
    return False


def _plan(doc, runs, room, i, lo, hi, options=None, *, run_id=None, ignore=(), level=0.0, _neighbours=True):
    opts = dict(DEFAULTS)
    opts.update({k: v for k, v in (options or {}).items() if v is not None or k in ("sink_xy", "hob_xy")})
    run = runs[i]
    run_id = run_id or uuid.uuid4().hex[:12]
    ignore = set(ignore)
    frame = _frame_of(run)
    for role in ("sink", "hob"):
        if opts.get(role) == "auto":
            # One sink and one hob per kitchen: the second wall of an L does not get another one.
            opts[role] = not _has_role(doc, room, level, role, ignore)
    spec = {k: opts[k] for k in DEFAULTS}
    spec.update(pick={"point": [float(v) for v in run.point((lo + hi) / 2, 0.3)], "wall_id": run.wall_ids[0] if run.wall_ids else "",
                      "u": [float(run.u[0]), float(run.u[1])], "lo": float(lo), "hi": float(hi)},
                level=level, sink_xy=opts.get("sink_xy"), hob_xy=opts.get("hob_xy"),
                end_override=opts.get("end_override") or {})
    notes, problems, ents, segments = [], [], [], []
    replace = []

    # ---------------------------------------------------------- base run: doors, low windows, things in the way
    typed = []
    for o in run.doors():
        typed.append((o.s0 - DOOR_MARGIN, o.s1 + DOOR_MARGIN, "free"))
    for o in run.windows():
        if o.sill < LOW_SILL:
            typed.append((o.s0, o.s1, "free"))
    for s0, s1, dd, e in _obstacle_intervals(doc, run, level, ignore, 0.05, 1.0, BASE_DEPTH - 0.03):
        typed.append((s0, s1, "run" if e.kind == "cabinet" else "free"))
    pieces_base = _subtract(lo, hi, [(c0, c1) for c0, c1, _k in typed], 0.15)
    if not pieces_base:
        problems.append("Δεν μένει ελεύθερος τοίχος για ντουλάπια (πόρτες / παράθυρα / άλλα ντουλάπια)")

    # Corners: an existing run at a corner → blind unit (or L) here, or re-plan the neighbour.
    end_pieces = {}
    overrides = dict(spec.get("end_override") or {})
    for end in ("lo", "hi"):
        s_end = 0.0 if end == "lo" else run.length
        if abs((lo if end == "lo" else hi) - s_end) > 0.005:
            continue
        if end in overrides:
            end_pieces[end] = overrides[end]
            continue
        nb = _neighbour_corner(doc, runs, run, end, level, ignore) if len(runs) > 1 else None
        if nb is None:
            if spec["corner"] == "L" and end == "hi" and len(runs) > 1 and room is not None:
                end_pieces[end] = ("corner", CORNER_W)
            continue
        dd, e = nb
        if dd >= BASE_DEPTH - 0.05:
            # The corner square is free and the other run starts beside it: our unit takes the corner.
            if spec["corner"] == "L" and end == "hi" and dd >= CORNER_W - 0.02:
                end_pieces[end] = ("corner", CORNER_W)
            else:
                end_pieces[end] = ("blind", BLIND_W)
                if dd > BASE_DEPTH + 0.10:
                    problems.append(f"Γωνία: το τυφλό γωνιακό μένει ακάλυπτο {fmt_cm(dd - BASE_DEPTH)} cm — "
                                    "μάζεψε τη διπλανή γραμμή ή βάλε συμπλήρωμα")
        elif _neighbours and e.params.get("run_id") and e.params.get("cabinet_type") not in ("corner", "corner_blind") \
                and e.params.get("run_id") != run_id:
            # The other run fills the corner square with a plain cabinet (a dead corner): plan it again
            # with a blind unit there; this run starts beside it with a filler.
            other = _replan_neighbour(doc, e.params["run_id"], e, ignore | {x.id for x in ents})
            if other is not None:
                replace += other[0]
                ents += other[1]
                before = {doc.get(x).params.get("run_role") for x in other[0]}
                after = {x.params.get("run_role") for x in other[1]}
                for role in ("sink", "hob"):
                    if role in before and role not in after and (options or {}).get(role, DEFAULTS[role]) == "auto":
                        spec[role] = True          # the corner took its place there: it comes to this wall
                notes.append("Γωνία με την υπάρχουσα γραμμή: τυφλό γωνιακό εκεί + συμπλήρωμα 5 cm εδώ")

    sink_xy, hob_xy = spec.get("sink_xy"), spec.get("hob_xy")
    want = []
    if spec["sink"]:
        if sink_xy:
            s_sink = frame_coords(frame, *sink_xy)[0]
        else:
            wins = [o for o in run.windows() if o.sill >= LOW_SILL and lo <= (o.s0 + o.s1) / 2 <= hi]
            s_sink = (wins[0].s0 + wins[0].s1) / 2 if wins else None
        want.append(["sink", s_sink])
    if spec["hob"]:
        want.append(["hob", frame_coords(frame, *hob_xy)[0] if hob_xy else None])

    base_pieces = []
    for p0, p1 in pieces_base:
        lo_kind, hi_kind = _end_kind(p0, run, typed), _end_kind(p1, run, typed)
        fend = _filler_end(lo_kind, hi_kind)
        mine = {k: v for k, v in end_pieces.items() if abs((p0 if k == "lo" else p1) - (lo if k == "lo" else hi)) < 1e-6}
        if fend in mine and mine[fend][0] == "blind":
            # A blind unit carries its own 5 cm filler: put the run's filler at the other end.
            fend = "hi" if fend == "lo" else "lo"
        fkind = hi_kind if fend == "hi" else lo_kind
        base_pieces.append([p0, p1, fend, _min_filler(fkind), mine])
    _place_fixed(run, base_pieces, want, problems)

    for p0, p1, fend, minf, mine, fixed in base_pieces:
        seg = {"frame": frame, "lo": p0, "hi": p1, "layer": "base", "filler_end": fend, "min_filler": minf,
               "level": level}
        segments.append((frame, p0, p1, "base"))
        for pc in pack(p0, p1, fend, minf, fixed, {k: v for k, v in mine.items()}):
            if pc.role == "sink":
                ents.append(_cabinet(frame, pc, BASE_DEPTH, level, 0.0, "sink", "sink", run_id, seg, spec,
                                     name="Ντουλάπι νεροχύτη"))
            elif pc.role == "hob":
                ents.append(_cabinet(frame, pc, BASE_DEPTH, level, 0.0, "drawers", "hob", run_id, seg, spec,
                                     name="Ντουλάπι εστίας (συρτάρια)"))
            elif pc.role == "filler":
                ents.append(_cabinet(frame, pc, BASE_DEPTH, level, 0.0, "filler", "filler", run_id, seg, spec))
            elif pc.role == "blind":
                ents.append(_cabinet(frame, pc, BASE_DEPTH, level, 0.0, "corner_blind", "corner", run_id, seg, spec,
                                     blind_side="left" if pc.extra.get("end") == "hi" else "right"))
            elif pc.role == "corner":
                ents.append(_cabinet(frame, pc, CORNER_W, level, 0.0, "corner", "corner", run_id, seg, spec))
            else:
                ents.append(_cabinet(frame, pc, BASE_DEPTH, level, 0.0, "base", "cabinet", run_id, seg, spec))

    # ---------------------------------------------------------- wall units
    hob_iv = [_iv(e, frame) for e in ents if e.params.get("run_role") == "hob" and e.params.get("run_id") == run_id]
    if spec["wall_units"] and pieces_base:
        typed_w = []
        for o in run.openings:
            if o.top > WALL_Z + 0.02 and o.sill < WALL_Z + WALL_HEIGHT:
                typed_w.append((o.s0 - 0.05, o.s1 + 0.05, "free"))
        for s0, s1, dd, e in _obstacle_intervals(doc, run, level, ignore | set(replace), WALL_Z, WALL_Z + WALL_HEIGHT,
                                                 WALL_DEPTH - 0.02):
            typed_w.append((s0, s1, "run" if e.kind == "cabinet" else "free"))
        from archforge.kitchen.cabinets import footprint
        for e in ents:
            if e.params.get("run_id") != run_id and (e.params.get("run_seg") or {}).get("layer") == "wall":
                st = [frame_coords(frame, x, y) for x, y in footprint(e.params)]
                if min(d for _s, d in st) < WALL_DEPTH - 0.02 and max(d for _s, d in st) > 0.0:
                    s0, s1 = min(x for x, _d in st), max(x for x, _d in st)
                    if s1 > 0 and s0 < run.length:
                        typed_w.append((s0, s1, "run"))
        for s0, s1 in hob_iv:
            typed_w.append((s0, s1, "free"))
        # Only over the base run (and the corner units), never over a door or a gap.
        spans = []
        for e in ents:
            if e.params.get("run_id") == run_id and e.params["run_seg"]["layer"] == "base":
                spans.append(_iv(e, frame))
        spans = _merge(spans, 0.005)
        # Beside another run at a corner the wall units go on into the corner (up to its wall units).
        spans = [(lo if a0 - lo <= BASE_DEPTH + 0.1 and _end_kind(a0, run, typed) == "run" else a0,
                  hi if hi - a1 <= BASE_DEPTH + 0.1 and _end_kind(a1, run, typed) == "run" else a1) for a0, a1 in spans]
        wall_pieces = []
        for a0, a1 in spans:
            for p0, p1 in _subtract(a0, a1, [(c0, c1) for c0, c1, _k in typed_w], 0.0):
                if p1 - p0 < 0.30 - 1e-6:
                    if p1 - p0 > 0.02:
                        problems.append(f"Κρεμαστά: κομμάτι {fmt_cm(p1 - p0)} cm έμεινε ελεύθερο (μικρότερο από 30)")
                    continue
                wall_pieces.append((p0, p1))
        for p0, p1 in wall_pieces:
            lo_kind = _end_kind(p0, run, typed_w + [(a0, a1, "free") for a0, a1 in spans])
            hi_kind = _end_kind(p1, run, typed_w + [(a0, a1, "free") for a0, a1 in spans])
            fend = _filler_end(lo_kind, hi_kind)
            minf = _min_filler(hi_kind if fend == "hi" else lo_kind)
            seg = {"frame": frame, "lo": p0, "hi": p1, "layer": "wall", "filler_end": fend, "min_filler": minf,
                   "level": level}
            segments.append((frame, p0, p1, "wall"))
            for pc in pack(p0, p1, fend, minf):
                kind = "filler" if pc.role == "filler" else "wall"
                ents.append(_cabinet(frame, pc, WALL_DEPTH, level, WALL_Z, kind, pc.role, run_id, seg, spec))
    # Every cabinet's z: base on the floor, wall units at WALL_Z.
    for e in ents:
        if e.params.get("run_id") == run_id and e.params["run_seg"]["layer"] == "wall":
            e.params["z"] = level + WALL_Z
    # Record where sink and hob ended up, so a re-plan keeps them.
    for e in ents:
        if e.params.get("run_id") != run_id:
            continue
        role = e.params.get("run_role")
        if role in ("sink", "hob"):
            for f in ents:
                if f.params.get("run_id") == run_id:
                    f.params["run_spec"][role + "_xy"] = [float(e.params["x"]), float(e.params["y"])]
    mine = [e for e in ents if e.params.get("run_id") == run_id]
    n_base = sum(1 for e in mine if e.params["run_seg"]["layer"] == "base" and e.params["cabinet_type"] != "filler")
    n_wall = sum(1 for e in mine if e.params["cabinet_type"] == "wall")
    fillers = [e for e in mine if e.params["cabinet_type"] == "filler"]
    roles = {e.params.get("run_role") for e in mine}
    if spec["sink"] and "sink" not in roles:
        problems.append("Ο νεροχύτης δεν χωράει με τις αποστάσεις (≥ 30 cm από άκρη/γωνία)")
    if spec["hob"] and "hob" not in roles:
        problems.append("Η εστία δεν χωράει με τις αποστάσεις (≥ 40 cm από άκρη/γωνία, ≥ 40 cm από τον νεροχύτη)")
    worktop = sum(p1 - p0 for p0, p1 in pieces_base)
    notes.insert(0, f"Πάγκος ≈ {fmt_m(worktop)} · {n_base} κάτω ντουλάπια, {n_wall} κρεμαστά"
                 + (f" · συμπληρώματα {', '.join(fmt_cm(float(f.params['width'])) for f in fillers)} cm" if fillers else ""))
    for e in mine:
        if e.params.get("run_role") == "sink":
            s = frame_coords(frame, float(e.params["x"]), float(e.params["y"]))[0]
            if any(o.s0 - 0.05 <= s <= o.s1 + 0.05 for o in run.windows() if o.sill >= LOW_SILL):
                notes.append("Νεροχύτης κάτω από το παράθυρο ✓")
    notes += list(RULES)
    label = f"Γραμμή ντουλαπιών {fmt_m(hi - lo)}"
    prop = RunProposal(ents, label, notes=notes, problems=problems, replace_ids=replace, run_id=run_id, spec=spec,
                       segments=segments)
    return prop


class _NoRunType:
    length, thickness, index = 0.0, 0.0, -1


_NoRun = _NoRunType()


def _iv(e, frame):
    p = e.params
    s = frame_coords(frame, float(p["x"]), float(p["y"]))[0]
    w = float(p["width"])
    if p.get("cabinet_type") == "corner":
        # Footprint along the face = its width; the centre sits half a width back.
        return s - w / 2, s + w / 2
    return s - w / 2, s + w / 2


def _merge(spans, gap):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + gap:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _place_fixed(run, base_pieces, want, problems):
    """Assign the sink and hob to straight pieces: ``fixed`` lists ``[(s_center, width, role)]``."""
    for bp in base_pieces:
        bp.append([])
    usable = [bp for bp in base_pieces if bp[1] - bp[0] >= 0.30]
    if not usable:
        return

    def room_for(bp, w, landing):
        p0, p1, fend, minf, mine, fixed = bp
        used = sum(v[1] for v in mine.values()) + sum(f[1] for f in fixed)
        return (p1 - p0) - used - w - 2 * landing - (SINK_HOB if fixed else 0.0) >= -1e-6

    def clamp(bp, c, w, landing):
        p0, p1, _f, _m, mine, _x = bp
        # A corner unit at an end is worktop too: no extra landing needed there.
        a = p0 + (mine["lo"][1] if "lo" in mine else landing)
        b = p1 - (mine["hi"][1] if "hi" in mine else landing)
        return min(max(c, a + w / 2), b - w / 2)

    sink = next((w for w in want if w[0] == "sink"), None)
    hob = next((w for w in want if w[0] == "hob"), None)
    sink_at = None
    if sink is not None:
        width = SINK_W
        cands = [bp for bp in usable if room_for(bp, width, SINK_LANDING)]
        if not cands:
            width = SINK_SMALL
            cands = [bp for bp in usable if room_for(bp, width, SINK_LANDING)]
        if cands:
            if sink[1] is None:
                bp = max(cands, key=lambda b: b[1] - b[0])
                c = bp[0] + (bp[1] - bp[0]) * 0.35
            else:
                bp = min(cands, key=lambda b: 0.0 if b[0] <= sink[1] <= b[1] else min(abs(sink[1] - b[0]), abs(sink[1] - b[1])))
                c = sink[1]
            c = clamp(bp, c, width, SINK_LANDING)
            bp[5].append((c, width, "sink"))
            sink_at = (bp, c, width)
    if hob is not None:
        cands = [bp for bp in usable if room_for(bp, HOB_W, HOB_LANDING)]
        if cands:
            if hob[1] is not None:
                bp = min(cands, key=lambda b: 0.0 if b[0] <= hob[1] <= b[1] else min(abs(hob[1] - b[0]), abs(hob[1] - b[1])))
                c = clamp(bp, hob[1], HOB_W, HOB_LANDING)
            else:
                # Best spot: about 90 cm of worktop from the sink, not under a window, landing on both sides.
                best = None
                for b in cands:
                    a0 = clamp(b, b[0], HOB_W, HOB_LANDING)
                    a1 = clamp(b, b[1], HOB_W, HOB_LANDING)
                    c = a0
                    while c <= a1 + 1e-9:
                        score = 0.0
                        if sink_at is not None and sink_at[0] is b:
                            gap = abs(c - sink_at[1]) - (HOB_W + sink_at[2]) / 2
                            if gap < SINK_HOB - 1e-6:
                                c += MODULE
                                continue
                            score += abs(gap - 0.90)
                        elif sink_at is not None:
                            score += 0.5
                        if any(o.s0 - 0.05 <= c <= o.s1 + 0.05 for o in run.windows()):
                            score += 3.0
                        if best is None or score < best[0] - 1e-9:
                            best = (score, b, c)
                        c += MODULE
                if best is None:
                    return
                _s, bp, c = best
            if sink_at is not None and sink_at[0] is bp:
                gap = abs(c - sink_at[1]) - (HOB_W + sink_at[2]) / 2
                if gap < SINK_HOB - 1e-6:
                    side = 1.0 if c >= sink_at[1] else -1.0
                    c = sink_at[1] + side * ((HOB_W + sink_at[2]) / 2 + SINK_HOB)
                    c = clamp(bp, c, HOB_W, HOB_LANDING)
                    if abs(c - sink_at[1]) - (HOB_W + sink_at[2]) / 2 < SINK_HOB - 1e-6:
                        return
            bp[5].append((c, HOB_W, "hob"))


def replan(doc, spec, options=None, *, run_id=None, ignore=(), neighbours=True):
    """The run of a stored ``run_spec`` planned again on the (current) walls, or None."""
    pick = spec.get("pick") or {}
    if not isinstance(pick, dict) or not pick.get("point"):
        return None
    level = float(spec.get("level", doc.work_plane.origin[2]))
    runs, room = runs_at(doc, *pick["point"], level)
    i = next((r.index for r in runs if pick.get("wall_id") in r.wall_ids
              and r.u[0] * pick["u"][0] + r.u[1] * pick["u"][1] > 0.99), None)
    if i is None:
        return None
    lo, hi = max(0.0, float(pick["lo"])), min(runs[i].length, float(pick["hi"]))
    opts = {k: spec[k] for k in DEFAULTS if k in spec}
    opts.update(options or {})
    return _plan(doc, runs, room, i, lo, hi, opts, run_id=run_id, ignore=ignore, level=level, _neighbours=neighbours)


def _replan_neighbour(doc, run_id, corner_entity, ignore):
    """The neighbouring run planned again with a blind unit at the corner it shares: ``(old ids, new entities)``."""
    old = [e for e in doc.entities.values() if e.params.get("run_id") == run_id]
    if not old:
        return None
    spec = dict(old[0].params.get("run_spec") or {})
    seg = corner_entity.params.get("run_seg") or {}
    frame = seg.get("frame")
    if not frame or not spec.get("pick"):
        return None
    s = frame_coords(frame, float(corner_entity.params["x"]), float(corner_entity.params["y"]))[0]
    end = "lo" if abs(s - float(seg["lo"])) < abs(s - float(seg["hi"])) else "hi"
    options = {k: spec[k] for k in DEFAULTS if k in spec}
    options.update(sink_xy=spec.get("sink_xy"), hob_xy=spec.get("hob_xy"),
                   end_override=dict(spec.get("end_override") or {}, **{end: ("blind", BLIND_W)}))
    prop = replan(doc, spec, options, run_id=run_id, ignore=set(ignore) | {e.id for e in old}, neighbours=False)
    if prop is None:
        return None
    if not prop.entities:
        return None
    return [e.id for e in old], prop.entities


# ------------------------------------------------------------------ editing an applied run
def run_members(doc, run_id):
    return [e for e in doc.entities.values() if e.kind == "cabinet" and run_id and e.params.get("run_id") == run_id]


def same_segment(a, b):
    sa, sb = a.get("run_seg") or {}, b.get("run_seg") or {}
    return (sa.get("layer") == sb.get("layer") and abs(float(sa.get("lo", 0)) - float(sb.get("lo", 0))) < 1e-6
            and abs(float(sa.get("hi", 0)) - float(sb.get("hi", 0))) < 1e-6
            and _frame_key(sa.get("frame") or {"a": [0, 0], "u": [0, 0], "n": [0, 0]})
            == _frame_key(sb.get("frame") or {"a": [0, 0], "u": [0, 0], "n": [0, 0]}))


def reflow_width(doc, entity_id, width):
    """Command: cabinet ``entity_id`` gets ``width``; its straight piece re-flows (filler absorbs the change).

    The other cabinets keep their order and widths; if the piece gets too
    long, the widest ordinary cabinets step down to the next standard width;
    if a gap of a whole cabinet opens, a cabinet is added.  One undo.
    """
    from archforge.core.commands import AddEntities, CompositeCommand, DeleteEntities, UpdateEntities
    from archforge.kitchen.cabinets import auto_doors
    target = doc.get(entity_id)
    p = target.params
    seg = p.get("run_seg")
    if not p.get("run_id") or not seg:
        raise ValueError("το ντουλάπι δεν ανήκει σε γραμμή ντουλαπιών")
    if p.get("cabinet_type") == "filler" or p.get("run_role") == "corner":
        raise ValueError("το συμπλήρωμα και τα γωνιακά προσαρμόζονται μόνα τους — άλλαξε ένα διπλανό ντουλάπι")
    width = round(float(width), 4)
    if width < 0.15:
        raise ValueError("πολύ στενό ντουλάπι")
    frame, lo, hi = seg["frame"], float(seg["lo"]), float(seg["hi"])
    fend, minf = seg.get("filler_end", "hi"), float(seg.get("min_filler", 0.0))
    group = [e for e in run_members(doc, p["run_id"]) if same_segment(e.params, p)]
    group.sort(key=lambda e: _iv(e, frame)[0], reverse=(fend == "lo"))
    keep = [e for e in group if e.params["cabinet_type"] != "filler"]
    widths = {e.id: float(e.params["width"]) for e in keep}
    widths[entity_id] = width
    # Corner units stay at their end; the rest pack from the non-filler end.
    ends = [e for e in keep if e.params.get("run_role") == "corner"]
    order = [e for e in keep if e not in ends]
    corner_len = sum(widths[e.id] for e in ends)
    room = (hi - lo) - corner_len
    over = sum(widths[e.id] for e in order) + minf - room
    if over > 1e-6:
        shrinkable = sorted((e for e in order if e.id != entity_id and e.params.get("run_role") == "cabinet"),
                            key=lambda e: -widths[e.id])
        for e in shrinkable * 6:
            if over <= 1e-6:
                break
            smaller = [w for w in STANDARD_WIDTHS if w < widths[e.id] - 1e-6]
            if not smaller:
                continue
            over -= widths[e.id] - smaller[-1]
            widths[e.id] = smaller[-1]
        if over > 1e-6:
            raise ValueError(f"Δεν χωράει: λείπουν {fmt_cm(over)} cm στη γραμμή")
    used = sum(widths[e.id] for e in order)
    extra_widths, filler = fill_widths(room - used, minf)
    # Lay out: corner units at their ends, then the cabinets in order from the non-filler end.
    changes, new = {}, []
    lo_c, hi_c = lo, hi
    for e in ends:
        s0, s1 = _iv(e, frame)
        if abs(s0 - lo) < abs(hi - s1):
            lo_c = max(lo_c, s1)
        else:
            hi_c = min(hi_c, s0)
    t = 0.0

    def place(w):
        return (lo_c + t) if fend == "hi" else (hi_c - t - w)

    for e in order:
        w = widths[e.id]
        s0 = place(w)
        x, y = frame_point(frame, s0 + w / 2, float(e.params["depth"]) / 2)
        delta = {"x": x, "y": y, "width": w}
        if int(e.params.get("doors", 0)):
            delta["doors"] = auto_doors(e.params["cabinet_type"], w)
        if any(abs(float(e.params[k]) - float(v)) > 1e-9 for k, v in delta.items()):
            changes[e.id] = delta
        t += w
    template = next((e for e in order if e.params.get("run_role") == "cabinet"), target)
    layer = seg["layer"]
    depth = float(template.params["depth"])
    zrel = float(template.params["z"]) - float(seg.get("level", 0.0))
    for w in extra_widths:
        s0 = place(w)
        new.append(_cabinet(frame, Piece(s0, w, "cabinet"), depth, float(seg.get("level", 0.0)), zrel,
                            "wall" if layer == "wall" else "base", "cabinet", p["run_id"], seg, p.get("run_spec") or {}))
        t += w
    if filler > 0.002:
        s0 = place(filler)
        new.append(_cabinet(frame, Piece(s0, filler, "filler"), depth, float(seg.get("level", 0.0)), zrel,
                            "filler", "filler", p["run_id"], seg, p.get("run_spec") or {}))
    for e in new:
        e.params["z"] = float(seg.get("level", 0.0)) + zrel
        if template is not None and template.params.get("surface_materials"):
            e.params["surface_materials"] = dict(template.params["surface_materials"])
        for key in ("front_style", "handle"):
            if key in template.params and e.params.get("cabinet_type") != "filler":
                e.params[key] = template.params[key]
    old_fillers = [e.id for e in group if e.params["cabinet_type"] == "filler"]
    commands = []
    if changes:
        commands.append(UpdateEntities(changes))
    if old_fillers:
        commands.append(DeleteEntities(old_fillers))
    if new:
        commands.append(AddEntities(new))
    return CompositeCommand(commands, label="Πλάτος ντουλαπιού")


def delete_run_command(doc, run_id):
    from archforge.core.commands import DeleteEntities
    ids = [e.id for e in run_members(doc, run_id)]
    return DeleteEntities(ids) if ids else None


def set_run_option(doc, run_id, key, value):
    """Command: change one choice of an applied run (cornice, worktop material/thickness/overhang, fronts)."""
    from archforge.core.commands import UpdateEntities
    changes = {}
    for e in run_members(doc, run_id):
        spec = dict(e.params.get("run_spec") or {})
        spec[key] = value
        delta = {"run_spec": spec}
        if key == "front_material":
            sm = dict(e.params.get("surface_materials") or {})
            if value:
                sm["front"] = value
            else:
                sm.pop("front", None)
            delta["surface_materials"] = sm
        changes[e.id] = delta
    return UpdateEntities(changes) if changes else None


# ------------------------------------------------------------------ derived geometry
def _signature(doc):
    out = []
    for e in doc.entities.values():
        if e.kind == "cabinet" and e.params.get("run_id"):
            p = e.params
            out.append((e.id, p["run_id"], round(float(p["x"]), 5), round(float(p["y"]), 5), round(float(p["z"]), 5),
                        round(float(p["width"]), 5), round(float(p["depth"]), 5), round(float(p["height"]), 5),
                        round(float(p.get("rotation", 0.0)), 4), p.get("cabinet_type"), p.get("run_role"),
                        repr(sorted((p.get("run_spec") or {}).items())), repr(p.get("blind_side")),
                        repr(sorted((p.get("surface_materials") or {}).items()))))
    return tuple(sorted(out))


_CACHE = {}


def run_geometry(doc):
    """Derived parts of every run: worktops (with cut-outs), plinths, cornices, sinks, hobs, hoods.

    Returns ``{"worktops": [...], "plinths": [...], "cornices": [...], "sinks": [...], "hobs": [...],
    "hoods": [...], "corner_tops": [...]}``; straight parts are ``(frame, s0, s1, d0, d1, z0, z1, spec)``.
    """
    key = _signature(doc)
    if _CACHE.get("key") == key:
        return _CACHE["value"]
    value = _derive(doc)
    _CACHE["key"], _CACHE["value"] = key, value
    return value


def _derive(doc):
    from archforge.kitchen.cabinets import _corner_outline, _world
    out = {"worktops": [], "plinths": [], "cornices": [], "sinks": [], "hobs": [], "hoods": [], "corner_tops": []}
    groups = {}
    for e in doc.entities.values():
        if e.kind != "cabinet" or not e.params.get("run_id") or not e.params.get("run_seg"):
            continue
        seg = e.params["run_seg"]
        groups.setdefault((e.params["run_id"], _frame_key(seg["frame"]), seg["layer"]), []).append(e)
    for (run_id, _fk, layer), members in sorted(groups.items(), key=lambda kv: kv[0]):
        frame = members[0].params["run_seg"]["frame"]
        spec = dict(DEFAULTS)
        spec.update(members[0].params.get("run_spec") or {})
        level = float(members[0].params["run_seg"].get("level", 0.0))
        ivs = [(*_iv(e, frame), e) for e in members]
        if layer == "base":
            thick, ov = float(spec.get("worktop_thick", WORKTOP_THICK)), float(spec.get("overhang", WORKTOP_OVERHANG))
            straight = [(a, b, e) for a, b, e in ivs if e.params.get("cabinet_type") != "corner"]
            for e in members:
                if e.params.get("cabinet_type") == "corner":
                    q = e.params
                    top = level + float(q["height"])
                    out["corner_tops"].append((_world(q, _corner_outline(q, 0.0, 0.0, -ov)), top, top + thick, spec, run_id))
            top = level + max([float(e.params["height"]) for e in members] or [BASE_HEIGHT])
            for s0, s1 in _merge([(a, b) for a, b, _e in straight], BRIDGE):
                holes = []
                for a, b, e in straight:
                    if a < s0 - 1e-6 or b > s1 + 1e-6:
                        continue
                    role = e.params.get("run_role")
                    c, w = (a + b) / 2, b - a
                    front = BASE_DEPTH + ov
                    if role == "sink":
                        hw, hd, fm = min(w - 0.14, 0.76), 0.44, 0.08
                        holes.append(("sink", c - hw / 2, c + hw / 2, front - fm - hd, front - fm))
                    elif role == "hob":
                        hw, hd, fm = min(w - 0.04, 0.56), 0.49, 0.065
                        holes.append(("hob", c - hw / 2, c + hw / 2, front - fm - hd, front - fm))
                out["worktops"].append((frame, s0, s1, 0.0, BASE_DEPTH + ov, top, top + thick, spec, holes, run_id))
                for kind, h0, h1, d0, d1 in holes:
                    if kind == "sink":
                        out["sinks"].append((frame, h0, h1, d0, d1, top, top + thick, spec, run_id))
                    else:
                        out["hobs"].append((frame, h0, h1, d0, d1, top + thick, top + thick + 0.006, spec, run_id))
                        hood_z = top + thick + HOOD_ABOVE - 0.04
                        out["hoods"].append((frame, (h0 + h1) / 2, hood_z, spec, run_id))
            for s0, s1 in _merge([(a, b) for a, b, _e in straight], 0.005):
                plinth = min(float(e.params.get("plinth", PLINTH)) for a, b, e in straight if s0 - 1e-6 <= a and b <= s1 + 1e-6)
                if plinth <= 0:
                    continue
                d1 = BASE_DEPTH - 0.05
                out["plinths"].append((frame, s0, s1, d1 - PLINTH_BOARD, d1, level, level + plinth, spec, run_id))
                # Returns at both ends back to the wall (closed on the side too).
                out["plinths"].append((frame, s0, s0 + PLINTH_BOARD, 0.0, d1 - PLINTH_BOARD, level, level + plinth, spec, run_id))
                out["plinths"].append((frame, s1 - PLINTH_BOARD, s1, 0.0, d1 - PLINTH_BOARD, level, level + plinth, spec, run_id))
        elif spec.get("cornice"):
            for s0, s1 in _merge([(a, b) for a, b, _e in ivs], 0.005):
                top = level + max(float(e.params["z"]) - level + float(e.params["height"]) for e in members)
                out["cornices"].append((frame, s0, s1, 0.0, WALL_DEPTH + CORNICE_PROJ, top, top + CORNICE_H, spec, run_id))
    return out


def worktop_boxes(part):
    """A straight worktop with its cut-outs as boxes ``[(s0, s1, d0, d1)]`` (strips around the holes)."""
    _frame, s0, s1, d0, d1, _z0, _z1, _spec, holes, _rid = part
    cuts = sorted({s0, s1} | {h[1] for h in holes if s0 < h[1] < s1} | {h[2] for h in holes if s0 < h[2] < s1})
    boxes = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 1e-6:
            continue
        mid = (a + b) / 2
        spans = [(d0, d1)]
        for _k, h0, h1, hd0, hd1 in holes:
            if h0 < mid < h1:
                nxt = []
                for x0, x1 in spans:
                    if hd1 <= x0 or hd0 >= x1:
                        nxt.append((x0, x1))
                        continue
                    if hd0 > x0:
                        nxt.append((x0, hd0))
                    if hd1 < x1:
                        nxt.append((hd1, x1))
                spans = nxt
        boxes += [(a, b, x0, x1) for x0, x1 in spans if x1 - x0 > 1e-6]
    return boxes


def worktop_length(doc):
    """Running metres of worktop per material (along the wall; L corners counted on both legs)."""
    from archforge.kitchen.cabinets import CORNER_ARM
    g = run_geometry(doc)
    out = {}
    for part in g["worktops"]:
        spec = part[7]
        k = (spec.get("worktop_material"), float(spec.get("worktop_thick", WORKTOP_THICK)))
        out[k] = out.get(k, 0.0) + (part[2] - part[1])
    for poly, z0, z1, spec, _rid in g["corner_tops"]:
        k = (spec.get("worktop_material"), float(spec.get("worktop_thick", WORKTOP_THICK)))
        out[k] = out.get(k, 0.0) + 2 * CORNER_W - CORNER_ARM
    return out


# ------------------------------------------------------------------ plan and 3D
def _ring(frame, s0, s1, d0, d1):
    return [frame_point(frame, s0, d0), frame_point(frame, s1, d0), frame_point(frame, s1, d1), frame_point(frame, s0, d1)]


def _circle(cx, cy, r, n=20):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]


def plan_primitives(doc):
    """Derived plan lines ``[(role, points, closed)]`` of the active storey."""
    level = float(doc.work_plane.origin[2])
    g = run_geometry(doc)
    out = []

    def here(z):
        return level - 0.05 <= z <= level + 2.6

    for part in g["worktops"]:
        frame, s0, s1, d0, d1, z0 = part[:6]
        if not here(z0):
            continue
        out.append(("worktop", _ring(frame, s0, s1, d0, d1), True))
        for kind, h0, h1, hd0, hd1 in part[8]:
            out.append(("worktop-cutout", _ring(frame, h0, h1, hd0, hd1), True))
    for poly, z0, _z1, _spec, _rid in g["corner_tops"]:
        if here(z0):
            out.append(("worktop", list(poly), True))
    for frame, h0, h1, d0, d1, z0, *_ in g["sinks"]:
        if not here(z0):
            continue
        # Bowl (rounded corners) and the waste.
        r = 0.04
        pts = []
        for (cs, cd, a0) in ((h1 - r, d1 - r, 0), (h0 + r, d1 - r, 90), (h0 + r, d0 + r, 180), (h1 - r, d0 + r, 270)):
            for k in range(6):
                ang = math.radians(a0 + 90 * k / 5)
                pts.append(frame_point(frame, cs + r * math.cos(ang), cd + r * math.sin(ang)))
        pts.append(pts[0])
        out.append(("sink-symbol", pts, False))
        cx, cy = frame_point(frame, (h0 + h1) / 2, (d0 + d1) / 2)
        out.append(("sink-symbol", _circle(cx, cy, 0.03), False))
        tx, ty = frame_point(frame, (h0 + h1) / 2, d0 - 0.035)
        out.append(("sink-symbol", _circle(tx, ty, 0.02), False))
    for frame, h0, h1, d0, d1, z0, *_ in g["hobs"]:
        if not here(z0):
            continue
        for fs, fd, r in ((0.27, 0.28, 0.09), (0.73, 0.28, 0.07), (0.27, 0.74, 0.07), (0.73, 0.74, 0.09)):
            cx, cy = frame_point(frame, h0 + (h1 - h0) * fs, d0 + (d1 - d0) * fd)
            out.append(("hob-symbol", _circle(cx, cy, r), False))
    for frame, s, z, _spec, _rid in g["hoods"]:
        if here(z - 1.0):
            out.append(("hood", _ring(frame, s - 0.30, s + 0.30, 0.0, 0.50), True))
    return out


def _add_box(verts, tris, corners, z0, z1, flip):
    base = len(verts)
    for zz in (z0, z1):
        verts.extend([float(cx), float(cy), float(zz)] for cx, cy in corners)
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7)]
    for i in range(4):
        j = (i + 1) % 4
        faces += [(i, j, 4 + j), (i, 4 + j, 4 + i)]
    for a, b, c in faces:
        tris.append([base + a, base + c, base + b] if flip else [base + a, base + b, base + c])


def _frame_flip(frame):
    u, n = frame["u"], frame["n"]
    return u[0] * n[1] - u[1] * n[0] < 0


def _ccw(poly):
    return sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly))) > 0


def _add_prism(verts, tris, poly, z0, z1):
    from archforge.geometry.mesh import _triangulate
    pts = list(poly) if _ccw(poly) else list(poly)[::-1]
    base, n = len(verts), len(pts)
    for zz in (z0, z1):
        verts.extend([float(x), float(y), float(zz)] for x, y in pts)
    cap = _triangulate(pts)
    tris += [[base + i, base + k, base + j] for i, j, k in cap]
    tris += [[base + n + i, base + n + j, base + n + k] for i, j, k in cap]
    for i in range(n):
        j = (i + 1) % n
        tris += [[base + i, base + j, base + n + j], [base + i, base + n + j, base + n + i]]


def _add_rect(verts, tris, frame, s0, s1, d0, d1, z0, z1):
    _add_box(verts, tris, _ring(frame, s0, s1, d0, d1), z0, z1, _frame_flip(frame))


def _worktop_material(spec, selected=False):
    from archforge.rendering.materials import material_spec
    from archforge.rendering.patterns import pattern_key
    mid = spec.get("worktop_material") or "marble_thassos"
    custom = material_spec(mid) or {"color": "#e4e3df", "roughness": 0.3, "metalness": 0.0, "name": mid}
    m = {"color": custom.get("color"), "roughness": custom.get("roughness", 0.3), "metalness": custom.get("metalness", 0.0),
         "material_id": str(mid), "material_name": str(custom.get("name", mid))}
    pat = custom.get("pattern")
    if pat:
        # One slab, no joints: the stone's veins at real size, without the tile grid of a floor.
        slab = dict(pat, unit_w=3.0, unit_h=3.0, joint=0.0, variation=0.0)
        m["pattern"] = slab
        m["pattern_key"] = pattern_key(str(mid) + ":worktop", slab, str(m["color"]))
    return m


def scene_objects(doc):
    """Derived 3D meshes (layer «kitchen»): worktops, plinths, cornices, sinks, taps, hob plates, hoods."""
    g = run_geometry(doc)
    if not any(g.values()):
        return []
    from archforge.rendering.materials import material_spec
    objects = []

    def obj(part, verts, tris, material, surface):
        if tris:
            objects.append({"id": "", "render_part": f"run:{part}", "kind": "kitchen_run", "layer": "kitchen",
                            "vertices": verts, "triangles": tris, "surfaces": [surface] * len(tris), "material": material})

    by_mat = {}
    for part in g["worktops"]:
        frame, z0, z1, spec = part[0], part[5], part[6], part[7]
        key = repr(_worktop_material(spec))
        verts, tris, mat = by_mat.setdefault(key, ([], [], _worktop_material(spec)))
        for s0, s1, d0, d1 in worktop_boxes(part):
            _add_rect(verts, tris, frame, s0, s1, d0, d1, z0, z1)
    for poly, z0, z1, spec, _rid in g["corner_tops"]:
        key = repr(_worktop_material(spec))
        verts, tris, mat = by_mat.setdefault(key, ([], [], _worktop_material(spec)))
        _add_prism(verts, tris, poly, z0, z1)
    for k, (key, (verts, tris, mat)) in enumerate(sorted(by_mat.items())):
        obj(f"worktop{k}", verts, tris, mat, "worktop")

    def front_material(spec):
        m = material_spec(spec.get("front_material")) if spec.get("front_material") else None
        if m:
            return {"color": m["color"], "roughness": m.get("roughness", 0.45), "metalness": m.get("metalness", 0.0),
                    "material_id": spec["front_material"], "material_name": m.get("name", "")}
        return {"color": "#f4f1ea", "roughness": 0.45, "metalness": 0.0}

    verts, tris = [], []
    for frame, s0, s1, d0, d1, z0, z1, _spec, _rid in g["plinths"]:
        _add_rect(verts, tris, frame, s0, s1, d0, d1, z0, z1)
    obj("plinth", verts, tris, {"color": "#8f9396", "roughness": 0.35, "metalness": 0.7}, "plinth")
    corn = {}
    for frame, s0, s1, d0, d1, z0, z1, spec, _rid in g["cornices"]:
        key = repr(front_material(spec))
        v, t, m = corn.setdefault(key, ([], [], front_material(spec)))
        _add_rect(v, t, frame, s0 - CORNICE_PROJ, s1 + CORNICE_PROJ, d0, d1, z0, z1)
    for k, (v, t, m) in enumerate(corn.values()):
        obj(f"cornice{k}", v, t, m, "cornice")
    steel = {"color": "#b9bfc3", "roughness": 0.25, "metalness": 0.85}
    verts, tris = [], []
    for frame, h0, h1, d0, d1, z0, z1, _spec, _rid in g["sinks"]:
        wall, depth = 0.008, 0.19
        bottom = z0 - depth
        # Rim on the worktop, bowl walls and bottom under the cut-out, the tap behind.
        for a, b, c, d in ((h0 - 0.015, h1 + 0.015, d0 - 0.015, d0), (h0 - 0.015, h1 + 0.015, d1, d1 + 0.015),
                           (h0 - 0.015, h0, d0, d1), (h1, h1 + 0.015, d0, d1)):
            _add_rect(verts, tris, frame, a, b, c, d, z1, z1 + 0.003)
        _add_rect(verts, tris, frame, h0, h1, d0, d1, bottom, bottom + wall)
        _add_rect(verts, tris, frame, h0, h1, d0, d0 + wall, bottom, z1)
        _add_rect(verts, tris, frame, h0, h1, d1 - wall, d1, bottom, z1)
        _add_rect(verts, tris, frame, h0, h0 + wall, d0, d1, bottom, z1)
        _add_rect(verts, tris, frame, h1 - wall, h1, d0, d1, bottom, z1)
        c = (h0 + h1) / 2
        _add_rect(verts, tris, frame, c - 0.018, c + 0.018, d0 - 0.06, d0 - 0.024, z1, z1 + 0.30)       # tap body
        _add_rect(verts, tris, frame, c - 0.012, c + 0.012, d0 - 0.06, d0 + 0.17, z1 + 0.27, z1 + 0.30)  # spout
    obj("sinks", verts, tris, steel, "sink")
    verts, tris = [], []
    rings_v, rings_t = [], []
    for frame, h0, h1, d0, d1, z0, z1, _spec, _rid in g["hobs"]:
        _add_rect(verts, tris, frame, h0 - 0.01, h1 + 0.01, d0 - 0.01, d1 + 0.01, z0, z1)
        for fs, fd, r in ((0.27, 0.28, 0.09), (0.73, 0.28, 0.07), (0.27, 0.74, 0.07), (0.73, 0.74, 0.09)):
            cx, cy = frame_point(frame, h0 + (h1 - h0) * fs, d0 + (d1 - d0) * fd)
            _add_prism(rings_v, rings_t, _circle(cx, cy, r, 24)[:-1], z1, z1 + 0.0015)
    obj("hobs", verts, tris, {"color": "#141518", "roughness": 0.08, "metalness": 0.2}, "hob")
    obj("hob_zones", rings_v, rings_t, {"color": "#3d2b2b", "roughness": 0.3, "metalness": 0.0}, "hob")
    verts, tris = [], []
    for frame, s, z, _spec, _rid in g["hoods"]:
        _add_rect(verts, tris, frame, s - 0.30, s + 0.30, 0.0, 0.50, z, z + 0.06)          # canopy
        _add_rect(verts, tris, frame, s - 0.13, s + 0.13, 0.02, 0.27, z + 0.06, z + 0.75)  # chimney
    obj("hoods", verts, tris, steel, "hood")
    return objects


def proposal_ghost(proposal):
    """What the plan draws before «Εφαρμογή»: ``[(kind, points, closed)]``."""
    from archforge.kitchen.cabinets import footprint, front_line
    out = []
    for e in proposal.entities:
        p = e.params
        kind = "wall" if float(p.get("z", 0.0)) - float((p.get("run_seg") or {}).get("level", 0.0)) > 1.0 else "base"
        if p.get("cabinet_type") == "filler":
            kind = "filler-" + kind
        out.append((kind, footprint(p), True))
        if p.get("cabinet_type") not in ("filler",):
            out.append(("front", front_line(p), False))
    return out
