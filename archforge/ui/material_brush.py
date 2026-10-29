"""«Πινέλο» υλικού (owner 28/10): one material, many clicks.

The button opens the Material Library to choose (or edit) a material; then every click on a wall or object in the
plan paints it — one undo per click, on a wall only the face that was clicked — until Esc.  Each click goes through
``material_library._apply_material``, the same command the browser's «Εφαρμογή υλικού» runs: no second material path.
"""
from __future__ import annotations

TOOL = 'paint_material'


def wall_side_role(wall, x, y):
    """The wall face on the clicked half: ``'exterior'`` = side A (left of x1→x2), ``'interior'`` = side B.

    These are the same keys as the browser's «Πλευρά A / B» (``material_library._targets``), whichever of them looks
    outside (``wall_face.side_roles``)."""
    p = wall.params
    x1, y1, x2, y2 = (float(p[k]) for k in ('x1', 'y1', 'x2', 'y2'))
    ax, ay = -(y2 - y1), x2 - x1                     # side A's direction, as wall_face.outside_signs
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    return 'exterior' if (x - mx) * ax + (y - my) * ay >= 0 else 'interior'


def start(window, material_id=None):
    """Choose the material in the Library (or take ``material_id``), then the plan paints on click. False = cancelled."""
    if material_id is None:
        from PySide6.QtWidgets import QDialog
        from archforge.ui.material_library import MaterialLibraryDialog
        dialog = MaterialLibraryDialog(window, None, brush=True)
        window._material_library_dialog = dialog           # reachable from tests
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_material_id:
            return False
        material_id = dialog.selected_material_id
    window._brush_material_id = str(material_id)
    window._start_site_tool(TOOL, f"Πινέλο «{_name(window, material_id)}»: κλικ σε τοίχο (η πλευρά που πατάς) ή "
                                  "αντικείμενο — Esc για τέλος")
    return True


def paint(window, entity_id, x, y):
    """Paint what was clicked with the brush's material — one undo. Returns the role painted ('' = whole) or None."""
    from archforge.ui.material_library import MATERIAL_KINDS, _apply_material
    material_id = getattr(window, '_brush_material_id', None)
    if not material_id:
        window.statusBar().showMessage('Πινέλο: δεν έχει επιλεγεί υλικό — πατήστε ξανά «Πινέλο»', 5000)
        return None
    if not entity_id or entity_id not in window.doc.entities:
        window.statusBar().showMessage('Πινέλο: κλικ πάνω σε τοίχο ή αντικείμενο — Esc για τέλος', 4000)
        return None
    entity = window.doc.get(entity_id)
    if entity.kind not in MATERIAL_KINDS:
        window.statusBar().showMessage(f'Πινέλο: δεν υπάρχουν ακόμη υλικά για {entity.kind}', 4000)
        return None
    if entity.locked:
        window.statusBar().showMessage(f'Πινέλο: «{entity.name or entity.kind}» είναι κλειδωμένο', 4000)
        return None
    role = wall_side_role(entity, x, y) if entity.kind == 'wall' else ''
    _apply_material(window, entity_id, role, material_id)
    where = ''
    if role:
        from archforge.ui.material_library import _targets
        where = ' · ' + next((t.label for t in _targets(entity, window.doc) if t.key == role), role)
    window.statusBar().showMessage(f"Πινέλο «{_name(window, material_id)}» → {entity.name or entity.kind}{where} — "
                                   'Ctrl+Z για αναίρεση, Esc για τέλος', 5000)
    return role


def _name(window, material_id):
    from archforge.rendering.materials import material_spec
    spec = material_spec(material_id, window.doc) or {}
    return str(spec.get('name', material_id))
