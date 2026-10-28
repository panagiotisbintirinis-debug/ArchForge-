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
        add_switch_info_rows(window, eid)
        return True
    if not is_luminaire(entity):
        return False
    if p.get('fixture_asset'):
        from archforge.mep.fixture_models import model_record
        model = model_record(entity)
        label = QLabel(model['name'] if model else 'Το 3D σώμα λείπει από τη βιβλιοθήκη αυτού του υπολογιστή')
        label.setWordWrap(True)
        form.addRow('3D σώμα', label)
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
    from archforge.ui.fixture_controls import bind_control
    bind_control(window, eid, dim, shown, "dim_level", lambda v:v/100.0,
                 lambda v:window._set_entity_choice(eid,"dim_level",v))
    form.addRow("Ένταση (ροοστάτης)", dim)
    form.addRow("", shown)
    add_aim_rows(window, eid)
    form.addRow("Ομάδα αυτοματισμού", _group_combo(window, eid, str(p.get("automation_group", ""))))
    add_switch_rows(window, eid)
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
        window.statusBar().showMessage(f"Γωνία δέσμης: «{text}» δεν είναι αριθμός — δεν άλλαξε", 6000)
        return
    if not 1.0 <= value <= 180.0:
        window.statusBar().showMessage(f"Γωνία δέσμης: {value:g}° εκτός ορίων 1–180° — δεν άλλαξε", 6000)
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
        window.statusBar().showMessage(f"Θερμοκρασία χρώματος: «{text}» δεν είναι αριθμός — δεν άλλαξε", 6000)
        return
    if not 1000.0 <= value <= 10000.0:
        window.statusBar().showMessage(f"Θερμοκρασία χρώματος: {value:g} K εκτός ορίων 1000–10000 K — δεν άλλαξε", 6000)
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
        window.form.addRow("Κατεύθυνση", QLabel(fixed_direction_text(window.doc, entity)))
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
    from archforge.ui.fixture_controls import add_aim_rotors
    add_aim_rotors(window, eid)
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


# -- switches of a luminaire (owner 25/10: «δεύτερο διακόπτη απλό ή dimmable ή τρίτο, συνδεδεμένο με συγκεκριμένο
# φωτιστικό μέσα από τις Ιδιότητες· οι συνδέσεις στο ηλεκτρολογικό να ακολουθούν, εκτός αν έχουμε KNX») ----------
def _switch_name(window, sid):
    from archforge.mep.electrical import POINT_TYPES, _floor_of, _room_of
    sw = window.doc.get(sid)
    p = sw.params
    room = _room_of(window.doc, float(p["x"]), float(p["y"]), _floor_of(window.doc, float(p["z"]))) or "εκτός χώρου"
    return f"{POINT_TYPES[p['point_type']][0]} · {room}"


def add_switch_rows(window, eid):
    """«Διακόπτες»: who switches this luminaire (and how), unlink, and «Προσθήκη διακόπτη» by a click in the plan."""
    from PySide6.QtWidgets import QHBoxLayout, QMenu, QPushButton, QToolButton, QWidget
    from archforge.mep.electrical import SCHEMES, switches_of
    from archforge.mep.knx import control_system
    knx = control_system(window.doc) == "knx"
    links = switches_of(window.doc, eid)
    if not links:
        window.form.addRow("Διακόπτες", QLabel("⚠ κανένας — προσθέστε διακόπτη"))
    for link in links:
        row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(0, 0, 0, 0)
        scheme = "μπουτόν KNX" if knx else SCHEMES[link.get("scheme", "single")]
        lay.addWidget(QLabel(f"{_switch_name(window, link['switch'])} — {scheme}"), 1)
        off = QPushButton("Αποσύνδεση"); off.setObjectName("switchUnlink")
        off.clicked.connect(lambda _=False, s=link["switch"]: unlink_switch(window, eid, s))
        lay.addWidget(off)
        window.form.addRow("Διακόπτης", row)
    add = QToolButton(); add.setText("Προσθήκη διακόπτη…"); add.setObjectName("switchAdd")
    add.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    menu = QMenu(add)
    choices = []
    if links:
        choices += [("Απλός — άλλη θέση του ίδιου (αλέ-ρετούρ)", "switch", "same"),
                    ("Ροοστάτης — άλλη θέση του ίδιου (αλέ-ρετούρ)", "dimmer", "same")]
    choices += [("Απλός — μόνο για αυτό το φωτιστικό", "switch", "own"),
                ("Ροοστάτης — μόνο για αυτό το φωτιστικό", "dimmer", "own")]
    for label, kind, mode in choices:
        a = menu.addAction(label)
        a.setData((kind, mode))
        a.triggered.connect(lambda _=False, k=kind, m=mode: start_linked_switch(window, eid, k, m))
    add.setMenu(menu)
    window._switch_add_menu = menu          # reachable from tests
    window.form.addRow("", add)


