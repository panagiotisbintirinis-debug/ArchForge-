"""Every layer of a wall can be picked and changed (owner 30/10: «κάθε στρώση να είναι επιλέξιμη και δυνατότητα να
αλλαχτεί»).

On a wall that is already selected, a click (not a drag — a drag still moves the wall) on one of its layers in the
plan picks **that layer**: it is outlined in the plan, its row is marked in Ιδιότητες ▸ Σύνθεση·υλικά, and a small
menu opens by the cursor — Υλικό ▸, Πάχος…, Ρόλος ▸, προς τα έξω / μέσα, Αφαίρεση, ⓘ Ιδιότητες υλικού.  A change goes
where a change in Ιδιότητες goes (``wall_assemblies.layer_change_command``: a built-in type → this wall's own copy, a
project type → all its walls unless «Μόνο αυτός ο τοίχος»), one undo each.  The pick is view state, not the model.
"""
from __future__ import annotations

from archforge.geometry.regions import point_in_polygon


def layer_at(doc, wall_id, x, y):
    """The index (in the wall's type, exterior first) of the layer under plan point (x, y), or None."""
    from archforge.architecture.wall_layer_plan import wall_bands
    wall = doc.entities.get(wall_id)
    if wall is None or wall.kind != "wall":
        return None
    for band in wall_bands(doc, wall):
        for outer, holes in band["islands"]:
            if point_in_polygon(x, y, outer) and not any(point_in_polygon(x, y, h) for h in holes):
                return band["index"]
    return None


def current(window):
    """``(wall id, index)`` of the picked layer while its wall is the selection, else None."""
    pick = getattr(window.plan_view, "layer_pick", None)
    if not pick:
        return None
    wid, index = pick
    from archforge.architecture.wall_types import layers
    wall = window.doc.entities.get(wid)
    if wall is None or list(window.doc.selection or ()) != [wid] or index >= len(
            layers(wall.params.get("wall_type", "generic"), window.doc)):
        window.plan_view.layer_pick = None
        return None
    return pick


class Highlight:
    """Paints the picked layer's outline over the plan (``plan_view.redraw`` calls ``paint``)."""

    def __init__(self, window):
        self.window = window

    def paint(self, view):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
        from archforge.architecture.wall_layer_plan import wall_bands
        pick = current(self.window)
        if not pick:
            return
        wid, index = pick
        pen = QPen(QColor(240, 140, 30)); pen.setWidthF(.02); pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        for band in wall_bands(view.doc, view.doc.get(wid)):
            if band["index"] != index:
                continue
            for outer, _holes in band["islands"]:
                path = QPainterPath(QPointF(*outer[0]))
                for q in outer[1:]:
                    path.lineTo(QPointF(*q))
                path.closeSubpath()
                view._scene.addPath(path, pen, QBrush(QColor(240, 140, 30, 70))).setZValue(25)


def pick(window, wall_id, x, y, global_pos=None):
    """Pick the layer of ``wall_id`` under (x, y): outline, mark in Ιδιότητες, open the layer menu.  Returns the
    index, or None (the click was not on a layer: nothing picked)."""
    from archforge.ui import wall_layers_panel
    index = layer_at(window.doc, wall_id, x, y)
    window.plan_view.layer_pick = (wall_id, index) if index is not None else None
    if index is None:
        window.plan_view.redraw()
        return None
    wall_layers_panel._OPEN.add(wall_id)
    window.refresh_inspector()
    window.plan_view.redraw()
    menu = layer_menu(window, wall_id, index)
    if global_pos is not None:
        menu.popup(global_pos)
    return index


def _rows(window, wall_id):
    from archforge.architecture.wall_assemblies import layer_specs
    return layer_specs(window.doc, window.doc.get(wall_id).params.get("wall_type", "generic"))


def apply(window, wall_id, rows, index=None):
    """Run the layer change for ``rows`` (one undo); the pick follows the layer to ``index``."""
    from archforge.architecture.wall_assemblies import layer_change_command
    scope = "wall" if getattr(window, "_layer_scope_wall_only", False) else None
    try:
        window.stack.execute(layer_change_command(window.doc, wall_id, rows, scope))
    except (ValueError, KeyError) as exc:
        window.statusBar().showMessage(f"Στρώση: η αλλαγή δεν έγινε — {exc}", 8000)
        return False
    window.plan_view.layer_pick = (wall_id, index) if index is not None else None
    window._redraw_views(all_views=True)
    window.refresh_inspector()
    return True


