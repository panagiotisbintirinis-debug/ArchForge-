"""One mouse menu for every task (marking menu, Inventor style).

Right click opens it at the cursor: the current task in the centre, the
primary action on top (north), up to seven more around it (compass order)
and a short list below for the rest.  Its content follows the task — wall
drawing, Sculpt, an object under the cursor or empty space — so only the
essentials are offered.  The wheel acts on the menu while it is open: brush
size in Sculpt, angle step while drawing walls.

``build_menu`` decides the content (shared by the 2D plan and the 3D view);
``run`` and ``wheel`` carry out the choices through the window's existing
commands.  ``MarkingMenu`` draws it in Qt (plan); the 3D view draws the same
data in its web overlay.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QToolButton, QVBoxLayout, QWidget

SCULPT_OPS = (("pull", "Τράβηγμα"), ("push", "Σπρώξιμο"), ("inflate", "Φούσκωμα"), ("recess", "Βύθιση"),
              ("smooth", "Λείανση"), ("crease", "Πτυχή"))
ANGLES = ("magnet", 90.0, 45.0, 15.0, None)
STAIR_TYPES = ((None, "Αυτόματη"), ("straight", "Ευθεία"), ("l", "Γ (L)"), ("u", "Π (U)"), ("spiral", "Σπιράλ"))
TOOLS = (("select", "Επιλογή"), ("wall", "Τοίχος"), ("door", "Πόρτα"), ("window", "Παράθυρο"),
         ("structural_column", "Κολώνα"), ("structural_beam", "Δοκός"), ("opening_rect", "Άνοιγμα"))
# The empty-space menu: what you draw first, in that order.
BUILD_TOOLS = (("wall", "Τοίχος"), ("door", "Πόρτα"), ("window", "Παράθυρο"), ("opening_rect", "Άνοιγμα"))
BRUSH_STEP = 0.05


def _e(action_id, label, placement="radial", checked=False, danger=False):
    return {"id": action_id, "label": label, "placement": placement, "checked": checked, "danger": danger}


def _same_angle(a, b):
    if a is None or b is None or a == "magnet" or b == "magnet":
        return a == b
    return abs(float(a) - float(b)) < 1e-9


def _angle_label(v):
    if v == "magnet":
        return "Μαγνήτες 90/45/15"
    return "Ελεύθερη" if v is None else f"{float(v):g}°"


def build_menu(window, view, entity_id=None):
    """``{"center", "entries", "wheel"}`` for the task in hand."""
    plan = getattr(window, "plan_view", None)
    tool = getattr(getattr(plan, "controller", None), "tool", "select")
    # Sculpt: operations around, brush size on the wheel.
    if getattr(window, "sculpt_action", None) is not None and window.sculpt_action.isChecked():
        op = window.sculpt_operation.currentText()
        entries = [_e("mm:sculpt:exit", "✓ Τέλος Sculpt")]
        entries += [_e(f"mm:sculpt:{key}", label, checked=(key == op)) for key, label in SCULPT_OPS]
        return {"center": f"Sculpt · {dict(SCULPT_OPS).get(op, op)} · βούρτσα Ø{window.sculpt_radius.value():.2f} m",
                "entries": entries, "wheel": "brush"}
    # Placing a stair: cancel on top, the types around, the wheel cycles the options.
    pbr = getattr(window, "pbr_view", None)
    placing_3d = pbr is not None and getattr(pbr, "_stair_tx", None) is not None
    if tool == "stair" or placing_3d:
        layout = getattr(window, "_stair_layout", None)
        entries = [_e("mm:stair:cancel", "✕ Ακύρωση σκάλας", danger=True)]
        entries += [_e(f"mm:stair:{key or 'auto'}", label, checked=(key == layout))
                    for key, label in STAIR_TYPES]
        entries.append(_e("mm:tool:select", "✓ Τέλος σκάλας"))
        return {"center": f"Σκάλα · {dict(STAIR_TYPES).get(layout, 'Αυτόματη')}", "entries": entries, "wheel": "stair"}
    # Drawing walls: angle step, finish, cancel the live segment.
    if view == "plan" and tool == "wall":
        current = plan.controller.wall_angle_increment
        entries = [_e("mm:tool:select", "✓ Τέλος τοίχων")]
        entries += [_e(f"mm:angle:{'free' if v is None else (v if v == 'magnet' else int(v))}", _angle_label(v),
                       checked=_same_angle(current, v))
                    for v in ANGLES]
        if plan.controller.active is not None and hasattr(plan.controller.active, "start"):
            entries.append(_e("mm:wall:cancel", "Ακύρωση τμήματος", danger=True))
        if _last_wall(window):
            entries.append(_e("mm:wall:delete_last", "Διαγραφή τελευταίου τοίχου", "panel", danger=True))
        return {"center": f"Τοίχος · γωνία {_angle_label(current)}", "entries": entries, "wheel": "angle"}
    # «Κουζίνα / Μπάνιο εδώ» of the assistant: apply, variants, shape, discard.
    if view == "plan" and str(tool).startswith("layout_") and getattr(window, "_layout_assist", None) is not None:
        from archforge.ui.layout_assist import marking_entries
        return marking_entries(window)
    # An object under the cursor: its own actions.
    if entity_id and entity_id in window.doc.entities:
        from archforge.assistant.target import describe_entity
        from archforge.ui.object_context_menu import object_context_actions
        entity = window.doc.get(entity_id)
        actions = [a for a in object_context_actions(entity.kind, view) if a is not None]
        entries = [_e(a["id"], {"properties": "Ιδιότητες", "move": "Μετακίνηση", "stretch": "Επιμήκυνση",
                                "rotate": "Περιστροφή", "materials": "Υλικά", "support": "Στήριξη…",
                                "load": "Φορτίο…", "delete": _delete_label(window, entity_id)}.get(a["id"], a["label"]),
                      danger=a["id"] == "delete") for a in actions]
        if not any(e["id"] == "delete" for e in entries):
            entries.append(_e("delete", _delete_label(window, entity_id), danger=True))   # every object can go
        from archforge.ui.object_menu import marking_entries as object_entries
        for action_id, label in reversed(object_entries(entity)):
            # Placed objects: turn 90°, mirror, duplicate; doors/windows: hinge side, swing (object_menu.py).
            entries.insert(max(0, len(entries) - 1), _e(action_id, label))
        if entity.kind == "wall" and view == "plan":
            # Walls move with what is joined to them and split where you click (wall_edit.py).
            entries.insert(len(entries) - 1, _e("mm:wall:moveby", "Μετακίνηση κατά…"))
            entries.insert(len(entries) - 1, _e("mm:wall:split", "Διαχωρισμός εδώ"))
        entries.append(_e("mm:assist:entity", "📍 Βοηθός εδώ", "panel"))
        if entity.kind in ("structural_column", "structural_beam"):
            entries.append(_e("mm:analyze", "Στατική ανάλυση", "panel"))
        if entity.kind == "slab_opening":
            entries.insert(1, _e("mm:slab:railing", "Κάγκελο γύρω από την οπή"))
        if entity.kind in ("room_floor", "room_roof", "room_ceiling") and view == "plan":
            entries += _slab_entries()
        if entity.params.get("layout_id"):
            entries.append(_e("mm:layout:refit", "Αναπροσαρμογή διάταξης", "panel"))
            entries.append(_e("mm:layout:delete_all", "Διαγραφή όλης της διάταξης", "panel", danger=True))
        return {"center": describe_entity(window.doc, entity), "entries": _fit(entries), "wheel": None}
    # A submenu asked from the empty-space menu (kitchen, stairs, structure), shown once.
    sub = getattr(window, "_marking_submenu", None)
    window._marking_submenu = None
    if sub == "kitchen":
        names = list(getattr(window, "_kitchen_item_names", ()))
        i = getattr(window, "_kitchen_wheel", 0) % max(1, len(names))
        entries = [_e("mm:kitchen:current", f"✓ {names[i]}" if names else "—")]
        entries += [_e(f"mm:kitchen:{k}", n) for k, n in enumerate(names)]
        return {"center": f"Κουζίνα · {names[i] if names else ''} — ροδέλα: επόμενο", "entries": _fit(entries), "wheel": "kitchen"}
    if sub == "stair":
        entries = [_e("mm:tool:stair", "Σκάλα"), _e("mm:tool:ramp", "Ράμπα")]
        entries += [_e(f"mm:stair:{key or 'auto'}", f"Σκάλα {label}") for key, label in STAIR_TYPES]
        return {"center": "Σκάλα / Ράμπα", "entries": _fit(entries), "wheel": None}
    if sub == "structure":
        entries = [_e("mm:tool:structural_column", "Κολώνα"), _e("mm:tool:structural_beam", "Δοκός"),
                   _e("mm:structure:design", "Βάσεις — υπολογισμός φέροντα"), _e("mm:structure:frame", "Πρόταση από τους τοίχους"),
                   _e("mm:analyze", "Στατική ανάλυση")]
        return {"center": "Δομικά: κολόνες, δοκάρια, βάσεις", "entries": _fit(entries), "wheel": None}
    # Empty space: the drawing tools in the order you build (walls, doors, windows …), kitchen and structure.
    last = getattr(window, "_last_marking_tool", None)
    entries = [_e(f"mm:tool:{last}", f"↻ {dict(TOOLS).get(last, last)}") if last else _e("mm:tool:select", "Επιλογή")]
    entries += [_e(f"mm:tool:{key}", label) for key, label in BUILD_TOOLS if key != last]
    entries += [_e("mm:menu:stair", "Σκάλα ▸"), _e("mm:menu:kitchen", "Κουζίνα ▸"), _e("mm:menu:structure", "Δομικά ▸")]
    entries.append(_e("mm:sculpt:on", "Sculpt", "panel"))
    if view == "plan":
        entries.append(_e("mm:assist:point", "📍 Βοηθός εδώ", "panel"))
        entries.append(_e("mm:layout:kitchen", "Κουζίνα εδώ…", "panel"))
        entries.append(_e("mm:layout:bath", "Μπάνιο εδώ…", "panel"))
        entries.append(_e("mm:roofroom:tiled", "Κεραμοσκεπή σε αυτόν τον χώρο", "panel"))
        entries.append(_e("mm:roofroom:terrace", "Ταράτσα σε αυτόν τον χώρο", "panel"))
        entries += _slab_entries()
    if any(e.kind in ("structural_column", "structural_beam") for e in window.doc.entities.values()):
        entries.append(_e("mm:analyze", "Στατική ανάλυση", "panel"))
    entries.append(_e("mm:undo", "Αναίρεση", "panel"))
    return {"center": "Σχεδίαση", "entries": _fit(entries), "wheel": None}


def _delete_label(window, entity_id):
    from archforge.ui.shortcuts import hint
    many = [i for i in window.doc.selection if i in window.doc.entities]
    text = f"Διαγραφή {len(many)} επιλεγμένων" if entity_id in many and len(many) > 1 else "Διαγραφή"
    return text + hint(window, "edit.delete")


def _last_wall(window):
    """The wall drawn last (the Document keeps insertion order), for «Διαγραφή τελευταίου τοίχου»."""
    return next((i for i in reversed(list(window.doc.entities)) if window.doc.entities[i].kind == "wall"), None)


def _slab_entries():
    # Slab openings (architecture/storey_slabs.py): the room under the cursor, or a drawn outline.
    return [_e("mm:slab:atrium", "Αίθριο σε αυτόν τον χώρο", "panel"),
            _e("mm:slab:inner_balcony", "Κενό πλάκας (εσωτερικό μπαλκόνι) σε αυτόν τον χώρο", "panel"),
            _e("mm:slab:draw", "Οπή πλάκας (σχεδίαση)", "panel"),
            _e("mm:drywall:room", "Ψευδοροφή γυψοσανίδας σε αυτόν τον χώρο", "panel")]


def _fit(entries):
    """At most eight around the centre; the rest go to the list below."""
    radial = [e for e in entries if e["placement"] == "radial"]
    for e in radial[8:]:
        e["placement"] = "panel"
    return entries


def run(window, view, entity_id, action_id, plan_xy=None):
    """Carry out a menu choice with the window's existing commands."""
    action_id = str(action_id)
    if not action_id.startswith("mm:"):
        window._handle_object_context_action(entity_id, action_id)
        return
    _mm, group, *rest = action_id.split(":")
    arg = rest[0] if rest else ""
    if group == "tool":
        window._last_marking_tool = arg if arg != "select" else getattr(window, "_last_marking_tool", None)
        if window.sculpt_action.isChecked():
            window.sculpt_action.setChecked(False)
        window._set_active_tool(arg)
    elif group == "sculpt":
        if arg == "exit":
            window.sculpt_action.setChecked(False)
        elif arg == "on":
            window.sculpt_action.setChecked(True)
        else:
            window.sculpt_operation.setCurrentText(arg)
    elif group == "stair":
        if arg == "cancel":
            window.pbr_view.cancel_interaction()
            window.plan_view.controller.set_tool("select")
            window._set_active_tool("select")
        else:
            window._choose_stair_layout(None if arg == "auto" else arg)
    elif group == "angle":
        window.plan_view._choose_wall_angle(None if arg == "free" else (arg if arg == "magnet" else float(arg)))
    elif group == "obj" and entity_id:
        from archforge.ui.object_menu import run_object_op
        run_object_op(window, entity_id, arg)
    elif group == "wall" and arg == "cancel":
        window.plan_view._wall_radial_command("delete")
    elif group == "wall" and arg == "delete_last":
        last = _last_wall(window)
        if last:
            window.doc.select([last])
            window._delete_selection()
    elif group == "wall" and arg in ("moveby", "split"):
        from archforge.ui import wall_edit_actions
        if arg == "moveby":
            wall_edit_actions.move_by_dialog(window, entity_id)
        else:
            wall_edit_actions.split_here(window, entity_id, plan_xy)
    elif group == "assist":
        if arg == "entity" and entity_id:
            window.doc.select([entity_id])
            window._assistant_target_from_selection()
        elif plan_xy is not None:
            window._assistant_target_at(*plan_xy)
    elif group == "menu":
        # Open the submenu where the menu was.
        window._marking_submenu = arg
        if view == "plan" and getattr(window.plan_view, "_last_marking", None):
            window.plan_view.show_marking_menu(*window.plan_view._last_marking)
        elif view == "pbr" and getattr(window.pbr_view, "_last_marking_xy", None):
            window.pbr_view._show_context_menu("", *window.pbr_view._last_marking_xy)
    elif group == "kitchen":
        names = list(getattr(window, "_kitchen_item_names", ()))
        if names:
            i = getattr(window, "_kitchen_wheel", 0) if arg == "current" else int(arg)
            window._kitchen_wheel = i % len(names)
            window._place_kitchen_item(names[i % len(names)])
    elif group == "layout":
        from archforge.ui.layout_assist import run as layout_run
        layout_run(window, arg, entity_id, plan_xy)
    elif group == "roofroom" and plan_xy is not None:
        window._set_room_roof(arg, *plan_xy)
    elif group == "slab":
        from archforge.ui import slab_tools
        if arg == "railing" and entity_id:
            slab_tools.opening_railing(window, entity_id)
        elif arg == "draw":
            slab_tools.start_opening_tool(window)
        elif plan_xy is not None:
            slab_tools.room_opening(window, *plan_xy, use=arg)
    elif group == "drywall" and plan_xy is not None:
        from archforge.ui.drywall_tools import place_in_room
        place_in_room(window, *plan_xy)
    elif group == "structure":
        (window._design_structure if arg == "design" else window._propose_frame)()
    elif group == "analyze":
        window._show_structural_analysis()
    elif group == "undo":
        window._undo()


