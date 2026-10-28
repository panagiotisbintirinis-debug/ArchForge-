"""The mouse menu as the human wants it, per task (owner 15/10: «σου προτείνω να κάνουμε και το ποντίκι με
ικανότητα απορρόφησης εργασιών — κάθε ένας επιλέγει άλλη ανάλογα τι δουλεύει … μενού με εργασίες και
δυνατότητα προσθαφαίρεσης στα μενού του ποντικιού σε ξεχωριστό φάκελο ποντίκι με οπτικό έλεγχο· λες τι θέλω
να βάλω στο ποντίκι για αυτή την εργασία, κάνω drag and drop και το έχω, τι δεν θέλω το αφαιρώ, τι μέγεθος θα
είναι το μενού ανάλογα τις εργασίες που βάζω» · «αυτό είναι η λύση»).

* A **task** (εργασία) is the situation of the right click: empty space, drawing walls, a wall, a door/window,
  a piece of furniture, a stair, another object, Sculpt.
* Each task has the built-in menu (``marking_menu``); the human may replace it with his own list.  An item is
  a command of that task's menu (``mm:…`` / object action ids) or **any command of the menu bar**
  (``menu:Κατασκευή / Στέγη / Δίρριχτη``); a menu-bar submenu dropped in becomes a ▸ submenu.
* «Εργαλεία ▸ Μενού ποντικιού…»: tasks on the left, the ring as it will look in the middle (drag commands in,
  reorder, drag out = remove), every command on the right.  ≤ 4 = cross, ≤ 8 = ring, ≤ 16 = two rings.
* Saved with the layout preferences (``layout.ini``) — presentation only, never in the Document.
"""
from __future__ import annotations

import json
import math

from PySide6.QtCore import QMimeData, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

MIME = "application/x-archforge-mouse-item"
MAX_ITEMS = 16

TASKS = (("empty", "Κενός χώρος"), ("wall_draw", "Σχεδίαση τοίχων"), ("object:wall", "Τοίχος"),
         ("object:opening", "Πόρτα / παράθυρο"), ("object:furniture", "Έπιπλο / ντουλάπι"),
         ("object:stair", "Σκάλα / ράμπα"), ("object:other", "Άλλο αντικείμενο"), ("sculpt", "Γλυπτική"))
TASK_NAMES = dict(TASKS)


# --------------------------------------------------------------------------- which task
def task_of(window, view, entity_id=None):
    """The task of a right click (None: a temporary menu that is not customised, e.g. placing a stair)."""
    plan = getattr(window, "plan_view", None)
    tool = str(getattr(getattr(plan, "controller", None), "tool", "select"))
    if getattr(window, "sculpt_action", None) is not None and window.sculpt_action.isChecked():
        return "sculpt"
    pbr = getattr(window, "pbr_view", None)
    if tool in ("stair", "ramp") or (pbr is not None and getattr(pbr, "_stair_tx", None) is not None):
        return None
    if view == "plan" and tool == "wall":
        return "wall_draw"
    if tool.startswith("layout_") or getattr(window, "_marking_submenu", None):
        return None
    if entity_id and entity_id in window.doc.entities:
        kind = window.doc.get(entity_id).kind
        if kind == "wall":
            return "object:wall"
        if kind in ("door", "window", "opening"):
            return "object:opening"
        if kind in ("library_object", "cabinet"):
            return "object:furniture"
        if kind in ("stair", "ramp"):
            return "object:stair"
        return "object:other"
    return "empty"


# --------------------------------------------------------------------------- the saved menus
def saved(window):
    from archforge.ui.toolbar_custom import prefs
    return prefs(window).setdefault("mouse", {})


def _save(window):
    from archforge.ui.toolbar_custom import save
    save(window)


def set_task(window, task, items):
    saved(window)[task] = [dict(i) for i in items][:MAX_ITEMS]
    _save(window)


def reset_task(window, task):
    saved(window).pop(task, None)
    _save(window)


def flatten(entries):
    """Every command of a built-in menu (submenus opened), first occurrence of each id."""
    out, seen = [], set()

    def walk(es):
        for e in es:
            if e.get("children"):
                walk(e["children"])
                continue
            if e["id"] not in seen and not e["id"].startswith("mm:menu:"):
                seen.add(e["id"]); out.append(e)
    walk(entries)
    return out


