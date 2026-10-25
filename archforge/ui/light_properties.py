"""Properties of a luminaire / switch: the light (beam, Kelvin, lumen, dim, direction) and its control group.

Same entity as the electrical point (``mep/lighting.py``): every change is one
``UpdateEntity`` through ``window._set_entity_choice`` (undo, save/load), and
the line underneath shows what it means electrically (W, circuit, dimmer,
driver for a strip).
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLabel, QSlider

LIGHT_KEYS = ("lumen", "kelvin", "beam_deg", "dim_level", "w_per_m", "power_w",
              "light_on", "aim_tilt_deg", "aim_azimuth_deg", "target_x", "target_y", "target_z")
KELVINS = (2700.0, 3000.0, 4000.0, 5000.0)   # quick picks of the colour temperature written on the data sheet
DIRECTION_LABELS = {"auto": "Αυτόματα", "down": "Προς τα κάτω", "up": "Προς τα πάνω (έμμεσο)",
                    "wall": "Προς τον τοίχο", "both": "Πάνω και κάτω"}


def _groups(doc):
    return sorted({str(e.params.get("automation_group", "")) for e in doc.entities.values()
                   if e.kind == "electrical_point" and e.params.get("automation_group")})


def _group_combo(window, eid, current):
    combo = QComboBox(); combo.setEditable(True)
    combo.addItem("")
    for g in _groups(window.doc):
        combo.addItem(g)
    combo.setCurrentText(current)
    combo.lineEdit().setPlaceholderText("καμία (ο διακόπτης του χώρου)")
    combo.lineEdit().editingFinished.connect(
        lambda w=combo: window._set_entity_choice(eid, "automation_group", w.currentText().strip()))
    combo.activated.connect(lambda _i, w=combo: window._set_entity_choice(eid, "automation_group", w.currentText().strip()))
    return combo


def _spin(window, eid, key, value, hi, step, decimals, suffix):
    """0 = not entered (shown as «— από το φύλλο»): no hidden catalogue default."""
    spin = QDoubleSpinBox(); spin.setRange(0.0, hi); spin.setDecimals(decimals); spin.setSingleStep(step)
    spin.setSuffix(suffix); spin.setSpecialValueText("— από το φύλλο"); spin.setValue(float(value or 0.0))
    spin.editingFinished.connect(lambda w=spin: (w.value() > 0 or key in window.doc.get(eid).params)
                                 and window._set_entity_choice(eid, key, float(w.value())))
    return spin


def add_rows(window, eid):
    """Rows for a luminaire, a switch or a dimmer; returns True when it added any."""
    from archforge.mep.electrical import SWITCH_TYPES, point_load_w, strip_length
    from archforge.mep.lighting import BEAM_PRESETS, PROVENANCE, is_luminaire, light_spec
    doc, form = window.doc, window.form
    entity = doc.get(eid)
    p = entity.params
    kind = p.get("point_type")
    if kind in SWITCH_TYPES:
        form.addRow("Ελέγχει ομάδα", _group_combo(window, eid, str(p.get("automation_group", ""))))
        return True
    if not is_luminaire(entity):
        return False
    from archforge.mep.luminaire_catalog import DIMMING, apply_values, entries_for, status_of
    catalog = QComboBox()
    catalog.addItem("— επιλέξτε από κατάλογο", None)
    for e in entries_for(kind):
        catalog.addItem(e.label, e.id)
    catalog.setCurrentIndex(max(0, catalog.findData(p.get("catalog_id")) if p.get("catalog_id") else 0))
    catalog.activated.connect(lambda _i, w=catalog: w.currentData() is not None and _apply_catalog(window, eid, w.currentData()))
    form.addRow("Από κατάλογο", catalog)
    _status, source_text = status_of(p)
    source = QLabel(source_text); source.setWordWrap(True)
    form.addRow("Προέλευση στοιχείων", source)
    dimming = QComboBox()
    dimming.addItem("On/Off (προεπιλογή — επιλογή του πελάτη)", None)
    for value, label in DIMMING.items():
        if value == "onoff":
            continue
        dimming.addItem(label, value)
    dimming.setCurrentIndex(max(0, dimming.findData(p.get("dimming")) if p.get("dimming") else 0))
    dimming.activated.connect(lambda _i, w=dimming: w.currentData() is not None
                              and window._set_entity_choice(eid, "dimming", w.currentData()))
    form.addRow("Ρύθμιση έντασης (τροφοδοτικό)", dimming)
    if kind == "led_strip":
        form.addRow("Μήκος ταινίας", QLabel(f"{strip_length(p):.2f} m".replace(".", ",")))
        form.addRow("Ισχύς ταινίας", _spin(window, eid, "w_per_m", p.get("w_per_m"), 100.0, 0.1, 1, " W/m"))
        form.addRow("Φωτεινή ροή", _spin(window, eid, "lumen", p.get("lumen"), 20000.0, 10.0, 0, " lm/m"))
    else:
        form.addRow("Ισχύς", _spin(window, eid, "power_w", p.get("power_w"), 5000.0, 1.0, 1, " W"))
        form.addRow("Φωτεινή ροή", _spin(window, eid, "lumen", p.get("lumen"), 200000.0, 10.0, 0, " lm"))
    if kind in ("spot", "downlight", "wall_washer", "led_strip"):
        beams = QComboBox(); beams.setEditable(True)
        beams.addItem("— από το φύλλο", None)
        for b in BEAM_PRESETS + ((float(p["beam_deg"]),) if "beam_deg" in p and float(p["beam_deg"]) not in BEAM_PRESETS else ()):
            beams.addItem(f"{b:g}°", float(b))
        beams.setCurrentIndex(max(0, beams.findData(float(p["beam_deg"])) if "beam_deg" in p else 0))
        beams.activated.connect(lambda _i, w=beams: w.currentData() is not None
                                and window._set_entity_choice(eid, "beam_deg", float(w.currentData())))
        beams.lineEdit().editingFinished.connect(lambda w=beams: _typed_beam(window, eid, w.currentText()))
        form.addRow("Δέσμη", beams)
    temps = QComboBox(); temps.setEditable(True)
    temps.addItem("— από το φύλλο", None)
    for k in KELVINS + ((float(p["kelvin"]),) if "kelvin" in p and float(p["kelvin"]) not in KELVINS else ()):
        temps.addItem(f"{k:g} K", float(k))
    temps.setCurrentIndex(max(0, temps.findData(float(p["kelvin"])) if "kelvin" in p else 0))
    temps.activated.connect(lambda _i, w=temps: w.currentData() is not None
                            and window._set_entity_choice(eid, "kelvin", float(w.currentData())))
    temps.lineEdit().editingFinished.connect(lambda w=temps: _typed_kelvin(window, eid, w.currentText()))
    form.addRow("Χρώμα φωτός", temps)
    on = QCheckBox("Αναμμένο (στο 3D / νύχτα)")
    on.setObjectName("lightOnChoice")
    on.setChecked(bool(int(p.get("light_on", 1))))
    on.toggled.connect(lambda checked: window._set_entity_choice(eid, "light_on", 1 if checked else 0))
    form.addRow("Φωτιστικό", on)
    dim = QSlider(); dim.setOrientation(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Orientation.Horizontal)
    dim.setRange(0, 100); dim.setValue(int(round(float(p.get("dim_level", 1.0)) * 100)))
    shown = QLabel(f"{dim.value()} %")
    dim.valueChanged.connect(lambda v, l=shown: l.setText(f"{v} %"))
    dim.sliderReleased.connect(lambda w=dim: window._set_entity_choice(eid, "dim_level", w.value() / 100.0))
    form.addRow("Ένταση (ροοστάτης)", dim)
    form.addRow("", shown)
    add_aim_rows(window, eid)
    form.addRow("Ομάδα αυτοματισμού", _group_combo(window, eid, str(p.get("automation_group", ""))))
    spec = light_spec(doc, entity)
    control = ("ροοστάτης" if spec["dimmer"] else "διακόπτης") if spec["switch"] else "⚠ χωρίς διακόπτη"
    text = f"{point_load_w(p):.0f} W · {spec['circuit'] or '⚠ χωρίς κύκλωμα (βάλτε πίνακα)'} · {control} · φως {spec['direction']}"
    if not spec["photometry_entered"]:
        text += " · ⚠ χωρίς φωτομετρικά: στο 3D με εμφάνιση οθόνης, όχι πραγματική"
    info = QLabel(f"{text}<br><i>{PROVENANCE}</i>"); info.setWordWrap(True)
    form.addRow("", info)
    return True


def _typed_beam(window, eid, text):
    try:
        value = float(str(text).replace("°", "").replace(",", ".").strip())
    except ValueError:
        return
    if 1.0 <= value <= 180.0:
        window._set_entity_choice(eid, "beam_deg", value)


def _apply_catalog(window, eid, entry_id):
    """All the entry's values in one UpdateEntity (one undo)."""
    from archforge.core.commands import UpdateEntity
    from archforge.mep.luminaire_catalog import apply_values
    window.stack.execute(UpdateEntity(eid, apply_values(entry_id)))
    window._redraw_views(all_views=True)
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window.refresh_inspector)


