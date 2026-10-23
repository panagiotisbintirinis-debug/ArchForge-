"""Αρχική σελίδα (owner 23/10: «κάτι τέτοιο με το σύμβολο του ArchForge σαν background» — the Home Designer
dashboard): the first tab when the program opens — new / open / sample / drawing set on the left, the recent
projects under them, getting started and resources on the right, the build at the bottom; the ArchForge mark large
and faint behind it all.  Αρχείο ▸ «Αρχική σελίδα» brings it back.

Recent projects are kept in the user's data folder (``recent.json``): every project opened or saved.
"""
from __future__ import annotations

import json
import math
import os

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

TITLE = "Αρχική"
RECENT_MAX = 10
DARK = QColor(46, 49, 54)
INK = QColor(230, 233, 237)
ACCENT = QColor(220, 120, 40)         # forge orange
BLUE = QColor(35, 95, 160)


# --------------------------------------------------------------------------------------------- recent projects
def _recent_file():
    from archforge.library.assets import data_dir
    return data_dir() / "recent.json"


def recent(limit=RECENT_MAX):
    """Recent projects that still exist, newest first."""
    try:
        paths = json.loads(_recent_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [p for p in paths if isinstance(p, str) and os.path.exists(p)][:limit]


def remember(path):
    """``path`` to the top of the recent projects (a sample or backup is not a project of the person's)."""
    if not path or not str(path).endswith(".archforge"):
        return
    path = os.path.abspath(path)
    try:
        old = json.loads(_recent_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = []
    paths = [path] + [p for p in old if isinstance(p, str) and os.path.abspath(p) != path]
    try:
        _recent_file().parent.mkdir(parents=True, exist_ok=True)
        _recent_file().write_text(json.dumps(paths[:RECENT_MAX * 2], ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------------------------- the mark
def mark_path(size):
    """The ArchForge mark in a ``size`` square: a stone arch — its voussoirs round a semicircle, the keystone
    standing proud at the top, on two piers of laid stones (owner 23/10: «το σχέδιο είναι η καμάρα με τις πέτρες»).
    Pure vector, no image file."""
    s = size
    cx, spring = 0.5 * s, 0.56 * s                 # centre of the arch and the springing line
    r_in, r_out = 0.25 * s, 0.40 * s
    gap = math.radians(2.2)
    path = QPainterPath()
    n = 9                                          # voussoirs, the middle one the keystone

    def at(r, a):
        return QPointF(cx + r * math.cos(a), spring - r * math.sin(a))
    for k in range(n):
        a0 = math.pi * (n - k) / n - (0 if k == 0 else gap / 2)
        a1 = math.pi * (n - k - 1) / n + (0 if k == n - 1 else gap / 2)
        outer = r_out + (0.06 * s if k == n // 2 else 0.0)      # the keystone stands proud
        stone = QPainterPath(at(r_in, a0))
        stone.lineTo(at(outer, a0))
        stone.lineTo(at(outer, a1))
        stone.lineTo(at(r_in, a1))
        stone.closeSubpath()
        path.addPath(stone)
    # Piers: stones laid in courses under each springing.
    course, gap_y = 0.085 * s, 0.012 * s
    for side in (-1, 1):
        x0 = cx + side * r_in if side > 0 else cx - r_out
        width = r_out - r_in
        y = spring + gap_y
        for row in range(4):
            path.addRect(QRectF(x0, y, width, course))
            y += course + gap_y
    return path.simplified()


class Mark(QWidget):
    """The mark at a fixed size (the header)."""

    def __init__(self, size=56, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, BLUE); g.setColorAt(1.0, ACCENT)
        p.fillPath(mark_path(self.width()), QBrush(g))


class _Dark(QWidget):
    """The dark body with the mark large and faint behind it."""

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), DARK)
        size = min(self.width(), self.height()) * 0.95
        p.translate(self.width() - size * 0.92, (self.height() - size) / 2)
        c = QColor(255, 255, 255, 14)
        p.fillPath(mark_path(size), c)


def _link(text, run, big=False):
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFlat(True)
    f = b.font(); f.setPointSizeF(f.pointSizeF() * (1.25 if big else 1.05)); b.setFont(f)
    b.setStyleSheet(f"QPushButton{{color:#E6E9ED;text-align:left;border:none;padding:4px 2px;background:transparent;"
                    f"font-size:{17 if big else 15}px}}"
                    "QPushButton:hover{color:#F0A050;text-decoration:underline}")
    b.clicked.connect(lambda _=False: run())
    return b


def _heading(text):
    h = QLabel(text)
    f = h.font(); f.setPointSizeF(f.pointSizeF() * 1.9); f.setWeight(QFont.Weight.Light); h.setFont(f)
    h.setStyleSheet("color:#E6E9ED;background:transparent;font-size:26px;font-weight:300;padding:6px 0")
    return h


class StartPage(QWidget):
    opened = Signal()

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        # Header: the mark and the name on white.
        head = QWidget(); head.setStyleSheet("background:#FFFFFF")
        hl = QHBoxLayout(head); hl.setContentsMargins(60, 18, 60, 18)
        hl.addStretch(1)
        hl.addWidget(Mark(72))
        name = QLabel("<span style='color:#235FA0'>Arch</span><span style='color:#DC7828'>Forge</span>")
        name.setStyleSheet("font-size:54px;font-weight:300")
        f = name.font(); f.setPointSizeF(f.pointSizeF() * 3.6); f.setWeight(QFont.Weight.Light); name.setFont(f)
        sub = QLabel("Σχεδιασμός · Κατασκευή · Η/Μ · Έδαφος — από το σχέδιο στο 3D")
        sub.setStyleSheet("color:#5B6778;font-size:15px")
        col = QVBoxLayout(); col.addWidget(name); col.addWidget(sub)
        hl.addSpacing(14); hl.addLayout(col); hl.addStretch(2)
        outer.addWidget(head)
        # Body.
        body = _Dark()
        bl = QHBoxLayout(body); bl.setContentsMargins(40, 24, 40, 24); bl.setSpacing(60)
        left = QVBoxLayout(); left.setSpacing(2)
        w = window
        for text, run in (("Νέο έργο", lambda: self._go(w.new_project)),
                          ("Άνοιγμα έργου…", lambda: self._go(w.open)),
                          ("Άνοιγμα δείγματος…", lambda: self._go(w.open_sample)),
                          ("Από τα σχέδια του μηχανικού (PDF)…", lambda: self._go(lambda: __import__(
                              "archforge.ui.drawing_set_import", fromlist=["import_set"]).import_set(w)))):
            left.addWidget(_link(text, run, big=True))
        left.addSpacing(24)
        left.addWidget(_heading("Πρόσφατα έργα"))
        self.recent_box = QVBoxLayout(); self.recent_box.setSpacing(0)
        left.addLayout(self.recent_box)
        left.addStretch(1)
        bl.addLayout(left, 1)
        right = QVBoxLayout(); right.setSpacing(2)
        right.addWidget(_heading("Ξεκίνημα"))
        for text, tip in (("Σχεδίασε τοίχους και δωμάτια", "Κατασκευή ▸ Τοίχοι & δωμάτια"),
                          ("Φέρε τα σχέδια του μηχανικού (PDF / DXF)", "Αρχείο ▸ Εισαγωγή"),
                          ("Έδαφος: στάθμες πλατωμάτων και τοιχία", "Κατασκευή ▸ Έδαφος & περιβάλλον"),
                          ("Ολοκλήρωση κτιρίου", "Κατασκευή ▸ Ολοκλήρωση κτιρίου…")):
            lab = QLabel(f"›  {text}<br><span style='color:#9AA5B4;font-size:small'>{tip}</span>")
            lab.setStyleSheet("color:#E6E9ED;background:transparent;padding:4px 0;font-size:15px")
            right.addWidget(lab)
        right.addSpacing(24)
        right.addWidget(_heading("Πόροι"))
        right.addWidget(_link("Έλεγχος για ενημερώσεις", lambda: __import__(
            "archforge.ui.updates_ui", fromlist=["check"]).check(w, True)))
        right.addWidget(_link("Τι νέο υπάρχει (αρχείο εργασιών)", lambda: self._worklog()))
        right.addStretch(1)
        bl.addLayout(right, 1)
        outer.addWidget(body, 1)
        # Footer: the build.
        foot = QWidget(); foot.setStyleSheet("background:#3A3E44")
        fl = QHBoxLayout(foot); fl.setContentsMargins(40, 10, 40, 10)
        fl.addStretch(1)
        fl.addWidget(QLabel(f"<span style='color:#C9D3DE;font-size:13px'>{build_text()}</span>"))
        outer.addWidget(foot)
        self.refresh()

    def refresh(self):
        while self.recent_box.count():
            item = self.recent_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        paths = recent()
        if not paths:
            empty = QLabel("Κανένα ακόμα — ό,τι ανοίγεις ή αποθηκεύεις εμφανίζεται εδώ")
            empty.setStyleSheet("color:#9AA5B4;background:transparent;font-size:14px")
            self.recent_box.addWidget(empty)
        for p in paths:
            b = _link(os.path.basename(p), lambda path=p: self._go(lambda: self.window.open(path)))
            b.setToolTip(p)
            self.recent_box.addWidget(b)

    def _go(self, run):
        """Run an action; the page steps aside when it leads to a project."""
        result = run()
        if result is not False:
            close_start(self.window)
        return result

    def _worklog(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "WORKLOG.md")
        if os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))


def build_text():
    from archforge import updates
    b = updates.current_build()
    if b:
        return f"Έκδοση {str(b.get('sha', ''))[:7]} · {b.get('date', '')}"
    return "Από τον κώδικα (git)"


# --------------------------------------------------------------------------------------------- the tab
def show_start(window):
    """The start page as the first tab (made current); returns it."""
    tabs = getattr(window, "_central_tabs", None)
    page = getattr(window, "_start_page", None)
    if page is None:
        page = window._start_page = StartPage(window)
    else:
        page.refresh()
    if tabs is not None:
        if tabs.indexOf(page) < 0:
            tabs.insertTab(0, page, TITLE)
        tabs.setCurrentWidget(page)
    return page


def close_start(window):
    tabs = getattr(window, "_central_tabs", None)
    page = getattr(window, "_start_page", None)
    if tabs is not None and page is not None and tabs.indexOf(page) >= 0:
        tabs.removeTab(tabs.indexOf(page))
        if tabs.count():
            tabs.setCurrentIndex(0)


def install(window):
    """Αρχείο ▸ «Αρχική σελίδα»."""
    from PySide6.QtGui import QAction
    menu = next((a.menu() for a in window.menuBar().actions() if a.menu() and a.text().replace("&", "") == "Αρχείο"), None)
    action = QAction("Αρχική σελίδα", window)
    action.triggered.connect(lambda: show_start(window))
    if menu is not None:
        first = menu.actions()[0] if menu.actions() else None
        menu.insertAction(first, action) if first else menu.addAction(action)
    window._start_action = action
    return action