def item_of(entry):
    """A saved item from a menu entry (only what is needed to show and run it); a submenu keeps its items."""
    item = {"id": entry["id"], "label": entry["label"].lstrip("✓↻ ").strip() or entry["label"]}
    if entry.get("children"):
        item["children"] = [item_of(c) for c in entry["children"]]
        item["icon"] = entry.get("icon") or "more"
        if entry.get("small"):
            item["small"] = True
        return item
    if entry.get("icon"):
        item["icon"] = entry["icon"]
    if entry.get("danger") or entry["id"] == "delete":
        item["danger"] = True
    return item


def item_of_path(path, action=None):
    """A saved item for a menu-bar command (or submenu) at ``path``."""
    from archforge.ui.toolbar_custom import SEP
    item = {"id": "menu:" + path, "label": path.split(SEP)[-1]}
    if action is not None and action.menu() is not None:
        item["submenu"] = True
    return item


def custom_entries(window, task, default_entries):
    """The human's menu for ``task`` as marking-menu entries, or None (built-in menu)."""
    items = saved(window).get(task)
    if not items:
        return None
    live = {e["id"]: e for e in flatten(default_entries)}
    return _entries(window, items, live)


def _entries(window, items, live):
    out = []
    for it in items:
        iid = it["id"]
        if it.get("children") and not iid.startswith("menu:"):
            e = {"id": iid, "label": it["label"], "placement": "radial", "checked": False, "danger": False,
                 "icon": it.get("icon") or "more", "children": _entries(window, it["children"], live)}
            if it.get("small"):
                e["small"] = True
            if e["children"]:
                out.append(e)
        elif iid.startswith("menu:"):
            e = {"id": iid, "label": it["label"], "placement": "radial", "checked": False, "danger": False,
                 "icon": it.get("icon") or "more"}
            if it.get("submenu"):
                e["children"] = _menu_children(window, iid[5:])
                if not e["children"]:
                    continue
            out.append(e)
        elif iid in live:                       # the live entry: current label / state (e.g. «Διαγραφή (Del)»)
            e = dict(live[iid]); e["placement"] = "radial"; out.append(e)
        else:
            out.append({"id": iid, "label": it["label"], "placement": "radial", "checked": False,
                        "danger": bool(it.get("danger")), **({"icon": it["icon"]} if it.get("icon") else {})})
    return out


def _find_action(window, path):
    from archforge.ui.toolbar_custom import SEP
    parts = path.split(SEP)
    actions = window.menuBar().actions()
    found = None
    for k, name in enumerate(parts):
        found = next((a for a in actions if a.text().replace("&&", "&") == name), None)
        if found is None:
            return None
        if k < len(parts) - 1:
            if found.menu() is None:
                return None
            if not found.menu().actions():
                found.menu().aboutToShow.emit()
            actions = found.menu().actions()
    return found


def _menu_children(window, path):
    from archforge.ui.toolbar_custom import SEP
    a = _find_action(window, path)
    if a is None or a.menu() is None:
        return []
    if not a.menu().actions():
        a.menu().aboutToShow.emit()
    out = []
    for c in a.menu().actions():
        if c.isSeparator() or not c.text():
            continue
        text = c.text().replace("&&", "&")
        child = {"id": "menu:" + path + SEP + text, "label": text, "placement": "radial", "checked": c.isChecked(),
                 "danger": False}
        if c.menu() is not None:
            child["children"] = _menu_children(window, path + SEP + text)
            if not child["children"]:
                continue
        elif not c.isEnabled():
            continue
        out.append(child)
    return out


def run_menu_path(window, path):
    """A menu-bar command chosen from the mouse menu: the very same QAction (same command, key, undo)."""
    a = _find_action(window, path)
    if a is None or a.menu() is not None:
        window.statusBar().showMessage(f"Η εντολή «{path}» δεν βρέθηκε στα μενού", 5000)
        return False
    a.trigger()
    return True


