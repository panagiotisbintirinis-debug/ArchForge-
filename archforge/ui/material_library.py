from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from archforge.core.commands import CompositeCommand, UpdateEntity
from archforge.rendering.materials import (
    USER_CATEGORY,
    material_spec,
    picker_categories,
    picker_materials,
)
from archforge.rendering import user_materials as um
from archforge.ui.pattern_swatch import material_swatch


# ---------------------------------------------------------------------------
# Surface targets

@dataclass(frozen=True)
class SurfaceTarget:
    key: str
    label: str


def _targets(entity, doc=None) -> tuple[SurfaceTarget, ...]:
    """Human-facing targets, backed by the existing material_id/surface_materials.

    This deliberately does not create a second material model.  It only exposes
    roles already understood by ArchForge, plus roles that are already present
    on the entity itself.
    """
    whole_label = "Όλος ο τοίχος" if entity.kind == "wall" else "Όλο το αντικείμενο"
    out: list[SurfaceTarget] = [SurfaceTarget("", whole_label)]
    known: dict[str, tuple[tuple[str, str], ...]] = {
        "wall": (("exterior", "Πλευρά A / εξωτερική"), ("interior", "Πλευρά B / εσωτερική")),
        "stair": (
            ("tread", "Πατήματα"), ("riser", "Ρίχτια"), ("landing", "Πλατύσκαλο"),
            ("slab", "Πλάκα / κάτω πλευρά"), ("stringer", "Λουκέτα"),
            ("edge", "Πλευρές"), ("bottom", "Κάτω πλευρά"),
        ),
        "cabinet": (
            ("front", "Πρόσοψη"), ("carcass", "Σώμα"), ("worktop", "Πάγκος"),
            ("handle", "Χερούλι"), ("plinth", "Μπάζα"),
        ),
        "door": (("frame", "Κάσα"), ("leaf", "Φύλλο"), ("handle", "Χερούλι"), ("glass", "Τζάμι")),
        "window": (("frame", "Πλαίσιο"), ("leaf", "Φύλλο"), ("handle", "Χερούλι"), ("glass", "Τζάμι"), ("sill", "Ποδιά")),
    }
    if entity.kind == "wall" and doc is not None and entity.id in doc.entities:
        # Owner 23/10 «μέσα / έξω είναι ανάποδα»: the face that really looks out is «εξωτερική», whichever way the
        # wall was drawn (wall_face.side_roles); a wall with rooms on both sides keeps sides A / B.
        from archforge.architecture.wall_face import side_roles
        roles = side_roles(doc, entity.id)
        if roles:
            known["wall"] = ((roles[0], "Εξωτερική πλευρά (προς τα έξω)"), (roles[1], "Εσωτερική πλευρά"))
        else:
            known["wall"] = (("exterior", "Πλευρά A"), ("interior", "Πλευρά B"))
    seen = {""}
    for key, label in known.get(str(entity.kind), ()): 
        if key not in seen:
            out.append(SurfaceTarget(key, label)); seen.add(key)
    surface_map = entity.params.get("surface_materials") or {}
    if isinstance(surface_map, dict):
        for key in surface_map:
            key = str(key)
            if key and key not in seen:
                out.append(SurfaceTarget(key, key.replace("_", " ").title())); seen.add(key)
    return tuple(out)


def _assigned_material(entity, role: str) -> str:
    if role:
        surface_map = entity.params.get("surface_materials") or {}
        if isinstance(surface_map, dict) and surface_map.get(role):
            return str(surface_map[role])
        if entity.kind == "stair":
            try:
                from archforge.architecture.stair_options import role_material_id
                return str(role_material_id(entity.params, role) or "")
            except Exception as exc:
                from archforge.core.notices import not_computed
                not_computed("materials.stair_part", f"Σκάλα: δεν διαβάστηκε το υλικό του τμήματος «{role}» — "
                             "φαίνεται το υλικό όλης της σκάλας", entity.id, exc)
    return str(entity.params.get("material_id", "") or "")