def wheel(window, kind, steps):
    """Wheel while the menu is open; returns the new centre text."""
    if kind == "stair":
        if getattr(window.pbr_view, "_stair_tx", None) is not None:
            window.pbr_view._cycle_stair_from_web(steps)
        elif window.plan_view.controller.cycle_option(1 if steps > 0 else -1):
            window.plan_view.redraw()
        return build_menu(window, "plan")["center"]
    if kind == "kitchen":
        names = list(getattr(window, "_kitchen_item_names", ()))
        if names:
            window._kitchen_wheel = (getattr(window, "_kitchen_wheel", 0) + (1 if steps > 0 else -1)) % len(names)
            return f"Κουζίνα · {names[window._kitchen_wheel]} — ✓ για τοποθέτηση"
        return "Κουζίνα"
    if kind == "brush":
        window.sculpt_radius.setValue(round(window.sculpt_radius.value() + BRUSH_STEP * steps, 2))
    elif kind == "angle":
        current = window.plan_view.controller.wall_angle_increment
        i = next((k for k, v in enumerate(ANGLES) if _same_angle(current, v)), 0)
        window.plan_view.set_wall_angle_increment(ANGLES[(i + (1 if steps > 0 else -1)) % len(ANGLES)])
        if window.plan_view.controller.active is not None:
            window.plan_view.redraw()
    return build_menu(window, "plan")["center"]


