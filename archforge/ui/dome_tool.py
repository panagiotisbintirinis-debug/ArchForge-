"""Κατασκευή ▸ Θόλοι Bio-Spectre: θόλος, θόλος επάνω, σύμπλεγμα — κλικ στην κάτοψη (organic/domes.py).

* «Θόλος…»: διάμετρος / βάθος / ύψος / κέλυφος, μετά κλικ στο κέντρο, στον ενεργό όροφο.
* «Θόλος επάνω (πάνω σε θόλους)…»: το δάπεδό του κάθεται στο κέλυφος των θόλων από κάτω.
* «Σύμπλεγμα Bio-Spectre»: κεντρικός θόλος 8 m + 3 περιφερειακοί + θόλος επάνω (Patent Brief).

Όπου δύο θόλοι τέμνονται τα κελύφη γίνονται ένα επίπεδο κοινό χώρισμα (organic_junction).
Κάθε τοποθέτηση = μία αναίρεση· όταν ένας θόλος μετακινηθεί / αλλάξει διαστάσεις / σβηστεί,
τα χωρίσματα ακολουθούν μέσα στο ίδιο βήμα αναίρεσης (``install``).
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout

from archforge.core.commands import AddEntities, CompositeCommand
from archforge.core.model import Entity
from archforge.organic import domes as D

TITLES = {"dome": "Θόλος", "upper": "Θόλος επάνω", "cluster": "Σύμπλεγμα Bio-Spectre"}
CLUSTER_NAMES = {"central_pod": "Κεντρικός θόλος (καθιστικό / κουζίνα)", "master_pod": "Θόλος κύριου υπνοδωματίου",
                 "studio_pod": "Θόλος στούντιο", "bath_pod": "Θόλος μπάνιου / ευεξίας", "upper_dome": "Θόλος επάνω (παρατηρητήριο)"}


def _ask_sizes(window, kind):
    """Diameter, depth, height, shell (m) — or None when cancelled."""
    dlg = QDialog(window); dlg.setWindowTitle(TITLES[kind])
    form = QFormLayout(dlg)
    boxes = {}
    for key, label, value, lo, hi, step, decimals in (
            ("diameter", "Διάμετρος (m)", D.DEFAULT_DIAMETER if kind == "dome" else 4.6, 1.0, 40.0, 0.1, 2),
            ("depth", "Βάθος (m) — ίδιο = κύκλος", D.DEFAULT_DIAMETER if kind == "dome" else 4.6, 1.0, 40.0, 0.1, 2),
            ("height", "Ύψος θόλου (m)", D.DEFAULT_HEIGHT, 1.0, 20.0, 0.1, 2),
            ("shell", "Κέλυφος (m)", D.SHELL, 0.005, 0.5, 0.001, 3)):
        b = QDoubleSpinBox(); b.setRange(lo, hi); b.setSingleStep(step); b.setDecimals(decimals); b.setValue(value)
        boxes[key] = b; form.addRow(label, b)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); form.addRow(buttons)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return {k: b.value() for k, b in boxes.items()}


def _ask_cluster(window):
    dlg = QDialog(window); dlg.setWindowTitle(TITLES["cluster"])
    form = QFormLayout(dlg)
    upper = QCheckBox("Με θόλο επάνω (παρατηρητήριο)"); upper.setChecked(True); form.addRow(upper)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); form.addRow(buttons)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return {"upper": upper.isChecked()}


def start(window, kind="dome", spec=None):
    """Ask the sizes (unless ``spec``), then the next plan click places it."""
    if spec is None:
        spec = _ask_cluster(window) if kind == "cluster" else _ask_sizes(window, kind)
        if spec is None:
            return None
    window._dome_spec = {"kind": kind, **spec}
    window._start_site_tool("dome_place", f"{TITLES[kind]}: κλικ στο κέντρο στην κάτοψη — Esc για τέλος")
    return window._dome_spec


def entities_at(doc, spec, x, y, level):
    """The pods ``spec`` makes at (x, y) on ``level`` (nothing added yet)."""
    from archforge.organic.bubble_cluster import cluster_specs
    kind = spec["kind"]
    if kind == "cluster":
        return [Entity("pod", p, name=name) for _k, name, p in
                cluster_specs(x, y, level, bool(spec.get("upper", True)), names=CLUSTER_NAMES)]
    base = D.resting_level(doc, x, y, level) if kind == "upper" else level
    n = 1 + sum(1 for e in doc.entities.values() if e.kind == "pod")
    return [Entity("pod", D.dome_params(x, y, base, spec["diameter"], spec["height"], spec.get("depth"),
                                        shell=spec.get("shell", D.SHELL)), name=f"{TITLES[kind]} {n}")]


def place(window, x, y, spec=None):
    """Click in the plan: the dome(s) and their flat shared partitions, one undo; the tool stays on."""
    spec = spec or getattr(window, "_dome_spec", None)
    if not spec:
        return []
    doc = window.doc
    level = float(doc.work_plane.origin[2])
    pods = entities_at(doc, spec, x, y, level)
    if spec["kind"] == "upper" and abs(pods[0].params["floor_level"] - level) < 1e-6:
        window.statusBar().showMessage("Θόλος επάνω: δεν υπάρχει θόλος κάτω από το σημείο — κλικ πάνω σε θόλο", 8000)
        return []
    before = {e.params.get("junction_key") for e in doc.entities.values()
              if e.kind == "organic_junction" and e.params.get("status") == "active"}
    window.stack.execute(CompositeCommand([AddEntities(pods), D.SyncOrganicJunctions()], TITLES[spec["kind"]]))
    joined = {e.params.get("junction_key") for e in doc.entities.values()
              if e.kind == "organic_junction" and e.params.get("status") == "active"} - before
    doc.select([p.id for p in pods])
    window._redraw_views(all_views=True)
    window._refresh_project_tree()
    top = pods[0].params
    msg = (f"{TITLES[spec['kind']]}: {len(pods)} θόλοι" if len(pods) > 1 else
           f"{pods[0].name}: Ø {top['diameter_x']:.2f} × {top['diameter_y']:.2f}, ύψος {top['height']:.2f} m, "
           f"δάπεδο {top['floor_level']:+.2f}").replace(".", ",")
    msg += f" · {len(joined)} επίπεδα κοινά χωρίσματα" if joined else ""
    window.statusBar().showMessage(msg + " — διαστάσεις στις Ιδιότητες · Ctrl+Z αναιρεί", 10000)
    return pods


def install(window):
    """After any edit (move, stretch, Ιδιότητες, delete) the partitions follow the domes, in the same undo step."""
    def follow():
        stack = window.stack
        if stack.undone or not stack.done or getattr(window, "_dome_following", False):
            return                                  # undo / redo restore their own consistent state
        if not any(e.kind in ("pod", "organic_junction") for e in window.doc.entities.values()):
            return
        if not D.junctions_out_of_date(window.doc):
            return
        window._dome_following = True
        try:
            stack.amend(D.SyncOrganicJunctions())
        finally:
            window._dome_following = False
    window.stack.listeners.append(follow)
    return follow


def actions(window):
    """The «Θόλοι Bio-Spectre» entries for Κατασκευή."""
    from PySide6.QtGui import QAction
    out = []
    for kind, text, tip in (("dome", "Θόλος… (κλικ στο κέντρο)", "Θόλος Bio-Spectre στον ενεργό όροφο"),
                            ("upper", "Θόλος επάνω (πάνω σε θόλους)…", "Το δάπεδό του κάθεται στο κέλυφος των θόλων από κάτω"),
                            ("cluster", "Σύμπλεγμα Bio-Spectre (κεντρικός + 3 + επάνω)…",
                             "Κεντρικός θόλος 8 m, υπνοδωμάτιο, στούντιο, μπάνιο και θόλος επάνω — επίπεδα κοινά χωρίσματα")):
        a = QAction(text, window); a.setToolTip(tip)
        a.triggered.connect(lambda _=False, k=kind: start(window, k))
        out.append(a)
    window._dome_actions = out
    return out
