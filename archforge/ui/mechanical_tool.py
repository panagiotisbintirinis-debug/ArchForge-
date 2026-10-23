"""Η/Μ εγκαταστάσεις ▸ Μηχανισμοί: εξάρτημα με κλικ, άρθρωση ανάμεσα σε δύο, θέση με ρυθμιστικό (kinematics/).

* «Εξάρτημα…»: πλάτος / βάθος / ύψος / ύψος από δάπεδο, μετά κλικ στο κέντρο στην κάτοψη.
* «Άρθρωση…»: επιλέγεις δύο εξαρτήματα — το πρώτο μένει, το δεύτερο κινείται — και τύπο
  (στροφή / ολίσθηση / σταθερή). Άξονας, σημείο και όρια βγαίνουν μόνα τους (kinematics/authoring.py).
* Ιδιότητες άρθρωσης: «Θέση» με ρυθμιστικό ανάμεσα στα όρια — η κάτοψη και το 3D δείχνουν το
  εξάρτημα εκεί· κάθε αλλαγή = μία αναίρεση.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QMenu,
                               QSlider)

from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.kinematics import authoring as A


def _ask_part(window):
    dlg = QDialog(window); dlg.setWindowTitle("Μηχανικό εξάρτημα")
    form = QFormLayout(dlg)
    boxes = {}
    for key, label, value, lo, hi in (("width", "Πλάτος (m)", 0.80, 0.01, 50.0), ("depth", "Βάθος (m)", 0.05, 0.005, 50.0),
                                      ("height", "Ύψος (m)", 2.00, 0.01, 50.0), ("z", "Από το δάπεδο (m)", 0.0, -10.0, 50.0)):
        b = QDoubleSpinBox(); b.setRange(lo, hi); b.setDecimals(3); b.setSingleStep(0.05); b.setValue(value)
        boxes[key] = b; form.addRow(label, b)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); form.addRow(buttons)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return {k: b.value() for k, b in boxes.items()}


def start_part(window, spec=None):
    spec = spec or _ask_part(window)
    if not spec:
        return None
    window._mech_part_spec = dict(spec)
    window._start_site_tool("mech_part_place", "Εξάρτημα: κλικ στο κέντρο στην κάτοψη — Esc για τέλος")
    return spec


def place_part(window, x, y, spec=None):
    """Click: one mechanical_part centred there on the active storey (one undo); the tool stays on."""
    spec = spec or getattr(window, "_mech_part_spec", None)
    if not spec:
        return None
    level = float(window.doc.work_plane.origin[2])
    n = 1 + sum(1 for e in window.doc.entities.values() if e.kind == "mechanical_part")
    part = Entity("mechanical_part", A.part_params(x, y, level + float(spec.get("z", 0.0)), spec["width"], spec["depth"],
                                                  spec["height"], spec.get("rotation", 0.0)), name=f"Εξάρτημα {n}")
    window.stack.execute(AddEntity(part))
    window.doc.select([part.id])
    window._redraw_views(all_views=True)
    window._refresh_project_tree()
    window.statusBar().showMessage(f"{part.name} — για να κινείται: επίλεξε το σταθερό και μετά αυτό (Ctrl+κλικ), "
                                   "Μηχανισμοί ▸ Άρθρωση…", 10000)
    return part


def _ask_type(window):
    from PySide6.QtWidgets import QInputDialog
    labels = list(A.JOINT_LABELS.values())
    choice, ok = QInputDialog.getItem(window, "Άρθρωση", "Πώς κινείται το δεύτερο εξάρτημα;", labels, 0, False)
    return list(A.JOINT_LABELS)[labels.index(choice)] if ok else None


def add_joint(window, joint_type=None, ids=None):
    """Two selected parts (first stays, second moves): one mechanical_joint (one undo)."""
    doc = window.doc
    ids = list(ids if ids is not None else doc.selection or ())
    parts = [i for i in ids if i in doc.entities and doc.get(i).kind == "mechanical_part"]
    if len(parts) != 2:
        window.statusBar().showMessage("Άρθρωση: επίλεξε δύο εξαρτήματα — πρώτα αυτό που μένει, μετά αυτό που κινείται "
                                       "(Ctrl+κλικ)", 8000)
        return None
    parent, child = parts
    if any(e.kind == "mechanical_joint" and e.params.get("child_part") == child for e in doc.entities.values()):
        window.statusBar().showMessage(f"{doc.get(child).name}: έχει ήδη άρθρωση — ένα εξάρτημα κινείται από ένα μόνο", 8000)
        return None
    joint_type = joint_type or _ask_type(window)
    if not joint_type:
        return None
    joint = Entity("mechanical_joint", A.default_joint(doc.get(parent), doc.get(child), joint_type),
                   name=f"{A.JOINT_LABELS[joint_type].split(' (')[0]}: {doc.get(parent).name} → {doc.get(child).name}")
    try:
        window.stack.execute(AddEntity(joint))
    except ValueError as exc:
        window.statusBar().showMessage(str(exc), 8000)
        return None
    doc.select([joint.id])
    window._redraw_views(all_views=True)
    window._refresh_project_tree()
    window.refresh_inspector()
    p = joint.params
    window.statusBar().showMessage(f"{joint.name}: {p['min_value']:g}…{p['max_value']:g} {A.UNITS[joint_type]} — "
                                   "«Θέση» στις Ιδιότητες · Ctrl+Z αναιρεί", 10000)
    return joint


def set_value(window, eid, value):
    """Joint position (clamped to its limits): one undo."""
    from archforge.kinematics.model import clamp_joint_value
    p = window.doc.get(eid).params
    window._set_entity_choice(eid, "value", clamp_joint_value(p, float(value)))


def add_rows(window, eid):
    """Properties of a joint: type, limits, «Θέση» slider."""
    p = window.doc.get(eid).params
    jtype = str(p["joint_type"])
    unit = A.UNITS.get(jtype, "")
    window.form.addRow("Τύπος", QLabel(A.JOINT_LABELS.get(jtype, jtype)))
    if jtype == "fixed":
        return True
    lo, hi, value = float(p["min_value"]), float(p["max_value"]), float(p["value"])
    window.form.addRow("Όρια", QLabel(f"{lo:g} … {hi:g} {unit}".replace(".", ",")))
    steps = 1000
    slider = QSlider(); slider.setOrientation(Qt.Orientation.Horizontal); slider.setRange(0, steps)
    slider.setValue(int(round((value - lo) / (hi - lo) * steps)) if hi > lo else 0)
    readout = QLabel(f"{value:.3g} {unit}".replace(".", ","))
    to_value = lambda pos: lo + (hi - lo) * pos / steps
    slider.valueChanged.connect(lambda pos: readout.setText(f"{to_value(pos):.3g} {unit}".replace(".", ",")))
    slider.sliderReleased.connect(lambda: set_value(window, eid, to_value(slider.value())))
    window.form.addRow("Θέση", slider)
    window.form.addRow("", readout)
    window._joint_slider = slider
    return True


def menu(window):
    """«Μηχανισμοί» submenu."""
    from PySide6.QtGui import QAction
    sub = QMenu("Μηχανισμοί (εξαρτήματα && αρθρώσεις)", window)
    part = QAction("Εξάρτημα… (κλικ στο κέντρο)", window); part.triggered.connect(lambda _=False: start_part(window))
    joint = QAction("Άρθρωση… (δύο επιλεγμένα: σταθερό, μετά κινητό)", window)
    joint.triggered.connect(lambda _=False: add_joint(window))
    sub.addAction(part); sub.addAction(joint)
    window._mechanism_menu, window._mechanism_actions = sub, [part, joint]
    return sub
