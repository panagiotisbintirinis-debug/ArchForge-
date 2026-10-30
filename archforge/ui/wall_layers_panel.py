"""«Σύνθεση·υλικά» in a wall's Ιδιότητες (spec §3 step 3, owner 30/10: «λεπτομέρεια μόνο όταν πραγματικά χρειάζεται»
· «οι ιδιότητες των υλικών μέσα στα μενού, εκτός από τη βιβλιοθήκη να υπάρχει σχέση»).

Closed: one line (layers · thickness · indicative U).  «Στρώσεις ▸» opens the layers, exterior first: material,
thickness, role, ⓘ (the building material's properties: λ with its status, density, price code, the look it links
to — the data-sheet values can be typed there).  A change goes to every wall of a project type or, for a built-in
type, to this wall's own copy (``wall_assemblies.default_scope``); «Μόνο αυτός ο τοίχος» says otherwise.
Every change is one undo (``wall_assemblies`` / ``building_materials`` commands).
"""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QToolButton, QVBoxLayout, QWidget)

_OPEN = set()          # wall ids whose layers are open (kept across the inspector rebuilds)


def summary(doc, wall_type):
    from archforge.architecture.wall_types import indicative_u, layers
    ls = layers(wall_type, doc)
    if not ls:
        return ""
    u = indicative_u(wall_type, doc)
    text = f"{len(ls)} στρώσεις · {sum(l[1] for l in ls) * 100:.1f} cm"
    return text + (f" · U ≈ {u:.2f} W/m²K (ενδεικτικό, όχι ΚΕΝΑΚ)" if u else "")


def add_rows(window, eid):
    from archforge.architecture import wall_assemblies as wa
    from archforge.architecture.wall_types import layers
    doc, form = window.doc, window.form
    wall_type = str(doc.get(eid).params.get("wall_type", "generic"))
    ls = layers(wall_type, doc)
    if not ls:
        return
    head = QWidget(); row = QHBoxLayout(head); row.setContentsMargins(0, 0, 0, 0)
    toggle = QToolButton(); toggle.setText("Στρώσεις ▾" if eid in _OPEN else "Στρώσεις ▸")
    toggle.setToolTip("Τα υλικά της σύνθεσης, από έξω προς τα μέσα")
    text = QLabel(summary(doc, wall_type)); text.setWordWrap(True)
    row.addWidget(toggle); row.addWidget(text, 1)
    form.addRow("Σύνθεση·υλικά", head)
    window._wall_layers_toggle = toggle

    def flip():
        _OPEN.symmetric_difference_update({eid})
        _rebuild(window)
    toggle.clicked.connect(flip)
    if eid not in _OPEN:
        return

    scope_box = None
    if wa.default_scope(doc, eid) == "type":
        n = len(wa.walls_of_type(doc, wall_type))
        scope_box = QCheckBox(f"Μόνο αυτός ο τοίχος (αλλιώς και οι {n} τοίχοι της σύνθεσης)" if n > 1
                              else "Μόνο αυτός ο τοίχος")
        form.addRow("", scope_box)
    window._wall_layers_scope = scope_box
    rows = [l.spec() for l in ls]

    def apply(new_rows):
        scope = "wall" if scope_box is not None and scope_box.isChecked() else None
        _execute(window, lambda: wa.layer_change_command(doc, eid, new_rows, scope))

    window._wall_layer_rows = []
    for i, layer in enumerate(ls):
        form.addRow(f"{i + 1}." if i else "1. έξω", _layer_row(window, rows, i, apply))
    add = QPushButton("+ στρώση μέσα"); add.setToolTip("Νέα στρώση στην εσωτερική πλευρά")
    add.clicked.connect(lambda: apply(rows + [{"material": "cement_plaster", "thickness": 0.02}]))
    form.addRow("", add)
    window._wall_layers_add = add


