from __future__ import annotations
import math
import numpy as np
from typing import Optional, Dict

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QPainter
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsTextItem

from archforge.core.model import Document
from archforge.core.commands import CommandStack
from archforge.core.viewport import PointerController, PointerEvent
from archforge.core.interaction import VertexMoveTransaction
from archforge.core.plan_scene import (
    build_plan_frame, Primitive2D, Handle2D, _mesh_world_vertices, _convex_hull_xy,
)

class PlanView(QGraphicsView):
    selectionChangedByView=Signal();statusChanged=Signal(str);catalogItemDropped=Signal(str,float,float)
    CATALOG_MIME='application/x-archforge-catalog-item'
    def __init__(self,doc:Document,stack:CommandStack,parent=None):
        self._scene=QGraphicsScene();super().__init__(self._scene,parent);self.doc=doc;self.stack=stack;self.controller=PointerController(doc,stack)
        self.setRenderHint(QPainter.RenderHint.Antialiasing,True);self.setDragMode(QGraphicsView.DragMode.NoDrag);self.setMouseTracking(True);self.setAcceptDrops(True);self.viewport().setAcceptDrops(True);self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse);self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter);self.setBackgroundBrush(QColor(248,248,248))
        self._mouse_down=False;self._handle_items={};self._entity_items={};self._active_handle=None;self._hud_item=None
        self._vertex_tx=None;self._vertex_drag_origin=None
        self._ghost_path=();self._ghost_diameter=0.0;self._ghost_vertices=();self._ghost_faces=();self._interaction_locked=False
        self._dimension_labels=[];self._dimension_records=[]
        self.scale(55.0,-55.0);self.redraw()
    def rebind(self,doc,stack):
        self.doc=doc;self.stack=stack;self.controller=PointerController(doc,stack)
        self._vertex_tx=None;self._vertex_drag_origin=None;self._ghost_path=();self._ghost_diameter=0.0;self._ghost_vertices=();self._ghost_faces=();self._interaction_locked=False;self.redraw()
    def set_interaction_locked(self,locked):self._interaction_locked=bool(locked)
    def set_ghost_preview(self,path_vertices,diameter):
        from archforge.geometry.mesh import generate_conduit_topology
        self._ghost_path=tuple(tuple(float(v) for v in point) for point in path_vertices);self._ghost_diameter=float(diameter)
        self._ghost_vertices,self._ghost_faces=generate_conduit_topology(self._ghost_path,self._ghost_diameter)
        self._interaction_locked=True;self.redraw()
    def clear_ghost_preview(self):
        self._ghost_path=();self._ghost_diameter=0.0;self._ghost_vertices=();self._ghost_faces=();self._interaction_locked=False;self.redraw()
    def set_tool(self,tool):self.controller.set_tool(tool);self._active_handle=None;self.statusChanged.emit(f'Tool: {tool}');self.redraw()
    def _scene_to_plane(self,pos):p=self.mapToScene(pos);return PointerEvent(p.x(),p.y())

    def _world_delta_to_mesh_local(self,eid,dx,dy,dz=0.0):
        matrix=np.asarray(self.doc.get(eid).params['matrix'],dtype=float).reshape(4,4)
        linear=matrix[:3,:3]
        return tuple(float(v) for v in np.linalg.solve(linear,np.asarray((dx,dy,dz),dtype=float)))

    def _vertex_preview_world_vertices(self):
        if self._vertex_tx is None:return ()
        entity=self.doc.get(self._vertex_tx.eid);params=dict(entity.params)
        params['vertices']=self._vertex_tx.preview_vertices()
        return tuple(_mesh_world_vertices(params))
    def wheelEvent(self,event):self.scale(1.15 if event.angleDelta().y()>0 else 1/1.15,1.15 if event.angleDelta().y()>0 else 1/1.15)
    def dragEnterEvent(self,event):
        if event.mimeData().hasFormat(self.CATALOG_MIME):event.acceptProposedAction();return
        super().dragEnterEvent(event)
    def dragMoveEvent(self,event):
        if event.mimeData().hasFormat(self.CATALOG_MIME):event.acceptProposedAction();return
        super().dragMoveEvent(event)
    def dropEvent(self,event):
        if event.mimeData().hasFormat(self.CATALOG_MIME):
            key=bytes(event.mimeData().data(self.CATALOG_MIME)).decode('utf-8').strip()
            point=self.mapToScene(event.position().toPoint())
            self.catalogItemDropped.emit(key,float(point.x()),float(point.y()))
            event.acceptProposedAction();return
        super().dropEvent(event)
    def mousePressEvent(self,event):
        if self._interaction_locked and event.button()==Qt.MouseButton.LeftButton:return
        if event.button()!=Qt.MouseButton.LeftButton:super().mousePressEvent(event);return
        self._mouse_down=True;hit=self.itemAt(event.position().toPoint())
        if hit in self._handle_items:
            h=self._handle_items[hit];self._active_handle=h
            self.doc.select([h.entity_id]);self.selectionChangedByView.emit()
            if h.handle.startswith('vertex:'):
                self._vertex_tx=VertexMoveTransaction(self.stack,h.entity_id,int(h.handle.split(':',1)[1]))
                p=self.mapToScene(event.position().toPoint());self._vertex_drag_origin=(p.x(),p.y())
                self.statusChanged.emit(f'Mesh vertex {self._vertex_tx.v_index} selected')
                self.redraw();return
            if h.handle=='move' or h.cursor=='move':
                self.controller.set_tool('move');self.controller.set_target(h.entity_id,h.handle)
            else:
                self.controller.set_tool('stretch');self.controller.set_target(h.entity_id,h.handle)
        elif self.controller.tool=='select':
            eid=self._entity_items.get(hit)
            if eid:self.doc.select([eid],add=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier))
            elif not(event.modifiers()&Qt.KeyboardModifier.ControlModifier):self.doc.select([])
            self.selectionChangedByView.emit();self.redraw();return
        elif self.controller.tool in ('stretch','rotate') and self.doc.selection:self.controller.set_target(self.doc.selection[-1],self._active_handle.handle if self._active_handle else None)
        ev=self._scene_to_plane(event.position().toPoint());ev.shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier);self.controller.pointer_down(ev);self.redraw()
    def mouseMoveEvent(self,event):
        if self._mouse_down and self._vertex_tx is not None and self._vertex_drag_origin is not None:
            p=self.mapToScene(event.position().toPoint());ox,oy=self._vertex_drag_origin
            local=self._world_delta_to_mesh_local(self._vertex_tx.eid,p.x()-ox,p.y()-oy,0.0)
            self._vertex_tx.update_drag(*local)
            q=self._vertex_tx.preview_position
            self.statusChanged.emit(f'Vertex {self._vertex_tx.v_index}: {q[0]:.3f}, {q[1]:.3f}, {q[2]:.3f}')
            self.redraw();return
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
            if self._vertex_tx is not None:
                tx=self._vertex_tx;self._vertex_tx=None;self._vertex_drag_origin=None;self._active_handle=None
                tx.commit();return
            if self.controller.active is not None:
                ev=self._scene_to_plane(event.position().toPoint());ev.shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)
                try:self.controller.pointer_up(ev)
                except ValueError as exc:self.statusChanged.emit(str(exc));self.controller.cancel()
                self._active_handle=None;return
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape and self._vertex_tx is not None:
            self._vertex_tx.cancel();self._vertex_tx=None;self._vertex_drag_origin=None;self._active_handle=None;self._mouse_down=False;self.redraw();return
        if event.key()==Qt.Key.Key_Escape:self.controller.cancel();self._mouse_down=False;self.redraw();return
        super().keyPressEvent(event)
    def redraw(self):
        self._scene.clear();self._handle_items.clear();self._entity_items.clear();self._draw_grid();frame=build_plan_frame(self.doc,self.controller.preview)
        preview_eid=self._vertex_tx.eid if self._vertex_tx is not None else None
        for p in frame.primitives:
            if preview_eid and p.entity_id==preview_eid and self.doc.get(preview_eid).kind=='mesh':continue
            self._draw_primitive(p)
        for h in frame.handles:
            if preview_eid and h.entity_id==preview_eid and h.handle.startswith('vertex:'):continue
            self._draw_handle(h)
        if self._vertex_tx is not None:
            world=self._vertex_preview_world_vertices()
            hull=_convex_hull_xy(world)
            if hull:self._draw_primitive(Primitive2D('polygon',hull,entity_id=self._vertex_tx.eid,role='vertex-preview',meta=(('semantic','mesh'),)))
            for index,(x,y,_z) in enumerate(world):
                self._draw_handle(Handle2D(x,y,self._vertex_tx.eid,f'vertex:{index}','vertex'))
        self._draw_automatic_dimensions()
        if self._ghost_path:self._draw_ghost_preview()
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
    def _preview_param_overrides(self):
        preview=self.controller.preview
        if preview is None:return {}
        geometry=preview.geometry or {}
        if preview.kind in ('move','stretch') and isinstance(geometry.get('entities'),dict):
            return geometry['entities']
        if preview.entity_id and isinstance(geometry,dict):
            return {preview.entity_id:geometry}
        return {}
    def _dimension_boundaries(self):
        overrides=self._preview_param_overrides();out=[]
        for eid,entity in self.doc.entities.items():
            if not self.doc.entity_is_visible(entity):continue
            if entity.kind=='wall':
                p=dict(entity.params);p.update(overrides.get(eid,{}) or {})
                a=(float(p['x1']),float(p['y1']));b=(float(p['x2']),float(p['y2']))
                if math.dist(a,b)>1e-9:
                    out.append((eid,'length',a,b,.28))
                    dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
                    nx,ny=-dy/length,dx/length;half=float(p['thickness'])/2.0
                    mid=((a[0]+b[0])/2.0,(a[1]+b[1])/2.0)
                    out.append((eid,'thickness',(mid[0]-nx*half,mid[1]-ny*half),(mid[0]+nx*half,mid[1]+ny*half),.16))
            elif entity.kind=='mesh':
                if self._vertex_tx is not None and self._vertex_tx.eid==eid:
                    world=self._vertex_preview_world_vertices()
                else:
                    params=dict(entity.params)
                    if eid in overrides:params.update(overrides[eid] or {})
                    world=tuple(_mesh_world_vertices(params))
                hull=_convex_hull_xy(world)
                if len(hull)>=2:
                    for i,a in enumerate(hull):
                        b=hull[(i+1)%len(hull)]
                        if math.dist(a,b)>1e-9:out.append((eid,f'edge:{i}',a,b,.20))
        return out
    @staticmethod
    def _dimension_text(a,b):
        return f'{int(round(math.hypot(b[0]-a[0],b[1]-a[1])*1000.0))} mm'
    def _draw_dimension_segment(self,eid,role,a,b,offset):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length<=1e-9:return
        nx,ny=-dy/length,dx/length
        da=(a[0]+nx*offset,a[1]+ny*offset);db=(b[0]+nx*offset,b[1]+ny*offset)
        pen=QPen(QColor(35,35,35));pen.setWidthF(.012)
        extension=QPen(QColor(85,85,85));extension.setWidthF(.008)
        for p0,p1 in ((a,da),(b,db)):
            item=self._scene.addLine(p0[0],p0[1],p1[0],p1[1],extension);item.setZValue(38)
        line=self._scene.addLine(da[0],da[1],db[0],db[1],pen);line.setZValue(39)
        tick=.055
        for q in (da,db):
            t=self._scene.addLine(q[0]-nx*tick,q[1]-ny*tick,q[0]+nx*tick,q[1]+ny*tick,pen);t.setZValue(39)
        label=self._dimension_text(a,b)
        text=self._scene.addText(label);text.setDefaultTextColor(QColor(18,18,18))
        text.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
        text.setPos((da[0]+db[0])/2.0,(da[1]+db[1])/2.0)
        angle=math.degrees(math.atan2(dy,dx))
        if angle>90 or angle<-90:angle+=180
        text.setRotation(-angle);text.setZValue(40)
        self._dimension_labels.append(label)
        self._dimension_records.append((eid,role,label,a,b))
    def _draw_automatic_dimensions(self):
        self._dimension_labels=[];self._dimension_records=[]
        for eid,role,a,b,offset in self._dimension_boundaries():
            self._draw_dimension_segment(eid,role,a,b,offset)

    def _draw_ghost_preview(self):
        from PySide6.QtGui import QPolygonF
        pen=QPen(QColor(0,220,255,220));pen.setWidthF(.028);pen.setStyle(Qt.PenStyle.DotLine)
        brush=QBrush(QColor(0,220,255,42))
        for face in self._ghost_faces:
            pts=[QPointF(self._ghost_vertices[index][0],self._ghost_vertices[index][1]) for index in face]
            item=self._scene.addPolygon(QPolygonF(pts),pen,brush);item.setZValue(35);item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _draw_handle(self,h):
        r=.09;it=self._scene.addEllipse(h.x-r,h.y-r,2*r,2*r,QPen(QColor(20,90,180),0),QBrush(QColor(255,255,255)));it.setZValue(50);self._handle_items[it]=h
    def _draw_snap(self,s):r=.08;self._scene.addEllipse(s['x']-r,s['y']-r,2*r,2*r,QPen(QColor(220,80,40),0)).setZValue(70)
    def _draw_hud(self,hud):
        text='  '.join(f'{k}: {v:.3f}' for k,v in hud.items() if isinstance(v,(int,float)));it=self._scene.addText(text);it.setDefaultTextColor(QColor(20,20,20));it.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True);it.setPos(self.mapToScene(self.viewport().rect().topLeft()));it.setZValue(100)
