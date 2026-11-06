"""Φύλλα σχεδίων (κενό 4 της αποτύπωσης δυνατοτήτων, 06/11): πολλές προβολές σε ένα φύλλο A4…A0, με πινακίδα.

Ένα στοιχείο ``sheet`` ανά φύλλο: ``title``, ``number`` (π.χ. «Α-01»), ``paper`` A4 / A3 / A2 / A1 / A0, ``orientation``
landscape / portrait και ``views``: λίστα από ``{"type", "ref", "scale", "title"}``:

* ``plan``: κάτοψη του ορόφου με υψόμετρο ``ref`` (ίδια σχεδίαση με το PDF κατόψεων: ``output/pdf.draw_plan``)·
* ``section``: η τομή του ``section_line`` ``ref`` (ίδια δεδομένα με την καρτέλα τομής: ``output/section_cut``)·
* ``list``: μια ζωντανή λίστα (``ref`` = openings / envelope / rooms / circuits / clashes, ``quantities/schedules``)·
* ``note``: κείμενο (``text``).

Οι προβολές μπαίνουν αυτόματα σε σειρές (αριστερά → δεξιά, πάνω → κάτω) με τίτλο και κλίμακα από κάτω· ό,τι δεν χωρά
λέγεται. Η πινακίδα παίρνει τα Στοιχεία έργου (τίτλος, πελάτης, θέση, μηχανικός). Η κάτοψη / τομή είναι πάντα του
μοντέλου τη στιγμή της εξαγωγής — το φύλλο κρατά μόνο τι δείχνει και σε ποια κλίμακα.
"""
from __future__ import annotations

import datetime

PAPER = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0), "A1": (841.0, 594.0), "A0": (1189.0, 841.0)}
ORIENTATIONS = {"landscape": "Οριζόντιο", "portrait": "Κατακόρυφο"}
VIEW_TYPES = {"plan": "Κάτοψη", "section": "Τομή", "list": "Λίστα", "note": "Σημείωση"}
SCALES = (20, 50, 100, 200, 500)
MARGIN = 10.0                  # mm frame of the sheet (ISO 5457: 20 mm on the binding side is the office's choice)
TITLE_W, TITLE_H = 180.0, 32.0
GAP = 8.0                      # mm between views
LABEL_H = 7.0                  # mm under each view for its title and scale
LIST_ROW_H, LIST_SIZE = 5.0, 6.5
LIST_MAX_ROWS = 40
# The columns a list shows on a sheet (the full list stays in Λίστες / PDF / Excel): the schedule a drawing carries.
SHEET_COLUMNS = {"openings": ("mark", "kind", "typology", "storey", "width", "height", "sill", "area", "glazing",
                              "uw_used", "shading"),
                 "envelope": ("element", "storey", "type", "quantity", "unit", "u", "umax", "ok"),
                 "clashes": ("group", "a", "b", "depth", "storey", "note")}


def validate(p):
    """Checked copy of a sheet's params (called by the model's schema)."""
    out = dict(p)
    out["title"] = str(out.get("title") or "Φύλλο").strip() or "Φύλλο"
    out["number"] = str(out.get("number") or "").strip()
    if out.get("paper", "A3") not in PAPER:
        raise ValueError(f"paper must be one of {', '.join(PAPER)}")
    out["paper"] = out.get("paper", "A3")
    if out.get("orientation", "landscape") not in ORIENTATIONS:
        raise ValueError("orientation must be landscape or portrait")
    out["orientation"] = out.get("orientation", "landscape")
    views = []
    for v in out.get("views") or ():
        v = dict(v)
        if v.get("type") not in VIEW_TYPES:
            raise ValueError(f"view type must be one of {', '.join(VIEW_TYPES)}")
        if v["type"] in ("plan", "section"):
            if v.get("scale") is not None and int(v["scale"]) not in SCALES:
                raise ValueError(f"scale must be one of {SCALES}")
            v["scale"] = None if v.get("scale") is None else int(v["scale"])
        if v["type"] == "plan":
            v["ref"] = float(v.get("ref", 0.0))
        elif v["type"] == "note":
            v["text"] = str(v.get("text", "")).strip()
            if not v["text"]:
                raise ValueError("σημείωση χωρίς κείμενο")
        else:
            v["ref"] = str(v.get("ref", ""))
        views.append(v)
    out["views"] = views
    return out


