"""Numeric transform access, using the same commands as direct manipulation."""
import math
from PySide6.QtWidgets import QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox, QLabel, QHBoxLayout, QPushButton
from archforge.core.commands import CompositeCommand, MoveEntities, UpdateEntity
from archforge.core import object_ops

SCALE_KINDS = ('library_object', 'box')
TRANSFORM_KINDS = tuple(set(object_ops.USER_PLACED_KINDS) - {'door', 'window'}) + ('wall', 'pod', 'mechanical_part')

class TransformDialog(QDialog):
    def __init__(self, window, eid):
        super().__init__(window)
        self.window, self.eid = window, str(eid)
        e = window.doc.get(self.eid); p = e.params
        self.setWindowTitle('Transform — Μετακίνηση / Περιστροφή / Κλίμακα')
        form = QFormLayout(self); self.fields = {}
        self.xy = object_ops.pivot(window.doc, object_ops.group_ids(window.doc, self.eid))
        if e.kind == 'wall':
            self.xy = ((float(p['x1'])+float(p['x2']))/2, (float(p['y1'])+float(p['y2']))/2)
        elif e.kind == 'pod':
            self.xy = (float(p['cx']), float(p['cy']))
        zkey = 'floor_level' if e.kind == 'pod' else 'elevation' if e.kind == 'mep_terminal' else 'z'
        self.zkey = zkey
        self.angle = float(p.get('angle_deg', p.get('rotation', 0.)))
        if e.kind in ('wall', 'structural_beam'):
            self.angle = math.degrees(math.atan2(float(p['y2'])-float(p['y1']), float(p['x2'])-float(p['x1'])))
        values = [('x','Θέση X (m)',self.xy[0]), ('y','Θέση Y (m)',self.xy[1])]
        if zkey in p and e.kind not in ('stair','ramp','structural_column','structural_beam'):
            values.append(('z','Στάθμη (m)',float(p[zkey])))
        if e.kind not in ('mechanical_part', 'plant', *object_ops.POINT_KINDS):
            values.append(('rotation','Περιστροφή στο οριζόντιο επίπεδο (°)',self.angle))
        if e.kind in SCALE_KINDS:
            values.append(('scale','Ομοιόμορφη κλίμακα ×',1.))
        for key, label, value in values:
            spin = QDoubleSpinBox(self); spin.setRange(.001 if key=='scale' else -100000,100000)
            spin.setDecimals(3 if key != 'rotation' else 1); spin.setValue(value)
            spin.setSingleStep(.1 if key != 'rotation' else 15)
            self.fields[key] = spin; form.addRow(label,spin)
        mouse = QHBoxLayout()
        for action, label in (('move', 'Μετακίνηση με ποντίκι'), ('rotate', 'Περιστροφή με ποντίκι')):
            if action == 'rotate' and 'rotation' not in self.fields:
                continue
            button = QPushButton(label, self)
            button.clicked.connect(lambda _checked=False, tool=action: self.start_tool(tool))
            mouse.addWidget(button)
        form.addRow(mouse)
        form.addRow(QLabel('Οι αλλαγές εφαρμόζονται μαζί · μία αναίρεση με Ctrl+Z.'))
        self.error = QLabel(); self.error.setWordWrap(True); form.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Εφαρμογή')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Άκυρο')
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def start_tool(self, tool):
        self.reject()
        self.window._handle_object_context_action(self.eid, tool)

    def accept(self):
        doc = self.window.doc
        if self.eid not in doc.entities: return self.reject()
        e = doc.get(self.eid); p=e.params
        if e.locked:
            self.error.setText('Το αντικείμενο είναι κλειδωμένο.'); return
        ids=object_ops.group_ids(doc,self.eid)
        commands=[]
        pivot = object_ops.pivot(doc, ids)
        if e.kind == 'wall':
            pivot = ((float(p['x1'])+float(p['x2']))/2, (float(p['y1'])+float(p['y2']))/2)
        elif e.kind == 'pod':
            pivot = (float(p['cx']), float(p['cy']))
        dx=self.fields['x'].value()-pivot[0]; dy=self.fields['y'].value()-pivot[1]
        dz=self.fields['z'].value()-float(p[self.zkey]) if 'z' in self.fields else 0.
        if any(abs(v)>1e-9 for v in (dx,dy,dz)): commands.append(MoveEntities(ids,dx,dy,dz))
        current_angle = float(p.get('angle_deg', p.get('rotation', 0.)))
        if e.kind in ('wall', 'structural_beam'):
            current_angle = math.degrees(math.atan2(float(p['y2'])-float(p['y1']), float(p['x2'])-float(p['x1'])))
        angle=self.fields['rotation'].value()-current_angle if 'rotation' in self.fields else 0.
        if abs(angle)>1e-9:
            commands.append(object_ops.rotate_command(doc,self.eid,angle))
            # The pivot follows the translation; otherwise a combined edit drifts.
            commands[-1].pivot=(pivot[0]+dx,pivot[1]+dy)
        scale=self.fields['scale'].value() if 'scale' in self.fields else 1.
        if abs(scale-1)>1e-9:
            commands.append(UpdateEntity(self.eid,{k:float(p[k])*scale for k in ('width','depth','height')}))
        try:
            if commands: self.window.stack.execute(CompositeCommand(commands,label='Transform'))
        except (ValueError, PermissionError, KeyError) as exc:
            self.error.setText(str(exc)); return
        self.window.doc.select([self.eid]); self.window._redraw_views(all_views=True); self.window.refresh_inspector()
        super().accept()


def open_transform(window,eid):
    entity=window.doc.get(eid)
    if entity.kind in ('door','window'):
        # Hosted openings use their wall's offset/size controls, never detach from it.
        return window._open_object_properties(eid)
    dialog=TransformDialog(window,eid); window._transform_dialog=dialog
    dialog.show(); return dialog
