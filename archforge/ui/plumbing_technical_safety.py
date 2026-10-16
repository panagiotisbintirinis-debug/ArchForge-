"""Safety patch for the Plumbing technical-plan connectivity overlay.

The topology helper can report junctions and risers, but screen-fixed ellipse
items with metre-sized scene bounds can distort QGraphicsScene extents and the
plan ruler.  Until dedicated marker primitives are implemented, draw only the
proven bend bridges.  This preserves network continuity without changing
routing, BOM or the technical-plan pan/zoom behaviour.
"""
from __future__ import annotations

from PySide6.QtGui import QPen


def install_safe_connectivity_overlay():
    from archforge.ui.plumbing_tab import PlumbingTechnicalPlan

    if getattr(PlumbingTechnicalPlan, "_archforge_safe_connectivity_overlay", False):
        return

    def _draw_connectivity(self, routed, level, screed, hot_offset):
        from archforge.mep.plumbing_drawing import technical_plan_topology

        topology = technical_plan_topology(routed, level, screed, hot_offset)
        for bridge in topology["bridges"]:
            colour = self._network_colour(bridge["network"])
            pen = QPen(colour)
            pen.setWidthF(2.4)
            pen.setCosmetic(True)
            a, b = bridge["a"], bridge["b"]
            item = self._scene.addLine(a[0], a[1], b[0], b[1], pen)
            item.setZValue(79)

    PlumbingTechnicalPlan._draw_connectivity = _draw_connectivity
    PlumbingTechnicalPlan._archforge_safe_connectivity_overlay = True
