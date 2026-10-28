"""Qt pens and brushes from the shared plan styles (core/plan_style.py) — used by the plan view and the PDF alike."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen

DASH = {'solid': Qt.PenStyle.SolidLine, 'dash': Qt.PenStyle.DashLine, 'dashdot': Qt.PenStyle.DashDotLine,
        'dot': Qt.PenStyle.DotLine}
CAP = {'square': Qt.PenCapStyle.SquareCap, 'flat': Qt.PenCapStyle.FlatCap}
JOIN = {'bevel': Qt.PenJoinStyle.BevelJoin, 'miter': Qt.PenJoinStyle.MiterJoin}


def qcolor(rgba):
    return QColor(*rgba)


def qpen(s, width=None):
    """QPen of style ``s``; ``width`` overrides the width (e.g. paper units when printing)."""
    pen = QPen(qcolor(s.color))
    pen.setWidthF(s.width if width is None else width)
    pen.setStyle(DASH[s.dash]); pen.setCapStyle(CAP[s.cap]); pen.setJoinStyle(JOIN[s.join])
    if s.cosmetic:
        pen.setCosmetic(True)
    return pen


def qbrush(s):
    return QBrush(qcolor(s.fill)) if s.fill is not None else QBrush(Qt.BrushStyle.NoBrush)
