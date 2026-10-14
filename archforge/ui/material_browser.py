from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from archforge.core.commands import UpdateEntity
from archforge.rendering.materials import MATERIAL_PRESETS, material_categories


_SUPPORTED_KINDS = {
    'wall', 'floor', 'room_floor', 'room_roof', 'room_ceiling',
    'room_foundation', 'box', 'pod', 'stair', 'ramp',
    'structural_column', 'structural_beam', 'mechanical_part', 'mesh',
}

# Semantic surface roles already emitted by ArchForge geometry. These are not
# screen-space faces: they remain stable design roles when the camera changes.
_SURFACE_ROLES = {
    'wall': ('exterior', 'interior'),
    'floor': ('top', 'bottom', 'edge'),
    'room_floor': ('top', 'bottom', 'edge'),
    'room_roof': ('top', 'bottom', 'edge'),
    'room_ceiling': ('top', 'bottom', 'edge'),
    'room_foundation': ('top', 'bottom', 'edge'),
    'box': ('front', 'right', 'back', 'left', 'top', 'bottom'),
    'structural_column': ('side_a', 'side_b', 'side_c', 'side_d', 'top', 'bottom'),
    'structural_beam': ('side_a', 'end', 'side_b', 'start', 'top', 'bottom'),
    'pod': ('pod_shell',),
}


def _surface_roles(entity):
    if entity.kind == 'mesh':
        faces = entity.params.get('faces') or ()
        return tuple(f'mesh_face:{index}' for index in range(len(faces)))
    return tuple(_SURFACE_ROLES.get(entity.kind, ()))


def _material_label(material_id: str | None) -> str:
    spec = MATERIAL_PRESETS.get(str(material_id or ''))
    return str(spec['name']) if spec else 'Default by object type'


def _current_material_id(entity, target_mode: str = 'object') -> str:
    surface_map = entity.params.get('surface_materials') or {}
    if target_mode == 'both' and entity.kind == 'wall':
        a = surface_map.get('exterior')
        b = surface_map.get('interior')
        if a and a == b:
            return str(a)
        return str(entity.params.get('material_id', '') or '')
    if target_mode.startswith('surface:'):
        role = target_mode.split(':', 1)[1]
        return str(surface_map.get(role) or entity.params.get('material_id', '') or '')
    return str(entity.params.get('material_id', '') or '')


def _apply_material(main_window, entity_id: str, material_id: str, target_mode: str) -> None:
    entity = main_window.doc.get(entity_id)
    changes = {}
    target_label = entity.kind.title()

    if target_mode == 'both' and entity.kind == 'wall':
        surface_map = dict(entity.params.get('surface_materials') or {})
        surface_map['exterior'] = material_id
        surface_map['interior'] = material_id
        changes['surface_materials'] = surface_map
        target_label = 'both wall sides'
    elif target_mode.startswith('surface:'):
        role = target_mode.split(':', 1)[1]
        surface_map = dict(entity.params.get('surface_materials') or {})
        surface_map[role] = material_id
        changes['surface_materials'] = surface_map
        target_label = role.replace('_', ' ')
    else:
        # "Entire object" is intentionally decisive: remove old face overrides
        # so the newly chosen finish really appears on every surface.
        changes['material_id'] = material_id
        if entity.params.get('surface_materials'):
            changes['surface_materials'] = {}
        target_label = 'entire object'

    main_window.stack.execute(UpdateEntity(entity_id, changes))
    main_window.doc.select([entity_id])
    main_window._redraw_views(all_views=True)
    main_window.refresh_inspector()
    spec = MATERIAL_PRESETS[material_id]
    main_window.statusBar().showMessage(
        f"Applied {spec['name']} to {target_label} — Undo is available",
        3500,
    )


