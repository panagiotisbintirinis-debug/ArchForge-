"""Κατασκευή ▸ Ολοκλήρωση κτιρίου… (owner 18/10, proposal step 1): the human draws walls and rooms; one command adds
what the building still lacks — floors, roof, kitchen and baths where a room is named so, light / switch / sockets in
every room, the electrical board, heating emitters and supplies, the load-bearing frame.

Every part runs through the same window commands as its own menu entry (the scenario builder's path), shows first
what it will do (each part can be unticked), skips what is already there, and the whole run is ONE undo step.
"""
from __future__ import annotations

from archforge.geometry.regions import point_in_polygon

# F10: a part that added nothing says so — never «✓» for nothing.
SKIPPED = "παραλείφθηκε"
KITCHEN_WORDS = ("κουζ", "kitchen")
BATH_WORDS = ("μπάνιο", "λουτρ", "wc", "bath", "ντους")


def _faces(window):
    from archforge.architecture.roof_need import OPEN_AIR_USES
    doc = window.doc
    return [f for f in doc.active_room_faces() if doc.room_metadata(f.signature).get("use") not in OPEN_AIR_USES]


def _use(window, face):
    meta = window.doc.room_metadata(face.signature)
    return str(meta.get("use") or meta.get("name") or "").lower()


def _z(window):
    return float(window.doc.work_plane.origin[2])


def _inside(window, face, kinds, z):
    return [e for e in window.doc.entities.values() if e.kind in kinds and "x" in e.params
            and abs(float(e.params.get("z", z)) - z) < 2.6
            and point_in_polygon(float(e.params["x"]), float(e.params["y"]), face.polygon)]


def _storeys(window):
    return sorted(window.doc.levels.items(), key=lambda kv: float(kv[1]))


def _each_storey(window, fn):
    """Run ``fn`` on every storey that has walls; the active storey comes back at the end."""
    doc = window.doc
    back = doc.active_level_name()
    out = []
    zs = {round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall"}
    for name, z in _storeys(window):
        if round(float(z), 4) not in zs:
            continue
        window._activate_level_by_name(name)
        out.append(fn(name, float(z)))
    if back:
        window._activate_level_by_name(back)
    return out


# ----------------------------------------------------------------------------------------------------------- parts
def _need_floors(window):
    doc = window.doc
    zs = {round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall"}
    have = {round(float(e.params.get("level_z", 1e9)), 4) for e in doc.entities.values()
            if e.kind == "room_floor" and e.params.get("scope") == "storey"}
    return sorted(zs - have)


def floors(window, options):
    def run(name, z):
        if round(z, 4) in _need_floors(window) and window.doc.active_room_faces():
            return name if window._create_auto_floors() is not None else None
    done = [n for n in _each_storey(window, run) if n]
    return f"δάπεδα: {', '.join(done)}" if done else None


def has_roof(window):
    """The TOP storey (highest one with walls) is covered — a canopy or a roof on another storey does not count (F09)."""
    doc = window.doc
    walls = [e for e in doc.entities.values() if e.kind == "wall"]
    if not walls:
        return False
    top = max(float(e.params.get("z", 0.0)) for e in walls)
    wall_top = max(float(e.params.get("z", 0.0)) + float(e.params.get("height", 0.0)) for e in walls
                   if abs(float(e.params.get("z", 0.0)) - top) < 0.05)
    for e in doc.entities.values():
        if e.kind == "room_roof" and abs(float(e.params.get("level_z", -1e9)) - top) < 0.05:
            return True
        if e.kind == "pitched_roof" and float(e.params.get("eave_z", -1e9)) >= wall_top - 0.30:
            return True
    return False


def roof(window, options):
    form = options.get("roof", "gable")
    if form == "flat":
        return "δώμα" if window._auto_roofs() else None
    return "κεραμοσκεπή" if window._create_pitched_roof(form) else None


def kitchens_and_baths(window, options):
    from archforge.ui.layout_assist import run as layout_run

    def run(name, z):
        made = []
        for face in _faces(window):
            use = _use(window, face)
            kind = "kitchen" if any(w in use for w in KITCHEN_WORDS) else "bath" if any(w in use for w in BATH_WORDS) else None
            # F03: what is already in the room stays and the planner works around it (room_layout.obstacles); only a
            # room that already HAS its kitchen (a sink) / bath (a WC) is left alone.
            if kind is None or _has_layout(window, face, kind, z):
                continue
            cx = sum(p[0] for p in face.polygon) / len(face.polygon)
            cy = sum(p[1] for p in face.polygon) / len(face.polygon)
            layout_run(window, kind, None, (cx, cy))
            p = window._layout_assist.proposal
            if p is not None and p.entities:
                layout_run(window, "apply")
                made.append("κουζίνα" if kind == "kitchen" else "μπάνιο")
            else:
                window._layout_assist.cancel()
        return made
    made = [m for ms in _each_storey(window, run) for m in ms]
    return ", ".join(made) or None


def _has_layout(window, face, kind, z):
    """A kitchen has its sink, a bath its WC (cabinet / fixture role or the plumbing point)."""
    role, point = ("sink", "kitchen_sink") if kind == "kitchen" else ("wc", "wc")
    return any(e.params.get("layout_role") == role or (e.kind == "plumbing_point" and e.params.get("point_type") == point)
               for e in _inside(window, face, ("cabinet", "library_object", "plumbing_point"), z))


# F02: per room, each role on its own — the human's socket does not stop the light and the switch.
POINT_ROLES = {"elec_light": "lighting", "elec_switch": "switch", "elec_socket": "sockets"}


def _role_of(point_type):
    from archforge.mep.electrical import POINT_TYPES
    group = POINT_TYPES.get(point_type, ("", ""))[1]
    return {"kitchen_sockets": "sockets"}.get(group, group)


def room_points(window, options):
    from archforge.scenarios.builder import _room_points

    def run(name, z):
        n = 0
        for face in _faces(window):
            have = {_role_of(e.params.get("point_type")) for e in _inside(window, face, ("electrical_point",), z)}
            for tool, (x, y) in _room_points(window.doc, face, z):
                if POINT_ROLES.get(tool) in have:
                    continue                               # the human placed this role in this room already
                window._place_site_point(tool, float(x), float(y))
                n += 1
        return n
    n = sum(_each_storey(window, run))
    return f"{n} ηλεκτρολογικά σημεία" if n else None


def has_panel(window):
    return any(e.kind == "electrical_point" and e.params.get("point_type") == "panel" for e in window.doc.entities.values())


def panel(window, options):
    """The board on the ground storey, on the longest wall of the largest room, 60 cm from its corner."""
    import math
    from archforge.quantities.takeoff import net_polygon
    storeys = _storeys(window)
    ground = next((n for n, z in storeys if abs(float(z)) < 1e-6), storeys[0][0] if storeys else None)
    if ground is None:
        return None
    window._activate_level_by_name(ground)
    z = _z(window)
    faces = _faces(window)
    if not faces:
        return None
    face = max(faces, key=lambda f: abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2)
                                            in zip(f.polygon, f.polygon[1:] + f.polygon[:1]))))
    net = net_polygon(window.doc, face.polygon, z)
    i = max(range(len(net)), key=lambda k: math.dist(net[k], net[(k + 1) % len(net)]))
    a, b = net[i], net[(i + 1) % len(net)]
    L = math.dist(a, b) or 1.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    for sgn in (1, -1):
        q = (a[0] + ux * 0.6 - uy * 0.12 * sgn, a[1] + uy * 0.6 + ux * 0.12 * sgn)
        if point_in_polygon(q[0], q[1], net):
            window._place_site_point("elec_panel", q[0], q[1])
            return "ηλεκτρολογικός πίνακας"
    return None


