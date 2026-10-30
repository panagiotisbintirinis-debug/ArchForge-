"""Αρχείο ▸ Εξαγωγή ▸ «IFC για μηχανικούς» / «DXF κατόψεις ανά όροφο» and Αρχείο ▸ Εισαγωγή ▸ «IFC» (the translator,
archforge/exchange)."""
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


def import_ifc(window, path=None):
    """Storeys, walls with their build-up and the doors / windows in them from an IFC file — one undo step."""
    from archforge.exchange.ifc_import import import_ifc as read_into
    if path is None and not getattr(window, "_no_modal_dialogs", False):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(window, "Εισαγωγή IFC", "", "IFC (*.ifc)")
    if not path:
        return None
    try:
        result = read_into(window.doc, window.stack, path)
    except Exception as exc:                                            # noqa: BLE001 — told, nothing added
        window.statusBar().showMessage(f"IFC: δεν διαβάστηκε — {exc}", 10000)
        return None
    window._redraw_views(all_views=True)
    rest = ", ".join(f"{n} {cls[3:]}" for cls, n in sorted(result["not_imported"].items()))
    window.statusBar().showMessage(
        f"IFC: {result['walls']} τοίχοι · {result['openings']} κουφώματα · {result['storeys']} όροφοι"
        + (f" · {result['new_types']} νέες συνθέσεις" if result["new_types"] else "")
        + (f" — δεν εισήχθησαν: {rest}" if rest else "") + " · Ctrl+Z για αναίρεση", 15000)
    return result


def import_action(window):
    if getattr(window, "_import_ifc_action", None) is None:
        a = QAction("IFC (τοίχοι, κουφώματα, όροφοι)…", window)
        a.setToolTip("Από ArchiCAD, Revit ή άλλο πρόγραμμα: όροφοι, τοίχοι με τη σύνθεσή τους, πόρτες και παράθυρα "
                     "στα ανοίγματά τους — μία αναίρεση· ό,τι άλλο λέγεται, δεν χάνεται σιωπηλά")
        a.triggered.connect(lambda _=False: import_ifc(window))
        window._import_ifc_action = a
    return window._import_ifc_action


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
