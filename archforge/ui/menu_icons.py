"""Small line icons for the mouse menu (drawn in code — no image files, nothing to license).

``icon(name)`` gives a QIcon for the Qt menu of the plan; ``icon_data(name)`` the same picture as a PNG data
URI for the 3D view's web menu, so both show the same thing.
"""
from __future__ import annotations

import base64

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

INK = QColor(40, 62, 92)
ACCENT = QColor(47, 107, 214)
RED = QColor(200, 60, 50)
WOOD = QColor(176, 122, 70)
_cache = {}


def _pen(color=INK, width=2.2):
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _draw(name, p):
    P = QPointF
    p.setPen(_pen()); p.setBrush(Qt.BrushStyle.NoBrush)
    if name == "select":
        p.setBrush(QColor(255, 255, 255))
        p.drawPolygon(QPolygonF([P(9, 4), P(9, 25), P(14.5, 20), P(18.5, 28), P(22, 26), P(18, 18.5), P(25, 18)]))
    elif name == "wall":
        p.setBrush(QColor(200, 210, 224)); p.drawRect(QRectF(3, 11, 26, 10))
        for x in (10, 16, 22):
            p.drawLine(P(x, 11), P(x, 21))
    elif name == "door":
        p.drawLine(P(5, 27), P(27, 27)); p.drawLine(P(8, 27), P(8, 7))
        p.setPen(_pen(ACCENT)); p.drawArc(QRectF(-12, 7, 40, 40), 0, 90 * 16)
    elif name == "window":
        p.drawRect(QRectF(4, 7, 24, 18)); p.drawLine(P(16, 7), P(16, 25))
        p.setPen(_pen(ACCENT, 1.6)); p.drawLine(P(7, 16), P(13, 16)); p.drawLine(P(19, 16), P(25, 16))
    elif name == "opening":
        p.drawLine(P(3, 16), P(10, 16)); p.drawLine(P(22, 16), P(29, 16))
        p.setPen(_pen(ACCENT, 1.6)); p.drawRect(QRectF(10, 10, 12, 12))
    elif name in ("stair", "ramp"):
        if name == "stair":
            p.drawPolyline(QPolygonF([P(3, 28), P(3, 23), P(9, 23), P(9, 18), P(15, 18), P(15, 13), P(21, 13),
                                      P(21, 8), P(28, 8)]))
        else:
            p.drawLine(P(3, 27), P(29, 27)); p.drawLine(P(3, 27), P(29, 9)); p.drawLine(P(29, 9), P(29, 27))
    elif name == "column":
        p.setBrush(QColor(210, 214, 220)); p.drawRect(QRectF(11, 5, 10, 22))
        p.setBrush(Qt.BrushStyle.NoBrush); p.drawLine(P(6, 27), P(26, 27))
    elif name == "beam":
        p.setBrush(QColor(210, 214, 220)); p.drawRect(QRectF(3, 11, 26, 8))
        p.setBrush(Qt.BrushStyle.NoBrush); p.drawLine(P(6, 19), P(6, 28)); p.drawLine(P(26, 19), P(26, 28))
    elif name == "cabinet":
        p.drawRect(QRectF(5, 7, 22, 20)); p.drawLine(P(16, 7), P(16, 27))
        p.drawLine(P(13, 15), P(13, 19)); p.drawLine(P(19, 15), P(19, 19))
    elif name.startswith("way_"):
        # Plan of a door in a wall: hinge left/right, leaf into the room (up) or out (down).
        _w, side, hinge = name.split("_")
        y0, r = (22, 16) if side == "in" else (10, 16)          # the wall line, the leaf length = the opening
        p.setPen(_pen(INK, 2.8)); p.drawLine(P(1, y0), P(8, y0)); p.drawLine(P(24, y0), P(31, y0))
        hx = 8 if hinge == "left" else 24
        tip = y0 - r if side == "in" else y0 + r
        p.setPen(_pen(ACCENT, 2.4)); p.drawLine(P(hx, y0), P(hx, tip))
        p.setPen(_pen(ACCENT, 1.4))
        rect = QRectF(hx - r, y0 - r, 2 * r, 2 * r)
        start = {("in", "left"): 0, ("in", "right"): 90, ("out", "left"): 270, ("out", "right"): 180}[(side, hinge)]
        p.drawArc(rect, start * 16, 90 * 16)
    elif name == "appliance":
        p.drawRoundedRect(QRectF(6, 4, 20, 24), 2, 2); p.drawLine(P(6, 13), P(26, 13))
        p.setPen(_pen(ACCENT, 1.8)); p.drawLine(P(10, 8), P(14, 8)); p.drawEllipse(P(16, 20), 3.5, 3.5)
    elif name == "bath":
        p.drawRoundedRect(QRectF(4, 13, 24, 10), 4, 4); p.drawLine(P(8, 23), P(7, 27)); p.drawLine(P(24, 23), P(25, 27))
        p.setPen(_pen(ACCENT)); p.drawLine(P(8, 13), P(8, 6)); p.drawLine(P(8, 6), P(12, 6))
    elif name == "room":
        p.setBrush(QColor(225, 238, 228)); p.drawRect(QRectF(5, 5, 22, 22))
        p.setPen(_pen(ACCENT, 1.8)); p.drawEllipse(P(16, 16), 3, 3)
    elif name in ("slab", "balcony", "terrace"):
        p.setBrush(QColor(210, 214, 220))
        p.drawPolygon(QPolygonF([P(3, 18), P(17, 11), P(29, 16), P(15, 23)]))
        if name == "balcony":
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(_pen(ACCENT, 1.6))
            for x in (6, 11, 16):
                p.drawLine(P(x, 18 + (x - 3) * 0.4), P(x, 10 + (x - 3) * 0.4))
            p.drawLine(P(5, 9), P(17, 14))
        if name == "terrace":
            p.setPen(_pen(ACCENT, 1.6)); p.drawLine(P(3, 18), P(3, 13)); p.drawLine(P(29, 16), P(29, 11))
    elif name == "roof":
        p.setBrush(QColor(196, 90, 70)); p.drawPolygon(QPolygonF([P(3, 17), P(16, 5), P(29, 17)]))
        p.setBrush(Qt.BrushStyle.NoBrush); p.drawRect(QRectF(7, 17, 18, 11))
    elif name == "ceiling":
        p.drawLine(P(3, 6), P(29, 6))
        for x in (8, 16, 24):
            p.drawLine(P(x, 6), P(x, 12))
        p.setPen(_pen(ACCENT, 2.4)); p.drawLine(P(4, 13), P(28, 13))
    elif name == "dropper":
        # Eyedropper: a pipette, its drop the sampled colour.
        p.setPen(_pen(INK, 2.2)); p.drawLine(P(10, 22), P(22, 10))
        p.setBrush(QColor(200, 210, 224)); p.drawRoundedRect(QRectF(20, 4, 8, 8), 2, 2)
        p.setBrush(ACCENT); p.setPen(_pen(ACCENT, 1.2))
        p.drawPolygon(QPolygonF([P(7, 22), P(10, 26), P(7, 30), P(4, 26)]))
    elif name in _MORE:
        _MORE[name](p, P)
    elif name == "more":
        p.setBrush(INK)
        for x in (8, 16, 24):
            p.drawEllipse(P(x, 16), 2.2, 2.2)
    elif name == "properties":
        for y in (9, 16, 23):
            p.drawLine(P(5, y), P(27, y))
        p.setBrush(QColor(255, 255, 255)); p.setPen(_pen(ACCENT, 2))
        for x, y in ((11, 9), (21, 16), (14, 23)):
            p.drawEllipse(P(x, y), 2.6, 2.6)
    elif name == "move":
        p.drawLine(P(16, 4), P(16, 28)); p.drawLine(P(4, 16), P(28, 16))
        for tip, a, b in (((16, 4), (13, 8), (19, 8)), ((16, 28), (13, 24), (19, 24)),
                          ((4, 16), (8, 13), (8, 19)), ((28, 16), (24, 13), (24, 19))):
            p.drawLine(P(*tip), P(*a)); p.drawLine(P(*tip), P(*b))
    elif name == "rotate":
        p.drawArc(QRectF(6, 6, 20, 20), 60 * 16, 280 * 16)
        p.setPen(_pen(ACCENT)); p.drawLine(P(21, 5), P(22, 10)); p.drawLine(P(22, 10), P(17, 11))
    elif name == "stretch":
        p.drawRect(QRectF(5, 10, 12, 12)); p.setPen(_pen(ACCENT))
        p.drawLine(P(17, 16), P(28, 16)); p.drawLine(P(28, 16), P(24, 12)); p.drawLine(P(28, 16), P(24, 20))
    elif name == "materials":
        for i, c in enumerate((QColor(214, 120, 70), QColor(120, 170, 90), QColor(90, 140, 210))):
            p.setBrush(c); p.drawRoundedRect(QRectF(4 + i * 5, 5 + i * 4, 14, 18), 2, 2)
    elif name == "delete":
        p.setPen(_pen(RED, 2.6)); p.drawLine(P(8, 8), P(24, 24)); p.drawLine(P(24, 8), P(8, 24))
    elif name == "duplicate":
        p.drawRect(QRectF(5, 5, 15, 15)); p.setBrush(QColor(255, 255, 255)); p.drawRect(QRectF(12, 12, 15, 15))
    elif name == "mirror":
        p.setPen(_pen(ACCENT, 1.6)); p.drawLine(P(16, 3), P(16, 29)); p.setPen(_pen())
        p.drawPolygon(QPolygonF([P(13, 8), P(13, 24), P(4, 24)]))
        p.drawPolygon(QPolygonF([P(19, 8), P(19, 24), P(28, 24)]))
    elif name == "swing":
        p.drawLine(P(6, 26), P(6, 6)); p.setPen(_pen(ACCENT)); p.drawArc(QRectF(-14, 6, 40, 40), 0, 90 * 16)
        p.drawLine(P(26, 26), P(22, 22)); p.drawLine(P(26, 26), P(27, 21))
    elif name == "assist":
        p.setBrush(ACCENT); p.setPen(_pen(ACCENT, 1.5))
        p.drawEllipse(P(16, 12), 6, 6); p.drawPolygon(QPolygonF([P(11, 15), P(21, 15), P(16, 28)]))
        p.setBrush(QColor(255, 255, 255)); p.drawEllipse(P(16, 12), 2.2, 2.2)
    elif name == "statics":
        p.drawLine(P(4, 22), P(28, 22)); p.drawLine(P(6, 22), P(6, 27)); p.drawLine(P(26, 22), P(26, 27))
        p.setPen(_pen(ACCENT)); p.drawArc(QRectF(6, 6, 20, 26), 0, 180 * 16)
    elif name == "footing":
        p.setBrush(QColor(210, 214, 220)); p.drawRect(QRectF(12, 4, 8, 16)); p.drawRect(QRectF(5, 20, 22, 7))
    elif name == "split":
        p.drawLine(P(3, 16), P(13, 16)); p.drawLine(P(19, 16), P(29, 16))
        p.setPen(_pen(RED, 2)); p.drawLine(P(14, 8), P(18, 24))
    elif name == "corner":
        p.drawLine(P(4, 26), P(20, 26)); p.drawLine(P(26, 4), P(26, 20))
        p.setPen(_pen(ACCENT)); p.drawLine(P(20, 26), P(26, 26)); p.drawLine(P(26, 26), P(26, 20))
        p.drawRect(QRectF(23, 23, 6, 6))
    elif name == "fit":
        p.drawLine(P(4, 5), P(28, 5)); p.drawRect(QRectF(9, 14, 14, 14))
        p.setPen(_pen(ACCENT)); p.drawLine(P(16, 13), P(16, 7)); p.drawLine(P(16, 7), P(13, 10)); p.drawLine(P(16, 7), P(19, 10))
    elif name == "camera":
        p.drawRoundedRect(QRectF(4, 10, 18, 13), 2, 2)
        p.drawPolygon(QPolygonF([P(22, 14), P(29, 10), P(29, 23), P(22, 19)]))
    elif name == "level":
        p.setPen(_pen(ACCENT)); p.drawLine(P(4, 26), P(28, 26))
        p.drawLine(P(4, 14), P(28, 14)); p.setPen(_pen(INK))
        p.drawLine(P(16, 24), P(16, 17)); p.drawLine(P(12, 21), P(16, 17)); p.drawLine(P(20, 21), P(16, 17))
        p.drawLine(P(26, 4), P(26, 11)); p.drawLine(P(22, 8), P(26, 4)); p.drawLine(P(30, 8), P(26, 4))
    elif name == "plant":
        p.setPen(_pen(WOOD, 2.8)); p.drawLine(P(16, 15), P(16, 29))
        p.setBrush(QColor(88, 157, 95)); p.setPen(_pen(QColor(58, 120, 72), 1.6))
        p.drawEllipse(QRectF(8, 5, 16, 15)); p.drawEllipse(QRectF(4, 12, 12, 10))
        p.drawEllipse(QRectF(17, 12, 12, 10))
    elif name == "water":
        p.setPen(_pen(ACCENT, 1.8)); p.setBrush(QColor(193, 225, 254))
        p.drawPolygon(QPolygonF([P(16, 3), P(8, 18), P(8, 23), P(12, 28), P(20, 28), P(24, 23), P(24, 18)]))
        p.drawArc(QRectF(11, 15, 10, 10), 180 * 16, 90 * 16)
    elif name == "power":
        p.drawRoundedRect(QRectF(6, 5, 20, 23), 4, 4)
        p.setPen(_pen(ACCENT, 2.8)); p.drawLine(P(12, 11), P(12, 18)); p.drawLine(P(20, 11), P(20, 18))
        p.drawArc(QRectF(11, 18, 10, 7), 180 * 16, 180 * 16)
    elif name == "pool":
        p.setPen(_pen(ACCENT, 2)); p.drawRoundedRect(QRectF(4, 5, 24, 22), 2, 2)
        for y in (13, 19):
            p.drawPolyline(QPolygonF([P(7, y), P(12, y - 2), P(17, y), P(22, y - 2), P(26, y)]))
    elif name == "road":
        p.drawLine(P(10, 3), P(6, 29)); p.drawLine(P(22, 3), P(26, 29))
        p.setPen(_pen(ACCENT, 1.8))
        for y in (4, 12, 20):
            p.drawLine(P(16, y), P(16, y + 4))
    elif name == "lighting":
        p.setPen(_pen(ACCENT)); p.drawEllipse(P(16, 12), 7, 7)
        p.setPen(_pen()); p.drawLine(P(12, 21), P(20, 21)); p.drawLine(P(13, 25), P(19, 25))
        for x1, y1, x2, y2 in ((16, 1, 16, 3), (3, 12, 6, 12), (26, 12, 29, 12),
                                (6, 3, 9, 6), (26, 3, 23, 6)):
            p.drawLine(P(x1, y1), P(x2, y2))
    elif name in ("save", "undo"):
        if name == "save":
            p.drawRoundedRect(QRectF(5, 5, 22, 22), 2, 2)
            p.drawRect(QRectF(10, 5, 12, 8)); p.setPen(_pen(ACCENT)); p.drawRect(QRectF(10, 19, 12, 8))
        else:
            p.setPen(_pen(ACCENT, 2.6)); p.drawArc(QRectF(8, 8, 20, 17), 280 * 16, 220 * 16)
            p.drawLine(P(8, 9), P(8, 18)); p.drawLine(P(8, 9), P(17, 9))
    else:
        p.drawEllipse(P(16, 16), 9, 9)


