from __future__ import annotations

import copy
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QDockWidget, QWidget, QFormLayout, QDoubleSpinBox,
    QLabel, QTabWidget, QStatusBar, QFileDialog, QMessageBox, QComboBox, QInputDialog,
    QDialog, QDialogButtonBox, QVBoxLayout, QListWidget, QListWidgetItem,
    QToolButton, QMenu, QSplitter, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QPushButton, QHBoxLayout, QGroupBox,
)

from archforge.core.model import Document, WorkPlane, Entity
from archforge.core.commands import (
    CommandStack, UpdateEntity, CreateRoomFloors, CreateRoomRoofs,
    DeleteEntities, CreateFloorLevel, SetWorkPlane, RouteAndConnectInfrastructure, AddEntity, AddEntities,
)
from archforge.kitchen import build_straight_kitchen
from archforge.rendering.materials import MATERIAL_PRESETS, material_categories, materials_in_category
from .plan_view import PlanView
from .pbr_viewport import PBRViewport
from .object_properties import property_fields, property_values, property_changes
from .workspace_docks import WorkspaceDockSpec, install_workspace_dock, add_workspace_toggles
from .approved_mockup_shell import install_approved_mockup_shell


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ArchForge Development')
        self.resize(1400, 900)
        self.doc = Document()
        self.stack = CommandStack(self.doc)
        self.stack.listeners.append(self._on_document_changed)
        self.current_path = None
        self._clean_state = copy.deepcopy(self.doc.to_dict())
        self.tabs = QTabWidget()
        self.plan_view = PlanView(self.doc, self.stack)
        self.pbr_view = PBRViewport(self.doc, self.stack)
        self.structural_view = PBRViewport(self.doc, self.stack, structural_only=True)
        self.tabs.addTab(self.plan_view, 'FLOOR PLAN')
        self.tabs.addTab(self.pbr_view, '3D STUDIO')
        self.tabs.addTab(self.structural_view, 'STRUCTURAL')

        # Preserve the proven ArchForge 14 editor ownership/runtime.
        # The approved mockup docks surround these real editors; they must not
        # reparent PlanView/PBRViewport away from the tab widget.
        self.setCentralWidget(self.tabs)
        self.view = self.plan_view
        self.setStatusBar(QStatusBar())
        for view in (self.plan_view, self.pbr_view, self.structural_view):
            view.statusChanged.connect(self.statusBar().showMessage)
            view.selectionChangedByView.connect(self._selection_from_view)
            view.contextActionRequested.connect(self._handle_object_context_action)
        self.plan_view.commandRequested.connect(self._handle_plan_command)
        self.plan_view.previewChanged.connect(self.pbr_view.set_stair_preview)
        self.plan_view.viewLineRequested.connect(self._apply_view_line)
        self.plan_view.sitePointRequested.connect(self._place_site_point)
        self.plan_view.siteLineRequested.connect(self._place_site_line)
        # Esc always cancels what is in progress, in 2D and 3D alike.
        self._escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._escape_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._escape_shortcut.activated.connect(self._cancel_interactions)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._build_toolbar()
        self._build_view_toolbar()
        self._build_edit_menu()
        self._build_view_menu()
        self._build_inspector()
        install_approved_mockup_shell(self)
        self._refresh_library_panel()
        if not os.environ.get('PYTEST_CURRENT_TEST'):
            # First run builds the shipped core library in the background.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(300, self._seed_core_library)
        self._refresh_project_tree()
        self.refresh_inspector()

    def _on_tab_changed(self, idx):
        # In the approved mockup the plan is permanently visible on the left
        # and this tab widget owns the real 3D / Structural pane on the right.
        current = self.tabs.currentWidget() if hasattr(self, 'tabs') else None
        if current is self.pbr_view:
            self.view = self.pbr_view
        elif current is self.structural_view:
            self.view = self.structural_view
        if self.view is self.pbr_view:
            self.pbr_view.activate()
        elif self.view is self.structural_view:
            self.structural_view.activate()
            self.structural_view.set_render_technique('technical')
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

    def _ensure_upper_level_for(self, tool):
        """Stair/Ramp need a storey above; offer to create it instead of failing."""
        from archforge.architecture.stairs import upper_floor_landing
        active_z = float(self.doc.work_plane.origin[2])
        # A storey above, or a flat roof terrace, is a valid destination.
        if upper_floor_landing(self.doc, active_z) is not None:
            return True
        number = 2
        while f'Floor {number}' in self.doc.levels:
            number += 1
        name = f'Floor {number}'
        elevation = active_z + 2.70
        what = 'Η σκάλα' if tool == 'stair' else 'Η ράμπα'
        answer = QMessageBox.question(
            self, 'Σκάλα / Ράμπα',
            f'{what} χρειάζεται όροφο ή ταράτσα από πάνω, αλλά δεν υπάρχει.\n'
            f'(Για σκάλα προς ταράτσα, φτιάξε πρώτα Flat / Auto Roof.)\n\n'
            f'Να δημιουργηθεί «{name}» στα {elevation:.2f} m;',
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.statusBar().showMessage('Πρόσθεσε όροφο (+ Όροφος) για να βάλεις σκάλα ή ράμπα', 5000)
            return False
        before = copy.deepcopy(self.doc.work_plane)
        try:
            self.stack.execute(CreateFloorLevel(name, elevation))
            # Keep drawing on the storey the human was on.
            self.stack.execute(SetWorkPlane(before))
        except Exception as exc:
            QMessageBox.warning(self, 'Σκάλα / Ράμπα', str(exc))
            return False
        self._refresh_floor_selector()
        self._redraw_views(all_views=True)
        self.statusBar().showMessage(f'Δημιουργήθηκε {name} στα {elevation:.2f} m — σχεδίασε τη σκάλα/ράμπα', 5000)
        return True

    def _choose_stair_layout(self, layout):
        """Stair type picked from the ribbon: None = best fit for the drag."""
        self._stair_layout = layout
        self._set_active_tool('stair')

    def _set_active_tool(self, tool):
        tool = str(tool)
        if tool in ('stair', 'ramp') and not self._ensure_upper_level_for(tool):
            return
        if tool == 'stair':
            layout = getattr(self, '_stair_layout', None)
            self.plan_view.controller.stair_layout = layout
            self.pbr_view.stair_layout = layout
        # The approved shell defaults ordinary architectural authoring to the
        # real central PlanView. Switching tabs must never leave Wall/Door/etc.
        # routed to an invisible 3D widget.
        plan_tools = {'select','wall','door','window','opening_rect','opening_arch','stair','ramp','move','stretch','rotate','component'}
        # Tools the 3D Scene places by clicking on the model itself.
        pbr_tools = {'select','door','window','opening_rect','opening_arch','stair','ramp','move','rotate'}
        central = getattr(self, '_central_tabs', None)
        simultaneous = getattr(self, '_simultaneous_action', None)
        simultaneous = simultaneous is not None and simultaneous.isChecked()
        looking_at_3d = (
            central is not None and not simultaneous and central.currentIndex() == 1
            and self.tabs.currentWidget() is self.pbr_view
        )
        if looking_at_3d and tool in pbr_tools:
            # Stay in 3D: Door/Window/Opening/Stair work directly on the model.
            self.view = self.pbr_view
            self.pbr_view.activate()
        elif tool in plan_tools and central is not None and not simultaneous:
            central.setCurrentIndex(0)
            self.view = self.plan_view
        # Column/Beam are placed in whichever editor the human is using; the
        # 2D plan supports them, so do not jump to the Structural tab.
        if self.view is self.structural_view and str(tool) not in (
            'select','structural_column','structural_beam','move','rotate'
        ):
            # PlanView is simultaneously visible in the approved split shell;
            # it is no longer a tab that needs to be selected.
            self.view = self.plan_view
        # Keep frame-free openings in the active human view. PBR now routes
        # Rectangle/Arch openings through the same authoritative OpeningPlaceTransaction
        # used by Floor Plan; only MEP authoring still requires the plan workflow.
        if str(tool).startswith('mep_') and self.view is self.pbr_view:
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

    def _activate_sculpt_tool(self, enabled=True):
        if enabled:
            self.tabs.setCurrentWidget(self.pbr_view)
            self.pbr_view.activate()
            self.pbr_view.set_tool('sculpt')
            self.statusBar().showMessage('Sculpt 3D ON', 2000)
        else:
            self.pbr_view.set_tool('orbit')
            self.statusBar().showMessage('Sculpt 3D OFF — camera navigation restored', 2000)

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

        kitchen_action = QAction('Kitchen Run', self)
        kitchen_action.setToolTip('Create an undoable semantic straight kitchen run')
        kitchen_action.triggered.connect(self._create_straight_kitchen)
        toolbar.addAction(kitchen_action)
        self.kitchen_action = kitchen_action

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
        sculpt.setCheckable(True)
        sculpt.setChecked(False)
        sculpt.setToolTip('Toggle Sculpt 3D on/off. Highlighted = active.')
        sculpt.toggled.connect(self._activate_sculpt_tool)
        toolbar.addAction(sculpt)
        self.sculpt_action = sculpt

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
        self.auto_floors_action = auto_floors

        # Preserve the historical ArchForge Flat Roof action, but keep it
        # reachable when the mockup toolbar is narrower than its contents.
        flat_roof = QAction('Flat Roof', self)
        flat_roof.triggered.connect(self._create_flat_roofs)
        toolbar.addAction(flat_roof)
        self.flat_roof_action = flat_roof
        toolbar.addSeparator()

        self.roof_toolbar = QToolBar('Roof', self)
        self.roof_toolbar.setObjectName('roof_toolbar')
        self.roof_toolbar.setMovable(False)
        self.roof_toolbar.addAction(self.flat_roof_action)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.roof_toolbar)
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
        self.new_action = new_action
        save = QAction('Save', self)
        save.setShortcut(QKeySequence.StandardKey.Save)
        save.triggered.connect(self.save)
        toolbar.addAction(save)
        self.save_action = save
        open_action = QAction('Open', self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open)
        toolbar.addAction(open_action)
        self.open_action = open_action
        stl_action = QAction('Export STL', self)
        stl_action.triggered.connect(self.export_stl)
        toolbar.addAction(stl_action)
        self.export_stl_action = stl_action



    def _create_straight_kitchen(self):
        length, ok = QInputDialog.getDouble(
            self, 'Kitchen Run', 'Length (m):', 3.60, 0.60, 30.0, 2
        )
        if not ok:
            return
        modules, ok = QInputDialog.getInt(
            self, 'Kitchen Run', 'Base modules:', 6, 1, 30, 1
        )
        if not ok:
            return
        origin = getattr(self.doc.work_plane, 'origin', (0.0, 0.0, 0.0))
        entities = build_straight_kitchen(
            run_id='Kitchen',
            total_length=float(length) * 1000.0,
            num_base_modules=int(modules),
            num_wall_modules=int(modules),
            origin_x=float(origin[0]),
            origin_y=float(origin[1]),
            origin_z=float(origin[2]),
        )
        self.stack.execute(AddEntities(entities))
        self.doc.selection = [entities[0].id] if entities else []
        self._redraw_views(all_views=True)
        self.refresh_inspector()
        self.statusBar().showMessage(
            f'Kitchen Run created — {length:.2f} m / {modules} modules', 4000
        )

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

    def _create_terrain(self):
        """Έδαφος: one site terrain around the building (select it if present)."""
        from archforge.site.terrain import default_terrain_params
        existing = next((e for e in self.doc.entities.values() if e.kind == 'terrain'), None)
        if existing is None:
            existing = Entity('terrain', default_terrain_params(self.doc), name='Έδαφος')
            self.stack.execute(AddEntity(existing))
            message = 'Έδαφος: άλλαξε υψόμετρο, κλίση (slope_x / slope_y %) και όρια στις Ιδιότητες'
        else:
            message = 'Το έδαφος υπάρχει ήδη — επιλέχθηκε για επεξεργασία'
        self.doc.select([existing.id])
        self._redraw_views(all_views=True)
        self.refresh_inspector()
        self.statusBar().showMessage(message, 6000)
        return existing.id

    def _terrain_entity(self):
        return next((e for e in self.doc.entities.values() if e.kind == 'terrain'), None)

    def _show_terrain_specification(self):
        terrain = self._terrain_entity()
        if terrain is None:
            self._create_terrain()
            return
        self.doc.select([terrain.id])
        self.refresh_inspector()
        self._redraw_views(all_views=True)
        self.statusBar().showMessage(
            'Προδιαγραφές εδάφους στις Ιδιότητες: elevation, slope_x/slope_y %, thickness, όρια, blend_radius', 6000)

    def _delete_terrain(self):
        terrain = self._terrain_entity()
        if terrain is None:
            self.statusBar().showMessage('Δεν υπάρχει έδαφος', 3000)
            return
        self.stack.execute(DeleteEntities([terrain.id]))
        self._redraw_views(all_views=True)
        self.refresh_inspector()
        self.statusBar().showMessage('Το έδαφος διαγράφηκε (Ctrl+Z για αναίρεση)', 4000)

    def _start_site_tool(self, tool, message):
        central = getattr(self, '_central_tabs', None)
        simultaneous = getattr(self, '_simultaneous_action', None)
        if central is not None and not (simultaneous is not None and simultaneous.isChecked()):
            central.setCurrentIndex(0)
        self.view = self.plan_view
        self.plan_view.controller.set_tool(tool)
        self.statusBar().showMessage(message, 8000)

    def _place_site_line(self, tool, x1, y1, x2, y2):
        from archforge.site.paths import STYLES
        style = tool.split('_', 1)[1]
        spec = STYLES[style]
        path = Entity('site_path', {
            'x1': float(x1), 'y1': float(y1), 'x2': float(x2), 'y2': float(y2),
            'z': float(self.doc.work_plane.origin[2]), 'style': style,
            'width': spec['width'], 'thickness': spec['thickness'],
        }, name=spec['name'])
        self.stack.execute(AddEntity(path))
        self._redraw_views(all_views=True)
        self.statusBar().showMessage(f"{spec['name']}: πλάτος στις Ιδιότητες — σύρε για επόμενο, Esc για τέλος", 5000)

    def _place_site_point(self, tool, x, y):
        from archforge.site.terrain import terrain_contains, terrain_height
        if tool in ('plant_tree', 'plant_shrub'):
            from archforge.site.plants import SPECIES
            species = 'tree' if tool == 'plant_tree' else 'shrub'
            plant = Entity('plant', {
                'x': float(x), 'y': float(y), 'z': float(self.doc.work_plane.origin[2]),
                'species': species, **SPECIES[species],
            }, name='Δέντρο' if species == 'tree' else 'Θάμνος')
            self.stack.execute(AddEntity(plant))
            self._redraw_views(all_views=True)
            self.statusBar().showMessage(
                f'{plant.name}: ύψος/κόμη στις Ιδιότητες — κλικ για επόμενο, Esc για τέλος', 5000)
            return
        if tool == 'library_place':
            self._place_library_object(x, y)
            return
        if str(tool).startswith('plumb_'):
            self._place_plumbing_point(tool[len('plumb_'):], x, y)
            return
        if tool == 'terrain_point':
            terrain = self._terrain_entity()
            if terrain is None:
                self._create_terrain()
                terrain = self._terrain_entity()
            if not terrain_contains(terrain.params, x, y):
                self.statusBar().showMessage('Το σημείο είναι έξω από το έδαφος', 4000)
                return
            current = terrain_height(terrain.params, x, y)
            z, ok = QInputDialog.getDouble(
                self, 'Υψομετρικό σημείο', f'Υψόμετρο εδάφους στο ({x:.2f}, {y:.2f}) σε m:',
                round(current, 3), -1000.0, 1000.0, 3)
            if not ok:
                return
            points = [list(p) for p in terrain.params.get('points') or ()] + [[float(x), float(y), float(z)]]
            self.stack.execute(UpdateEntity(terrain.id, {'points': points}))
            self._redraw_views(all_views=True)
            self.statusBar().showMessage(f'Υψομετρικό σημείο {z:+.2f} m — Esc για τέλος', 5000)

    # ---------------------------------------------------------------- library
    def _library_list_dialog(self, title, rows, multi=False):
        """Searchable list; rows are (label, data). Returns chosen data list."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QAbstractItemView
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(560, 520)
        layout = QVBoxLayout(dialog)
        search = QLineEdit(dialog)
        search.setPlaceholderText('Αναζήτηση…')
        listing = QListWidget(dialog)
        if multi:
            listing.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for label, data in rows:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, data)
            listing.addItem(item)
        if listing.count():
            listing.setCurrentRow(0)

        def filter_rows(text):
            text = text.lower()
            for i in range(listing.count()):
                listing.item(i).setHidden(text not in listing.item(i).text().lower())

        search.textChanged.connect(filter_rows)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        listing.itemDoubleClicked.connect(lambda *_: dialog.accept())
        layout.addWidget(search)
        layout.addWidget(listing)
        layout.addWidget(buttons)
        self._library_dialog = dialog  # reachable from tests
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return []
        return [i.data(Qt.ItemDataRole.UserRole) for i in listing.selectedItems() if not i.isHidden()]

    def _import_hd_catalog(self, path=None, object_ids=None):
        """Import 3D objects from a Home Designer catalog into the local library.

        The catalog is read in place; meshes are stored in the user data
        folder marked as local-use-only Home Designer content.
        """
        from PySide6.QtWidgets import QFileDialog
        from archforge.library import assets, hd_calib
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, 'Κατάλογος Home Designer', r'C:\ProgramData',
                'Κατάλογοι Home Designer (*.calib *.calibz)')
            if not path:
                return []
        try:
            conn = hd_calib.open_catalog(path)
            objects = hd_calib.catalog_objects(conn)
        except Exception as exc:
            QMessageBox.warning(self, 'Βιβλιοθήκη', f'Ο κατάλογος δεν διαβάζεται:\n{exc}')
            return []
        interactive = object_ids is None
        if interactive:
            rows = [(f'{name}   ({size / 1048576:.1f} MB)', oid) for oid, name, _typ, size in objects]
            object_ids = self._library_list_dialog(
                f'Εισαγωγή από {os.path.basename(path)} — επιλέξτε (Ctrl/Shift για πολλά)', rows, multi=True)
        names = {oid: name for oid, name, _t, _s in objects}
        imported = []
        for oid in object_ids:
            parts = hd_calib.object_parts(conn, oid)
            for i, (offset, tris) in enumerate(parts, 1):
                label = names[oid] if len(parts) == 1 else f'{names[oid]} — κομμάτι {i}'
                asset_id, _ = assets.store_asset(label, tris, {
                    'source': 'home-designer-calib', 'catalog': os.path.basename(path),
                    'object_id': int(oid), 'offset': int(offset), 'redistributable': False,
                })
                imported.append(asset_id)
        self.statusBar().showMessage(
            f'Βιβλιοθήκη: εισήχθησαν {len(imported)} αντικείμενα (Home Designer — μόνο τοπική χρήση)', 6000)
        self._refresh_library_panel()
        if imported and interactive:
            self._choose_library_asset()
        return imported

    def _import_gltf_model(self, path=None, name=None):
        """Import a user glTF/GLB model (metres, +Y up) into the local library."""
        from PySide6.QtWidgets import QFileDialog
        from archforge.library import assets
        from archforge.library.gltf import drop_ground_planes, read_gltf
        interactive = path is None
        if interactive:
            path, _ = QFileDialog.getOpenFileName(self, 'Μοντέλο glTF', '', 'glTF (*.gltf *.glb)')
            if not path:
                return None
        try:
            parts, dropped = drop_ground_planes(read_gltf(path))
        except Exception as exc:
            QMessageBox.warning(self, 'Βιβλιοθήκη', f'Το μοντέλο δεν διαβάζεται:\n{exc}')
            return None
        if name is None:
            name, ok = QInputDialog.getText(
                self, 'Βιβλιοθήκη', 'Όνομα αντικειμένου:', text=os.path.splitext(os.path.basename(path))[0])
            if not ok or not name.strip():
                return None
        tris = [t for p, _c, _m in parts for t in p]
        colors = [c for p, c, _m in parts for _t in p]
        part_names = {c: m for p, c, m in parts if m}
        asset_id, size = assets.store_asset(name.strip(), tris, {
            'source': 'user-file', 'file': os.path.basename(path),
            'license': 'supplied by the user', 'redistributable': False,
        }, colors=colors, part_names=part_names)
        self._refresh_library_panel()
        note = f' (αφαιρέθηκε βάση: {", ".join(dropped)})' if dropped else ''
        self.statusBar().showMessage(
            f'{name}: {size[0] * 100:.0f}×{size[1] * 100:.0f}×{size[2] * 100:.0f} cm στη Βιβλιοθήκη{note}', 6000)
        if interactive:
            self._choose_library_asset(asset_id)
        return asset_id

    def _open_object_modifier(self, entity_id=None):
        from .object_modifier import CabinetModifierDialog, ObjectModifierDialog
        if entity_id is None:
            if len(self.doc.selection) != 1:
                self.statusBar().showMessage('Επιλέξτε ένα αντικείμενο βιβλιοθήκης', 3000)
                return None
            entity_id = self.doc.selection[0]
        kind = self.doc.get(entity_id).kind
        if kind not in ('library_object', 'cabinet'):
            self.statusBar().showMessage('Το Object Modifier αφορά αντικείμενα βιβλιοθήκης και ντουλάπια', 3000)
            return None
        old = getattr(self, '_object_modifier', None)
        if old is not None:
            old.close()
        dialog_class = CabinetModifierDialog if kind == 'cabinet' else ObjectModifierDialog
        self._object_modifier = dialog_class(self, entity_id)
        self._object_modifier.show()
        return self._object_modifier

    def _refresh_project_tree(self):
        """Rebuild the project tree, storeys and used materials from the Document."""
        from PySide6.QtWidgets import QListWidgetItem, QTreeWidgetItem
        from .project_outline import _levels, project_outline, used_materials
        tree = getattr(self, 'project_tree', None)
        if tree is None or not hasattr(tree, 'invisibleRootItem'):
            return
        title = os.path.splitext(os.path.basename(getattr(self, 'current_path', '') or ''))[0] or 'Έργο'
        outline = project_outline(self.doc, title)

        def add(parent, node):
            item = QTreeWidgetItem(parent, [node['label']])
            item.setData(0, Qt.ItemDataRole.UserRole, node['entity_id'])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, node['level'])
            for child in node['children']:
                add(item, child)
            return item
        tree.clear()
        root = add(tree, outline)
        root.setExpanded(True)
        for i in range(root.childCount()):
            root.child(i).setExpanded(True)
        levels_list = getattr(self, '_project_levels_list', None)
        if levels_list is not None:
            levels_list.clear()
            for name, z in _levels(self.doc):
                item = QListWidgetItem(f'{name}   {z:+.2f} m')
                item.setData(Qt.ItemDataRole.UserRole, name)
                levels_list.addItem(item)
        materials_list = getattr(self, '_project_materials_list', None)
        if materials_list is not None:
            materials_list.clear()
            for _mid, name, count in used_materials(self.doc):
                materials_list.addItem(f'{name}   ×{count}')

    def _project_tree_clicked(self, item):
        entity_id = item.data(0, Qt.ItemDataRole.UserRole)
        level = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if level:
            self._activate_level_by_name(level)
        if entity_id and entity_id in self.doc.entities:
            self.doc.select([entity_id])
            self.refresh_inspector()
            self._redraw_views(all_views=True)

    def _activate_level_by_name(self, name):
        selector = getattr(self, 'floor_selector', None)
        if selector is None or not name:
            return
        for i in range(selector.count()):
            data = selector.itemData(i)
            if isinstance(data, (tuple, list)) and data and str(data[0]) == str(name):
                if selector.currentIndex() != i:
                    selector.setCurrentIndex(i)
                return

    def _place_plumbing_point(self, point_type, x, y):
        """Add a plumbing point; pipes re-route automatically from the points."""
        from archforge.mep.plumbing import POINT_TYPES, route_plumbing_cached
        z = float(self.doc.work_plane.origin[2])
        if point_type == 'solar_heater':
            z = max([float(v) for v in self.doc.levels.values()] + [z]) + 3.0   # on the roof
        label = POINT_TYPES[point_type][0]
        point = Entity('plumbing_point', {'x': float(x), 'y': float(y), 'z': z, 'point_type': point_type}, name=label)
        self.stack.execute(AddEntity(point))
        self._redraw_views(all_views=True)
        report = route_plumbing_cached(self.doc)['report']
        extra = f" · χωρίς σύνδεση: {len(report['unserved'])}" if report['unserved'] else ''
        self.statusBar().showMessage(
            f"{label} · κρύο {report['cold_m']:.1f} m, ζεστό {report['hot_m']:.1f} m{extra} — προμελέτη, προς έλεγχο μηχανολόγου",
            7000)
        return point

    def _set_layer_visible(self, layer, visible):
        hidden = set(getattr(self.pbr_view, 'hidden_layers', set()))
        (hidden.discard if visible else hidden.add)(layer)
        self.pbr_view.hidden_layers = hidden
        self._redraw_views(all_views=True)

    def _set_wall_type(self, entity_id, wall_type):
        """Apply a wall assembly: sets the type and the matching total thickness."""
        from archforge.architecture.wall_types import total_thickness
        entity = self.doc.get(entity_id)
        if entity.params.get('wall_type', 'generic') == wall_type:
            return
        changes = {'wall_type': str(wall_type)}
        thickness = total_thickness(wall_type)
        if thickness > 0:
            changes['thickness'] = thickness
        self.stack.execute(UpdateEntity(entity_id, changes))
        self._redraw_views(all_views=True)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.refresh_inspector)   # rebuild the form outside the combo's signal

    def _seed_core_library(self):
        """Build the shipped core library into the local store (first run only)."""
        from archforge.library.catalog import seed_core_library
        try:
            built = seed_core_library()
        except Exception as exc:
            self.statusBar().showMessage(f'Βασική βιβλιοθήκη: {exc}', 6000)
            return
        if built:
            self.statusBar().showMessage(f'Βασική βιβλιοθήκη: {len(built)} αντικείμενα έτοιμα', 5000)
        self._refresh_library_panel()

    def _refresh_library_panel(self):
        listing = getattr(self, '_library_assets_list', None)
        if listing is not None:
            from PySide6.QtWidgets import QListWidgetItem
            from archforge.library import assets
            from archforge.library.catalog import CATEGORIES
            listing.clear()
            records = assets.list_assets()

            def category(r):
                cat = (r.get('category') or ['Εισαγωγές'])[0]
                return (CATEGORIES.index(cat) if cat in CATEGORIES else len(CATEGORIES), cat)
            current = None
            for r in sorted(records, key=lambda r: (category(r), r['name'].lower())):
                cat = category(r)[1]
                if cat != current:
                    header = QListWidgetItem(f'— {cat} —')
                    header.setFlags(Qt.ItemFlag.NoItemFlags)
                    listing.addItem(header)
                    current = cat
                w, d, h = (v * 100 for v in r['size'])
                item = QListWidgetItem(f"  {r['name']}  {w:.0f}×{d:.0f}×{h:.0f} cm")
                item.setData(Qt.ItemDataRole.UserRole, r['id'])
                if r['provenance'].get('source') == 'home-designer-calib':
                    item.setToolTip('Home Designer — μόνο τοπική χρήση, δεν διανέμεται')
                elif r['provenance'].get('attribution'):
                    item.setToolTip(f"{r['provenance'].get('license', '')}: {r['provenance']['attribution']}")
                listing.addItem(item)
        mats = getattr(self, '_library_materials_list', None)
        if mats is not None and mats.count() == 0:
            from PySide6.QtWidgets import QListWidgetItem
            from PySide6.QtGui import QColor
            for category_name in material_categories():
                header = QListWidgetItem(f'— {category_name} —')
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                mats.addItem(header)
                for material_id, spec in materials_in_category(category_name):
                    item = QListWidgetItem(f"  ■ {spec['name']}")
                    item.setData(Qt.ItemDataRole.UserRole, material_id)
                    item.setForeground(QColor(str(spec['color'])))
                    mats.addItem(item)

    def _library_item_count(self):
        listing = getattr(self, '_library_assets_list', None)
        if listing is None:
            return 0
        return sum(1 for i in range(listing.count()) if listing.item(i).data(Qt.ItemDataRole.UserRole))

    def _place_library_by_name(self, name):
        from archforge.library import assets
        for r in assets.list_assets():
            if r['name'] == name:
                return self._choose_library_asset(r['id'])
        self._seed_core_library()
        for r in assets.list_assets():
            if r['name'] == name:
                return self._choose_library_asset(r['id'])
        self.statusBar().showMessage(f'{name}: δεν βρέθηκε στη βιβλιοθήκη', 4000)
        return None

    def _start_structural_preset(self, tool, preset):
        self.plan_view.controller.structural_preset = dict(preset)
        self._set_active_tool(tool)
        self.statusBar().showMessage('Διατομή ' + ' × '.join(f"{v * 100:.0f}" for v in preset.values()) + ' cm — κλικ στην κάτοψη', 5000)

    def _apply_material_to_selection(self, material_id):
        if not material_id or len(self.doc.selection) != 1:
            self.statusBar().showMessage('Επιλέξτε ένα αντικείμενο για να εφαρμόσετε το υλικό', 3000)
            return False
        entity_id = self.doc.selection[0]
        entity = self.doc.get(entity_id)
        changes = {'material_id': str(material_id)}
        if entity.kind in ('library_object', 'cabinet'):
            changes['surface_materials'] = {}
        self.stack.execute(UpdateEntity(entity_id, changes))
        self._redraw_views(all_views=True)
        self.refresh_inspector()
        self.statusBar().showMessage(f"{MATERIAL_PRESETS[material_id]['name']} → {entity.name or entity.kind}", 3000)
        return True

    def _choose_library_asset(self, asset_id=None):
        from archforge.library import assets
        records = assets.list_assets()
        if not records:
            QMessageBox.information(
                self, 'Βιβλιοθήκη', 'Η βιβλιοθήκη είναι άδεια. Εισαγάγετε πρώτα αντικείμενα από κατάλογο.')
            return None
        if asset_id is None:
            rows = []
            for r in records:
                w, d, h = (v * 100 for v in r['size'])
                tag = '  · HD (τοπικά)' if r['provenance'].get('source') == 'home-designer-calib' else ''
                rows.append((f"{r['name']}   {w:.0f}×{d:.0f}×{h:.0f} cm{tag}", r['id']))
            chosen = self._library_list_dialog('Βιβλιοθήκη — τοποθέτηση αντικειμένου', rows)
            if not chosen:
                return None
            asset_id = chosen[0]
        self._pending_library_asset = next(r for r in records if r['id'] == asset_id)
        self._start_site_tool(
            'library_place', f"{self._pending_library_asset['name']}: κλικ στην κάτοψη — Esc για τέλος")
        return asset_id

    def _place_library_object(self, x, y):
        record = getattr(self, '_pending_library_asset', None)
        if record is None:
            return None
        w, d, h = record['size']
        obj = Entity('library_object', {
            'x': float(x), 'y': float(y), 'z': float(self.doc.work_plane.origin[2]),
            'rotation': 0.0, 'width': float(w), 'depth': float(d), 'height': float(h),
            'uniform': 1.0, 'asset': record['id'],
        }, name=record['name'])
        self.stack.execute(AddEntity(obj))
        self._redraw_views(all_views=True)
        self.statusBar().showMessage(
            f"{record['name']}: μέγεθος/περιστροφή στις Ιδιότητες (uniform=1 κρατά αναλογίες) — κλικ για επόμενο, Esc για τέλος",
            6000)
        return obj

    def _choose_sun_time(self):
        current = self.pbr_view._sun or (11.0, 6)
        hour, ok = QInputDialog.getDouble(self, 'Ήλιος', 'Ώρα (ηλιακή, 0–24):', current[0], 0.0, 24.0, 2)
        if not ok:
            return
        month, ok = QInputDialog.getInt(self, 'Ήλιος', 'Μήνας (1–12):', current[1], 1, 12, 1)
        if not ok:
            return
        self.pbr_view.set_sun(hour, month)
        el, az = self.pbr_view.sun_angles()
        self.statusBar().showMessage(f'Ήλιος: ύψος {el:.1f}°, αζιμούθιο {az:.0f}°', 5000)

    def _cancel_interactions(self):
        self.plan_view.controller.cancel()
        self.plan_view._mouse_down = False
        self.plan_view._view_drag = None
        self.plan_view.redraw()
        for view in (self.pbr_view, self.structural_view):
            view.cancel_interaction()
        self.statusBar().showMessage('Ακυρώθηκε', 2000)

    def _show_3d_view(self):
        """Bring the 3D Scene forward (unless 2D + 3D are side by side)."""
        central = getattr(self, '_central_tabs', None)
        simultaneous = getattr(self, '_simultaneous_action', None)
        if central is not None and not (simultaneous is not None and simultaneous.isChecked()):
            if central.count() > 1:
                central.setCurrentIndex(1)
        self.tabs.setCurrentWidget(self.pbr_view)
        self.pbr_view.activate()

    def _start_view_line_tool(self, kind):
        """Section / interior camera: drag a line in the 2D plan."""
        central = getattr(self, '_central_tabs', None)
        simultaneous = getattr(self, '_simultaneous_action', None)
        if central is not None and not (simultaneous is not None and simultaneous.isChecked()):
            central.setCurrentIndex(0)
        self.view = self.plan_view
        tool = 'view_section' if kind == 'section' else 'view_camera'
        self.plan_view.controller.set_tool(tool)
        self.statusBar().showMessage(
            'Τομή: τράβηξε γραμμή στην κάτοψη, από το σημείο κοπής προς την κατεύθυνση θέασης'
            if kind == 'section' else
            'Εσωτερική όψη: τράβηξε από το σημείο που στέκεσαι προς την κατεύθυνση που κοιτάς',
            8000,
        )

    def _apply_view_line(self, kind, x1, y1, x2, y2):
        try:
            self._show_3d_view()
            self.pbr_view.set_view_line(kind, x1, y1, x2, y2, z=float(self.doc.work_plane.origin[2]))
        except ValueError as exc:
            self.statusBar().showMessage(str(exc), 5000)

    def _set_pbr_camera(self, mode):
        self._show_3d_view()
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

    def _build_mockup_workspace(self):
        """Install the approved mockup regions as real dockable Qt widgets."""
        self.workspace_docks = []

        project = QWidget(self)
        project_layout = QVBoxLayout(project)
        project_layout.setContentsMargins(6, 6, 6, 6)
        project_layout.addWidget(QLabel('PROJECT'))
        self.project_tree = QTreeWidget(project)
        self.project_tree.setHeaderHidden(True)
        root = QTreeWidgetItem(['Project'])
        root.addChild(QTreeWidgetItem(['Levels']))
        root.addChild(QTreeWidgetItem(['Materials']))
        self.project_tree.addTopLevelItem(root)
        root.setExpanded(True)
        project_layout.addWidget(self.project_tree)
        project_layout.addWidget(QLabel('Active level'))
        project_layout.addWidget(self.floor_selector)
        project_layout.addWidget(QLabel('Materials are applied to the selected semantic object.'))
        building_actions = QHBoxLayout()
        auto_floor_button = QPushButton('Auto Floors', project)
        auto_floor_button.clicked.connect(self._create_auto_floors)
        flat_roof_button = QPushButton('Flat Roof', project)
        flat_roof_button.clicked.connect(self._create_flat_roofs)
        building_actions.addWidget(auto_floor_button)
        building_actions.addWidget(flat_roof_button)
        project_layout.addLayout(building_actions)

        library = QWidget(self)
        library_layout = QVBoxLayout(library)
        library_layout.setContentsMargins(6, 6, 6, 6)
        library_layout.addWidget(QLabel('LIBRARY'))
        self.library_search = QLineEdit(library)
        self.library_search.setPlaceholderText('Search library…')
        library_layout.addWidget(self.library_search)
        self.library_list = QListWidget(library)
        for label in ('Doors', 'Windows', 'Openings', 'Stairs / Ramps', 'Structure', 'Furniture', 'Kitchen'):
            self.library_list.addItem(label)
        library_layout.addWidget(self.library_list)

        ai = QWidget(self)
        ai_layout = QVBoxLayout(ai)
        ai_layout.setContentsMargins(6, 6, 6, 6)
        ai_layout.addWidget(QLabel('AI ASSISTANT'))
        ai_layout.addWidget(QLabel('Optional assistant — human editing remains authoritative.'))
        self.ai_prompt = QLineEdit(ai)
        self.ai_prompt.setPlaceholderText('Describe an optional command…')
        ai_layout.addWidget(self.ai_prompt)
        self.ai_apply = QPushButton('Apply through CommandStack', ai)
        self.ai_apply.setEnabled(False)
        self.ai_apply.setToolTip('Reserved for optional AI commands using the same authoritative command path.')
        ai_layout.addWidget(self.ai_apply)
        ai_layout.addStretch(1)

        views = QWidget(self)
        views_layout = QHBoxLayout(views)
        views_layout.setContentsMargins(6, 6, 6, 6)
        views_layout.addWidget(QLabel('VIEWS / RENDERING STYLE'))
        for label, mode in (('Top', 'top'), ('Front', 'front'), ('Side', 'side'), ('ISO', 'iso30'), ('Eye', 'eye')):
            button = QPushButton(label, views)
            button.clicked.connect(lambda checked=False, m=mode: self._set_pbr_camera(m))
            views_layout.addWidget(button)
        views_layout.addWidget(QLabel('Render'))
        # Keep the compact toolbar selector and expose the same authoritative
        # render modes clearly in the mockup workspace.
        self.render_style_buttons = []
        for label, mode in (('PBR', 'pbr'), ('Technical', 'technical'), ('Glass', 'glass')):
            button = QPushButton(label, views)
            button.setCheckable(True)
            button.setChecked(self.render_technique.currentData() == mode)
            button.clicked.connect(
                lambda checked=False, m=mode: self._set_render_style_from_workspace(m)
            )
            views_layout.addWidget(button)
            self.render_style_buttons.append((button, mode))
        views_layout.addStretch(1)

        specs = (
            (WorkspaceDockSpec('project', 'Project / Levels / Materials', Qt.DockWidgetArea.LeftDockWidgetArea), project),
            (WorkspaceDockSpec('library', 'Library', Qt.DockWidgetArea.LeftDockWidgetArea), library),
            (WorkspaceDockSpec('ai', 'AI', Qt.DockWidgetArea.RightDockWidgetArea), ai),
            (WorkspaceDockSpec('views', 'Views / Rendering Style', Qt.DockWidgetArea.BottomDockWidgetArea), views),
        )
        for spec, widget in specs:
            self.workspace_docks.append(install_workspace_dock(self, spec, widget))

        self.dock.setWindowTitle('Properties')
        self.dock.setObjectName('workspace_dock_properties')
        self.workspace_docks.append(self.dock)
        self.tabifyDockWidget(self.workspace_docks[0], self.workspace_docks[1])
        self.workspace_docks[0].raise_()
        add_workspace_toggles(self.view_menu, self.workspace_docks)

    def _set_render_style_from_workspace(self, mode):
        index=self.render_technique.findData(str(mode))
        if index >= 0:
            self.render_technique.setCurrentIndex(index)
        for button, button_mode in getattr(self,'render_style_buttons',()):
            button.setChecked(button_mode == str(mode))

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
        params = dict(entity.params)
        if entity.kind == 'room_roof':
            # Roofs saved before the overhang field still get the editor.
            params.setdefault('overhang', 0.0)
        for key, value in params.items():
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
        if entity.kind == 'wall':
            from archforge.architecture.wall_types import WALL_TYPES, indicative_u, layers
            combo = QComboBox()
            for key, (label, _layers) in WALL_TYPES.items():
                combo.addItem(label, key)
            current_type = params.get('wall_type', 'generic')
            combo.setCurrentIndex(max(0, combo.findData(current_type)))
            combo.currentIndexChanged.connect(
                lambda _i, widget=combo, entity_id=eid: self._set_wall_type(entity_id, widget.currentData()))
            self.form.addRow('Τύπος τοίχου', combo)
            build_up = layers(current_type)
            if build_up:
                text = '<br>'.join(f'{name} {d * 100:g} cm' for name, d, _l, _c, _i in build_up)
                u = indicative_u(current_type)
                text += f'<br><i>U ≈ {u:.2f} W/m²K — ενδεικτικό (τυπικά λ, EN ISO 6946), όχι μελέτη ΚΕΝΑΚ</i>'
                label = QLabel(text)
                label.setWordWrap(True)
                self.form.addRow('Στρώσεις (έξω→μέσα)', label)
        if entity.kind in ('library_object', 'cabinet'):
            button = QPushButton('Object Modifier…')
            button.setToolTip('Διαστάσεις, υλικά ανά τμήμα και Sculpt του αντικειμένου')
            button.clicked.connect(lambda _=False, entity_id=eid: self._open_object_modifier(entity_id))
            self.form.addRow(button)

    def _commit_property(self, eid, key, value):
        try:
            entity = self.doc.get(eid)
            changes = {key: value}
            if entity.kind == 'library_object' and key in ('width', 'depth', 'height'):
                from archforge.library.objects import resized
                changes = resized(entity.params, key, value)
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
            base_idx=base_level_editor.findData(str(entity.params.get('base_level',self.doc.active_level_name())))
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
            level_idx=beam_level_editor.findData(str(entity.params.get('level',self.doc.active_level_name())))
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

    def _open_materials(self, entity_id, part_role=None):
        entity_id = str(entity_id)
        if entity_id not in self.doc.entities:
            return
        entity = self.doc.get(entity_id)
        supported = {
            'wall', 'floor', 'room_floor', 'room_roof', 'room_ceiling',
            'room_foundation', 'box', 'pod', 'stair', 'ramp',
            'structural_column', 'structural_beam',
            'mechanical_part', 'mesh', 'library_object', 'cabinet',
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
        elif entity.kind == 'library_object':
            from archforge.library.objects import asset_parts
            target = QComboBox(dialog)
            target.addItem('Όλο το αντικείμενο', 'all')
            for k, (role, color, name) in enumerate(asset_parts(entity.params), 1):
                target.addItem(f'Τμήμα {k}' + (f' — {name}' if name else '') + f'  ({color})', role)
            if part_role:
                index = target.findData(part_role)
                if index >= 0:
                    target.setCurrentIndex(index)
            layout.addWidget(QLabel('Εφαρμογή σε'))
            layout.addWidget(target)
        elif entity.kind == 'cabinet':
            from archforge.kitchen.cabinets import ROLE_NAMES
            target = QComboBox(dialog)
            target.addItem('Όλο το ντουλάπι', 'all')
            for role, label in ROLE_NAMES.items():
                target.addItem(label, role)
            if part_role:
                index = target.findData(part_role)
                if index >= 0:
                    target.setCurrentIndex(index)
            layout.addWidget(QLabel('Εφαρμογή σε'))
            layout.addWidget(target)
        self._materials_target = target  # reachable from tests

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
            if entity.kind in ('library_object', 'cabinet') and target is not None and target.currentData() != 'all':
                surface_map = entity.params.get('surface_materials') or {}
                return str(surface_map.get(str(target.currentData())) or entity.params.get('material_id', '') or '')
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
        elif entity.kind in ('library_object', 'cabinet') and target is not None and target.currentData() != 'all':
            role = str(target.currentData())
            surface_map = dict(entity.params.get('surface_materials') or {})
            surface_map[role] = str(material_id)
            changes['surface_materials'] = surface_map
            target_label = target.currentText().split('  (')[0]
        elif entity.kind in ('library_object', 'cabinet'):
            # Whole object: one finish everywhere, part overrides cleared.
            changes['material_id'] = str(material_id)
            changes['surface_materials'] = {}
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
            # Deleting the object that owned an in-progress PBR gesture must
            # release any stale WebGL pointer/orbit state before redrawing.
            if self.pbr_view.web_view is not None:
                self.pbr_view.web_view.page().runJavaScript(
                    "if (window.archforgeResetInteraction) window.archforgeResetInteraction();"
                )
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
            # Floors affect the shared building model, so refresh every live
            # representation (2D, PBR 3D and Structural), not only the active tab.
            self._redraw_views(all_views=True)
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

    def _update_plan_title(self):
        label = getattr(self, '_plan_title', None)
        if label is None:
            return
        name = self.doc.active_level_name()
        label.setText('Κάτοψη - ' + ('Ισόγειο' if name in ('Ground', 'XY') else name))

    def _on_document_changed(self):
        self._update_plan_title()
        self._refresh_project_tree()
        # Refresh every editor the human can currently see (e.g. 2D + 3D side
        # by side) so a committed edit appears without switching tabs. Hidden
        # editors refresh when they are shown.
        for view in (getattr(self, 'plan_view', None), getattr(self, 'pbr_view', None), getattr(self, 'structural_view', None)):
            if view is None or view is self.view or not view.isVisible():
                continue
            view.redraw()

    def _selection_from_view(self):
        self.refresh_inspector()

    def _redraw_views(self, *, all_views=False, fit_camera=False):
        targets=(self.plan_view,self.pbr_view,self.structural_view) if all_views else (self.view,)
        for view in targets:
            if isinstance(view, PBRViewport):
                # A normal redraw must preserve the human's orbit/zoom.
                # Camera fitting is explicit only (initial load / Fit command).
                view.redraw(force_full=bool(fit_camera))
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
        self.stack.listeners.append(self._on_document_changed)
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