# Compass positions, north first (Inventor order): N, NE, E, SE, S, SW, W, NW.
COMPASS = tuple((math.sin(math.radians(a)), -math.cos(math.radians(a))) for a in range(0, 360, 45))


class MarkingMenu(QWidget):
    """Qt drawing of a menu from ``build_menu`` (used by the 2D plan)."""
    chosen = Signal(str)
    wheeled = Signal(int)
    RADIUS = 96

    def __init__(self, parent, menu, center_pos):
        super().__init__(parent)
        self.setObjectName("markingMenu")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.menu = menu
        size = 2 * self.RADIUS + 300
        panel = [e for e in menu["entries"] if e["placement"] == "panel"]
        self.resize(size, size + 30 * len(panel) + 10)
        cx, cy = size // 2, size // 2
        self.buttons = {}
        self.center = QLabel(menu["center"], self)
        self.center.setStyleSheet("QLabel { background: rgba(32,41,53,0.88); color: white; border-radius: 9px;"
                                  " padding: 3px 8px; font-weight: 600; }")
        self.center.adjustSize()
        self.center.move(cx - self.center.width() // 2, cy - self.center.height() // 2)
        radial = [e for e in menu["entries"] if e["placement"] == "radial"]
        clear = self.center.width() / 2 + 12                 # keep the side buttons off the centre title
        for k, e in enumerate(radial):
            dx, dy = COMPASS[k]
            b = self._button(e)
            x = cx + dx * self.RADIUS + math.copysign(max(0.0, clear - self.RADIUS * abs(dx) + b.width() / 2), dx) * (abs(dx) > 0.5)
            b.move(int(x - b.width() / 2), int(cy + dy * self.RADIUS - b.height() / 2))
        if panel:
            frame = QFrame(self)
            frame.setStyleSheet("QFrame { background: rgba(247,248,250,0.97); border: 1px solid #7c8792; border-radius: 8px; }")
            lay = QVBoxLayout(frame)
            lay.setContentsMargins(4, 4, 4, 4)
            lay.setSpacing(2)
            for e in panel:
                lay.addWidget(self._button(e, frame, flat=True))
            frame.adjustSize()
            frame.move(cx - frame.width() // 2, int(cy + self.RADIUS + 26))
        x, y = int(center_pos.x() - cx), int(center_pos.y() - cy)
        if parent is not None:
            x = max(0, min(parent.width() - self.width(), x))
            y = max(0, min(parent.height() - self.height(), y))
        self.move(x, y)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _button(self, e, parent=None, flat=False):
        b = QToolButton(parent or self)
        b.setText(e["label"])
        base = "#ffe5e5" if e["danger"] else ("#cfe7ff" if e["checked"] else "#f7f7f7")
        b.setStyleSheet("QToolButton { background: %s; border: 1px solid #7c8792; border-radius: %dpx; padding: 4px 10px;"
                        " font-weight: %s; } QToolButton:hover { background: #d9ecff; }"
                        % (base, 6 if flat else 15, "600" if e["checked"] else "400"))
        b.adjustSize()
        b.resize(max(64, b.sizeHint().width()), max(30, b.sizeHint().height()))
        b.clicked.connect(lambda _=False, i=e["id"]: self.chosen.emit(i))
        self.buttons[e["id"]] = b
        return b

    def set_center(self, text):
        cx = self.center.x() + self.center.width() // 2
        self.center.setText(text)
        self.center.adjustSize()
        self.center.move(cx - self.center.width() // 2, self.center.y())

    def wheelEvent(self, event):
        steps = 1 if event.angleDelta().y() > 0 else -1
        self.wheeled.emit(steps)
        event.accept()

    def mousePressEvent(self, event):
        self.close()               # a click on empty menu space just closes it

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
