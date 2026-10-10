"""Cameras with a direction («Κάμερες»): choose what you see, whenever you want.

Owner: «ΠΡΕΠΕΙ ΟΠΩΣΔΗΠΟΤΕ ΝΑ ΒΑΛΟΥΜΕ ΚΑΜΕΡΑ ΜΕ ΚΑΤΕΥΘΥΝΣΗ ΟΥΤΩΣ ΩΣΤΕ ΝΑ ΕΠΙΛΕΓΩ ΤΙ ΘΑ ΔΩ ΟΠΟΤΕ ΘΕΛΩ».

* Εργαλείο «Κάμερα» (Προβολή → Κάμερες, γραμμή εργαλείων): κλικ = το μάτι, κίνηση = προς τα πού
  κοιτάζει (ζωντανός κώνος θέασης), δεύτερο κλικ = τέλος (ή σύρσιμο και άφημα). Το 3D πάει εκεί.
* Στην κάτοψη: σύρε το σώμα για μετακίνηση, τη μύτη του κώνου για στροφή (ένα undo το καθένα),
  διπλό κλικ = δες από εκεί· Delete / δεξί κλικ όπως σε κάθε αντικείμενο· layer «Κάμερες».
* Πάνελ «Κάμερες» και «Κάμερες ▾» στη γραμμή Προβολή: κλικ = το 3D πάει στην κάμερα, διπλό κλικ =
  μετονομασία, «Από εδώ που κοιτάζω τώρα», «Επιστροφή στην κάμερα», «Εξαγωγή εικόνας…».

The camera itself is a Document entity (core/cameras.py); the 3D view stands at it through the
existing eye-level view line (pbr_viewport.set_camera_view), so the mouse can still look around.
"""
from __future__ import annotations

import base64
import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF, QTransform
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDockWidget, QDoubleSpinBox, QGraphicsTextItem,
                               QLabel, QListWidget, QListWidgetItem, QMenu, QPushButton, QToolButton,
                               QVBoxLayout, QWidget)

from archforge.core import cameras
from archforge.core.commands import AddEntity, RenameEntities, UpdateEntity

ORANGE = QColor(226, 110, 20)
INK = QColor(38, 44, 54)


# --- 3D (injected into the 3D page next to the other helpers) ----------------------------------

def camera_js():
    return r'''
// Saved cameras (ui/camera_tool.py): horizontal lens, smooth flight, the view as it is now.
function cameraVerticalFov(h) {
  const a = Math.max(0.2, camera.aspect || 1);
  return 2 * Math.atan(Math.tan(Number(h) * Math.PI / 360) / a) * 180 / Math.PI;
}
window.afFlyCamera = function(pos, to) {
  const p0 = camera.position.clone(), t0 = controls.target.clone();
  const start = performance.now(), dur = 650;
  const token = (window.__afFlyToken = (window.__afFlyToken || 0) + 1);
  function step() {
    if (token !== window.__afFlyToken || activeCameraPreset !== "line") return;
    const k = Math.min(1, (performance.now() - start) / dur);
    const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    camera.position.lerpVectors(p0, pos, e);
    controls.target.lerpVectors(t0, to, e);
    camera.lookAt(controls.target);
    if (k < 1) requestAnimationFrame(step);
  }
  step();
};
window.afCameraState = function() {
  const hfov = 2 * Math.atan(Math.tan(camera.fov * Math.PI / 360) * camera.aspect) * 180 / Math.PI;
  return {position: [camera.position.x, camera.position.y, camera.position.z],
          target: [controls.target.x, controls.target.y, controls.target.z], hfov: hfov};
};
window.addEventListener("resize", () => {
  if (activeViewLine && activeViewLine.kind === "camera" && activeViewLine.hfov) setLens(cameraVerticalFov(activeViewLine.hfov));
});
'''


# --- plan drawing --------------------------------------------------------------------------------

def _pen(color, width, style=Qt.PenStyle.SolidLine):
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setStyle(style)
    return pen


