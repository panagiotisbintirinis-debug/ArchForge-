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
            except Exception as exc:
                # Α3: unknown is not «the whole object» — the material is not applied (``_choose_selected``).
                from archforge.core.notices import not_computed
                not_computed("materials.part", "Υλικό: δεν αναγνωρίστηκε το επιλεγμένο τμήμα", exc=exc)
                raise LookupError("δεν αναγνωρίστηκε το επιλεγμένο τμήμα") from exc
            if role:
                return role
    return None


def _choose_selected(dialog):
    try:
        role = _selected_role(dialog)
    except LookupError as exc:
        dialog.window.statusBar().showMessage(f"Υλικό: {exc} — δεν εφαρμόστηκε, επιλέξτε ξανά το τμήμα", 8000)
        return None
    return dialog.choose_material(role)


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
    except Exception as exc:
        label.setText(f"Υλικό: δεν διαβάστηκε ({exc})")     # never a plausible «default» that is not the case


def _sync_preview_from_part_list(dialog):
    """Selecting a row must visibly select the same semantic part in preview."""
    parts = getattr(dialog, "parts", None)
    preview = getattr(dialog, "preview", None)
    if parts is None or preview is None:
        return
    item = parts.currentItem()
    role = item.data(256) if item is not None else None  # Qt.ItemDataRole.UserRole
    preview.selected_role = role or None
    preview.update()
    if item is not None and hasattr(dialog, "part_label"):
        dialog.part_label.setText(f"Τμήμα: {item.text()}")
    _refresh_material_card(dialog)


def _ensure_part_list_sync(dialog):
    parts = getattr(dialog, "parts", None)
    if parts is None or getattr(parts, "_archforge_preview_sync", False):
        return
    parts.currentItemChanged.connect(lambda _cur, _prev, d=dialog: _sync_preview_from_part_list(d))
    parts._archforge_preview_sync = True


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
    selected.clicked.connect(lambda: _choose_selected(dialog))
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