# --------------------------------------------------------------- more task drawings (owner 04/11: an icon on every
# command of the menus).  Each one draws on the 32 × 32 grid with the pens above.
def _page(p, P, fold=True):
    p.drawPolygon(QPolygonF([P(8, 3), P(20, 3), P(26, 9), P(26, 29), P(8, 29)]))
    if fold:
        p.drawPolyline(QPolygonF([P(20, 3), P(20, 9), P(26, 9)]))


def _arrow(p, P, x1, y1, x2, y2, color=None):
    import math
    if color is not None:
        p.setPen(_pen(color))
    p.drawLine(P(x1, y1), P(x2, y2))
    a = math.atan2(y1 - y2, x1 - x2)
    for s in (-0.5, 0.5):
        p.drawLine(P(x2, y2), P(x2 + 6 * math.cos(a + s), y2 + 6 * math.sin(a + s)))


def _new(p, P):
    _page(p, P)
    p.setPen(_pen(ACCENT, 2.6)); p.drawLine(P(17, 15), P(17, 25)); p.drawLine(P(12, 20), P(22, 20))


def _open(p, P):
    p.drawPolygon(QPolygonF([P(3, 9), P(12, 9), P(15, 12), P(28, 12), P(28, 26), P(3, 26)]))
    p.setPen(_pen(ACCENT)); p.drawLine(P(6, 17), P(29, 17))


