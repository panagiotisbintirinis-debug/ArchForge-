"""Material swatches for the materials dialog (QPainter).

Draws the same pattern period as the 3D view (``rendering/patterns.py``,
painted in JS by ``patternPaint`` in ``ui/pbr_viewport.py``): joint colour,
a soft shadow under raised stones, each stone/tile in its own tone with a
light-to-dark gradient, then grain/vein lines.  Materials without a pattern
get a plain colour swatch.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QImage, QLinearGradient, QPainter, QPen, QPixmap, QPolygonF

from archforge.rendering.materials import material_spec
from archforge.rendering.patterns import pattern_geometry, shade


def swatch_span(pattern) -> float:
    """Metres shown across a swatch: a few units, so a tile reads as a tile."""
    if not pattern:
        return 1.0
    if pattern.get("type") == "grain":
        return 0.8                       # a door-sized piece of board
    if pattern.get("type") == "speckle":
        return max(0.2, min(0.6, 60 * float(pattern["unit_w"])))
    return max(0.3, min(2.0, 6.0 * float(pattern["unit_w"])))


def paint_pattern(painter: QPainter, geometry: dict, width: int, height: int, ppm: float) -> None:
    """Fill a width x height pixel area with the pattern at ``ppm`` pixels per metre."""
    gw, gh = float(geometry["width"]), float(geometry["height"])
    painter.fillRect(0, 0, width, height, QColor(geometry["joint_color"]))
    relief = float(geometry.get("relief", 0.0))
    shadow = max(1.0, relief * float(geometry["joint"]) * 0.45 * ppm) if relief >= 0.5 else 0.0
    shadow_color = QColor(shade(geometry["joint_color"], -0.45))
    painter.setPen(Qt.PenStyle.NoPen)
    tiles_x = int(width / (gw * ppm)) + 2
    tiles_y = int(height / (gh * ppm)) + 2
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            ox, oy = tx * gw * ppm, height - ty * gh * ppm   # y up, from the bottom edge
            for cell in geometry["cells"]:
                poly = QPolygonF([QPointF(ox + x * ppm, oy - y * ppm) for x, y in cell["pts"]])
                box = poly.boundingRect()
                if box.right() < 0 or box.left() > width or box.bottom() < 0 or box.top() > height:
                    continue
                if shadow:
                    painter.setBrush(shadow_color)
                    painter.drawPolygon(poly.translated(shadow, shadow))
                k = 0.10 * relief
                grad = QLinearGradient(box.topLeft(), box.bottomRight())
                grad.setColorAt(0.0, QColor(shade(cell["color"], k)))
                grad.setColorAt(1.0, QColor(shade(cell["color"], -k)))
                painter.setBrush(QBrush(grad))
                painter.drawPolygon(poly)
            for line in geometry["lines"]:
                pen = QPen(QColor(line["color"]))
                pen.setWidthF(max(0.8, float(line["width"]) * ppm))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setOpacity(0.75)
                painter.drawPolyline(QPolygonF([QPointF(ox + x * ppm, oy - y * ppm) for x, y in line["pts"]]))
                painter.setOpacity(1.0)
                painter.setPen(Qt.PenStyle.NoPen)


def material_swatch(material_id: str, width: int, height: int, doc=None, spec=None) -> QImage:
    """Preview image of a material; patterned ones show joints at scale.

    ``spec`` previews a material not saved yet (the «Νέο υλικό» form)."""
    spec = spec or material_spec(str(material_id), doc) or {}
    image = QImage(max(1, width), max(1, height), QImage.Format.Format_RGB32)
    image.fill(QColor(spec.get("color", "#9a9a9a")))
    pattern = spec.get("pattern")
    if not pattern:
        return image
    geometry = pattern_geometry(pattern, str(spec["color"]), seed=str(material_id))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    paint_pattern(painter, geometry, width, height, ppm=width / swatch_span(pattern))
    painter.end()
    return image


def material_icon(material_id: str, size: int = 28, doc=None) -> QIcon:
    return QIcon(QPixmap.fromImage(material_swatch(material_id, size, size, doc=doc)))
