"""Εισαγωγή DXF ως **επεξεργάσιμο σχέδιο 2D** (κενό 3 της αποτύπωσης δυνατοτήτων, 06/11).

Το «Σχέδιο μηχανικού ως υπόβαθρο» (``project/underlay.py``) κρατά το DXF ως γραμμές αναφοράς. Εδώ κάθε γραμμή, τόξο,
κύκλος, πολυγραμμή, κείμενο και γέμισμα γίνεται στοιχείο ``drafting`` (``architecture/drafting.py``) του ενεργού ορόφου:
επιλέγεται, μετακινείται, σβήνεται, βγαίνει ξανά στο DXF / PDF. Όλη η εισαγωγή = **μία αναίρεση**.

* LINE, LWPOLYLINE / POLYLINE (κλειστή → πολύγωνο· καμπύλα τμήματα / bulge → σημεία), CIRCLE, ARC, TEXT, MTEXT,
  HATCH (εξωτερικά όρια → πολύγωνο με γέμισμα), ELLIPSE / SPLINE (→ πολυγραμμή), INSERT (τα blocks αναλύονται στα
  στοιχεία τους, με τη θέση / κλίμακα / περιστροφή τους)· DIMENSION / LEADER → οι γραμμές, τα βέλη και το κείμενό τους
  (σχέδιο, όχι συνδεδεμένη διάσταση).
* Μονάδες: από το ``$INSUNITS`` του αρχείου ή όπως τις δώσει ο χρήστης (mm / cm / m).
* Τύπος γραμμής (DASHED, DOT, DASHDOT / CENTER…) → συνεχής / διακεκομμένη / στικτή / αξονική· πάχος από το lineweight.
* Ό,τι δεν διαβάζεται (DIMENSION, 3D στερεά, εικόνες, …) μετριέται και λέγεται — τίποτα δεν χάνεται σιωπηλά.
* DWG: κλειστή μορφή της Autodesk· δεν διαβάζεται. Αποθηκεύστε ως DXF από το CAD.
"""
from __future__ import annotations

import math

UNITS = {"mm": 0.001, "cm": 0.01, "m": 1.0}
INSUNITS = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 14: 0.1}     # in, ft, mm, cm, m, dm (DXF $INSUNITS codes)
MAX_ENTITIES = 20000


def _style(linetype):
    lt = str(linetype or "").upper()
    if "DASHDOT" in lt or "CENTER" in lt or "AXIS" in lt or "PHANTOM" in lt:
        return "dashdot"
    if "DOT" in lt:
        return "dotted"
    if "DASH" in lt or "HIDDEN" in lt:
        return "dashed"
    return "solid"


def _weight(lw):
    from archforge.architecture.drafting import WEIGHTS
    try:
        v = int(lw)
    except (TypeError, ValueError):
        return 0.25
    if v <= 0:                                        # BYLAYER / BYBLOCK / DEFAULT
        return 0.25
    return min(WEIGHTS, key=lambda w: abs(w - v / 100.0))


def units_of(doc_dxf):
    """Metres per drawing unit from ``$INSUNITS``, or None when the file does not say."""
    try:
        code = int(doc_dxf.header.get("$INSUNITS", 0))
    except (TypeError, ValueError):
        return None
    return INSUNITS.get(code)