def _recover(p, P):
    _page(p, P); p.setPen(_pen(ACCENT, 2)); p.drawArc(QRectF(11, 13, 12, 12), 30 * 16, 300 * 16)
    p.drawLine(P(22, 13), P(23, 18)); p.drawLine(P(23, 18), P(18, 17))


def _home(p, P):
    p.drawPolyline(QPolygonF([P(3, 16), P(16, 4), P(29, 16)])); p.drawRect(QRectF(8, 15, 16, 13))
    p.setPen(_pen(ACCENT)); p.drawRect(QRectF(14, 20, 5, 8))


def _tray(p, P, up):
    p.drawPolyline(QPolygonF([P(4, 19), P(4, 28), P(28, 28), P(28, 19)]))
    _arrow(p, P, 16, 22, 16, 4, ACCENT) if up else _arrow(p, P, 16, 3, 16, 21, ACCENT)


def _pdf(p, P):
    _page(p, P); p.setBrush(RED); p.setPen(_pen(RED, 1)); p.drawRect(QRectF(5, 15, 18, 8))
    p.setPen(_pen(QColor(255, 255, 255), 1.4)); p.drawLine(P(8, 19), P(20, 19))


def _phase(kind):
    def draw(p, P):
        if kind == "existing":
            p.setBrush(QColor(200, 204, 210)); p.drawRect(QRectF(5, 9, 22, 14))
        elif kind == "demolish":
            p.setPen(_pen(INK, 1.6)); pen = p.pen(); pen.setStyle(Qt.PenStyle.DashLine); p.setPen(pen)
            p.drawRect(QRectF(5, 9, 22, 14)); p.setPen(_pen(RED, 2.4)); p.drawLine(P(9, 12), P(23, 20)); p.drawLine(P(23, 12), P(9, 20))
        else:
            p.drawRect(QRectF(5, 9, 22, 14)); p.setPen(_pen(ACCENT, 2.6)); p.drawLine(P(16, 12), P(16, 20)); p.drawLine(P(12, 16), P(20, 16))
    return draw


