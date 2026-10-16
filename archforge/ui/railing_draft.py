"""Railing drawn in the plan: click points, double click / Enter to finish.

Plain UI state (no Qt): the plan view feeds clicks and the cursor, and on
finish hands the points to the main window, which adds one ``railing``
entity through the shared commands (one undo).  Points are rounded to 1 cm;
Shift keeps the next segment horizontal or vertical; a click on the first
point closes the railing.
"""
from __future__ import annotations

import math

CLOSE_REACH = 0.15


class RailingDraft:
    def __init__(self):
        self.points = []
        self.cursor = None
        self.closed = False

    def _snap(self, x, y, ortho=False):
        x, y = round(float(x), 2), round(float(y), 2)
        if ortho and self.points:
            px, py = self.points[-1]
            if abs(x - px) >= abs(y - py):
                y = py
            else:
                x = px
        return x, y

    def add(self, x, y, ortho=False):
        """Add a corner; True when this click closed the railing on its first point."""
        x, y = self._snap(x, y, ortho)
        if len(self.points) >= 3 and math.hypot(x - self.points[0][0], y - self.points[0][1]) <= CLOSE_REACH:
            self.closed = True
            return True
        if self.points and math.hypot(x - self.points[-1][0], y - self.points[-1][1]) < 0.01:
            return False                     # the second press of a double click
        self.points.append((x, y))
        return False

    def move(self, x, y, ortho=False):
        self.cursor = self._snap(x, y, ortho)

    def preview(self):
        """Polyline to draw while drawing (with the rubber band to the cursor)."""
        pts = list(self.points)
        if self.closed and pts:
            return pts + pts[:1]
        if self.cursor is not None and pts:
            pts.append(self.cursor)
        return pts

    def finish(self):
        """``(points, closed)`` when there is a railing to add, else None."""
        if len(self.points) < 2:
            return None
        return [list(q) for q in self.points], self.closed