class MaterialBrowserDialog(QDialog):
    """Visual material workspace linked to the authoritative selected entity."""

    def __init__(self, main_window, entity_id: str):
        super().__init__(main_window)
        self.main_window = main_window
        self.entity_id = str(entity_id)
        self.entity = main_window.doc.get(self.entity_id)
        self.selected_material_id = ''
        self.setWindowTitle('ArchForge — Material Browser')
        self.resize(1040, 680)
        self.setModal(True)
        self.setStyleSheet(
            "QDialog{background:#111821;color:#e9eef5;}"
            "QFrame#panel{background:#18222d;border:1px solid #2c3a48;border-radius:10px;}"
            "QLineEdit,QComboBox,QListWidget{background:#0f1720;color:#eef4fb;border:1px solid #334454;border-radius:6px;padding:6px;}"
            "QPushButton{background:#1d6fdc;color:white;border:0;border-radius:6px;padding:8px 14px;font-weight:600;}"
            "QPushButton:disabled{background:#34404c;color:#7f8a95;}"
            "QLabel#title{font-size:18px;font-weight:700;}"
            "QLabel#muted{color:#9eacba;}"
        )

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel('Material Browser')
        title.setObjectName('title')
        subtitle = QLabel(f"Selected object: {self.entity.kind}  ·  {self.entity_id}")
        subtitle.setObjectName('muted')
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        root.addLayout(header)

        body = QHBoxLayout()
        root.addLayout(body, 1)

        nav = QFrame()
        nav.setObjectName('panel')
        nav.setMinimumWidth(190)
        nav_l = QVBoxLayout(nav)
        nav_l.addWidget(QLabel('LIBRARY'))
        self.category = QListWidget()
        self.category.addItem('All Materials')
        for category in material_categories():
            self.category.addItem(category)
        nav_l.addWidget(self.category, 1)
        body.addWidget(nav)

        center = QFrame()
        center.setObjectName('panel')
        center_l = QVBoxLayout(center)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search materials…')
        center_l.addWidget(self.search)
        self.materials = QListWidget()
        self.materials.setSpacing(5)
        center_l.addWidget(self.materials, 1)
        body.addWidget(center, 2)

        detail = QFrame()
        detail.setObjectName('panel')
        detail.setMinimumWidth(330)
        detail_l = QVBoxLayout(detail)
        detail_l.addWidget(QLabel('MATERIAL PREVIEW'))
        self.preview = QFrame()
        self.preview.setMinimumHeight(220)
        self.preview.setFrameShape(QFrame.Shape.StyledPanel)
        detail_l.addWidget(self.preview)
        self.preview_name = QLabel('Select a material')
        self.preview_name.setObjectName('title')
        self.preview_meta = QLabel('')
        self.preview_meta.setObjectName('muted')
        self.preview_meta.setWordWrap(True)
        detail_l.addWidget(self.preview_name)
        detail_l.addWidget(self.preview_meta)

        detail_l.addSpacing(10)
        detail_l.addWidget(QLabel('Apply to'))
        self.target = QComboBox()
        self.target.addItem('Entire object', 'object')
        if self.entity.kind == 'wall':
            self.target.addItem('Both wall sides', 'both')
        for role in _surface_roles(self.entity):
            label = role.replace('_', ' ').replace('mesh face:', 'Face ')
            self.target.addItem(label.title(), f'surface:{role}')
        detail_l.addWidget(self.target)

        self.current = QLabel('Current: —')
        self.current.setWordWrap(True)
        detail_l.addWidget(self.current)
        self.override_hint = QLabel('')
        self.override_hint.setObjectName('muted')
        self.override_hint.setWordWrap(True)
        detail_l.addWidget(self.override_hint)
        detail_l.addStretch(1)

        self.apply_button = QPushButton('Apply Material')
        self.apply_button.setEnabled(False)
        detail_l.addWidget(self.apply_button)
        body.addWidget(detail)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.category.currentTextChanged.connect(self._refill)
        self.search.textChanged.connect(self._refill)
        self.materials.currentItemChanged.connect(self._selection_changed)
        self.target.currentIndexChanged.connect(self._refresh_current)
        self.apply_button.clicked.connect(self._apply)

        self.category.setCurrentRow(0)
        self._refill()
        self._refresh_current()

    def _matching_materials(self):
        selected_category = self.category.currentItem().text() if self.category.currentItem() else 'All Materials'
        needle = self.search.text().strip().lower()
        for material_id, spec in MATERIAL_PRESETS.items():
            if selected_category != 'All Materials' and spec.get('category') != selected_category:
                continue
            haystack = f"{material_id} {spec.get('name','')} {spec.get('category','')}".lower()
            if needle and needle not in haystack:
                continue
            yield material_id, spec

    def _refill(self, *_args):
        previous = self.selected_material_id
        self.materials.clear()
        restore_item = None
        for material_id, spec in self._matching_materials():
            item = QListWidgetItem(f"{spec['name']}\n{spec['category']}")
            item.setData(Qt.ItemDataRole.UserRole, material_id)
            item.setBackground(QColor(str(spec['color'])))
            color = QColor(str(spec['color']))
            luminance = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
            item.setForeground(QColor('#111820' if luminance > 160 else '#f4f7fa'))
            self.materials.addItem(item)
            if material_id == previous:
                restore_item = item
        if restore_item is not None:
            self.materials.setCurrentItem(restore_item)

    def _selection_changed(self, current, _previous):
        if current is None:
            self.selected_material_id = ''
            self.apply_button.setEnabled(False)
            return
        material_id = str(current.data(Qt.ItemDataRole.UserRole))
        self.selected_material_id = material_id
        spec = MATERIAL_PRESETS[material_id]
        self.preview.setStyleSheet(
            f"background:{spec['color']};border:1px solid #4d5c6b;border-radius:12px;"
        )
        self.preview_name.setText(str(spec['name']))
        self.preview_meta.setText(
            f"{spec['category']}  ·  Roughness {float(spec['roughness']):.2f}  ·  "
            f"Metalness {float(spec['metalness']):.2f}"
        )
        self.apply_button.setEnabled(True)

    def _refresh_current(self, *_args):
        mode = str(self.target.currentData() or 'object')
        current_id = _current_material_id(self.entity, mode)
        self.current.setText(f"Current: {_material_label(current_id)}")
        overrides = self.entity.params.get('surface_materials') or {}
        if overrides:
            self.override_hint.setText(
                f"{len(overrides)} surface override(s) active. Applying to Entire object clears them."
            )
        else:
            self.override_hint.setText('No surface overrides active.')

    def _apply(self):
        if not self.selected_material_id:
            return
        mode = str(self.target.currentData() or 'object')
        _apply_material(self.main_window, self.entity_id, self.selected_material_id, mode)
        self.entity = self.main_window.doc.get(self.entity_id)
        self._refresh_current()


