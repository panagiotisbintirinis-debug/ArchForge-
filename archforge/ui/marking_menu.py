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

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import QToolButton, QWidget

SCULPT_OPS = (("pull", "Τράβηγμα"), ("push", "Σπρώξιμο"), ("inflate", "Φούσκωμα"), ("recess", "Βύθιση"),
              ("smooth", "Λείανση"), ("crease", "Πτυχή"))
ANGLES = ("magnet", 90.0, 45.0, 15.0, None)
STAIR_TYPES = ((None, "Αυτόματη"), ("straight", "Ευθεία"), ("l", "Γ (L)"), ("u", "Π (U)"), ("spiral", "Σπιράλ"))
TOOLS = (("select", "Επιλογή"), ("wall", "Τοίχος"), ("door", "Πόρτα"), ("window", "Παράθυρο"),
         ("structural_column", "Κολώνα"), ("structural_beam", "Δοκός"), ("opening_rect", "Άνοιγμα"))
# The empty-space menu: what you draw first, in that order.
BUILD_TOOLS = (("wall", "Τοίχος"), ("door", "Πόρτα"), ("window", "Παράθυρο"), ("opening_rect", "Άνοιγμα"))
BRUSH_STEP = 0.05


def _e(action_id, label, placement="radial", checked=False, danger=False, children=None):
    e = {"id": action_id, "label": label, "placement": placement, "checked": checked, "danger": danger}
    if children:
        e["children"] = list(children)        # a submenu: opens in place, in the mouse menu itself
    return e


# Icon per command (drawn in code: ui/menu_icons.py). Choices that are a state (✓, angles, types) stay text.
ICONS = {
    "mm:tool:select": "select", "mm:tool:wall": "wall", "mm:tool:door": "door", "mm:tool:window": "window",
    "mm:tool:opening_rect": "opening", "mm:tool:stair": "stair", "mm:tool:ramp": "ramp",
    "mm:tool:structural_column": "column", "mm:tool:structural_beam": "beam",
    "mm:menu:stair": "stair", "mm:menu:kitchen": "cabinet", "mm:menu:structure": "column",
    "mm:menu:openings": "door", "mm:menu:way": "way_in_left", "mm:menu:build": "more", "mm:menu:wall_more": "more", "mm:tool:opening_arch": "opening",
    "mm:group:room": "room", "mm:menu:roomuse": "room", "mm:group:slab": "slab", "mm:more": "more", "mm:kgroup:0": "cabinet",
    "mm:kgroup:1": "cabinet", "mm:kgroup:2": "cabinet", "mm:kgroup:3": "cabinet", "mm:kgroup:4": "appliance",
    "properties": "properties", "move": "move", "rotate": "rotate", "stretch": "stretch", "materials": "materials",
    "delete": "delete", "mm:obj:duplicate": "duplicate", "mm:obj:mirror": "mirror", "mm:obj:rot90": "rotate",
    "mm:obj:hinge": "mirror", "mm:obj:swing": "swing",
    "mm:assist:point": "assist", "mm:assist:entity": "assist", "mm:layout:kitchen": "cabinet", "mm:layout:bath": "bath",
    "mm:krun:start": "cabinet", "mm:slab:balcony": "balcony", "mm:slab:draw": "slab", "mm:slab:atrium": "slab",
    "mm:slab:inner_balcony": "slab", "mm:roofroom:tiled": "roof", "mm:roofroom:terrace": "terrace",
    "mm:drywall:room": "ceiling", "mm:analyze": "statics", "mm:member_statics": "statics",
    "mm:structure:design": "footing", "mm:structure:frame": "column", "mm:wall:moveby": "move",
    "mm:wall:split": "split", "mm:wall:corner": "corner", "mm:stairdlg:open": "stair", "mm:fit:ceiling": "fit", "mm:camera:view": "camera",
}


def all_ids(entries):
    """Every command id in ``entries`` and their submenus (what the mouse menu can reach)."""
    out = []
    for e in entries:
        out.append(e["id"])
        if e.get("children"):
            out += all_ids(e["children"])
    return out


def _decorate(entries):
    """Icon names on the entries (and their submenus); a label with ✓/✕/↻ keeps only its text."""
    for e in entries:
        if "icon" not in e and e["id"] in ICONS and not e["label"][:1] in ("✓", "✕"):
            e["icon"] = ICONS[e["id"]]
        if e["id"].startswith("mm:tool:") and e["label"].startswith("↻"):
            e["icon"] = ICONS.get(e["id"])
        if e.get("children"):
            _decorate(e["children"])
    return entries


