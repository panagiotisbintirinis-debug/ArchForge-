"""Έλεγχοι ορθότητας (oracles) για τα bot — ιδιοκτήτης 07/11: «προχωράμε στον εσωτερικό έλεγχο».

Τα bot έλεγχαν ότι το πρόγραμμα δεν σπάει· εδώ ελέγχεται ότι **τα νούμερα στέκουν** απέναντι σε κανόνες που
βγαίνουν από τους ίδιους τους τύπους (όχι από ξανά-γράψιμο του ίδιου κώδικα):

* **Θερμικό φορτίο ∝ ΔT** (EN 12831 / ΤΟΤΕΕ: κάθε όρος είναι H·ΔT): με ΔT = 0 → 0 W· με 2ΔT → 2× W· και το σύνολο
  ίσο με το άθροισμα των όρων.
* **Όγκος θέρμανσης** = Σ εμβαδόν χώρου × ύψος των τοίχων **που τον περικλείουν** (ανεξάρτητος υπολογισμός).
* **U τοίχου**: πεπερασμένο, 0,05–6 W/m²K, και οι στρώσεις του να έχουν το πάχος του τοίχου (αλλιώς το U δεν
  αντιστοιχεί σε αυτό που σχεδιάστηκε).
* **Κουφώματα μέσα στον τοίχο τους** (κατά μήκος και καθ' ύψος).
* **Χώροι χωρίς επικάλυψη**: Σ εμβαδών χώρων ενός ορόφου = εμβαδόν της ένωσής τους.
* **Επιμέτρηση**: δάπεδο χώρου > 0 και όχι μεγαλύτερο από τον χώρο στους άξονες· τοίχοι = περίμετρος × ύψος − ανοίγματα.

Μόνο διαβάζουν το Document (ο παρατηρητής)· όπου χρειάζεται «άλλη θερμοκρασία» αλλάζουν την **είσοδο της
συνάρτησης** (τις υποθέσεις), ποτέ το έργο.  ``audit(doc)`` → ``[(τίτλος, λεπτομέρεια, extra)]``.
"""
from __future__ import annotations

import math

TOL_LEN = 0.002          # m: ανοχή μήκους (στρογγυλέματα σχεδίασης)
TOL_W = 3                # W: στρογγύλεμα κάθε όρου του θερμικού φορτίου (round ανά όρο)
TOL_VOL = 0.03           # 3%: όγκος θέρμανσης απέναντι στον ανεξάρτητο


def _wall_len(p):
    return math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))


def openings_in_host(doc):
    out = []
    for o in doc.entities.values():
        if o.kind not in ("door", "window", "opening") or not o.parent_id:
            continue
        w = doc.entities.get(o.parent_id)
        if w is None or w.kind != "wall":
            continue
        p, q = o.params, w.params
        L, half = _wall_len(q), float(p.get("width", 0.0)) / 2
        c = float(p.get("offset", 0.0))
        if c - half < -TOL_LEN or c + half > L + TOL_LEN:
            out.append(("κούφωμα έξω από τον τοίχο του", f"{o.kind} πλάτους {2 * half:.2f} m στη θέση {c:.2f} m "
                        f"τοίχου μήκους {L:.2f} m", o.id))
        sill = float(p.get("sill", 0.0)) if o.kind != "door" else 0.0
        top = sill + float(p.get("height", 0.0))
        if sill < -TOL_LEN or top > float(q["height"]) + TOL_LEN:
            out.append(("κούφωμα έξω από τον τοίχο του", f"{o.kind} {sill:.2f}–{top:.2f} m σε τοίχο ύψους "
                        f"{float(q['height']):.2f} m", o.id))
    return out


