from __future__ import annotations
import math
import copy
from typing import Optional, Dict

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsTextItem, QMenu, QToolButton

from archforge.core.model import Document
from archforge.core.commands import CommandStack
from archforge.core.viewport import PointerController, PointerEvent
from archforge.core.plan_scene import build_plan_frame, Primitive2D, Handle2D
from archforge.ui.object_context_menu import object_context_actions

class PlanView(QGraphicsView):
    selectionChangedByView=Signal();contextActionRequested=Signal(str,str);commandRequested=Signal(str);previewChanged=Signal(object);statusChanged=Signal(str)
    # (kind, x1, y1, x2, y2): a Section or Camera line dragged in the plan.
    viewLineRequested=Signal(str,float,float,float,float)
    VIEW_LINE_TOOLS={'view_section':'section','view_camera':'camera'}
    # Single-click site tools: (tool, x, y) handled by the main window.
    sitePointRequested=Signal(str,float,float)
    SITE_POINT_TOOLS=('terrain_point','plant_tree','plant_shrub','library_place')
    # Drag tools for site strips: (tool, x1, y1, x2, y2).
    siteLineRequested=Signal(str,float,float,float,float)
    SITE_LINE_TOOLS=('path_path','path_sidewalk','path_road','pergola_timber','pergola_aluminium')
    # Railing tools ('railing_<type>'): click corners, double click / Enter to finish -> (tool, points, closed).
    railingRequested=Signal(str,object,bool)
    def _railing_tool(self):return str(self.controller.tool).startswith('railing_')
    def _railing_press(self,event):
        from archforge.ui.railing_draft import RailingDraft
        if getattr(self,'_railing_draft',None) is None:self._railing_draft=RailingDraft()
        ev=self._scene_to_plane(event.position().toPoint())
        if self._railing_draft.add(ev.a,ev.b,bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)):self.finish_railing();return
        self.statusChanged.emit('Κάγκελο: κλικ στην επόμενη γωνία · διπλό κλικ / Enter = τέλος · κλικ στο πρώτο σημείο = κλειστό · Shift = ορθή γωνία · Esc = ακύρωση')
        self.redraw()
    def finish_railing(self):
        draft=getattr(self,'_railing_draft',None);self._railing_draft=None
        done=draft.finish() if draft is not None else None
        self.redraw()
        if done is None:self.statusChanged.emit('Κάγκελο: χρειάζονται τουλάχιστον δύο σημεία');return
        self.railingRequested.emit(self.controller.tool,done[0],done[1])
    def begin_view_line(self,x,y):self._view_drag=[(float(x),float(y)),(float(x),float(y))];self.redraw()
    def move_view_line(self,x,y):
        if getattr(self,'_view_drag',None):self._view_drag[1]=(float(x),float(y));self.redraw()
    def end_view_line(self,x,y):
        drag=getattr(self,'_view_drag',None);self._view_drag=None
        if not drag:return
        (x1,y1),_=drag;kind=self.VIEW_LINE_TOOLS.get(self.controller.tool)
        self.redraw()
        if self.controller.tool in self.SITE_LINE_TOOLS:
            if math.hypot(float(x)-x1,float(y)-y1)<0.2:
                self.statusChanged.emit('Σύρε από την αρχή ως το τέλος της διαδρομής');return
            self.siteLineRequested.emit(self.controller.tool,x1,y1,float(x),float(y));return
        if kind is None:return
        if math.hypot(float(x)-x1,float(y)-y1)<0.05:
            self.statusChanged.emit('Τράβηξε γραμμή: από το σημείο θέασης προς την κατεύθυνση που κοιτάς');return
        self.viewLineRequested.emit(kind,x1,y1,float(x),float(y))
    def __init__(self,doc:Document,stack:CommandStack,parent=None,structural_only=False):
        self._scene=QGraphicsScene();super().__init__(self._scene,parent);self.doc=doc;self.stack=stack;self.controller=PointerController(doc,stack);self.structural_only=bool(structural_only)
        self.setRenderHint(QPainter.RenderHint.Antialiasing,True);self.setDragMode(QGraphicsView.DragMode.NoDrag);self.setMouseTracking(True);self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse);self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter);self.setBackgroundBrush(QColor(248,248,248))
        self._mouse_down=False;self._handle_items={};self._entity_items={};self._active_handle=None;self._hud_item=None;self._wall_angle_buttons=[];self._wall_menu_target_entity=None;self.scale(55.0,-55.0);self.redraw()
    def rebind(self,doc,stack):self.doc=doc;self.stack=stack;self.controller=PointerController(doc,stack);self.redraw()
    def set_tool(self,tool):self.controller.set_tool(tool);self._active_handle=None;self._railing_draft=None;self.statusChanged.emit(f'Tool: {tool}');self.redraw()
    # Things that carry other things (slabs, roofs, joists, ground): picked only
    # when nothing more specific (a stair, a cabinet, an MEP point…) is under the cursor.
    CONTAINER_KINDS=('room_floor','room_ceiling','room_foundation','room_roof','floor','room',
                     'pitched_roof','ceiling_joists','terrain')

    def itemAt(self,*args):
        """Most specific pickable item under the cursor (handles first, then objects, then containers)."""
        items=self.items(*args)
        if not items:
            return None
        for item in items:
            if item in getattr(self,'_handle_items',{}):
                return item
        containers=[]
        for item in items:
            eid=self._entity_items.get(item)
            if not eid or eid not in self.doc.entities:
                continue
            if self.doc.get(eid).kind in self.CONTAINER_KINDS:
                containers.append(item)
                continue
            return item
        return containers[0] if containers else items[0]

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
    def wheelEvent(self,event):
        # During a live Stair/Ramp placement the wheel picks the next option.
        if self.controller.cycle_option(-1 if event.angleDelta().y()>0 else 1):
            self.redraw();event.accept();return
        self.scale(1.15 if event.angleDelta().y()>0 else 1/1.15,1.15 if event.angleDelta().y()>0 else 1/1.15)
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self._railing_tool():self.finish_railing();event.accept();return
        if event.button()==Qt.MouseButton.LeftButton:
            hit=self.itemAt(event.position().toPoint());eid=self._entity_items.get(hit)
            if eid and eid in self.doc.entities:
                self.doc.select([eid]);self.controller.set_target(eid,None)
                self.selectionChangedByView.emit();self.redraw();event.accept();return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self,event):
        window=getattr(self,'marking_menu_window',None)
        if window is not None:
            # One task-dependent mouse menu (marking menu), shared with the 3D view.
            eid=self._entity_items.get(self.itemAt(event.pos()))
            busy=self.controller.tool=='wall' or window.sculpt_action.isChecked()
            if busy or not eid or eid not in self.doc.entities:
                eid=None
            else:
                self.doc.select([eid]);self.controller.set_target(eid,None)
                self.selectionChangedByView.emit();self.redraw()
            pos=event.pos()
            if self.controller.tool=='wall':
                self._wall_menu_target_entity=None
                pos=self._wall_angle_anchor(event.pos())
            self.show_marking_menu(pos,eid,self._scene_to_plane(event.pos()))
            event.accept()
            return
        if self.controller.tool=='wall':
            hit=self.itemAt(event.pos())
            eid=self._entity_items.get(hit)
            self._wall_menu_target_entity=None
            if eid and eid in self.doc.entities and self.doc.get(eid).kind=='wall':
                self._wall_menu_target_entity=eid
            elif len(self.doc.selection)==1:
                selected=self.doc.selection[0]
                if selected in self.doc.entities and self.doc.get(selected).kind=='wall':
                    self._wall_menu_target_entity=selected
            else:
                preview_id=getattr(self.controller.preview,'entity_id',None)
                if preview_id and preview_id in self.doc.entities and self.doc.get(preview_id).kind=='wall':
                    self._wall_menu_target_entity=preview_id
            self._show_wall_angle_radial(event.pos())
            event.accept()
            return
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
        if event.button()==Qt.MouseButton.LeftButton:
            self._hide_wall_angle_radial();self.hide_marking_menu()
        if event.button()!=Qt.MouseButton.LeftButton:super().mousePressEvent(event);return
        if self._railing_tool():self._railing_press(event);event.accept();return
        if self.controller.tool in self.SITE_POINT_TOOLS or str(self.controller.tool).startswith(('plumb_','elec_','vent_','assist_','drain_','roofroom_','railingstair_')):
            ev=self._scene_to_plane(event.position().toPoint())
            self.sitePointRequested.emit(self.controller.tool,float(ev.a),float(ev.b));event.accept();return
        if self.controller.tool in self.VIEW_LINE_TOOLS or self.controller.tool in self.SITE_LINE_TOOLS:
            ev=self._scene_to_plane(event.position().toPoint());self._mouse_down=True
            self.begin_view_line(ev.a,ev.b);event.accept();return
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
            # Pressing on a wall's body: a drag moves it perpendicular to its axis (wall_edit.py).
            ev=self._scene_to_plane(event.position().toPoint())
            self._wall_press=(eid,ev.a,ev.b,event.position()) if eid and self.doc.get(eid).kind=='wall' and not(event.modifiers()&Qt.KeyboardModifier.ControlModifier) else None
            self.selectionChangedByView.emit();self.redraw();return
        elif self.controller.tool=='move':
            if not self._acquire_move_target(hit):self._mouse_down=False;self.redraw();return
        elif self.controller.tool=='rotate':
            if not self._acquire_rotate_target(hit):self._mouse_down=False;self.redraw();return
        elif self.controller.tool=='stretch':
            if not self._acquire_stretch_target(hit):self._mouse_down=False;self.redraw();return
        ev=self._scene_to_plane(event.position().toPoint())
        ev.shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)
        ev.ctrl=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier)
        try:
            self.controller.pointer_down(ev)
        except (ValueError, RuntimeError) as exc:
            self._mouse_down=False
            self._active_handle=None
            self.controller.cancel()
            self.statusChanged.emit(str(exc))
            self.redraw()
            event.accept()
            return
        self.redraw()
    def mouseMoveEvent(self,event):
        if self._railing_tool() and getattr(self,'_railing_draft',None) is not None:
            ev=self._scene_to_plane(event.position().toPoint())
            self._railing_draft.move(ev.a,ev.b,bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier));self.redraw();return
        if self._mouse_down and getattr(self,'_view_drag',None):
            ev=self._scene_to_plane(event.position().toPoint());self.move_view_line(ev.a,ev.b);return
        press=getattr(self,'_wall_press',None)
        if self._mouse_down and press and self.controller.active is None and (event.position()-press[3]).manhattanLength()>6:
            try:self.controller.begin_wall_move(press[0],press[1],press[2])
            except ValueError as exc:self.statusChanged.emit(str(exc))
            self._wall_press=None
        if self._mouse_down and self.controller.active is not None:
            ev=self._scene_to_plane(event.position().toPoint())
            ev.shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)
            ev.ctrl=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier)
            try:
                self.controller.pointer_move(ev);self.redraw()
                problem=getattr(self.controller.active,'problem',None)
                if self.controller.preview.kind=='wall-move':
                    self.statusChanged.emit(f'⚠ {problem}' if problem else f'Μετακίνηση τοίχου {self.controller.active.distance*100:+.0f} cm — αφήνεις για να γίνει · Esc = ακύρωση')
                elif problem:self.statusChanged.emit(f'⚠ Δεν χωράει: {problem} — μετακίνησε ή άλλαξε πλάτος')
            except ValueError as exc:self.statusChanged.emit(str(exc))
        else:
            p=self.mapToScene(event.position().toPoint());self.statusChanged.emit(f'X {p.x():.3f}   Y {p.y():.3f}')
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self._mouse_down and getattr(self,'_view_drag',None):
            self._mouse_down=False;ev=self._scene_to_plane(event.position().toPoint())
            self.end_view_line(ev.a,ev.b);event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and self._mouse_down:
            self._mouse_down=False;self._wall_press=None
            if self.controller.active is not None:
                ev=self._scene_to_plane(event.position().toPoint())
                ev.shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)
                ev.ctrl=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier)
                moved_wall=getattr(self.controller.active,'distance',None) if self.controller.preview.kind=='wall-move' else None
                try:
                    self.controller.pointer_up(ev)
                    if getattr(self.controller,'last_warning',None):self.statusChanged.emit(self.controller.last_warning)
                except ValueError as exc:self.statusChanged.emit(str(exc));self.controller.cancel()
                self._active_handle=None;self.redraw()
                if moved_wall is not None:
                    self.selectionChangedByView.emit()
                    if self.controller.preview.kind!='wall-move' and abs(moved_wall)>1e-9:
                        self.statusChanged.emit(f'Ο τοίχος μετακινήθηκε {moved_wall*100:+.0f} cm — μαζί οι ενωμένοι τοίχοι, πόρτες/παράθυρα και ό,τι ακουμπά πάνω του · Ctrl+Z = αναίρεση')
                return
        super().mouseReleaseEvent(event)
    def focusNextPrevChild(self,next):
        # Tab cycles Stair/Ramp options instead of moving keyboard focus.
        if self.controller.tool in ('stair','ramp') and self.controller.active is not None:return False
        return super().focusNextPrevChild(next)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:self.controller.cancel();self._mouse_down=False;self._wall_press=None;self._railing_draft=None;self.redraw();return
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self._railing_tool():self.finish_railing();event.accept();return
        if event.key() in (Qt.Key.Key_Tab,Qt.Key.Key_Space) and self.controller.cycle_option(1):
            self.redraw();event.accept();return
        super().keyPressEvent(event)
    def set_snap_enabled(self, enabled):
        self.controller.set_snap_enabled(enabled)
        self.statusChanged.emit('Snap ON' if enabled else 'Snap OFF — Free mode')
    def set_wall_angle_increment(self, increment):
        self.controller.set_wall_angle_increment(increment)
        label='ελεύθερη' if increment is None else ('μαγνήτες 90/45/15' if increment=='magnet' else f'{float(increment):g}°')
        self.statusChanged.emit(f'Γωνία τοίχου: {label}')
    def set_wall_angle_reference(self, mode):
        self.controller.set_wall_angle_reference(mode)
        self.statusChanged.emit(f'Wall angle reference: {str(mode).title()}')

    def hide_marking_menu(self):
        menu=getattr(self,'_marking_menu',None)
        if menu is not None:
            menu.close();menu.deleteLater()
        self._marking_menu=None

    def show_marking_menu(self,pos,entity_id=None,plan_point=None):
        self._last_marking=(pos,entity_id,plan_point)
        from archforge.ui.marking_menu import MarkingMenu,build_menu,run,wheel
        window=self.marking_menu_window
        self.hide_marking_menu();self._hide_wall_angle_radial()
        menu=build_menu(window,'plan',entity_id)
        xy=(float(plan_point.a),float(plan_point.b)) if plan_point is not None else None
        widget=MarkingMenu(self.viewport(),menu,pos)

        def choose(action_id):
            self.hide_marking_menu()
            run(window,'plan',entity_id,action_id,xy)
        widget.chosen.connect(choose)
        if menu['wheel']:
            widget.wheeled.connect(lambda steps:widget.set_center(wheel(window,menu['wheel'],steps)))
        widget.show();widget.raise_();widget.setFocus()
        self._marking_menu=widget
        self.statusChanged.emit(f"{menu['center']} — επίλεξε από το μενού{' · ροδέλα: '+('βούρτσα' if menu['wheel']=='brush' else 'γωνία') if menu['wheel'] else ''}")
        return widget

    def _hide_wall_angle_radial(self):
        for button in self._wall_angle_buttons:
            button.hide()
            button.deleteLater()
        self._wall_angle_buttons=[]

    def _choose_wall_angle(self, increment):
        self.set_wall_angle_increment(increment)
        # If a wall is already being previewed, refresh it immediately using
        # the new angle mode without committing/cancelling the transaction.
        if self.controller.active is not None:
            self.redraw()
        self._hide_wall_angle_radial()

    def _wall_radial_command(self, command):
        command=str(command)
        if command=='undo':
            self.commandRequested.emit('undo')
        elif command=='delete':
            # During a live wall drag Delete means cancel this uncommitted segment.
            if self.controller.active is not None and hasattr(self.controller.active,'start'):
                self.controller.cancel()
                self._mouse_down=False
                self.statusChanged.emit('Current wall segment cancelled')
                self.redraw()
            else:
                target=self._wall_menu_target_entity
                if target and target in self.doc.entities:
                    self.doc.select([target])
                    self.controller.set_target(target,None)
                    self.selectionChangedByView.emit()
                    self.commandRequested.emit('delete')
                else:
                    self.statusChanged.emit('Nothing to delete at this wall corner')
        self._hide_wall_angle_radial()

    def _wall_angle_anchor(self, pos):
        # While a segment is live, its angle belongs to its start/joint.
        active=self.controller.active
        if active is not None and hasattr(active,'start'):
            sx,sy=active.start
            return self.mapFromScene(QPointF(float(sx),float(sy)))

        click_scene=self.mapToScene(pos)

        # After committing a segment, anchor the menu to the nearest end of that
        # last wall instead of leaving the choices floating under the mouse.
        preview=self.controller.preview
        if getattr(preview,'kind','')=='wall':
            geom=getattr(preview,'geometry',{}) or {}
            if all(key in geom for key in ('x1','y1','x2','y2')):
                candidates=((float(geom['x1']),float(geom['y1'])),(float(geom['x2']),float(geom['y2'])))
                px,py=float(click_scene.x()),float(click_scene.y())
                ax,ay=min(candidates,key=lambda p:(p[0]-px)**2+(p[1]-py)**2)
                return self.mapFromScene(QPointF(ax,ay))

        # If an existing wall is the context target, use its nearest endpoint.
        target=self._wall_menu_target_entity
        if target and target in self.doc.entities:
            entity=self.doc.get(target)
            if entity.kind=='wall':
                p=entity.params
                candidates=((float(p['x1']),float(p['y1'])),(float(p['x2']),float(p['y2'])))
                px,py=float(click_scene.x()),float(click_scene.y())
                ax,ay=min(candidates,key=lambda q:(q[0]-px)**2+(q[1]-py)**2)
                return self.mapFromScene(QPointF(ax,ay))

        return pos

    def _show_wall_angle_radial(self, pos):
        self._hide_wall_angle_radial()

        # The menu belongs to the architectural corner, not to the cursor.
        anchor=self._wall_angle_anchor(pos)
        cx,cy=int(anchor.x()),int(anchor.y())

        options=(
            ('90°','angle',90.0,0,-72),
            ('45°','angle',45.0,70,-36),
            ('15°','angle',15.0,70,36),
            ('Free','angle',None,0,72),
            ('Undo','command','undo',-74,36),
            ('Delete','command','delete',-74,-36),
        )
        current=self.controller.wall_angle_increment
        for label,kind,value,dx,dy in options:
            button=QToolButton(self.viewport())
            button.setText(label)
            button.setAutoRaise(False)
            selected=False
            if kind=='angle':
                selected=(
                    (current is None and value is None)
                    or (current not in (None,'magnet') and value not in (None,'magnet') and abs(float(current)-float(value))<1e-9)
                )
            danger=(kind=='command' and value=='delete')
            base='#ffe5e5' if danger else ('#cfe7ff' if selected else '#f7f7f7')
            button.setStyleSheet(
                'QToolButton {'
                'background: %s; border: 1px solid #7c8792; border-radius: 15px;'
                'padding: 4px 9px; font-weight: %s;'
                '} QToolButton:hover { background: %s; }'
                % (
                    base,
                    '600' if selected else '400',
                    '#ffd0d0' if danger else '#d9ecff',
                )
            )
            button.adjustSize()
            w=max(48,button.sizeHint().width());h=max(30,button.sizeHint().height())
            button.resize(w,h)
            button.move(cx+dx-w//2,cy+dy-h//2)
            if kind=='angle':
                button.clicked.connect(lambda checked=False,v=value:self._choose_wall_angle(v))
            else:
                button.clicked.connect(lambda checked=False,v=value:self._wall_radial_command(v))
            button.show()
            button.raise_()
            self._wall_angle_buttons.append(button)

        label='Free' if current is None else ('Magnets' if current=='magnet' else f'{float(current):g}°')
        self.statusChanged.emit(
            f'Wall corner menu — {label} · Undo/Delete available · Shift = temporary Free'
        )

    def redraw(self):
        self._scene.clear();self._handle_items.clear();self._entity_items.clear();self._draw_grid();frame=build_plan_frame(self.doc,self.controller.preview);self._frame=frame
        if self.structural_only:
            structural_ids={
                eid for eid,e in self.doc.entities.items()
                if e.kind in ('structural_column','structural_beam')
                and str(e.params.get('role','structural'))=='structural'
            }
            structural_ids.update(
                eid for eid,e in self.doc.entities.items()
                if e.kind in ('structural_support','structural_load')
                and e.parent_id in structural_ids
            )
            context_kinds={
                'wall','pod','door','window','opening','stair','ramp',
                'room_floor','room_foundation','room_roof',
            }
            structural_primitives=[]
            for p in frame.primitives:
                if p.role=='preview' or (p.entity_id and p.entity_id in structural_ids):
                    structural_primitives.append(p)
                    continue
                if p.entity_id and p.entity_id in self.doc.entities:
                    entity=self.doc.get(p.entity_id)
                    if entity.kind in context_kinds:
                        # Architectural geometry remains visible only as orientation
                        # context. It has no entity id in this view, so Structural mode
                        # cannot accidentally edit architectural objects.
                        structural_primitives.append(
                            Primitive2D(
                                p.kind,p.points,p.radius_x,p.radius_y,p.rotation,'',
                                'structural-context',p.meta,
                            )
                        )
            frame.primitives=structural_primitives
            frame.handles=[h for h in frame.handles if h.entity_id in structural_ids]
            try:
                from archforge.structure.graph import build_structural_graph
                graph=build_structural_graph(self.doc)
                visible_node_ids=set()
                member_map={member.entity_id:member for member in graph.members}
                for member in graph.members:
                    if member.entity_id in structural_ids:
                        visible_node_ids.add(member.start_node)
                        visible_node_ids.add(member.end_node)
                for node in graph.nodes:
                    if node.index not in visible_node_ids:
                        continue
                    x,y,z=node.point
                    frame.primitives.append(
                        Primitive2D(
                            'ellipse',((x,y),),0.055,0.055,0.0,'','structural-node',
                            meta=(('semantic','structural-node'),('node_index',node.index),('z',z)),
                        )
                    )

                for load in graph.loads:
                    member=member_map.get(load.member_entity_id)
                    if member is None or member.entity_id not in structural_ids:
                        continue
                    a=graph.nodes[member.start_node].point
                    b=graph.nodes[member.end_node].point
                    t=max(0.0,min(1.0,float(load.position)))
                    x=float(a[0])+(float(b[0])-float(a[0]))*t
                    y=float(a[1])+(float(b[1])-float(a[1]))*t
                    dx,dy,dz=(float(v) for v in load.direction)
                    scale=0.55
                    if abs(dx)+abs(dy)>1e-9:
                        mag=(dx*dx+dy*dy)**0.5
                        ux,uy=dx/mag,dy/mag
                        frame.primitives.append(
                            Primitive2D(
                                'line',((x-ux*scale,y-uy*scale),(x,y)),
                                entity_id=load.entity_id,role='structural-load',
                                meta=(('semantic','structural-load'),('input_only',True)),
                            )
                        )
                    else:
                        frame.primitives.append(
                            Primitive2D(
                                'ellipse',((x,y),),0.07,0.07,0.0,
                                load.entity_id,'structural-load',
                                meta=(('semantic','structural-load'),('input_only',True)),
                            )
                        )
                    arrow='↓' if dz<0 else ('↑' if dz>0 else '→')
                    label=f'INPUT {arrow} {load.magnitude:g} {load.unit} · {load.load_case}'
                    frame.primitives.append(
                        Primitive2D(
                            'label',((x+0.08,y+0.08),),
                            entity_id=load.entity_id,role='structural-load-label',
                            meta=(('semantic','structural-load'),('text',label),('source',load.source)),
                        )
                    )
            except (ValueError,KeyError):
                pass
        for p in frame.primitives:self._draw_primitive(p)
        for h in frame.handles:self._draw_handle(h)
        if frame.snap:self._draw_snap(frame.snap)
        if frame.hud:self._draw_hud(frame.hud)
        draft=getattr(self,'_railing_draft',None)
        if draft is not None and len(draft.preview())>=2:
            # Railing being drawn: dashed line through the corners and to the cursor.
            pen=QPen(QColor(40,150,70));pen.setWidthF(.04);pen.setStyle(Qt.PenStyle.DashLine);pts=draft.preview()
            path=QPainterPath(QPointF(*pts[0]))
            for q in pts[1:]:path.lineTo(QPointF(*q))
            self._scene.addPath(path,pen).setZValue(30)
        drag=getattr(self,'_view_drag',None)
        if drag:
            # Section/camera line: dashed from the eye point along the view.
            pen=QPen(QColor(200,60,40));pen.setWidthF(.05);pen.setStyle(Qt.PenStyle.DashLine)
            (ax,ay),(bx,by)=drag;self._scene.addLine(ax,ay,bx,by,pen).setZValue(30)
            dot=QPen(QColor(200,60,40));dot.setWidthF(.05);self._scene.addEllipse(ax-.12,ay-.12,.24,.24,dot,QBrush(QColor(200,60,40))).setZValue(30)
        marker=getattr(self,'assistant_marker',None)
        if marker is not None:
            # Assistant marker: where the human pointed (UI state, not part of the Document).
            mx,my=marker;red=QColor(220,30,40);pen=QPen(red);pen.setWidthF(.04)
            self._scene.addEllipse(mx-.18,my-.18,.36,.36,pen,QBrush(QColor(220,30,40,60))).setZValue(40)
            self._scene.addLine(mx-.32,my,mx+.32,my,pen).setZValue(40);self._scene.addLine(mx,my-.32,mx,my+.32,pen).setZValue(40)
        r=self.mapToScene(self.viewport().rect()).boundingRect();self._scene.setSceneRect(r.adjusted(-5,-5,5,5))
        self.previewChanged.emit(copy.deepcopy(self.controller.preview))
    def _draw_grid(self):
        extent=100;pen=QPen(QColor(225,225,225));pen.setWidthF(0);axis=QPen(QColor(160,160,160));axis.setWidthF(0)
        for i in range(-extent,extent+1):self._scene.addLine(i,-extent,i,extent,axis if i==0 else pen).setZValue(-100);self._scene.addLine(-extent,i,extent,i,axis if i==0 else pen).setZValue(-100)
    def _has_symbol(self,entity_id):
        frame=getattr(self,'_frame',None)
        prims=frame.primitives if frame is not None else ()
        return any(q.role=='library-symbol' and q.entity_id==entity_id for q in prims)
    def _draw_primitive(self,p:Primitive2D):
        preview=p.role=='preview';opening=p.role=='opening';room=p.role=='derived-room';terrain=p.role in ('terrain','plant')
        # The storey below is drawn like structural context: faint grey.
        context=p.role in ('structural-context','floor-underlay')
        pen=QPen(
            QColor(150,150,150,150)
            if context else
            (QColor(180,90,20) if opening else (QColor(40,150,70) if preview else (QColor(95,140,60) if terrain else QColor(45,55,65))))
        )
        pen.setWidthF(.022 if context else (.06 if opening else (.04 if preview else .035)));item=None
        if opening and dict(p.meta).get('typed'):
            # Typed joinery draws its own symbol; keep the pick line light.
            pen=QPen(QColor(180,90,20,110));pen.setWidthF(.02)
        if preview and dict(p.meta).get('fits') is False:pen=QPen(QColor(210,40,40));pen.setWidthF(.05)
        if p.role=='library-symbol':pen=QPen(QColor(40,45,55));pen.setWidthF(.012)
        if p.role in ('cabinet','cabinet-front'):pen=QPen(QColor(40,45,55));pen.setWidthF(.012)
        if p.role in ('railing','railing-post'):pen=QPen(QColor(40,45,55));pen.setWidthF(.01)
        if p.role in ('pipe-cold','pipe-hot'):
            pen=QPen(QColor(31,111,209) if p.role=='pipe-cold' else QColor(209,48,31))
            pen.setWidthF(.035 if dict(p.meta).get('diameter',16)>=20 else .02)
        if p.role in ('roof-outline','roof-ridge'):
            pen=QPen(QColor(150,70,40));pen.setWidthF(.02 if p.role=='roof-outline' else .015)
            pen.setStyle(Qt.PenStyle.DashLine if p.role=='roof-outline' else Qt.PenStyle.DashDotLine)
        if p.role=='cable':
            from archforge.mep.electrical import CABLE_COLORS
            pen=QPen(QColor(CABLE_COLORS.get(dict(p.meta).get('group'),'#e07a00')));pen.setWidthF(.015)
            pen.setStyle({'wall':Qt.PenStyle.SolidLine,'floor':Qt.PenStyle.DotLine}.get(dict(p.meta).get('run'),Qt.PenStyle.DashLine))
        if p.role=='manifold':
            pen=QPen(QColor(31,111,209) if dict(p.meta).get('system')=='cold' else QColor(209,48,31));pen.setWidthF(.012)
        if p.role=='elec-box':
            pen=QPen(QColor({'pull':'#c0262d','floor':'#0a8a5a'}.get(dict(p.meta).get('box'),'#3a3f48')));pen.setWidthF(.012)
        if p.role=='electrical-point':pen=QPen(QColor(200,120,0));pen.setWidthF(.02)
        if p.role=='plumbing-point':pen=QPen(QColor(31,90,160));pen.setWidthF(.02)
        if p.role=='duct':
            # Overhead element (under the ceiling): dashed, drawn at its true Ø.
            pen=QPen(QColor(105,115,128,200));pen.setWidthF(float(dict(p.meta).get('diameter',125))/1000.)
            pen.setStyle(Qt.PenStyle.DashLine);pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        if p.role in ('drain','drain-node','drain-stack','drainage-point'):
            pen=QPen(QColor(150,80,30));pen.setWidthF(max(.015,float(dict(p.meta).get('diameter',50))/2500.) if p.role=='drain' else .015)
            if p.role=='drain' and dict(p.meta).get('kind')=='branch':pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='wall-move-opening':
            pen=QPen(QColor(180,90,20,170));pen.setWidthF(.07)
        if p.role=='wall-move-arrow':
            pen=QPen(QColor(20,110,220));pen.setWidthF(.025);pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='angle-arc':
            # Corner mark: blue on a magnet (90/45/15), grey for a free angle.
            pen=QPen(QColor(20,110,220) if dict(p.meta).get('magnet') else QColor(120,120,120));pen.setWidthF(.02)
        if p.role in ('footing','tie-beam'):
            # Below the floor: hidden lines.
            pen=QPen(QColor(95,95,90));pen.setWidthF(.015);pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='joist':
            pen=QPen(QColor(150,105,45) if dict(p.meta).get('ok',True) else QColor(200,40,40));pen.setWidthF(.02);pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='joists-area':pen=QPen(QColor(150,105,45,120));pen.setWidthF(.01)
        if p.role in ('vent-terminal','ventilation-point'):pen=QPen(QColor(70,80,95));pen.setWidthF(.015)
        if p.role in ('wall-layer','wall-insulation'):
            pen=QPen(QColor(120,110,95) if p.role=='wall-layer' else QColor(200,150,40));pen.setWidthF(.008)
            if p.role=='wall-insulation':pen.setStyle(Qt.PenStyle.DashLine)
        if p.role in ('opening-symbol','opening-symbol-hidden'):
            pen=QPen(QColor(40,45,55));pen.setWidthF(.018 if dict(p.meta).get('style')=='solid' else .01)
            if p.role=='opening-symbol-hidden':pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='cabinet-wall':
            pen=QPen(QColor(70,80,95));pen.setWidthF(.01);pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='library-object' and self._has_symbol(p.entity_id):
            # Footprint stays for picking; the symbol carries the drawing.
            pen=QPen(QColor(150,160,170,90));pen.setWidthF(.006)
        if p.kind=='line':a,b=p.points;item=self._scene.addLine(a[0],a[1],b[0],b[1],pen)
        elif p.kind=='polyline':
            if len(p.points)>=2:
                path=QPainterPath(QPointF(p.points[0][0],p.points[0][1]))
                for x,y in p.points[1:]:
                    path.lineTo(float(x),float(y))
                item=self._scene.addPath(path,pen)
        elif p.kind=='polygon':
            from PySide6.QtGui import QPolygonF
            brush=QBrush(
                QColor(160,160,160,18)
                if context else
                (QColor(90,180,120,28) if room else (QColor(150,140,125,70) if p.role=='site-path' else (QColor(255,255,255,1) if p.role=='library-object' else (QColor(236,230,220,120) if p.role=='cabinet' else (QColor(0,0,0,0) if p.role in ('cabinet-wall','joists-area') else QColor(80,160,220,40))))))
            )
            room_pen=QPen(QColor(110,150,120));room_pen.setWidthF(.015)
            item=self._scene.addPolygon(QPolygonF([QPointF(x,y) for x,y in p.points]),room_pen if room else pen,brush)
        elif p.kind=='ellipse':
            cx,cy=p.points[0];item=self._scene.addEllipse(
                cx-p.radius_x,cy-p.radius_y,2*p.radius_x,2*p.radius_y,pen,
                QBrush(QColor(160,160,160,14) if context else QColor(170,120,210,30))
            )
        elif p.kind=='label':
            meta=dict(p.meta);text=str(meta.get('text',''));cx,cy=p.points[0];item=self._scene.addText(text);item.setDefaultTextColor(QColor(55,80,65))
            if p.role=='wall-move-label':
                # Distance of a dragged wall: blue and bold, like the angle mark.
                f=item.font();f.setBold(True);f.setPointSizeF(f.pointSizeF()*1.25);item.setFont(f)
                item.setDefaultTextColor(QColor(210,40,40) if text.startswith('⚠') else QColor(20,110,220))
            item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True);item.setPos(cx,cy);item.setTransformOriginPoint(item.boundingRect().center());item.setScale(1.0);item.setZValue(8);return
        if item is not None:
            container=bool(p.entity_id) and p.entity_id in self.doc.entities and self.doc.get(p.entity_id).kind in self.CONTAINER_KINDS
            item.setZValue(-20 if context else (-10 if room else (10 if opening else (20 if preview else (-5 if container else 0)))))
            if p.entity_id and not preview:self._entity_items[item]=p.entity_id
    def _draw_handle(self,h):
        r=.09;it=self._scene.addEllipse(h.x-r,h.y-r,2*r,2*r,QPen(QColor(20,90,180),0),QBrush(QColor(255,255,255)));it.setZValue(50);self._handle_items[it]=h
    def _draw_snap(self,s):
        r=.08
        angle_lock=str(s.get('kind','')).startswith('angle')
        color=QColor(50,110,220) if angle_lock else QColor(220,80,40)
        self._scene.addEllipse(
            s['x']-r,s['y']-r,2*r,2*r,QPen(color,0)
        ).setZValue(70)
    def _draw_hud(self,hud):
        text='  '.join(f'{k}: {v:.3f}' for k,v in hud.items() if isinstance(v,(int,float)));it=self._scene.addText(text);it.setDefaultTextColor(QColor(20,20,20));it.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True);it.setPos(self.mapToScene(self.viewport().rect().topLeft()));it.setZValue(100)