def catalog_items_for_test(window, n):
    """``n`` menu-bar commands as items (tests and examples)."""
    from archforge.ui.toolbar_custom import catalog
    return [item_of_path(p, a) for p, a in list(catalog(window).items())[:n]]


# --------------------------------------------------------------------------- ring geometry (shared)
def ring_slots(n, radius):
    """``[(dx, dy)]`` for ``n`` buttons: ≤ 4 a cross, ≤ 8 a ring, ≤ 16 two rings (outer in between)."""
    if n <= 4:
        angles = [0, 90, 180, 270][:n]
        return [(math.sin(math.radians(a)) * radius, -math.cos(math.radians(a)) * radius) for a in angles]
    inner = [(math.sin(math.radians(a)) * radius, -math.cos(math.radians(a)) * radius) for a in range(0, 360, 45)][:min(n, 8)]
    outer = [(math.sin(math.radians(a)) * radius * 1.85, -math.cos(math.radians(a)) * radius * 1.85)
             for a in [22.5 + 45 * k for k in range(8)]][:max(0, n - 8)]
    return inner + outer


# --------------------------------------------------------------------------- the editor
class RingPreview(QWidget):
    """The ring as it will look; drop commands in, drag to reorder, drag out (or Delete / right click) to remove."""
    changed = Signal(list)
    RADIUS = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(560, 520)
        self.items = []
        self.title = ""
        self.buttons = []
        self._press = None
        self.selected = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_items(self, items, title):
        self.items, self.title = [dict(i) for i in items], title
        self._layout()

    def _layout(self):
        from archforge.ui.menu_icons import icon
        for b in self.buttons:
            b.hide(); b.deleteLater()
        self.buttons = []
        cx, cy = self.width() / 2, self.height() / 2
        r = self.RADIUS if len(self.items) <= 8 else self.RADIUS * 0.95
        for k, ((dx, dy), it) in enumerate(zip(ring_slots(len(self.items), r), self.items)):
            b = QToolButton(self)
            b.setText(it["label"] + (" ▸" if it.get("submenu") or it.get("children") else ""))
            if it.get("icon"):
                b.setIcon(icon(it["icon"]))
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setStyleSheet("QToolButton { background:%s; border:1px solid %s; border-radius:8px; padding:3px 6px;"
                            " font-size:11px; color:#1E2A3B; }"
                            % ("#ffe9e7" if it.get("danger") else "#ffffff", "#2F6BD6" if k == self.selected else "#c3ccd8"))
            b.adjustSize()
            # Side buttons step out past the title, as in the real menu (marking_menu.MarkingMenu).
            half = self.fontMetrics().horizontalAdvance(self.title) / 2 + 9
            if abs(dx) > 0.5 * r:
                dx += math.copysign(max(0.0, half + 10 - abs(dx) + b.width() / 2), dx)
            b.move(int(cx + dx - b.width() / 2), int(cy + dy - b.height() / 2))
            b.installEventFilter(self)
            b.setProperty("slot", k)
            b.setToolTip("Σύρε για αλλαγή θέσης · σύρε έξω από τον κύκλο ή Delete = αφαίρεση")
            b.show()
            self.buttons.append(b)
        self.update()

    def resizeEvent(self, event):
        self._layout()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cx, cy = self.width() / 2, self.height() / 2
        n = len(self.items)
        r = self.RADIUS + 46 if n <= 8 else self.RADIUS * 1.85 + 46
        p.setPen(QPen(QColor(195, 204, 216), 1)); p.setBrush(QColor(246, 248, 251))
        p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(32, 41, 53, 230))
        fm = p.fontMetrics(); w = fm.horizontalAdvance(self.title) + 18
        p.drawRoundedRect(QRectF(cx - w / 2, cy - 11, w, 22), 9, 9)
        p.setPen(QColor(255, 255, 255)); p.drawText(QRectF(cx - w / 2, cy - 11, w, 22), Qt.AlignmentFlag.AlignCenter, self.title)
        p.setPen(QColor(107, 118, 134))
        shape = "σταυρός" if n <= 4 else ("κύκλος" if n <= 8 else "διπλός κύκλος")
        p.drawText(QRectF(0, self.height() - 22, self.width(), 20), Qt.AlignmentFlag.AlignCenter,
                   f"{n} εντολές · {shape} · μέγιστο {MAX_ITEMS} — σύρε εδώ εντολές από δεξιά" if n else
                   "Άδειο — σύρε εδώ εντολές από δεξιά (ή «Επαναφορά» για το αρχικό)")

    def _slot_at(self, pos):
        """The slot a drop at ``pos`` goes to: the nearest button, or the end."""
        best = None
        for k, b in enumerate(self.buttons):
            d = (b.geometry().center() - pos).manhattanLength()
            if best is None or d < best[0]:
                best = (d, k)
        return best[1] if best and best[0] < 70 else len(self.items)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj in self.buttons:
            k = obj.property("slot")
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._press = (k, event.position().toPoint()); self.selected = k; self.setFocus(); return False
            if event.type() == QEvent.Type.MouseMove and self._press is not None and \
                    (event.position().toPoint() - self._press[1]).manhattanLength() > 6:
                k = self._press[0]; self._press = None
                drag = QDrag(obj); data = QMimeData()
                data.setData(MIME, json.dumps({"move": k}).encode("utf8")); drag.setMimeData(data)
                drag.setPixmap(obj.grab())
                if drag.exec(Qt.DropAction.MoveAction) == Qt.DropAction.IgnoreAction:
                    self.remove(k)                  # dropped outside the ring: out of the menu
                return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._press = None; self._layout(); return False
            if event.type() == QEvent.Type.ContextMenu:
                m = QMenu(self); a = m.addAction("Αφαίρεση από το μενού")
                if m.exec(event.globalPos()) is a:
                    self.remove(k)
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selected is not None:
            self.remove(self.selected); return
        super().keyPressEvent(event)

    def remove(self, k):
        if 0 <= k < len(self.items):
            del self.items[k]
            self.selected = None
            self._layout(); self.changed.emit(self.items)

    def add(self, item, at=None):
        if len(self.items) >= MAX_ITEMS:
            return False
        if any(i["id"] == item["id"] for i in self.items):
            return False
        at = len(self.items) if at is None else max(0, min(at, len(self.items)))
        self.items.insert(at, dict(item))
        self._layout(); self.changed.emit(self.items)
        return True

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):
        data = json.loads(bytes(event.mimeData().data(MIME)).decode("utf8"))
        at = self._slot_at(event.position().toPoint())
        if "move" in data:
            k = int(data["move"])
            if 0 <= k < len(self.items):
                it = self.items.pop(k)
                self.items.insert(min(at, len(self.items)), it)
                self._layout(); self.changed.emit(self.items)
        elif "item" in data:
            self.add(data["item"], at)
        event.acceptProposedAction()