def _material_property_widget(main_window, entity):
    panel = QFrame()
    panel.setStyleSheet(
        "QFrame{background:#18222d;border:1px solid #304151;border-radius:7px;}"
        "QLabel{border:0;background:transparent;}"
    )
    layout = QHBoxLayout(panel)
    layout.setContentsMargins(8, 7, 8, 7)

    current_id = str(entity.params.get('material_id', '') or '')
    spec = MATERIAL_PRESETS.get(current_id)
    swatch = QLabel()
    swatch.setFixedSize(34, 34)
    swatch.setStyleSheet(
        f"background:{spec['color'] if spec else '#7d8791'};border:1px solid #566574;border-radius:5px;"
    )
    layout.addWidget(swatch)

    text_box = QVBoxLayout()
    name = QLabel(_material_label(current_id))
    category = QLabel(str(spec.get('category', 'Object default')) if spec else 'Object default')
    category.setStyleSheet('color:#9eacba;')
    text_box.addWidget(name)
    text_box.addWidget(category)
    overrides = entity.params.get('surface_materials') or {}
    if overrides:
        detail = QLabel(f"{len(overrides)} surface override(s)")
        detail.setStyleSheet('color:#72aef5;')
        text_box.addWidget(detail)
    layout.addLayout(text_box, 1)

    browse = QPushButton('Browse…')
    browse.clicked.connect(lambda checked=False, eid=entity.id: open_material_browser(main_window, eid))
    layout.addWidget(browse)
    return panel


def open_material_browser(main_window, entity_id: str):
    entity_id = str(entity_id)
    if entity_id not in main_window.doc.entities:
        return
    entity = main_window.doc.get(entity_id)
    if entity.kind not in _SUPPORTED_KINDS:
        main_window.statusBar().showMessage(
            f'Materials are not available for {entity.kind} yet',
            3000,
        )
        return
    MaterialBrowserDialog(main_window, entity_id).exec()


def install_material_browser(main_window_cls) -> None:
    """Attach material browsing to the proven editor without forking it."""
    if getattr(main_window_cls, '_archforge_material_browser_installed', False):
        return

    original_refresh_inspector = main_window_cls.refresh_inspector

    def _open_materials(self, entity_id):
        return open_material_browser(self, entity_id)

    def _refresh_inspector_with_material(self):
        original_refresh_inspector(self)
        if len(self.doc.selection) != 1:
            return
        entity = self.doc.get(self.doc.selection[0])
        if entity.kind not in _SUPPORTED_KINDS:
            return
        self.form.addRow('Material', _material_property_widget(self, entity))

    main_window_cls._open_materials = _open_materials
    main_window_cls.refresh_inspector = _refresh_inspector_with_material
    main_window_cls._archforge_material_browser_installed = True