def _tree(p, P):
    p.drawRect(QRectF(4, 4, 8, 6)); p.drawRect(QRectF(16, 13, 10, 6)); p.drawRect(QRectF(16, 23, 10, 6))
    p.setPen(_pen(ACCENT, 1.8)); p.drawPolyline(QPolygonF([P(8, 10), P(8, 26), P(16, 26)])); p.drawLine(P(8, 16), P(16, 16))


def _railing(p, P):
    p.drawLine(P(3, 8), P(29, 8)); p.drawLine(P(3, 27), P(29, 27))
    p.setPen(_pen(ACCENT, 1.8))
    for x in (6, 11, 16, 21, 26):
        p.drawLine(P(x, 8), P(x, 27))


def _part(p, P):
    p.drawPolygon(QPolygonF([P(16, 4), P(26, 10), P(26, 22), P(16, 28), P(6, 22), P(6, 10)]))
    p.setPen(_pen(ACCENT)); p.drawEllipse(P(16, 16), 4.5, 4.5)


def _hinge(p, P):
    p.drawRect(QRectF(4, 8, 10, 16)); p.drawRect(QRectF(18, 8, 10, 16))
    p.setBrush(QColor(255, 255, 255)); p.setPen(_pen(ACCENT)); p.drawEllipse(P(16, 16), 3.5, 3.5)


