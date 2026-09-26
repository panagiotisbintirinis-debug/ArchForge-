from __future__ import annotations

import copy
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QDockWidget, QWidget, QFormLayout, QDoubleSpinBox,
    QLabel, QTabWidget, QStatusBar, QFileDialog, QMessageBox, QComboBox, QInputDialog,
    QDialog, QDialogButtonBox, QVBoxLayout,
)

from archforge.core.model import Document, WorkPlane
from archforge.core.commands import (
    CommandStack, UpdateEntity, CreateRoomFloors, CreateRoomRoofs,
    DeleteEntities, CreateFloorLevel, SetWorkPlane,
)
from .plan_view import PlanView
from .pbr_viewport import PBRViewport
from .object_properties import property_fields, property_values, property_changes


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ArchForge Development')
        self.resize(1400, 900)
        self.doc = Document()
        self.stack = CommandStack(self.doc)
        self.current_path = None
        self._clean_state = copy.deepcopy(self.doc.to_dict())
        self.tabs = QTabWidget()
        self.plan_view = PlanView(self.doc, self.stack)
        self.pbr_view = PBRViewport(self.doc, self.stack)
        self.tabs.addTab(self.plan_view, 'FLOOR PLAN')
        self.tabs.addTab(self.pbr_view, '3D STUDIO')
        self.setCentralWidget(self.tabs)
        self.view = self.plan_view
        self.setStatusBar(QStatusBar())
        for view in (self.plan_view, self.pbr_view):
            view.statusChanged.connect(self.statusBar().showMessage)
            view.selectionChangedByView.connect(self._selection_from_view)
            view.contextActionRequested.connect(self._handle_object_context_action)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._build_toolbar()
        self._build_view_toolbar()
        self._build_view_menu()
        self._build_inspector()
        self.refresh_inspector()

    def _on_tab_changed(self, idx):
        widgets = [self.plan_view, self.pbr_view]
        if 0 <= idx < len(widgets):
            self.view = widgets[idx]
        if self.view is self.pbr_view:
            self.pbr_view.activate()
        self._redraw_views()

    def _set_active_tool(self, tool):
        if hasattr(self.view, 'set_tool'):
            self.view.set_tool(tool)

    def _activate_sculpt_tool(self):
        self.tabs.setCurrentWidget(self.pbr_view)
        self.pbr_view.activate()
        self.pbr_view.set_tool('sculpt')

    def _configure_sculpt_views(self, **kwargs):
        self.pbr_view.configure_sculpt(**kwargs)

    def _build_toolbar(self):
        self.tools_toolbar = QToolBar('Tools')
        self.tools_toolbar.setObjectName('tools_toolbar')
        self.tools_toolbar.setMovable(False)
        self.addToolBar(self.tools_toolbar)
        toolbar = self.tools_toolbar
        for text, tool, key in [
            ('Select', 'select', 'S'), ('Wall', 'wall', 'W'), ('Door', 'door', 'D'),
            ('Window', 'window', 'N'), ('Move', 'move', 'G'), ('Stretch', 'stretch', 'T'),
            ('Rotate', 'rotate', 'R'),
        ]:
            action = QAction(text, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(lambda checked=False, t=tool: self._set_active_tool(t))
            toolbar.addAction(action)

        delete_action = QAction('Delete', self)
        delete_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        delete_action.triggered.connect(self._delete_selection)
        self.addAction(delete_action)
        self.delete_action = delete_action

        sculpt = QAction('Sculpt 3D', self)
        sculpt.setShortcut(QKeySequence('C'))
        sculpt.triggered.connect(self._activate_sculpt_tool)
        toolbar.addAction(sculpt)

        self.sculpt_operation = QComboBox()
        self.sculpt_operation.addItems(
            ['pull', 'push', 'inflate', 'recess', 'smooth', 'crease']
        )
        self.sculpt_operation.currentTextChanged.connect(
            lambda value: self._configure_sculpt_views(operation=value)
        )
        toolbar.addWidget(QLabel(' Op '))
        toolbar.addWidget(self.sculpt_operation)

        self.sculpt_radius = QDoubleSpinBox()
        self.sculpt_radius.setRange(0.10, 5.0)
        self.sculpt_radius.setDecimals(2)
        self.sculpt_radius.setSingleStep(0.05)
        self.sculpt_radius.setValue(self.pbr_view.sculpt_brush.radius)
        self.sculpt_radius.setToolTip(
            'Local brush diameter control: smaller values deform a tighter area around the picked point.'
        )
        self.sculpt_radius.valueChanged.connect(
            lambda value: self._configure_sculpt_views(
                radius=value,
                strength=1.0,
            )
        )
        toolbar.addWidget(QLabel(' Brush '))
        toolbar.addWidget(self.sculpt_radius)
        toolbar.addSeparator()

        self.render_technique = QComboBox()
        self.render_technique.addItem('PBR', 'pbr')
        self.render_technique.addItem('Technical', 'technical')
        self.render_technique.addItem('Glass', 'glass')
        self.render_technique.currentIndexChanged.connect(
            lambda _index: self.pbr_view.set_render_technique(
                self.render_technique.currentData()
            )
        )
        toolbar.addWidget(QLabel(' Render '))
        toolbar.addWidget(self.render_technique)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(' Floor '))
        self.floor_selector = QComboBox()
        self.floor_selector.setMinimumWidth(110)
        self.floor_selector.currentIndexChanged.connect(self._activate_selected_floor)
        toolbar.addWidget(self.floor_selector)

        add_floor = QAction('+ Floor', self)
        add_floor.triggered.connect(self._add_floor_level)
        toolbar.addAction(add_floor)
        self.add_floor_action = add_floor
        self._refresh_floor_selector()

        auto_floors = QAction('Auto Floors', self)
        auto_floors.triggered.connect(self._create_auto_floors)
        toolbar.addAction(auto_floors)

        flat_roof = QAction('Flat Roof', self)
        flat_roof.triggered.connect(self._create_flat_roofs)
        toolbar.addAction(flat_roof)
        toolbar.addSeparator()
        undo = QAction('Undo', self)
        undo.setShortcut(QKeySequence.StandardKey.Undo)
        undo.triggered.connect(self._undo)
        toolbar.addAction(undo)
        redo = QAction('Redo', self)
        redo.setShortcut(QKeySequence.StandardKey.Redo)
        redo.triggered.connect(self._redo)
        toolbar.addAction(redo)
        toolbar.addSeparator()
        new_action = QAction('New', self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_project)
        toolbar.addAction(new_action)
        save = QAction('Save', self)
        save.setShortcut(QKeySequence.StandardKey.Save)
        save.triggered.connect(self.save)
        toolbar.addAction(save)
        open_action = QAction('Open', self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open)
        toolbar.addAction(open_action)
        stl_action = QAction('Export STL', self)
        stl_action.triggered.connect(self.export_stl)
        toolbar.addAction(stl_action)



    def _build_view_menu(self):
        view_menu = self.menuBar().addMenu('&View')

        self.status_bar_action = QAction('Status Bar', self, checkable=True)
        self.status_bar_action.setChecked(not self.statusBar().isHidden())
        self.status_bar_action.toggled.connect(self.statusBar().setVisible)
        view_menu.addAction(self.status_bar_action)

        self.tools_toolbar_action = self.tools_toolbar.toggleViewAction()
        self.tools_toolbar_action.setText('Tools Toolbar')
        view_menu.addAction(self.tools_toolbar_action)

    def _build_view_toolbar(self):
        self.addToolBarBreak()
        toolbar = QToolBar('View')
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addWidget(QLabel(' Camera '))
        for text, mode in (
            ('Cutaway', 'cutaway'),
            ('Top', 'top'),
            ('Front', 'front'),
            ('Side', 'side'),
            ('ISO 30°', 'iso30'),
            ('Eye', 'eye'),
            ('Orbit', 'orbit'),
        ):
            action = QAction(text, self)
            action.triggered.connect(
                lambda checked=False, m=mode: self._set_pbr_camera(m)
            )
            toolbar.addAction(action)

        toolbar.addSeparator()

        axes = QAction('Axes', self)
        axes.setCheckable(True)
        axes.setChecked(False)
        axes.toggled.connect(self.pbr_view.set_axes_visible)
        toolbar.addAction(axes)
        self.axes_action = axes

        cutaway = QAction('Cutaway', self)
        cutaway.setCheckable(True)
        cutaway.setChecked(False)
        cutaway.toggled.connect(self.pbr_view.set_cutaway)
        toolbar.addAction(cutaway)
        self.cutaway_action = cutaway

        auto_rotate = QAction('Auto Rotate', self)
        auto_rotate.setCheckable(True)
        auto_rotate.setChecked(False)
        auto_rotate.toggled.connect(self.pbr_view.set_auto_rotate)
        toolbar.addAction(auto_rotate)
        self.auto_rotate_action = auto_rotate

    def _set_pbr_camera(self, mode):
        self.tabs.setCurrentWidget(self.pbr_view)
        self.pbr_view.activate()
        self.pbr_view.set_camera_preset(mode)
        if hasattr(self, 'cutaway_action'):
            self.cutaway_action.blockSignals(True)
            self.cutaway_action.setChecked(mode == 'cutaway')
            self.cutaway_action.blockSignals(False)

    def _build_inspector(self):
        self.dock = QDockWidget('Inspector', self)
        self.dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.inspector = QWidget()
        self.form = QFormLayout(self.inspector)
        self.dock.setWidget(self.inspector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)

    def _clear_form(self):
        while self.form.rowCount():
            self.form.removeRow(0)

    def refresh_inspector(self):
        self._clear_form()
        if len(self.doc.selection) != 1:
            self.form.addRow(QLabel(f'{len(self.doc.selection)} selected'))
            return
        eid = self.doc.selection[0]
        entity = self.doc.get(eid)
        self.form.addRow('Type', QLabel(entity.kind))
        self.form.addRow('Name', QLabel(entity.name or entity.kind.title()))
        if entity.parent_id and entity.parent_id in self.doc.entities:
            host = self.doc.get(entity.parent_id)
            self.form.addRow('Host', QLabel(host.name or f'{host.kind.title()} {host.id[:8]}'))
        for key, value in entity.params.items():
            if isinstance(value, (int, float)):
                spin = QDoubleSpinBox()
                spin.setDecimals(4)
                spin.setRange(-1e6, 1e6)
                spin.setValue(float(value))
                spin.setSingleStep(.1)
                spin.editingFinished.connect(
                    lambda property_key=key, widget=spin: self._commit_property(eid, property_key, widget.value())
                )
                self.form.addRow(key, spin)
            elif entity.kind == 'room_floor' and key == 'room_signature':
                self.form.addRow('Room', QLabel(str(value)))

    def _commit_property(self, eid, key, value):
        try:
            self.stack.execute(UpdateEntity(eid, {key: value}))
            self._redraw_views()
        except Exception as exc:
            QMessageBox.warning(self, 'Invalid value', str(exc))
            self.refresh_inspector()

    def _apply_object_properties(self, entity_id, values):
        entity_id = str(entity_id)
        if entity_id not in self.doc.entities:
            raise KeyError(entity_id)
        entity = self.doc.get(entity_id)
        changes = property_changes(entity, values)
        self.stack.execute(UpdateEntity(entity_id, changes))
        self.doc.select([entity_id])
        self._redraw_views(all_views=True)
        self.refresh_inspector()

    def _open_object_properties(self, entity_id):
        entity_id = str(entity_id)
        if entity_id not in self.doc.entities:
            return
        entity = self.doc.get(entity_id)
        fields = property_fields(entity.kind)
        if not fields:
            self.dock.show()
            self.dock.raise_()
            self.statusBar().showMessage(
                f'No editable dimension set yet for {entity.kind}',
                3000,
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f'{entity.name or entity.kind.title()} Properties')
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        layout.addLayout(form)

        current = property_values(entity)
        editors = {}
        for spec in fields:
            spin = QDoubleSpinBox(dialog)
            spin.setDecimals(3)
            spin.setRange(float(spec.get('minimum', -1e6)), float(spec.get('maximum', 1e6)))
            spin.setSingleStep(float(spec.get('step', 0.05)))
            spin.setValue(float(current[spec['id']]))
            spin.setSuffix(f" {spec.get('unit', '')}" if spec.get('unit') else '')
            form.addRow(spec['label'], spin)
            editors[spec['id']] = spin

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = {key: editor.value() for key, editor in editors.items()}
        try:
            self._apply_object_properties(entity_id, values)
        except Exception as exc:
            QMessageBox.warning(dialog, 'Invalid dimensions', str(exc))
            self.refresh_inspector()
            return

        self.statusBar().showMessage(
            f'Updated {entity.name or entity.kind.title()} dimensions — Undo is available',
            3500,
        )

    def _handle_object_context_action(self, entity_id, action_id):
        entity_id = str(entity_id)
        action_id = str(action_id)
        if entity_id not in self.doc.entities:
            return

        self.doc.select([entity_id])
        self.refresh_inspector()

        if action_id == 'properties':
            self._open_object_properties(entity_id)
            return

        if action_id == 'delete':
            self._delete_selection()
            return

        if action_id in ('move', 'stretch', 'rotate'):
            # These actions are currently implemented through the Floor Plan
            # direct-manipulation controller. The PBR registry intentionally
            # does not advertise them until equivalent 3D gizmos exist.
            self.tabs.setCurrentWidget(self.plan_view)
            self.plan_view.set_tool(action_id)
            self.plan_view.controller.set_target(entity_id, None)
            self.plan_view.redraw()
            self.statusBar().showMessage(
                f'{action_id.title()} {self.doc.get(entity_id).name or self.doc.get(entity_id).kind.title()}',
                3000,
            )
            return

    def _delete_selection(self):
        ids = list(self.doc.selection)
        if not ids:
            self.statusBar().showMessage('Nothing selected to delete', 2500)
            return
        try:
            self.stack.execute(DeleteEntities(ids))
            self._redraw_views(all_views=True)
            self.refresh_inspector()
            self.statusBar().showMessage(f'Deleted {len(ids)} object(s) — Undo is available', 3500)
        except Exception as exc:
            QMessageBox.warning(self, 'Delete failed', str(exc))

    def _refresh_floor_selector(self):
        if not hasattr(self, 'floor_selector'):
            return
        active_name = str(getattr(self.doc.work_plane, 'name', '') or '')
        active_z = float(self.doc.work_plane.origin[2])
        levels = sorted(
            ((str(name), float(z)) for name, z in self.doc.levels.items()),
            key=lambda item: (item[1], item[0]),
        )
        self.floor_selector.blockSignals(True)
        self.floor_selector.clear()
        active_index = 0
        for index, (name, elevation) in enumerate(levels):
            self.floor_selector.addItem(f'{name}  ({elevation:.2f} m)', (name, elevation))
            if name == active_name or abs(elevation - active_z) <= 1e-6:
                active_index = index
        if levels:
            self.floor_selector.setCurrentIndex(active_index)
        self.floor_selector.blockSignals(False)

    def _activate_selected_floor(self, index):
        if index < 0 or not hasattr(self, 'floor_selector'):
            return
        data = self.floor_selector.itemData(index)
        if not data:
            return
        name, elevation = data
        elevation = float(elevation)
        if (
            str(self.doc.work_plane.name) == str(name)
            and abs(float(self.doc.work_plane.origin[2]) - elevation) <= 1e-6
        ):
            return
        wp = self.doc.work_plane
        self.stack.execute(SetWorkPlane(WorkPlane(
            name=str(name),
            origin=(float(wp.origin[0]), float(wp.origin[1]), elevation),
            u=tuple(wp.u),
            v=tuple(wp.v),
        )))
        self.doc.select([])
        self._redraw_views(all_views=True)
        self.refresh_inspector()
        self.statusBar().showMessage(f'Active floor: {name} — {elevation:.2f} m', 3000)

    def _add_floor_level(self):
        existing = sorted(float(z) for z in self.doc.levels.values())
        default_elevation = (max(existing) if existing else 0.0) + 2.70
        elevation, accepted = QInputDialog.getDouble(
            self,
            'Add Floor',
            'Floor elevation (m):',
            default_elevation,
            -1000.0,
            1000.0,
            3,
        )
        if not accepted:
            return
        number = 2
        existing_names = set(self.doc.levels)
        while f'Floor {number}' in existing_names:
            number += 1
        name = f'Floor {number}'
        try:
            self.stack.execute(CreateFloorLevel(name, elevation))
        except Exception as exc:
            QMessageBox.warning(self, 'Add Floor', str(exc))
            return
        self._refresh_floor_selector()
        self._redraw_views(all_views=True)
        self.refresh_inspector()
        self.statusBar().showMessage(
            f'Created and activated {name} at {float(elevation):.2f} m',
            3500,
        )

    def _create_auto_floors(self):
        faces = self.doc.active_room_faces()
        if not faces:
            self.statusBar().showMessage('No closed rooms on the current work plane', 4000)
            return
        existing = {
            entity.params.get('room_signature')
            for entity in self.doc.entities.values()
            if entity.kind == 'room_floor'
        }
        signatures = [face.signature for face in faces if face.signature not in existing]
        if not signatures:
            self.statusBar().showMessage('All current rooms already have automatic floors', 4000)
            return
        try:
            self.stack.execute(CreateRoomFloors(signatures))
            self._redraw_views()
            self.refresh_inspector()
            self.statusBar().showMessage(f'Created {len(signatures)} automatic floor(s)', 4000)
        except Exception as exc:
            QMessageBox.warning(self, 'Auto Floors', str(exc))

    def _create_flat_roofs(self):
        faces = self.doc.active_room_faces()
        if not faces:
            self.statusBar().showMessage(
                'No closed rooms available for a flat roof',
                4000,
            )
            return

        existing = {
            entity.params.get('room_signature')
            for entity in self.doc.entities.values()
            if entity.kind == 'room_roof'
            and entity.params.get('roof_type') == 'flat'
        }
        signatures = [
            face.signature
            for face in faces
            if face.signature not in existing
        ]
        if not signatures:
            self.statusBar().showMessage(
                'All current rooms already have flat roofs',
                4000,
            )
            return

        try:
            self.stack.execute(
                CreateRoomRoofs(
                    signatures,
                    thickness=.20,
                    roof_type='flat',
                )
            )
            self._redraw_views(all_views=True)
            self.refresh_inspector()
            self.statusBar().showMessage(
                f'Created {len(signatures)} flat roof slab(s)',
                4000,
            )
        except Exception as exc:
            QMessageBox.warning(self, 'Flat Roof', str(exc))

    def _selection_from_view(self):
        self.refresh_inspector()

    def _redraw_views(self, *, all_views=False):
        targets=(self.plan_view,self.pbr_view) if all_views else (self.view,)
        for view in targets:
            if view is self.pbr_view:
                view.redraw(force_full=True)
            else:
                view.redraw()

    def _undo(self):
        self.stack.undo()
        self._redraw_views()
        self.refresh_inspector()

    def _redo(self):
        self.stack.redo()
        self._redraw_views()
        self.refresh_inspector()

    def _authoritative_state(self):
        return self.doc.to_dict()

    def _is_dirty(self):
        return self._authoritative_state() != self._clean_state

    def _mark_clean(self):
        self._clean_state = copy.deepcopy(self._authoritative_state())

    def _confirm_destructive_action(self):
        if not self._is_dirty():
            return True
        choice = QMessageBox.warning(
            self,
            'Unsaved changes',
            'The current project has unsaved changes. Save them before continuing?',
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Save:
            return self.save()
        return choice == QMessageBox.StandardButton.Discard


    def closeEvent(self, event):
        if self._confirm_destructive_action():
            event.accept()
        else:
            event.ignore()

    def _replace_project(self, doc, path=None):
        self.doc = doc
        self.stack = CommandStack(self.doc)
        for view in (self.plan_view, self.pbr_view):
            view.rebind(self.doc, self.stack)
        self.current_path = path
        self._mark_clean()
        self._refresh_floor_selector()
        self._redraw_views(all_views=True)
        self.refresh_inspector()

    def new_project(self):
        if not self._confirm_destructive_action():
            return False
        self._replace_project(Document())
        self.statusBar().showMessage('New project', 3000)
        return True

    def save(self):
        path = self.current_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, 'Save ArchForge Project', '', 'ArchForge Project (*.archforge)')
        if not path:
            return False
        if not path.lower().endswith('.archforge'):
            path += '.archforge'
        try:
            self.doc.save(path)
        except Exception as exc:
            QMessageBox.critical(self, 'Save failed', str(exc))
            return False
        self.current_path = path
        self._mark_clean()
        self.statusBar().showMessage(f'Saved {os.path.basename(path)}', 3000)
        return True

    def open(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open ArchForge Project', '', 'ArchForge Project (*.archforge)')
        if not path:
            return False
        if not self._confirm_destructive_action():
            return False
        try:
            doc = Document.load(path)
        except Exception as exc:
            QMessageBox.critical(self, 'Open failed', str(exc))
            return False
        self._replace_project(doc, path)
        return True

    def export_stl(self):
        from archforge.geometry.fabrication import export_document_stl
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export STL for Fabrication / 3D Printing', '', 'Stereolithography (*.stl)'
        )
        if not path:
            return
        if not path.lower().endswith('.stl'):
            path += '.stl'
        try:
            scope = list(self.doc.selection) if self.doc.selection else None
            count = export_document_stl(self.doc, path, entity_ids=scope, binary=True)
            self.statusBar().showMessage(f'Exported {count} triangles to {os.path.basename(path)}', 4000)
        except Exception as exc:
            QMessageBox.warning(self, 'Fabrication Gate Failed', f'Cannot export STL: {exc}')
