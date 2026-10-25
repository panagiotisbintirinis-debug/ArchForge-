"""Φωτισμός ανά χώρο: a small strip at the bottom of the screen, one button per room, a pop-up menu per room.

Owner 25/10: «μικρό μενού που θα μας δείχνει όλα τα φώτα του κτιρίου ανά χώρο … ανοίγουμε / κλείνουμε τα φώτα που
επιλέγουμε ή τα dimmάρουμε ένα ένα, βλέπουμε αντίδραση στο φωτισμό άμεσα · αν ένα φωτιστικό δεν μας κάνει, το
αλλάζουμε από τη βιβλιοθήκη στο ίδιο σημείο» — «μικρό, με δυνατότητα ρύθμισης και τοποθέτησης μέσα στην οθόνη, στην
κάτω σειρά, με αναδυόμενα μενού» — «όχι μαζική, τοπική αλλαγή».

* The strip is a dock: bottom by default, can be dragged anywhere (floating) and resized; hidden until asked.
* Each room's menu lists its luminaires under their kind (Κεντρικό, Απλίκες, Κρυφός φωτισμός …). Every row acts on
  **that one luminaire only**: «Αναμμένο», the dimmer, «Αλλαγή ▸» (another fitting / catalogue entry at the same
  point, ``mep.lighting.replace_luminaire``). Each change is one undo step through the stack, so the 3D redraws now.
* Clicking a luminaire's name selects it (Ιδιότητες show it).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QDockWidget, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QSlider,
                               QToolButton, QWidget, QWidgetAction)


class LightingStrip(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName("lightingStrip")
        outer = QHBoxLayout(self); outer.setContentsMargins(4, 2, 4, 2); outer.setSpacing(4)
        self.night = QPushButton("Νύχτα"); self.night.setObjectName("lightingNight")
        self.night.setToolTip("3D σε νύχτα: φαίνονται μόνο τα φώτα του έργου")
        self.night.clicked.connect(self._to_night)
        outer.addWidget(self.night)
        self.rooms = QWidget()
        self.row = QHBoxLayout(self.rooms); self.row.setContentsMargins(0, 0, 0, 0); self.row.setSpacing(4)
        scroll = QScrollArea(); scroll.setWidget(self.rooms); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)
        self.buttons = {}            # room title -> QToolButton
        self._open_menu = None
        self._pending = False

    # -- model -------------------------------------------------------------------------------------------------
    def _rooms(self):
        from archforge.mep.lighting import lights_by_room
        try:
            return lights_by_room(self.window.doc)
        except Exception:            # a half-drawn plan must never break the strip
            return []

    def schedule(self):
        """After every change of the stack, while the strip is shown."""
        if not self._pending and self.isVisible():
            self._pending = True
            QTimer.singleShot(0, self.refresh)

    def refresh(self):
        """Room buttons with «lit / all». While a room's menu is open the buttons stay (the menu is filled on opening)."""
        self._pending = False
        rooms = self._rooms()
        titles = [r["title"] for r in rooms]
        if titles != list(self.buttons) and self._open_menu is None:
            while self.row.count():
                item = self.row.takeAt(0)
                if item.widget() is not None:
                    item.widget().deleteLater()
            self.buttons = {}
            for title in titles:
                b = QToolButton(); b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                menu = QMenu(b)
                menu.aboutToShow.connect(lambda m=menu, t=title: self._fill(m, t))
                menu.aboutToHide.connect(lambda: setattr(self, "_open_menu", None))
                b.setMenu(menu)
                self.row.addWidget(b)
                self.buttons[title] = b
            self.row.addStretch(1)
            if not titles:
                self.row.insertWidget(0, QLabel("Δεν υπάρχουν φωτιστικά στο σχέδιο (Η/Μ ▸ Ηλεκτρολογικά ▸ Φωτισμός)"))
        from archforge.mep.lighting import is_on
        for room in (r for r in rooms if r["title"] in self.buttons):
            ids = [i for g in room["groups"] for i in g["ids"]]
            lit = sum(1 for i in ids if is_on(self.window.doc.get(i).params))
            self.buttons[room["title"]].setText(f"{'💡' if lit else '○'} {room['title']}  {lit}/{len(ids)}")

    # -- one room's pop-up ---------------------------------------------------------------------------------------
    def _fill(self, menu, title):
        self._open_menu = menu
        menu.clear()
        room = next((r for r in self._rooms() if r["title"] == title), None)
        if room is None:
            menu.addAction("— ο χώρος δεν έχει πια φωτιστικά").setEnabled(False)
            return
        for group in room["groups"]:
            menu.addSection(group["label"])
            for n, eid in enumerate(group["ids"], 1):
                act = QWidgetAction(menu)
                act.setDefaultWidget(self._row(eid, f"{group['label']} {n}" if len(group["ids"]) > 1 else group["label"]))
                menu.addAction(act)

    def _row(self, eid, label):
        p = self.window.doc.get(eid).params
        w = QWidget(); w.setObjectName(f"lightRow_{eid}")
        lay = QHBoxLayout(w); lay.setContentsMargins(8, 1, 8, 1); lay.setSpacing(6)
        on = QCheckBox(); on.setObjectName("lightRowOn"); on.setChecked(bool(int(p.get("light_on", 1))))
        on.setToolTip("Αναμμένο / σβηστό — μόνο αυτό το φωτιστικό")
        on.toggled.connect(lambda checked, i=eid: self._set(i, {"light_on": 1 if checked else 0}))
        name = QPushButton(label); name.setFlat(True); name.setObjectName("lightRowName")
        name.setToolTip("Επιλογή — οι Ιδιότητές του στο πάνελ")
        name.clicked.connect(lambda _=False, i=eid: self._select(i))
        dim = QSlider(Qt.Orientation.Horizontal); dim.setObjectName("lightRowDim"); dim.setRange(0, 100)
        dim.setFixedWidth(110); dim.setValue(int(round(float(p.get("dim_level", 1.0)) * 100)))
        shown = QLabel(f"{dim.value()} %"); shown.setFixedWidth(36)
        dim.valueChanged.connect(lambda v, l=shown: l.setText(f"{v} %"))
        dim.sliderReleased.connect(lambda s=dim, i=eid: self._set(i, {"dim_level": s.value() / 100.0}))
        dim.valueChanged.connect(lambda v, s=dim, i=eid: not s.isSliderDown() and self._set(i, {"dim_level": v / 100.0}))
        change = QToolButton(); change.setText("Αλλαγή"); change.setObjectName("lightRowChange")
        change.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        change.setToolTip("Άλλο φωτιστικό στο ίδιο σημείο (βιβλιοθήκη ▸ Φωτιστικά) — μόνο αυτό")
        options = QMenu(change)
        self._fill_replacements(options, eid)
        change.setMenu(options)
        for widget in (on, name):
            lay.addWidget(widget)
        lay.addStretch(1)
        for widget in (dim, shown, change):
            lay.addWidget(widget)
        return w

    def _fill_replacements(self, menu, eid):
        from archforge.mep.lighting import replacement_choices
        entity = self.window.doc.get(eid)
        current = (entity.params.get("point_type"), entity.params.get("catalog_id") or None)
        for label, point_type, catalog_id in replacement_choices(entity):
            a = menu.addAction(label)
            a.setCheckable(True); a.setChecked((point_type, catalog_id) == current)
            a.triggered.connect(lambda _=False, i=eid, t=point_type, c=catalog_id: self.replace(i, t, c))

    # -- commands (one luminaire each) ---------------------------------------------------------------------------
    def _set(self, eid, changes):
        from archforge.core.commands import UpdateEntity
        if eid not in self.window.doc.entities:
            return False
        p = self.window.doc.get(eid).params
        if all(k in p and p[k] == v for k, v in changes.items()):
            return False
        self.window.stack.execute(UpdateEntity(eid, changes))
        self._hint()
        QTimer.singleShot(0, self.window.refresh_inspector)
        return True

    def replace(self, eid, point_type, catalog_id=None):
        from archforge.mep.lighting import replace_luminaire
        command, new = replace_luminaire(self.window.doc, eid, point_type, catalog_id)
        self.window.stack.execute(command)
        if self._open_menu is not None:
            self._open_menu.close()
        self._select(new.id)
        self.window.statusBar().showMessage(f"Αντικατάσταση: {new.name} στο ίδιο σημείο — Αναίρεση για επιστροφή", 5000)
        return new

    def _select(self, eid):
        if eid not in self.window.doc.entities:
            return
        self.window.doc.select([eid])
        self.window.refresh_inspector()
        for view in (self.window.plan_view, self.window.pbr_view):
            if view.isVisible():
                view.redraw()

    def _to_night(self):
        setter = getattr(self.window.pbr_view, "set_lighting_mode", None)
        if setter is not None:
            setter("night")
        action = getattr(self.window, "_mockup_night_action", None)
        if action is not None:
            action.setChecked(True)

    def _hint(self):
        view = self.window.pbr_view
        if getattr(view, "_project_lights", "auto") == "auto" and getattr(view, "_architectural_lighting_mode", "day") != "night":
            self.window.statusBar().showMessage("Τα φώτα του έργου φαίνονται στο 3D τη νύχτα — πατήστε «Νύχτα» στη λωρίδα", 5000)