def _same_angle(a, b):
    if a is None or b is None or a == "magnet" or b == "magnet":
        return a == b
    return abs(float(a) - float(b)) < 1e-9


def _angle_label(v):
    if v == "magnet":
        return "Μαγνήτες 90/45/15"
    return "Ελεύθερη" if v is None else f"{float(v):g}°"


def build_menu(window, view, entity_id=None, xy=None):
    """``{"center", "entries", "wheel"}`` for the task in hand (``xy``: plan point of the right click).

    An entry with ``children`` is a submenu that opens in place (2D and 3D alike); icons by ``ICONS``."""
    from archforge.ui.mouse_menus import custom_entries, task_of
    task = task_of(window, view, entity_id)              # before _build_menu: it consumes a submenu request
    menu = _build_menu(window, view, entity_id, xy)
    _decorate(menu["entries"])
    if task is not None:
        # The human's own menu for this task (Εργαλεία ▸ Μενού ποντικιού…), built from the live entries.
        mine = custom_entries(window, task, menu["entries"])
        if mine is not None:
            menu["entries"], menu["custom"], menu["task"] = mine, True, task
    return menu


def _kitchen_entries(window):
    names = list(getattr(window, "_kitchen_item_names", ()))
    i = getattr(window, "_kitchen_wheel", 0) % max(1, len(names))
    entries = [_e("mm:kitchen:current", f"✓ {names[i]}" if names else "—")]
    entries += [_e(f"mm:kitchen:{k}", n) for k, n in enumerate(names)]
    return entries, (names[i] if names else "")


# The kitchen catalogue in the mouse menu as short groups (a submenu in the submenu), by name.
KITCHEN_GROUPS = (("Βάσης", ("Κάτω ντουλάπι", "Συρτάρια", "Ντουλάπι νεροχύτη", "Νησίδα", "Νεροχύτη με κάδους",
                             "Με εσωτερικά συρτάρια", "Συρόμενο καλάθι")),
                  ("Κρεμαστά", ("Κρεμαστό",)),
                  ("Ψηλά && ντουλάπες", ("Ψηλό", "Ψηλή", "Ντουλάπα")),
                  ("Γωνιακά", ("Γωνιακό",)),
                  ("Συσκευές", ("Κουζίνα με φούρνο", "Εστία", "Ψυγείο", "Πλυντήριο", "Απορροφητήρας", "Σκαμπό")))


def _kitchen_groups(window):
    names = list(getattr(window, "_kitchen_item_names", ()))
    used, out = set(), []
    for title, starts in KITCHEN_GROUPS:
        items = [_e(f"mm:kitchen:{k}", n) for k, n in enumerate(names)
                 if k not in used and any(n.startswith(x) for x in starts)]
        used.update(int(e["id"].rsplit(":", 1)[1]) for e in items)
        if items:
            out.append(_e(f"mm:kgroup:{len(out)}", title.replace("&&", "&"), children=items))
    rest = [_e(f"mm:kitchen:{k}", n) for k, n in enumerate(names) if k not in used]
    if rest:
        out.append(_e("mm:kgroup:rest", "Άλλα", children=rest))
    return out


def _stair_entries():
    entries = [_e("mm:tool:stair", "Σκάλα"), _e("mm:tool:ramp", "Ράμπα")]
    entries += [_e(f"mm:stair:{key or 'auto'}", f"Σκάλα {label}") for key, label in STAIR_TYPES]
    return entries


def _structure_entries():
    return [_e("mm:tool:structural_column", "Κολώνα"), _e("mm:tool:structural_beam", "Δοκός"),
            _e("mm:structure:design", "Βάσεις — υπολογισμός φέροντα"), _e("mm:structure:frame", "Πρόταση από τους τοίχους"),
            _e("mm:analyze", "Στατική ανάλυση")]


