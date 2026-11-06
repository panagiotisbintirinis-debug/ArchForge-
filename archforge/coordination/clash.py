"""Έλεγχος συγκρούσεων (clash detection) αρχιτεκτονικών, στατικών και Η/Μ — κενό 2 της αποτύπωσης δυνατοτήτων (06/11).

Ένα μοντέλο, άρα χωρίς ανταλλαγή αρχείων: τα δίκτυα που παράγει το πρόγραμμα (ύδρευση, θέρμανση, αποχέτευση,
ηλεκτρολογικές και ασθενείς σωληνώσεις) και τα στοιχεία του σχεδίου ελέγχονται απευθείας στη γεωμετρία τους.

Ζεύγη που ελέγχονται (όλα σε 3Δ, με ανοχή ``TOLERANCE``):

* **Η/Μ ↔ φέρων:** σωλήνας / σωλήνωση που περνά μέσα από δοκό ή κολόνα (χρειάζεται διέλευση / χιτώνιο ή αλλαγή
  όδευσης). Οι πλάκες δεν ελέγχονται: η κατακόρυφη διέλευση από πλάκα είναι κανονική.
* **Κούφωμα ↔ φέρων:** δοκός που κατεβαίνει μέσα στο άνοιγμα, κολόνα μέσα στο άνοιγμα.
* **Έπιπλο / ντουλάπι ↔ φέρων / τοίχος:** αντικείμενο που μπαίνει μέσα σε κολόνα ή στο πάχος τοίχου.
* **Σημείο Η/Μ ↔ κολόνα:** σημείο (πρίζα, παροχή, στόμιο) μέσα στο σκυρόδεμα.

Τι δεν είναι: έλεγχος αποστάσεων κανονισμού (ελεύθερο ύψος, αποστάσεις ασφαλείας) — αυτά θέλουν κείμενο κανονισμού.
Οι σωληνώσεις ηλεκτρολογικών / ασθενών δεν έχουν δική τους διάμετρο στη διαδρομή: λαμβάνονται Ø 20 mm (DESIGN_DEFAULT).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

TOLERANCE = 0.01            # m: less than this inside the other element is contact, not a clash (DESIGN_DEFAULT)
CONDUIT_D = 0.020           # m: electrical / low-voltage conduit without its own size on the route (DESIGN_DEFAULT)

NETWORKS = {"cold": "Ύδρευση κρύο", "hot": "Ύδρευση ζεστό", "supply": "Θέρμανση προσαγωγή", "return": "Θέρμανση επιστροφή",
            "drainage": "Αποχέτευση", "electrical": "Ηλεκτρολογική σωλήνωση", "low_voltage": "Ασθενή"}
KIND_LABEL = {"structural_beam": "Δοκός", "structural_column": "Κολόνα", "window": "Παράθυρο", "door": "Πόρτα",
              "wall": "Τοίχος", "library_object": "Αντικείμενο", "cabinet": "Ντουλάπι", "electrical_point": "Ηλεκτρολογικό σημείο",
              "plumbing_point": "Υδραυλικό σημείο", "drainage_point": "Σημείο αποχέτευσης", "heating_point": "Σημείο θέρμανσης",
              "ventilation_point": "Στόμιο αερισμού"}


@dataclass(frozen=True)
class Box:
    """An oriented box: centre (cx, cy), half sizes along its axes (hu along ``angle``, hv across), z0 … z1."""
    eid: str
    kind: str
    cx: float
    cy: float
    hu: float
    hv: float
    angle: float            # radians
    z0: float
    z1: float

    def local(self, x, y):
        c, s = math.cos(self.angle), math.sin(self.angle)
        dx, dy = x - self.cx, y - self.cy
        return dx * c + dy * s, -dx * s + dy * c

    def corners(self):
        c, s = math.cos(self.angle), math.sin(self.angle)
        return [(self.cx + u * c - v * s, self.cy + u * s + v * c)
                for u, v in ((-self.hu, -self.hv), (self.hu, -self.hv), (self.hu, self.hv), (-self.hu, self.hv))]


@dataclass
class Clash:
    a_kind: str
    a_id: str
    b_kind: str
    b_id: str
    depth: float            # m inside (length of pipe inside, or overlap)
    at: Tuple[float, float, float]
    group: str
    note: str = ""
    ids: Tuple[str, ...] = field(default_factory=tuple)


# ------------------------------------------------------------------ elements as boxes

def _column(e):
    p = e.params
    return Box(e.id, e.kind, float(p["x"]), float(p["y"]), float(p["width"]) / 2, float(p["depth"]) / 2,
               math.radians(float(p.get("rotation", 0.0))), float(p.get("z", 0.0)), float(p.get("z", 0.0)) + float(p["height"]))


def _beam(e):
    p = e.params
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    z = float(p.get("z", 0.0))
    return Box(e.id, e.kind, (x1 + x2) / 2, (y1 + y2) / 2, math.hypot(x2 - x1, y2 - y1) / 2, float(p["width"]) / 2,
               math.atan2(y2 - y1, x2 - x1), z, z + float(p["height"]))


def _wall(e):
    p = e.params
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    z = float(p.get("z", 0.0))
    return Box(e.id, e.kind, (x1 + x2) / 2, (y1 + y2) / 2, math.hypot(x2 - x1, y2 - y1) / 2, float(p["thickness"]) / 2,
               math.atan2(y2 - y1, x2 - x1), z, z + float(p["height"]))


def _opening(doc, e):
    """The opening as a box in its wall: centre at ``offset`` along the wall, as deep as the wall."""
    w = doc.entities.get(e.parent_id) if e.parent_id else None
    if w is None or w.kind != "wall":
        return None
    p, wp = e.params, w.params
    x1, y1, x2, y2 = (float(wp[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    c = float(p["offset"])
    z0 = float(wp.get("z", 0.0)) + (float(p.get("sill", 0.0)) if e.kind == "window" else 0.0)
    return Box(e.id, e.kind, x1 + ux * c, y1 + uy * c, float(p["width"]) / 2, float(wp["thickness"]) / 2,
               math.atan2(uy, ux), z0, z0 + float(p["height"]))


def _object(e):
    p = e.params
    z = float(p.get("z", 0.0))
    return Box(e.id, e.kind, float(p["x"]), float(p["y"]), float(p["width"]) / 2, float(p["depth"]) / 2,
               math.radians(float(p.get("rotation", 0.0))), z, z + float(p.get("height", 0.0)))


def _visible(doc, kind):
    return [e for e in doc.entities.values() if e.kind == kind and e.visible and str(e.params.get("phase", "new")) != "demolish"]


def structure(doc):
    out = []
    for e in _visible(doc, "structural_column"):
        out.append(_column(e))
    for e in _visible(doc, "structural_beam"):
        if math.hypot(float(e.params["x2"]) - float(e.params["x1"]), float(e.params["y2"]) - float(e.params["y1"])) > 1e-6:
            out.append(_beam(e))
    return out


# ------------------------------------------------------------------ geometry

def segment_in_box(a, b, box, radius=0.0):
    """Length of the segment a–b (3D) inside ``box`` grown by ``radius``, and the midpoint of that part, or (0, None)."""
    au, av = box.local(a[0], a[1])
    bu, bv = box.local(b[0], b[1])
    lo, hi = 0.0, 1.0
    for p0, p1, mn, mx in ((au, bu, -box.hu - radius, box.hu + radius), (av, bv, -box.hv - radius, box.hv + radius),
                           (a[2], b[2], box.z0 - radius, box.z1 + radius)):
        d = p1 - p0
        if abs(d) < 1e-12:
            if p0 < mn or p0 > mx:
                return 0.0, None
            continue
        t0, t1 = (mn - p0) / d, (mx - p0) / d
        if t0 > t1:
            t0, t1 = t1, t0
        lo, hi = max(lo, t0), min(hi, t1)
        if lo >= hi:
            return 0.0, None
    seg = math.dist(a, b) * (hi - lo)
    tm = (lo + hi) / 2
    return seg, tuple(a[i] + (b[i] - a[i]) * tm for i in range(3))


def _project(box, axis):
    ax, ay = axis
    c, s = math.cos(box.angle), math.sin(box.angle)
    centre = box.cx * ax + box.cy * ay
    r = box.hu * abs(c * ax + s * ay) + box.hv * abs(-s * ax + c * ay)
    return centre - r, centre + r


def box_overlap(a, b):
    """Smallest overlap (m) of two oriented boxes over the plan axes and z, or 0 when they are apart."""
    dz = min(a.z1, b.z1) - max(a.z0, b.z0)
    if dz <= 0:
        return 0.0
    best = dz
    for box in (a, b):
        c, s = math.cos(box.angle), math.sin(box.angle)
        for axis in ((c, s), (-s, c)):
            a0, a1 = _project(a, axis)
            b0, b1 = _project(b, axis)
            o = min(a1, b1) - max(a0, b0)
            if o <= 0:
                return 0.0
            best = min(best, o)
    return best


def _centre(a, b):
    return ((a.cx + b.cx) / 2, (a.cy + b.cy) / 2, (max(a.z0, b.z0) + min(a.z1, b.z1)) / 2)


# ------------------------------------------------------------------ networks

def network_segments(doc):
    """``[(network key, a, b, diameter m)]`` of every derived network (the same routes the plan and 3D draw)."""
    out = []
    try:
        from archforge.mep.plumbing import plumbing_points, route_plumbing_cached
        if plumbing_points(doc):
            r = route_plumbing_cached(doc)
            for key in ("cold", "hot"):
                out += [(key, a, b, float(d) / 1000) for a, b, d in r.get(key, ())]
    except Exception:                                   # noqa: BLE001 — a network that cannot route is said elsewhere
        pass
    try:
        from archforge.mep.heating_layout import heating_points, route_heating_cached
        if heating_points(doc):
            r = route_heating_cached(doc)
            for key in ("supply", "return"):
                out += [(key, a, b, float(d) / 1000) for a, b, d in r.get(key, ())]
    except Exception:                                   # noqa: BLE001
        pass
    try:
        from archforge.mep.drainage import drainage_points, route_drainage_cached
        from archforge.mep.plumbing import plumbing_points
        if plumbing_points(doc) or drainage_points(doc):
            r = route_drainage_cached(doc)
            out += [("drainage", q[0], q[1], float(q[2]) / 1000) for q in r.get("pipes", ())]
    except Exception:                                   # noqa: BLE001
        pass
    try:
        from archforge.mep.electrical import electrical_points, route_cables_cached
        if electrical_points(doc):
            r = route_cables_cached(doc)
            out += [("electrical", q[0], q[1], CONDUIT_D) for q in r.get("runs", ())]
    except Exception:                                   # noqa: BLE001
        pass
    try:
        from archforge.mep.low_voltage import lv_points, route_low_voltage_cached
        if lv_points(doc):
            r = route_low_voltage_cached(doc)
            out += [("low_voltage", q[0], q[1], CONDUIT_D) for q in r.get("runs", ())]
    except Exception:                                   # noqa: BLE001
        pass
    return [(k, tuple(map(float, a)), tuple(map(float, b)), d) for k, a, b, d in out if len(a) == 3 and len(b) == 3]


# ------------------------------------------------------------------ the checks

def find(doc, tolerance=TOLERANCE):
    """Every clash of the project, ordered by group and depth: ``[Clash]``."""
    found = []
    frame = structure(doc)
    # 1. networks through beams / columns — one clash per network and member, all its passes summed. Electrical and
    #    low-voltage conduits cast in the concrete (owner 06/11: «μπορεί να γίνει προσωλήνωση») are not clashes when
    #    the project allows it: they are the «Προσωλήνωση» list (cast_in), work before the pour.
    passes = member_passes(doc, frame, tolerance)
    allowed = CAST_IN_NETWORKS if cast_in_allowed(doc) else ()
    for (net, _eid), (box, total, n, at, d, _pts) in passes.items():
        if net in allowed:
            continue
        n = len(crossings(_pts))
        found.append(Clash("network:" + net, "", box.kind, box.eid, total, at, "Η/Μ ↔ φέρων",
                           f"{NETWORKS[net]} Ø{d * 1000:.0f}: {n} διελεύσεις, {total * 100:.0f} cm μέσα σε "
                           f"{KIND_LABEL[box.kind].lower()}", (box.eid,)))
    # 2. openings against the frame
    for kind in ("window", "door"):
        for e in _visible(doc, kind):
            ob = _opening(doc, e)
            if ob is None:
                continue
            for box in frame:
                o = box_overlap(ob, box)
                if o > tolerance:
                    what = ("η δοκός κατεβαίνει μέσα στο άνοιγμα" if box.kind == "structural_beam" else
                            "η κολόνα είναι μέσα στο άνοιγμα")
                    found.append(Clash(kind, e.id, box.kind, box.eid, o, _centre(ob, box), "Κούφωμα ↔ φέρων",
                                       f"{what} ({o * 100:.0f} cm)", (e.id, box.eid)))
    # 3. furniture / cabinets against columns and walls
    walls = [_wall(e) for e in _visible(doc, "wall")]
    columns = [b for b in frame if b.kind == "structural_column"]
    for kind in ("library_object", "cabinet"):
        for e in _visible(doc, kind):
            try:
                ob = _object(e)
            except (KeyError, ValueError, TypeError):
                continue
            if ob.hu <= 0 or ob.hv <= 0:
                continue
            for box in columns + walls:
                o = box_overlap(ob, box)
                if o > max(tolerance, 0.02):         # an object set against a wall touches it: 2 cm before it counts
                    found.append(Clash(kind, e.id, box.kind, box.eid, o, _centre(ob, box), "Αντικείμενο ↔ δομικό",
                                       f"μπαίνει {o * 100:.0f} cm μέσα σε {KIND_LABEL[box.kind].lower()}", (e.id, box.eid)))
    # 4. MEP points inside columns
    for kind in ("electrical_point", "plumbing_point", "drainage_point", "heating_point", "ventilation_point"):
        for e in _visible(doc, kind):
            p = e.params
            if "x" not in p or "y" not in p:
                continue
            x, y, z = float(p["x"]), float(p["y"]), float(p.get("z", 0.0))
            if kind == "electrical_point":
                try:
                    from archforge.mep.electrical import mount_z
                    z = mount_z(doc, p)
                except Exception:                     # noqa: BLE001 — the point's floor level then
                    pass
            for box in columns:
                u, v = box.local(x, y)
                margin = min(box.hu - abs(u), box.hv - abs(v))
                if margin > tolerance and box.z0 - 1e-6 <= z <= box.z1 + 1e-6:
                    found.append(Clash(kind, e.id, box.kind, box.eid, margin, (x, y, z), "Σημείο Η/Μ ↔ κολόνα",
                                       f"{KIND_LABEL[kind]} {margin * 100:.0f} cm μέσα στο σκυρόδεμα", (e.id, box.eid)))
    found.sort(key=lambda c: (c.group, -c.depth))
    return found


CAST_IN_NETWORKS = ("electrical", "low_voltage")


def cast_in_allowed(doc):
    """Conduits may be cast in the concrete (electrical_board settings on the panel; default yes, owner 06/11)."""
    try:
        from archforge.mep.electrical_board import settings
        return bool(settings(doc)["cast_in_concrete"])
    except Exception:                                   # noqa: BLE001 — no panel: the default
        return True


def member_passes(doc, frame=None, tolerance=TOLERANCE):
    """``{(network, member id): [box, length inside, passes, first point, Ø, [points]]}``."""
    frame = structure(doc) if frame is None else frame
    passes = {}
    for net, a, b, d in network_segments(doc):
        for box in frame:
            inside, at = segment_in_box(a, b, box, d / 2)
            if inside > tolerance:
                key = (net, box.eid)
                if key not in passes:
                    passes[key] = [box, 0.0, 0, at, d, []]
                passes[key][1] += inside
                passes[key][2] += 1
                passes[key][4] = max(passes[key][4], d)
                passes[key][5].append(at)
    return passes


def crossings(points, reach=0.35):
    """The physical crossings of one member: grid pieces of the same conduit (≤ ``reach`` apart, a 20 cm grid) are
    one crossing. ``[(x, y, z)]`` one point each."""
    groups = []
    for q in points:
        hit = [g for g in groups if any(math.dist(q, p) <= reach for p in g)]
        merged = [q] + [p for g in hit for p in g]
        groups = [g for g in groups if g not in hit] + [merged]
    return [tuple(sum(p[i] for p in g) / len(g) for i in range(3)) for g in groups]


def cast_in(doc):
    """The conduits to place in the formwork before the pour: ``[{"member", "kind", "network", "passes", "length",
    "points", "diameter"}]`` per member and network (electrical / low voltage), by member."""
    out = []
    for (net, eid), (box, total, n, _at, d, pts) in member_passes(doc).items():
        if net not in CAST_IN_NETWORKS:
            continue
        where = crossings(pts)
        out.append({"member": eid, "kind": box.kind, "network": net, "passes": len(where), "length": total,
                    "points": where, "diameter": d})
    out.sort(key=lambda r: (r["kind"], r["member"], r["network"]))
    return out


def summary(clashes):
    """``{group: count}``."""
    out = {}
    for c in clashes:
        out[c.group] = out.get(c.group, 0) + 1
    return out
