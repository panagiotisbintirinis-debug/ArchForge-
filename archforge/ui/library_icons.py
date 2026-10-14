"""Qt-native library icons; asset thumbnails use the actual stored mesh."""
from functools import lru_cache
import math
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication, QStyle


def category_icon():
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)


@lru_cache(maxsize=512)
def asset_icon(asset_id, size=48, folder=''):
    # Folder is part of the cache key: importing a different local library is safe.
    from archforge.library.assets import load_asset
    record = load_asset(str(asset_id))
    if not record:
        return category_icon()
    pix = QPixmap(size, size); pix.fill(QColor('#f3f6fa'))
    painter = QPainter(pix); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    vertices = record['vertices']
    projected = [(0.82*(x-y), .38*(x+y)-.92*z) for x, y, z in vertices]
    lo_x, hi_x = min(v[0] for v in projected), max(v[0] for v in projected)
    lo_y, hi_y = min(v[1] for v in projected), max(v[1] for v in projected)
    scale = (size-8)/max(hi_x-lo_x, hi_y-lo_y, 1e-6)
    cx, cy = (lo_x+hi_x)/2, (lo_y+hi_y)/2
    points = [QPointF(size/2+(x-cx)*scale, size/2+(y-cy)*scale) for x,y in projected]
    palette = record.get('palette') or ['#a6bac9']
    indices = record.get('tri_part') or []
    # Painter's ordering for this isometric viewing direction.
    order = sorted(range(len(record['triangles'])), key=lambda n: sum(
        vertices[i][0]+vertices[i][1]+vertices[i][2] for i in record['triangles'][n]))
    painter.setPen(QPen(QColor('#34495e'), .35))
    for n in order:
        tri = record['triangles'][n]
        color = QColor(palette[indices[n]] if n < len(indices) and indices[n] < len(palette) else palette[0])
        a,b,c = [vertices[i] for i in tri]
        u,v = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
        normal = (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        length = math.sqrt(sum(t*t for t in normal)) or 1
        shade = .72+.28*abs(sum(t*l for t,l in zip(normal,(.3,.4,.86)))/length)
        color.setRgbF(color.redF()*shade,color.greenF()*shade,color.blueF()*shade)
        painter.setBrush(color); painter.drawPolygon(QPolygonF([points[i] for i in tri]))
    painter.end()
    return QIcon(pix)


@lru_cache(maxsize=256)
def _preset_material_icon(material_id):
    from archforge.ui.pattern_swatch import material_icon
    return material_icon(material_id, 40)


def action_icon(action, label=''):
    """One visual identity in the tree, list and object menus."""
    from archforge.library.assets import data_dir
    if action and action[0] == 'asset':
        return asset_icon(str(action[1]), size=64, folder=str(data_dir()))
    if action and action[0] == 'material':
        return _preset_material_icon(str(action[1]))
    key = str(action[0] if action else 'folder')
    # Small line drawings, independent of fonts or an icon theme being installed.
    pix = QPixmap(40,40); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor('#315c82'),2)); p.setBrush(QColor('#e0edf7'))
    if key == 'sample_material':
        p.drawLine(10,30,29,11); p.drawLine(7,33,12,31)
        p.drawPolygon(QPolygonF([QPointF(24,6),QPointF(34,16),QPointF(30,20),QPointF(20,10)]))
    elif key in ('materials','color'):
        for x,y,c in ((8,8,'#bca27e'),(23,8,'#849ea9'),(8,23,'#abbd93'),(23,23,'#b99dba')):
            p.fillRect(x,y,11,11,QColor(c))
    elif key == 'delete':
        p.drawLine(9,10,31,10); p.drawRect(12,12,16,22)
        p.drawLine(16,5,24,5); p.drawLine(17,16,17,30); p.drawLine(23,16,23,30)
    elif key in ('move', 'rotate', 'stretch'):
        p.drawLine(6,20,34,20); p.drawLine(6,20,12,14); p.drawLine(6,20,12,26)
        p.drawLine(34,20,28,14); p.drawLine(34,20,28,26)
        if key == 'rotate': p.drawArc(8,7,24,24,30*16,280*16)
    elif key == 'properties':
        p.drawRect(9,4,22,32)
        for y in (12,20,28): p.drawLine(14,y,27,y)
    elif key == 'transform':
        p.drawLine(8,31,33,31); p.drawLine(8,31,8,6)
        p.drawLine(33,31,28,27); p.drawLine(33,31,28,35)
        p.drawLine(8,6,4,11); p.drawLine(8,6,12,11)
        p.drawRect(17,11,12,12)
    elif key == 'cabinet':
        p.drawRect(7,5,26,29); p.drawLine(20,5,20,34); p.drawLine(17,17,17,22); p.drawLine(23,17,23,22)
    elif key == 'opening':
        p.drawRect(8,4,24,32); p.drawLine(20,4,20,36); p.drawLine(8,20,32,20)
    elif key == 'structural':
        p.drawRect(13,6,14,28); p.drawLine(7,35,33,35); p.drawLine(7,5,33,5)
    elif key in ('railing','tool'):
        p.drawLine(5,10,35,10)
        for x in (7,15,23,31): p.drawLine(x,10,x,34)
    else:
        p.drawRect(6,10,28,23); p.drawRect(6,6,12,6)
    p.end(); return QIcon(pix)