def _build_menu(window, view, entity_id=None, xy=None):
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
        # Owner 15/10: the angle is seen while drawing (magnets 90/45/15 work by themselves, Shift = free), so no
        # angle choices here; the last wall goes with Delete. Only what ends or undoes the drawing.
        entries = [_e("mm:tool:select", "✓ Τέλος τοίχων")]
        if plan.controller.active is not None and hasattr(plan.controller.active, "start"):
            entries.append(_e("mm:wall:cancel", "Ακύρωση τμήματος", danger=True))
        return {"center": "Τοίχος", "entries": entries, "wheel": None}
    # «Κουζίνα / Μπάνιο εδώ» of the assistant: apply, variants, shape, discard.
    if view == "plan" and tool == "layout_cabinet_run" and getattr(window, "_cabinet_run", None) is not None \
            and (window._cabinet_run.proposal is not None or not entity_id):
        # On a cabinet already placed (no ghost) its own menu opens instead: widths, delete the run.
        from archforge.ui.cabinet_run_tool import marking_entries as run_entries
        return run_entries(window)
    if view == "plan" and str(tool).startswith("layout_") and tool != "layout_cabinet_run" \
            and getattr(window, "_layout_assist", None) is not None:
        from archforge.ui.layout_assist import marking_entries
        return marking_entries(window)
    # An object under the cursor: its own actions.
    if entity_id and entity_id in window.doc.entities:
        from archforge.assistant.target import describe_entity
        from archforge.ui.object_context_menu import object_context_actions
        entity = window.doc.get(entity_id)
        # No «Μετακίνηση» / «Επιμήκυνση» buttons (owner 15/10): drag the object = move, drag a side / handle =
        # stretch, with its distances shown live (wall_dims_tool). They stay in Επεξεργασία and «Κοινά».
        actions = [a for a in object_context_actions(entity.kind, view) if a is not None
                   and a["id"] not in ("move", "stretch")]
        entries = [_e(a["id"], {"properties": "Ιδιότητες", "move": "Μετακίνηση", "stretch": "Επιμήκυνση",
                                "rotate": "Περιστροφή", "materials": "Υλικά", "support": "Στήριξη…",
                                "load": "Φορτίο…", "delete": _delete_label(window, entity_id)}.get(a["id"], a["label"]),
                      danger=a["id"] == "delete") for a in actions]
        if not any(e["id"] == "delete" for e in entries):
            entries.append(_e("delete", _delete_label(window, entity_id), danger=True))   # every object can go
        from archforge.ui.object_menu import marking_entries as object_entries
        for action_id, label in reversed(object_entries(entity)):
            # Placed objects: turn 90°, mirror, duplicate; doors/windows: «Φορά ▸» = 4 positions (object_menu.py).
            if action_id == "mm:menu:way":
                from archforge.ui.object_menu import way_entries
                kids = []
                for wid, wlabel, on, wicon in way_entries(entity):
                    k = _e(wid, wlabel, checked=on); k["icon"] = wicon; kids.append(k)
                entries.insert(max(0, len(entries) - 1), _e(action_id, label, children=kids))
                continue
            entries.insert(max(0, len(entries) - 1), _e(action_id, label))
        if entity.kind == "wall" and view == "plan":
            # Walls move with what is joined to them and split where you click (wall_edit.py).
            # Rarely used: behind a small «⋯» (owner 15/10: rare things in a small icon with submenus).
            more = _e("mm:menu:wall_more", "Επεξεργασία τοίχου", children=[
                _e("mm:wall:moveby", "Μετακίνηση κατά…"), _e("mm:wall:split", "Διαχωρισμός εδώ"),
                _e("mm:wall:corner", "Γωνία με άλλο τοίχο")])
            more["small"] = True
            entries.insert(len(entries) - 1, more)
        assist = _e("mm:assist:entity", "Βοηθός εδώ", "panel")
        assist["small"] = True
        entries.append(assist)
        if entity.kind in ("structural_column", "structural_beam"):
            # Radial: one click from the member to its own statics (actions, bars, re-check, undo).
            entries.insert(1, _e("mm:member_statics", "Στατικά μέλους…"))
            entries.append(_e("mm:analyze", "Στατική ανάλυση", "panel"))
        if entity.kind == "pool":
            # Owner 30/10: the pool's own drawing tools on its menu, not only behind Ιδιότητες.
            entries.insert(1, _e("mm:pool:shape", "Σχήμα πισίνας (σχεδίαση)"))
            entries.append(_e("mm:pool:section", "Τομή πισίνας", "panel"))
            if entity.params.get("outline"):
                entries.append(_e("mm:pool:rect", "Ξανά ορθογώνια", "panel"))
        if entity.kind == "slab_opening":
            entries.insert(1, _e("mm:slab:railing", "Κάγκελο γύρω από την οπή"))
        if entity.kind in ("cabinet", "library_object"):
            # Any placed object: its top up to the ceiling over it (stair, roof, slab), sloped where that is.
            entries.append(_e("mm:fit:ceiling", "Ύψος ως την οροφή (ακολουθεί κλίση)", "panel"))
            if entity.params.get("top_heights"):
                entries.append(_e("mm:fit:flat", "Ίσιο καπάκι", "panel"))
        if entity.kind == "stair":
            # One window for the stair: sizes, structure, railing, materials (ui/stair_dialog.py).
            entries.insert(0, _e("mm:stairdlg:open", "Σκάλα…"))
            from archforge.architecture.stair_options import has_space_under
            if has_space_under(entity.params):
                entries.append(_e("mm:stairdlg:cabinets", "Ντουλάπια κάτω από τη σκάλα", "panel"))
        if entity.kind == "camera":
            entries.insert(0, _e("mm:camera:view", "Δες από αυτή την κάμερα"))
        if entity.kind in ("room_floor", "room_roof", "room_ceiling") and view == "plan":
            entries += _slab_entries()
        if entity.kind == "cabinet" and entity.params.get("run_id"):
            # A cabinet of a «Γραμμή ντουλαπιών»: standard widths (the run re-flows), delete the whole run.
            from archforge.ui.cabinet_run_tool import entity_entries
            entries += entity_entries(window, entity)
        if entity.params.get("layout_id"):
            entries.append(_e("mm:layout:refit", "Αναπροσαρμογή διάταξης", "panel"))
            entries.append(_e("mm:layout:delete_all", "Διαγραφή όλης της διάταξης", "panel", danger=True))
        return {"center": describe_entity(window.doc, entity), "entries": _fit(entries), "wheel": None}
    # A submenu asked from the empty-space menu (kitchen, stairs, structure), shown once.
    sub = getattr(window, "_marking_submenu", None)
    window._marking_submenu = None
    if sub == "kitchen":
        entries, name = _kitchen_entries(window)
        return {"center": f"Κουζίνα · {name} — ροδέλα: επόμενο", "entries": entries, "wheel": "kitchen"}   # a grid
    if sub == "stair":
        return {"center": "Σκάλα / Ράμπα", "entries": _fit(_stair_entries()), "wheel": None}
    if sub == "structure":
        return {"center": "Δομικά: κολόνες, δοκάρια, βάσεις", "entries": _fit(_structure_entries()), "wheel": None}
    # Empty space (owner 15/10): only what is used all the time — walls and openings. Stair, kitchen,
    # structure, slabs are used once per house: they wait behind one small «⋯» icon, in submenus.
    last = getattr(window, "_last_marking_tool", None)
    entries = [_e(f"mm:tool:{last}", f"↻ {dict(TOOLS).get(last, last)}") if last else _e("mm:tool:select", "Επιλογή")]
    if last != "wall":
        entries.append(_e("mm:tool:wall", "Τοίχος"))
    openings = [_e("mm:tool:door", "Πόρτα"), _e("mm:tool:window", "Παράθυρο"),
                _e("mm:tool:opening_rect", "Άνοιγμα"), _e("mm:tool:opening_arch", "Τοξωτό άνοιγμα")]
    entries.append(_e("mm:menu:openings", "Κουφώματα", children=openings))
    kitchen = _kitchen_groups(window)
    if view == "plan":
        # Owner 15/10: no fixed Γ / Π shapes — the kitchen is drawn freely and the cabinets follow the line.
        kitchen.insert(0, _e("mm:krun:start", "Σχεδίασε κουζίνα (ελεύθερα)…"))
    rare = [_e("mm:curvedwall:start", "Καμπύλος τοίχος"),
            _e("mm:menu:stair", "Σκάλα", children=_stair_entries()),
            _e("mm:menu:kitchen", "Κουζίνα", children=kitchen),
            _e("mm:menu:structure", "Δομικά", children=_structure_entries())]
    if view == "plan":
        rare.append(_e("mm:group:slab", "Πλάκα", children=[
            _e("mm:slab:balcony", "Μπαλκόνι (σχεδίαση)"), _e("mm:slab:draw", "Οπή πλάκας (σχεδίαση)")]))
        # «… σε αυτόν τον χώρο» only inside a closed room: outside one they do nothing (walk-through 14/10).
        if xy is None or _in_room(window.doc, *xy):
            rare.append(_e("mm:group:room", "Σε αυτόν τον χώρο", children=[
                _e("mm:menu:roomuse", "Χρήση χώρου", children=[_e(f"mm:roomuse:{i}", u) for i, u in enumerate(ROOM_USES)]
                   + [_e("mm:roomuse:name", "Όνομα…")]),
                _e("mm:layout:bath", "Μπάνιο εδώ…"),
                _e("mm:survey:room", "Αποτύπωση από μετρήσεις…"),
                _e("mm:roofroom:tiled", "Κεραμοσκεπή"), _e("mm:roofroom:terrace", "Ταράτσα"),
                _e("mm:slab:atrium", "Αίθριο"), _e("mm:slab:inner_balcony", "Κενό πλάκας (εσωτ. μπαλκόνι)"),
                _e("mm:drywall:room", "Ψευδοροφή γυψοσανίδας")]))
        assist = _e("mm:assist:point", "Βοηθός εδώ")
        assist["small"] = True                 # owner 15/10: kept only as an icon, «βλέπουμε»
        rare.append(assist)
    build = _e("mm:menu:build", "Κατασκευή", children=rare)
    build["small"] = True                      # a small icon only (tooltip «Κατασκευή»)
    entries.append(build)
    return {"center": "Σχεδίαση", "entries": _fit(entries), "wheel": None}