def _place(p, P):
    p.setBrush(QColor(225, 230, 238)); p.drawRect(QRectF(8, 15, 16, 12)); _arrow(p, P, 16, 2, 16, 12, ACCENT)


def _edit(p, P):
    p.drawPolygon(QPolygonF([P(6, 26), P(8, 20), P(22, 6), P(26, 10), P(12, 24)]))
    p.setPen(_pen(ACCENT)); p.drawLine(P(19, 9), P(23, 13))


def _sculpt(p, P):
    p.drawPath(_curve(P(3, 25), P(16, 2), P(29, 25)))
    p.setBrush(ACCENT); p.setPen(_pen(ACCENT, 1)); p.drawEllipse(P(16, 13), 2.6, 2.6)


def _curve(a, c, b):
    from PySide6.QtGui import QPainterPath
    path = QPainterPath(a); path.quadTo(c, b); return path


def _tape(p, P):
    p.drawLine(P(4, 16), P(28, 16)); p.drawLine(P(4, 10), P(4, 22)); p.drawLine(P(28, 10), P(28, 22))
    p.setPen(_pen(ACCENT, 1.6)); p.drawLine(P(7, 19), P(9, 13)); p.drawLine(P(23, 19), P(25, 13))


def _autodim(p, P):
    p.drawRect(QRectF(6, 14, 20, 14)); p.setPen(_pen(ACCENT, 1.6))
    p.drawLine(P(6, 7), P(26, 7)); p.drawLine(P(6, 4), P(6, 10)); p.drawLine(P(16, 4), P(16, 10)); p.drawLine(P(26, 4), P(26, 10))


def _line(p, P):
    p.drawLine(P(5, 26), P(27, 6)); p.setBrush(ACCENT); p.setPen(_pen(ACCENT, 1))
    p.drawEllipse(P(5, 26), 2.4, 2.4); p.drawEllipse(P(27, 6), 2.4, 2.4)


def _polyline(p, P):
    p.drawPolyline(QPolygonF([P(4, 25), P(11, 8), P(20, 20), P(28, 6)])); p.setBrush(ACCENT); p.setPen(_pen(ACCENT, 1))
    for x, y in ((4, 25), (11, 8), (20, 20), (28, 6)):
        p.drawEllipse(P(x, y), 2, 2)