def paper_mm(params):
    w, h = PAPER[params.get("paper", "A3")]
    return (w, h) if params.get("orientation", "landscape") == "landscape" else (h, w)


def new_sheet(doc, title="Φύλλο", paper="A3", orientation="landscape", views=()):
    """A new ``sheet`` Entity with the next number «Α-0n»."""
    from archforge.core.model import Entity
    n = sum(1 for e in doc.entities.values() if e.kind == "sheet") + 1
    return Entity("sheet", validate({"title": title, "number": f"Α-{n:02d}", "paper": paper, "orientation": orientation,
                                     "views": list(views)}), name=f"Φύλλο Α-{n:02d}")


# ------------------------------------------------------------------ what each view is and how big

def _storey(doc, z):
    from archforge.assistant.understanding import read_drawing
    return next((s for s in read_drawing(doc)["storeys"] if abs(float(s["z"]) - float(z)) < 1e-3), None)


def _storey_label(doc, z):
    from archforge.core.cameras import storey_name
    from archforge.core.storey_names import level_name
    name = storey_name(doc, float(z))
    return level_name(name) if name else f"{float(z):+.2f}".replace(".", ",")


def _section_data(doc, ref):
    from archforge.output.section_cut import cut_section
    e = doc.entities.get(ref)
    if e is None or e.kind != "section_line":
        return None, None
    return e, cut_section(doc, e.params)


def greek_upper(text):
    """Capitals without accents, as Greek typography writes them («Κάτοψη Ισογείου» → «ΚΑΤΟΨΗ ΙΣΟΓΕΙΟΥ»); the
    diaeresis stays (Ϊ, Ϋ)."""
    import unicodedata
    out = []
    for ch in unicodedata.normalize("NFD", str(text).upper()):
        if unicodedata.category(ch) == "Mn" and ch != "\u0308":
            continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def view_title(doc, v):
    if v.get("title"):
        return v["title"]
    if v["type"] == "plan":
        return f"Κάτοψη {_storey_label(doc, v['ref'])}"
    if v["type"] == "section":
        e = doc.entities.get(v["ref"])
        return f"{e.name}" if e is not None and e.name else "Τομή"
    if v["type"] == "list":
        from archforge.ui.live_lists import NAMES
        return NAMES.get(v["ref"], v["ref"])
    return ""


