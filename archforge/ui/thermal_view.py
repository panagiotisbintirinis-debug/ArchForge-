"""Προβολή › «Χρωματισμός κατά U»: η θερμική («υπέρυθρη») εικόνα της κάτοψης (κριτική v5, k7).

Ιδιοκτήτης 30/10: «εργαλείο θερμομόνωσης με υπέρυθρη απεικόνιση: αλλάζεις μόνωση → αλλάζει λ, U, χρώμα τοίχων».
Κάθε τοίχος βάφεται με το U του (``wall_types.indicative_u``: από τις στρώσεις και τα λ τους, ή το U του φυλλαδίου
Isotex)· ψυχρό μπλε = καλή μόνωση, κόκκινο = απώλειες. Τοίχος χωρίς σύνθεση: γκρι διαγράμμιση, «U άγνωστο».
Υπόμνημα κάτω δεξιά. Αλλάζεις τύπο ή στρώσεις (εργαλείο +/−) → το χρώμα αλλάζει στο επόμενο σχέδιο της κάτοψης.

Μόνο εικόνα: δεν αλλάζει τίποτα στο έργο. Τα λ των υλικών είναι τυπικές τιμές προς επαλήθευση, εκτός αν έχουν δοθεί
από φύλλο προϊόντος· το υπόμνημα το λέει.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPen, QPolygonF

U_MIN, U_MAX = 0.2, 2.4                      # W/m²K, logarithmic scale of the legend
STOPS = ((0.0, QColor(47, 107, 214)), (1 / 3, QColor(124, 180, 201)), (2 / 3, QColor(227, 195, 90)),
         (1.0, QColor(196, 54, 27)))


def colour(u):
    """Colour of a U value on the legend's scale."""
    t = (math.log(max(u, U_MIN)) - math.log(U_MIN)) / (math.log(U_MAX) - math.log(U_MIN))
    t = max(0.0, min(1.0, t))
    for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
        if t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return QColor(round(c0.red() + (c1.red() - c0.red()) * f), round(c0.green() + (c1.green() - c0.green()) * f),
                          round(c0.blue() + (c1.blue() - c0.blue()) * f))
    return STOPS[-1][1]


def wall_u(doc, e):
    from archforge.architecture.wall_types import indicative_u
    return indicative_u(e.params.get("wall_type") or "generic", doc)


def draw(view):
    """Paint every visible wall of the active storey with its U (scene items above the walls, below the handles)."""
    doc = view.doc
    z = float(doc.work_plane.origin[2])
    unknown = QBrush(QColor(150, 150, 150, 200), Qt.BrushStyle.BDiagPattern)
    edge = QPen(QColor(40, 50, 65)); edge.setWidthF(0)
    counted = {"known": 0, "unknown": 0}
    for e in doc.entities.values():
        if e.kind != "wall" or not e.visible or abs(float(e.params.get("z", 0.0)) - z) > 0.05:
            continue
        p = e.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            continue
        t = float(p.get("thickness", 0.15)) / 2
        nx, ny = -(y2 - y1) / L * t, (x2 - x1) / L * t
        poly = QPolygonF([QPointF(x1 + nx, y1 + ny), QPointF(x2 + nx, y2 + ny), QPointF(x2 - nx, y2 - ny), QPointF(x1 - nx, y1 - ny)])
        u = wall_u(doc, e)
        if u is None:
            brush = unknown; counted["unknown"] += 1
        else:
            c = colour(u); c.setAlpha(235); brush = QBrush(c); counted["known"] += 1
        item = view._scene.addPolygon(poly, edge, brush)
        item.setZValue(26)
        item.setToolTip(f"U {u:.2f} W/m²K".replace(".", ",") if u is not None else "U άγνωστο: τοίχος χωρίς σύνθεση")
        view._entity_items[item] = e.id                     # click / hover still find the wall
    view._thermal_counts = counted