def start_linked_switch(window, eid, kind, mode):
    """Click in the plan places the switch already linked to this luminaire (one undo with the placement)."""
    label = "Ροοστάτης" if kind == "dimmer" else "Διακόπτης"
    window._start_site_tool(f"elec_{kind}", f"{label} για το επιλεγμένο φωτιστικό: κλικ στη θέση του (στον τοίχο) — Esc για ακύρωση")
    window._pending_switch_link = (eid, mode)


def finish_linked_switch(window, switch):
    """Called after a switch was placed: link it if «Προσθήκη διακόπτη» asked for it."""
    pending = getattr(window, "_pending_switch_link", None)
    window._pending_switch_link = None
    if pending is None:
        return False
    from archforge.core.commands import UpdateEntities
    from archforge.mep.electrical import link_switch_changes
    light_id, mode = pending
    if light_id not in window.doc.entities:
        return False
    window.stack.amend(UpdateEntities(link_switch_changes(window.doc, light_id, switch.id, mode)))
    window._set_active_tool("select")
    window.doc.select([light_id])
    window._redraw_views(all_views=True)
    window.refresh_inspector()
    return True


def unlink_switch(window, eid, sid):
    from archforge.core.commands import UpdateEntities
    from archforge.mep.electrical import unlink_switch_changes
    changes = unlink_switch_changes(window.doc, eid, sid)
    if changes:
        window.stack.execute(UpdateEntities(changes))
        window._redraw_views(all_views=True)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, window.refresh_inspector)


def add_switch_info_rows(window, sid):
    """On a switch: its switching scheme and luminaires; with KNX the data the owner enters (address, channels)."""
    from PySide6.QtWidgets import QLineEdit, QSpinBox
    from archforge.mep.electrical import POINT_TYPES, SCHEMES, route_cables_cached
    from archforge.mep.knx import control_system
    link = next((l for l in route_cables_cached(window.doc)["switch_links"] if l["switch"] == sid), None)
    p = window.doc.get(sid).params
    if control_system(window.doc) == "knx":
        window.form.addRow("Σύστημα", QLabel("KNX — μπουτόν στο bus (χωρίς αγωγούς 230 V μεταξύ διακοπτών)"))
        address = QLineEdit(str(p.get("knx_group_address", ""))); address.setObjectName("knxAddress")
        address.setPlaceholderText("π.χ. 1/0/1 — από τη μελέτη KNX")
        address.editingFinished.connect(lambda w=address: window._set_entity_choice(sid, "knx_group_address", w.text().strip()))
        window.form.addRow("Διεύθυνση ομάδας KNX", address)
        channels = QSpinBox(); channels.setObjectName("knxChannels"); channels.setRange(0, 16)
        channels.setSpecialValueText("— από τη μελέτη"); channels.setValue(int(p.get("knx_channels", 0)))
        channels.editingFinished.connect(lambda w=channels: window._set_entity_choice(sid, "knx_channels", w.value()))
        window.form.addRow("Κανάλια μπουτόν", channels)
    elif link is not None:
        text = SCHEMES[link.get("scheme", "single")]
        if link.get("scheme") != "single":
            text += f" · {len(link['partners'])} θέσεις · 2 ενδιάμεσοι αγωγοί μεταξύ τους"
        window.form.addRow("Σχήμα", QLabel(text))
    if link is not None:
        names = [window.doc.get(i).name or POINT_TYPES[window.doc.get(i).params["point_type"]][0] for i in link["lights"]]
        lights = QLabel(", ".join(names) if names else "⚠ κανένα φωτιστικό"); lights.setWordWrap(True)
        window.form.addRow("Ανάβει", lights)


FIXED_LIGHT = {"down": "φως προς τα κάτω", "up": "φως προς τα πάνω (έμμεσο)", "wall": "φως στον τοίχο",
               "both": "φως πάνω και κάτω"}


def fixed_direction_text(doc, entity):
    """What a fitting that does not turn does with its light (a strip: where its cove sends it)."""
    if entity.kind != "electrical_point":
        return "Σταθερό — η δέσμη του μοντέλου (δεν στρέφεται)"
    from archforge.mep.lighting import direction_of
    light = FIXED_LIGHT.get(direction_of(doc, entity), "")
    if entity.params.get("point_type") == "led_strip":
        return f"Ταινία — {light}, από τη θέση της (εσοχή / ψευδοροφή)"
    return f"Σταθερό — {light} (δεν στρέφεται)"