def heat_linear(doc):
    """Κάθε όρος του φορτίου είναι H·ΔT: ΔT=0 → 0· 2ΔT → 2×· σύνολο = Σ όρων."""
    import archforge.mep.heat_load as hl
    base = hl.heat_load(doc)
    out = []
    parts = sum(v for _n, v in base["parts"])
    if abs(parts - base["watts"]) > TOL_W * len(base["parts"]):
        out.append(("θερμικό φορτίο", f"σύνολο {base['watts']} W ≠ άθροισμα όρων {parts} W", str(base["parts"])))
    real = hl.assumptions
    try:
        for factor in (0.0, 2.0):
            def changed(d, real=real, factor=factor):
                a = dict(real(d))
                a["heat_theta_ext_winter"] = a["heat_theta_int"] - factor * (a["heat_theta_int"] - a["heat_theta_ext_winter"])
                return a
            hl.assumptions = changed
            r = hl.heat_load(doc)
            want = base["watts"] * factor
            if abs(r["watts"] - want) > TOL_W * len(base["parts"]) * max(1.0, factor):
                out.append(("θερμικό φορτίο όχι ανάλογο του ΔT",
                            f"ΔT×{factor:g}: {r['watts']} W αντί {want:.0f} W", f"{base['parts']} → {r['parts']}"))
    finally:
        hl.assumptions = real
    return out, base


def _enclosing_height(doc, poly, z):
    """Ύψος του χώρου: το μικρότερο ύψος των τοίχων πάνω στους οποίους πέφτουν οι πλευρές του (ανεξάρτητα)."""
    walls = [w for w in doc.entities.values() if w.kind == "wall" and w.visible
             and abs(float(w.params.get("z", 0.0)) - z) < 0.05]
    hs = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        mx, my = (float(a[0]) + float(b[0])) / 2, (float(a[1]) + float(b[1])) / 2
        for w in walls:
            p = w.params
            x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy
            if L2 < 1e-9:
                continue
            t = ((mx - x1) * dx + (my - y1) * dy) / L2
            if -0.01 <= t <= 1.01 and math.hypot(mx - (x1 + t * dx), my - (y1 + t * dy)) <= float(p["thickness"]) / 2 + 0.01:
                hs.append(float(p["height"]))
                break
    return min(hs) if hs else None


def heat_volume(doc, base):
    from archforge.mep.heat_load import _polygon_area, _storeys
    vol = 0.0
    for z in _storeys(doc):
        for f in doc.active_room_faces(z=z):
            h = _enclosing_height(doc, f.polygon, z)
            if h is not None:
                vol += _polygon_area(f.polygon) * h
    got = float(base.get("volume_m3", 0.0))
    if vol > 1.0 and abs(got - vol) > max(0.5, TOL_VOL * vol):
        return [("όγκος θέρμανσης", f"ο αερισμός μετρά {got:.1f} m³, οι χώροι × το ύψος των τοίχων τους δίνουν "
                 f"{vol:.1f} m³ ({(got - vol) / vol:+.0%})", "")]
    return []


def wall_u(doc):
    from archforge.architecture.wall_types import indicative_u, layers
    from archforge.construction.isotex import BLOCKS, code_of_wall_type
    out, seen = [], set()
    for w in doc.entities.values():
        if w.kind != "wall" or not w.visible:
            continue
        wt = w.params.get("wall_type", "generic")
        t = round(float(w.params["thickness"]), 3)
        if (wt, t) in seen:
            continue
        seen.add((wt, t))
        u = indicative_u(wt, doc)
        if u is None:
            continue
        if not math.isfinite(u) or not 0.05 <= u <= 6.0:
            out.append(("U τοίχου εκτός ορίων", f"«{wt}»: U = {u}", ""))
        code = code_of_wall_type(wt)
        if code and BLOCKS[code][6] is not None:
            continue                                  # δημοσιευμένο U του block, όχι από στρώσεις
        ls = layers(wt, doc) or []
        d = sum(float(x[1]) for x in ls)
        if ls and abs(d - t) > 0.015:
            out.append(("U με άλλο πάχος από τον τοίχο",
                        f"«{wt}»: το U ({u:.2f}) βγαίνει από στρώσεις {d * 100:.1f} cm, ο τοίχος έχει {t * 100:.1f} cm", ""))
    return out


