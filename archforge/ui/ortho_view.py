from __future__ import annotations
from typing import Dict, Optional
from PySide6.QtCore import Qt,QPointF,Signal
from PySide6.QtGui import QPen,QBrush,QColor,QPainter,QPolygonF,QPainterPath
from PySide6.QtWidgets import QGraphicsView,QGraphicsScene
from archforge.core.model import Document
from archforge.core.commands import CommandStack,SetWallTopEndpoint
from archforge.core.interaction import VerticalStretchTransaction
from archforge.core.opening_vertical import OpeningVerticalEditTransaction,opening_elevation_handles
from archforge.core.view_frame import build_view_frame,ViewPrimitive,elevation_top_handle

class OrthoView(QGraphicsView):
    selectionChangedByView=Signal();statusChanged=Signal(str)
    def __init__(self,doc,stack,axis,parent=None):
        if axis not in ('XZ','YZ'):raise ValueError('OrthoView supports XZ/YZ')
        self._scene=QGraphicsScene();super().__init__(self._scene,parent);self.doc=doc;self.stack=stack;self.axis=axis;self._entity_items={};self._handle_items={};self._drag_tx=None;self._drag_eid=None;self._wall_top_drag=None;self._preview_overrides={}
        self.setRenderHint(QPainter.RenderHint.Antialiasing,True);self.setMouseTracking(True);self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse);self.setBackgroundBrush(QColor(248,248,248));self.scale(55,-55);self.redraw()
    def rebind(self,doc,stack):self.doc=doc;self.stack=stack;self._drag_tx=None;self._drag_eid=None;self._wall_top_drag=None;self._preview_overrides.clear();self.redraw()
    def wheelEvent(self,event):f=1.15 if event.angleDelta().y()>0 else 1/1.15;self.scale(f,f)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            hit=self.itemAt(event.position().toPoint())
            if hit in self._handle_items:
                eid,handle=self._handle_items[hit];e=self.doc.get(eid)
                if e.kind=='wall' and handle in ('start_top','end_top'):
                    endpoint='start' if handle=='start_top' else 'end';self._wall_top_drag=(eid,endpoint);self._drag_eid=eid;p=self.mapToScene(event.position().toPoint())
                    try:self._update_wall_top_drag(p.y());self.redraw()
                    except ValueError as exc:self.statusChanged.emit(str(exc))
                    return
                if e.kind in ('door','window'):
                    self._drag_tx=OpeningVerticalEditTransaction(self.doc,self.stack,eid,handle)
                else:
                    self._drag_tx=VerticalStretchTransaction(self.doc,self.stack,eid)
                self._drag_eid=eid;p=self.mapToScene(event.position().toPoint())
                try:self._update_drag(p.y());self.redraw()
                except ValueError as exc:self.statusChanged.emit(str(exc))
                return
            eid=self._entity_items.get(hit)
            if eid:self.doc.select([eid],add=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier))
            elif not(event.modifiers()&Qt.KeyboardModifier.ControlModifier):self.doc.select([])
            self.selectionChangedByView.emit();self.redraw();return
        super().mousePressEvent(event)
    def _update_wall_top_drag(self,z):
        eid,endpoint=self._wall_top_drag;e=self.doc.get(eid);base=float(e.params['z']);height=float(z)-base
        if height<=0:raise ValueError('wall top must remain above base')
        p=e.params.copy();p[f'{endpoint}_height']=height;self._preview_overrides[eid]=p;self.statusChanged.emit(f"{endpoint.title()} top height {height:.3f}   Top Z {float(z):.3f}");return height
    def _update_drag(self,z):
        result=self._drag_tx.update(z);self._preview_overrides[self._drag_eid]=dict(self._drag_tx.preview)
        if hasattr(result,'values'):
            hud=result.values
        else:hud=result
        if self.doc.get(self._drag_eid).kind in ('door','window'):
            self.statusChanged.emit(f"Height {hud['height']:.3f}   Sill {hud['sill']:.3f}   Top Z {hud['top_z']:.3f}")
        else:self.statusChanged.emit(f"Height {hud['height']:.3f}   Top Z {hud['top_z']:.3f}")
        return hud
    def mouseMoveEvent(self,event):
        p=self.mapToScene(event.position().toPoint())
        if self._wall_top_drag is not None:
            try:self._update_wall_top_drag(p.y());self.redraw()
            except ValueError as exc:self.statusChanged.emit(str(exc))
            return
        if self._drag_tx is not None and self._drag_eid is not None:
            try:self._update_drag(p.y());self.redraw()
            except ValueError as exc:self.statusChanged.emit(str(exc))
            return
        labels=('X','Z') if self.axis=='XZ' else ('Y','Z');self.statusChanged.emit(f'{labels[0]} {p.x():.3f}   {labels[1]} {p.y():.3f}');super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self._wall_top_drag is not None:
            p=self.mapToScene(event.position().toPoint());eid,endpoint=self._wall_top_drag
            try:
                height=self._update_wall_top_drag(p.y());self.stack.execute(SetWallTopEndpoint(eid,endpoint,height))
            except ValueError as exc:self.statusChanged.emit(str(exc))
            self._wall_top_drag=None;self._drag_eid=None;self._preview_overrides.clear();self.selectionChangedByView.emit();self.redraw();return
        if event.button()==Qt.MouseButton.LeftButton and self._drag_tx is not None:
            p=self.mapToScene(event.position().toPoint())
            try:self._update_drag(p.y());self._drag_tx.commit()
            except ValueError as exc:self.statusChanged.emit(str(exc));self._drag_tx.cancel()
            self._drag_tx=None;self._drag_eid=None;self._preview_overrides.clear();self.selectionChangedByView.emit();self.redraw();return
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape and self._wall_top_drag is not None:self._wall_top_drag=None;self._drag_eid=None;self._preview_overrides.clear();self.redraw();return
        if event.key()==Qt.Key.Key_Escape and self._drag_tx is not None:self._drag_tx.cancel();self._drag_tx=None;self._drag_eid=None;self._preview_overrides.clear();self.redraw();return
        super().keyPressEvent(event)
    def redraw(self):
        self._scene.clear();self._entity_items.clear();self._handle_items.clear();self._draw_grid();frame=build_view_frame(self.doc,self.axis,self._preview_overrides);selected=set(self.doc.selection)
        for p in frame.primitives:self._draw_primitive(p,p.entity_id in selected)
        for eid in self.doc.selection:
            if eid not in self.doc.entities or self.doc.get(eid).locked:continue
            e=self.doc.get(eid);override=self._preview_overrides.get(eid)
            if e.kind in ('door','window'):
                for handle,x,z in opening_elevation_handles(self.doc,eid,self.axis,override):self._draw_handle(eid,x,z,handle)
            elif e.kind=='wall':
                p=override or e.params;base=float(p['z']);legacy=float(p['height']);coord1=float(p['x1'] if self.axis=='XZ' else p['y1']);coord2=float(p['x2'] if self.axis=='XZ' else p['y2'])
                self._draw_handle(eid,coord1,base+float(p.get('start_height',legacy)),'start_top');self._draw_handle(eid,coord2,base+float(p.get('end_height',legacy)),'end_top')
            else:
                hp=elevation_top_handle(self.doc,eid,self.axis,override)
                if hp:self._draw_handle(eid,*hp,'top')
        r=self.mapToScene(self.viewport().rect()).boundingRect();self._scene.setSceneRect(r.adjusted(-5,-5,5,5))
    def _draw_grid(self):
        extent=100;pen=QPen(QColor(225,225,225));pen.setWidthF(0);axis=QPen(QColor(160,160,160));axis.setWidthF(0)
        for i in range(-extent,extent+1):self._scene.addLine(i,-extent,i,extent,axis if i==0 else pen).setZValue(-100);self._scene.addLine(-extent,i,extent,i,axis if i==0 else pen).setZValue(-100)
    def _draw_handle(self,eid,x,z,handle='top'):
        r=.09;it=self._scene.addEllipse(x-r,z-r,2*r,2*r,QPen(QColor(20,90,180),0),QBrush(QColor(255,255,255)));it.setZValue(50);self._handle_items[it]=(eid,handle)
    def _draw_primitive(self,p,selected=False):
        opening=p.role=='opening';pen=QPen(QColor(180,90,20) if opening else (QColor(20,90,180) if selected else QColor(45,55,65)));pen.setWidthF(.06 if opening else (.04 if selected else .03));item=None
        if p.kind=='line':a,b=p.points;item=self._scene.addLine(a[0],a[1],b[0],b[1],pen)
        elif p.kind=='polygon':item=self._scene.addPolygon(QPolygonF([QPointF(x,y) for x,y in p.points]),pen,QBrush(QColor(255,170,60,25) if opening else QColor(90,150,210,30)))
        elif p.kind=='upper_ellipse':
            cx,z0=p.points[0];rx,rz=p.radius_a,p.radius_b;path=QPainterPath(QPointF(cx-rx,z0));k=.5522847498307936;path.cubicTo(cx-rx,z0+k*rz,cx-k*rx,z0+rz,cx,z0+rz);path.cubicTo(cx+k*rx,z0+rz,cx+rx,z0+k*rz,cx+rx,z0);path.lineTo(cx-rx,z0);path.closeSubpath();item=self._scene.addPath(path,pen,QBrush(QColor(170,120,210,25)))
        if item is not None and p.entity_id:self._entity_items[item]=p.entity_id