def layer_menu(window, wall_id, index):
    from PySide6.QtGui import QAction, QActionGroup
    from PySide6.QtWidgets import QInputDialog, QMenu
    from archforge.architecture.wall_assemblies import default_scope, walls_of_type
    from archforge.construction.building_materials import MATERIALS, ROLES, by_category
    rows = _rows(window, wall_id)
    row = rows[index]
    m = MATERIALS[row["material"]]
    menu = QMenu(window.plan_view)
    head = menu.addAction(f"Στρώση {index + 1}/{len(rows)} · {m.name} · {row['thickness'] * 100:g} cm · {ROLES[row['role']]}")
    head.setEnabled(False)
    acts = {}

    def change(**kw):
        new = [dict(r) for r in rows]
        new[index].update(kw)
        return apply(window, wall_id, new, index)

    mats = menu.addMenu("Υλικό")
    for category, items in by_category().items():
        sub = mats.addMenu(category)
        group = QActionGroup(sub)
        for mat in items:
            a = QAction(mat.name, sub); a.setCheckable(True); a.setChecked(mat.id == row["material"])
            a.triggered.connect(lambda _=False, mid=mat.id: mid != row["material"] and change(material=mid,
                                                                                           role=MATERIALS[mid].role))
            group.addAction(a); sub.addAction(a); acts[f"material:{mat.id}"] = a

    def ask_thickness():
        if getattr(window, "_no_modal_dialogs", False):
            return
        value, ok = QInputDialog.getDouble(window, "Πάχος στρώσης", f"{m.name} (cm):", row["thickness"] * 100, 0.1, 200.0, 1)
        if ok and abs(value / 100 - row["thickness"]) > 1e-9:
            change(thickness=round(value / 100, 4))
    acts["thickness"] = menu.addAction("Πάχος…"); acts["thickness"].triggered.connect(ask_thickness)
    roles = menu.addMenu("Ρόλος")
    for key, text in ROLES.items():
        a = roles.addAction(text); a.setCheckable(True); a.setChecked(key == row["role"])
        a.triggered.connect(lambda _=False, k=key: k != row["role"] and change(role=k)); acts[f"role:{key}"] = a
    menu.addSeparator()

    def move(step):
        j = index + step
        new = [dict(r) for r in rows]
        new[index], new[j] = new[j], new[index]
        apply(window, wall_id, new, j)
    acts["out"] = menu.addAction("Προς τα έξω"); acts["out"].setEnabled(index > 0)
    acts["out"].triggered.connect(lambda: move(-1))
    acts["in"] = menu.addAction("Προς τα μέσα"); acts["in"].setEnabled(index < len(rows) - 1)
    acts["in"].triggered.connect(lambda: move(1))
    acts["remove"] = menu.addAction("Αφαίρεση στρώσης"); acts["remove"].setEnabled(len(rows) > 1)
    acts["remove"].triggered.connect(lambda: apply(window, wall_id, [r for k, r in enumerate(rows) if k != index]))
    menu.addSeparator()
    if default_scope(window.doc, wall_id) == "type" and len(walls_of_type(
            window.doc, window.doc.get(wall_id).params.get("wall_type"))) > 1:
        only = menu.addAction("Μόνο αυτός ο τοίχος"); only.setCheckable(True)
        only.setChecked(bool(getattr(window, "_layer_scope_wall_only", False)))
        only.toggled.connect(lambda on: setattr(window, "_layer_scope_wall_only", bool(on)))
        acts["only"] = only
    info = menu.addAction("ⓘ Ιδιότητες υλικού…")
    from archforge.ui.wall_layers_panel import material_dialog
    info.triggered.connect(lambda: material_dialog(window, row["material"])); acts["info"] = info
    window._layer_menu, window._layer_menu_actions = menu, acts
    return menu