def rooms_overlap(doc):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from archforge.mep.heat_load import _storeys
    out = []
    for z in _storeys(doc):
        polys = []
        for f in doc.active_room_faces(z=z):
            g = Polygon([(float(x), float(y)) for x, y, *_ in f.polygon])
            polys.append(g if g.is_valid else g.buffer(0))
        if len(polys) < 2:
            continue
        s, u = sum(g.area for g in polys), unary_union(polys).area
        if s - u > 0.05:
            out.append(("χώροι επικαλύπτονται", f"όροφος {z:+.2f}: Σ χώρων {s:.2f} m², ένωση {u:.2f} m²", ""))
    return out


def takeoff_sane(doc):
    from archforge.quantities.takeoff import take_off
    out = []
    for r in take_off(doc)["rooms"]:
        w = r["perimeter_m"] * r["height_m"] - r["openings_m2"]
        if abs(max(0.0, w) - r["walls_m2"]) > 0.05:
            out.append(("επιμέτρηση", f"{r['storey']} «{r['name']}»: τοίχοι {r['walls_m2']} m² ≠ περίμετρος × ύψος − "
                        f"ανοίγματα {w:.2f} m²", ""))
        if r["floor_m2"] < 0 or r["walls_m2"] < 0:
            out.append(("επιμέτρηση", f"{r['storey']} «{r['name']}»: αρνητική ποσότητα", str(r)))
    return out


def audit(doc):
    """Όλοι οι έλεγχοι· ένα σφάλμα σε έλεγχο είναι κι αυτό εύρημα (ποτέ σιωπηλά)."""
    out = []
    checks = [("κουφώματα", openings_in_host), ("U τοίχων", wall_u), ("χώροι", rooms_overlap),
              ("επιμέτρηση", takeoff_sane), ("όγκος τοίχων", wall_volume)]
    for name, fn in checks:
        try:
            out += fn(doc)
        except Exception as exc:                                    # noqa: BLE001
            out.append(("έλεγχος ορθότητας κατέρρευσε", f"{name}: {type(exc).__name__}: {exc}", ""))
    try:
        for kind, (n, o, inv) in sorted(mesh_report(doc).items()):
            if o:
                out.append(("3D στερεό ανοιχτό", f"{kind}: {o} από {n} με τρύπες (ακμές χωρίς δεύτερο τρίγωνο)", ""))
            if inv:
                out.append(("3D στερεό ανάποδα", f"{kind}: {inv} από {n} με τις όψεις προς τα μέσα", ""))
    except Exception as exc:                                        # noqa: BLE001
        out.append(("έλεγχος ορθότητας κατέρρευσε", f"3D στερεά: {type(exc).__name__}: {exc}", ""))
    try:
        found, base = heat_linear(doc)
        out += found + heat_volume(doc, base)
    except Exception as exc:                                        # noqa: BLE001
        out.append(("έλεγχος ορθότητας κατέρρευσε", f"θερμικό φορτίο: {type(exc).__name__}: {exc}", ""))
    return out


# -- 3D στερεά: κλειστά (κάθε ακμή σε δύο τρίγωνα) και με τις όψεις προς τα έξω (θετικός όγκος) ---------------
def mesh_report(doc):
    """``{kind: (πλήθος, ανοιχτά, ανάποδα)}`` για τα σώματα της 3D (τα ίδια που γράφουν IFC / STL), με τον ελεγκτή
    του προγράμματος (``geometry/mesh_validation.validate_mesh``)."""
    from archforge.exchange.ifc import _bodies
    from archforge.geometry.mesh_validation import open_length, validate_mesh, welded
    out = {}
    for eid, m in _bodies(doc).items():
        e = doc.entities.get(eid)
        kind = e.kind if e is not None else "?"
        n, o, inv = out.get(kind, (0, 0, 0))
        r = validate_mesh(welded(m))
        out[kind] = (n + 1, o + (r.boundary_edges > 0 and open_length(m) > 0.001), inv + r.inside_out)
    return out

