"""Αρχείο ▸ Εξαγωγή ▸ «IFC για μηχανικούς» / «DXF κατόψεις ανά όροφο» (the translator, archforge/exchange)."""
from __future__ import annotations

import os

from PySide6.QtGui import QAction


def _project_name(window):
    path = getattr(window, "current_path", None)
    return os.path.splitext(os.path.basename(path))[0] if path else "ArchForge"


def _ask(window, title, default, pattern):
    if getattr(window, "_no_modal_dialogs", False):
        return None
    from PySide6.QtWidgets import QFileDialog
    path, _ = QFileDialog.getSaveFileName(window, title, default, pattern)
    return path or None


def export_ifc(window, path=None):
    """The model as IFC4 — storeys, walls with their layers, openings with doors / windows, slabs, roofs, stairs,
    columns, beams, MEP, rooms with net area."""
    from archforge.exchange.ifc import export_ifc as write
    name = _project_name(window)
    path = path or _ask(window, "Εξαγωγή IFC (BIM)", f"{name}.ifc", "IFC (*.ifc)")
    if not path:
        return None
    if not path.lower().endswith(".ifc"):
        path += ".ifc"
    try:
        result = write(window.doc, path, name)
    except Exception as exc:                                            # noqa: BLE001 — told, nothing half-written kept
        window.statusBar().showMessage(f"IFC: δεν βγήκε — {exc}", 10000)
        return None
    c = result["counts"]
    window.statusBar().showMessage(
        f"IFC: {len(result['storeys'])} όροφοι · {c.get('IfcWall', 0)} τοίχοι · {c.get('IfcDoor', 0)} πόρτες · "
        f"{c.get('IfcWindow', 0)} παράθυρα · {len(result['spaces'])} χώροι — {path}", 12000)
    return result


def export_dxf(window, path=None):
    """The plan of each storey as DXF, in metres, layers A-WALL / A-DOOR / S-COLS …"""
    from archforge.exchange.dxf import export_dxf as write
    name = _project_name(window)
    path = path or _ask(window, "Εξαγωγή DXF (κατόψεις)", f"{name}.dxf", "DXF (*.dxf)")
    if not path:
        return None
    if not path.lower().endswith(".dxf"):
        path += ".dxf"
    try:
        result = write(window.doc, path, name)
    except Exception as exc:                                            # noqa: BLE001
        window.statusBar().showMessage(f"DXF: δεν βγήκε — {exc}", 10000)
        return None
    window.statusBar().showMessage(f"DXF: {len(result['files'])} αρχεία (ένα ανά όροφο) — "
                                   f"{os.path.dirname(result['files'][0]) or '.'}", 12000)
    return result


def actions(window):
    """The two menu commands (made once, kept on the window)."""
    if getattr(window, "_export_ifc_action", None) is None:
        ifc = QAction("IFC για μηχανικούς (BIM)…", window)
        ifc.setToolTip("Όλο το μοντέλο σε IFC4: όροφοι, τοίχοι με στρώσεις, κουφώματα στα ανοίγματά τους, πλάκες, "
                       "στέγες, σκάλες, φέρων, Η/Μ, χώροι με εμβαδόν — ανοίγει σε ArchiCAD, Revit, στατικά προγράμματα")
        ifc.triggered.connect(lambda _=False: export_ifc(window))
        dxf = QAction("DXF κατόψεις ανά όροφο…", window)
        dxf.setToolTip("Η κάτοψη κάθε ορόφου όπως τη βλέπεις, σε μέτρα, με layers A-WALL, A-DOOR, A-ANNO-DIMS, S-COLS …")
        dxf.triggered.connect(lambda _=False: export_dxf(window))
        window._export_ifc_action, window._export_dxf_action = ifc, dxf
    return [window._export_ifc_action, window._export_dxf_action]