def _delete_label(window, entity_id):
    from archforge.ui.shortcuts import hint
    many = [i for i in window.doc.selection if i in window.doc.entities]
    text = f"Διαγραφή {len(many)} επιλεγμένων" if entity_id in many and len(many) > 1 else "Διαγραφή"
    return text + hint(window, "edit.delete")


def _last_wall(window):
    """The wall drawn last (the Document keeps insertion order), for «Διαγραφή τελευταίου τοίχου»."""
    return next((i for i in reversed(list(window.doc.entities)) if window.doc.entities[i].kind == "wall"), None)


def _in_room(doc, x, y):
    from archforge.geometry.regions import point_in_polygon
    return any(point_in_polygon(float(x), float(y), face.polygon) for face in doc.active_room_faces())


def _slab_entries():
    # Slab openings (architecture/storey_slabs.py): the room under the cursor, or a drawn outline.
    return [_e("mm:slab:balcony", "Μπαλκόνι (σχεδίαση)", "panel"),
            _e("mm:slab:atrium", "Αίθριο σε αυτόν τον χώρο", "panel"),
            _e("mm:slab:inner_balcony", "Κενό πλάκας (εσωτερικό μπαλκόνι) σε αυτόν τον χώρο", "panel"),
            _e("mm:slab:draw", "Οπή πλάκας (σχεδίαση)", "panel"),
            _e("mm:drywall:room", "Ψευδοροφή γυψοσανίδας σε αυτόν τον χώρο", "panel")]