def _apply_material(main_window, entity_id: str, role: str, material_id: str) -> None:
    entity = main_window.doc.get(entity_id)
    changes = {}
    if role:
        surface_map = dict(entity.params.get("surface_materials") or {})
        surface_map[str(role)] = str(material_id)
        changes["surface_materials"] = surface_map
    else:
        changes["material_id"] = str(material_id)
        # Whole-object assignment must win over previous per-face finishes.
        # Otherwise a wall that was textured separately on both sides would
        # not visibly change when the user chooses «Όλος ο τοίχος».
        if entity.params.get("surface_materials"):
            changes["surface_materials"] = {}

    commands = []
    carry = um.carry_command(main_window.doc, material_id)
    if carry is not None:
        commands.append(carry)
    commands.append(UpdateEntity(entity_id, changes))
    command = commands[0] if len(commands) == 1 else CompositeCommand(commands, "Υλικό")
    main_window.stack.execute(command)
    main_window.doc.select([entity_id])
    main_window._redraw_views(all_views=True)
    main_window.refresh_inspector()


# ---------------------------------------------------------------------------
# Preview

class MaterialSphere(QWidget):
    """Fast Qt preview sphere using the same swatch generator as the library.

    It is intentionally a material preview, not a second renderer.  The actual
    3D object continues to be rendered by ArchForge's PBR scene.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.material_id = ""
        self.doc = None
        self.scale = 1.0
        self.rotation = 0.0
        self.brightness = 1.0
        self.roughness = None
        self.setMinimumSize(250, 250)

    def set_material(self, material_id, doc=None):
        self.material_id = str(material_id or "")
        self.doc = doc
        spec = material_spec(self.material_id, doc) or {}
        self.roughness = float(spec.get("roughness", 0.6))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#161d25"))
        side = min(self.width(), self.height()) - 34
        x = (self.width() - side) // 2
        y = (self.height() - side) // 2
        if not self.material_id:
            p.setPen(QColor("#82909f"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Επίλεξε υλικό")
            return
        image = material_swatch(self.material_id, max(96, int(side * self.scale)), max(96, int(side * self.scale)), doc=self.doc)
        pix = QPixmap.fromImage(image)
        p.save()
        p.setClipRegion(self._circle_region(x, y, side))
        p.translate(self.width() / 2, self.height() / 2)
        p.rotate(self.rotation)
        p.translate(-self.width() / 2, -self.height() / 2)
        p.drawPixmap(x, y, side, side, pix)
        # soft lighting overlay: highlight at upper left, darker lower/right edge
        # This is a qualitative Qt highlight, not a physically accurate PBR
        # preview. The 3D renderer receives the actual persisted roughness.
        rough = max(0.0, min(1.0, float(self.roughness if self.roughness is not None else 0.6)))
        grad = QRadialGradient(x + side * 0.32, y + side * 0.27, side * (0.28 + 0.5 * rough))
        grad.setColorAt(0.0, QColor(255, 255, 255, int((150 - 85 * rough) * self.brightness)))
        grad.setColorAt(0.58, QColor(255, 255, 255, 0))
        grad.setColorAt(1.0, QColor(0, 0, 0, 155))
        p.setBrush(grad); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(x, y, side, side)
        p.restore()
        p.setPen(QColor("#596675"))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(x, y, side, side)

    @staticmethod
    def _circle_region(x, y, side):
        from PySide6.QtGui import QRegion
        return QRegion(x, y, side, side, QRegion.RegionType.Ellipse)


# ---------------------------------------------------------------------------
# Browser dialog

class MaterialLibraryDialog(QDialog):
    def __init__(self, main_window, entity_id: str | None = None, part_role: str | None = None,
                 legacy_opener=None, initial_material_id: str | None = None):
        super().__init__(main_window)
        self.main_window = main_window
        self.entity_id = str(entity_id) if entity_id is not None else ""
        self.entity = main_window.doc.get(self.entity_id) if self.entity_id else None
        self.legacy_opener = legacy_opener
        self.selected_material_id = str(initial_material_id or "")
        self.setWindowTitle("ArchForge — Βιβλιοθήκη Υλικών")
        self.resize(1230, 870)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background:#10161d; color:#edf2f7; }
            QLabel,QCheckBox { color:#e0e9f3; }
            QFrame#panel { background:#18212b; border:1px solid #2b3845; border-radius:10px; }
            QLineEdit,QComboBox,QDoubleSpinBox,QListWidget {
                background:#0f151c; color:#edf2f7; border:1px solid #344553; border-radius:6px; padding:6px;
            }
            QPushButton,QToolButton { background:#253341; color:#eef4fa; border:1px solid #3b4c5d; border-radius:6px; padding:7px 10px; }
            QPushButton#apply { background:#1976d2; border:0; font-weight:700; }
            QPushButton#apply:disabled { background:#334150; color:#7d8a96; }
            QLabel#title { font-size:19px; font-weight:700; }
            QLabel#muted { color:#95a3b2; }
            QScrollArea { background:#10161d; border:0; }
            QWidget#materialRightContent, QWidget#materialPropertiesHost { background:#18212b; }
            QLabel#materialEmptyProperties { background:#18212b; color:#95a3b2; }
            QListWidget::item { border-radius:5px; padding:8px; }
            QListWidget::item:selected { background:#245f95; }
        """)

        root = QVBoxLayout(self)
        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Βιβλιοθήκη Υλικών"); title.setObjectName("title")
        subject = (self.entity.name or self.entity.kind.title()) if self.entity is not None else "Διαχείριση υλικών"
        subtitle = QLabel(f"{subject} · επίλεξε, προεπισκόπησε και εφάρμοσε")
        subtitle.setObjectName("muted")
        title_box.addWidget(title); title_box.addWidget(subtitle)
        head.addLayout(title_box); head.addStretch(1)
        self.advanced = QPushButton("Προχωρημένα / κωδικός προμηθευτή…")
        self.advanced.setVisible(callable(self.legacy_opener))
        self.advanced.clicked.connect(self._open_legacy)
        head.addWidget(self.advanced)
        root.addLayout(head)

        body = QHBoxLayout(); root.addLayout(body, 1)

        # The left column is now a real work area: categories above, full
        # material editor below. Editing never competes with the sphere.
        left = QFrame(); left.setObjectName("panel"); left.setMinimumWidth(345); left.setMaximumWidth(465)
        ll = QVBoxLayout(left); ll.addWidget(QLabel("ΚΑΤΗΓΟΡΙΕΣ"))
        self.categories = QListWidget(); self.categories.addItem("Όλα τα υλικά")
        for cat in picker_categories(self.main_window.doc): self.categories.addItem(str(cat))
        ll.addWidget(self.categories, 2)
        ll.addWidget(QLabel("ΕΠΕΞΕΡΓΑΣΙΑ ΥΛΙΚΟΥ · ΧΡΩΜΑ · ΜΟΤΙΒΟ · ΦΩΤΟΓΡΑΦΙΑ"))
        self.properties_scroll = QScrollArea(left)
        self.properties_scroll.setWidgetResizable(True)
        self.properties_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.properties_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.properties_scroll.setMinimumHeight(320)
        self.properties_host = QWidget(); self.properties_host.setObjectName("materialPropertiesHost")
        self.properties_layout = QVBoxLayout(self.properties_host)
        self.properties_layout.setContentsMargins(4, 4, 4, 4)
        self.properties_layout.setSpacing(0)
        self.properties_editor = None
        self._set_properties_editor(None)
        self.properties_scroll.setWidget(self.properties_host)
        ll.addWidget(self.properties_scroll, 5)
        self.save_properties_button = QPushButton("Αποθήκευση ιδιοτήτων")
        self.save_properties_button.setEnabled(False)
        ll.addWidget(self.save_properties_button)
        body.addWidget(left, 3)

        # Material grid ------------------------------------------------------
        center = QFrame(); center.setObjectName("panel")
        cl = QVBoxLayout(center)
        self.search = QLineEdit(); self.search.setPlaceholderText("Αναζήτηση υλικού, κατηγορίας ή κωδικού…")
        cl.addWidget(self.search)
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.setIconSize(QSize(112, 76))
        self.grid.setGridSize(QSize(150, 122))
        self.grid.setSpacing(4)
        cl.addWidget(self.grid, 1)
        body.addWidget(center, 4)

        # Preview / assignment ---------------------------------------------
        right = QFrame(); right.setObjectName("panel"); right.setMinimumWidth(330); right.setMaximumWidth(405)
        rl = QVBoxLayout(right)
        # Preview stays on the right, with application independent of editing.
        self.right_scroll = QScrollArea(right)
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_content = QWidget(); right_content.setObjectName("materialRightContent")
        detail = QVBoxLayout(right_content)
        detail.addWidget(QLabel("ΠΡΟΕΠΙΣΚΟΠΗΣΗ"))
        self.sphere = MaterialSphere(); self.sphere.doc = self.main_window.doc
        self.sphere.setMinimumSize(155, 155)
        self.sphere.setMaximumHeight(190)
        detail.addWidget(self.sphere)
        self.preview_name = QLabel("Επίλεξε υλικό"); self.preview_name.setObjectName("title")
        self.preview_info = QLabel(""); self.preview_info.setObjectName("muted"); self.preview_info.setWordWrap(True)
        detail.addWidget(self.preview_name); detail.addWidget(self.preview_info)

        detail.addWidget(QLabel("Εφαρμογή σε"))
        self.target = QComboBox()
        targets = _targets(self.entity, getattr(self.main_window, 'doc', None)) if self.entity is not None else ()
        for target in targets: self.target.addItem(target.label, target.key)
        if self.entity is None:
            self.target.addItem("Επιλέξτε πρώτα αντικείμενο", "")
            self.target.setEnabled(False)
        if part_role:
            idx = self.target.findData(str(part_role))
            if idx >= 0: self.target.setCurrentIndex(idx)
        detail.addWidget(self.target)
        self.current = QLabel(""); self.current.setObjectName("muted"); self.current.setWordWrap(True)
        detail.addWidget(self.current)

        # Appearance controls are useful already for preview and define the
        # intended interaction. Renderer-side persistence can evolve without
        # changing the library workflow.
        detail.addWidget(QLabel("Κλίμακα προεπισκόπησης"))
        self.scale = QSlider(Qt.Orientation.Horizontal); self.scale.setRange(40, 220); self.scale.setValue(100)
        detail.addWidget(self.scale)
        detail.addWidget(QLabel("Περιστροφή"))
        self.rotation = QSlider(Qt.Orientation.Horizontal); self.rotation.setRange(0, 359); self.rotation.setValue(0)
        detail.addWidget(self.rotation)
        detail.addWidget(QLabel("Φωτεινότητα προεπισκόπησης"))
        self.brightness = QSlider(Qt.Orientation.Horizontal); self.brightness.setRange(50, 150); self.brightness.setValue(100)
        detail.addWidget(self.brightness)

        rough_row = QHBoxLayout(); rough_row.addWidget(QLabel("Τραχύτητα"))
        self.roughness = QDoubleSpinBox(); self.roughness.setRange(0.0, 1.0); self.roughness.setSingleStep(0.05); self.roughness.setDecimals(2)
        self.roughness.setEnabled(False)
        self.roughness.setToolTip("Επεξεργασία τραχύτητας — αποθηκεύεται μαζί με τις υπόλοιπες ιδιότητες του υλικού.")
        rough_row.addWidget(self.roughness); detail.addLayout(rough_row)

        detail.addStretch(1)
        self.right_scroll.setWidget(right_content)
        rl.addWidget(self.right_scroll, 1)

        self.apply = QPushButton("Εφαρμογή υλικού"); self.apply.setObjectName("apply"); self.apply.setEnabled(False)
        rl.addWidget(self.apply)
        close = QPushButton("Κλείσιμο"); close.clicked.connect(self.accept); rl.addWidget(close)
        body.addWidget(right, 3)

        self.categories.currentTextChanged.connect(self._refill)
        self.search.textChanged.connect(self._refill)
        self.grid.currentItemChanged.connect(self._material_changed)
        self.target.currentIndexChanged.connect(self._refresh_current)
        self.scale.valueChanged.connect(self._preview_controls)
        self.rotation.valueChanged.connect(self._preview_controls)
        self.brightness.valueChanged.connect(self._preview_controls)
        self.roughness.valueChanged.connect(self._roughness_changed)
        self.save_properties_button.clicked.connect(self._save_selected_properties)
        self.apply.clicked.connect(self._apply)
        self.categories.setCurrentRow(0)
        self._refill(); self._refresh_current()

    def _all_materials(self):
        seen = set()
        for category in picker_categories(self.main_window.doc):
            for material_id, spec in picker_materials(category, self.main_window.doc):
                if material_id in seen: continue
                seen.add(material_id)
                yield str(material_id), dict(spec)

    def _refill(self, *_args):
        selected_category = self.categories.currentItem().text() if self.categories.currentItem() else "Όλα τα υλικά"
        needle = self.search.text().strip().casefold()
        old = self.selected_material_id
        self.grid.clear()
        items = self._all_materials() if selected_category == "Όλα τα υλικά" else picker_materials(selected_category, self.main_window.doc)
        restore = None
        for material_id, spec in items:
            material_id = str(material_id); spec = dict(spec)
            hay = " ".join(str(spec.get(k, "")) for k in ("name", "category", "code", "supplier")).casefold()
            if needle and needle not in hay and needle not in material_id.casefold(): continue
            item = QListWidgetItem(str(spec.get("name", material_id)))
            item.setData(Qt.ItemDataRole.UserRole, material_id)
            image = material_swatch(material_id, 112, 76, doc=self.main_window.doc)
            item.setIcon(QPixmap.fromImage(image))
            item.setToolTip(" · ".join(x for x in (str(spec.get("category", "")), str(spec.get("code", "")), str(spec.get("supplier", ""))) if x))
            self.grid.addItem(item)
            if material_id == old: restore = item
        if restore is not None: self.grid.setCurrentItem(restore)

    def _material_changed(self, current, _previous):
        if current is None:
            self.selected_material_id = ""
            self.apply.setEnabled(False)
            self.save_properties_button.setEnabled(False)
            self._set_properties_editor(None)
            return
        self.selected_material_id = str(current.data(Qt.ItemDataRole.UserRole))
        spec = material_spec(self.selected_material_id, self.main_window.doc) or {}
        self.preview_name.setText(str(spec.get("name", self.selected_material_id)))
        details = [str(spec.get("category", ""))]
        if spec.get("code"): details.append(f"Κωδικός {spec['code']}")
        if spec.get("supplier"): details.append(str(spec["supplier"]))
        self.preview_info.setText(" · ".join(x for x in details if x))
        blocked = self.roughness.blockSignals(True)
        self.roughness.setValue(float(spec.get("roughness", 0.6)))
        self.roughness.blockSignals(blocked)
        self.roughness.setEnabled(True)
        self.sphere.set_material(self.selected_material_id, self.main_window.doc)
        self._preview_controls()
        self.apply.setEnabled(self.entity is not None)
        self.save_properties_button.setEnabled(True)
        from archforge.ui.material_properties import MaterialPropertiesDialog
        editor = MaterialPropertiesDialog(self, self.selected_material_id, self.main_window.doc, embedded=True)
        self._set_properties_editor(editor)

    def _set_properties_editor(self, editor):
        old = self.properties_layout.takeAt(0)
        if old is not None and old.widget() is not None:
            old.widget().deleteLater()
        self.properties_editor = editor
        if editor is None:
            empty = QLabel("Επίλεξε υλικό για επεξεργασία")
            empty.setObjectName("materialEmptyProperties")
            self.properties_layout.addWidget(empty)
        else:
            self.properties_layout.addWidget(editor)

    def _roughness_changed(self, value):
        if self.properties_editor is not None:
            self.properties_editor.roughness.setValue(value)
        self.sphere.roughness = float(value)
        self.sphere.update()

    def _save_selected_properties(self):
        """Save in the same user-material registry and project command stack as before."""
        editor = self.properties_editor
        if editor is None or not self.selected_material_id:
            return None
        try:
            spec = editor.spec()
            saved = um.save_properties(self.selected_material_id, spec)
        except ValueError as exc:
            QMessageBox.information(self, "Ιδιότητες υλικού", str(exc))
            return None
        self.selected_material_id = saved
        if saved in (getattr(self.main_window.doc, "materials", None) or {}):
            carry = um.carry_command(self.main_window.doc, saved)
            if carry is not None:
                self.main_window.stack.execute(carry)
        self.main_window._refresh_library_tree()
        # A modified built-in becomes a new entry under «Δικά μου υλικά».
        spec = material_spec(saved, self.main_window.doc) or {}
        new_category = str(spec.get("category", ""))
        if new_category != self.categories.currentItem().text():
            matches = self.categories.findItems(new_category, Qt.MatchFlag.MatchExactly)
            if matches:
                self.categories.setCurrentItem(matches[0])
            else:
                self._refill()
        else:
            self._refill()
        self.main_window._redraw_views(all_views=True)
        self.main_window.statusBar().showMessage(f"Αποθηκεύτηκε υλικό «{spec.get('name', saved)}»", 4000)
        return saved

    def _preview_controls(self, *_args):
        self.sphere.scale = float(self.scale.value()) / 100.0
        self.sphere.rotation = float(self.rotation.value())
        self.sphere.brightness = float(self.brightness.value()) / 100.0
        self.sphere.update()

    def _refresh_current(self, *_args):
        if self.entity is None:
            self.current.setText("Επιλέξτε αντικείμενο για εφαρμογή · οι ιδιότητες αποθηκεύονται κανονικά")
            return
        role = str(self.target.currentData() or "")
        current_id = _assigned_material(self.entity, role)
        spec = material_spec(current_id, self.main_window.doc) if current_id else None
        target = self.target.currentText()
        self.current.setText(f"Τώρα — {target}: {spec.get('name', current_id) if spec else 'προεπιλογή αντικειμένου'}")

    def _apply(self):
        if not self.selected_material_id or self.entity is None: return
        role = str(self.target.currentData() or "")
        _apply_material(self.main_window, self.entity_id, role, self.selected_material_id)
        self.entity = self.main_window.doc.get(self.entity_id)
        self._refresh_current()
        spec = material_spec(self.selected_material_id, self.main_window.doc) or {}
        self.main_window.statusBar().showMessage(
            f"Εφαρμόστηκε «{spec.get('name', self.selected_material_id)}» — Αναίρεση διαθέσιμη", 3500
        )

    def _open_legacy(self):
        if not callable(self.legacy_opener): return
        role = str(self.target.currentData() or "")
        self.hide()
        try:
            self.legacy_opener(self.main_window, self.entity_id, role or None)
        finally:
            self.show(); self.raise_(); self.activateWindow()
            self.entity = self.main_window.doc.get(self.entity_id)
            self._refill(); self._refresh_current()


def open_material_library(main_window, entity_id: str, part_role: str | None = None, legacy_opener=None):
    entity_id = str(entity_id) if entity_id is not None else None
    if entity_id is not None and entity_id not in main_window.doc.entities: return
    MaterialLibraryDialog(main_window, entity_id, part_role, legacy_opener=legacy_opener).exec()


def install_material_library(main_window_cls):
    """Use the new visual browser while preserving the mature old dialog.

    The old method remains the advanced editor, so supplier codes, user-material
    creation and any specialised surface rules remain available during the UI
    transition.  Both dialogs write the same authoritative fields.
    """
    legacy = getattr(main_window_cls, "_open_materials", None)
    if legacy is None or getattr(main_window_cls, "_material_library_installed", False):
        return

    def _open_materials(self, entity_id, part_role=None):
        return open_material_library(self, entity_id, part_role, legacy_opener=legacy)

    main_window_cls._open_materials = _open_materials
    main_window_cls._material_library_installed = True