def heating_source(window):
    return next((e for e in window.doc.entities.values() if e.kind == "heating_point"
                 and e.params.get("point_type") in ("boiler", "heat_source", "heat_pump")), None)


def heating(window, options):
    emitters = sum(_each_storey(window, lambda name, z: window._auto_heating_emitters("radiator") or 0))
    supplies = window._heating_supplies() or 0
    return f"{emitters} σώματα · {supplies} παροχές" if emitters or supplies else None


def structure(window, options):
    out = window._design_structure()
    res = out.get("result") or {}
    if res.get("error"):
        raise ValueError(res["error"])
    from archforge.structure.design_all import summary
    return summary(out)


REBUILT = ("pitched_roof", "structural_column", "structural_beam", "structural_support")


def has_rebuildable(window):
    return any(e.kind in REBUILT for e in window.doc.entities.values())


def rebuild(window, options):
    """After changes to the walls: the old roof and frame go, so the roof and frame parts are made again."""
    from archforge.core.commands import DeleteEntities
    ids = [e.id for e in window.doc.entities.values() if e.kind in REBUILT]
    if ids:
        window.stack.execute(DeleteEntities(ids))
    return f"σβήστηκαν {len(ids)} στοιχεία στέγης / φέροντα" if ids else None


def plan(window):
    """[(key, label, ticked, why-not-or-None, run)] — what «Ολοκλήρωση» would do in this project now."""
    doc = window.doc
    walls = any(e.kind == "wall" for e in doc.entities.values())
    named = any(any(w in str(m.get("use") or m.get("name") or "").lower() for w in KITCHEN_WORDS + BATH_WORDS)
                for m in getattr(doc, "room_data", {}).values() if isinstance(m, dict))
    no_walls = None if walls else "σχεδίασε πρώτα τοίχους / δωμάτια"
    return [
        ("rebuild", "Ενημέρωση μετά από αλλαγές: στέγη και φέρων ξανά από την αρχή", False,
         no_walls or (None if has_rebuildable(window) else "δεν υπάρχουν ακόμα"), rebuild),
        ("floors", "Δάπεδα σε κάθε όροφο", True, no_walls or (None if _need_floors(window) else "υπάρχουν ήδη"), floors),
        ("roof", "Στέγη στον τελευταίο όροφο", True, no_walls or ("υπάρχει ήδη" if has_roof(window) else None), roof),
        ("kitchen_bath", "Κουζίνα και μπάνια (όπου ο χώρος λέγεται έτσι)", True,
         no_walls or (None if named else "δώσε χρήση στους χώρους (δεξί κλικ ▸ Χρήση χώρου)"), kitchens_and_baths),
        ("room_points", "Φως, διακόπτης και πρίζες σε κάθε χώρο", True, no_walls, room_points),
        ("panel", "Ηλεκτρολογικός πίνακας", True, no_walls or ("υπάρχει ήδη" if has_panel(window) else None), panel),
        ("heating", "Θέρμανση: σώματα σε κάθε χώρο και παροχές", True,
         no_walls or (None if heating_source(window) is not None else "βάλε πρώτα λέβητα / αντλία θερμότητας"), heating),
        ("structure", "Φέρων οργανισμός: κολόνες, δοκοί, θεμελίωση", True, no_walls, structure),
    ]


