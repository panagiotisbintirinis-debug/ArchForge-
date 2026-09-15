from __future__ import annotations
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction,QKeySequence
from PySide6.QtWidgets import QMainWindow,QToolBar,QDockWidget,QWidget,QFormLayout,QDoubleSpinBox,QLabel,QTabWidget,QStatusBar,QFileDialog,QMessageBox
from archforge.core.model import Document
from archforge.core.commands import CommandStack,UpdateEntity,CreateRoomFloors
from .plan_view import PlanView
from .ortho_view import OrthoView
from .viewport_3d import Viewport3D

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('ArchForge Development');self.resize(1400,900);self.doc=Document();self.stack=CommandStack(self.doc);self.current_path=None
        self.tabs=QTabWidget();self.plan_view=PlanView(self.doc,self.stack);self.front_view=OrthoView(self.doc,self.stack,'XZ');self.side_view=OrthoView(self.doc,self.stack,'YZ')
        self.view_3d=Viewport3D(self.doc,self.stack)
        self.tabs.addTab(self.plan_view,'XY PLAN');self.tabs.addTab(self.front_view,'XZ FRONT');self.tabs.addTab(self.side_view,'YZ SIDE');self.tabs.addTab(self.view_3d,'3D PERSPECTIVE');self.setCentralWidget(self.tabs);self.view=self.plan_view;self.setStatusBar(QStatusBar())
        for v in (self.plan_view,self.front_view,self.side_view,self.view_3d):v.statusChanged.connect(self.statusBar().showMessage);v.selectionChangedByView.connect(self._selection_from_view)
        self.tabs.currentChanged.connect(self._on_tab_changed);self._build_toolbar();self._build_inspector();self.refresh_inspector()
    def _on_tab_changed(self, idx):
        widgets=[self.plan_view,self.front_view,self.side_view,self.view_3d]
        if 0<=idx<len(widgets):self.view=widgets[idx]
        self._redraw_views()
    def _set_active_tool(self, tool):
        if hasattr(self.view, 'set_tool'):
            self.view.set_tool(tool)
    def _build_toolbar(self):
        tb=QToolBar('Tools');tb.setMovable(False);self.addToolBar(tb)
        for text,tool,key in [('Select','select','S'),('Wall','wall','W'),('Door','door','D'),('Window','window','N'),('Move','move','G'),('Stretch','stretch','T'),('Rotate','rotate','R')]:
            a=QAction(text,self);a.setShortcut(QKeySequence(key));a.triggered.connect(lambda checked=False,t=tool:self._set_active_tool(t));tb.addAction(a)
        sc=QAction('Sculpt 3D',self);sc.setShortcut(QKeySequence('C'));sc.triggered.connect(lambda:self.view_3d.set_tool('sculpt'));tb.addAction(sc)
        tb.addSeparator();af=QAction('Auto Floors',self);af.triggered.connect(self._create_auto_floors);tb.addAction(af)
        tb.addSeparator();au=QAction('Undo',self);au.setShortcut(QKeySequence.StandardKey.Undo);au.triggered.connect(self._undo);tb.addAction(au);ar=QAction('Redo',self);ar.setShortcut(QKeySequence.StandardKey.Redo);ar.triggered.connect(self._redo);tb.addAction(ar);tb.addSeparator();sv=QAction('Save',self);sv.setShortcut(QKeySequence.StandardKey.Save);sv.triggered.connect(self.save);tb.addAction(sv);op=QAction('Open',self);op.setShortcut(QKeySequence.StandardKey.Open);op.triggered.connect(self.open);tb.addAction(op);stl_act=QAction('Export STL',self);stl_act.triggered.connect(self.export_stl);tb.addAction(stl_act)
    def _build_inspector(self):
        self.dock=QDockWidget('Inspector',self);self.dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea|Qt.DockWidgetArea.RightDockWidgetArea);self.inspector=QWidget();self.form=QFormLayout(self.inspector);self.dock.setWidget(self.inspector);self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.dock)
    def _clear_form(self):
        while self.form.rowCount():self.form.removeRow(0)
    def refresh_inspector(self):
        self._clear_form()
        if len(self.doc.selection)!=1:self.form.addRow(QLabel(f'{len(self.doc.selection)} selected'));return
        eid=self.doc.selection[0];e=self.doc.get(eid);self.form.addRow('Type',QLabel(e.kind));self.form.addRow('Name',QLabel(e.name or e.kind.title()))
        if e.parent_id and e.parent_id in self.doc.entities:
            host=self.doc.get(e.parent_id);self.form.addRow('Host',QLabel(host.name or f'{host.kind.title()} {host.id[:8]}'))
        for k,v in e.params.items():
            if isinstance(v,(int,float)):
                sp=QDoubleSpinBox();sp.setDecimals(4);sp.setRange(-1e6,1e6);sp.setValue(float(v));sp.setSingleStep(.1);sp.editingFinished.connect(lambda key=k,widget=sp:self._commit_property(eid,key,widget.value()));self.form.addRow(k,sp)
            elif e.kind=='room_floor' and k=='room_signature':self.form.addRow('Room',QLabel(str(v)))
    def _commit_property(self,eid,key,value):
        try:self.stack.execute(UpdateEntity(eid,{key:value}));self._redraw_views()
        except Exception as exc:QMessageBox.warning(self,'Invalid value',str(exc));self.refresh_inspector()
    def _create_auto_floors(self):
        faces=self.doc.active_room_faces()
        if not faces:
            self.statusBar().showMessage('No closed rooms on the current work plane',4000);return
        existing={e.params.get('room_signature') for e in self.doc.entities.values() if e.kind=='room_floor'}
        signatures=[f.signature for f in faces if f.signature not in existing]
        if not signatures:
            self.statusBar().showMessage('All current rooms already have automatic floors',4000);return
        try:
            self.stack.execute(CreateRoomFloors(signatures));self._redraw_views();self.refresh_inspector();self.statusBar().showMessage(f'Created {len(signatures)} automatic floor(s)',4000)
        except Exception as exc:QMessageBox.warning(self,'Auto Floors',str(exc))
    def _selection_from_view(self):self._redraw_views();self.refresh_inspector()
    def _redraw_views(self):
        for v in (self.plan_view,self.front_view,self.side_view,self.view_3d):v.redraw()
    def _undo(self):self.stack.undo();self._redraw_views();self.refresh_inspector()
    def _redo(self):self.stack.redo();self._redraw_views();self.refresh_inspector()
    def save(self):
        path=self.current_path
        if not path:path,_=QFileDialog.getSaveFileName(self,'Save ArchForge Project','','ArchForge Project (*.archforge)')
        if path:
            if not path.lower().endswith('.archforge'):path+='.archforge'
            self.doc.save(path);self.current_path=path;self.statusBar().showMessage(f'Saved {os.path.basename(path)}',3000)
    def open(self):
        path,_=QFileDialog.getOpenFileName(self,'Open ArchForge Project','','ArchForge Project (*.archforge)')
        if not path:return
        try:
            self.doc=Document.load(path);self.stack=CommandStack(self.doc);self.plan_view.rebind(self.doc,self.stack);self.front_view.rebind(self.doc,self.stack);self.side_view.rebind(self.doc,self.stack);self.view_3d.rebind(self.doc,self.stack);self.current_path=path;self._redraw_views();self.refresh_inspector()
        except Exception as exc:QMessageBox.critical(self,'Open failed',str(exc))
    def export_stl(self):
        from archforge.geometry.fabrication import export_document_stl
        path,_=QFileDialog.getSaveFileName(self,'Export STL for Fabrication / 3D Printing','','Stereolithography (*.stl)')
        if not path:return
        if not path.lower().endswith('.stl'):path+='.stl'
        try:
            scope=list(self.doc.selection) if self.doc.selection else None
            count=export_document_stl(self.doc,path,entity_ids=scope,binary=True)
            self.statusBar().showMessage(f'Exported {count} triangles to {os.path.basename(path)}',4000)
        except Exception as exc:QMessageBox.warning(self,'Fabrication Gate Failed',f'Cannot export STL: {exc}')