def wall_volume(doc):
    """Όγκος κάθε τοίχου στο 3D = μήκος άξονα × ύψος × πάχος − ανοίγματα, με ανοχή τον όγκο των γωνιών του
    (t_A × t_B × H σε κάθε άκρο που ακουμπά άλλον τοίχο: φάλτσο / Τ) — προδιαγραφή 07/11."""
    from archforge.exchange.ifc import _bodies
    from archforge.geometry.mesh_validation import validate_mesh, welded
    bodies = _bodies(doc)
    walls = [e for e in doc.entities.values() if e.kind == "wall" and e.visible]
    out = []
    for w in walls:
        m = bodies.get(w.id)
        if m is None:
            continue
        r = validate_mesh(welded(m))
        if not r.watertight:
            continue                                   # «3D στερεό ανοιχτό» το λέει ήδη
        q = w.params
        L, H, t = _wall_len(q), float(q["height"]), float(q["thickness"])
        holes = sum(float(o.params.get("width", 0.0)) * float(o.params.get("height", 0.0)) * t
                    for o in doc.entities.values() if o.kind in ("door", "window", "opening") and o.parent_id == w.id)
        corners = 0.0
        for ex, ey in ((float(q["x1"]), float(q["y1"])), (float(q["x2"]), float(q["y2"]))):
            for o in walls:
                op = o.params
                if o is w or abs(float(op.get("z", 0.0)) - float(q.get("z", 0.0))) > 0.05:
                    continue
                ax, ay, bx, by = (float(op[k]) for k in ("x1", "y1", "x2", "y2"))
                dx, dy = bx - ax, by - ay
                LL = dx * dx + dy * dy or 1.0
                k = max(0.0, min(1.0, ((ex - ax) * dx + (ey - ay) * dy) / LL))
                if math.hypot(ex - ax - k * dx, ey - ay - k * dy) <= max(t, float(op["thickness"])):
                    corners += t * float(op["thickness"]) * H
        nominal = L * H * t - holes
        if abs(r.signed_volume - nominal) > corners + 1e-3:
            out.append(("όγκος τοίχου", f"«{w.name or w.id[:8]}»: 3D {r.signed_volume:.3f} m³, αναμενόμενο "
                        f"{nominal:.3f} ± {corners:.3f} m³ (γωνίες)", w.id))
    return out


def ifc_file_check(doc, path):
    """Το αρχείο IFC απέναντι στο 3D του προγράμματος, στοιχείο προς στοιχείο (Tag = id): κάθε σώμα γράφτηκε,
    όρια στον χώρο ≤ 5 mm, όγκος ≤ 1 % — και για ό,τι δεν ξαναδιαβάζει η εισαγωγή (πλάκες, δοκοί, στέγες …)."""
    import ifcopenshell
    import ifcopenshell.geom
    from archforge.exchange.ifc import _bodies
    from archforge.exchange.mapping import SKIP
    from archforge.geometry.mesh import MeshPayload
    from archforge.geometry.mesh_validation import validate_mesh, welded
    s = ifcopenshell.geom.settings()
    s.set(s.USE_WORLD_COORDS, True)
    f = ifcopenshell.open(path)
    bodies = {k: v for k, v in _bodies(doc).items() if k in doc.entities and doc.get(k).kind not in SKIP}
    seen, out = set(), []
    for el in f.by_type("IfcProduct"):
        tag = getattr(el, "Tag", None)
        if not tag or tag not in bodies or tag in seen:
            continue
        seen.add(tag)
        kind = doc.get(tag).kind
        try:
            sh = ifcopenshell.geom.create_shape(s, el)
        except Exception as exc:                                    # noqa: BLE001
            out.append(("IFC αρχείο", f"{kind}: χωρίς γεωμετρία στο IFC ({exc})", tag)); continue
        v, fa = sh.geometry.verts, sh.geometry.faces
        V = [(v[i], v[i + 1], v[i + 2]) for i in range(0, len(v), 3)]
        T = [(fa[i], fa[i + 1], fa[i + 2]) for i in range(0, len(fa), 3)]
        m = bodies[tag]
        err = max(abs(min(a[k] for a in m.vertices) - min(b[k] for b in V)) +
                  abs(max(a[k] for a in m.vertices) - max(b[k] for b in V)) for k in range(3))
        if err > 0.005:
            out.append(("IFC αρχείο", f"{kind}: όρια στον χώρο διαφέρουν {err * 1000:.0f} mm από το 3D", tag)); continue
        r = validate_mesh(welded(m))
        if r.watertight and abs(r.signed_volume) > 1e-6 and T:
            vol = abs(validate_mesh(welded(MeshPayload(tuple(V), tuple(T), ("x",) * len(T)))).signed_volume)
            if abs(vol - abs(r.signed_volume)) > 0.01 * abs(r.signed_volume):
                out.append(("IFC αρχείο", f"{kind}: όγκος {vol:.3f} m³ στο IFC, {abs(r.signed_volume):.3f} m³ στο 3D", tag))
    missing = sorted({doc.get(k).kind for k in set(bodies) - seen})
    if missing:
        out.append(("IFC αρχείο", f"{len(set(bodies) - seen)} στοιχεία με 3D σώμα δεν γράφτηκαν", str(missing)))
    return out