def complete(window, keys=None, options=None):
    """Run the chosen parts (default: every part that applies) as one undo step; [(label, ok, note)]."""
    options = dict(options or {})
    if keys is not None and "rebuild" in keys:
        keys = list(keys) + ["roof", "structure"]     # what «Ενημέρωση» clears is made again
    report = []
    since = len(window.stack.done)
    back = window.doc.active_level_name()
    import copy
    # Layers are view state: the human asked for the whole building, so no environment's lock stops a part;
    # the environment (the frame's report brings «Φέρων» forward) and the locks come back as they were.
    view_layers = copy.deepcopy(getattr(window.doc, "view_layers", None))
    window.doc.view_layers = {}
    quiet = getattr(window, "_no_modal_dialogs", False)
    window._no_modal_dialogs = True
    try:
        done = set()
        while True:
            # Re-planned after every part: «Ενημέρωση» clears the roof and frame, which then apply again.
            step = next(((key, label, run) for key, label, ticked, why_not, run in plan(window)
                         if key not in done and not why_not
                         and (key in keys if keys is not None else ticked)), None)
            if step is None:
                break
            key, label, run = step
            done.add(key)
            try:
                note = run(window, options)
                report.append((label, True, note or f"{SKIPPED} — δεν έλειπε κάτι"))
            except Exception as exc:                     # noqa: BLE001 — shown to the human, never hidden
                report.append((label, False, f"{exc}"))
    finally:
        window._no_modal_dialogs = quiet
        if back and window.doc.active_level_name() != back:
            window._activate_level_by_name(back)
        window.doc.view_layers = view_layers
        from archforge.ui.layers_panel import refresh as refresh_layers
        refresh_layers(window)
        window.stack.squash(since, "Ολοκλήρωση κτιρίου")
        window._redraw_views(all_views=True)
        window.refresh_inspector()
    return report


def open_dialog(window):
    from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QLabel, QMessageBox,
                                   QVBoxLayout)
    dialog = QDialog(window)
    dialog.setWindowTitle("Ολοκλήρωση κτιρίου")
    box = QVBoxLayout(dialog)
    box.addWidget(QLabel("<b>Τι θα προστεθεί</b> (ό,τι υπάρχει ήδη μένει όπως είναι · όλο = μία αναίρεση):"))
    checks = {}
    roof_form = QComboBox(dialog)
    for value, text in (("gable", "Δίρριχτη κεραμοσκεπή"), ("hip", "Τετράριχτη κεραμοσκεπή"), ("flat", "Δώμα")):
        roof_form.addItem(text, value)
    for key, label, ticked, why_not, _run in plan(window):
        c = QCheckBox(label + (f"  — {why_not}" if why_not else ""), dialog)
        c.setChecked(ticked and not why_not)
        c.setEnabled(not why_not)
        box.addWidget(c)
        checks[key] = c
        if key == "roof":
            box.addWidget(roof_form)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    box.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    keys = [k for k, c in checks.items() if c.isChecked() and c.isEnabled()]
    report = complete(window, keys, {"roof": roof_form.currentData()})
    mark = lambda ok, note: ("–" if str(note).startswith(SKIPPED) else "✓") if ok else "✗"
    text = "\n".join(f"{mark(ok, note)} {label}: {note}" for label, ok, note in report) or "Τίποτα να προστεθεί."
    QMessageBox.information(window, "Ολοκλήρωση κτιρίου", text + "\n\nCtrl+Z = αναίρεση όλων.")
    window.statusBar().showMessage("Ολοκλήρωση κτιρίου: " + " · ".join(l for l, ok, n in report
                                                                      if ok and not str(n).startswith(SKIPPED)), 10000)
    return report