INLINE_PANEL = 3      # up to this many secondary choices show as buttons under the ring


def _fit(entries):
    """At most eight around the centre; up to three more below; anything beyond goes into «Περισσότερα ▸»,
    a submenu that opens in place (no list popping over the drawing)."""
    radial = [e for e in entries if e["placement"] == "radial"]
    late = [e for e in radial[8:] if e["id"] == "delete"]
    if late:
        # «Διαγραφή» always stays on the ring (every object can go, one gesture away).
        entries = [e for e in entries if e is not late[0]]
        entries.insert(entries.index(radial[7]), late[0])
        radial = [e for e in entries if e["placement"] == "radial"]
    for e in radial[8:]:
        e["placement"] = "panel"
    panel = [e for e in entries if e["placement"] == "panel"]
    if len(panel) > INLINE_PANEL:
        keep = [e for e in entries if e["placement"] != "panel"]
        for e in panel:
            e["placement"] = "radial"
        keep.append(_e("mm:more", "Περισσότερα", "panel", children=panel))
        return keep
    return entries


# Owner 17/10: rooms by use, so finishes and materials can be told apart room by room. A kitchen is its own
# room only when closed; open to the living room it is «Σαλόνι – κουζίνα».
ROOM_USES = ("Σαλόνι", "Κουζίνα", "Σαλόνι – κουζίνα", "Υπνοδωμάτιο", "Μπάνιο", "WC", "Διάδρομος", "Γραφείο",
             "Αποθήκη", "Πλυσταριό", "Λεβητοστάσιο", "Γκαράζ", "Πισίνα", "Αυλή")


def set_room_use(window, x, y, name):
    """Name / use of the room under (x, y) — one undo step."""
    from archforge.core.commands import SetRoomMetadata
    from archforge.geometry.regions import point_in_polygon
    face = next((f for f in window.doc.active_room_faces() if point_in_polygon(float(x), float(y), f.polygon)), None)
    if face is None or not str(name).strip():
        return False
    window.stack.execute(SetRoomMetadata(face.signature, {"name": str(name).strip(), "use": str(name).strip()}))
    window._redraw_views(all_views=True)
    window.statusBar().showMessage(f"Χώρος: {str(name).strip()} — Ctrl+Z για αναίρεση", 5000)
    return True


