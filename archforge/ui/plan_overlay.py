"""What the plan shows over the drawing, in screen pixels (view state only).

Rulers with metres along the top and left edge, a scale bar, the cursor
coordinates, the live measurements of the tool (in Greek) and, while the
project is empty, a short hint how to start with the mouse.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPen

RULER = 18                                     # px band along the top / left edge
STEPS = (0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, 20, 50, 100)

# Live tool values worth reading while drawing; internal ones (snap flags, pivots, x/y) stay out.
HUD_LABELS = {
    "length": ("Μήκος", "m"), "angle_deg": ("Γωνία", "°"), "corner_deg": ("με τον προηγούμενο", "°"),
    "width": ("Πλάτος", "m"), "depth": ("Βάθος", "m"), "height": ("Ύψος", "m"), "sill": ("Ποδιά", "m"),
    "distance": ("Απόσταση", "m"), "offset": ("Μετατόπιση", "m"), "dx": ("Δx", "m"), "dy": ("Δy", "m"),
    "dz": ("Δz", "m"), "top_z": ("Άνω στάθμη", "m"), "base_z": ("Κάτω στάθμη", "m"),
    "floor_level": ("Στάθμη", "m"), "diameter_x": ("Διάμετρος x", "m"), "diameter_y": ("Διάμετρος y", "m"),
}

EMPTY_HINT = ("Ξεκίνα: Τοίχος → κλικ στις γωνίες (ή σύρε)",
              "κλικ στο πρώτο σημείο = κλείσιμο · διπλό κλικ / Enter = τέλος · ροδέλα = ζουμ · Esc = ακύρωση")


def hud_text(hud):
    """Greek one-liner of the measurements the active tool reports."""
    parts = []
    for key, (label, unit) in HUD_LABELS.items():
        value = hud.get(key) if hud else None
        if isinstance(value, (int, float)) and math.isfinite(value):
            parts.append(f"{label} {value:.0f}{unit}" if unit == "°" else f"{label} {value:.2f} {unit}")
    return "   ".join(parts)


def ruler_step(pixels_per_metre, min_px=48):
    for step in STEPS:
        if step * pixels_per_metre >= min_px:
            return step
    return STEPS[-1]


def _fmt(v, step):
    return f"{v:.0f}" if step >= 1 else f"{v:.2f}".rstrip("0").rstrip(".")


def _chip(painter, rect, fill=QColor(255, 255, 255, 230), border=QColor(200, 208, 220)):
    painter.setPen(QPen(border, 1))
    painter.setBrush(fill)
    painter.drawRoundedRect(rect, 6, 6)


def paint_overlay(view, painter):
    vp = view.viewport().rect()
    ppm = abs(view.transform().m11()) or 1.0
    step = ruler_step(ppm)
    font = QFont(painter.font()); font.setPointSizeF(8.5); painter.setFont(font)
    fm = QFontMetrics(font)
    ink = QColor(70, 82, 100)
    # Rulers: a light band with a tick and the metres at every step.
    band = QColor(247, 249, 252, 235)
    painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(band)
    painter.drawRect(QRectF(0, 0, vp.width(), RULER)); painter.drawRect(QRectF(0, 0, RULER, vp.height()))
    top_left = view.mapToScene(vp.topLeft()); bottom_right = view.mapToScene(vp.bottomRight())
    x0, x1 = sorted((top_left.x(), bottom_right.x())); y0, y1 = sorted((top_left.y(), bottom_right.y()))
    painter.setPen(QPen(ink, 1))
    k = math.ceil(x0 / step)
    while k * step <= x1:
        x = k * step; px = view.mapFromScene(QPointF(x, 0)).x()
        if px > RULER + 2:
            painter.drawLine(QPointF(px, RULER - 5), QPointF(px, RULER))
            painter.drawText(QPointF(px + 2, RULER - 6), _fmt(x, step))
        k += 1
    k = math.ceil(y0 / step)
    while k * step <= y1:
        y = k * step; py = view.mapFromScene(QPointF(0, y)).y()
        if py > RULER + 2:
            painter.drawLine(QPointF(RULER - 5, py), QPointF(RULER, py))
            painter.save(); painter.translate(RULER - 6, py - 2); painter.rotate(-90)
            painter.drawText(QPointF(0, 0), _fmt(y, step)); painter.restore()
        k += 1
    painter.setBrush(band); painter.setPen(Qt.PenStyle.NoPen); painter.drawRect(QRectF(0, 0, RULER, RULER))
    painter.setPen(QPen(ink, 1)); painter.drawText(QRectF(0, 0, RULER, RULER), Qt.AlignmentFlag.AlignCenter, "m")
    # Scale bar, bottom left: two blocks of one ruler step each.
    length = step * ppm
    bx, by = RULER + 12, vp.height() - 26
    _chip(painter, QRectF(bx - 8, by - 18, 2 * length + 16 + fm.horizontalAdvance(" 00 m"), 34))
    for i in range(2):
        painter.setPen(QPen(ink, 1)); painter.setBrush(ink if i == 0 else QColor(255, 255, 255))
        painter.drawRect(QRectF(bx + i * length, by, length, 6))
    painter.setPen(QPen(ink, 1))
    painter.drawText(QPointF(bx - 2, by - 4), "0")
    painter.drawText(QPointF(bx + length - 4, by - 4), _fmt(step, step))
    painter.drawText(QPointF(bx + 2 * length - 4, by - 4), f"{_fmt(2 * step, step)} m")
    # Cursor coordinates, bottom right.
    cursor = getattr(view, "_cursor_xy", None)
    if cursor is not None:
        text = f"X {cursor[0]:.2f} m   Y {cursor[1]:.2f} m"
        w = fm.horizontalAdvance(text) + 18
        rect = QRectF(vp.width() - w - 10, vp.height() - 34, w, 24)
        _chip(painter, rect); painter.setPen(QPen(ink, 1))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    # Live measurements of the tool, top left under the rulers.
    frame = getattr(view, "_frame", None)
    live = hud_text(getattr(frame, "hud", None)) if frame is not None else ""
    if live:
        bold = QFont(font); bold.setPointSizeF(10); bold.setBold(True); painter.setFont(bold)
        w = QFontMetrics(bold).horizontalAdvance(live) + 20
        rect = QRectF(RULER + 8, RULER + 8, w, 26)
        if cursor is not None:
            # Next to the mouse, where the eye is while drawing (kept inside the view).
            c = view.mapFromScene(QPointF(*cursor))
            x = min(max(RULER + 4, c.x() + 18), vp.width() - w - 8)
            y = c.y() + 22 if c.y() + 56 < vp.height() else c.y() - 48
            rect = QRectF(x, max(RULER + 4, y), w, 26)
        _chip(painter, rect, QColor(232, 240, 252, 240), QColor(47, 107, 214))
        painter.setPen(QPen(QColor(25, 45, 80), 1)); painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, live)
        painter.setFont(font)
    # Empty project: how to start, with the mouse.
    if not view.doc.entities and not getattr(view, "structural_only", False) and view.controller.active is None:
        big = QFont(font); big.setPointSizeF(12); big.setBold(True)
        small = QFont(font); small.setPointSizeF(10)
        w = max(QFontMetrics(big).horizontalAdvance(EMPTY_HINT[0]), QFontMetrics(small).horizontalAdvance(EMPTY_HINT[1])) + 40
        rect = QRectF((vp.width() - w) / 2, vp.height() * 0.30, w, 62)
        _chip(painter, rect, QColor(255, 255, 255, 235), QColor(47, 107, 214))
        painter.setPen(QPen(QColor(25, 45, 80), 1)); painter.setFont(big)
        painter.drawText(rect.adjusted(0, 8, 0, -30), Qt.AlignmentFlag.AlignCenter, EMPTY_HINT[0])
        painter.setPen(QPen(ink, 1)); painter.setFont(small)
        painter.drawText(rect.adjusted(0, 32, 0, -6), Qt.AlignmentFlag.AlignCenter, EMPTY_HINT[1])
