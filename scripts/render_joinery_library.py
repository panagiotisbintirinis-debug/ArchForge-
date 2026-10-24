"""Render review sheets from actual joinery library thumbnails (no external assets).

Run: QT_QPA_PLATFORM=offscreen python scripts/render_joinery_library.py
"""
from pathlib import Path
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication
from archforge.architecture.joinery import PRESETS
from archforge.ui.library_icons import opening_thumbnail


def render_sheet(kind, output):
    items = [p for p in PRESETS[19:] if p[1] == kind]
    cols, tw, th = 4, 320, 340
    rows = (len(items) + cols - 1) // cols
    image = QImage(cols * tw, 100 + rows * th, QImage.Format.Format_ARGB32)
    image.fill(QColor('#f1f3f5'))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor('#243544')); painter.setFont(QFont('DejaVu Sans', 20, QFont.Weight.Bold))
    title = 'Νέα παράθυρα' if kind == 'window' else 'Νέες πόρτες & μπαλκονόπορτες'
    painter.drawText(QRectF(20, 10, image.width()-40, 45), title + f' · {len(items)} σχέδια')
    painter.setFont(QFont('DejaVu Sans', 10))
    painter.drawText(QRectF(20, 55, image.width()-40, 30), 'ArchForge · Παραμετρικά σχέδια · Οι διαστάσεις αλλάζουν στις Ιδιότητες')
    for i, (key, _kind, name, *_rest) in enumerate(items):
        x, y = (i % cols) * tw, 100 + (i // cols) * th
        painter.fillRect(QRectF(x+8, y+6, tw-16, th-12), QColor('white'))
        thumb = opening_thumbnail(key, 240)
        painter.drawImage(x+40, y+12, thumb)
        painter.setPen(QColor('#243544')); painter.setFont(QFont('DejaVu Sans', 11))
        painter.drawText(QRectF(x+20, y+260, tw-40, 66), Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap, name)
    painter.end()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(output)):
        raise RuntimeError(f'Could not save {output}')
    print(output)


if __name__ == '__main__':
    app = QApplication.instance() or QApplication([])
    folder = Path(sys.argv[1]) if len(sys.argv)>1 else Path('docs/media/joinery')
    for kind in ('window', 'door'):
        render_sheet(kind, folder / f'new_{kind}_designs.png')