def measure(doc, v, room=None):
    """``{"w", "h", "scale", "data", "problem"}`` mm of a view's drawing (without its label). ``room`` = the largest
    (w, h) it may take, for the automatic scale."""
    from archforge.output import pdf as P
    out = {"w": 0.0, "h": 0.0, "scale": v.get("scale"), "data": None, "problem": None}
    if v["type"] == "plan":
        st = _storey(doc, v["ref"])
        if st is None or not st["walls"]:
            out["problem"] = "ο όροφος δεν έχει τοίχους"
            return out
        ext = P.plan_extent(doc, st)
        scale = v.get("scale") or (P.fit_scale(ext, *room) if room else 100)
        k = 1000.0 / scale
        out.update(w=(ext[2] - ext[0]) * k, h=(ext[3] - ext[1]) * k, scale=scale, data=st)
    elif v["type"] == "section":
        e, data = _section_data(doc, v["ref"])
        if data is None:
            out["problem"] = "η τομή δεν υπάρχει πια"
            return out
        u0, z0, u1, z1 = data["bounds"]
        ext = (u0 - 1.0, z0 - 1.0, u1 + 1.0, z1 + 1.0)
        scale = v.get("scale") or (P.fit_scale(ext, *room) if room else 100)
        k = 1000.0 / scale
        out.update(w=(ext[2] - ext[0]) * k, h=(ext[3] - ext[1]) * k, scale=scale, data=(ext, data))
    elif v["type"] == "list":
        from archforge.quantities import schedules as S
        if v["ref"] not in S.LISTS:
            out["problem"] = "άγνωστη λίστα"
            return out
        data = S.LISTS[v["ref"]](doc)
        keep = SHEET_COLUMNS.get(v["ref"])
        if keep:
            data = {**data, "columns": [c for c in data["columns"] if c[0] in keep]}
        header, rows = S.table(data)
        widths = _col_widths(header, rows)
        shown = rows[:LIST_MAX_ROWS]
        out.update(w=sum(widths), h=(len(shown) + 1) * LIST_ROW_H, data=(header, shown, widths, len(rows) - len(shown)))
    else:
        lines = v["text"].splitlines() or [""]
        out.update(w=min(180.0, max(30.0, max(len(t) for t in lines) * 2.4)), h=len(lines) * 5.0 + 2, data=lines)
    return out


def _col_widths(header, rows):
    from archforge.quantities.schedules import _fmt
    out = []
    for i, h in enumerate(header):
        longest = max([len(str(h))] + [len(_fmt(r[i])) for r in rows[:LIST_MAX_ROWS]])
        out.append(min(45.0, 4.0 + longest * 1.45))
    return out


def layout(doc, params):
    """``{"placed": [(view, measure, (x, y))], "problems": [(view, text)], "paper": (w, h), "area": (x, y, w, h),
    "scale"}``: the views in rows inside the frame, above the title block. Plans and sections without their own scale
    share one: the largest drawing (1:20 → 1:500) at which every view of the sheet fits."""
    auto = [i for i, v in enumerate(params["views"]) if v["type"] in ("plan", "section") and not v.get("scale")]
    if auto:
        best = None
        for scale in SCALES:
            views = [dict(v, scale=scale) if i in auto else v for i, v in enumerate(params["views"])]
            lay = _layout(doc, dict(params, views=views))
            if not lay["problems"] or (best is None and scale == SCALES[-1]):
                best = lay
                break
            # keep the first scale with the fewest problems as the fallback
            if best is None or len(lay["problems"]) < len(best["problems"]):
                best = lay
        best["scale"] = best["placed"][0][1]["scale"] if best["placed"] else None
        return best
    lay = _layout(doc, params)
    lay["scale"] = None
    return lay


def _layout(doc, params):
    W, H = paper_mm(params)
    ax, ay = MARGIN + 5, MARGIN + 5
    aw, ah = W - 2 * MARGIN - 10, H - 2 * MARGIN - 10 - TITLE_H - 4
    placed, problems = [], []
    x, y, row_h = ax, ay, 0.0
    for v in params["views"]:
        m = measure(doc, v, room=(aw, ah - LABEL_H))
        if m["problem"]:
            problems.append((v, m["problem"])); continue
        w, h = m["w"], m["h"] + LABEL_H
        if w > aw or h > ah:
            problems.append((v, f"δεν χωρά στο {params['paper']} σε 1:{m['scale']} ({w:.0f} × {h:.0f} mm)" if m["scale"]
                             else f"δεν χωρά στο {params['paper']} ({w:.0f} × {h:.0f} mm)"))
            continue
        if x + w > ax + aw + 1e-6:                         # next row
            x, y, row_h = ax, y + row_h + GAP, 0.0
        if y + h > ay + ah + 1e-6:
            problems.append((v, "δεν χωρά άλλη προβολή στο φύλλο: προσθέστε φύλλο ή μεγαλύτερο χαρτί"))
            continue
        placed.append((v, m, (x, y)))
        x += w + GAP
        row_h = max(row_h, h)
    return {"placed": placed, "problems": problems, "paper": (W, H), "area": (ax, ay, aw, ah)}