def _install_textured_object_preview():
    """Make the lightweight object preview show material patterns as patterns.

    The authoritative 3D renderer already understands patterned materials.
    The small QPainter preview used to collapse every finish to a flat QColor,
    which made fabrics/wood/stone look destroyed after assignment.  This patch
    keeps that preview lightweight while tiling the same swatch generator used
    by the Material Library on each semantic part.
    """
    import math

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap, QPolygonF

    from archforge.ui import object_preview as op
    from archforge.rendering.materials import material_spec
    from archforge.ui.pattern_swatch import material_swatch

    if getattr(op.ObjectPreview, "_archforge_textured_material_preview", False):
        return

    def role_visuals(self, params, roles):
        overrides = params.get("surface_materials") or {}
        whole = params.get("material_id")
        palette = {}
        if self.kind == "library_object":
            from archforge.library.objects import asset_parts
            palette = {role: colour for role, colour, _name in asset_parts(params)}

        cache = {}
        out = []
        for role in roles:
            material_id = overrides.get(role) or whole
            fallback = QColor(palette.get(role) or op.ROLE_COLORS.get(role, "#c8c4bc"))
            if not material_id:
                out.append((fallback, None))
                continue

            spec = material_spec(material_id) or {}
            colour = QColor(str(spec.get("color", fallback.name())))
            if not spec.get("pattern"):
                out.append((colour, None))
                continue

            key = str(material_id)
            pixmap = cache.get(key)
            if pixmap is None:
                try:
                    image = material_swatch(key, 96, 96)
                    pixmap = QPixmap.fromImage(image)
                except Exception:
                    pixmap = QPixmap()
                cache[key] = pixmap
            out.append((colour, pixmap if not pixmap.isNull() else None))
        return out

    original_rebuild = op.ObjectPreview._rebuild

    def rebuild(self):
        original_rebuild(self)
        _verts, _tris, roles = self._mesh
        self._material_visuals = role_visuals(self, self._local_params(), roles)

    def paint_event(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(246, 246, 243))
        verts, tris, roles = self._mesh
        pts = [self.project(v) for v in verts]
        light = (0.35, -0.55, 0.76)
        faces = []
        for i, (a, b, c) in enumerate(tris):
            va, vb, vc = verts[a], verts[b], verts[c]
            ux, uy, uz = vb[0] - va[0], vb[1] - va[1], vb[2] - va[2]
            wx, wy, wz = vc[0] - va[0], vc[1] - va[1], vc[2] - va[2]
            nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
            length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nx, ny, nz = nx / length, ny / length, nz / length
            shade = 0.55 + 0.45 * abs(nx * light[0] + ny * light[1] + nz * light[2])
            depth = (pts[a][2] + pts[b][2] + pts[c][2]) / 3
            faces.append((depth, i, shade))
        faces.sort(reverse=True)

        visuals = getattr(self, "_material_visuals", None)
        if not visuals or len(visuals) != len(roles):
            visuals = role_visuals(self, self._local_params(), roles)
            self._material_visuals = visuals

        self._screen_tris = []
        for _depth, i, shade in faces:
            a, b, c = tris[i]
            poly = QPolygonF([
                QPointF(pts[a][0], pts[a][1]),
                QPointF(pts[b][0], pts[b][1]),
                QPointF(pts[c][0], pts[c][1]),
            ])
            base, texture = visuals[i] if i < len(visuals) else (QColor(200, 200, 200), None)
            chosen = self.selected_role is not None and roles[i] == self.selected_role

            edge = QColor(240, 130, 20, 235) if chosen else QColor(
                int(base.red() * shade), int(base.green() * shade), int(base.blue() * shade)
            )
            painter.setPen(QPen(edge, 2.8 if chosen else 0.6))
            painter.setBrush(QBrush(texture) if texture is not None else QBrush(base))
            painter.drawPolygon(poly)

            # Preserve simple directional lighting without replacing the finish.
            darkness = max(0, min(115, int((1.0 - shade) * 150)))
            if darkness:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(0, 0, 0, darkness)))
                painter.drawPolygon(poly)

            # Strong selection feedback: keep the real finish visible under a
            # translucent orange wash and a thick outline.
            if chosen:
                painter.setPen(QPen(QColor(255, 133, 20, 245), 2.8))
                painter.setBrush(QBrush(QColor(255, 145, 20, 52)))
                painter.drawPolygon(poly)
            self._screen_tris.append((poly, roles[i]))

        self._screen_tris.reverse()
        sizes = self.sizes()
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        self._handles = {}
        for key, ((hx, hy), (dx, dy)) in self.handle_points().items():
            length = math.hypot(dx, dy) or 1.0
            ex, ey = hx + dx / length * 26, hy + dy / length * 26
            pen = QPen(op.HANDLE_COLORS[key], 2.2)
            painter.setPen(pen)
            painter.drawLine(QPointF(hx, hy), QPointF(ex, ey))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            radius = 8 if self._drag_handle != key else 10
            painter.drawEllipse(QPointF(ex, ey), radius, radius)
            painter.drawText(QPointF(ex - 4, ey + 4), op.HANDLE_NAMES[key])
            text = f"{sizes[key] * 100:.0f} cm"
            box = painter.fontMetrics().boundingRect(text).adjusted(-3, -2, 3, 2).translated(int(ex + 12), int(ey + 4))
            painter.fillRect(box, QColor(255, 255, 255, 220))
            painter.drawText(QPointF(ex + 12, ey + 4), text)
            self._handles[key] = (ex, ey)

        painter.setPen(QPen(QColor(90, 90, 90)))
        font.setBold(False)
        painter.setFont(font)
        hint = "Σύρε λαβή Π/Β/Υ = μέγεθος · σύρε στο κενό = περιστροφή θέας · κλικ σε τμήμα = υλικό"
        if self.lock:
            hint = "🔒 αναλογίες κλειδωμένες · " + hint
        painter.drawText(
            self.rect().adjusted(8, 0, -8, -6),
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
            hint,
        )
        painter.end()

    op.ObjectPreview._rebuild = rebuild
    op.ObjectPreview.paintEvent = paint_event
    op.ObjectPreview._archforge_textured_material_preview = True


def install_material_object_integration():
    """Install the object/material UI bridge once per process."""
    from archforge.ui import material_library as ml
    from archforge.ui import object_modifier as om

    if getattr(ml, "_object_material_integration_installed", False):
        return

    old_targets = ml._targets

    def targets(entity, doc=None):                      # the browser passes the document too (owner's fix 28/10)
        out = list(old_targets(entity, doc))
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
            except Exception as exc:
                from archforge.core.notices import not_computed
                not_computed("materials.parts", f"«{entity.name or entity.id}»: τα τμήματα δεν φορτώθηκαν, μόνο «Όλο το "
                             "αντικείμενο» διαθέσιμο", entity.id, exc)
        return tuple(out)

    ml._targets = targets
    om.visual_column = _compact_visual_column
    _install_textured_object_preview()

    # Keep the compact material card and the 3D highlight in sync after normal
    # refreshes, list selection and direct picking in the preview.
    for cls_name in ("ObjectModifierDialog", "CabinetModifierDialog"):
        cls = getattr(om, cls_name, None)
        if cls is None:
            continue

        original_refresh = cls.refresh
        def refresh(self, _orig=original_refresh):
            result = _orig(self)
            _ensure_part_list_sync(self)
            _sync_preview_from_part_list(self)
            _refresh_material_card(self)
            return result
        cls.refresh = refresh

        original_pick = cls.pick_part
        def pick_part(self, role, _orig=original_pick):
            result = _orig(self, role)
            _ensure_part_list_sync(self)
            _refresh_material_card(self)
            if getattr(self, "preview", None) is not None:
                self.preview.selected_role = role
                self.preview.update()
            return result
        cls.pick_part = pick_part

    ml._object_material_integration_installed = True