def _rect(p, P):
    p.drawRect(QRectF(5, 8, 22, 16)); p.setBrush(ACCENT); p.setPen(_pen(ACCENT, 1))
    p.drawEllipse(P(5, 24), 2.2, 2.2); p.drawEllipse(P(27, 8), 2.2, 2.2)


def _circle(p, P):
    p.drawEllipse(P(16, 16), 11, 11); p.setPen(_pen(ACCENT, 1.6)); p.drawLine(P(16, 16), P(27, 16))
    p.setBrush(ACCENT); p.drawEllipse(P(16, 16), 1.8, 1.8)


def _arc(p, P):
    p.drawArc(QRectF(5, 7, 22, 22), 0, 180 * 16); p.setBrush(ACCENT); p.setPen(_pen(ACCENT, 1))
    for x, y in ((5, 18), (16, 7), (27, 18)):
        p.drawEllipse(P(x, y), 2.2, 2.2)


def _note(p, P):
    p.drawRoundedRect(QRectF(4, 5, 24, 18), 2, 2); p.drawPolyline(QPolygonF([P(9, 23), P(9, 29), P(15, 23)]))
    p.setPen(_pen(ACCENT, 1.8)); p.drawLine(P(8, 11), P(24, 11)); p.drawLine(P(8, 17), P(20, 17))


def _leader(p, P):
    p.setPen(_pen(ACCENT, 1.8)); p.drawLine(P(14, 9), P(28, 9)); p.drawLine(P(14, 14), P(24, 14))
    p.setPen(_pen()); _arrow(p, P, 14, 12, 4, 27)


def _sheet(p, P):
    p.drawRect(QRectF(4, 6, 24, 20)); p.setPen(_pen(ACCENT, 1.4)); p.drawRect(QRectF(19, 20, 9, 6))
    p.drawLine(P(8, 11), P(16, 11)); p.drawLine(P(8, 15), P(14, 15))


def _section(p, P):
    p.setPen(_pen(RED, 2.2)); pen = p.pen(); pen.setStyle(Qt.PenStyle.DashDotLine); p.setPen(pen)
    p.drawLine(P(16, 3), P(16, 29)); p.setPen(_pen())
    _arrow(p, P, 16, 6, 26, 6); _arrow(p, P, 16, 26, 26, 26)


def _elevation(p, P):
    p.drawRect(QRectF(6, 12, 20, 16)); p.drawPolyline(QPolygonF([P(4, 13), P(16, 4), P(28, 13)]))
    p.setPen(_pen(ACCENT, 1.6)); p.drawRect(QRectF(10, 17, 5, 5)); p.drawRect(QRectF(18, 17, 5, 11))


def _price(p, P):
    p.drawEllipse(P(16, 16), 12, 12); p.setPen(_pen(ACCENT, 2.2))
    p.drawArc(QRectF(10, 9, 13, 14), 50 * 16, 260 * 16); p.drawLine(P(8, 14), P(18, 14)); p.drawLine(P(8, 18), P(18, 18))


def _cube(p, P, persp=True):
    p.drawPolygon(QPolygonF([P(6, 11), P(16, 6), P(26, 11), P(16, 16)]))
    p.drawLine(P(6, 11), P(6, 23)); p.drawLine(P(26, 11), P(26, 23)); p.drawLine(P(16, 16), P(16, 28))
    p.drawLine(P(6, 23), P(16, 28)); p.drawLine(P(26, 23), P(16, 28))
    if persp:
        p.setPen(_pen(ACCENT, 1.4)); p.drawLine(P(16, 16), P(16, 6))


def _top(p, P):
    p.drawRect(QRectF(6, 10, 20, 18)); _arrow(p, P, 16, 2, 16, 15, ACCENT)


def _front(p, P):
    p.drawRect(QRectF(6, 13, 20, 15)); p.drawPolyline(QPolygonF([P(4, 14), P(16, 4), P(28, 14)]))
    p.setPen(_pen(ACCENT)); p.drawRect(QRectF(13, 19, 6, 9))


def _side(p, P):
    p.drawRect(QRectF(5, 14, 22, 14)); p.drawPolygon(QPolygonF([P(5, 14), P(10, 6), P(27, 6), P(27, 14)]))
    p.setPen(_pen(ACCENT)); p.drawRect(QRectF(9, 18, 5, 5)); p.drawRect(QRectF(18, 18, 5, 5))


def _realistic(p, P):
    _cube(p, P, False); p.setPen(_pen(QColor(232, 170, 20), 2)); p.drawEllipse(P(26, 6), 3.2, 3.2)