# ------------------------------------------------------------------ drawing

def _section(sh, ext, data, box, scale):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPen
    from archforge.ui.section_view import _Drawing
    bx, by, _w, _h = box
    k = 1000.0 / scale
    p = sh.p
    p.save()
    p.translate((bx - ext[0] * k) * sh.k, (by + ext[3] * k) * sh.k)
    p.scale(k * sh.k, -k * sh.k)
    _Drawing(data).paint(p, None, None)
    p.restore()
    u0, u1 = ext[0] + 0.3, ext[2] - 0.3
    for z, mark, name in data.get("levels", ()):
        y = by + (ext[3] - z) * k
        if by <= y <= by + (ext[3] - ext[1]) * k:
            sh.line(bx + (u0 - ext[0]) * k, y, bx + (u1 - ext[0]) * k, y, color=QColor(120, 120, 120), width=.13,
                    style=__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.PenStyle.DashDotLine)
            sh.text(bx + 1, y - 1.8, f"{mark} {name}".strip(), size=6, w=60, color=QColor(80, 80, 80))


def _list(sh, data, box):
    from PySide6.QtGui import QColor
    from archforge.quantities.schedules import _fmt
    header, rows, widths, more = data
    x0, y0 = box[0], box[1]
    y = y0
    sh.rect(x0, y, sum(widths), LIST_ROW_H, width=.2, fill=QColor(235, 235, 235))
    for line, cells in enumerate([header] + rows):
        x = x0
        for i, c in enumerate(cells):
            sh.text(x + 1, y + LIST_ROW_H / 2, _fmt(c) if line else str(c), size=LIST_SIZE, bold=not line, w=widths[i] - 2)
            x += widths[i]
        y += LIST_ROW_H
        sh.line(x0, y, x0 + sum(widths), y, width=.1)
    if more:
        sh.text(x0, y + 3, f"… και {more} γραμμές ακόμη (ολόκληρη στο PDF / Excel των Λιστών)", size=6, w=sum(widths),
                color=QColor(110, 110, 110))


def title_block(sh, doc, params, sheet_no, scales, date):
    from PySide6.QtGui import QColor
    from archforge.project.brief import get_brief
    W, H = paper_mm(params)
    x, y, w, h = W - MARGIN - TITLE_W, H - MARGIN - TITLE_H, TITLE_W, TITLE_H
    b = get_brief(doc) or {}
    sh.rect(x, y, w, h, width=.35)
    sh.line(x, y + 11, x + w, y + 11, width=.2)
    sh.line(x + 110, y + 11, x + 110, y + h, width=.2)
    sh.text(x + 3, y + 4, b.get("title") or "Έργο", size=10, bold=True, w=w - 6)
    sh.text(x + 3, y + 8.5, " · ".join(t for t in (b.get("address"), b.get("client") and f"Ιδιοκτήτης: {b['client']}") if t),
            size=7, w=w - 6, color=QColor(70, 70, 70))
    sh.text(x + 3, y + 16, params["title"], size=11, bold=True, w=105)
    sh.text(x + 3, y + 22, "Κλίμακα " + (", ".join(f"1:{s}" for s in scales) if scales else "—"), size=8, w=105)
    sh.text(x + 3, y + 27.5, f"Μελετητής: {b['engineer']}" if b.get("engineer") else "", size=7, w=105)
    sh.text(x + 113, y + 16, f"Φύλλο {params.get('number') or sheet_no}", size=11, bold=True, w=64)
    sh.text(x + 113, y + 22, f"{params['paper']} · {date}", size=8, w=64)
    sh.text(x + w - 2, y - 2.5, "ArchForge", size=6.5, align="right", color=QColor(120, 120, 120), w=80, italic=True)