def draw_plan_primitive(view, p):
    """Paint one camera primitive (body, lens, cone, axis, name) in the plan's scene."""
    meta = dict(p.meta)
    scene = view._scene
    ghost = bool(meta.get("ghost"))
    selected = bool(meta.get("selected")) or (p.entity_id and p.entity_id in (view.doc.selection or ()))
    item = None
    if p.role == "camera-cone":
        if meta.get("axis"):
            item = scene.addLine(p.points[0][0], p.points[0][1], p.points[1][0], p.points[1][1],
                                 _pen(QColor(ORANGE.red(), ORANGE.green(), ORANGE.blue(), 200), .018, Qt.PenStyle.DashDotLine))
        else:
            fill = QColor(255, 165, 50, 95 if (selected or ghost) else 55)
            item = scene.addPolygon(QPolygonF([QPointF(x, y) for x, y in p.points]),
                                    _pen(ORANGE, .03 if selected else .02, Qt.PenStyle.DashLine if ghost else Qt.PenStyle.SolidLine),
                                    QBrush(fill))
        item.setZValue(6)
    elif p.role == "camera":
        body = QColor(255, 255, 255) if ghost else (QColor(200, 90, 10) if selected else INK)
        item = scene.addPolygon(QPolygonF([QPointF(x, y) for x, y in p.points]),
                                _pen(ORANGE if ghost or selected else INK, .02), QBrush(body))
        item.setZValue(26)
        if p.entity_id and not ghost:
            view._entity_items[item] = p.entity_id
    elif p.role == "camera-label":
        item = scene.addText(str(meta.get("text", "")))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setDefaultTextColor(QColor(170, 75, 5) if not ghost else ORANGE)
        item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        item.setPos(p.points[0][0], p.points[0][1])
        r = item.boundingRect()
        hx, vy = meta.get("align", (0.5, 0.0))
        item.setTransform(QTransform.fromTranslate(-hx * r.width(), -vy * r.height()))
        item.setZValue(27)
    if item is not None and meta.get("layer_dim"):
        item.setOpacity(.3)
    return item


def _draw_ghost(view, params, name):
    for p in [cameras.plan_body(params)] + cameras.plan_extras(params, name, ghost=True):
        draw_plan_primitive(view, p)
    # Angle of the view just beyond the cone tip.
    ax, ay = cameras.aim_point(params, cameras.CONE_LENGTH + 0.35)
    text = view._scene.addText(f"{float(params['heading']):.0f}° · γωνία {float(params['fov']):.0f}°")
    text.setDefaultTextColor(QColor(170, 75, 5))
    text.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
    text.setPos(ax, ay)
    r = text.boundingRect()
    text.setTransform(QTransform.fromTranslate(-r.width() / 2, -r.height() / 2))
    text.setZValue(60)


def _draw_aim_ring(view, handle):
    """The turning handle at the cone tip: an orange ring with a curved arrow (drag = turn)."""
    from PySide6.QtGui import QPainterPath
    r, x, y = .16, handle.x, handle.y
    ring = view._scene.addEllipse(x - r, y - r, 2 * r, 2 * r, _pen(ORANGE, .03), QBrush(QColor(255, 240, 220, 200)))
    ring.setZValue(49)
    view._handle_items[ring] = handle            # the whole ring grabs, not only the small dot
    arc = QPainterPath()
    arc.arcMoveTo(x - r * .62, y - r * .62, r * 1.24, r * 1.24, 30)
    arc.arcTo(x - r * .62, y - r * .62, r * 1.24, r * 1.24, 30, 270)
    view._scene.addPath(arc, _pen(ORANGE, .022)).setZValue(53)