def _typed_kelvin(window, eid, text):
    try:
        value = float(str(text).replace("K", "").replace(",", ".").strip())
    except ValueError:
        return
    if 1000.0 <= value <= 10000.0:
        window._set_entity_choice(eid, "kelvin", value)


def _set_direction(window, eid, value):
    # «Αυτόματα» = 'auto': cove strips light upwards, the rest by type (mep/lighting.direction_of).
    window._set_entity_choice(eid, "direction", value or "auto")


def add_aim_rows(window, eid):
    """Aim of an adjustable head (σποτ, wall washer): tilt from the vertical and compass bearing, one undo each.

    A fixed fitting (downlight, plafonnier, απλίκα, ταινία) says so instead — its beam follows «Κατεύθυνση».
    """
    from archforge.mep.lighting import fixture_aimable
    entity = window.doc.get(eid)
    p = entity.params
    # Owner 25/10: «κατεύθυνση μόνο σε αυτά που έχουν τη δυνατότητα» — the dimmer is for all (above). A library model
    # turns only when its content says ``aimable`` (a spot cone alone does not).
    if not fixture_aimable(entity):
        window.form.addRow("Κατεύθυνση", QLabel("Σταθερή δέσμη — το φωτιστικό δεν στρέφεται"))
        return False
    if entity.kind == "electrical_point":
        direction = QComboBox()
        for value, label in DIRECTION_LABELS.items():
            direction.addItem(label, value)
        direction.setCurrentIndex(max(0, direction.findData(str(p.get("direction", "auto")))))
        direction.activated.connect(lambda _i, w=direction: _set_direction(window, eid, w.currentData()))
        window.form.addRow("Κατεύθυνση", direction)
    else:
        window.form.addRow("Κατεύθυνση", QLabel("Ρυθμιζόμενη κεφαλή — Κλίση και Προσανατολισμός"))
    tilt = QDoubleSpinBox(); tilt.setObjectName("aimTilt")
    tilt.setRange(0.0, 90.0); tilt.setDecimals(0); tilt.setSingleStep(5.0); tilt.setSuffix("°")
    tilt.setValue(float(p.get("aim_tilt_deg", 0.0)))
    tilt.setToolTip("0° = κατακόρυφα (κάτω, ή πάνω με «Προς τα πάνω») · 90° = οριζόντια")
    tilt.editingFinished.connect(lambda w=tilt: _set_aim(window, eid, "aim_tilt_deg", w.value()))
    window.form.addRow("Κλίση δέσμης", tilt)
    bearing = QDoubleSpinBox(); bearing.setObjectName("aimBearing")
    bearing.setRange(0.0, 359.0); bearing.setDecimals(0); bearing.setSingleStep(15.0); bearing.setSuffix("°")
    bearing.setWrapping(True)
    bearing.setValue(float(p.get("aim_azimuth_deg", 0.0)))
    bearing.setToolTip("Προς τα πού στην κάτοψη: 0° Βορράς (+y) · 90° Ανατολή (+x) · 180° Νότος · 270° Δύση")
    bearing.editingFinished.connect(lambda w=bearing: _set_aim(window, eid, "aim_azimuth_deg", w.value()))
    window.form.addRow("Προσανατολισμός", bearing)
    return True


def _set_aim(window, eid, key, value):
    """Tilt and bearing together (one UpdateEntity): the first change of either fixes the other at its shown value."""
    from archforge.core.commands import UpdateEntity
    p = window.doc.get(eid).params
    changes = {"aim_tilt_deg": float(p.get("aim_tilt_deg", 0.0)), "aim_azimuth_deg": float(p.get("aim_azimuth_deg", 0.0))}
    changes[key] = float(value)
    if all(k in p and float(p[k]) == v for k, v in changes.items()):
        return
    window.stack.execute(UpdateEntity(eid, changes))
    window._redraw_views(all_views=True)
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window.refresh_inspector)
