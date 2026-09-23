from __future__ import annotations

import copy
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QDockWidget, QWidget, QFormLayout, QDoubleSpinBox,
    QLabel, QTabWidget, QStatusBar, QFileDialog, QMessageBox,
)

from archforge.core.model import Document
from archforge.core.commands import CommandStack, UpdateEntity, CreateRoomFloors
from .plan_view import PlanView
from .ortho_view import OrthoView
from .viewport_3d import Viewport3D


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
        self.front_view = OrthoView(self.doc, self.stack, 'XZ')
        self.side_view = OrthoView(self.doc, self.stack, 'YZ')
        self.view_3d = Viewport3D(self.doc, self.stack)
        self.tabs.addTab(self.plan_view, 'XY PLAN')
        self.tabs.addTab(self.front_view, 'XZ FRONT')
        self.tabs.addTab(self.side_view, 'YZ SIDE')
        self.tabs.addTab(self.view_3d, '3D PERSPECTIVE')
        self.setCentralWidget(self.tabs)
        self.view = self.plan_view
        self.setStatusBar(QStatusBar())
        for view in (self.plan_view, self.front_view, self.side_view, self.view_3d):
            view.statusChanged.connect(self.statusBar().showMessage)
            view.selectionChangedByView.connect(self._selection_from_view)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._build_toolbar()
        self._build_inspector()
        self.refresh_inspector()

    def _on_tab_changed(self, idx):
        widgets = [self.plan_view, self.front_view, self.side_view, self.view_3d]
        if 0 <= idx < len(widgets):
            self.view = widgets[idx]
        self._redraw_views()

    def _set_active_tool(self, tool):
        if hasattr(self.view, 'set_tool'):
            self.view.set_tool(tool)

    def _build_toolbar(self):
        toolbar = QToolBar('Tools')
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, tool, key in [
            ('Select', 'select', 'S'), ('Wall', 'wall', 'W'), ('Door', 'door', 'D'),
            ('Window', 'window', 'N'), ('Move', 'move', 'G'), ('Stretch', 'stretch', 'T'),
            ('Rotate', 'rotate', 'R'),
        ]:
            action = QAction(text, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(lambda checked=False, t=tool: self._set_active_tool(t))
            toolbar.addAction(action)
        sculpt = QAction('Sculpt 3D', self)
        sculpt.setShortcut(QKeySequence('C'))
        sculpt.triggered.connect(lambda: self.view_3d.set_tool('sculpt'))
        toolbar.addAction(sculpt)
        toolbar.addSeparator()
        auto_floors = QAction('Auto Floors', self)
        auto_floors.triggered.connect(self._create_auto_floors)
        toolbar.addAction(auto_floors)
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

    def _selection_from_view(self):
        sender = self.sender()
        if sender is self.view_3d:
            self.view_3d.refresh_selection()
        self.refresh_inspector()

    def _redraw_views(self, *, all_views=False):
        targets=(self.plan_view,self.front_view,self.side_view,self.view_3d) if all_views else (self.view,)
        for view in targets:
            if view is self.view_3d:
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

    def _replace_project(self, doc, path=None):
        self.doc = doc
        self.stack = CommandStack(self.doc)
        for view in (self.plan_view, self.front_view, self.side_view, self.view_3d):
            view.rebind(self.doc, self.stack)
        self.current_path = path
        self._mark_clean()
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