def run(window, view, entity_id, action_id, plan_xy=None):
    """Carry out a menu choice with the window's existing commands."""
    action_id = str(action_id)
    if action_id.startswith("menu:"):
        from archforge.ui.mouse_menus import run_menu_path
        run_menu_path(window, action_id[5:])               # a menu-bar command put in the mouse menu
        return
    if not action_id.startswith("mm:"):
        window._handle_object_context_action(entity_id, action_id)
        return
    _mm, group, *rest = action_id.split(":")
    arg = rest[0] if rest else ""
    if group == "survey":
        from archforge.ui.survey_dialog import open_survey
        open_survey(window, plan_xy)
        return
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
    elif group == "camera" and entity_id and getattr(window, "_cameras", None) is not None:
        window._cameras.activate(entity_id)
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
    elif group == "wall" and arg == "corner" and entity_id and plan_xy is not None:
        window._corner_tool.start()                        # this wall is the 1st: next click on the other one
        window._corner_tool.pick(entity_id, (float(plan_xy[0]), float(plan_xy[1])))
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
    elif group == "krun":
        from archforge.ui.cabinet_run_tool import run as cabinet_run
        cabinet_run(window, arg, entity_id, plan_xy)
    elif group == "roomuse" and plan_xy is not None:
        if arg == "name":
            if getattr(window, "_no_modal_dialogs", False):
                return
            from PySide6.QtWidgets import QInputDialog
            text, ok = QInputDialog.getText(window, "Όνομα χώρου", "Όνομα (π.χ. Υπνοδωμάτιο 2):")
            if ok:
                set_room_use(window, *plan_xy, text)
        else:
            set_room_use(window, *plan_xy, ROOM_USES[int(arg)])
    elif group == "roofroom" and plan_xy is not None:
        window._set_room_roof(arg, *plan_xy)
    elif group == "slab":
        from archforge.ui import slab_tools
        if arg == "railing" and entity_id:
            slab_tools.opening_railing(window, entity_id)
        elif arg == "draw":
            slab_tools.start_opening_tool(window)
        elif arg == "balcony":
            slab_tools.start_balcony_tool(window)
        elif plan_xy is not None:
            slab_tools.room_opening(window, *plan_xy, use=arg)
    elif group == "drywall" and plan_xy is not None:
        from archforge.ui.drywall_tools import place_in_room
        place_in_room(window, *plan_xy)
    elif group == "structure":
        (window._design_structure if arg == "design" else window._propose_frame)()
    elif group == "analyze":
        window._show_structural_analysis()
    elif group == "fit" and entity_id:
        from archforge.core.commands import UpdateEntity
        from archforge.geometry.fit_top import fit_to_ceiling
        entity = window.doc.get(entity_id)
        try:
            if arg == "flat":
                h = entity.params.get("top_heights") or [entity.params["height"]]
                changes = {"height": min(h), "top_heights": []}
            else:
                changes = fit_to_ceiling(window.doc, entity)
            window.stack.execute(UpdateEntity(entity_id, changes))
        except ValueError as exc:
            window.statusBar().showMessage(str(exc), 6000)
        else:
            window._redraw_views(all_views=True); window.refresh_inspector()
            h = changes.get("top_heights") or [changes["height"]]
            window.statusBar().showMessage(
                (f"Ύψος ως την οροφή: {min(h) * 100:.0f}–{max(h) * 100:.0f} cm (λοξό καπάκι)" if len(h) > 1 else
                 f"Ύψος {h[0] * 100:.0f} cm") + " · Ctrl+Z = αναίρεση", 7000)
    elif group == "stairdlg" and entity_id and arg == "cabinets":
        from archforge.architecture.stair_options import under_stair_command
        try:
            command, new = under_stair_command(window.doc, entity_id)
            window.stack.execute(command)
        except ValueError as exc:
            window.statusBar().showMessage(str(exc), 6000)
        else:
            window._redraw_views(all_views=True)
            window.statusBar().showMessage(f'Ντουλάπια κάτω από τη σκάλα: {len(new)} — ύψος κατά την κλίση · Ctrl+Z', 7000)
    elif group == "stairdlg" and entity_id:
        from archforge.ui.stair_dialog import open_stair_dialog
        open_stair_dialog(window, entity_id)
    elif group == "curvedwall":
        window._curved_wall_tool.start()
    elif group == "pool" and entity_id:
        if arg == "shape":
            window._pool_shape_tool.start(entity_id)
        elif arg == "section":
            from archforge.ui.section_view import pool_section
            pool_section(window, entity_id)
        elif arg == "rect":
            window._set_entity_choice(entity_id, "outline", [])
    elif group == "member_statics" and entity_id:
        window._show_member_statics(entity_id)
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
CROSS = (0, 2, 4, 6)


