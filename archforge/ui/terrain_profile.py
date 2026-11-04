"""Terrain elevation profiles on the existing saved section lines.

Open from SectionPanel. Double click creates a design control, dragging a blue
control previews locally and commits once on release. Green survey records are
read-only. Numeric edits, drag edits and deletion use the same shared commands.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QGraphicsEllipseItem,
    QGraphicsItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QHeaderView)

from archforge.site.terrain_profiles import profile, edit_control, remove_control, edit_grade


class ProfileView(QGraphicsView):
    def __init__(self, editor):
        super().__init__(editor)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.editor = editor
        self.drag = None
        self.setBackgroundBrush(QColor('white'))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scale(40., -40.)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def wheelEvent(self, event):
        from archforge.ui.view_zoom import zoom_about
        zoom_about(self,event)

    def draw_profile(self, data, fit=False):
        self.drag = None
        scene = self.scene(); scene.clear()
        rows = data['samples']
        if not rows:
            return
        path = QPainterPath(QPointF(rows[0]['station'],rows[0]['z']))
        for row in rows[1:]:
            path.lineTo(row['station'],row['z'])
        pen = QPen(QColor('#82582e')); pen.setCosmetic(True); pen.setWidthF(2.)
        scene.addPath(path,pen)
        for kind,color in [('survey','#24814b'),('controls','#226fce')]:
            for row in data[kind]:
                item = QGraphicsEllipseItem(-5,-5,10,10)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                item.setPos(row['station'],row['z'])
                item.setBrush(QBrush(QColor(color)))
                item.setPen(QPen(QColor('white')))
                item.setData(0,row.get('id'))
                item.setToolTip(('Protected source' if kind=='survey' else 'Design control')+
                                f" · {row['station']:.3f} m / {row['z']:+.3f} m")
                scene.addItem(item)
        zs = [r['z'] for r in rows+data['survey']]
        lo,hi = data['range']
        low,high = min(zs),max(zs)
        if high-low < 1e-6:
            low,high = low-.5,high+.5
        grid_pen = QPen(QColor('#e2e6eb')); grid_pen.setCosmetic(True)
        for i in range(6):
            u = lo+(hi-lo)*i/5
            z = low+(high-low)*i/5
            scene.addLine(u,low,u,high,grid_pen).setZValue(-2)
            scene.addLine(lo,z,hi,z,grid_pen).setZValue(-2)
            for text,x,y in ((f'{u:.2f}',u,low-.3),(f'{z:+.2f}',lo-.7,z)):
                label = scene.addText(text)
                label.setDefaultTextColor(QColor('#647080'))
                label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                label.setPos(x,y)
        rect = QRectF(lo-.9,low-.7,hi-lo+1.5,high-low+1.2)
        scene.setSceneRect(rect)
        if fit:
            self.fitInView(rect,Qt.AspectRatioMode.KeepAspectRatio)

    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            q = self.mapToScene(event.position().toPoint())
            self.editor.commit(q.x(),q.y())
            event.accept(); return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self,event):
        item = self.itemAt(event.position().toPoint())
        if event.button()==Qt.MouseButton.LeftButton and item is not None and item.data(0):
            self.drag = item, str(item.data(0))
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        q = self.mapToScene(event.position().toPoint())
        if self.drag:
            self.drag[0].setPos(q)
            self.editor.distance.setValue(q.x()); self.editor.elevation.setValue(q.y())
            event.accept(); return
        self.editor.readout.setText(f'Distance {q.x():.3f} m · cursor elevation {q.y():+.3f} m')
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self.drag:
            item,identity = self.drag
            station,z = item.pos().x(),item.pos().y()
            self.drag = None
            self.editor.commit(station,z,identity)
            event.accept(); return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape and self.drag:
            self.drag = None; self.editor.refresh()
            event.accept(); return
        super().keyPressEvent(event)


class TerrainProfileDialog(QDialog):
    def __init__(self,window,section_id):
        super().__init__(window)
        self.window = window
        self.section_id = section_id
        self.control_id = None
        self.data = None
        self._choice_key = None
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle('Terrain elevation profiles')
        self.resize(1180,640)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.sections = QComboBox(); self.terrains = QComboBox()
        top.addWidget(QLabel('Section')); top.addWidget(self.sections,1)
        top.addWidget(QLabel('Terrain')); top.addWidget(self.terrains,1)
        new = QPushButton('New section in plan'); top.addWidget(new)
        new.clicked.connect(self.new_section)
        fit = QPushButton('Fit'); top.addWidget(fit)
        fit.clicked.connect(lambda: self.refresh(fit=True))
        layout.addLayout(top)
        split = QSplitter(); layout.addWidget(split,1)
        self.plot = ProfileView(self); split.addWidget(self.plot)
        self.table = QTableWidget(0,5)
        self.table.setHorizontalHeaderLabels(['Source','Distance (m)','Source Z (m)','Model Z (m)','Absolute Z (m)'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.pick_row)
        split.addWidget(self.table); split.setSizes([650,500])
        row = QHBoxLayout()
        self.distance = QDoubleSpinBox(); self.elevation = QDoubleSpinBox()
        for spin in (self.distance,self.elevation):
            spin.setDecimals(6); spin.setRange(-1e9,1e9); spin.setSuffix(' m')
        row.addWidget(QLabel('Distance')); row.addWidget(self.distance)
        row.addWidget(QLabel('Model elevation Z')); row.addWidget(self.elevation)
        self.add = QPushButton('Add design point'); self.apply = QPushButton('Update design point')
        self.delete = QPushButton('Delete design point')
        self.add.clicked.connect(lambda: self.commit(self.distance.value(),self.elevation.value()))
        self.apply.clicked.connect(lambda: self.commit(self.distance.value(),self.elevation.value(),self.control_id))
        self.delete.clicked.connect(self.delete_selected)
        for b in (self.add,self.apply,self.delete): row.addWidget(b)
        layout.addLayout(row)
        grade_row = QHBoxLayout()
        self.grade = QDoubleSpinBox(); self.grade.setDecimals(6); self.grade.setRange(-1e9,1e9); self.grade.setSuffix(' %')
        grade_row.addWidget(QLabel('Average grade from preceding source/design point')); grade_row.addWidget(self.grade)
        grade_button = QPushButton('Set target from average grade'); grade_row.addWidget(grade_button)
        grade_button.clicked.connect(self.apply_grade)
        grade_row.addStretch(1); layout.addLayout(grade_row)
        self.readout = QLabel(); layout.addWidget(self.readout)
        note = QLabel('Brown: sampled model field · green: protected source records · blue: editable design points. '
                      'Double click to add; drag blue points; Esc cancels a drag. One Undo per committed edit. '
                      'Interpolation between records is not measured survey data; this height field does not represent vertical faces. '
                      'The section drawing shows building/pool excavation cuts; this profile shows the terrain field.')
        note.setWordWrap(True); layout.addWidget(note)
        self.sections.currentIndexChanged.connect(self.change_section)
        self.terrains.currentIndexChanged.connect(lambda _i: self.refresh(fit=True))
        self._stack = window.stack
        self._listener = lambda: self.refresh()
        self._stack.listeners.append(self._listener)
        self.destroyed.connect(lambda *_: self._detach())
        self.refresh(fit=True)

    def _detach(self):
        if self._listener in self._stack.listeners:
            self._stack.listeners.remove(self._listener)

    def _choices(self):
        doc = self.window.doc
        old = self.terrains.currentData()
        for combo,kind,selected in ((self.sections,'section_line',self.section_id),(self.terrains,'terrain',old)):
            combo.blockSignals(True); combo.clear()
            for e in doc.entities.values():
                if e.kind==kind:
                    combo.addItem(e.name or e.id,e.id)
            i = combo.findData(selected)
            combo.setCurrentIndex(i if i>=0 else (0 if combo.count() else -1))
            combo.blockSignals(False)
        self.section_id = self.sections.currentData()

    def change_section(self,_i):
        self.section_id = self.sections.currentData()
        self.refresh(fit=True)

    def new_section(self):
        self.hide()
        self.window._start_view_line_tool('section')

    def refresh(self,fit=False):
        if self._stack is not self.window.stack:
            self._detach(); self._stack = self.window.stack; self._stack.listeners.append(self._listener)
        self._choices()
        self.control_id = None; self.apply.setEnabled(False); self.delete.setEnabled(False)
        try:
            if self.terrains.currentData() is None or self.section_id is None:
                raise ValueError('Create a terrain and draw a section line first.')
            self.data = profile(self.window.doc,self.terrains.currentData(),self.section_id)
        except (ValueError,KeyError) as exc:
            self.data = None; self.plot.scene().clear(); self.table.setRowCount(0)
            self.add.setEnabled(False); self.readout.setText(str(exc)); return
        self.add.setEnabled(self.data['range'] is not None)
        choice = self.terrains.currentData(),self.section_id
        if self._choice_key != choice and self.data['samples']:
            lo,hi = self.data['range']
            middle = min(self.data['samples'],key=lambda r:abs(r['station']-(lo+hi)/2))
            self.distance.setValue(middle['station']); self.elevation.setValue(middle['z'])
        self._choice_key = choice
        self.plot.draw_profile(self.data,fit)
        self.table.blockSignals(True)
        records = sorted([dict(r,kind='Survey' if r['source']=='points' else 'Terrace') for r in self.data['survey']]+
                         [dict(r,kind='Design') for r in self.data['controls']],key=lambda r:r['station'])
        self.table.setRowCount(len(records))
        from archforge.site.terrain import terrain_heights,barriers,green_roofs
        params = self.window.doc.get(self.terrains.currentData()).params
        model = terrain_heights(params,[(r['x'],r['y']) for r in records],barriers(self.window.doc),green_roofs(self.window.doc))
        ref = self.data['altitude_ref']
        for i,(r,z) in enumerate(zip(records,model)):
            values = [r['kind'],f"{r['station']:.6f}",f"{r['z']:+.6f}",f'{z:+.6f}',
                      'Datum not set' if ref is None else f'{z+ref:+.6f}']
            for j,value in enumerate(values):
                item = QTableWidgetItem(value); item.setData(Qt.ItemDataRole.UserRole,r)
                item.setToolTip(f"Plan X {r['x']:.6f} m / Y {r['y']:.6f} m")
                if abs(z-r['z'])>1e-6:
                    item.setToolTip(item.toolTip()+'\nRecorded source and current model field differ. The source record is unchanged.')
                    item.setForeground(QColor('#a34018'))
                self.table.setItem(i,j,item)
        self.table.blockSignals(False)
        self.readout.setText('No intersection with this terrain.' if self.data['range'] is None else
                             'Select a source/control row, or double click the model profile to add a design point.')

    def pick_row(self):
        row = self.table.currentRow()
        if row<0 or self.table.item(row,0) is None: return
        record = self.table.item(row,0).data(Qt.ItemDataRole.UserRole)
        self.control_id = record.get('id')
        self.distance.setValue(record['station']); self.elevation.setValue(record['z'])
        self.apply.setEnabled(self.control_id is not None); self.delete.setEnabled(self.control_id is not None)
        if self.control_id is None:
            self.readout.setText('Protected source record. Add a design point elsewhere; source records cannot be edited here.')

    def commit(self,station,z,control_id=None):
        try:
            command = edit_control(self.window.doc,self.terrains.currentData(),self.section_id,station,z,control_id)
            self.window.stack.execute(command)
            self.window._redraw_views(all_views=True)
            self.refresh()
            return True
        except (ValueError,KeyError,PermissionError,RuntimeError) as exc:
            self.refresh(); self.readout.setText(str(exc)); return False

    def delete_selected(self):
        if self.control_id is None: return
        try:
            self.window.stack.execute(remove_control(self.window.doc,self.terrains.currentData(),self.control_id))
            self.window._redraw_views(all_views=True); self.refresh()
        except (ValueError,KeyError,PermissionError,RuntimeError) as exc:
            self.readout.setText(str(exc))

    def apply_grade(self):
        try:
            command = edit_grade(self.window.doc,self.terrains.currentData(),self.section_id,
                                 self.distance.value(),self.grade.value(),self.control_id)
            self.window.stack.execute(command)
            self.window._redraw_views(all_views=True); self.refresh()
        except (ValueError,KeyError,PermissionError,RuntimeError) as exc:
            self.readout.setText(str(exc))


def open_profile(window,section_id):
    previous = getattr(window,'_terrain_profile_dialog',None)
    if previous is not None:
        previous.close()
    dialog = TerrainProfileDialog(window,section_id)
    window._terrain_profile_dialog = dialog
    dialog.destroyed.connect(lambda *_: setattr(window,'_terrain_profile_dialog',None)
                             if getattr(window,'_terrain_profile_dialog',None) is dialog else None)
    dialog.show()
    return dialog