def _split(p, P):
    p.drawRect(QRectF(3, 6, 26, 20)); p.drawLine(P(16, 6), P(16, 26))
    p.setPen(_pen(ACCENT, 1.4)); p.drawRect(QRectF(6, 12, 7, 8))
    p.drawPolygon(QPolygonF([P(19, 15), P(22, 12), P(26, 15), P(22, 18)]))


def _ao(p, P):
    p.setBrush(QColor(170, 178, 190)); p.setPen(_pen(INK, 1.6))
    p.drawPolygon(QPolygonF([P(4, 26), P(4, 6), P(10, 12), P(10, 26)])); p.drawPolygon(QPolygonF([P(4, 26), P(10, 20), P(28, 20), P(28, 26)]))


def _sun(p, P):
    p.setPen(_pen(QColor(222, 150, 20), 2.2)); p.drawEllipse(P(16, 16), 6, 6)
    for x1, y1, x2, y2 in ((16, 2, 16, 6), (16, 26, 16, 30), (2, 16, 6, 16), (26, 16, 30, 16),
                           (6, 6, 9, 9), (26, 6, 23, 9), (6, 26, 9, 23), (26, 26, 23, 23)):
        p.drawLine(P(x1, y1), P(x2, y2))


def _moon(p, P):
    from PySide6.QtGui import QPainterPath
    outer = QPainterPath(); outer.addEllipse(QRectF(5, 5, 22, 22))
    cut = QPainterPath(); cut.addEllipse(QRectF(12, 2, 20, 20))
    p.setBrush(QColor(90, 110, 160)); p.drawPath(outer.subtracted(cut))


def _studio(p, P):
    p.drawRect(QRectF(5, 4, 22, 14)); p.drawLine(P(16, 18), P(16, 28)); p.drawLine(P(10, 28), P(22, 28))
    p.setPen(_pen(ACCENT, 1.4)); p.drawLine(P(8, 8), P(24, 8)); p.drawLine(P(8, 13), P(24, 13))


def _bulb(on):
    def draw(p, P):
        p.setPen(_pen(QColor(222, 150, 20) if on else INK, 2.2)); p.drawEllipse(P(16, 12), 8, 8)
        p.setPen(_pen()); p.drawLine(P(12, 22), P(20, 22)); p.drawLine(P(13, 27), P(19, 27))
        if not on:
            p.setPen(_pen(RED, 2)); p.drawLine(P(5, 4), P(27, 26))
    return draw


def _clock(p, P):
    p.drawEllipse(P(16, 16), 12, 12); p.setPen(_pen(ACCENT, 2.2)); p.drawLine(P(16, 16), P(16, 8)); p.drawLine(P(16, 16), P(22, 19))


def _layers(p, P):
    for k, y in enumerate((20, 14, 8)):
        p.setBrush(QColor(255, 255, 255) if k else QColor(200, 210, 224))
        p.drawPolygon(QPolygonF([P(3, y), P(16, y - 5), P(29, y), P(16, y + 5)]))


def _update(p, P):
    p.setPen(_pen(ACCENT, 2.2)); p.drawArc(QRectF(6, 6, 20, 20), 40 * 16, 140 * 16); p.drawArc(QRectF(6, 6, 20, 20), 220 * 16, 140 * 16)
    p.drawLine(P(24, 7), P(25, 13)); p.drawLine(P(25, 13), P(19, 12)); p.drawLine(P(8, 25), P(7, 19)); p.drawLine(P(7, 19), P(13, 20))


def _units(p, P):
    p.drawRect(QRectF(3, 11, 26, 10)); p.setPen(_pen(ACCENT, 1.6))
    for k, x in enumerate(range(6, 28, 4)):
        p.drawLine(P(x, 11), P(x, 15 if k % 2 else 17))


def _mouse(p, P):
    p.drawRoundedRect(QRectF(9, 4, 14, 24), 7, 7); p.drawLine(P(16, 4), P(16, 13)); p.drawLine(P(9, 13), P(23, 13))
    p.setPen(_pen(ACCENT, 2.4)); p.drawLine(P(16, 7), P(16, 10))


def _info(p, P):
    p.drawEllipse(P(16, 16), 12, 12); p.setPen(_pen(ACCENT, 2.8)); p.drawLine(P(16, 14), P(16, 23))
    p.setBrush(ACCENT); p.drawEllipse(P(16, 9), 1.4, 1.4)


def _panel(p, P):
    p.drawRect(QRectF(3, 5, 26, 22)); p.setBrush(QColor(200, 210, 224)); p.drawRect(QRectF(20, 5, 9, 22))


