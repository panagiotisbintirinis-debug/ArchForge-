"""From the Document to an analytical frame: members, nodes, supports, loads, masses.

Rules (stated so a structural engineer can check them):

* Members: structural-role Columns and Beams.  Reinforced concrete (and
  'generic') members use their b×h; steel members use their rolled profile
  (``profile``; default HEB200 column / IPE300 beam until designed).
  Timber and aluminium members are listed but not analysed here.
* Analytical axes: column axis from base to top; beam axis on its top plane
  (the slab level).  Members are split where another member meets them
  (tolerance 15 cm in plan, 5 cm in height); beams are cut into ≤ 0.5 m
  elements so slab loads are applied along them.  Beam-column joints are
  rigid (monolithic RC / moment frame).
* Supports: explicit Supports when given; otherwise a column base that rests
  on nothing else is fixed (footing).
* Stiffness for the analysis: RC cracked sections, 50 % of the gross
  flexural stiffness (EN 1998-1 §4.3.1(7)), torsion 10 %.
* Slabs: each room below a beam plane is a slab panel; its load goes to the
  nearest beam of the plane (tributary areas, ≈ the 45° rule for
  rectangles), sampled on a 10 cm grid.  Dead load = 25 kN/m³ × thickness
  + finishes + partitions (floors) or roof finishes (roof); imposed load by
  occupancy (EN 1991-1-1).
* Walls standing on a beam plane, along a beam: line load = wall weight per
  m² × wall height.  Masonry: 2.1 kN/m² (half-brick, ≤ 15 cm) or 3.6 kN/m²
  (thicker) — usual Greek practice values incl. plaster; drywall 0.5 kN/m².
* Seismic masses: G + ψ2·Q at the nodes (EN 1998-1 §3.2.4).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

from archforge.structure.analysis.fem import Element
from archforge.structure.analysis.sections import CONCRETE, STEEL_E, STEEL_G, profile
from archforge.structure.analysis.settings import OCCUPANCIES, ROOF_ACCESS

TOL_XY, TOL_Z, MAX_ELEMENT = 0.15, 0.05, 0.5
CONCRETE_WEIGHT, CRACKED, TORSION = 25.0, 0.5, 0.1
DEFAULT_PROFILE = {"structural_column": "HEB200", "structural_beam": "IPE300"}
ANALYSED = ("reinforced_concrete", "generic", "steel")


@dataclass
class Member:
    id: str
    kind: str                       # 'column' | 'beam'
    name: str
    material: str                   # 'rc' | 'steel'
    p1: Tuple[float, float, float]
    p2: Tuple[float, float, float]
    b: float                        # RC: width (column: along local y) ; steel: profile width
    h: float                        # RC: depth / height ; steel: profile height
    profile: str = ""
    y_dir: Tuple[float, float, float] = (1.0, 0.0, 0.0)
    elements: List[int] = field(default_factory=list)

    @property
    def length(self):
        return math.dist(self.p1, self.p2)


@dataclass
class Model:
    nodes: List[Tuple[float, float, float]]
    elements: List[Element]
    members: Dict[str, Member]
    supports: Dict[int, Tuple[bool, ...]]
    loads: Dict[str, Dict[int, np.ndarray]]     # case -> node -> 6-vector
    mass: Dict[int, float]                      # t
    planes: List[float]
    base_z: float
    warnings: List[str]
    excluded: List[str]


def _rect_torsion(a, b):
    a, b = max(a, b), min(a, b)
    return a * b ** 3 * (1 / 3 - 0.21 * b / a * (1 - b ** 4 / (12 * a ** 4)))


def element_props(m: Member, settings):
    if m.material == "steel":
        p = profile(m.profile)
        E, G = STEEL_E * 1000, STEEL_G * 1000
        return dict(E=E, G=G, A=p["A"], Iy=p["Iy"], Iz=p["Iz"], J=p["J"]), p["weight"]
    E = CONCRETE[settings["concrete"]][2] * 1000 * CRACKED
    A = m.b * m.h
    return dict(E=E, G=E / 2.4, A=A, Iy=m.b * m.h ** 3 / 12, Iz=m.h * m.b ** 3 / 12,
                J=_rect_torsion(m.b, m.h) * TORSION / CRACKED), CONCRETE_WEIGHT * A


def read_members(doc):
    members, excluded = {}, []
    counters = {"column": 0, "beam": 0}

    def reading_order(eid):
        # Plan reading order per storey: bottom level first, then top-to-bottom, left-to-right.
        p = doc.entities[eid].params
        x = float(p.get("x", p.get("x1", 0.0)))
        y = float(p.get("y", p.get("y1", 0.0)))
        return (round(float(p.get("z", 0.0)), 1), -round(y, 1), round(x, 1), eid)

    for eid in sorted((i for i, e in doc.entities.items() if e.kind in ("structural_column", "structural_beam")),
                      key=reading_order):
        e = doc.entities[eid]
        if e.kind not in ("structural_column", "structural_beam"):
            continue
        p = e.params
        if str(p.get("role", "structural")) != "structural":
            continue
        construction = str(p.get("construction", "generic"))
        if construction not in ANALYSED:
            excluded.append(f"{e.name or e.kind} ({construction}): δεν αναλύεται εδώ")
            continue
        material = "steel" if construction == "steel" else "rc"
        kind = "column" if e.kind == "structural_column" else "beam"
        counters[kind] += 1
        name = f"{'Κ' if kind == 'column' else 'Δ'}{counters[kind]}"
        prof = str(p.get("profile") or DEFAULT_PROFILE[e.kind]) if material == "steel" else ""
        if kind == "column":
            x, y, z = (float(p[k]) for k in ("x", "y", "z"))
            rot = math.radians(float(p.get("rotation", 0.0)))
            members[eid] = Member(eid, kind, name, material, (x, y, z), (x, y, z + float(p["height"])),
                                  float(p["width"]), float(p["depth"]), prof, (math.cos(rot), math.sin(rot), 0.0))
        else:
            top = float(p["z"]) + float(p["height"])
            members[eid] = Member(eid, kind, name, material, (float(p["x1"]), float(p["y1"]), top),
                                  (float(p["x2"]), float(p["y2"]), top), float(p["width"]), float(p["height"]), prof)
    return members, excluded


def _project(p, a, b):
    ax, ay, az = a
    d = np.subtract(b, a)
    L2 = float(d @ d)
    t = float(np.dot(np.subtract(p, a), d) / L2)
    q = np.add(a, d * t)
    return t, math.hypot(p[0] - q[0], p[1] - q[1]), abs(p[2] - q[2])


def _cuts(m: Member, points, others):
    """Parameters along the member where it must be split."""
    ts = {0.0, 1.0}
    for p in points:
        t, dxy, dz = _project(p, m.p1, m.p2)
        if 1e-6 < t < 1 - 1e-6 and dxy <= TOL_XY and dz <= TOL_Z * (1 if m.kind == "beam" else 1e9):
            if m.kind == "column" and dxy > TOL_XY:
                continue
            ts.add(round(t, 6))
    if m.kind == "beam":
        for o in others:
            if o.kind != "beam" or o.id == m.id or abs(o.p1[2] - m.p1[2]) > TOL_Z:
                continue
            (x1, y1, _), (x2, y2, _) = m.p1, m.p2
            (x3, y3, _), (x4, y4, _) = o.p1, o.p2
            den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if abs(den) < 1e-12:
                continue
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
            u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / den
            if 1e-6 < t < 1 - 1e-6 and -1e-6 <= u <= 1 + 1e-6:
                ts.add(round(t, 6))
    ts = sorted(ts)
    out = []
    for a, b in zip(ts, ts[1:]):
        n = max(1, math.ceil((b - a) * m.length / MAX_ELEMENT - 1e-9)) if m.kind == "beam" else 1
        out += [a + (b - a) * k / n for k in range(n)]
    return out + [1.0]


def build_model(doc, settings):
    members, excluded = read_members(doc)
    warnings = []
    nodes: List[Tuple[float, float, float]] = []

    def node_for(p):
        for i, q in enumerate(nodes):
            if math.hypot(p[0] - q[0], p[1] - q[1]) <= TOL_XY and abs(p[2] - q[2]) <= TOL_Z:
                return i
        nodes.append(tuple(float(v) for v in p))
        return len(nodes) - 1

    # Columns first, so beam ends snap onto the column axes.
    ordered = sorted(members.values(), key=lambda m: (m.kind != "column", m.id))
    for m in ordered:
        node_for(m.p1); node_for(m.p2)
    ends = [m.p1 for m in members.values()] + [m.p2 for m in members.values()]
    elements: List[Element] = []
    weights = []
    for m in ordered:
        props, w = element_props(m, settings)
        ts = _cuts(m, ends, members.values())
        ids = [node_for(tuple(np.add(m.p1, np.subtract(m.p2, m.p1) * t))) for t in ts]
        for a, b in zip(ids, ids[1:]):
            if a == b:
                continue
            m.elements.append(len(elements))
            elements.append(Element(a, b, y_dir=m.y_dir if m.kind == "column" else None, tag=m.id, **props))
            weights.append(w)
    # Supports.
    supports = {}
    for e in doc.entities.values():
        if e.kind == "structural_support" and e.parent_id in members:
            m = members[e.parent_id]
            nid = node_for(m.p1 if str(e.params.get("member_end")) == "start" else m.p2)
            kind = str(e.params.get("support_type"))
            supports[nid] = (True,) * 6 if kind == "fixed" else ((True,) * 3 + (False,) * 3 if kind == "pinned"
                                                                 else (False, False, True, False, False, False))
    if not supports:
        use = {}
        for el in elements:
            use[el.n1] = use.get(el.n1, 0) + 1
            use[el.n2] = use.get(el.n2, 0) + 1
        for m in members.values():
            if m.kind == "column":
                nid = node_for(m.p1)
                if use.get(nid, 0) == 1:
                    supports[nid] = (True,) * 6
    base_z = min((nodes[n][2] for n in supports), default=0.0)
    # Drop elements not connected to a support (they would make the system singular).
    adj = {}
    for k, el in enumerate(elements):
        adj.setdefault(el.n1, []).append((el.n2, k)); adj.setdefault(el.n2, []).append((el.n1, k))
    seen, stack = set(supports), list(supports)
    while stack:
        n = stack.pop()
        for o, _k in adj.get(n, ()):
            if o not in seen:
                seen.add(o); stack.append(o)
    for m in members.values():
        if any(elements[k].n1 not in seen for k in m.elements):
            warnings.append(f"{m.name}: δεν στηρίζεται σε κολώνα/στήριξη — εξαιρείται")
    keep = [k for k, el in enumerate(elements) if el.n1 in seen and el.n2 in seen]
    remap = {old: new for new, old in enumerate(keep)}
    elements = [elements[k] for k in keep]
    weights = [weights[k] for k in keep]
    for m in list(members.values()):
        m.elements = [remap[k] for k in m.elements if k in remap]
        if not m.elements:
            del members[m.id]

    loads = {"G": {}, "Q": {}}

    def add(case, nid, fz):
        loads[case].setdefault(nid, np.zeros(6))[2] += fz

    for el, w in zip(elements, weights):
        L = math.dist(nodes[el.n1], nodes[el.n2])
        add("G", el.n1, -w * L / 2); add("G", el.n2, -w * L / 2)
    planes = sorted({round(m.p1[2], 2) for m in members.values() if m.kind == "beam"})
    occupancy = OCCUPANCIES[settings["occupancy"]]
    for zp in planes:
        beam_els = [k for m in members.values() if m.kind == "beam" and abs(m.p1[2] - zp) <= TOL_Z for k in m.elements]
        if not beam_els:
            continue
        walls_on = [w for w in doc.entities.values() if w.kind == "wall" and abs(float(w.params.get("z", 0.0)) - zp) <= 0.10]
        roof = not walls_on
        g = CONCRETE_WEIGHT * float(settings["slab_thickness"]) + (float(settings["roof_finishes"]) if roof else
                                                                  float(settings["finishes"]) + float(settings["partitions"]))
        q = ROOF_ACCESS[settings["roof_access"]][1] if roof else occupancy[1]
        _slab_loads(doc, zp, nodes, elements, beam_els, g, q, add, warnings)
        _wall_loads(walls_on, nodes, elements, beam_els, add)
    psi2 = occupancy[2]
    mass = {}
    for case, factor in (("G", 1.0), ("Q", psi2)):
        for nid, vec in loads[case].items():
            mass[nid] = mass.get(nid, 0.0) + max(0.0, -vec[2]) * factor / 9.81
    for nid in supports:
        mass.pop(nid, None)
    return Model(nodes, elements, members, supports, loads, mass, planes, base_z, warnings, excluded)


def _inside(poly, pts):
    x, y = pts[:, 0], pts[:, 1]
    hit = np.zeros(len(pts), bool)
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        cond = (y1 > y) != (y2 > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
        hit ^= cond & (x < xi)
    return hit


def _slab_loads(doc, zp, nodes, elements, beam_els, g, q, add, warnings, cell=0.10):
    levels = sorted(float(v) for v in doc.levels.values())
    below = [lz for lz in levels if lz < zp - 1.0]
    if not below:
        return
    try:
        faces = doc.active_room_faces(z=below[-1])
    except Exception:
        faces = []
    if not faces:
        warnings.append(f"Στάθμη +{zp:.2f}: δεν βρέθηκαν χώροι κάτω από την πλάκα — φορτία πλάκας δεν εφαρμόστηκαν")
        return
    A = np.array([nodes[elements[k].n1][:2] for k in beam_els])
    B = np.array([nodes[elements[k].n2][:2] for k in beam_els])
    for face in faces:
        poly = [(float(p[0]), float(p[1])) for p in face.polygon]
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        gx, gy = np.meshgrid(np.arange(min(xs) + cell / 2, max(xs), cell), np.arange(min(ys) + cell / 2, max(ys), cell))
        pts = np.column_stack([gx.ravel(), gy.ravel()])
        pts = pts[_inside(poly, pts)]
        if not len(pts):
            continue
        d = B - A
        L2 = np.maximum((d ** 2).sum(1), 1e-12)
        t = np.clip(((pts[:, None, :] - A[None]) * d[None]).sum(2) / L2[None], 0, 1)
        proj = A[None] + t[..., None] * d[None]
        dist = np.hypot(*(pts[:, None, :] - proj).transpose(2, 0, 1))
        near = dist.argmin(1)
        # Beams on or near this panel only (a slab bears on its edge beams).
        if dist[np.arange(len(pts)), near].min() > 1.0:
            warnings.append(f"Στάθμη +{zp:.2f}: χώρος χωρίς δοκούς στο περίγραμμα — φορτίο πλάκας δεν μεταφέρθηκε")
            continue
        a = cell * cell
        for case, w in (("G", g), ("Q", q)):
            for k in np.unique(near):
                sel = near == k
                tt = t[sel, k]
                el = elements[beam_els[k]]
                add(case, el.n1, -w * a * float((1 - tt).sum()))
                add(case, el.n2, -w * a * float(tt.sum()))


def wall_weight(w):
    t = float(w.params.get("thickness", 0.2))
    wt = str(w.params.get("wall_type", "generic"))
    per_m2 = 0.5 if "gypsum" in wt or "drywall" in wt else (2.1 if t <= 0.15 else 3.6)
    return per_m2 * float(w.params.get("height", 2.7))


def _wall_loads(walls, nodes, elements, beam_els, add):
    for w in walls:
        p = w.params
        a = np.array([float(p["x1"]), float(p["y1"])])
        b = np.array([float(p["x2"]), float(p["y2"])])
        L = float(np.linalg.norm(b - a))
        if L < 1e-6:
            continue
        u = (b - a) / L
        load = wall_weight(w)
        for k in beam_els:
            el = elements[k]
            p1, p2 = np.array(nodes[el.n1][:2]), np.array(nodes[el.n2][:2])
            e = p2 - p1
            le = float(np.linalg.norm(e))
            if le < 1e-9 or abs(abs(float(e @ u)) / le - 1) > 0.004:
                continue
            off = abs((p1 - a)[0] * u[1] - (p1 - a)[1] * u[0])
            if off > TOL_XY:
                continue
            s1, s2 = sorted((float((p1 - a) @ u), float((p2 - a) @ u)))
            overlap = max(0.0, min(L, s2) - max(0.0, s1))
            if overlap > 1e-6:
                add("G", el.n1, -load * overlap / 2)
                add("G", el.n2, -load * overlap / 2)
