from __future__ import annotations

import copy
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QDockWidget, QWidget, QFormLayout, QDoubleSpinBox,
    QLabel, QTabWidget, QStatusBar, QFileDialog, QMessageBox, QComboBox, QInputDialog,
    QDialog, QDialogButtonBox, QVBoxLayout, QListWidget, QListWidgetItem,
    QToolButton, QMenu,
)

from archforge.core.model import Document, WorkPlane, Entity
from archforge.core.commands import (
    CommandStack, UpdateEntity, CreateRoomFloors, CreateRoomRoofs,
    DeleteEntities, CreateFloorLevel, SetWorkPlane, RouteAndConnectInfrastructure, AddEntity,
)
from archforge.rendering.materials import MATERIAL_PRESETS, material_categories, materials_in_category
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
        self.structural_view = PlanView(self.doc, self.stack, structural_only=True)
        self.tabs.addTab(self.plan_view, 'FLOOR PLAN')
        self.tabs.addTab(self.pbr_view, '3D STUDIO')
        self.tabs.addTab(self.structural_view, 'STRUCTURAL')
        self.setCentralWidget(self.tabs)
        self.view = self.plan_view
        self.setStatusBar(QStatusBar())
        for view in (self.plan_view, self.pbr_view, self.structural_view):
            view.statusChanged.connect(self.statusBar().showMessage)
            view.selectionChangedByView.connect(self._selection_from_view)
            view.contextActionRequested.connect(self._handle_object_context_action)
        self.plan_view.commandRequested.connect(self._handle_plan_command)
        self.plan_view.previewChanged.connect(self.pbr_view.set_stair_preview)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._build_toolbar()
        self._build_view_toolbar()
        self._build_edit_menu()
        self._build_view_menu()
        self._build_inspector()
        self.refresh_inspector()

    def _on_tab_changed(self, idx):
        widgets = [self.plan_view, self.pbr_view, self.structural_view]
        if 0 <= idx < len(widgets):
            self.view = widgets[idx]
        if self.view is self.pbr_view:
            self.pbr_view.activate()
        elif self.view is self.structural_view:
            try:
                from archforge.structure.graph import build_structural_graph
                graph=build_structural_graph(self.doc)
                self.statusBar().showMessage(
                    f'Structural View — {len(graph.members)} members / {len(graph.nodes)} nodes / '
                    f'{len(graph.supports)} supports / {len(graph.loads)} input loads · '
                    'results require validated analysis',
                    5000,
                )
            except Exception as exc:
                self.statusBar().showMessage(f'Structural View — graph issue: {exc}',5000)
        self._redraw_views()

    def _set_active_tool(self, tool):
        if str(tool).startswith('structural_') and self.view is self.pbr_view:
            self.tabs.setCurrentWidget(self.structural_view)
            self.view = self.structural_view
        if self.view is self.structural_view and str(tool) not in (
            'select','structural_column','structural_beam','move','rotate'
        ):
            self.tabs.setCurrentWidget(self.plan_view)
            self.view = self.plan_view
        # Keep frame-free openings in the active human view. PBR now routes
        # Rectangle/Arch openings through the same authoritative OpeningPlaceTransaction
        # used by Floor Plan; only MEP authoring still requires the plan workflow.
        if str(tool).startswith('mep_') and self.view is self.pbr_view:
            self.tabs.setCurrentWidget(self.plan_view)
            self.view = self.plan_view
        if hasattr(self.view, 'set_tool'):
            self.view.set_tool(tool)

    def _set_snap_enabled(self, enabled):
        enabled = bool(enabled)
        self.plan_view.set_snap_enabled(enabled)
        self.pbr_view.set_snap_enabled(enabled)
        self.structural_view.set_snap_enabled(enabled)
        self.statusBar().showMessage(
            'Snap ON — wall faces/endpoints/midpoints | Shift = Free | Ctrl = X/Y constraint'
            if enabled
            else 'Snap OFF — Free placement | Ctrl still constrains X/Y',
            4500,
        )

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
            ('Window', 'window', 'N'),
        ]:
            action = QAction(text, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(lambda checked=False, t=tool: self._set_active_tool(t))
            toolbar.addAction(action)

        opening_menu = QMenu(self)
        opening_rect_action = QAction('Rectangle Opening', self)
        opening_rect_action.triggered.connect(
            lambda checked=False: self._set_active_tool('opening_rect')
        )
        opening_menu.addAction(opening_rect_action)

        opening_arch_action = QAction('Arch Opening', self)
        opening_arch_action.triggered.connect(
            lambda checked=False: self._set_active_tool('opening_arch')
        )
        opening_menu.addAction(opening_arch_action)

        opening_button = QToolButton(self)
        opening_button.setText('Opening')
        opening_button.setToolTip('Frame-free wall opening: Rectangle or Arch')
        opening_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        opening_button.setMenu(opening_menu)
        opening_button.setDefaultAction(opening_rect_action)
        opening_button.setText('Opening')
        toolbar.addWidget(opening_button)
        self.opening_button = opening_button
        self.opening_rect_action = opening_rect_action
        self.opening_arch_action = opening_arch_action

        circulation_menu = QMenu(self)
        stair_action = QAction('Stair', self)
        stair_action.setShortcut(QKeySequence('A'))
        stair_action.triggered.connect(lambda checked=False: self._set_active_tool('stair'))
        circulation_menu.addAction(stair_action)
        self.addAction(stair_action)

        ramp_action = QAction('Ramp', self)
        ramp_action.setShortcut(QKeySequence('P'))
        ramp_action.triggered.connect(lambda checked=False: self._set_active_tool('ramp'))
        circulation_menu.addAction(ramp_action)
        self.addAction(ramp_action)

        circulation = QToolButton(self)
        circulation.setText('Stair / Ramp')
        circulation.setToolTip('Vertical circulation: Stair or Ramp')
        circulation.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        circulation.setMenu(circulation_menu)
        circulation.setDefaultAction(stair_action)
        circulation.setText('Stair / Ramp')
        toolbar.addWidget(circulation)
        self.circulation_button = circulation
        self.stair_action = stair_action
        self.ramp_action = ramp_action

        structure_menu = QMenu(self)

        column_action = QAction('Column / Pillar', self)
        column_action.setToolTip('Place a semantic Column/Post; Role and Construction remain editable.')
        column_action.triggered.connect(
            lambda checked=False: self._set_active_tool('structural_column')
        )
        structure_menu.addAction(column_action)

        beam_action = QAction('Beam', self)
        beam_action.setToolTip('Draw a semantic Beam between two plan points.')
        beam_action.triggered.connect(
            lambda checked=False: self._set_active_tool('structural_beam')
        )
        structure_menu.addAction(beam_action)

        structure_button = QToolButton(self)
        structure_button.setText('Structure')
        structure_button.setToolTip('Columns and Beams — structural, pergola, or architectural roles')
        structure_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        structure_button.setMenu(structure_menu)
        structure_button.setDefaultAction(column_action)
        structure_button.setText('Structure')
        toolbar.addWidget(structure_button)

        self.structure_button = structure_button
        self.structural_column_action = column_action
        self.structural_beam_action = beam_action

        for text, tool, key in [
            ('Move', 'move', 'G'), ('Stretch', 'stretch', 'T'), ('Rotate', 'rotate', 'R'),
        ]:
            action = QAction(text, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(lambda checked=False, t=tool: self._set_active_tool(t))
            toolbar.addAction(action)

        snap_action = QAction('Snap', self)
        snap_action.setCheckable(True)
        snap_action.setChecked(True)
        snap_action.setToolTip(
            'Snap ON: endpoints, midpoints and wall faces. Shift = temporary Free, Ctrl = X/Y constraint while moving.'
        )
        snap_action.toggled.connect(self._set_snap_enabled)
        toolbar.addAction(snap_action)
        self.snap_action = snap_action

        materials_action = QAction('Materials', self)
        materials_action.setToolTip('Assign a surface material to the selected object')
        materials_action.triggered.connect(self._open_selected_materials)
        toolbar.addAction(materials_action)
        self.materials_action = materials_action

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
        self.undo_action = undo
        redo = QAction('Redo', self)
        redo.setShortcut(QKeySequence.StandardKey.Redo)
        redo.triggered.connect(self._redo)
        toolbar.addAction(redo)
        self.redo_action = redo
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



    def _build_edit_menu(self):
        edit_menu = self.menuBar().addMenu('&Edit')
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action)

    def _handle_plan_command(self, command):
        command = str(command)
        if command == 'undo':
            self._undo()
        elif command == 'delete':
            self._delete_selection()

    def _build_view_menu(self):
        # Retain the Python wrapper for the lifetime of the window. PySide can
        # otherwise collect the local QMenu wrapper even though its QAction is
        # still present in the native menu bar, leaving action.menu() dangling.
        self.view_menu = self.menuBar().addMenu('&View')

        self.status_bar_action = QAction('Status Bar', self, checkable=True)
        self.status_bar_action.setChecked(not self.statusBar().isHidden())
        self.status_bar_action.toggled.connect(self.statusBar().setVisible)
        self.view_menu.addAction(self.status_bar_action)

        self.tools_toolbar_action = self.tools_toolbar.toggleViewAction()
        self.tools_toolbar_action.setText('Tools Toolbar')
        self.view_menu.addAction(self.tools_toolbar_action)

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
            entity = self.doc.get(eid)
            changes = {key: value}
            if entity.kind == 'stair':
                p = entity.params
                lower_z = float(p['lower_z'])
                upper_floor_z = float(p.get('upper_floor_z', p['upper_z']))
                slab_thickness = float(p.get('upper_slab_thickness', max(0.0, float(p['upper_z']) - upper_floor_z)))
                upper_z = float(p['upper_z'])
                riser_count = int(p['riser_count'])

                if key == 'riser_count':
                    riser_count = max(2, int(round(float(value))))
                    changes['riser_count'] = riser_count
                    changes['riser_height'] = (upper_z - lower_z) / riser_count
                elif key == 'riser_height':
                    requested = max(1e-6, float(value))
                    riser_count = max(2, int(round((upper_z - lower_z) / requested)))
                    changes['riser_count'] = riser_count
                    changes['riser_height'] = (upper_z - lower_z) / riser_count
                elif key == 'upper_slab_thickness':
                    slab_thickness = max(0.0, float(value))
                    upper_z = upper_floor_z + slab_thickness
                    changes['upper_slab_thickness'] = slab_thickness
                    changes['upper_z'] = upper_z
                    changes['riser_height'] = (upper_z - lower_z) / riser_count
                elif key == 'upper_floor_z':
                    upper_floor_z = float(value)
                    upper_z = upper_floor_z + slab_thickness
                    changes['upper_floor_z'] = upper_floor_z
                    changes['upper_z'] = upper_z
                    changes['riser_height'] = (upper_z - lower_z) / riser_count
                elif key == 'upper_z':
                    upper_z = float(value)
                    changes['upper_z'] = upper_z
                    changes['upper_slab_thickness'] = max(0.0, upper_z - upper_floor_z)
                    changes['riser_height'] = (upper_z - lower_z) / riser_count
                elif key == 'lower_z':
                    lower_z = float(value)
                    changes['lower_z'] = lower_z
                    changes['riser_height'] = (upper_z - lower_z) / riser_count

            elif entity.kind == 'ramp':
                p = entity.params
                lower_z = float(p['lower_z'])
                upper_z = float(p['upper_z'])
                rise = upper_z - lower_z
                slope = float(p['slope_pct'])
                run = float(p['run_length'])

                if key == 'slope_pct':
                    slope = max(1e-6, float(value))
                    changes['slope_pct'] = slope
                    changes['run_length'] = rise / (slope / 100.0)
                elif key == 'run_length':
                    run = max(1e-6, float(value))
                    changes['run_length'] = run
                    changes['slope_pct'] = rise / run * 100.0
                elif key == 'upper_slab_thickness':
                    upper_floor_z = float(p.get('upper_floor_z', upper_z))
                    upper_z = upper_floor_z + max(0.0, float(value))
                    rise = upper_z - lower_z
                    changes['upper_slab_thickness'] = max(0.0, float(value))
                    changes['upper_z'] = upper_z
                    changes['run_length'] = rise / (slope / 100.0)
                elif key == 'upper_floor_z':
                    slab_thickness = float(p.get('upper_slab_thickness', 0.0))
                    upper_z = float(value) + slab_thickness
                    rise = upper_z - lower_z
                    changes['upper_floor_z'] = float(value)
                    changes['upper_z'] = upper_z
                    changes['run_length'] = rise / (slope / 100.0)
                elif key == 'upper_z':
                    upper_z = float(value)
                    rise = upper_z - lower_z
                    changes['upper_z'] = upper_z
                    changes['run_length'] = rise / (slope / 100.0)
                elif key == 'lower_z':
                    lower_z = float(value)
                    rise = upper_z - lower_z
                    changes['lower_z'] = lower_z
                    changes['run_length'] = rise / (slope / 100.0)

            self.stack.execute(UpdateEntity(eid, changes))
            self._redraw_views(all_views=True)
            self.refresh_inspector()
        except Exception as exc:
            QMessageBox.warning(self, 'Invalid value', str(exc))
            self.refresh_inspector()

    def _apply_object_properties(self, entity_id, values, extra_changes=None):
        entity_id = str(entity_id)
        if entity_id not in self.doc.entities:
            raise KeyError(entity_id)
        entity = self.doc.get(entity_id)
        changes = property_changes(entity, values)
        if extra_changes:
            changes.update(dict(extra_changes))
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
        shape_editor = None
        if entity.kind == 'opening':
            shape_editor = QComboBox(dialog)
            shape_editor.addItem('Rectangle', 'rectangle')
            shape_editor.addItem('Arch', 'arch')
            shape_idx = shape_editor.findData(str(entity.params.get('shape', 'rectangle')))
            if shape_idx >= 0:
                shape_editor.setCurrentIndex(shape_idx)
            form.addRow('Shape', shape_editor)

        role_editor = None
        construction_editor = None
        if entity.kind in ('structural_column','structural_beam'):
            role_editor = QComboBox(dialog)
            for label,value in (
                ('Structural','structural'),
                ('Pergola','pergola'),
                ('Architectural / Decorative','architectural'),
            ):
                role_editor.addItem(label,value)
            role_idx = role_editor.findData(str(entity.params.get('role','structural')))
            if role_idx >= 0:
                role_editor.setCurrentIndex(role_idx)
            form.addRow('Role', role_editor)

            construction_editor = QComboBox(dialog)
            for label,value in (
                ('Reinforced Concrete','reinforced_concrete'),
                ('Steel','steel'),
                ('Timber','timber'),
                ('Aluminium','aluminium'),
                ('Generic','generic'),
            ):
                construction_editor.addItem(label,value)
            construction_idx = construction_editor.findData(str(entity.params.get('construction','generic')))
            if construction_idx >= 0:
                construction_editor.setCurrentIndex(construction_idx)
            form.addRow('Construction', construction_editor)

            section_label = QLabel('Rectangular', dialog)
            section_label.setToolTip('Only rectangular structural sections are geometrically implemented in this build.')
            form.addRow('Section', section_label)

        base_level_editor = None
        top_level_editor = None
        beam_level_editor = None
        if entity.kind == 'structural_column':
            ordered_levels=sorted(self.doc.levels.items(),key=lambda item:float(item[1]))

            base_level_editor=QComboBox(dialog)
            for name,z in ordered_levels:
                base_level_editor.addItem(f'{name} ({float(z):.2f} m)', str(name))
            base_idx=base_level_editor.findData(str(entity.params.get('base_level',self.doc.work_plane.name)))
            if base_idx >= 0:
                base_level_editor.setCurrentIndex(base_idx)
            form.addRow('Base Level',base_level_editor)

            top_level_editor=QComboBox(dialog)
            top_level_editor.addItem('Unassigned','Unassigned')
            for name,z in ordered_levels:
                top_level_editor.addItem(f'{name} ({float(z):.2f} m)', str(name))
            top_idx=top_level_editor.findData(str(entity.params.get('top_level','Unassigned')))
            if top_idx >= 0:
                top_level_editor.setCurrentIndex(top_idx)
            form.addRow('Top Level',top_level_editor)

        elif entity.kind == 'structural_beam':
            ordered_levels=sorted(self.doc.levels.items(),key=lambda item:float(item[1]))
            beam_level_editor=QComboBox(dialog)
            for name,z in ordered_levels:
                beam_level_editor.addItem(f'{name} ({float(z):.2f} m)', str(name))
            level_idx=beam_level_editor.findData(str(entity.params.get('level',self.doc.work_plane.name)))
            if level_idx >= 0:
                beam_level_editor.setCurrentIndex(level_idx)
            form.addRow('Storey',beam_level_editor)

        for spec in fields:
            spin = QDoubleSpinBox(dialog)
            spin.setDecimals(3)
            spin.setRange(float(spec.get('minimum', -1e6)), float(spec.get('maximum', 1e6)))
            spin.setSingleStep(float(spec.get('step', 0.05)))
            spin.setValue(float(current[spec['id']]))
            spin.setSuffix(f" {spec.get('unit', '')}" if spec.get('unit') else '')
            form.addRow(spec['label'], spin)
            editors[spec['id']] = spin

        if shape_editor is not None and 'arch_rise' in editors:
            def update_arch_rise_enabled(*_):
                editors['arch_rise'].setEnabled(str(shape_editor.currentData()) == 'arch')
            shape_editor.currentIndexChanged.connect(update_arch_rise_enabled)
            update_arch_rise_enabled()

        if top_level_editor is not None and 'height' in editors:
            def update_column_height_enabled(*_):
                editors['height'].setEnabled(str(top_level_editor.currentData()) == 'Unassigned')
            top_level_editor.currentIndexChanged.connect(update_column_height_enabled)
            update_column_height_enabled()

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

        try:
            values = {key: editor.value() for key, editor in editors.items()}
            extra_changes = {}
            if shape_editor is not None:
                extra_changes['shape'] = str(shape_editor.currentData())
            if role_editor is not None:
                extra_changes['role'] = str(role_editor.currentData())
            if construction_editor is not None:
                extra_changes['construction'] = str(construction_editor.currentData())

            if base_level_editor is not None:
                base_name=str(base_level_editor.currentData())
                top_name=str(top_level_editor.currentData()) if top_level_editor is not None else 'Unassigned'
                extra_changes['base_level']=base_name
                extra_changes['top_level']=top_name
                if base_name not in self.doc.levels:
                    raise ValueError('selected base level no longer exists')
                base_z=float(self.doc.levels[base_name])
                extra_changes['z']=base_z
                if top_name!='Unassigned':
                    if top_name not in self.doc.levels:
                        raise ValueError('selected top level no longer exists')
                    top_z=float(self.doc.levels[top_name])
                    if top_z<=base_z:
                        raise ValueError('Column Top Level must be above Base Level')
                    values['height']=top_z-base_z

            if beam_level_editor is not None:
                level_name=str(beam_level_editor.currentData())
                if level_name not in self.doc.levels:
                    raise ValueError('selected beam storey no longer exists')
                extra_changes['level']=level_name
                # Beam level is the structural plane at the beam top face.
                # Keep the physical solid and derived analysis node aligned.
                level_z=float(self.doc.levels[level_name])
                beam_height=float(values.get('height', entity.params['height']))
                extra_changes['z']=level_z-beam_height

            if not extra_changes:
                extra_changes = None
            self._apply_object_properties(entity_id, values, extra_changes=extra_changes)
        except Exception as exc:
            QMessageBox.warning(dialog, 'Invalid dimensions', str(exc))
            self.refresh_inspector()
            return

        self.statusBar().showMessage(
            f'Updated {entity.name or entity.kind.title()} dimensions — Undo is available',
            3500,
        )

    def _add_structural_support(self, entity_id):
        entity_id=str(entity_id)
        if entity_id not in self.doc.entities:
            return
        member=self.doc.get(entity_id)
        if member.kind not in ('structural_column','structural_beam'):
            self.statusBar().showMessage('Support requires a structural Column or Beam',3000)
            return
        if str(member.params.get('role','structural'))!='structural':
            self.statusBar().showMessage('Only Structural-role members can receive supports',3500)
            return

        end_label,ok=QInputDialog.getItem(
            self,'Add Structural Support','Member end',
            ['Start','End'],0,False,
        )
        if not ok:
            return
        support_label,ok=QInputDialog.getItem(
            self,'Add Structural Support','Support type',
            ['Fixed','Pinned','Roller'],0,False,
        )
        if not ok:
            return

        support=Entity(
            'structural_support',
            {
                'member_end':str(end_label).lower(),
                'support_type':str(support_label).lower(),
            },
            name=f'{support_label} Support',
            parent_id=entity_id,
        )
        try:
            self.stack.execute(AddEntity(support))
            self.doc.select([support.id])
            self._redraw_views(all_views=True)
            self.refresh_inspector()
            self.statusBar().showMessage(
                f'Added {support_label} support at {end_label} — Undo is available',
                3500,
            )
        except Exception as exc:
            QMessageBox.warning(self,'Support',str(exc))

    def _add_structural_load(self, entity_id):
        entity_id=str(entity_id)
        if entity_id not in self.doc.entities:
            return
        member=self.doc.get(entity_id)
        if member.kind not in ('structural_column','structural_beam'):
            self.statusBar().showMessage('Load requires a structural Column or Beam',3000)
            return
        if str(member.params.get('role','structural'))!='structural':
            self.statusBar().showMessage('Only Structural-role members can receive loads',3500)
            return

        load_label,ok=QInputDialog.getItem(
            self,'Add Structural Load','Load type',
            ['Point','Distributed'],0,False,
        )
        if not ok:
            return
        load_type=str(load_label).lower()
        magnitude,ok=QInputDialog.getDouble(
            self,'Add Structural Load',
            'Magnitude (kN)' if load_type=='point' else 'Magnitude (kN/m)',
            1.0,0.0,1e9,3,
        )
        if not ok:
            return

        direction_label,ok=QInputDialog.getItem(
            self,'Add Structural Load','Direction',
            ['Down (-Z)','Up (+Z)','+X','-X','+Y','-Y'],0,False,
        )
        if not ok:
            return
        directions={
            'Down (-Z)':(0.0,0.0,-1.0),
            'Up (+Z)':(0.0,0.0,1.0),
            '+X':(1.0,0.0,0.0),'-X':(-1.0,0.0,0.0),
            '+Y':(0.0,1.0,0.0),'-Y':(0.0,-1.0,0.0),
        }
        direction=directions[str(direction_label)]

        position=0.5
        if load_type=='point':
            pct,ok=QInputDialog.getDouble(
                self,'Add Structural Load','Position along member (%)',
                50.0,0.0,100.0,1,
            )
            if not ok:
                return
            position=float(pct)/100.0

        load_case,ok=QInputDialog.getText(
            self,'Add Structural Load','Load case',text='User Load'
        )
        if not ok or not str(load_case).strip():
            return
        source,ok=QInputDialog.getText(
            self,'Add Structural Load','Source / note',text='User input'
        )
        if not ok or not str(source).strip():
            return

        unit='kN' if load_type=='point' else 'kN/m'
        load=Entity(
            'structural_load',
            {
                'load_type':load_type,
                'magnitude':float(magnitude),
                'direction':list(direction),
                'position':float(position),
                'load_case':str(load_case).strip(),
                'unit':unit,
                'source':str(source).strip(),
            },
            name=f'{load_label} Load',
            parent_id=entity_id,
        )
        try:
            self.stack.execute(AddEntity(load))
            self.doc.select([load.id])
            self._redraw_views(all_views=True)
            self.refresh_inspector()
            self.statusBar().showMessage(
                f'Added {float(magnitude):g} {unit} {load_label.lower()} — input only, no analysis run',
                4500,
            )
        except Exception as exc:
            QMessageBox.warning(self,'Structural Load',str(exc))

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

        if action_id == 'materials':
            self._open_materials(entity_id)
            return

        if action_id == 'support':
            self._add_structural_support(entity_id)
            return

        if action_id == 'load':
            self._add_structural_load(entity_id)
            return

        if action_id == 'delete':
            self._delete_selection()
            return

        if action_id in ('move', 'stretch', 'rotate'):
            entity = self.doc.get(entity_id)
            if self.view is self.pbr_view:
                if action_id == 'move' and entity.kind in {
                    'stair', 'ramp', 'wall', 'box', 'pod', 'structural_column', 'structural_beam', 'floor', 'room', 'mechanical_part'
                }:
                    self.pbr_view.set_tool('move')
                    self.statusBar().showMessage(
                        f'Move {entity.name or entity.kind.title()}: click object, move pointer, click to place',
                        4000,
                    )
                    return
                if action_id == 'rotate' and entity.kind in {
                    'stair', 'ramp', 'wall', 'box', 'pod', 'structural_column', 'structural_beam'
                }:
                    self.pbr_view.set_tool('rotate')
                    self.statusBar().showMessage(
                        f'Rotate {entity.name or entity.kind.title()}: click object, move pointer, click to place · Shift = free angle',
                        4500,
                    )
                    return
            target_view = self.structural_view if self.view is self.structural_view else self.plan_view
            self.tabs.setCurrentWidget(target_view)
            target_view.set_tool(action_id)
            target_view.controller.set_target(entity_id, None)
            target_view.redraw()
            self.statusBar().showMessage(
                f'{action_id.title()} {entity.name or entity.kind.title()}',
                3000,
            )
            return

    def _route_selected_mep(self):
        ids=[eid for eid in self.doc.selection if eid in self.doc.entities]
        if len(ids)!=2:
            QMessageBox.warning(
                self,
                'MEP Route',
                'Select exactly two MEP points with Ctrl, then choose Route Selected.',
            )
            return
        endpoints=[self.doc.get(eid) for eid in ids]
        if any(e.kind!='mep_terminal' for e in endpoints):
            QMessageBox.warning(
                self,
                'MEP Route',
                'Route Selected currently connects two MEP points, not arbitrary objects.',
            )
            return
        systems={str(e.params.get('system_type','')).lower() for e in endpoints}
        if len(systems)!=1:
            QMessageBox.warning(
                self,
                'MEP Route',
                'The two MEP points belong to different systems.',
            )
            return
        diameters=[float(e.params.get('diameter',0.0)) for e in endpoints]
        if abs(diameters[0]-diameters[1])>1e-9:
            QMessageBox.warning(
                self,
                'MEP Route',
                'The two MEP points have different diameters. A reducer fitting is required and is not added automatically yet.',
            )
            return
        system=next(iter(systems))
        try:
            command=RouteAndConnectInfrastructure(
                ids[0],ids[1],diameters[0],system,grid_resolution=0.05,
            )
            self.stack.execute(command)
            self.doc.select([command.generated_id])
            self._redraw_views(all_views=True)
            self.refresh_inspector()
            self.statusBar().showMessage(
                f'Routed {system} connection — Undo is available',
                4000,
            )
        except Exception as exc:
            QMessageBox.warning(self,'MEP Route',str(exc))

    def _open_selected_materials(self):
        if len(self.doc.selection) != 1:
            self.statusBar().showMessage('Select one object before choosing a material', 3000)
            return
        self._open_materials(self.doc.selection[0])

    def _open_materials(self, entity_id):
        entity_id = str(entity_id)
        if entity_id not in self.doc.entities:
            return
        entity = self.doc.get(entity_id)
        supported = {
            'wall', 'floor', 'room_floor', 'room_roof', 'room_ceiling',
            'room_foundation', 'box', 'pod', 'stair', 'ramp',
            'structural_column', 'structural_beam',
            'mechanical_part', 'mesh',
        }
        if entity.kind not in supported:
            self.statusBar().showMessage(
                f'Materials are not available yet for {entity.kind}',
                3000,
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f'Materials / Surfaces — {entity.name or entity.kind.title()}')
        dialog.resize(450, 500)
        layout = QVBoxLayout(dialog)

        target = None
        if entity.kind == 'wall':
            target = QComboBox(dialog)
            target.addItem('Side A', 'exterior')
            target.addItem('Side B', 'interior')
            target.addItem('Both Sides', 'both')
            target.setToolTip(
                'Wall finishes are face-specific. Side A and Side B are the two '
                'sides of the wall; room-aware names will replace these labels later.'
            )
            layout.addWidget(QLabel('Apply to'))
            layout.addWidget(target)

        current = QLabel()
        layout.addWidget(current)

        category = QComboBox(dialog)
        for name in material_categories():
            category.addItem(name)
        layout.addWidget(category)

        materials = QListWidget(dialog)
        layout.addWidget(materials)

        preview = QLabel('Surface preview')
        preview.setMinimumHeight(52)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(preview)

        state = {'material_id': None}

        def current_material_id():
            if entity.kind != 'wall' or target is None:
                return str(entity.params.get('material_id', '') or '')
            mode = str(target.currentData())
            surface_map = entity.params.get('surface_materials') or {}
            if mode == 'both':
                a = surface_map.get('exterior')
                b = surface_map.get('interior')
                if a and a == b:
                    return str(a)
                return ''
            return str(
                surface_map.get(mode)
                or entity.params.get('material_id', '')
                or ''
            )

        def update_current_label():
            material_id = current_material_id()
            spec = MATERIAL_PRESETS.get(material_id, {})
            current_label = spec.get('name', 'Default by object type')
            current.setText(f'Current: {current_label}')
            return material_id

        def fill_materials(category_name):
            selected_id = current_material_id()
            materials.clear()
            for material_id, spec in materials_in_category(category_name):
                item = QListWidgetItem(str(spec['name']))
                item.setData(Qt.ItemDataRole.UserRole, material_id)
                item.setToolTip(
                    f"roughness {float(spec.get('roughness', 0.0)):.2f} · "
                    f"metalness {float(spec.get('metalness', 0.0)):.2f}"
                )
                materials.addItem(item)
                if material_id == selected_id:
                    materials.setCurrentItem(item)
            if materials.currentItem() is None and materials.count():
                materials.setCurrentRow(0)

        def refresh_preview():
            item = materials.currentItem()
            if item is None:
                return
            material_id = str(item.data(Qt.ItemDataRole.UserRole))
            state['material_id'] = material_id
            spec = MATERIAL_PRESETS[material_id]
            preview.setText(
                f"{spec['name']}  ·  rough {float(spec['roughness']):.2f}  ·  metal {float(spec['metalness']):.2f}"
            )
            preview.setStyleSheet(
                f"background: {spec['color']}; border: 1px solid #747b82; "
                "padding: 8px; font-weight: 600;"
            )

        def refresh_for_target():
            selected_id = update_current_label()
            selected_spec = MATERIAL_PRESETS.get(selected_id, {})
            if selected_spec:
                idx = category.findText(str(selected_spec.get('category', '')))
                if idx >= 0:
                    category.setCurrentIndex(idx)
            fill_materials(category.currentText())
            refresh_preview()

        category.currentTextChanged.connect(fill_materials)
        materials.currentItemChanged.connect(lambda *_: refresh_preview())
        if target is not None:
            target.currentIndexChanged.connect(lambda *_: refresh_for_target())

        refresh_for_target()

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
        material_id = state.get('material_id')
        if not material_id:
            return

        changes = {}
        target_label = entity.kind.title()
        if entity.kind == 'wall' and target is not None:
            mode = str(target.currentData())
            surface_map = dict(entity.params.get('surface_materials') or {})
            if mode == 'both':
                surface_map['exterior'] = str(material_id)
                surface_map['interior'] = str(material_id)
                target_label = 'both wall sides'
            else:
                surface_map[mode] = str(material_id)
                target_label = 'Side A' if mode == 'exterior' else 'Side B'
            changes['surface_materials'] = surface_map
        else:
            changes['material_id'] = str(material_id)

        self.stack.execute(UpdateEntity(entity_id, changes))
        self.doc.select([entity_id])
        self._redraw_views(all_views=True)
        self.refresh_inspector()
        spec = MATERIAL_PRESETS[str(material_id)]
        self.statusBar().showMessage(
            f"Applied {spec['name']} to {target_label} — Undo is available",
            3500,
        )

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
        from archforge.architecture.stairs import discover_building_levels
        levels = discover_building_levels(self.doc)
        self.floor_selector.blockSignals(True)
        self.floor_selector.clear()
        active_index = 0
        for index, item in enumerate(levels):
            name = str(item['name'])
            elevation = float(item['elevation'])
            inferred = bool(item.get('inferred', False))
            label = f'{name}  ({elevation:.2f} m)'
            if inferred:
                label += ' *'
            self.floor_selector.addItem(label, (name, elevation, inferred))
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
        name, elevation, inferred = data
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
        from archforge.architecture.stairs import discover_building_levels
        discovered = discover_building_levels(self.doc)
        existing = sorted(float(item['elevation']) for item in discovered)
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
        targets=(self.plan_view,self.pbr_view,self.structural_view) if all_views else (self.view,)
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
        for view in (self.plan_view, self.pbr_view, self.structural_view):
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