def _size(n):
    def draw(p, P):
        side = {1: 8, 2: 13, 3: 20}[n]
        p.setBrush(QColor(200, 210, 224)); p.drawRect(QRectF(16 - side / 2, 16 - side / 2, side, side))
    return draw


def _text_below(p, P):
    p.drawRect(QRectF(9, 4, 14, 13)); p.setPen(_pen(ACCENT, 1.8)); p.drawLine(P(7, 22), P(25, 22)); p.drawLine(P(10, 27), P(22, 27))


def _toolbar(p, P):
    p.drawRect(QRectF(3, 10, 26, 12)); p.setPen(_pen(ACCENT, 1.6))
    for x in (6, 13, 20):
        p.drawRect(QRectF(x, 13, 5, 6))


def _lock(p, P):
    p.drawRoundedRect(QRectF(7, 14, 18, 14), 2, 2); p.drawArc(QRectF(10, 5, 12, 16), 0, 180 * 16)
    p.setPen(_pen(ACCENT, 2.4)); p.drawLine(P(16, 19), P(16, 23))


def _status(p, P):
    p.drawRect(QRectF(3, 5, 26, 22)); p.setBrush(QColor(200, 210, 224)); p.drawRect(QRectF(3, 22, 26, 5))


def _reset(p, P):
    p.setPen(_pen(ACCENT, 2.4)); p.drawArc(QRectF(6, 6, 20, 20), 90 * 16, 270 * 16)
    p.drawLine(P(16, 6), P(11, 3)); p.drawLine(P(16, 6), P(12, 10))


def _fan(p, P):
    p.drawEllipse(P(16, 16), 12, 12); p.setPen(_pen(ACCENT, 1.8))
    for a, b in (((16, 16), (16, 6)), ((16, 16), (25, 21)), ((16, 16), (7, 21))):
        p.drawLine(P(*a), P(*b))


_MORE = {
    "new": _new, "open": _open, "recover": _recover, "home": _home,
    "import": lambda p, P: _tray(p, P, False), "export": lambda p, P: _tray(p, P, True), "pdf": _pdf,
    "phase_existing": _phase("existing"), "phase_demolish": _phase("demolish"), "phase_new": _phase("new"),
    "tree": _tree, "railing": _railing, "part": _part, "hinge": _hinge, "place": _place, "edit": _edit,
    "sculpt": _sculpt, "tape": _tape, "autodim": _autodim, "line": _line, "polyline": _polyline, "rect": _rect,
    "circle": _circle, "arc": _arc, "note": _note, "leader": _leader, "sheet": _sheet, "section": _section,
    "elevation": _elevation, "price": _price, "view3d": _cube, "ortho": lambda p, P: _cube(p, P, False),
    "top": _top, "front": _front, "side": _side, "realistic": _realistic, "split": _split, "ao": _ao,
    "sun": _sun, "moon": _moon, "studio": _studio, "bulb_on": _bulb(True), "bulb_off": _bulb(False),
    "clock": _clock, "layers": _layers, "update": _update, "units": _units, "mouse": _mouse, "info": _info,
    "panel": _panel, "size_s": _size(1), "size_m": _size(2), "size_l": _size(3), "text_below": _text_below,
    "toolbar": _toolbar, "lock": _lock, "status": _status, "reset": _reset, "fan": _fan,
}
NAMES = tuple(_MORE)


def _pixmap(name, size=32):
    pix = QPixmap(size, size); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.scale(size / 32.0, size / 32.0)
    _draw(name, p)
    p.end()
    return pix


def icon(name):
    key = ("icon", name)
    if key not in _cache:
        _cache[key] = QIcon(_pixmap(name, 48))
    return _cache[key]


def icon_data(name):
    """``data:image/png;base64,…`` of the same icon (for the 3D view's web menu)."""
    key = ("data", name)
    if key not in _cache:
        raw = QByteArray(); buf = QBuffer(raw); buf.open(QIODevice.OpenModeFlag.WriteOnly)
        _pixmap(name, 40).save(buf, "PNG"); buf.close()
        _cache[key] = "data:image/png;base64," + base64.b64encode(bytes(raw)).decode("ascii")
    return _cache[key]


def with_icon_data(entries):
    """Copies of ``entries`` (and submenus) with ``iconData`` for the web menu."""
    out = []
    for e in entries:
        e = dict(e)
        if e.get("icon"):
            e["iconData"] = icon_data(e["icon"])
        if e.get("children"):
            e["children"] = with_icon_data(e["children"])
        out.append(e)
    return out