# -- IFC: εξαγωγή → εισαγωγή σε νέο έργο (ό,τι διαβάζει η εισαγωγή: όροφοι, τοίχοι, κουφώματα) ------------------
def _r(v):
    return round(float(v), 2)


def ifc_signature(doc):
    """``(τοίχοι, κουφώματα)`` ως πολυσύνολα, ανεξάρτητα από ids και φορά τοίχου: τοίχος = όροφος, άκρα, πάχος,
    ύψος, σύνθεση· κούφωμα = είδος, θέση στον χώρο, πλάτος, ύψος, ποδιά."""
    from collections import Counter
    walls = {e.id: e for e in doc.entities.values() if e.kind == "wall" and e.visible}
    W = Counter()
    for w in walls.values():
        p = w.params
        ends = tuple(sorted([(_r(p["x1"]), _r(p["y1"])), (_r(p["x2"]), _r(p["y2"]))]))
        W[(_r(p.get("z", 0.0)),) + ends + (_r(p["thickness"]), _r(p["height"]), p.get("wall_type", "generic"))] += 1
    O = Counter()
    for e in doc.entities.values():
        if e.kind not in ("door", "window", "opening") or e.parent_id not in walls:
            continue
        p = walls[e.parent_id].params
        L = _wall_len(p) or 1.0
        t = float(e.params.get("offset", 0.0)) / L
        x = float(p["x1"]) + t * (float(p["x2"]) - float(p["x1"]))
        y = float(p["y1"]) + t * (float(p["y2"]) - float(p["y1"]))
        sill = 0.0 if e.kind == "door" else _r(e.params.get("sill", 0.0))
        O[(e.kind, _r(x), _r(y), _r(e.params["width"]), _r(e.params["height"]), sill)] += 1
    return W, O


def ifc_compare(before, after):
    """``[(τίτλος, λεπτομέρεια, extra)]`` όσα άλλαξαν στην επανεισαγωγή."""
    out = []
    for name, a, b in (("τοίχοι", before[0], after[0]), ("κουφώματα", before[1], after[1])):
        if a != b:
            lost, new = a - b, b - a
            out.append(("IFC εξαγωγή → εισαγωγή", f"{name}: {sum(a.values())} πριν, {sum(b.values())} μετά · "
                        f"{sum(lost.values())} χάθηκαν/άλλαξαν", f"χάθηκαν {list(lost)[:4]} · νέα {list(new)[:4]}"))
    return out


if __name__ == "__main__":
    import sys
    from archforge.core.model import Document
    for path in sys.argv[1:]:
        d = Document.load(path)
        res = audit(d)
        print(path, len(res))
        for t, detail, _x in res[:40]:
            print("  ", t, "—", detail)
