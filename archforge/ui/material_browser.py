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
from archforge.rendering.materials import (
    MATERIAL_PRESETS,
    material_categories,
)


_SUPPORTED_KINDS = {
    'wall', 'floor', 'room_floor', 'room_roof', 'room_ceiling',
    'room_foundation', 'box', 'pod', 'stair', 'ramp',
    'structural_column', 'structural_beam', 'mechanical_part', 'mesh',
}


def _current_material_id(entity, target_mode: str = 'object') -> str:
    if entity.kind == 'wall' and target_mode in {'exterior', 'interior', 'both'}:
        surface_map = entity.params.get('surface_materials') or {}
        if target_mode == 'both':
            a = surface_map.get('exterior')
            b = surface_map.get('interior')
            if a and a == b:
                return str(a)
            return str(entity.params.get('material_id', '') or '')
        return str(surface_map.get(target_mode) or entity.params.get('material_id', '') or '')
    return str(entity.params.get('material_id', '') or '')


def _apply_material(main_window, entity_id: str, material_id: str, target_mode: str) -> None:
    entity = main_window.doc.get(entity_id)
    changes = {}
    target_label = entity.kind.title()

    if entity.kind == 'wall' and target_mode in {'exterior', 'interior', 'both'}:
        surface_map = dict(entity.params.get('surface_materials') or {})
        if target_mode == 'both':
            surface_map['exterior'] = material_id
            surface_map['interior'] = material_id
            target_label = 'both wall sides'
        else:
            surface_map[target_mode] = material_id
            target_label = 'Side A' if target_mode == 'exterior' else 'Side B'
        changes['surface_materials'] = surface_map
    else:
        changes['material_id'] = material_id

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
    """ArchForge material browser linked to the authoritative selected entity.

    The dialog deliberately separates two jobs:
    1. object properties tell the user what is currently assigned;
    2. this browser is the larger visual workspace used to explore and apply.

    Presets are still texture-free today, so the preview is an honest material
    swatch rather than a fake bitmap. The layout is ready for texture thumbnails
    and a real interactive 3D preview when maps are added to the material catalog.
    """

    def __init__(self, main_window, entity_id: str):
        super().__init__(main_window)
        self.main_window = main_window
        self.entity_id = str(entity_id)
        self.entity = main_window.doc.get(self.entity_id)
        self.selected_material_id = ''
        self.setWindowTitle('ArchForge — Material Browser')
        self.resize(980, 640)
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

        # Left: category + search. This is navigation, not object properties.
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

        # Center: browse and choose.
        center = QFrame()
        center.setObjectName('panel')
        center_l = QVBoxLayout(center)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search materials…')
        center_l.addWidget(self.search)
        self.materials = QListWidget()
        self.materials.setSpacing(4)
        center_l.addWidget(self.materials, 1)
        body.addWidget(center, 2)

        # Right: current/preview/application target. This mirrors the selected
        # object's material property without duplicating unrelated properties.
        detail = QFrame()
        detail.setObjectName('panel')
        detail.setMinimumWidth(310)
        detail_l = QVBoxLayout(detail)
        detail_l.addWidget(QLabel('MATERIAL PREVIEW'))
        self.preview = QFrame()
        self.preview.setMinimumHeight(210)
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
        if self.entity.kind == 'wall':
            self.target.addItem('Both wall sides', 'both')
            self.target.addItem('Side A / Exterior', 'exterior')
            self.target.addItem('Side B / Interior', 'interior')
        else:
            self.target.addItem('Selected object', 'object')
        detail_l.addWidget(self.target)

        self.current = QLabel('Current: —')
        self.current.setWordWrap(True)
        detail_l.addWidget(self.current)
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
            # Readable foreground over both light and dark swatches.
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
        spec = MATERIAL_PRESETS.get(current_id)
        self.current.setText(
            f"Current: {spec['name']}" if spec else 'Current: Default by object type'
        )

    def _apply(self):
        if not self.selected_material_id:
            return
        mode = str(self.target.currentData() or 'object')
        _apply_material(self.main_window, self.entity_id, self.selected_material_id, mode)
        self.entity = self.main_window.doc.get(self.entity_id)
        self._refresh_current()


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
    """Install the richer browser without forking the authoritative editor.

    Kept as a tiny runtime patch so this feature branch changes only the
    material UI surface and does not disturb the proven ArchForge-14 window.
    """
    def _open_materials(self, entity_id):
        return open_material_browser(self, entity_id)

    main_window_cls._open_materials = _open_materials
