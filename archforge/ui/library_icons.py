"""Icons of the library tree (QPainter): you see what you pick.

* objects (assets): a 3/4 thumbnail of the stored mesh in its own colours
  (``library/thumbnail.py``), cached as PNG next to the assets so it is drawn
  once per machine;
* materials: the real swatch, joints at scale (``ui/pattern_swatch.py``);
* tools and presets (column, beam, window, door, cabinet, railing, drywall,
  plumbing, electrical, ventilation): a small pictogram of the element.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap, QPolygonF

ICON_SIZE = 40
_ICONS: dict = {}

_INK = QColor("#3d4652")
_FILL = QColor("#dfe5ec")


def _canvas(size):
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return image, painter


def asset_thumbnail(asset_id, size=ICON_SIZE):
    """QImage of an asset (cached on disk); ``None`` when the asset is missing."""
    from archforge.library import assets
    from archforge.library.thumbnail import thumbnail_faces
    path = assets.asset_dir() / "thumbs" / f"{asset_id}_{size}.png"
    if path.is_file():
        image = QImage(str(path))
        if not image.isNull():
            return image
    record = assets.load_asset(asset_id)
    if not record:
        return None
    image, painter = _canvas(size)
    for points, color in thumbnail_faces(record, size):
        fill = QColor(color)
        painter.setPen(QPen(fill.darker(112), 0.6))
        painter.setBrush(fill)
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in points]))
    painter.end()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(path))
    except OSError:
        pass
    return image


def opening_thumbnail(key, size=ICON_SIZE):
    """Outside elevation of the real preset: no triangulation seams or hidden panels."""
    from archforge.library.joinery_preview import preview_boxes
    boxes = preview_boxes(key)
    image, painter = _canvas(size)
    margin = max(2, size // 16)
    x0 = min(lo[0] for lo, hi, color in boxes)
    x1 = max(hi[0] for lo, hi, color in boxes)
    z0 = min(lo[2] for lo, hi, color in boxes)
    z1 = max(hi[2] for lo, hi, color in boxes)
    scale = (size - 2 * margin) / max(x1-x0, z1-z0)
    cx, cz = (x0+x1)/2, (z0+z1)/2
    # Looking from -s: far faces first. Sorting along depth only is exact for
    # this orthographic elevation, unlike average triangle-depth ordering.
    for lo, hi, color in sorted(boxes, key=lambda b: -b[0][1]):
        fill = QColor(color)
        painter.setPen(QPen(fill.darker(125), max(0.4, size/600)))
        painter.setBrush(fill)
        painter.drawRect(QRectF(size/2+(lo[0]-cx)*scale, size/2-(hi[2]-cz)*scale,
                                (hi[0]-lo[0])*scale, (hi[2]-lo[2])*scale))
    painter.end()
    return image


# ------------------------------------------------------------ pictograms ---

def _column(p, s):
    p.drawRect(QRectF(s * .38, s * .12, s * .24, s * .76))
    p.drawLine(QPointF(s * .38, s * .12), QPointF(s * .62, s * .88))


def _beam(p, s):
    p.drawRect(QRectF(s * .08, s * .38, s * .84, s * .24))
    for x in (.08, .92):
        p.drawLine(QPointF(s * x, s * .62), QPointF(s * x, s * .85))


def _railing(p, s):
    p.drawLine(QPointF(s * .1, s * .25), QPointF(s * .9, s * .25))
    p.drawLine(QPointF(s * .1, s * .85), QPointF(s * .9, s * .85))
    for k in range(5):
        x = s * (.14 + .18 * k)
        p.drawLine(QPointF(x, s * .25), QPointF(x, s * .85))


def _drywall(p, s):
    p.drawRect(QRectF(s * .08, s * .30, s * .84, s * .14))
    for k in range(4):
        x = s * (.2 + .2 * k)
        p.drawLine(QPointF(x, s * .12), QPointF(x, s * .30))
    p.drawEllipse(QPointF(s * .5, s * .62), s * .06, s * .06)


def _cabinet(p, s):
    p.drawRect(QRectF(s * .14, s * .2, s * .72, s * .68))
    p.drawLine(QPointF(s * .14, s * .36), QPointF(s * .86, s * .36))
    p.drawLine(QPointF(s * .5, s * .36), QPointF(s * .5, s * .88))
    p.drawLine(QPointF(s * .42, s * .5), QPointF(s * .42, s * .62))
    p.drawLine(QPointF(s * .58, s * .5), QPointF(s * .58, s * .62))


def _window(p, s):
    p.drawRect(QRectF(s * .14, s * .14, s * .72, s * .72))
    p.drawLine(QPointF(s * .5, s * .14), QPointF(s * .5, s * .86))
    p.setBrush(QColor("#bcd8ee"))
    p.drawRect(QRectF(s * .2, s * .2, s * .24, s * .6))
    p.drawRect(QRectF(s * .56, s * .2, s * .24, s * .6))


def _door(p, s):
    p.drawRect(QRectF(s * .26, s * .08, s * .48, s * .84))
    p.setBrush(_INK)
    p.drawEllipse(QPointF(s * .64, s * .52), s * .035, s * .035)


def _plumb(p, s):
    path = QPolygonF([QPointF(s * .5, s * .1), QPointF(s * .75, s * .55), QPointF(s * .5, s * .88),
                      QPointF(s * .25, s * .55)])
    p.setBrush(QColor("#9cc8ea"))
    p.drawPolygon(path)


def _elec(p, s):
    p.setBrush(QColor("#f2d36b"))
    p.drawPolygon(QPolygonF([QPointF(s * .58, s * .08), QPointF(s * .26, s * .55), QPointF(s * .48, s * .55),
                             QPointF(s * .40, s * .92), QPointF(s * .74, s * .42), QPointF(s * .52, s * .42)]))


def _vent(p, s):
    p.drawEllipse(QPointF(s * .5, s * .5), s * .38, s * .38)
    for a, b in (((.5, .5), (.5, .16)), ((.5, .5), (.80, .66)), ((.5, .5), (.20, .66))):
        p.drawLine(QPointF(s * a[0], s * a[1]), QPointF(s * b[0], s * b[1]))


def _generic(p, s):
    p.drawRect(QRectF(s * .2, s * .2, s * .6, s * .6))


_PICTOS = {"column": _column, "beam": _beam, "railing": _railing, "drywall": _drywall,
           "cabinet": _cabinet, "window": _window, "door": _door, "plumb": _plumb,
           "elec": _elec, "vent": _vent, "generic": _generic}


def pictogram_kind(action) -> str:
    """Which pictogram a library action shows (see ``MainWindow._library_outline``)."""
    if not action:
        return "generic"
    kind = action[0]
    name = str(action[1]) if len(action) > 1 else ""
    if kind == "structural":
        return "beam" if "beam" in name else "column"
    if kind == "railing" or (kind == "tool" and name.startswith("railing")):
        return "railing"
    if kind == "cabinet":
        return "cabinet"
    if kind == "opening":
        from archforge.architecture.joinery import PRESETS
        for key, opening_kind, *_rest in PRESETS:
            if key == name:
                return "door" if opening_kind == "door" else "window"
        return "window"
    if kind == "tool":
        for prefix in ("plumb", "elec", "vent", "drywall"):
            if name.startswith(prefix):
                return prefix
    return "generic"


def pictogram(kind, size=ICON_SIZE):
    image, painter = _canvas(size)
    painter.setPen(QPen(_INK, max(1.2, size / 26)))
    painter.setBrush(_FILL)
    _PICTOS.get(kind, _generic)(painter, size)
    painter.end()
    return image


def library_icon(action, size=ICON_SIZE, doc=None) -> QIcon:
    """Icon of one library leaf (asset thumbnail, material swatch or pictogram)."""
    if not action:
        return QIcon()
    kind = action[0]
    key = (kind, action[1] if kind in ("asset", "material", "opening") else pictogram_kind(action), size)
    if kind == "material":
        # The user can edit a material: the look itself is part of the key.
        import json
        from archforge.rendering.materials import material_spec
        spec = material_spec(str(action[1]), doc) or {}
        key += (json.dumps([spec.get("color"), spec.get("pattern")], sort_keys=True, default=str),)
    if key in _ICONS:
        return _ICONS[key]
    image = None
    if kind == "asset":
        image = asset_thumbnail(action[1], size)
    elif kind == "opening":
        image = opening_thumbnail(action[1], size)
    elif kind == "material":
        from archforge.ui.pattern_swatch import material_swatch
        image = material_swatch(action[1], size, size, doc=doc)
    if image is None:
        image = pictogram(key[1] if kind not in ("asset", "material") else "generic", size)
    icon = QIcon(QPixmap.fromImage(image))
    _ICONS[key] = icon
    return icon