def read(path, unit=None, z=0.0, layers=None, to_origin=False):
    """``{"entities": [drafting Entity], "counts": {shape: n}, "skipped": {dxftype: n}, "layers": {name: n},
    "m_per_unit", "bounds"}`` — nothing is added to a project here."""
    import ezdxf
    from ezdxf import recover
    from archforge.architecture import drafting as DR
    try:
        dxf = ezdxf.readfile(str(path))
    except ezdxf.DXFStructureError:
        dxf, _auditor = recover.readfile(str(path))
    k = UNITS[unit] if unit else (units_of(dxf) or 1.0)
    msp = dxf.modelspace()
    raw, skipped, layer_count = [], {}, {}

    def keep(e):
        name = str(e.dxf.get("layer", "0"))
        layer_count[name] = layer_count.get(name, 0) + 1
        return layers is None or name in layers

    def walk(entities, depth=0):
        for e in entities:
            t = e.dxftype()
            if t in ("INSERT", "DIMENSION", "LEADER", "MLEADER") and depth < 8:
                # Blocks and dimensions: their own lines / arrows / texts, as drawn.
                try:
                    walk(list(e.virtual_entities()), depth + 1)
                except Exception:                         # noqa: BLE001 — a block that cannot be exploded is counted
                    skipped[t] = skipped.get(t, 0) + 1
                continue
            if str(e.dxf.get("layer", "")).upper() == "DEFPOINTS":
                continue                                   # the dimensions' construction points: never printed
            if keep(e):
                raw.append(e)
            if len(raw) > MAX_ENTITIES:
                raise ValueError(f"το DXF έχει πάνω από {MAX_ENTITIES} στοιχεία: χωρίστε το ή διαλέξτε layers")
    walk(msp)

    out, counts = [], {}

    def style_of(e):
        return {"style": _style(e.dxf.get("linetype", "") if e.dxf.get("linetype", "BYLAYER") != "BYLAYER" else
                                _layer_linetype(dxf, e)), "weight": _weight(e.dxf.get("lineweight", -1))}

    def add(shape, **params):
        try:
            out.append(DR.entity(shape, z, **params))
            counts[shape] = counts.get(shape, 0) + 1
        except (ValueError, KeyError):
            skipped["εκφυλισμένα"] = skipped.get("εκφυλισμένα", 0) + 1

    def pts2(seq):
        return [(float(p[0]) * k, float(p[1]) * k) for p in seq]

    for e in raw:
        t = e.dxftype()
        try:
            if t == "LINE":
                add("line", points=pts2([e.dxf.start, e.dxf.end]), **style_of(e))
            elif t in ("LWPOLYLINE", "POLYLINE"):
                if t == "POLYLINE" and (e.is_3d_polyline is False and e.is_2d_polyline is False):
                    skipped[t + " (πλέγμα)"] = skipped.get(t + " (πλέγμα)", 0) + 1
                    continue
                from ezdxf import path as dxfpath
                pts = pts2([(v.x, v.y) for v in dxfpath.make_path(e).flattening(0.01 / k if k else 0.01)])
                closed = bool(e.closed if t == "LWPOLYLINE" else e.is_closed)
                if closed and len(pts) >= 2 and math.dist(pts[0], pts[-1]) < 1e-9:
                    pts = pts[:-1]
                if closed and len(pts) >= 3:
                    add("polygon", points=pts, **style_of(e))
                else:
                    add("polyline" if len(pts) > 2 else "line", points=pts, **style_of(e))
            elif t == "CIRCLE":
                c = e.dxf.center
                add("circle", cx=c.x * k, cy=c.y * k, r=e.dxf.radius * k, **style_of(e))
            elif t == "ARC":
                c = e.dxf.center
                add("arc", cx=c.x * k, cy=c.y * k, r=e.dxf.radius * k, a0=e.dxf.start_angle, a1=e.dxf.end_angle, **style_of(e))
            elif t in ("ELLIPSE", "SPLINE"):
                from ezdxf import path as dxfpath
                pts = pts2([(v.x, v.y) for v in dxfpath.make_path(e).flattening(0.01 / k if k else 0.01)])
                add("polyline", points=pts, **style_of(e))
            elif t in ("TEXT", "MTEXT"):
                if t == "TEXT":
                    text, at, h = e.dxf.text, e.dxf.insert, e.dxf.get("height", 2.5)
                else:
                    text, at, h = e.plain_text(), e.dxf.insert, e.dxf.get("char_height", 2.5)
                text = " ".join(str(text).split())
                if text:
                    # The insertion of a TEXT is its baseline: the drafting text hangs from its top-left, so lift it.
                    ang = float(e.dxf.get("rotation", 0.0))
                    lift = h if t == "TEXT" else 0.0
                    x = at.x - lift * math.sin(math.radians(ang))
                    y = at.y + lift * math.cos(math.radians(ang))
                    add("text", x=x * k, y=y * k, text=text, height=max(0.01, h * k), angle=ang)
            elif t == "HATCH":
                solid = bool(e.dxf.get("solid_fill", 0))
                for path in e.paths:
                    if hasattr(path, "vertices"):
                        pts = pts2([(v[0], v[1]) for v in path.vertices])
                    else:
                        from ezdxf import path as dxfpath
                        pts = pts2([(v.x, v.y) for v in dxfpath.from_hatch_edge_path(path).flattening(0.01 / k if k else 0.01)])
                    if len(pts) >= 2 and math.dist(pts[0], pts[-1]) < 1e-9:
                        pts = pts[:-1]
                    if len(pts) >= 3:
                        add("polygon", points=pts, hatch="solid" if solid else "diagonal", weight=0.13)
            else:
                skipped[t] = skipped.get(t, 0) + 1
        except Exception:                                 # noqa: BLE001 — one bad entity is counted, the rest come in
            skipped[t] = skipped.get(t, 0) + 1
    bounds = _bounds(out)
    if to_origin and bounds is not None:
        from archforge.architecture.drafting import translated
        for e in out:
            e.params = translated(e.params, -bounds[0], -bounds[1])
        bounds = _bounds(out)
    return {"entities": out, "counts": counts, "skipped": skipped, "layers": layer_count, "m_per_unit": k,
            "bounds": bounds}