def listen(window):
    strip = getattr(window, "_lighting_strip", None)
    if strip is not None:
        window.stack.listeners.append(strip.schedule)


def install(window):
    """Dock at the bottom (hidden until asked), movable / floating / resizable; menu actions toggle it."""
    strip = window._lighting_strip = LightingStrip(window)
    dock = window._lighting_dock = QDockWidget("Φωτισμός ανά χώρο", window)
    dock.setObjectName("lighting_dock")
    dock.setWidget(strip)
    dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable
                     | QDockWidget.DockWidgetFeature.DockWidgetClosable)
    dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
    dock.hide()
    dock.visibilityChanged.connect(lambda shown: shown and strip.refresh())
    listen(window)
    # Owner 25/10: «σύνδεση με την επιλογή Φώτα του έργου — όταν θέλουμε ρύθμιση εμφανίζεται η σειρά, όταν
    # τελειώσουμε την κλείνουμε»: right under «Φώτα του έργου: …» in Ήλιος & ουρανός; ✕ of the strip closes it.
    action = dock.toggleViewAction()
    action.setText("Φώτα του έργου: ρύθμιση ανά χώρο…")
    action.setToolTip("Μικρή λωρίδα κάτω: τα φώτα κάθε χώρου — αναμμένο, ροοστάτης, αλλαγή φωτιστικού, ένα-ένα")
    window._lighting_strip_action = action
    sun = getattr(window, "_mockup_sun_menu", None)
    if sun is not None:
        options = [a for a in sun.actions() if a.text().startswith("Φώτα του έργου:")]
        after = sun.actions()[sun.actions().index(options[-1]) + 1] if options and options[-1] is not sun.actions()[-1] else None
        sun.insertAction(after, action) if after is not None else sun.addAction(action)
    view_menu = getattr(window, "view_menu", None)
    if view_menu is not None:
        view_menu.addAction(action)
    return dock