def render(sh, doc, params, sheet_no=1, date=None):
    """One sheet on ``sh`` (output/pdf.Sheet): frame, views, labels, title block. Returns the layout."""
    from PySide6.QtGui import QColor
    from archforge.output import pdf as P
    date = date or datetime.date.today().strftime("%d/%m/%Y")
    lay = layout(doc, params)
    W, H = lay["paper"]
    sh.rect(MARGIN, MARGIN, W - 2 * MARGIN, H - 2 * MARGIN, width=.5)
    scales = []
    for v, m, (x, y) in lay["placed"]:
        box = (x, y, m["w"], m["h"])
        if v["type"] == "plan":
            P.draw_plan(sh, doc, m["data"], box, m["scale"])
        elif v["type"] == "section":
            _section(sh, *m["data"], box, m["scale"])
        elif v["type"] == "list":
            _list(sh, m["data"], box)
        else:
            for i, t in enumerate(m["data"]):
                sh.text(x, y + 3 + 5 * i, t, size=8, w=m["w"])
        if m["scale"]:
            scales.append(m["scale"])
        title = view_title(doc, v)
        if title:
            ly = y + m["h"] + 4.0
            sh.text(x, ly, greek_upper(title) + (f"   1:{m['scale']}" if m["scale"] else ""), size=8, bold=True,
                    w=max(60.0, m["w"]))
            sh.line(x, ly + 2.4, x + min(max(40.0, m["w"]), 120.0), ly + 2.4, width=.25)
    if lay["problems"]:
        sh.text(MARGIN + 5, H - MARGIN - TITLE_H - 2, "Δεν μπήκαν: " + " · ".join(f"{view_title(doc, v) or VIEW_TYPES[v['type']]}: {t}"
                                                                         for v, t in lay["problems"]),
                size=7, w=W - TITLE_W - 40, color=QColor(190, 40, 40))
    title_block(sh, doc, params, sheet_no, sorted(set(scales)), date)
    return lay


def sheets_of(doc):
    return sorted((e for e in doc.entities.values() if e.kind == "sheet"), key=lambda e: (e.params.get("number", ""), e.id))


def export_sheets(doc, path, ids=None):
    """Every sheet (or ``ids``) as one page of a PDF, each at its paper size: ``{"pages", "path", "problems"}``."""
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
    from archforge.output.pdf import Sheet
    sheets = [e for e in sheets_of(doc) if ids is None or e.id in ids]
    if not sheets:
        raise ValueError("δεν υπάρχει φύλλο σχεδίου: Σχέδια ▸ Φύλλα σχεδίων ▸ Νέο φύλλο")
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setTitle("Φύλλα σχεδίων — ArchForge"); writer.setCreator("ArchForge")

    def page(e):
        W, H = paper_mm(e.params)
        return QPageLayout(QPageSize(QSizeF(W, H), QPageSize.Unit.Millimeter), QPageLayout.Orientation.Portrait,
                           QMarginsF(0, 0, 0, 0))
    writer.setPageLayout(page(sheets[0]))
    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    sh = Sheet(painter, 300 / 25.4)
    problems = {}
    for i, e in enumerate(sheets):
        if i:
            writer.setPageLayout(page(e))
            writer.newPage()
        lay = render(sh, doc, e.params, i + 1)
        if lay["problems"]:
            problems[e.id] = [t for _v, t in lay["problems"]]
    painter.end()
    return {"pages": len(sheets), "path": str(path), "problems": problems}


def preview(doc, params, px_per_mm=2.0):
    """A QImage of the sheet (white paper), for the sheets dialog."""
    from PySide6.QtGui import QColor, QImage, QPainter
    from archforge.output.pdf import Sheet
    W, H = paper_mm(params)
    img = QImage(int(W * px_per_mm), int(H * px_per_mm), QImage.Format.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    render(Sheet(p, px_per_mm), doc, params)
    p.end()
    return img