def _layer_row(window, rows, i, apply):
    from archforge.construction.building_materials import ROLES, by_category
    r = rows[i]
    box = QWidget(); v = QVBoxLayout(box); v.setContentsMargins(0, 0, 0, 4); v.setSpacing(2)
    line = QWidget(); h = QHBoxLayout(line); h.setContentsMargins(0, 0, 0, 0)
    mat = QComboBox()
    for category, items in by_category().items():
        for m in items:
            mat.addItem(f"{m.name}", m.id)
            mat.setItemData(mat.count() - 1, category, 3)      # tooltip = category
    mat.setCurrentIndex(max(0, mat.findData(r["material"])))
    thick = QDoubleSpinBox(); thick.setDecimals(1); thick.setRange(0.1, 200.0); thick.setSuffix(" cm")
    thick.setValue(r["thickness"] * 100)
    role = QComboBox()
    for k, text in ROLES.items():
        role.addItem(text, k)
    role.setCurrentIndex(max(0, role.findData(r["role"])))
    info = QToolButton(); info.setText("ⓘ"); info.setToolTip("Ιδιότητες υλικού (λ, πυκνότητα, κωδικός τιμής, εμφάνιση)")
    drop = QToolButton(); drop.setText("−"); drop.setToolTip("Αφαίρεση στρώσης"); drop.setEnabled(len(rows) > 1)
    v.addWidget(mat); v.addWidget(line)                  # narrow panel: material on its own line
    for w in (thick, role, info, drop):
        h.addWidget(w, 1 if w is role else 0)

    def changed(**kw):
        new = [dict(x) for x in rows]
        new[i].update(kw)
        if new != rows:
            apply(new)
    mat.currentIndexChanged.connect(lambda _i: changed(material=mat.currentData(), role=_default_role(mat.currentData())))
    thick.editingFinished.connect(lambda: abs(thick.value() / 100 - r["thickness"]) > 1e-9
                                  and changed(thickness=round(thick.value() / 100, 4)))
    role.currentIndexChanged.connect(lambda _i: changed(role=role.currentData()))
    info.clicked.connect(lambda: material_dialog(window, r["material"]))
    drop.clicked.connect(lambda: apply([x for k, x in enumerate(rows) if k != i]))
    from archforge.ui.layer_pick import current
    picked = current(window) == (window.doc.selection[0] if window.doc.selection else None, i)
    if picked:                                         # the layer picked in the plan (layer_pick.py)
        box.setStyleSheet("QWidget#picked { background: rgba(240, 140, 30, 60); border-radius: 4px; }")
        box.setObjectName("picked")
    window._wall_layer_rows.append({"material": mat, "thickness": thick, "role": role, "info": info, "drop": drop,
                                    "picked": picked})
    return box


def _default_role(material_id):
    from archforge.construction.building_materials import MATERIALS
    return MATERIALS[material_id].role


def material_text(doc, material_id):
    """What ⓘ shows, as text (also for tests)."""
    from archforge.construction.building_materials import ROLES, material
    from archforge.core.provenance import STATUS_LABELS
    from archforge.rendering.materials import material_name
    m = material(material_id, doc)
    lam = f"{m.conductivity:g} W/mK" if m.conductivity is not None else "—"
    lines = [f"<b>{m.name}</b> · {m.category} · {ROLES[m.role]}",
             f"λ = {lam} — {STATUS_LABELS[m.conductivity_status]}",
             f"<i>{m.conductivity_source}</i>",
             "Πυκνότητα: " + (f"{m.density:g} kg/m³" if m.density is not None else "— (από το φύλλο του προϊόντος)"),
             f"Κωδικός τιμοκαταλόγου: {m.price_code} (τιμή μόνο από τον τιμοκατάλογό σου, ανά m³)",
             "Εμφάνιση (3D): " + (material_name(m.appearance) if m.appearance else "δεν φαίνεται (μέσα στον τοίχο)")]
    return "<br>".join(lines)


def material_dialog(window, material_id):
    """The building material's properties; the data-sheet λ / density of the project can be typed (one undo)."""
    from archforge.construction import building_materials as bm
    doc = window.doc
    m = bm.material(material_id, doc)
    dlg = QDialog(window); dlg.setWindowTitle(f"Υλικό δόμησης — {m.name}")
    lay = QVBoxLayout(dlg)
    text = QLabel(material_text(doc, material_id)); text.setWordWrap(True); lay.addWidget(text)
    own = bm.overrides(doc).get(material_id, {})
    form = QFormLayout(); lay.addLayout(form)
    lam = QLineEdit("" if own.get("conductivity") is None else f"{own['conductivity']:g}")
    lam.setPlaceholderText("κενό = η τιμή του προγράμματος")
    rho = QLineEdit("" if own.get("density") is None else f"{own['density']:g}")
    src = QLineEdit(str(own.get("source") or "")); src.setPlaceholderText("π.χ. φύλλο προϊόντος, έκδοση")
    form.addRow("λ από φύλλο (W/mK)", lam); form.addRow("Πυκνότητα (kg/m³)", rho); form.addRow("Πηγή", src)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); lay.addWidget(buttons)
    buttons.rejected.connect(dlg.reject)

    def number(edit):
        t = edit.text().strip().replace(",", ".")
        return float(t) if t else None

    def accept():
        try:
            values = dict(conductivity=number(lam), density=number(rho), source=src.text().strip())
        except ValueError:
            window.statusBar().showMessage("Υλικό: γράψε αριθμό (π.χ. 0,035)", 6000)
            return
        if values["conductivity"] != own.get("conductivity") or values["density"] != own.get("density") \
                or values["source"] != str(own.get("source") or ""):
            _execute(window, lambda: bm.set_properties_command(doc, material_id, **values))
        dlg.accept()
    buttons.accepted.connect(accept)
    window._building_material_dialog = dlg
    dlg.open()
    return dlg


def _execute(window, make):
    try:
        window.stack.execute(make())
    except (ValueError, KeyError) as exc:
        window.statusBar().showMessage(f"Σύνθεση: η αλλαγή δεν έγινε — {exc}", 8000)
        return
    window._redraw_views(all_views=True)
    _rebuild(window)


def _rebuild(window):
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window.refresh_inspector)      # rebuild the form outside the widget's signal