def paint_legend(view, painter):
    """The scale, bottom right (bottom left holds the plan's scale bar), in screen pixels."""
    vp = view.viewport().rect()
    w, h = 260, 64
    r = QRectF(max(28, vp.width() - w - 16), vp.height() - h - 16, w, h)
    painter.setPen(QPen(QColor(200, 208, 220))); painter.setBrush(QColor(255, 255, 255, 235))
    painter.drawRoundedRect(r, 6, 6)
    bar = QRectF(r.left() + 10, r.top() + 24, w - 20, 10)
    g = QLinearGradient(bar.topLeft(), bar.topRight())
    for t, c in STOPS:
        g.setColorAt(t, c)
    painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(g)); painter.drawRect(bar)
    painter.setPen(QPen(QColor(25, 45, 80)))
    f = painter.font(); f.setPointSizeF(8.5); painter.setFont(f)
    counts = getattr(view, "_thermal_counts", {"known": 0, "unknown": 0})
    title = "U τοίχων (W/m²K)" + (f" · {counts['unknown']} χωρίς σύνθεση" if counts.get("unknown") else "")
    painter.drawText(QRectF(r.left() + 10, r.top() + 4, w - 20, 18), Qt.AlignmentFlag.AlignLeft, title)
    for value in (0.2, 0.4, 0.8, 1.6, 2.4):
        x = bar.left() + bar.width() * (math.log(value) - math.log(U_MIN)) / (math.log(U_MAX) - math.log(U_MIN))
        painter.drawText(QRectF(x - 18, bar.bottom() + 2, 36, 14), Qt.AlignmentFlag.AlignCenter, f"{value:g}".replace(".", ","))
    painter.setPen(QPen(QColor(90, 105, 125)))
    painter.drawText(QRectF(r.left() + 10, r.bottom() - 2, w - 20, 14), Qt.AlignmentFlag.AlignLeft,
                     "λ τυπικά, προς επαλήθευση")


def toggle(window, on):
    view = window.plan_view
    view.color_by_u = bool(on)
    view.redraw()
    if on:
        c = getattr(view, "_thermal_counts", {})
        window.statusBar().showMessage(
            f"Χρωματισμός κατά U: {c.get('known', 0)} τοίχοι με U"
            + (f", {c['unknown']} χωρίς σύνθεση (γκρι) — δώσε τύπο: Επεξεργασία › Επιλογή εξωτερικών τοίχων → Τύπος (όλων)"
               if c.get("unknown") else "") , 10000)


def install(window):
    from PySide6.QtGui import QAction
    a = QAction("Χρωματισμός κατά U (θερμική εικόνα)", window)
    a.setCheckable(True)
    a.setToolTip("Οι τοίχοι βάφονται με το U τους: μπλε = καλή μόνωση, κόκκινο = απώλειες")
    a.toggled.connect(lambda on: toggle(window, on))
    window._thermal_view_action = a
    window._main_actions.append(a)
    return a


def toggle_3d(window, on):
    """«Θερμική όψη 3D»: the façades in the thermography palette, outside surface temperatures (owner 05/11)."""
    view = window.pbr_view
    if on:
        window._show_3d_view()
        payload = view.set_thermal_view("exterior")
        n_unknown = len(payload["unknown"]) if payload else 0
        window.statusBar().showMessage(
            f"Θερμική όψη: {payload['count'] if payload else 0} επιφάνειες με θερμοκρασία"
            + (f", {n_unknown} χωρίς U (γκρι) — δώσε τύπο τοίχου / Uw κουφώματος (Λίστες › Κουφώματα)" if n_unknown else ""),
            12000)
        return payload
    view.set_thermal_view(None)
    return None


def install_3d(window):
    from PySide6.QtGui import QAction
    a = QAction("Θερμική όψη 3D (εξωτερικές επιφάνειες)", window)
    a.setCheckable(True)
    a.setToolTip("Οι όψεις όπως τις δείχνει μια θερμοκάμερα: θερμοκρασία εξωτερικής επιφάνειας από το U, "
                 "παλέτα «iron», κλίμακα σε °C · γκρι = δεν υπολογίστηκε")
    a.toggled.connect(lambda on: toggle_3d(window, on))
    window._thermal_3d_action = a
    window._main_actions.append(a)
    return a
