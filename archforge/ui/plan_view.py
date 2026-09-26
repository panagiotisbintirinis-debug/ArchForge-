from __future__ import annotations
import math
from typing import Optional, Dict

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QPainter
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsTextItem, QMenu

from archforge.core.model import Document
from archforge.core.commands import CommandStack
from archforge.core.viewport import PointerController, PointerEvent
from archforge.core.plan_scene import build_plan_frame, Primitive2D, Handle2D
from archforge.ui.object_context_menu import object_context_actions

class PlanView(QGraphicsView):
    selectionChangedByView=Signal();contextActionRequested=Signal(str,str);statusChanged=Signal(str)
    def __init__(self,doc:Document,stack:CommandStack,parent=None):
        self._scene=QGraphicsScene();super().__init__(self._scene,parent);self.doc=doc;self.stack=stack;self.controller=PointerController(doc,stack)
        self.setRenderHint(QPainter.RenderHint.Antialiasing,True);self.setDragMode(QGraphicsView.DragMode.NoDrag);self.setMouseTracking(True);self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse);self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter);self.setBackgroundBrush(QColor(248,248,248))
        self._mouse_down=False;self._handle_items={};self._entity_items={};self._active_handle=None;self._hud_item=None;self.scale(55.0,-55.0);self.redraw()
    def rebind(self,doc,stack):self.doc=doc;self.stack=stack;self.controller=PointerController(doc,stack);self.redraw()
    def set_tool(self,tool):self.controller.set_tool(tool);self._active_handle=None;self.statusChanged.emit(f'Tool: {tool}');self.redraw()
    def _scene_to_plane(self,pos):p=self.mapToScene(pos);return PointerEvent(p.x(),p.y())
    def _acquire_rotate_target(self,hit):
        eid=self._entity_items.get(hit)
        self.doc.select([eid] if eid else [])
        self.controller.set_target(eid,None)
        self.selectionChangedByView.emit()
        return eid is not None
    def _acquire_move_target(self,hit):
        eid=self._entity_items.get(hit)
        self.doc.select([eid] if eid else [])
        self.controller.set_target(eid,None)
        self.selectionChangedByView.emit()
        return eid is not None
    def _acquire_stretch_target(self,hit):
        eid=self._entity_items.get(hit)
        self.doc.select([eid] if eid else [])
        self.controller.set_target(eid,None)
        self.selectionChangedByView.emit()
        return eid is not None
    def wheelEvent(self,event):self.scale(1.15 if event.angleDelta().y()>0 else 1/1.15,1.15 if event.angleDelta().y()>0 else 1/1.15)
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            hit=self.itemAt(event.position().toPoint());eid=self._entity_items.get(hit)
            if eid and eid in self.doc.entities:
                self.doc.select([eid]);self.controller.set_target(eid,None)
                self.selectionChangedByView.emit();self.redraw();event.accept();return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self,event):
        hit=self.itemAt(event.pos());eid=self._entity_items.get(hit)
        if not eid or eid not in self.doc.entities:
            super().contextMenuEvent(event);return
        self.doc.select([eid]);self.controller.set_target(eid,None)
        self.selectionChangedByView.emit();self.redraw()

        entity=self.doc.get(eid);menu=QMenu(self);action_map={}
        for spec in object_context_actions(entity.kind,'plan'):
            if spec is None:
                menu.addSeparator();continue
            action=menu.addAction(spec['label']);action_map[action]=spec['id']
        chosen=menu.exec(event.globalPos())
        if chosen in action_map:self.contextActionRequested.emit(eid,action_map[chosen])
        event.accept()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:super().mousePressEvent(event);return
        self._mouse_down=True;hit=self.itemAt(event.position().toPoint())
        if hit in self._handle_items:
            h=self._handle_items[hit];self._active_handle=h
            self.doc.select([h.entity_id]);self.selectionChangedByView.emit()
            if h.handle=='move' or h.cursor=='move':
                self.controller.set_tool('move');self.controller.set_target(h.entity_id,h.handle)
            else:
                self.controller.set_tool('stretch');self.controller.set_target(h.entity_id,h.handle)
        elif self.controller.tool=='select':
            eid=self._entity_items.get(hit)
            if eid:self.doc.select([eid],add=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier))
            elif not(event.modifiers()&Qt.KeyboardModifier.ControlModifier):self.doc.select([])
            self.selectionChangedByView.emit();self.redraw();return
        elif self.controller.tool=='move':
            if not self._acquire_move_target(hit):self._mouse_down=False;self.redraw();return
        elif self.controller.tool=='rotate':
            if not self._acquire_rotate_target(hit):self._mouse_down=False;self.redraw();return
        elif self.controller.tool=='stretch':
            if not self._acquire_stretch_target(hit):self._mouse_down=False;self.redraw();return
        ev=self._scene_to_plane(event.position().toPoint());ev.shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier);self.controller.pointer_down(ev);self.redraw()
    def mouseMoveEvent(self,event):
        if self._mouse_down and self.controller.active is not None:
            ev=self._scene_to_plane(event.position().toPoint());ev.shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)
            try:self.controller.pointer_move(ev);self.redraw()
            except ValueError as exc:self.statusChanged.emit(str(exc))
        else:
            p=self.mapToScene(event.position().toPoint());self.statusChanged.emit(f'X {p.x():.3f}   Y {p.y():.3f}')
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self._mouse_down:
            self._mouse_down=False
            if self.controller.active is not None:
                ev=self._scene_to_plane(event.position().toPoint());ev.shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)
                try:self.controller.pointer_up(ev)
                except ValueError as exc:self.statusChanged.emit(str(exc));self.controller.cancel()
                self._active_handle=None;self.redraw();return
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:self.controller.cancel();self._mouse_down=False;self.redraw();return
        super().keyPressEvent(event)
    def redraw(self):
        self._scene.clear();self._handle_items.clear();self._entity_items.clear();self._draw_grid();frame=build_plan_frame(self.doc,self.controller.preview)
        for p in frame.primitives:self._draw_primitive(p)
        for h in frame.handles:self._draw_handle(h)
        if frame.snap:self._draw_snap(frame.snap)
        if frame.hud:self._draw_hud(frame.hud)
        r=self.mapToScene(self.viewport().rect()).boundingRect();self._scene.setSceneRect(r.adjusted(-5,-5,5,5))
    def _draw_grid(self):
        extent=100;pen=QPen(QColor(225,225,225));pen.setWidthF(0);axis=QPen(QColor(160,160,160));axis.setWidthF(0)
        for i in range(-extent,extent+1):self._scene.addLine(i,-extent,i,extent,axis if i==0 else pen).setZValue(-100);self._scene.addLine(-extent,i,extent,i,axis if i==0 else pen).setZValue(-100)
    def _draw_primitive(self,p:Primitive2D):
        preview=p.role=='preview';opening=p.role=='opening';room=p.role=='derived-room';pen=QPen(QColor(180,90,20) if opening else (QColor(40,150,70) if preview else QColor(45,55,65)));pen.setWidthF(.06 if opening else (.04 if preview else .035));item=None
        if p.kind=='line':a,b=p.points;item=self._scene.addLine(a[0],a[1],b[0],b[1],pen)
        elif p.kind=='polygon':
            from PySide6.QtGui import QPolygonF
            brush=QBrush(QColor(90,180,120,28) if room else QColor(80,160,220,40))
            room_pen=QPen(QColor(110,150,120));room_pen.setWidthF(.015)
            item=self._scene.addPolygon(QPolygonF([QPointF(x,y) for x,y in p.points]),room_pen if room else pen,brush)
        elif p.kind=='ellipse':
            cx,cy=p.points[0];item=self._scene.addEllipse(cx-p.radius_x,cy-p.radius_y,2*p.radius_x,2*p.radius_y,pen,QBrush(QColor(170,120,210,30)))
        elif p.kind=='label':
            meta=dict(p.meta);text=str(meta.get('text',''));cx,cy=p.points[0];item=self._scene.addText(text);item.setDefaultTextColor(QColor(55,80,65));item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True);item.setPos(cx,cy);item.setTransformOriginPoint(item.boundingRect().center());item.setScale(1.0);item.setZValue(8);return
        if item is not None:
            item.setZValue(-10 if room else (10 if opening else (20 if preview else 0)))
            if p.entity_id and not preview:self._entity_items[item]=p.entity_id
    def _draw_handle(self,h):
        r=.09;it=self._scene.addEllipse(h.x-r,h.y-r,2*r,2*r,QPen(QColor(20,90,180),0),QBrush(QColor(255,255,255)));it.setZValue(50);self._handle_items[it]=h
    def _draw_snap(self,s):r=.08;self._scene.addEllipse(s['x']-r,s['y']-r,2*r,2*r,QPen(QColor(220,80,40),0)).setZValue(70)
    def _draw_hud(self,hud):
        text='  '.join(f'{k}: {v:.3f}' for k,v in hud.items() if isinstance(v,(int,float)));it=self._scene.addText(text);it.setDefaultTextColor(QColor(20,20,20));it.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True);it.setPos(self.mapToScene(self.viewport().rect().topLeft()));it.setZValue(100)
