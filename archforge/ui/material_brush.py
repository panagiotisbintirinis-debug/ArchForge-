"""«Πινέλο» υλικού (owner 28/10): one material, many clicks — in the 3D view first, in the plan too (owner 29/10:
«πρέπει να δουλεύει στο 3Δ περισσότερο»).

The button opens the Material Library to choose (or edit) a material; then every click paints what it hits — one
undo per click — until Esc.  In 3D the exact face clicked (a wall's side or top, a door leaf, a cabinet front, a stair
tread, a slab edge) gets the material; in the plan a wall gets the side on the clicked half, anything else all of it.
Each click goes through ``material_library._apply_material``, the same command the browser's «Εφαρμογή υλικού» runs:
no second material path.  It is not Sculpt: Sculpt changes the shape, the brush only the finish.
"""
from __future__ import annotations

TOOL = 'paint_material'

# Kinds whose 3D picture is split per face (rendering/scene.py reads surface_materials[face] for every face of them):
# a click on any of their faces paints only that face.
PER_FACE_KINDS = frozenset({'wall', 'floor', 'room_floor', 'room_roof', 'room_ceiling'})


def face_role(doc, entity, surface_role):
    """The surface key a 3D click on ``surface_role`` paints: that face when the object keeps a finish per face, else
    ``''`` (the whole object)."""
    from archforge.ui.material_library import _targets
    role = str(surface_role or '')
    if not role:
        return ''
    if entity.kind in PER_FACE_KINDS or role in {t.key for t in _targets(entity, doc)}:
        return role
    return ''


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
    # Both views paint, whichever the human is looking at (no jump to the plan).
    window.plan_view.controller.set_tool(TOOL)
    pbr = getattr(window, 'pbr_view', None)
    if pbr is not None:
        pbr.set_tool(TOOL)
    window.statusBar().showMessage(f"Πινέλο «{_name(window, material_id)}»: κλικ στην επιφάνεια που βάφεις (3D) ή "
                                   "σε τοίχο / αντικείμενο στην κάτοψη — Esc για τέλος", 8000)
    return True


def end(window, quiet=False):
    """Esc in either view (or another tool): both views leave the brush."""
    was = False
    if getattr(window, 'plan_view', None) is not None and window.plan_view.controller.tool == TOOL:
        window.plan_view.controller.set_tool('select'); was = True
    pbr = getattr(window, 'pbr_view', None)
    if pbr is not None and getattr(pbr, 'active_tool', None) == TOOL:
        pbr.set_tool('select'); was = True
    if was and not quiet:
        window.statusBar().showMessage('Πινέλο: τέλος', 3000)


def paint(window, entity_id, x, y):
    """Plan click: paint what was clicked — one undo. Returns the role painted ('' = whole) or None."""
    entity = _paintable(window, entity_id)
    if entity is None:
        return None
    return _paint(window, entity, wall_side_role(entity, x, y) if entity.kind == 'wall' else '')


def paint_surface(window, entity_id, surface_role):
    """3D click on the face ``surface_role`` of ``entity_id`` — one undo. Returns the role painted or None."""
    entity = _paintable(window, entity_id)
    if entity is None:
        return None
    return _paint(window, entity, face_role(window.doc, entity, surface_role))


def _paintable(window, entity_id):
    from archforge.ui.material_library import MATERIAL_KINDS
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
    return entity


def _paint(window, entity, role):
    from archforge.ui.material_library import _apply_material
    material_id = window._brush_material_id
    _apply_material(window, entity.id, role, material_id)
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
