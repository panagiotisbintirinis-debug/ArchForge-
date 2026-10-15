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
    elif name == "fit":
        p.drawLine(P(4, 5), P(28, 5)); p.drawRect(QRectF(9, 14, 14, 14))
        p.setPen(_pen(ACCENT)); p.drawLine(P(16, 13), P(16, 7)); p.drawLine(P(16, 7), P(13, 10)); p.drawLine(P(16, 7), P(19, 10))
    elif name == "camera":
        p.drawRoundedRect(QRectF(4, 10, 18, 13), 2, 2)
        p.drawPolygon(QPolygonF([P(22, 14), P(29, 10), P(29, 23), P(22, 19)]))
    else:
        p.drawEllipse(P(16, 16), 9, 9)


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