class MarkingMenu(QWidget):
    """Qt drawing of a menu from ``build_menu`` (used by the 2D plan).

    The ring sits on a soft disc so its buttons read as one thing over the drawing; commands carry an icon
    with a short label.  An entry with ``children`` opens its submenu right here (the centre becomes
    «‹ title» = back); Esc / right click go back one level, then close.
    """
    chosen = Signal(str)
    wheeled = Signal(int)
    RADIUS = 92
    INLINE_PANEL = INLINE_PANEL      # up to this many secondary choices show as buttons under the ring
    GRID_COLUMNS = 3                 # a long submenu (the kitchen catalogue) is a grid, not a ring

    def __init__(self, parent, menu, center_pos):
        super().__init__(parent)
        self.setObjectName("markingMenu")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.menu = menu
        self.stack = []              # [(entries, centre)] — where «‹» goes back to
        self.buttons = {}
        self._anchor = center_pos
        self.center = QToolButton(self)
        self.center.setAutoRaise(True)
        self.center.clicked.connect(self.back)
        self._disc = None
        self._entries, self._center_text = menu["entries"], menu["center"]
        self._show(menu["entries"], menu["center"])
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ------------------------------------------------------------ content
    def _clear(self):
        for b in list(self.buttons.values()):
            b.hide(); b.deleteLater()
        self.buttons = {}
        for w in getattr(self, "_extra", ()):
            w.hide(); w.deleteLater()
        self._extra = []

    def _show(self, entries, center_text):
        self._clear()
        radial = [e for e in entries if e["placement"] == "radial"]
        panel = [e for e in entries if e["placement"] == "panel"]
        sub = bool(self.stack)
        self.center.setText(("‹ " if sub else "") + center_text)
        self.center.setToolTip("Πίσω" if sub else "")
        self.center.setCursor(Qt.CursorShape.PointingHandCursor if sub else Qt.CursorShape.ArrowCursor)
        self.center.setStyleSheet("QToolButton { background: rgba(32,41,53,0.90); color: white; border-radius: 9px;"
                                  " padding: 3px 9px; font-weight: 600; border: 0; }"
                                  + (" QToolButton:hover { background: rgba(47,107,214,0.95); }" if sub else ""))
        self.center.adjustSize()
        two_rings = self.menu.get("custom") and not self.stack and len(radial) <= 16
        if len(radial) > 8 and not two_rings:
            self._grid(radial + panel)
            return
        size = 2 * self.RADIUS + 300
        self.resize(size, size + 10)
        cx, cy = size // 2, size // 2
        self.center.move(cx - self.center.width() // 2, cy - self.center.height() // 2)
        clear = self.center.width() / 2 + 10                 # keep the side buttons off the centre title
        if len(radial) > 8:
            # The human's menu with more than 8: an outer ring between the inner slots (mouse_menus.ring_slots).
            from archforge.ui.mouse_menus import ring_slots
            size = int(2 * self.RADIUS * 1.85 + 260)
            self.resize(size, size + 10); cx = cy = size // 2
            self.center.move(cx - self.center.width() // 2, cy - self.center.height() // 2)
            for (dx, dy), e in zip(ring_slots(len(radial), self.RADIUS), radial):
                b = self._button(e)
                b.move(int(cx + dx - b.width() / 2), int(cy + dy - b.height() / 2))
            self._disc = (cx, cy, int(self.RADIUS * 1.85 + 46))
        else:
            slots = CROSS if len(radial) <= 4 else range(8)      # few choices: N, E, S, W (shorter, steadier moves)
            for k, e in zip(slots, radial):
                dx, dy = COMPASS[k]
                b = self._button(e)
                x = cx + dx * self.RADIUS + math.copysign(max(0.0, clear - self.RADIUS * abs(dx) + b.width() / 2), dx) * (abs(dx) > 0.5)
                b.move(int(x - b.width() / 2), int(cy + dy * self.RADIUS - b.height() / 2))
            self._disc = (cx, cy, self.RADIUS + 46)
        if panel:
            # Secondary choices under the ring (≤ 3: _fit puts the rest in «Περισσότερα ▸»).
            row = [self._button(e, flat=True) for e in panel]
            gap = 6
            x = cx - (sum(b.width() for b in row) + gap * (len(row) - 1)) // 2
            for b in row:
                b.move(int(x), int(cy + self.RADIUS + 50)); x += b.width() + gap
        self._place()
        self.update()

    def _grid(self, entries):
        cols = self.GRID_COLUMNS
        made = [self._button(e, flat=True, compact=True) for e in entries]
        w = max(b.width() for b in made); h = max(b.height() for b in made)
        for b in made:
            b.resize(w, h)
        rows = (len(made) + cols - 1) // cols
        gap = 4
        width = cols * w + (cols - 1) * gap + 24
        height = self.center.height() + 18 + rows * (h + gap) + 12
        self.resize(max(width, self.center.width() + 24), height)
        self.center.move(self.width() // 2 - self.center.width() // 2, 8)
        top = self.center.height() + 18
        for k, b in enumerate(made):
            r, c = divmod(k, cols)
            b.move(12 + c * (w + gap), top + r * (h + gap))
        self._disc = None
        self._place()
        self.update()

    def _place(self):
        parent = self.parentWidget()
        x, y = int(self._anchor.x() - self.width() / 2), int(self._anchor.y() - self.height() / 2)
        if parent is not None:
            x = max(0, min(parent.width() - self.width(), x))
            y = max(0, min(parent.height() - self.height(), y))
        self.move(x, y)

    def _button(self, e, flat=False, compact=False):
        from archforge.ui.menu_icons import icon
        b = QToolButton(self)
        label = e["label"] + (" ▸" if e.get("children") else "")
        b.setText(label)
        if e.get("small") and e.get("icon"):
            # The rarely used things: one small round icon, the name in its tooltip.
            b.setIcon(icon(e["icon"])); b.setIconSize(QSize(18, 18)); b.setToolTip(label)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            b.setStyleSheet("QToolButton { background: #ffffff; border: 1px solid #c3ccd8; border-radius: 15px; }"
                            " QToolButton:hover { background: #e3eefc; border-color: #2F6BD6; }")
            b.resize(30, 30)
            b.clicked.connect(lambda _=False, entry=e: self.open_submenu(entry))
            b.show()
            self.buttons[e["id"]] = b
            return b
        if e.get("icon"):
            b.setIcon(icon(e["icon"]))
            b.setIconSize(QSize(20, 20) if compact or flat else QSize(22, 22))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if (flat or compact)
                                 else Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        base = "#ffe9e7" if e["danger"] else ("#d6e7fb" if e["checked"] else "#ffffff")
        border = "#d9a29c" if e["danger"] else ("#2F6BD6" if e["checked"] else "#c3ccd8")
        b.setStyleSheet("QToolButton { background: %s; border: 1px solid %s; border-radius: 8px; padding: %s;"
                        " font-size: 12px; font-weight: %s; color: #1E2A3B; }"
                        " QToolButton:hover { background: #e3eefc; border-color: #2F6BD6; }"
                        % (base, border, "3px 8px" if (flat or compact) else "3px 6px", "600" if e["checked"] else "400"))
        b.adjustSize()
        b.resize(max(58, b.sizeHint().width()), max(28, b.sizeHint().height()))
        if e.get("children"):
            b.clicked.connect(lambda _=False, entry=e: self.open_submenu(entry))
        else:
            b.clicked.connect(lambda _=False, i=e["id"]: self.chosen.emit(i))
        b.show()
        self.buttons[e["id"]] = b
        return b

    # ------------------------------------------------------------ navigation
    def open_submenu(self, entry):
        """The submenu in place of the ring; «‹» (or Esc) back."""
        self.stack.append((self._entries, self._center_text))
        children = [dict(c) for c in entry["children"]]
        # Up to 8 on the ring (+3 below); a long list (the kitchen catalogue) as a grid.
        self._entries = _fit(children) if len(children) <= 8 + INLINE_PANEL else children
        self._center_text = entry["label"]
        self._show(self._entries, self._center_text)
        self.setFocus()

    def back(self):
        if not self.stack:
            return False
        self._entries, self._center_text = self.stack.pop()
        self._show(self._entries, self._center_text)
        self.setFocus()
        return True

    def set_center(self, text):
        cx = self.center.x() + self.center.width() // 2
        self.center.setText(("‹ " if self.stack else "") + text)
        self.center.adjustSize()
        self.center.move(cx - self.center.width() // 2, self.center.y())

    # ------------------------------------------------------------ Qt
    def event(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.ShortcutOverride and event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Backspace) \
                and self.stack:
            event.accept()             # Esc inside a submenu = back (not the window's «cancel everything»)
            return True
        return super().event(event)

    def paintEvent(self, event):
        if self._disc is None:
            from PySide6.QtGui import QColor, QPainter, QPen
            p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setPen(QPen(QColor(195, 204, 216), 1)); p.setBrush(QColor(255, 255, 255, 235))
            p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
            return
        from PySide6.QtGui import QColor, QPainter, QPen
        cx, cy, r = self._disc
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(195, 204, 216, 200), 1)); p.setBrush(QColor(246, 248, 251, 215))
        p.drawEllipse(QPoint(cx, cy), r, r)

    def wheelEvent(self, event):
        steps = 1 if event.angleDelta().y() > 0 else -1
        self.wheeled.emit(steps)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self.back():
            return
        self.close()               # a click on empty menu space just closes it

    def contextMenuEvent(self, event):
        if not self.back():
            self.close()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Backspace):
            if not self.back():
                self.close()
            return
        super().keyPressEvent(event)