def _layer_linetype(dxf, e):
    try:
        return dxf.layers.get(e.dxf.get("layer", "0")).dxf.get("linetype", "CONTINUOUS")
    except Exception:                                     # noqa: BLE001
        return "CONTINUOUS"


def _bounds(entities):
    from archforge.architecture.drafting import outline
    xs, ys = [], []
    for e in entities:
        p = e.params
        if p["shape"] in ("circle", "arc"):
            xs += [p["cx"] - p["r"], p["cx"] + p["r"]]; ys += [p["cy"] - p["r"], p["cy"] + p["r"]]
        else:
            pts, _c = outline(p)
            xs += [q[0] for q in pts]; ys += [q[1] for q in pts]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def import_command(doc, path, unit=None, layers=None, to_origin=False):
    """``(AddEntities, report)``: the drawing on the active storey, one undo."""
    from archforge.core.commands import AddEntities
    r = read(path, unit, float(doc.work_plane.origin[2]), layers, to_origin)
    if not r["entities"]:
        raise ValueError("το DXF δεν έχει γραμμές, τόξα, κύκλους, κείμενα ή γεμίσματα που να διαβάζονται"
                         + (f" (δεν διαβάστηκαν: {', '.join(f'{k} ×{n}' for k, n in r['skipped'].items())})" if r["skipped"] else ""))
    cmd = AddEntities(r["entities"])
    cmd.label = "Εισαγωγή DXF ως σχέδιο 2D"
    return cmd, r


def report_text(r):
    """«412 στοιχεία: 300 γραμμές, 40 τόξα … · δεν διαβάστηκαν: DIMENSION ×12»."""
    from archforge.architecture.drafting import SHAPES
    n = sum(r["counts"].values())
    parts = ", ".join(f"{SHAPES[s].lower()} ×{c}" for s, c in sorted(r["counts"].items(), key=lambda x: -x[1]))
    text = f"{n} στοιχεία ({parts})"
    if r["bounds"]:
        x0, y0, x1, y1 = r["bounds"]
        text += f" · {x1 - x0:.2f} × {y1 - y0:.2f} m".replace(".", ",")
    if r["skipped"]:
        text += " · δεν διαβάστηκαν: " + ", ".join(f"{k} ×{v}" for k, v in r["skipped"].items())
    return text
