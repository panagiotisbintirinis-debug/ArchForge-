"""A room by its name (owner 30/10: «Χώρος 1, Χώρος 2 — δεν μπορώ να αλλάξω το όνομα· το 2Δ να μου δίνει περιθώριο να
ονομάσω το χώρο, και μετά στο δέντρο να φαίνεται σαν δωμάτιο· αν το επιλέξω να μου δείχνει τους τοίχους και γενικές
πληροφορίες»).

- Double click on a room's label (or on the room where nothing else is) in the plan: its name, free text or one of
  the uses — ``SetRoomMetadata``, one undo.  The tree, the plan label and the take-off read the same name.
- A room chosen in the tree (or renamed): its walls selected, and Ιδιότητες shows the room — name (editable), use,
  storey, net / axis area, perimeter, size, its walls.
Rooms are derived from the walls (``doc.active_room_faces``); their name / use live in ``doc.room_data`` by signature.
"""
from __future__ import annotations


def find_room(doc, signature):
    """``(face, z, index)`` of the room with this signature on any storey (index = its «Χώρος N»), or None."""
    for z in sorted({round(float(v), 4) for v in doc.levels.values()} | {0.0}):
        for index, face in enumerate(doc.active_room_faces(z=z), start=1):
            if face.signature == signature:
                return face, z, index
    return None


def room_at(doc, x, y):
    """Signature of the room of the active storey under (x, y), or None."""
    from archforge.geometry.regions import point_in_polygon
    face = next((f for f in doc.active_room_faces() if point_in_polygon(float(x), float(y), f.polygon)), None)
    return face.signature if face is not None else None


def room_name(doc, signature, index=None):
    data = doc.room_metadata(signature) if hasattr(doc, "room_metadata") else {}
    return data.get("name") or (f"Χώρος {index}" if index else "Χώρος")


def _ask_name(window, current):
    """The human's name for the room: free text, or one of the uses (editable list)."""
    hook = getattr(window, "_room_name_prompt", None)       # tests
    if callable(hook):
        return hook(current)
    from PySide6.QtWidgets import QInputDialog
    from archforge.ui.marking_menu import ROOM_USES
    items = [current] + [u for u in ROOM_USES if u != current]
    text, ok = QInputDialog.getItem(window, "Όνομα χώρου", "Όνομα (γράψε ή διάλεξε):", items, 0, True)
    return text if ok else None


def rename_room(window, signature, name=None):
    """Set the room's name — one undo.  ``name`` None → ask.  A name that is one of the uses sets the use too."""
    from archforge.core.commands import SetRoomMetadata
    from archforge.ui.marking_menu import ROOM_USES
    found = find_room(window.doc, signature)
    if found is None:
        return False
    _face, _z, index = found
    current = room_name(window.doc, signature, index)
    if name is None:
        name = _ask_name(window, current)
    name = str(name or "").strip()
    if not name or name == current:
        return False
    changes = {"name": name}
    if name in ROOM_USES:
        changes["use"] = name
    window.stack.execute(SetRoomMetadata(signature, changes))
    window._redraw_views(all_views=True)
    if hasattr(window, "_refresh_project_tree"):
        window._refresh_project_tree()
    show_room(window, signature)
    window.statusBar().showMessage(f"Χώρος: «{name}» — Ctrl+Z για αναίρεση", 5000)
    return True


def show_room(window, signature):
    """Select the room's walls and show the room in Ιδιότητες."""
    found = find_room(window.doc, signature)
    if found is None:
        return False
    face, _z, _index = found
    window._inspected_room = signature
    window.doc.select([i for i in face.wall_ids if i in window.doc.entities])
    window.refresh_inspector()
    dock = getattr(window, "dock", None)
    if dock is not None:
        dock.show(); dock.raise_()
    return True


def is_room_selection(window):
    """The selection is exactly the walls of the room shown last (tree / plan): Ιδιότητες shows the room."""
    signature = getattr(window, "_inspected_room", None)
    found = find_room(window.doc, signature) if signature else None
    if found is None:
        return None
    walls = {i for i in found[0].wall_ids if i in window.doc.entities}
    return signature if walls and set(window.doc.selection or ()) == walls else None


def add_room_rows(window, signature):
    """Ιδιότητες of a room: name (editable), use, storey, areas, perimeter, size, walls."""
    from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit
    from archforge.architecture.topology import room_metrics
    from archforge.ui.marking_menu import ROOM_USES
    doc = window.doc
    face, z, index = find_room(doc, signature)
    data = doc.room_metadata(signature)
    form = window.form
    title = QLabel(f"<b>Χώρος {index}</b>"); form.addRow(title)
    name = QLineEdit(room_name(doc, signature, index)); name.setObjectName("roomName")
    name.editingFinished.connect(lambda: rename_room(window, signature, name.text()))
    form.addRow("Όνομα", name)
    use = QComboBox(); use.setObjectName("roomUse"); use.addItem("—", "")
    for u in ROOM_USES:
        use.addItem(u, u)
    use.setCurrentIndex(max(0, use.findData(data.get("use", ""))))

    def set_use(_i):
        from archforge.core.commands import SetRoomMetadata
        value = use.currentData() or ""
        if value != doc.room_metadata(signature).get("use", ""):
            window.stack.execute(SetRoomMetadata(signature, {"use": value}))
            window._redraw_views(all_views=True)
            window._refresh_project_tree()
    use.activated.connect(set_use)
    form.addRow("Χρήση", use)
    storey = next((n for n, v in doc.levels.items() if abs(float(v) - z) < 1e-4), f"{z:+.2f} m")
    from archforge.ui.workspace_layout import level_label
    form.addRow("Όροφος", QLabel(level_label(storey)))
    m = room_metrics(face.polygon)
    try:
        from archforge.quantities.takeoff import _area, net_polygon
        net = abs(_area(net_polygon(doc, face.polygon, z)))
        form.addRow("Εμβαδόν (καθαρό)", QLabel(f"{net:.2f} m²"))
    except Exception as exc:
        from archforge.core.notices import not_computed
        not_computed("room.net_area", "Χώρος: το καθαρό εμβαδόν δεν υπολογίστηκε", exc=exc)
        form.addRow("Εμβαδόν (καθαρό)", QLabel("δεν υπολογίστηκε"))
    form.addRow("Εμβαδόν (στους άξονες)", QLabel(f"{m['area']:.2f} m²"))
    form.addRow("Περίμετρος", QLabel(f"{m['perimeter']:.2f} m"))
    xs = [p[0] for p in face.polygon]; ys = [p[1] for p in face.polygon]
    form.addRow("Διαστάσεις", QLabel(f"{max(xs) - min(xs):.2f} × {max(ys) - min(ys):.2f} m"))
    walls = [doc.get(i) for i in face.wall_ids if i in doc.entities]
    names = ", ".join((w.name or "Τοίχος") for w in walls[:8]) + (" …" if len(walls) > 8 else "")
    shown = QLabel(f"{len(walls)} — {names}"); shown.setWordWrap(True)
    form.addRow("Τοίχοι", shown)
