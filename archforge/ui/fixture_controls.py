"""Mouse controls with read-only values: live view preview, one command on release."""
import math

from PySide6.QtCore import Qt, QPointF, QObject, QEvent, QSignalBlocker
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QDial, QLabel, QWidget, QHBoxLayout


class CompassDial(QDial):
    """Bearing knob: north at the top and clockwise degrees, matching the light's aim."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0,359);self.setWrapping(True);self.setFixedSize(84,84)
        self.setAccessibleName('Προσανατολισμός φωτιστικού')

    def paintEvent(self, event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        c=QPointF(self.width()/2,self.height()/2);r=min(self.width(),self.height())/2-15
        p.setPen(QPen(QColor('#728197'),1.5));p.setBrush(QColor('#eef2f7'));p.drawEllipse(c,r,r)
        for label,dx,dy in [('Β',0,-1),('Α',1,0),('Ν',0,1),('Δ',-1,0)]:
            p.drawText(int(c.x()+dx*(r+9)-6),int(c.y()+dy*(r+9)-7),12,14,Qt.AlignCenter,label)
        a=math.radians(self.value());tip=QPointF(c.x()+math.sin(a)*r*.85,c.y()-math.cos(a)*r*.85)
        p.setPen(QPen(QColor('#d17810'),3));p.drawLine(c,tip)
        p.setBrush(QColor('#d17810'));p.drawEllipse(tip,3,3)
        p.end()

    def _point(self,event):
        dx=event.position().x()-self.width()/2;dy=event.position().y()-self.height()/2
        if math.hypot(dx,dy)>3:self.setValue(round(math.degrees(math.atan2(dx,-dy)))%360)

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.setFocus();self.setSliderDown(True);self._point(event);event.accept()
        else:super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.isSliderDown():self._point(event);event.accept()
        else:super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self.isSliderDown():
            self._point(event);self.setSliderDown(False);event.accept()
        else:super().mouseReleaseEvent(event)


def _view_call(window, method, *args):
    view=getattr(window,'pbr_view',None)
    fn=getattr(view,method,None)
    if fn is not None:
        try:fn(*args)
        except RuntimeError:pass             # a property widget can be destroyed with its whole window


class _CancelGesture(QObject):
    def eventFilter(self,control,event):
        if ((event.type()==QEvent.KeyPress and event.key()==Qt.Key_Escape)
                or event.type()==QEvent.FocusOut) and control.isSliderDown():
            control._fixture_cancelled=True
            control.setSliderDown(False)
            return event.type()==QEvent.KeyPress
        return False


def bind_control(window,eid,control,label,key,to_value,commit,suffix=' %'):
    """Preview is view-owned; the Document changes once on release, also for keyboard steps."""
    def shown(value):label.setText(f'{value}{suffix}')
    def finish_value(value):
        entity=window.doc.entities.get(eid)
        if entity is not None and entity.params.get(key,1 if 'level' in key else 0)!=to_value(value):
            commit(to_value(value))
    def start():
        control._fixture_initial=control.value();control._fixture_cancelled=False
    def changed(value):
        shown(value)
        if control.isSliderDown():
            _view_call(window,'preview_fixture_control',eid,{key:to_value(value)})
        else:finish_value(value)
    def finish():
        _view_call(window,'clear_fixture_control_preview',eid)
        if getattr(control,'_fixture_cancelled',False):
            with QSignalBlocker(control):control.setValue(control._fixture_initial)
            shown(control.value());control._fixture_cancelled=False
        else:finish_value(control.value())
    control.sliderPressed.connect(start)
    control.valueChanged.connect(changed)
    control.sliderReleased.connect(finish)
    watcher=_CancelGesture(control);control.installEventFilter(watcher);control._fixture_watcher=watcher
    control.destroyed.connect(lambda:_view_call(window,'clear_fixture_control_preview',eid))


def add_aim_rotors(window,eid):
    p=window.doc.get(eid).params
    from archforge.ui.light_properties import _set_aim
    for key,name,label,maximum in [('aim_tilt_deg','aimTilt','Κλίση δέσμης',90),
                                   ('aim_azimuth_deg','aimBearing','Περιστροφή',359)]:
        dial=CompassDial() if maximum==359 else QDial()
        dial.setObjectName(name);dial.setRange(0,maximum);dial.setFixedSize(84,84)
        if maximum==90:dial.setNotchesVisible(True);dial.setAccessibleName('Κλίση δέσμης')
        dial.setValue(round(float(p.get(key,0))))
        text=QLabel(f'{dial.value()}°');text.setObjectName(name+'Value')
        text.setTextInteractionFlags(Qt.NoTextInteraction)
        row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0)
        layout.addWidget(dial);layout.addWidget(text);layout.addStretch(1)
        dial.setToolTip('Σύρετε τον ρότορα · Esc για ακύρωση. Η ένδειξη μοιρών δεν πληκτρολογείται.')
        bind_control(window,eid,dial,text,key,float,lambda value,k=key:_set_aim(window,eid,k,value),suffix='°')
        window.form.addRow(label,row)