def camera_icon(size=64):
    """Small camera with its cone (toolbar / list)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s = size / 64.0
    p.setPen(QPen(ORANGE, 2 * s))
    p.setBrush(QColor(255, 170, 60, 110))
    p.drawPolygon(QPolygonF([QPointF(30 * s, 32 * s), QPointF(62 * s, 12 * s), QPointF(62 * s, 52 * s)]))
    p.setPen(QPen(INK, 2 * s))
    p.setBrush(INK)
    p.drawRoundedRect(4 * s, 22 * s, 24 * s, 20 * s, 3 * s, 3 * s)
    p.drawPolygon(QPolygonF([QPointF(26 * s, 28 * s), QPointF(36 * s, 23 * s), QPointF(36 * s, 41 * s), QPointF(26 * s, 36 * s)]))
    p.end()
    return QIcon(pix)


# --- plan tool: place / move / turn --------------------------------------------------------------

class CameraTool:
    """Mouse in the plan for cameras; PlanView asks it first (PlanView._overlay)."""

    def __init__(self, window):
        self.window = window
        self.placing = None          # {'x','y','heading', 'press'}: eye set, direction follows the mouse
        self.drag = None             # {'eid','mode','start','press','params','moved'}

    # PlanView hook ---------------------------------------------------------------------------
    def handle(self, view, kind, event):
        if view.controller.tool == "camera":
            return self._place(view, kind, event)
        if self.drag is not None or kind in ("press", "dclick"):
            return self._edit(view, kind, event)
        return False

    def paint(self, view):
        if self.placing is not None:
            params = cameras.make_params(self.placing["x"], self.placing["y"], self.placing["heading"],
                                         float(view.doc.work_plane.origin[2]))
            _draw_ghost(view, params, cameras.next_camera_name(view.doc))
        elif self.drag is not None and self.drag["moved"]:
            _draw_ghost(view, self.drag["params"], view.doc.get(self.drag["eid"]).name
                        if self.drag["eid"] in view.doc.entities else "")
        else:
            for h in getattr(getattr(view, "_frame", None), "handles", ()):
                if h.handle == "camera_aim":
                    _draw_aim_ring(view, h)

    def cancel(self):
        busy = self.placing is not None or self.drag is not None
        self.placing = None
        self.drag = None
        return busy

    # placing -----------------------------------------------------------------------------------
    @staticmethod
    def _xy(view, event):
        ev = view._scene_to_plane(event.position().toPoint())
        return float(ev.a), float(ev.b)

    def _place(self, view, kind, event):
        status = view.statusChanged.emit
        if kind == "press":
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            x, y = self._xy(view, event)
            if self.placing is None:
                self.placing = {"x": x, "y": y, "heading": 90.0, "press": event.position(), "aimed": False}
                status("Κάμερα: κίνησε το ποντίκι προς τα εκεί που θέλεις να κοιτάζει · κλικ = τέλος · Esc = ακύρωση")
                view.redraw()
            else:
                self._finish(view, x, y)
            return True
        if kind == "move":
            if self.placing is None:
                return False
            x, y = self._xy(view, event)
            h = cameras.heading_to(self.placing["x"], self.placing["y"], x, y)
            if h is not None:
                self.placing["heading"] = h
                self.placing["aimed"] = True
            status(f"Κάμερα: κοιτάζει {self.placing['heading']:.0f}° · κλικ = τέλος · Esc = ακύρωση")
            view.redraw()
            return True
        if kind == "release":
            if self.placing is None:
                return False
            press = self.placing.get("press")
            if press is not None and (event.position() - press).manhattanLength() > 3 * view.CLICK_PX:
                self._finish(view, *self._xy(view, event))      # pressed, dragged, released: done as well
            return True
        if kind == "key":
            if event.key() == Qt.Key.Key_Escape:
                self.placing = None
                view.set_tool("select")
                status("Κάμερα: ακυρώθηκε")
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.placing is not None:
                self._finish(view, None, None)
                return True
            return False
        if kind in ("dclick", "context"):
            if kind == "context":
                self.placing = None
                view.set_tool("select")
                status("Κάμερα: ακυρώθηκε")
            return True
        return False

    def _finish(self, view, x, y):
        place, self.placing = self.placing, None
        heading = place["heading"]
        if x is not None:
            heading = cameras.heading_to(place["x"], place["y"], x, y) or heading
        command, entity = cameras.add_camera_command(view.doc, place["x"], place["y"], heading)
        window = self.window
        try:
            window.stack.execute(command)
        except ValueError as exc:
            view.set_tool("select")
            view.statusChanged.emit(str(exc))
            return None
        view.doc.select([entity.id])
        view.set_tool("select")
        view.selectionChangedByView.emit()
        manager = getattr(window, "_cameras", None)
        if manager is not None:
            manager.activate(entity.id)
        view.statusChanged.emit(f"{entity.name}: έτοιμη — το 3D κοιτάζει από εκεί · στην κάτοψη σύρε το σώμα για μετακίνηση, "
                                "τη μύτη του κώνου για στροφή · Ctrl+Z αναιρεί")
        return entity

    # editing an existing camera ---------------------------------------------------------------
    def _edit(self, view, kind, event):
        doc = view.doc
        if kind == "press":
            if event.button() != Qt.MouseButton.LeftButton or view.controller.tool != "select":
                return False
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                return False
            hit = view.itemAt(event.position().toPoint())
            handle = view._handle_items.get(hit)
            if handle is not None and handle.handle in ("camera_move", "camera_aim"):
                eid, mode = handle.entity_id, "aim" if handle.handle == "camera_aim" else "move"
            else:
                eid, mode = view._entity_items.get(hit), "move"
                if not eid or eid not in doc.entities or doc.get(eid).kind != cameras.KIND:
                    return False
            doc.select([eid])
            view.controller.set_target(eid, None)
            self.drag = {"eid": eid, "mode": mode, "start": self._xy(view, event), "press": event.position(),
                         "params": dict(doc.get(eid).params), "moved": False}
            view.selectionChangedByView.emit()
            view.redraw()
            return True
        if kind == "dclick":
            eid = view._entity_items.get(view.itemAt(event.position().toPoint()))
            if eid and eid in doc.entities and doc.get(eid).kind == cameras.KIND and getattr(self.window, "_cameras", None):
                self.drag = None
                self.window._cameras.activate(eid)
                return True
            return False
        drag = self.drag
        if drag is None or drag["eid"] not in doc.entities:
            self.drag = None
            return False
        if kind == "move":
            if not drag["moved"] and (event.position() - drag["press"]).manhattanLength() <= 6:
                return True
            drag["moved"] = True
            x, y = self._xy(view, event)
            base = doc.get(drag["eid"]).params
            if drag["mode"] == "move":
                drag["params"] = dict(base, x=float(base["x"]) + x - drag["start"][0], y=float(base["y"]) + y - drag["start"][1])
                view.statusChanged.emit("Κάμερα: μετακίνηση — άφησε για να γίνει · Esc = ακύρωση")
            else:
                h = cameras.heading_to(base["x"], base["y"], x, y)
                if h is not None:
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        h = round(h / 15.0) * 15.0 % 360.0
                    drag["params"] = dict(base, heading=h)
                view.statusChanged.emit(f"Κάμερα: κοιτάζει {float(drag['params']['heading']):.0f}° — άφησε για να γίνει · "
                                        "Shift = ανά 15° · Esc = ακύρωση")
            manager = getattr(self.window, "_cameras", None)
            if manager is not None:
                manager.preview(drag["eid"], drag["params"])         # the 3D follows live when it shows this camera
            view.redraw()
            return True
        if kind == "release":
            self.drag = None
            if drag["moved"]:
                keys = ("x", "y") if drag["mode"] == "move" else ("heading",)
                try:
                    self.window.stack.execute(UpdateEntity(drag["eid"], {k: drag["params"][k] for k in keys}))
                except ValueError as exc:
                    view.statusChanged.emit(str(exc))
                else:
                    view.statusChanged.emit(("Η κάμερα μετακινήθηκε" if drag["mode"] == "move" else "Η κάμερα γύρισε")
                                            + " · Ctrl+Z αναιρεί")
            view.redraw()
            view.selectionChangedByView.emit()
            return True
        if kind == "key" and event.key() == Qt.Key.Key_Escape:
            self.drag = None
            view.redraw()
            return True
        return False


def start_place(window):
    """Προβολή → Κάμερες → «Νέα κάμερα»: the tool in the plan."""
    central = getattr(window, "_central_tabs", None)
    simultaneous = getattr(window, "_simultaneous_action", None)
    if central is not None and not (simultaneous is not None and simultaneous.isChecked()):
        central.setCurrentIndex(0)
    window.view = window.plan_view
    window.plan_view.camera_tool.cancel()
    window.plan_view.set_tool("camera")
    window.statusBar().showMessage("Κάμερα: κλικ εκεί που στέκεσαι (το μάτι), κίνησε το ποντίκι προς τα εκεί που κοιτάς, "
                                   "κλικ ξανά = τέλος · Esc = ακύρωση", 12000)


# --- the list, the 3D and the commands around a camera -------------------------------------------

class CameraManager:
    """One per window: which camera the 3D shows, the «Κάμερες» list and its actions."""

    def __init__(self, window):
        self.window = window
        self.active_id = None
        self._pushed = None
        self._filling = False
        self.dock = None
        self.list = None

    # 3D -----------------------------------------------------------------------------------
    def _showing(self):
        line = getattr(self.window.pbr_view, "_view_line", None) or {}
        return self.active_id is not None and line.get("camera_id") == self.active_id

    def activate(self, eid, smooth=True):
        """The 3D view goes to camera ``eid`` (it can still look around with the mouse)."""
        w = self.window
        e = w.doc.entities.get(eid)
        if not cameras.is_camera(e):
            return None
        self.active_id = eid
        w._show_3d_view()
        payload = cameras.view_payload(e)
        w.pbr_view.set_camera_view(payload, smooth=smooth)
        self._pushed = payload
        self.refresh_list()
        w.statusBar().showMessage(f"{e.name}: σύρε στο 3D για να κοιτάξεις γύρω, W A S D για βήματα · "
                                  "«Επιστροφή στην κάμερα» για να ξαναγυρίσεις", 10000)
        return payload

    def back(self):
        """«Επιστροφή στην κάμερα»: snap back to the camera after looking around."""
        if self.active_id not in self.window.doc.entities:
            cams = cameras.cameras(self.window.doc)
            if not cams:
                self.window.statusBar().showMessage("Δεν υπάρχει κάμερα — βάλε μία με «Νέα κάμερα»", 6000)
                return None
            self.active_id = cams[0].id
        return self.activate(self.active_id)

    def preview(self, eid, params):
        """Live 3D while a camera is dragged in the plan (only if the 3D shows that camera)."""
        if eid != self.active_id or not self._showing() or eid not in self.window.doc.entities:
            return
        e = self.window.doc.get(eid)
        from archforge.core.model import Entity
        payload = cameras.view_payload(Entity(cameras.KIND, dict(params), name=e.name, id=e.id))
        self.window.pbr_view.set_camera_view(payload, smooth=False)
        self._pushed = payload

    def save_current(self):
        """«Από εδώ που κοιτάζω τώρα»: the 3D view as it is now becomes a new camera (one undo)."""
        w = self.window

        def got(state):
            if not state:
                w.statusBar().showMessage("Άνοιξε το 3D και κοίτα από εκεί που θέλεις, μετά «Από εδώ που κοιτάζω τώρα»", 8000)
                return None
            try:
                entity = cameras.camera_from_view(w.doc, state)
                w.stack.execute(AddEntity(entity))
            except ValueError as exc:
                w.statusBar().showMessage(str(exc), 6000)
                return None
            w.doc.select([entity.id])
            w.refresh_inspector()
            w.plan_view.redraw()
            self.activate(entity.id, smooth=False)
            w.statusBar().showMessage(f"{entity.name}: κρατήθηκε αυτό που βλέπεις · κλικ στη λίστα «Κάμερες» για να ξαναέρθεις", 8000)
            return entity
        w.pbr_view.request_camera_state(got)

    def export_image(self, path=None):
        """«Εξαγωγή εικόνας…»: what the 3D shows now, as a PNG."""
        w = self.window
        view = getattr(w.pbr_view, "web_view", None)
        if view is None:
            w.statusBar().showMessage("Άνοιξε πρώτα το 3D", 5000)
            return

        def got(data):
            if not data or "," not in str(data):
                w.statusBar().showMessage("Η εικόνα δεν βγήκε — δοκίμασε ξανά", 5000)
                return
            from PySide6.QtGui import QImage
            image = QImage.fromData(base64.b64decode(str(data).split(",", 1)[1]))
            target = path
            if target is None:
                from PySide6.QtWidgets import QFileDialog
                e = w.doc.entities.get(self.active_id)
                default = (e.name if e is not None else "Προβολή 3D") + ".png"
                target, _f = QFileDialog.getSaveFileName(w, "Εξαγωγή εικόνας", default, "Εικόνα PNG (*.png)")
            if target:
                image.save(target)
                w.statusBar().showMessage(f"Η εικόνα αποθηκεύτηκε: {target}", 8000)
        view.page().runJavaScript("window.__archforgeCanvasPng ? window.__archforgeCanvasPng() : ''", got)

    def delete(self, eid):
        w = self.window
        if eid in w.doc.entities:
            w.doc.select([eid])
            w._delete_selection()

    def rename(self, eid, name):
        w = self.window
        name = str(name).strip()
        if eid in w.doc.entities and name and name != w.doc.get(eid).name:
            w.stack.execute(RenameEntities({eid: name}))
            w.plan_view.redraw()

    def update(self, eid, **changes):
        """Properties panel: height, lens, direction, tilt, storey — one undo each."""
        w = self.window
        if eid not in w.doc.entities:
            return
        try:
            w.stack.execute(UpdateEntity(eid, changes))
        except ValueError as exc:
            w.statusBar().showMessage(str(exc), 6000)
            return
        w.plan_view.redraw()

    def on_document_changed(self):
        """Any change (also undo): the list follows; an active camera that changed moves the 3D live."""
        doc = self.window.doc
        if self.active_id is not None and self.active_id not in doc.entities:
            self.active_id = None
        elif self._showing():
            payload = cameras.view_payload(doc.get(self.active_id))
            if payload != self._pushed:
                self.window.pbr_view.set_camera_view(payload, smooth=False)
                self._pushed = payload
        self.refresh_list()

    # the list --------------------------------------------------------------------------------
    def build_dock(self):
        w = self.window
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(6, 6, 6, 6)
        self.list = QListWidget()
        self.list.setIconSize(self.list.iconSize() * 1.4)
        self.list.setStyleSheet("QListWidget::item { padding: 4px; } "
                                "QListWidget::item:selected { background: #ffe2be; color: #3a2a10; }")
        self.list.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.list.itemClicked.connect(lambda item: self.activate(item.data(Qt.ItemDataRole.UserRole)))
        self.list.itemChanged.connect(self._item_renamed)
        lay.addWidget(self.list, 1)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color:#7a3f06;")
        lay.addWidget(self.info)
        self.empty = QLabel("Δεν υπάρχουν κάμερες ακόμη.\nΠάτα «Νέα κάμερα» και κάνε κλικ στην κάτοψη.")
        self.empty.setStyleSheet("color:#5B6778;")
        lay.addWidget(self.empty)
        for text, tip, run in (
                ("Νέα κάμερα στην κάτοψη", "Κλικ = το μάτι, κίνηση = προς τα πού κοιτάζει, κλικ = τέλος", lambda: start_place(w)),
                ("Από εδώ που κοιτάζω τώρα", "Ό,τι δείχνει τώρα το 3D γίνεται νέα κάμερα", self.save_current),
                ("Επιστροφή στην κάμερα", "Μετά από βόλτα με το ποντίκι: πίσω στην κάμερα", self.back),
                ("Εξαγωγή εικόνας…", "Ό,τι δείχνει τώρα το 3D, σε εικόνα PNG", lambda: self.export_image()),
                ("Διαγραφή κάμερας", "Η επιλεγμένη κάμερα της λίστας (Ctrl+Z την επαναφέρει)", self._delete_current)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, r=run: r())
            lay.addWidget(b)
        hint = QLabel("Κλικ = το 3D πάει στην κάμερα · διπλό κλικ = μετονομασία\n"
                      "Στην κάτοψη: σύρε το σώμα = μετακίνηση, τη μύτη του κώνου = στροφή")
        hint.setStyleSheet("color:#5B6778;")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        dock = QDockWidget("Κάμερες", w)
        dock.setObjectName("cameras_dock")
        dock.setWidget(panel)
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock = dock
        self.refresh_list()
        return dock

    def _delete_current(self):
        item = self.list.currentItem() if self.list is not None else None
        eid = item.data(Qt.ItemDataRole.UserRole) if item is not None else self.active_id
        if eid:
            self.delete(eid)

    def _item_renamed(self, item):
        if self._filling:
            return
        self.rename(item.data(Qt.ItemDataRole.UserRole), item.text())

    def describe(self, e):
        from archforge.ui.workspace_layout import level_label
        p = e.params
        name = cameras.storey_name(self.window.doc, p.get("level_z", 0.0))
        storey = level_label(name) if name else f"{float(p.get('level_z', 0.0)):+.2f} m"
        return (f"{storey} · ύψος ματιού {float(p['height']):.2f} m · γωνία {float(p['fov']):.0f}° · "
                f"κατεύθυνση {float(p['heading']):.0f}°").replace(".", ",")

    def refresh_list(self):
        if self.list is None:
            return
        self._filling = True
        try:
            self.list.clear()
            icon = camera_icon()
            for e in cameras.cameras(self.window.doc):
                item = QListWidgetItem(icon, e.name or cameras.NAME_PREFIX)
                item.setData(Qt.ItemDataRole.UserRole, e.id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                item.setToolTip(self.describe(e))
                if e.id == self.active_id:
                    f = QFont(item.font())
                    f.setBold(True)
                    item.setFont(f)
                    item.setBackground(QColor(255, 226, 190))
                self.list.addItem(item)
                if e.id == self.active_id:
                    self.list.setCurrentItem(item)
            self.empty.setVisible(self.list.count() == 0)
            active = self.window.doc.entities.get(self.active_id)
            self.info.setText(f"Στο 3D: {active.name} — {self.describe(active)}" if active is not None else "")
            self.info.setVisible(active is not None)
        finally:
            self._filling = False

    def fill_menu(self, menu):
        """«Κάμερες ▾» on the view bar and Προβολή → Κάμερες: every camera, then the actions."""
        menu.clear()
        w = self.window
        for e in cameras.cameras(w.doc):
            a = menu.addAction(camera_icon(), e.name)
            a.setCheckable(True)
            a.setChecked(e.id == self.active_id)
            a.setToolTip(self.describe(e))
            a.triggered.connect(lambda _=False, i=e.id: self.activate(i))
        if menu.actions():
            menu.addSeparator()
        for text, run in (("Νέα κάμερα στην κάτοψη", lambda: start_place(w)),
                          ("Από εδώ που κοιτάζω τώρα", self.save_current),
                          ("Επιστροφή στην κάμερα", self.back),
                          ("Εξαγωγή εικόνας…", lambda: self.export_image())):
            menu.addAction(text).triggered.connect(lambda _=False, r=run: r())
        if self.dock is not None:
            menu.addSeparator()
            menu.addAction(self.dock.toggleViewAction())


def add_rows(window, eid):
    """Properties of a camera: height, lens, direction, tilt, storey, and «Δες στο 3D»."""
    manager = window._cameras
    p = window.doc.get(eid).params

    def spin(value, lo, hi, step, suffix, decimals=2):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(decimals)
        s.setSingleStep(step)
        s.setSuffix(suffix)
        s.setValue(float(value))
        return s
    rows = (("Ύψος ματιού", "height", spin(p.get("height", cameras.DEFAULT_HEIGHT), .3, 20.0, .05, " m")),
            ("Γωνία θέασης", "fov", spin(p.get("fov", cameras.DEFAULT_FOV), cameras.FOV_RANGE[0], cameras.FOV_RANGE[1], 5, "°", 0)),
            ("Κατεύθυνση", "heading", spin(float(p.get("heading", 0.0)) % 360.0, 0.0, 359.0, 5, "°", 0)),
            ("Κλίση (πάνω/κάτω)", "pitch", spin(p.get("pitch", 0.0), cameras.PITCH_RANGE[0], cameras.PITCH_RANGE[1], 5, "°", 0)))
    for label, key, widget in rows:
        widget.editingFinished.connect(
            lambda k=key, s=widget: abs(float(window.doc.get(eid).params.get(k, 0.0)) - s.value()) > 1e-9
            and manager.update(eid, **{k: s.value()}) if eid in window.doc.entities else None)
        window.form.addRow(label, widget)
    from archforge.ui.workspace_layout import level_label
    storey = QComboBox()
    for name, z in sorted(window.doc.levels.items(), key=lambda t: float(t[1])):
        storey.addItem(level_label(name), float(z))
    storey.setCurrentIndex(max(0, storey.findData(float(p.get("level_z", 0.0)))))
    storey.currentIndexChanged.connect(lambda _i: manager.update(eid, level_z=float(storey.currentData())))
    window.form.addRow("Όροφος", storey)
    note = QLabel("Βοήθημα προβολής: δεν μετράει στις ποσότητες\nκαι δεν φαίνεται στο 3D.")
    note.setStyleSheet("color:#5B6778;")
    window.form.addRow(note)
    for text, run in (("Δες από αυτή την κάμερα (3D)", lambda: manager.activate(eid)),
                      ("Εξαγωγή εικόνας…", lambda: (manager.activate(eid, smooth=False), manager.export_image()))):
        b = QPushButton(text)
        b.clicked.connect(lambda _=False, r=run: r())
        window.form.addRow(b)


def install(window):
    """Tool, list dock, «Κάμερες ▾» on the view bar, Προβολή → Κάμερες, ribbon button."""
    manager = window._cameras = CameraManager(window)
    window.plan_view.camera_tool = CameraTool(window)
    dock = manager.build_dock()
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    layers = getattr(window, "_layers_dock", None)
    if layers is not None:
        window.tabifyDockWidget(layers, dock)
    window.dock.raise_()
    # Menu Προβολή → Κάμερες
    menu = QMenu("Κάμερες", window)
    menu.setIcon(camera_icon())
    menu.aboutToShow.connect(lambda: manager.fill_menu(menu))
    manager.fill_menu(menu)
    view_menu = getattr(window, "view_menu", None)
    if view_menu is not None:
        view_menu.addMenu(menu)
    window._cameras_menu = menu
    # «Κάμερες ▾» on the «Προβολή» bar
    from PySide6.QtWidgets import QToolBar
    bar = window.findChild(QToolBar, "camera")
    if bar is not None:
        popup = QMenu("Κάμερες", window)
        popup.aboutToShow.connect(lambda: manager.fill_menu(popup))
        manager.fill_menu(popup)
        button = QToolButton(bar)
        button.setText("Κάμερες")
        button.setIcon(camera_icon())
        button.setToolTip("Οι κάμερές σου: κλικ = δες από εκεί · νέα κάμερα · από εδώ που κοιτάζω τώρα · επιστροφή")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setMenu(popup)
        bar.addWidget(button)
        window._cameras_button = button
        window._cameras_popup = popup
    # «Κάμερα» on the drawing tools
    ribbon = window.findChild(QToolBar, "ribbon")
    if ribbon is not None:
        from PySide6.QtGui import QAction
        action = QAction(camera_icon(), "Κάμερα", window)
        action.setToolTip("Κάμερα με κατεύθυνση: κλικ = το μάτι, κίνηση = προς τα πού κοιτάζει, κλικ = τέλος")
        action.triggered.connect(lambda: start_place(window))
        ribbon.addAction(action)
        window._camera_tool_action = action
    return manager