class CommandTree(QTreeWidget):
    """Every command that can go in the menu; drag one (or a whole submenu) into the ring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.DragOnly)

    def mimeData(self, items):
        data = QMimeData()
        it = items[0].data(0, Qt.ItemDataRole.UserRole) if items else None
        if it:
            data.setData(MIME, json.dumps({"item": it}).encode("utf8"))
        return data

    def mimeTypes(self):
        return [MIME]


class MouseMenuEditor(QDialog):
    def __init__(self, window, task=None):
        super().__init__(window)
        self.w = window
        self.setWindowTitle("Μενού ποντικιού — ανά εργασία")
        self.resize(1080, 620)
        lay = QHBoxLayout(self)
        left = QVBoxLayout(); lay.addLayout(left, 0)
        left.addWidget(QLabel("<b>Εργασία</b>"))
        self.tasks = QListWidget(); self.tasks.setFixedWidth(190)
        for key, name in TASKS:
            item = QListWidgetItem(name); item.setData(Qt.ItemDataRole.UserRole, key); self.tasks.addItem(item)
        left.addWidget(self.tasks, 1)
        self.state = QLabel(); self.state.setWordWrap(True); self.state.setStyleSheet("color:#6B7686")
        left.addWidget(self.state)
        mid = QVBoxLayout(); lay.addLayout(mid, 1)
        self.preview = RingPreview(); mid.addWidget(self.preview, 1)
        row = QHBoxLayout(); mid.addLayout(row)
        self.reset_button = QPushButton("Επαναφορά (το αρχικό μενού)"); row.addWidget(self.reset_button)
        self.clear_button = QPushButton("Άδειασμα"); row.addWidget(self.clear_button)
        row.addStretch(1)
        close = QPushButton("Κλείσιμο"); row.addWidget(close); close.clicked.connect(self.accept)
        right = QVBoxLayout(); lay.addLayout(right, 0)
        right.addWidget(QLabel("<b>Εντολές</b> — σύρε στον κύκλο (διπλό κλικ = πρόσθεση)"))
        self.search = QLineEdit(); self.search.setPlaceholderText("Αναζήτηση εντολής…"); right.addWidget(self.search)
        self.tree = CommandTree(); self.tree.setFixedWidth(330); right.addWidget(self.tree, 1)
        self.tasks.currentRowChanged.connect(lambda _r: self._load())
        self.preview.changed.connect(self._changed)
        self.reset_button.clicked.connect(self._reset)
        self.clear_button.clicked.connect(lambda: (self.preview.set_items([], self._title()), self._changed([])))
        self.tree.itemDoubleClicked.connect(self._double)
        self.search.textChanged.connect(self._filter)
        keys = [k for k, _n in TASKS]
        self.tasks.setCurrentRow(keys.index(task) if task in keys else 0)

    def task(self):
        item = self.tasks.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else "empty"

    def _title(self):
        return TASK_NAMES.get(self.task(), "")

    def _default_entries(self):
        """The built-in menu of the task (as the right click would build it now)."""
        from archforge.ui.marking_menu import _build_menu, _decorate
        task = self.task()
        doc = self.w.doc
        sample = None
        kinds = {"object:wall": ("wall",), "object:opening": ("door", "window", "opening"),
                 "object:furniture": ("library_object", "cabinet"), "object:stair": ("stair", "ramp")}
        if task.startswith("object:"):
            want = kinds.get(task)
            sample = next((e.id for e in doc.entities.values() if (want and e.kind in want) or
                           (not want and all(e.kind not in v for v in kinds.values()))), None)
        temp = None
        if task.startswith("object:") and sample is None:
            # Nothing of that kind drawn yet: a sample, only to read its menu (never in the stack or a file).
            from archforge.core.model import Entity
            params = {"object:wall": ("wall", {"x1": 0, "y1": 0, "x2": 4, "y2": 0, "z": 0.0, "height": 2.7, "thickness": 0.2}),
                      "object:opening": ("window", {"offset": 1.0, "width": 1.2, "height": 1.2, "sill": 0.9}),
                      "object:furniture": ("cabinet", {"x": 0, "y": 0, "z": 0.0, "width": .6, "depth": .6, "height": .86,
                                                       "rotation": 0.0, "cabinet_type": "base"}),
                      "object:stair": ("stair", {"x": 0, "y": 0, "z": 0.0, "width": 1.0, "length": 3.0}),
                      "object:other": ("structural_column", {"x": 0, "y": 0, "z": 0.0, "width": .3, "depth": .3, "height": 2.7})}[task]
            temp = Entity(params[0], dict(params[1]), name="δείγμα")
            doc.entities[temp.id] = temp
            sample = temp.id
        plan = self.w.plan_view
        old_tool, old_sculpt = str(plan.controller.tool), self.w.sculpt_action.isChecked()
        try:
            self.w.sculpt_action.blockSignals(True)
            self.w.sculpt_action.setChecked(task == "sculpt")
            plan.controller.tool = "wall" if task == "wall_draw" else ("select" if old_tool in ("wall",) else old_tool)
            if task in ("empty", "sculpt", "wall_draw") or sample:
                menu = _build_menu(self.w, "plan", sample if task.startswith("object:") else None, None)
                return _decorate(menu["entries"])
            return []
        except Exception as exc:
            from archforge.core.notices import not_computed
            not_computed("menus.defaults", "Μενού ποντικιού: οι προεπιλεγμένες εντολές δεν φορτώθηκαν (άδεια λίστα)",
                         exc=exc)
            return []
        finally:
            if temp is not None:
                doc.entities.pop(temp.id, None)
            plan.controller.tool = old_tool
            self.w.sculpt_action.setChecked(old_sculpt)
            self.w.sculpt_action.blockSignals(False)

    def _load(self):
        task = self.task()
        default = self._default_entries()
        current = saved(self.w).get(task)
        items = current if current is not None else [item_of(e) for e in default]
        self.preview.set_items(items[:MAX_ITEMS], self._title())
        self.state.setText("Δικό σου μενού" if current is not None else
                           "Αρχικό μενού (άλλαξέ το: σύρε εντολές μέσα / έξω)")
        self._fill_tree(default)

    def _fill_tree(self, default):
        from archforge.ui.menu_icons import icon
        from archforge.ui.toolbar_custom import SEP
        self.tree.clear()
        own = QTreeWidgetItem([f"Της εργασίας «{self._title()}»"]); self.tree.addTopLevelItem(own)

        def groups(es):
            for e in es:
                if e.get("children"):
                    yield e
                    yield from groups(e["children"])
        for e in groups(default):
            it = QTreeWidgetItem([e["label"] + " ▸"])
            it.setData(0, Qt.ItemDataRole.UserRole, item_of(e))
            it.setIcon(0, icon(e.get("icon") or "more"))
            own.addChild(it)
        for e in flatten(default):
            it = QTreeWidgetItem([e["label"].lstrip("✓↻ ").strip()])
            it.setData(0, Qt.ItemDataRole.UserRole, item_of(e))
            if e.get("icon"):
                it.setIcon(0, icon(e["icon"]))
            own.addChild(it)
        own.setExpanded(True)

        def walk(parent, menu, path):
            for a in menu.actions():
                if a.isSeparator() or not a.text():
                    continue
                text = a.text().replace("&&", "&")
                p = path + (text,)
                node = QTreeWidgetItem([text + (" ▸" if a.menu() is not None else "")])
                node.setData(0, Qt.ItemDataRole.UserRole, item_of_path(SEP.join(p), a))
                if not a.icon().isNull():
                    node.setIcon(0, a.icon())
                parent.addChild(node)
                if a.menu() is not None:
                    if not a.menu().actions():
                        a.menu().aboutToShow.emit()
                    walk(node, a.menu(), p)
        menus = QTreeWidgetItem(["Όλα τα μενού"]); self.tree.addTopLevelItem(menus)
        for top in self.w.menuBar().actions():
            if top.menu() is not None:
                name = top.text().replace("&&", "&")
                node = QTreeWidgetItem([name]); menus.addChild(node)
                walk(node, top.menu(), (name,))
        menus.setExpanded(True)
        self._filter(self.search.text())

    def _filter(self, text):
        text = text.strip().lower()

        def show(item):
            hit = not text or text in item.text(0).lower()
            child_hit = False
            for k in range(item.childCount()):
                child_hit = show(item.child(k)) or child_hit
            item.setHidden(not (hit or child_hit))
            if text and child_hit:
                item.setExpanded(True)
            return hit or child_hit
        for k in range(self.tree.topLevelItemCount()):
            show(self.tree.topLevelItem(k))

    def _double(self, node, _col):
        it = node.data(0, Qt.ItemDataRole.UserRole)
        if it:
            self.preview.add(it)

    def _changed(self, items):
        set_task(self.w, self.task(), items)
        self.state.setText("Δικό σου μενού — ισχύει αμέσως")

    def _reset(self):
        reset_task(self.w, self.task())
        self._load()


def open_editor(window, task=None):
    dialog = MouseMenuEditor(window, task)
    window._mouse_menu_editor = dialog
    dialog.exec()
    return dialog


def install(window):
    """«Εργαλεία ▸ Μενού ποντικιού…»."""
    from PySide6.QtGui import QAction
    tools = getattr(window, "_tools_menu", None)
    action = QAction("Μενού ποντικιού (ανά εργασία)…", window)
    action.setToolTip("Τι έχει το μενού του δεξιού κλικ σε κάθε εργασία: σύρε εντολές μέσα / έξω")
    action.triggered.connect(lambda: open_editor(window))
    if tools is not None:
        tools.addSeparator(); tools.addAction(action)
    window._mouse_menu_action = action
    return action
