"""Bridge the visual Material Library into placed-object editing.

This module intentionally patches only UI integration points.  It does not
introduce another material model: all assignments continue to use the existing
``material_id`` / ``surface_materials`` fields and the shared CommandStack.
"""
from __future__ import annotations


def _selected_role(dialog):
    role = getattr(getattr(dialog, "preview", None), "selected_role", None)
    if role:
        return role
    for name in ("_current_part", "_current_role"):
        fn = getattr(dialog, name, None)
        if callable(fn):
            try:
                role = fn()
            except Exception:
                role = None
            if role:
                return role
    return None


def _refresh_material_card(dialog):
    label = getattr(dialog, "material_current", None)
    if label is None or not hasattr(dialog, "entity"):
        return
    try:
        entity = dialog.entity
        role = _selected_role(dialog)
        overrides = entity.params.get("surface_materials") or {}
        material_id = (overrides.get(role) if role else None) or entity.params.get("material_id")
        from archforge.rendering.materials import material_spec
        spec = material_spec(material_id, dialog.window.doc) if material_id else None
        material_name = str(spec.get("name", material_id)) if spec else "Αρχικό υλικό αντικειμένου"
        if role:
            part_name = str(role)
            if entity.kind == "library_object":
                from archforge.library.objects import asset_parts
                for part_role, _colour, name in asset_parts(entity.params):
                    if part_role == role:
                        part_name = name or part_role
                        break
            label.setText(f"{part_name}:  {material_name}")
        else:
            label.setText(f"Όλο το αντικείμενο:  {material_name}")
    except Exception:
        label.setText("Υλικό: προεπιλογή αντικειμένου")


def _compact_visual_column(dialog):
    """Object preview + a clear, lazy entry point to the Material Library.

    The old always-loaded inline palette is deliberately removed.  The large
    browser is created only when the user asks for it, while the entry point
    remains obvious in the object editor.
    """
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout
    from archforge.ui.object_preview import ObjectPreview

    column = QVBoxLayout()
    dialog.preview = ObjectPreview(dialog)
    dialog.preview.sizeCommitted.connect(dialog.apply_sizes)
    dialog.preview.partPicked.connect(dialog.pick_part)
    column.addWidget(dialog.preview, 6)

    dialog.part_label = QLabel("Τμήμα: όλο το αντικείμενο — κλικ σε τμήμα της προεπισκόπησης")
    dialog.part_label.setWordWrap(True)
    column.addWidget(dialog.part_label)

    dialog.material_current = QLabel("Υλικό: προεπιλογή αντικειμένου")
    dialog.material_current.setWordWrap(True)
    dialog.material_current.setStyleSheet("font-weight:600; padding:6px 2px;")
    column.addWidget(dialog.material_current)

    row = QHBoxLayout()
    selected = QPushButton("Βιβλιοθήκη Υλικών…")
    selected.setToolTip("Άνοιγμα της οπτικής βιβλιοθήκης για το επιλεγμένο τμήμα")
    selected.clicked.connect(lambda: dialog.choose_material(_selected_role(dialog)))
    row.addWidget(selected, 2)

    whole = QPushButton("Όλο το αντικείμενο…")
    whole.setToolTip("Ρητή εφαρμογή υλικού σε όλο το αντικείμενο")
    whole.clicked.connect(lambda: dialog.choose_material(None))
    row.addWidget(whole, 1)
    column.addLayout(row)

    hint = QLabel("Η βιβλιοθήκη φορτώνεται μόνο όταν τη χρειάζεσαι. Η επιλογή τμήματος παραμένει ενεργή.")
    hint.setWordWrap(True)
    hint.setStyleSheet("color:#6f7780; font-size:11px;")
    column.addWidget(hint)
    return column


def install_material_object_integration():
    """Install the object/material UI bridge once per process."""
    from archforge.ui import material_library as ml
    from archforge.ui import object_modifier as om

    if getattr(ml, "_object_material_integration_installed", False):
        return

    old_targets = ml._targets

    def targets(entity):
        out = list(old_targets(entity))
        seen = {target.key for target in out}

        # Library assets know their material parts even before the user has
        # assigned an override.  Expose them now, so a request for fabric/legs
        # can never silently fall back to "whole object".
        if str(getattr(entity, "kind", "")) == "library_object":
            try:
                from archforge.library.objects import asset_parts
                for index, (role, _colour, name) in enumerate(asset_parts(entity.params), 1):
                    role = str(role)
                    if role and role not in seen:
                        label = str(name).strip() if name else f"Τμήμα {index}"
                        out.append(ml.SurfaceTarget(role, label))
                        seen.add(role)
            except Exception:
                pass
        return tuple(out)

    ml._targets = targets
    om.visual_column = _compact_visual_column

    # Keep the compact material card in sync after normal object refreshes and
    # after picking a semantic part in the preview.
    for cls_name in ("ObjectModifierDialog", "CabinetModifierDialog"):
        cls = getattr(om, cls_name, None)
        if cls is None:
            continue

        original_refresh = cls.refresh
        def refresh(self, _orig=original_refresh):
            result = _orig(self)
            _refresh_material_card(self)
            return result
        cls.refresh = refresh

        original_pick = cls.pick_part
        def pick_part(self, role, _orig=original_pick):
            result = _orig(self, role)
            _refresh_material_card(self)
            return result
        cls.pick_part = pick_part

    ml._object_material_integration_installed = True
