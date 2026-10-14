"""A textured 3D sample cube, painted in Qt without a WebGL dependency."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import QWidget
from archforge.ui.pattern_swatch import material_swatch

class MaterialPreview(QWidget):
    def __init__(self, parent=None, doc=None):
        super().__init__(parent); self.doc=doc; self.material_id=None; self.texture=None
        self.setMinimumSize(210,180)
        self.setToolTip('Το επιλεγμένο υλικό σε κύβο 3D')

    def set_material(self, material_id):
        self.material_id=str(material_id)
        self.texture=material_swatch(self.material_id,256,256,doc=self.doc)
        self.update()

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('#f3f6fa'))
        if self.texture is None:
            p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'Δείγμα υλικού σε 3D'); p.end(); return
        w,h=self.width(),self.height(); s=min(w*.38,h*.33); cx,cy=w*.5,h*.45
        a=(cx,cy-s); b=(cx+s,cy-s*.5); c=(cx,cy); d=(cx-s,cy-s*.5)
        e=(cx+s,cy+s*.65); f=(cx,cy+s*1.15); g=(cx-s,cy+s*.65)
        src=QPolygonF([QPointF(0,0),QPointF(256,0),QPointF(256,256),QPointF(0,256)])
        for corners,shade in (((a,b,c,d),0),((d,c,f,g),35),((c,b,e,f),65)):
            dest=QPolygonF([QPointF(*q) for q in corners]); transform=QTransform()
            if QTransform.quadToQuad(src,dest,transform):
                p.save(); p.setTransform(transform); p.drawImage(QPointF(0,0),self.texture); p.restore()
            p.setPen(QPen(QColor('#546273'),1)); p.setBrush(QColor(0,0,0,shade)); p.drawPolygon(dest)
        p.setPen(QColor('#31506b'))
        p.drawText(0,h-26,w,24,Qt.AlignmentFlag.AlignCenter,'Δείγμα σε κύβο 3D')
        p.end()
