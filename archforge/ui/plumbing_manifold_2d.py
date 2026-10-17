"""Technical-plan emphasis for derived plumbing manifolds."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsTextItem


def install() -> None:
    from archforge.ui import plumbing_tab

    cls = plumbing_tab.PlumbingTechnicalPlan
    if getattr(cls, "_archforge_manifold_2d_installed", False):
        return
    original = cls.redraw

    def redraw(self):
        original(self)
        try:
            from archforge.mep.plumbing import route_plumbing_cached
            routed = route_plumbing_cached(self.doc)
            level = float(self.doc.work_plane.origin[2])
            for manifold in routed.get("manifolds", ()):
                if abs(float(manifold.get("z", 0.0)) - level) > 1e-6:
                    continue
                system = str(manifold.get("system", "cold"))
                outlets = list(manifold.get("outlets", ()))
                n = len(outlets)
                x = float(manifold["x"])
                y = float(manifold["y"]) + (0.10 if system == "hot" else -0.10)
                w = 0.10 + 0.05 * n
                h = 0.14
                colour = QColor(31, 90, 160) if system == "cold" else QColor(190, 55, 45)
                pen = QPen(colour)
                pen.setWidthF(2.0)
                pen.setCosmetic(True)
                fill = QColor(colour)
                fill.setAlpha(28)
                box = self._scene.addRect(x - w / 2, y - h / 2, w, h, pen, QBrush(fill))
                box.setZValue(90)
                box.setToolTip(f"Συλλέκτης {'κρύου' if system == 'cold' else 'ζεστού'} — {n} εξόδων")

                # Outlet ticks make the object read as a collector, not a generic box.
                for k in range(n):
                    px = x - w / 2 + w * (k + 1) / (n + 1)
                    tick = self._scene.addLine(px, y - h / 2, px, y + h / 2, pen)
                    tick.setZValue(91)

                label = self._scene.addText(f"Σ{'Κ' if system == 'cold' else 'Ζ'}-{n}")
                label.setDefaultTextColor(colour)
                font = label.font(); font.setBold(True); label.setFont(font)
                label.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                label.setPos(x + w / 2 + 0.04, y)
                label.setZValue(92)
                label.setToolTip("Παρουσίαση συλλέκτη — ακριβές προϊόν/διαστάσεις όταν επιλεγεί κατασκευαστής")
        except Exception:
            pass

    cls.redraw = redraw
    cls._archforge_manifold_2d_installed = True
