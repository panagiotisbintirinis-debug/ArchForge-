from __future__ import annotations
import math
import copy
from typing import Optional, Dict

from PySide6.QtCore import QEvent, Qt, QPointF, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QPainterPath, QTransform
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsTextItem, QGraphicsPathItem, QMenu, QToolButton

from archforge.core.model import Document
from archforge.core.commands import CommandStack
from archforge.core.viewport import PointerController, PointerEvent
from archforge.core.plan_scene import build_plan_frame, Primitive2D, Handle2D
from archforge.ui.object_context_menu import object_context_actions

class _OpenPathItem(QGraphicsPathItem):
    """An open polyline (railing, run): picked near its line only — Qt's default shape also takes
    the area the path would enclose, so a click inside a balcony picked its railing."""
    REACH = 0.12
    def shape(self):
        from PySide6.QtGui import QPainterPathStroker
        stroker = QPainterPathStroker(); stroker.setWidth(2 * self.REACH)
        return stroker.createStroke(self.path())


_PDF_CACHE={}


def _pdf_page_image(path,page,dpi=150):
    """Rendered PDF page (QImage), cached per file/page/modification time; None when the file is missing."""
    import os
    try:
        key=(str(path),int(page),os.path.getmtime(path),dpi)
    except OSError:
        return None
    if key not in _PDF_CACHE:
        from PySide6.QtCore import QSize
        from PySide6.QtPdf import QPdfDocument
        doc=QPdfDocument()
        if doc.load(str(path))!=QPdfDocument.Error.None_ or not 0<=page<doc.pageCount():
            return None
        pt=doc.pagePointSize(page)
        len(_PDF_CACHE)>=4 and _PDF_CACHE.clear();_PDF_CACHE[key]=doc.render(page,QSize(int(pt.width()*dpi/72),int(pt.height()*dpi/72)))
    return _PDF_CACHE[key]


def add_underlay_item(scene,p):
    """One underlay (PDF page / DXF lines) in ``scene``: faint, behind everything, never selectable.

    Scene axes are the underlay's (x, y) with y up — plan x, y or a section's u, z."""
    if p['source']=='dxf':
        from PySide6.QtGui import QPainterPath
        from archforge.project.underlay import model_segments
        path=QPainterPath()
        for x1,y1,x2,y2 in model_segments(p):path.moveTo(x1,y1);path.lineTo(x2,y2)
        pen=QPen(QColor(70,90,120));pen.setCosmetic(True);pen.setWidthF(1.0)
        item=scene.addPath(path,pen)
    else:
        image=_pdf_page_image(p['path'],int(p['page']))
        if image is None:
            from archforge.project.underlay import to_model
            (ax,ay),(bx,by)=to_model(p,0,0),to_model(p,float(p.get('page_w',595)),float(p.get('page_h',842)))
            pen=QPen(QColor(200,60,60));pen.setCosmetic(True);pen.setStyle(Qt.PenStyle.DashLine)
            item=scene.addRect(min(ax,bx),min(ay,by),abs(bx-ax),abs(by-ay),pen)
            item.setToolTip(f"Λείπει το αρχείο PDF: {p['path']}")
        else:
            from PySide6.QtGui import QPixmap
            item=scene.addPixmap(QPixmap.fromImage(image))
            # Image pixels -> PDF points (y down) -> model (y up), scale and rotation of the underlay.
            k=float(p.get('page_w',image.width()))/max(1,image.width())
            s_=float(p['m_per_unit']);r=math.radians(float(p.get('rotation',0.0)));c,sn=math.cos(r),math.sin(r)
            ph=float(p.get('page_h',image.height()*k))
            a,b=s_*k*c,s_*k*sn;cc,d=s_*k*sn,-s_*k*c
            ox,oy=float(p['x'])-(float(p.get('u0',0.0)))*s_,float(p['y'])
            # v = ph - py*k  ->  model = base + R*s*(u, ph - py*k)
            tx=ox+(-sn)*s_*ph;ty=oy+c*s_*ph
            item.setTransform(QTransform(a,b,0,cc,d,0,tx,ty,1))
            item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
    item.setOpacity(float(p.get('opacity',0.6)));item.setZValue(-60)
    return item


class PlanView(QGraphicsView):
    selectionChangedByView=Signal();contextActionRequested=Signal(str,str);commandRequested=Signal(str);previewChanged=Signal(object);statusChanged=Signal(str)
    # (kind, x1, y1, x2, y2): a Section or Camera line dragged in the plan.
    viewLineRequested=Signal(str,float,float,float,float)
    VIEW_LINE_TOOLS={'view_section':'section','view_camera':'camera'}
    # Single-click site tools: (tool, x, y) handled by the main window.
    sitePointRequested=Signal(str,float,float)
    SITE_POINT_TOOLS=('terrain_point','plot_point','room_box','room_place','room_resize','plant_tree','plant_shrub','library_place','underlay_calibrate','pool_place','dome_place','mech_part_place')
    # Drag tools for site strips: (tool, x1, y1, x2, y2).
    siteLineRequested=Signal(str,float,float,float,float)
    SITE_LINE_TOOLS=('path_path','path_sidewalk','path_road','pergola_timber','pergola_aluminium','elec_led_strip')
    # Railing tools ('railing_<type>'): click corners, double click / Enter to finish -> (tool, points, closed).
    railingRequested=Signal(str,object,bool)
    # Slab opening / atrium tool: drag a rectangle or click a polygon -> outline points.
    slabOpeningRequested=Signal(object)
    # Suspended plasterboard ceiling ('drywall_ceiling'): same drawing as the slab opening -> outline points.
    drywallCeilingRequested=Signal(object)
    # Balcony ('balcony'): same drawing -> outline points (slab + railing, architecture/balcony.py).
    balconyRequested=Signal(object)
    def _slab_tool(self):return self.controller.tool in ('slab_opening','drywall_ceiling','balcony')
    def _slab_word(self):return {'drywall_ceiling':'Ψευδοροφή','balcony':'Μπαλκόνι'}.get(self.controller.tool,'Οπή πλάκας')
    def _slab_draft_get(self):
        if getattr(self,'_slab_draft',None) is None:
            from archforge.ui.slab_tools import SlabDraft
            self._slab_draft=SlabDraft()
        return self._slab_draft
    def finish_slab_opening(self,points=None):
        draft=self._slab_draft_get();points=points or draft.finish();self._slab_draft=None;self.redraw()
        if points:{'drywall_ceiling':self.drywallCeilingRequested,'balcony':self.balconyRequested}.get(self.controller.tool,self.slabOpeningRequested).emit([list(q) for q in points])
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
        self._mouse_down=False;self._handle_items={};self._entity_items={};self._active_handle=None;self._hud_item=None;self._wall_angle_buttons=[];self._wall_menu_target_entity=None;self.scale(55.0,-55.0);self.setAcceptDrops(True);self.viewport().setAcceptDrops(True);self.redraw()
    def rebind(self,doc,stack):
        self.doc=doc;self.stack=stack;self.controller=PointerController(doc,stack)
        if getattr(self,'_grid_step',None):self.controller.grid=self.controller.construction_grid=self._grid_step
        self.redraw()
    TOOL_LABELS={'select':'Επιλογή','wall':'Τοίχος','door':'Πόρτα','window':'Παράθυρο','opening_rect':'Άνοιγμα','stair':'Σκάλα',
                 'ramp':'Ράμπα','structural_column':'Κολόνα','structural_beam':'Δοκός','component':'Τοποθέτηση','move':'Μετακίνηση',
                 'rotate':'Περιστροφή','stretch':'Τέντωμα'}
    def set_tool(self,tool):self.controller.set_tool(tool);self._active_handle=None;self._railing_draft=None;self._slab_draft=None;self.statusChanged.emit(f'Εργαλείο: {self.TOOL_LABELS.get(tool,tool)}');self.redraw()
    # Grid lines on/off and the grid/snap step (Κάνναβος & έλξη bar): view state, not Document.
    def set_grid_visible(self,on):self._show_grid=bool(on);self.redraw()
    # Owner 22/10: «υποτίθεται ότι είχαμε αυτόματο σναπ … και εργαλείο να ρυθμίσουμε την απόσταση».  The snap
    # tolerance was a fixed 0,10 m: 5–7 pixels at a whole-house zoom, so an end clicked a little off stayed 2–5 cm
    # short and the room did not close.  It is a reach on the screen now (pixels, «Ακτίνα έλξης»), at any zoom.
    # Capped at 25 cm (what the room graph joins anyway): zoomed far out, 14 px would be metres and a moved
    # object would stick to where it was (CI, Windows runner: a body drag stayed at its start).
    SNAP_PIXELS=14;SNAP_MAX=0.25
    def set_snap_pixels(self,pixels):
        self.snap_pixels=max(2,int(pixels));self._sync_snap_tolerance()
    def _sync_snap_tolerance(self):
        px_per_m=abs(self.transform().m11()) or 1.0
        self.controller.snap_tolerance=min(self.SNAP_MAX,max(0.01,float(getattr(self,'snap_pixels',self.SNAP_PIXELS))/px_per_m))
    def set_grid_step(self,step):
        self._grid_step=float(step);self.controller.grid=self.controller.construction_grid=self._grid_step;self.redraw()
    def drawForeground(self,painter,rect):
        # Rulers, scale bar, cursor X/Y, live measures and the empty-project hint, in screen pixels.
        from archforge.ui.plan_overlay import paint_overlay
        painter.save();painter.resetTransform();paint_overlay(self,painter);painter.restore()
        if self.controller.tool in ('room_box','room_place'):
            from archforge.ui.room_box_tool import paint_preview
            paint_preview(self,painter)
    def leaveEvent(self,event):self._cursor_xy=None;self.viewport().update();super().leaveEvent(event)
    # Things that carry other things (slabs, roofs, joists, ground): picked only
    # when nothing more specific (a stair, a cabinet, an MEP point…) is under the cursor.
    CONTAINER_KINDS=('room_floor','room_ceiling','room_foundation','room_roof','floor','room',
                     'pitched_roof','ceiling_joists','terrain')

    def _room_at(self,pos):
        """True when the view point lies inside a room of the active storey."""
        from archforge.geometry.regions import point_in_polygon
        q=self._scene_to_plane(pos)
        try:return any(point_in_polygon(float(q.a),float(q.b),f.polygon) for f in self.doc.active_room_faces())
        except (ValueError,KeyError):return False
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
        if self.carry is not None:
            # A Library item in hand: the wheel turns it 15° before it is dropped.
            from archforge.ui.library_drag import TURN_STEP
            self.carry.turn_by(TURN_STEP if event.angleDelta().y()>0 else -TURN_STEP);self.redraw();self.statusChanged.emit(self.carry.label());event.accept();return
        # During a live Stair/Ramp placement the wheel picks the next option.
        if self.controller.cycle_option(-1 if event.angleDelta().y()>0 else 1):
            self.redraw();event.accept();return
        from archforge.ui.view_zoom import zoom_about
        zoom_about(self,event)   # the drawing point under the cursor stays under it (touchpad: two fingers pan)
        self._update_label_visibility()
    def _overlay(self,kind,event):
        # Overlay tool (the assistant's kitchen/bath guide lines, fixture drag): gets the mouse first.
        # The camera tool (ui/camera_tool.py: place / move / turn a camera) comes first.
        return any(tool is not None and bool(tool.handle(self,kind,event)) for tool in (getattr(self,'tape_tool',None),getattr(self,'pool_tool',None),getattr(self,'terrain_tool',None),getattr(self,'camera_tool',None),getattr(self,'overlay_tool',None),getattr(self,'dims_tool',None)))
    CLICK_PX=8   # press → release within this many screen pixels is a click, not a drag
    def _wall_chain_active(self):
        return getattr(self.controller,'wall_chain',None) is not None and self.controller.active is not None
    def _hovered_entity(self):
        """The object under the mouse (not a slab / roof / ground it stands on), or None."""
        cursor=getattr(self,'_cursor_xy',None)
        if cursor is None:return None                   # the mouse is not over the plan
        from PySide6.QtCore import QPointF
        hit=self.itemAt(self.mapFromScene(QPointF(*cursor)))
        eid=self._entity_items.get(hit)
        if eid and eid in self.doc.entities and self.doc.get(eid).kind not in self.CONTAINER_KINDS:return eid
        return None
    _indicated=None
    def indicate(self,eid):
        """One click: the object under the mouse is shown (outlined, its name and size below) — not selected."""
        self._indicated=eid if eid and eid in self.doc.entities else None
        if self._indicated:
            from archforge.ui.indication import describe
            self.statusChanged.emit(describe(self.doc,self._indicated)+' · διπλό κλικ = επιλογή')
    def to_select(self,message='Επιλογή'):
        """Back to Επιλογή (owner 23/10: «τα εργαλεία συνεχίζουν να δουλεύουν, πρέπει να πατήσω επιλογή»)."""
        window=getattr(self,'marking_menu_window',None)
        if str(self.controller.tool)!='select':
            (window._set_active_tool if window is not None else self.controller.set_tool)('select')
        self.statusChanged.emit(message);self.redraw()
    def finish_wall_chain(self):
        count=(self.controller.wall_chain or {}).get('count',0)
        self.controller.finish_wall_chain();self._mouse_down=False;self.redraw()
        self.statusChanged.emit(f'Τοίχοι: έγιναν {count} · Ctrl+Z = αναίρεση του τελευταίου' if count else 'Τοίχος: ακυρώθηκε')
    def mouseDoubleClickEvent(self,event):
        self._sync_snap_tolerance()
        if self._overlay('dclick',event):event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and self.controller.tool=='plot_point':
            self.finish_plot();event.accept();return
        # Double click, in every tool: what is being drawn ends there, and the tool gives way to Επιλογή (owner 23/10).
        if event.button()==Qt.MouseButton.LeftButton and self._wall_chain_active():
            count=(self.controller.wall_chain or {}).get('count',0)
            self.finish_wall_chain();self.to_select(f'Τοίχοι: έγιναν {count} · Επιλογή · Ctrl+Z = αναίρεση του τελευταίου' if count else 'Επιλογή')
            event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and self._railing_tool():self.finish_railing();self.to_select();event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and self._slab_tool():self.finish_slab_opening();self.to_select();event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and str(self.controller.tool)!='select' and self._tool_idle():
            self.to_select();event.accept();return
        if event.button()==Qt.MouseButton.LeftButton:
            # Double click = selection (owner 23/10): the object, its handles and its Ιδιότητες.
            hit=self.itemAt(event.position().toPoint());eid=self._entity_items.get(hit)
            if eid and eid in self.doc.entities:
                self.doc.select([eid],add=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier));self.controller.set_target(eid,None)
                self._indicated=None;self.selectionChangedByView.emit();self.redraw()
                self.statusChanged.emit('Επιλογή: '+__import__('archforge.ui.indication',fromlist=['describe']).describe(self.doc,eid)
                                        +' · πάτημα και σύρσιμο = μεταφορά · Delete = διαγραφή')
                event.accept();return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self,event):
        menu=getattr(self,'_marking_menu',None)
        if menu is not None and not menu.isHidden():
            self.hide_marking_menu();event.accept();return
        if self._overlay('context',event):event.accept();return
        if self._wall_chain_active():self.finish_wall_chain();event.accept();return
        window=getattr(self,'marking_menu_window',None)
        if window is not None:
            # One task-dependent mouse menu (marking menu), shared with the 3D view.
            hit=self.itemAt(event.pos());handle=self._handle_items.get(hit)
            eid=handle.entity_id if handle is not None else self._entity_items.get(hit)
            busy=self.controller.tool=='wall' or window.sculpt_action.isChecked()
            if eid in self.doc.entities and self.doc.get(eid).kind in self.CONTAINER_KINDS and self._room_at(event.pos()):
                eid=None          # inside a room the room's menu (Κουζίνα / Μπάνιο εδώ…), not the storey's floor slab
            if busy or not eid or eid not in self.doc.entities:
                eid=None
            elif eid not in self.doc.selection:      # right click inside a multiple selection keeps it (Διαγραφή = all)
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

    # Pan: hold the left button still (long press) or drag with the middle button / wheel pressed.
    LONG_PRESS_MS=400
    def _pan_begin(self,pos):
        from PySide6.QtGui import QCursor
        self._panning=pos;self._long_press=None
        self.viewport().setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        self.statusChanged.emit('Μετακίνηση σχεδίου — σύρε · άφησε το κουμπί για τέλος')
    def _pan_end(self):
        self._panning=None;self._mouse_down=False;self._wall_press=None;self._body_press=None
        self.viewport().unsetCursor();self.statusChanged.emit('')
    def _long_press_fire(self,token):
        lp=getattr(self,'_long_press',None)
        if lp is None or lp[0]!=token or getattr(self,'_panning',None) is not None:return
        from PySide6.QtWidgets import QApplication
        if not QApplication.mouseButtons()&Qt.MouseButton.LeftButton:return
        if self.controller.active is not None and self.controller.active is not lp[2]:
            self.controller.cancel()          # what this press started (a wall, a move) gives way to the pan
        self._railing_draft=None if lp[3] else getattr(self,'_railing_draft',None)
        self._pan_begin(lp[1]);self.redraw()
    def mousePressEvent(self,event):
        self._sync_snap_tolerance()
        if event.button()==Qt.MouseButton.MiddleButton:
            self._pan_begin(event.position());event.accept();return
        if event.button()==Qt.MouseButton.LeftButton:
            self._hide_wall_angle_radial();self.hide_marking_menu()
            from PySide6.QtCore import QTimer
            token=object()
            self._long_press=(token,event.position(),self.controller.active,getattr(self,'_railing_draft',None) is None)
            # Counted from when this press has been handled (a stair being solved can take 0,2–0,3 s): a 0 ms timer
            # runs once the handler returns, then the hold time starts — slow work never turns a drag into a pan.
            QTimer.singleShot(0,lambda t=token:QTimer.singleShot(self.LONG_PRESS_MS,lambda:self._long_press_fire(t)))
        if event.button()!=Qt.MouseButton.LeftButton:super().mousePressEvent(event);return
        if self._overlay('press',event):event.accept();return
        if self._railing_tool():self._railing_press(event);event.accept();return
        if self._slab_tool():
            ev=self._scene_to_plane(event.position().toPoint());self._slab_draft_get().down(ev.a,ev.b);self._mouse_down=True
            self.redraw();event.accept();return
        if self.controller.tool not in self.SITE_LINE_TOOLS and (self.controller.tool in self.SITE_POINT_TOOLS or str(self.controller.tool).startswith(('plumb_','elec_','vent_','heat_','assist_','drain_','roofroom_','railingstair_','drywallroom'))):
            ev=self._scene_to_plane(event.position().toPoint())
            self.sitePointRequested.emit(self.controller.tool,float(ev.a),float(ev.b));event.accept();return
        if self.controller.tool in self.VIEW_LINE_TOOLS or self.controller.tool in self.SITE_LINE_TOOLS:
            ev=self._scene_to_plane(event.position().toPoint());self._mouse_down=True
            self.begin_view_line(ev.a,ev.b);event.accept();return
        self._mouse_down=True;self._press_pos=event.position();hit=self.itemAt(event.position().toPoint())
        if hit in self._handle_items:
            # A press on a handle is a drag of that handle: holding still first is not the long-press pan.
            h=self._handle_items[hit];self._active_handle=h;self._long_press=None
            self.doc.select([h.entity_id]);self.selectionChangedByView.emit()
            if h.handle=='flip_swing':
                # Click on the swing arc: opens the other way; Shift/Ctrl = other hinge side (one undo).
                key='hinge' if event.modifiers()&(Qt.KeyboardModifier.ShiftModifier|Qt.KeyboardModifier.ControlModifier) else 'swing'
                self._mouse_down=False;self._active_handle=None;self.run_object_op(h.entity_id,key);event.accept();return
            if h.handle=='rotate':
                # Round handle: drag turns the object about its centre (15° steps, Shift free).
                self.controller.set_tool('rotate');self.controller.set_target(h.entity_id,None);self._restore_select=True
            else:
                # A handle dragged from Επιλογή gives the tool back afterwards (as the round rotate handle does).
                self._restore_select=getattr(self,'_restore_select',False) or self.controller.tool=='select'
                if h.handle=='move' or h.cursor=='move':
                    self.controller.set_tool('move');self.controller.set_target(h.entity_id,h.handle)
                else:
                    self.controller.set_tool('stretch');self.controller.set_target(h.entity_id,h.handle)
        elif self.controller.tool=='select':
            # Owner 24/10 (after Home Designer / Chief Architect / ArchiCAD): a click selects, pressing and dragging moves
            # it at once (was 23/10: click = indication, double click = selection). Ctrl+click adds / removes; a click
            # on empty space clears the selection.
            eid=self._entity_items.get(hit)
            ctrl=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier)
            if eid and ctrl:self.doc.select([eid],add=True);self.selectionChangedByView.emit()
            elif eid and eid not in (self.doc.selection or ()):
                self.doc.select([eid]);self.controller.set_target(eid,None);self.selectionChangedByView.emit()
            elif not eid and not ctrl and self.doc.selection:self.doc.select([]);self.selectionChangedByView.emit()
            self.indicate(eid)
            selected=bool(eid) and eid in (self.doc.selection or ())
            # Pressing on a selected wall's body: a drag moves it perpendicular to its axis (wall_edit.py).
            ev=self._scene_to_plane(event.position().toPoint())
            self._wall_press=(eid,ev.a,ev.b,event.position()) if selected and self.doc.get(eid).kind=='wall' and not ctrl else None
            # Pressing on a selected object's body: a drag moves it (with snapping), like a handle.
            from archforge.core.object_ops import USER_PLACED_KINDS
            self._body_press=(eid,event.position()) if selected and self.doc.get(eid).kind in USER_PLACED_KINDS and not self.doc.get(eid).locked and not ctrl else None
            self.redraw();return
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
        self._sync_snap_tolerance()
        pan=getattr(self,'_panning',None)
        if pan is not None:
            d=event.position()-pan;self._panning=event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-round(d.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-round(d.y()))
            event.accept();return
        lp=getattr(self,'_long_press',None)
        if lp is not None and (event.position()-lp[1]).manhattanLength()>self.CLICK_PX:self._long_press=None
        p=self.mapToScene(event.position().toPoint());self._cursor_xy=(p.x(),p.y());self.viewport().update()
        if self._overlay('move',event):return
        if self._slab_tool() and getattr(self,'_slab_draft',None) is not None:
            ev=self._scene_to_plane(event.position().toPoint());self._slab_draft.move(ev.a,ev.b)
            self.statusChanged.emit(self._slab_word()+': '+self._slab_draft.label());self.redraw();return
        if self._railing_tool() and getattr(self,'_railing_draft',None) is not None:
            ev=self._scene_to_plane(event.position().toPoint())
            self._railing_draft.move(ev.a,ev.b,bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier));self.redraw();return
        if self._mouse_down and getattr(self,'_view_drag',None):
            ev=self._scene_to_plane(event.position().toPoint());self.move_view_line(ev.a,ev.b);return
        body=getattr(self,'_body_press',None)
        if self._mouse_down and body and self.controller.active is None and (event.position()-body[1]).manhattanLength()>6:
            self._body_press=None;self.doc.select([body[0]]);self.controller.set_tool('move');self.controller.set_target(body[0],None);self._restore_select=True
            start=self._scene_to_plane(body[1].toPoint())
            try:self.controller.pointer_down(start)
            except (ValueError,RuntimeError) as exc:self.statusChanged.emit(str(exc));self.controller.set_tool('select');self._restore_select=False
        press=getattr(self,'_wall_press',None)
        if self._mouse_down and press and self.controller.active is None and (event.position()-press[3]).manhattanLength()>6:
            try:self.controller.begin_wall_move(press[0],press[1],press[2])
            except ValueError as exc:self.statusChanged.emit(str(exc))
            self._wall_press=None
        if (self._mouse_down or self._wall_chain_active()) and self.controller.active is not None:
            ev=self._scene_to_plane(event.position().toPoint())
            ev.shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)
            ev.ctrl=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier)
            try:
                self.controller.pointer_move(ev);self.redraw()
                problem=getattr(self.controller.active,'problem',None)
                if self.controller.preview.kind=='wall-move':
                    self.statusChanged.emit(f'⚠ {problem}' if problem else f'Μετακίνηση τοίχου {self.controller.active.distance*100:+.0f} cm — αφήνεις για να γίνει · Esc = ακύρωση')
                elif problem:self.statusChanged.emit(f'⚠ Δεν χωράει: {problem} — μετακίνησε ή άλλαξε πλάτος')
                elif self.controller.preview.kind=='rotate':
                    self.statusChanged.emit(f"Περιστροφή {float(self.controller.preview.hud.get('angle_deg',0.)):+.0f}° — έλξη 15° · Shift = ελεύθερα · Esc = ακύρωση")
                elif self.controller.preview.kind=='move':
                    hud=self.controller.preview.hud;self.statusChanged.emit(f"Μετακίνηση ΔX {float(hud.get('dx',0.))*100:+.0f} cm · ΔY {float(hud.get('dy',0.))*100:+.0f} cm — αφήνεις για να γίνει · Esc = ακύρωση")
            except ValueError as exc:self.statusChanged.emit(str(exc))
        else:
            p=self.mapToScene(event.position().toPoint());self.statusChanged.emit(f'X {p.x():.3f}   Y {p.y():.3f}')
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        self._sync_snap_tolerance()
        self._long_press=None
        if getattr(self,'_panning',None) is not None:
            self._pan_end();self.redraw();event.accept();return
        if self._overlay('release',event):event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and self._slab_tool() and getattr(self,'_slab_draft',None) is not None:
            self._mouse_down=False;ev=self._scene_to_plane(event.position().toPoint())
            done=self._slab_draft.up(ev.a,ev.b)
            if done:self.finish_slab_opening(done)
            else:
                self.statusChanged.emit(self._slab_word()+': κλικ στην επόμενη γωνία · διπλό κλικ / Enter / κλικ στην πρώτη = κλείσιμο · Esc = ακύρωση');self.redraw()
            event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and self._mouse_down and getattr(self,'_view_drag',None):
            self._mouse_down=False;ev=self._scene_to_plane(event.position().toPoint())
            self.end_view_line(ev.a,ev.b);event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and self._mouse_down:
            self._mouse_down=False;self._wall_press=None;self._body_press=None
            if self.controller.active is None and getattr(self,'_restore_select',False):
                self._restore_select=False;self.controller.set_tool('select')
            if self.controller.active is not None:
                pos=event.position()
                press=getattr(self,'_press_pos',None)
                if self.controller.tool=='wall' and press is not None and (pos-press).manhattanLength()<=self.CLICK_PX:
                    # A click is a click on screen, whatever the zoom: hand tremor of a few pixels
                    # must not draw a 5 cm wall (Windows mice move a little while clicking).
                    pos=press
                ev=self._scene_to_plane(pos.toPoint())
                ev.shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)
                ev.ctrl=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier)
                moved_wall=getattr(self.controller.active,'distance',None) if self.controller.preview.kind=='wall-move' else None
                stretched=self.controller.active.eid if type(self.controller.active).__name__=='ConnectedWallEndpointStretchTransaction' else None
                chain=self._wall_chain_active()
                try:
                    self.controller.pointer_up(ev)
                    if getattr(self.controller,'last_warning',None):self.statusChanged.emit(self.controller.last_warning)
                    elif chain and not self._wall_chain_active():
                        # The outline closed (or a click twice on a corner): the walls are done — Επιλογή.
                        self.to_select('Τοίχοι: το περίγραμμα έκλεισε · Επιλογή · Ctrl+Z = αναίρεση του τελευταίου τοίχου')
                    elif self._wall_chain_active():
                        self.statusChanged.emit('Τοίχος: κλικ στην επόμενη γωνία · κλικ στο πρώτο σημείο = κλείσιμο · διπλό κλικ / δεξί κλικ / Enter = τέλος · Esc = ακύρωση')
                except ValueError as exc:self.statusChanged.emit(str(exc));self.controller.cancel()
                self._active_handle=None
                if getattr(self,'_restore_select',False):
                    self._restore_select=False;self.controller.set_tool('select');self.selectionChangedByView.emit()
                self.redraw()
                if stretched and stretched in self.doc.entities and not getattr(self.controller,'last_warning',None):
                    q=self.doc.get(stretched).params
                    self.statusChanged.emit(f"Τοίχος: μήκος {math.hypot(q['x2']-q['x1'],q['y2']-q['y1']):.2f} m · Shift = ελεύθερη γωνία · Ctrl+Z = αναίρεση".replace('.',','))
                if moved_wall is not None:
                    self.selectionChangedByView.emit()
                    if self.controller.preview.kind!='wall-move' and abs(moved_wall)>1e-9:
                        self.statusChanged.emit(f'Ο τοίχος μετακινήθηκε {moved_wall*100:+.0f} cm — μαζί οι ενωμένοι τοίχοι, πόρτες/παράθυρα και ό,τι ακουμπά πάνω του · Ctrl+Z = αναίρεση')
                return
        super().mouseReleaseEvent(event)
    def focusNextPrevChild(self,next):
        # Tab cycles Stair/Ramp options instead of moving keyboard focus.
        if self.controller.tool in ('stair','ramp') and self.controller.active is not None:return False
        if str(self.controller.tool).startswith('layout_'):return False     # Tab = next layout variant
        return super().focusNextPrevChild(next)
    def finish_plot(self):
        draft=getattr(self,'plot_draft',None) or []
        if len(draft)<3:
            self.statusChanged.emit('Το περίγραμμα χρειάζεται τουλάχιστον 3 κορυφές');return
        self._long_press=None
        self.sitePointRequested.emit('plot_point',float(draft[0][0]),float(draft[0][1]))

    def _tool_idle(self):
        """No drawing in progress (segment, drag, railing/slab outline, site line)."""
        slab=getattr(self,'_slab_draft',None)
        return (self.controller.active is None and not self._wall_chain_active() and getattr(self,'_view_drag',None) is None
                and getattr(self,'_railing_draft',None) is None and not getattr(self,'plot_draft',None)
                and (slab is None or (not slab.points and slab.press is None)))
    def event(self,event):
        # Drawing with any tool: Delete is the plan's own (what is under the mouse first), not the window's «delete selection».
        if event.type()==QEvent.Type.ShortcutOverride and event.key()==Qt.Key.Key_Delete and str(self.controller.tool)!='select':
            event.accept();return True
        return super().event(event)
    def keyPressEvent(self,event):
        if self.carry is not None and event.key() in (Qt.Key.Key_Escape,Qt.Key.Key_R):
            if event.key()==Qt.Key.Key_R:self.carry.turn_by(90.0);self.statusChanged.emit(self.carry.label())
            else:self.carry=None;self.statusChanged.emit('Σύρσιμο ακυρώθηκε')
            self.redraw();event.accept();return
        if self._overlay('key',event):event.accept();return
        if event.key()==Qt.Key.Key_Delete and str(self.controller.tool)!='select' and getattr(self,'marking_menu_window',None) is not None:
            # Owner 23/10 «το Delete να δουλεύει παντού»: while drawing, Delete removes what the mouse points at;
            # nothing there → the last wall drawn (owner 15/10) in the wall tool, else the selection.
            window=self.marking_menu_window
            hovered=self._hovered_entity()
            if self._wall_chain_active():self.controller.finish_wall_chain()   # the rubber segment hung on that wall
            if hovered:
                self.doc.select([hovered]);window._delete_selection()
            elif str(self.controller.tool)=='wall':
                from archforge.ui.marking_menu import run as _mm_run
                _mm_run(window,'plan',None,'mm:wall:delete_last')
            else:
                window._delete_selection()
            self.redraw();event.accept();return
        if event.key() in (Qt.Key.Key_F,Qt.Key.Key_Space) and self.controller.tool=='wall' and not event.modifiers():
            # F or Space (as Revit's space bar): the wall's body to the other side of the drawn line (wall_face.py).
            from archforge.architecture.wall_face import LABELS
            mode=self.controller.flip_wall_face()
            if self.controller.active is not None and self._cursor_xy is not None:self.viewport().update()
            self.statusChanged.emit(f'Τοίχος από: {LABELS[mode]} · F / Διάστημα = άλλη πλευρά');self.redraw();event.accept();return
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self.controller.tool=='room_box':
            from archforge.ui.room_box_tool import ask_size
            ask_size(self);event.accept();return
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self.controller.tool=='plot_point':
            self.finish_plot();event.accept();return
        if event.key()==Qt.Key.Key_Escape and getattr(self,'_restore_select',False):
            self.controller.cancel();self._restore_select=False;self.controller.set_tool('select');self._mouse_down=False;self.redraw();return
        if event.key()==Qt.Key.Key_Escape and self._tool_idle() and self.controller.tool!='select':
            # Nothing in progress: Esc ends the tool (CAD convention: 1st Esc cancels, 2nd finishes).
            window=getattr(self,'marking_menu_window',None)
            (window._set_active_tool if window is not None else self.controller.set_tool)('select')
            self.statusChanged.emit('Επιλογή');self.redraw();event.accept();return
        if event.key()==Qt.Key.Key_Escape:self.controller.cancel();self._mouse_down=False;self._view_drag=None;self._wall_press=None;self._railing_draft=None;self._slab_draft=None;self.redraw();return
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self._wall_chain_active():self.finish_wall_chain();event.accept();return
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self._slab_tool():self.finish_slab_opening();event.accept();return
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self._railing_tool():self.finish_railing();event.accept();return
        if event.key() in (Qt.Key.Key_Tab,Qt.Key.Key_Space) and self.controller.cycle_option(1):
            self.redraw();event.accept();return
        super().keyPressEvent(event)
    # ---- Library drag (library_drag.py): ghost under the cursor, one command on drop.
    carry=None
    def _plan_xy_at(self,pos):return self.controller._plan_xy(self._scene_to_plane(pos))
    def carry_move(self,carry,pos):
        self.carry=carry;x,y=self._plan_xy_at(pos);carry.move(x,y,free=carry.free);self.redraw();self.statusChanged.emit(carry.label())
    def carry_leave(self):
        if self.carry is not None:self.carry=None;self.redraw()
    def carry_drop(self,carry,pos):
        x,y=self._plan_xy_at(pos);target=None
        if carry.kind=='material':
            eid=self._entity_items.get(self.itemAt(pos))
            if not eid or eid not in self.doc.entities or self.doc.get(eid).kind in self.CONTAINER_KINDS:
                from archforge.ui.library_drag import wall_at
                eid=wall_at(self.doc,x,y) or eid       # walls are drawn as outlines: pick inside the thickness too
            target=(eid,None) if eid and eid in self.doc.entities else None
        self.carry=None;done=carry.drop(x,y,target);self.redraw();self.selectionChangedByView.emit();return done
    def _drag_carry(self,event):
        from archforge.ui.library_drag import LibraryCarry,action_from_mime,droppable
        action=action_from_mime(event.mimeData());window=getattr(self,'marking_menu_window',None)
        if not droppable(action) or window is None:return None
        if self.carry is None or self.carry.action!=tuple(action):self.carry=LibraryCarry(window,action)
        self.carry.free=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier);return self.carry
    def dragEnterEvent(self,event):
        carry=self._drag_carry(event)
        if carry is None:super().dragEnterEvent(event);return
        self.carry_move(carry,event.position().toPoint());event.acceptProposedAction()
    def dragMoveEvent(self,event):
        carry=self._drag_carry(event)
        if carry is None:super().dragMoveEvent(event);return
        self.carry_move(carry,event.position().toPoint());event.acceptProposedAction()
    def dragLeaveEvent(self,event):self.carry_leave();event.accept()
    def dropEvent(self,event):
        carry=self._drag_carry(event)
        if carry is None:super().dropEvent(event);return
        self.carry_drop(carry,event.position().toPoint());event.acceptProposedAction()
    def run_object_op(self,eid,op):
        """Mouse-menu / handle actions on a placed object (object_ops): one command each."""
        window=getattr(self,'marking_menu_window',None)
        if window is not None:
            from archforge.ui.object_menu import run_object_op
            return run_object_op(window,eid,op)
        from archforge.core import object_ops
        command=object_ops.flip_command(self.doc,eid,op) if op in ('hinge','swing') else None
        if command is not None:self.stack.execute(command);self.redraw()
        return command
    def set_snap_enabled(self, enabled):
        self.controller.set_snap_enabled(enabled)
        self.statusChanged.emit('Έλξη ενεργή' if enabled else 'Έλξη ανενεργή — ελεύθερη σχεδίαση')
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
        xy=(float(plan_point.a),float(plan_point.b)) if plan_point is not None else None
        menu=build_menu(window,'plan',entity_id,xy)
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

    def _label_scale(self):
        """Current px per metre, corrected for a font larger than the one plan_scene's label boxes assume."""
        if not hasattr(PlanView,'_label_font_factor'):
            from PySide6.QtGui import QFontMetricsF
            from archforge.core.plan_scene import LABEL_CHAR_PX,LABEL_LINE_PX
            fm=QFontMetricsF(QGraphicsTextItem().font())
            PlanView._label_font_factor=max(1.0,fm.horizontalAdvance('ΣΔ1 25/50 4Ø14')/14/LABEL_CHAR_PX,fm.lineSpacing()/LABEL_LINE_PX)
        return abs(self.transform().m11())/PlanView._label_font_factor
    def _update_label_visibility(self):
        scale=self._label_scale()
        for item,min_scale in getattr(self,'_scaled_labels',()):item.setVisible(scale>=min_scale)
    def redraw(self):
        self._scaled_labels=[]
        self._scene.clear();self._handle_items.clear();self._entity_items.clear();self._draw_grid();self._draw_underlays();frame=build_plan_frame(self.doc,self.controller.preview,layers=not self.structural_only);self._frame=frame
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
                    if entity.kind in context_kinds and p.role!='stair':
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
        slab=getattr(self,'_slab_draft',None)
        if slab is not None and len(slab.preview())>=2:
            # Opening being drawn: dashed ghost with its size and area.
            pen=QPen(QColor(200,60,40));pen.setWidthF(.035);pen.setStyle(Qt.PenStyle.DashLine);pts=slab.preview()
            path=QPainterPath(QPointF(*pts[0]))
            for q in pts[1:]:path.lineTo(QPointF(*q))
            if len(pts)>=3:path.closeSubpath()
            self._scene.addPath(path,pen,QBrush(QColor(200,60,40,30))).setZValue(30)
            label=self._scene.addText(slab.label());label.setDefaultTextColor(QColor(170,40,30))
            label.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
            label.setPos(max(q[0] for q in pts),max(q[1] for q in pts));label.setZValue(31)
        drag=getattr(self,'_view_drag',None)
        if drag:
            # Section/camera line: dashed from the eye point along the view.
            pen=QPen(QColor(200,60,40));pen.setWidthF(.05);pen.setStyle(Qt.PenStyle.DashLine)
            (ax,ay),(bx,by)=drag
            if self.controller.tool=='view_section' and math.hypot(bx-ax,by-ay)>=.05:
                # Section ghost: the cut line, arrows to where it will look, its letter and length.
                from archforge.output.section_cut import next_section_name,plan_symbol,section_letter
                pen.setStyle(Qt.PenStyle.DashDotLine);self._scene.addLine(ax,ay,bx,by,pen).setZValue(30)
                sym=plan_symbol({'x1':ax,'y1':ay,'x2':bx,'y2':by},section_letter(next_section_name(self.doc)))
                solid=QPen(QColor(200,60,40));solid.setWidthF(.04)
                from PySide6.QtGui import QPolygonF
                for tail,head,(w1,w2) in sym['arrows']:
                    self._scene.addLine(tail[0],tail[1],head[0],head[1],solid).setZValue(30)
                    self._scene.addPolygon(QPolygonF([QPointF(*head),QPointF(*w1),QPointF(*w2)]),solid,QBrush(QColor(200,60,40))).setZValue(30)
                for text,(tx,ty) in sym['labels']+[(f'{math.hypot(bx-ax,by-ay):.2f} m'.replace('.',','),((ax+bx)/2,(ay+by)/2))]:
                    t=self._scene.addText(text);t.setDefaultTextColor(QColor(200,40,40));f=t.font();f.setBold(True);t.setFont(f)
                    t.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True);t.setPos(tx,ty);t.setZValue(31)
            else:
                self._scene.addLine(ax,ay,bx,by,pen).setZValue(30)
                dot=QPen(QColor(200,60,40));dot.setWidthF(.05);self._scene.addEllipse(ax-.12,ay-.12,.24,.24,dot,QBrush(QColor(200,60,40))).setZValue(30)
        overlay=getattr(self,'overlay_tool',None)
        if overlay is not None:overlay.paint(self)
        if getattr(self,'terrain_tool',None) is not None:self.terrain_tool.paint(self)
        if getattr(self,'pool_tool',None) is not None:self.pool_tool.paint(self)
        if getattr(self,'camera_tool',None) is not None:self.camera_tool.paint(self)
        if getattr(self,'tape_tool',None) is not None:self.tape_tool.paint(self)   # Μεζούρα (dimension_tool.py)
        if getattr(self,'dims_tool',None) is not None:self.dims_tool.paint(self)   # dimensions of a selected wall (wall_dims_tool.py)
        if getattr(self,'survey_tool',None) is not None:self.survey_tool.paint(self)   # corner numbers (survey_dialog.py)
        if self.carry is not None:self.carry.paint(self)
        if self.controller.preview.kind=='rotate' and self.controller.active is not None:self._draw_rotate_dial(self.controller.preview)
        draft=getattr(self,'plot_draft',None)
        if draft:
            # Plot outline being drawn: corners so far, the first one ringed (click it to close).
            pen=QPen(QColor(170,40,40));pen.setWidthF(.04);pen.setStyle(Qt.PenStyle.DashDotLine)
            for (ax,ay),(bx,by) in zip(draft,draft[1:]):self._scene.addLine(ax,ay,bx,by,pen).setZValue(35)
            for i,(ax,ay) in enumerate(draft):
                r=.3 if i==0 else .1
                self._scene.addEllipse(ax-r,ay-r,2*r,2*r,pen,QBrush(QColor(170,40,40,60 if i==0 else 160))).setZValue(35)
        marker=getattr(self,'assistant_marker',None)
        if marker is not None:
            # Assistant marker: where the human pointed (UI state, not part of the Document).
            mx,my=marker;red=QColor(220,30,40);pen=QPen(red);pen.setWidthF(.04)
            self._scene.addEllipse(mx-.18,my-.18,.36,.36,pen,QBrush(QColor(220,30,40,60))).setZValue(40)
            self._scene.addLine(mx-.32,my,mx+.32,my,pen).setZValue(40);self._scene.addLine(mx,my-.32,mx,my+.32,pen).setZValue(40)
        # A fixed, very large sheet (±5 km): a scene rect that followed the visible area clamped the
        # scroll bars, so the wheel zoom could not keep the point under the mouse (drawing slid left).
        self._scene.setSceneRect(-5000,-5000,10000,10000)
        self.previewChanged.emit(copy.deepcopy(self.controller.preview))
    def _draw_grid(self):
        if not getattr(self,'_show_grid',True):return
        extent=100;pen=QPen(QColor(225,225,225));pen.setWidthF(0);axis=QPen(QColor(160,160,160));axis.setWidthF(0)
        for i in range(-extent,extent+1):self._scene.addLine(i,-extent,i,extent,axis if i==0 else pen).setZValue(-100);self._scene.addLine(-extent,i,extent,i,axis if i==0 else pen).setZValue(-100)
    def _draw_underlays(self):
        """The engineer's drawing (PDF page / DXF lines) under the active storey: faint, never selectable."""
        from archforge.project.underlay import underlays
        if self.structural_only:return
        for e in underlays(self.doc,z=float(self.doc.work_plane.origin[2])):
            if e.visible:add_underlay_item(self._scene,e.params)
    def _has_symbol(self,entity_id):
        frame=getattr(self,'_frame',None)
        prims=frame.primitives if frame is not None else ()
        return any(q.role=='library-symbol' and q.entity_id==entity_id for q in prims)
    def _draw_primitive(self,p:Primitive2D):
        if p.role.startswith('camera'):
            from archforge.ui.camera_tool import draw_plan_primitive
            draw_plan_primitive(self,p);return
        if p.role in ('section-line','section-arrow'):
            # Section mark: red dash-dot cut line, filled arrows towards where the section looks.
            sel=p.entity_id in (self.doc.selection or ());pen=QPen(QColor(200,40,40));pen.setWidthF(.06 if sel else .035)
            if p.kind=='polygon':
                from PySide6.QtGui import QPolygonF
                item=self._scene.addPolygon(QPolygonF([QPointF(x,y) for x,y in p.points]),pen,QBrush(QColor(200,40,40)))
            else:
                if p.role=='section-line':pen.setStyle(Qt.PenStyle.DashDotLine)
                (ax,ay),(bx,by)=p.points[0],p.points[-1];item=self._scene.addLine(ax,ay,bx,by,pen)
            item.setZValue(25)
            if p.entity_id:self._entity_items[item]=p.entity_id
            return
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
        if preview and str(dict(p.meta).get('semantic','')).startswith('stair-preview-'):
            # Steps of the stair being placed: thin, so the treads read (red when it does not fit).
            pen=QPen(QColor(210,40,40) if dict(p.meta).get('fits') is False else QColor(40,150,70));pen.setWidthF(.015)
            if str(dict(p.meta)['semantic']).endswith(('hidden','walk-hidden')):pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='library-symbol':pen=QPen(QColor(40,45,55));pen.setWidthF(.012)
        if p.role in ('cabinet','cabinet-front'):pen=QPen(QColor(40,45,55));pen.setWidthF(.012)
        if p.role in ('railing','railing-post'):pen=QPen(QColor(40,45,55));pen.setWidthF(.01)
        if p.role in ('pipe-cold','pipe-hot'):
            pen=QPen(QColor(31,111,209) if p.role=='pipe-cold' else QColor(209,48,31))
            pen.setWidthF(.035 if dict(p.meta).get('diameter',16)>=20 else .02)
        if p.role=='dimension':
            # Dimensions (architecture/dimensions.py): blue, the ticks and extension lines thinner.
            sel=p.entity_id in (self.doc.selection or ());pen=QPen(QColor(20,110,220) if sel else QColor(30,90,170))
            pen.setWidthF((.008 if dict(p.meta).get('thin') else .012)*(2 if sel else 1))
        if p.role in ('roof-outline','roof-ridge'):
            pen=QPen(QColor(150,70,40));pen.setWidthF(.02 if p.role=='roof-outline' else .015)
            pen.setStyle(Qt.PenStyle.DashLine if p.role=='roof-outline' else Qt.PenStyle.DashDotLine)
        if p.role=='cable':
            from archforge.mep.electrical import CABLE_COLORS
            pen=QPen(QColor(CABLE_COLORS.get(dict(p.meta).get('group'),'#e07a00')));pen.setWidthF(.015)
            pen.setStyle({'wall':Qt.PenStyle.SolidLine,'floor':Qt.PenStyle.DotLine}.get(dict(p.meta).get('run'),Qt.PenStyle.DashLine))
        if p.role in ('lv-cable','lv-box'):
            from archforge.mep.electrical import CABLE_COLORS
            pen=QPen(QColor(CABLE_COLORS.get(dict(p.meta).get('system'),'#0e9aa7')));pen.setWidthF(.012 if p.role=='lv-cable' else .008)
            if p.role=='lv-cable':pen.setStyle(Qt.PenStyle.DashDotLine)
        if p.role=='led-strip':
            pen=QPen(QColor(232,170,20));pen.setWidthF(.03);pen.setStyle(Qt.PenStyle.DashLine);pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        if p.role=='manifold':
            pen=QPen(QColor(31,111,209) if dict(p.meta).get('system')=='cold' else QColor(209,48,31));pen.setWidthF(.012)
        if p.role=='elec-box':
            pen=QPen(QColor({'pull':'#c0262d','floor':'#0a8a5a'}.get(dict(p.meta).get('box'),'#3a3f48')));pen.setWidthF(.012)
        if p.role=='electrical-point':pen=QPen(QColor(200,120,0));pen.setWidthF(.02)
        if p.role=='plumbing-point':pen=QPen(QColor(31,90,160));pen.setWidthF(.02)
        if p.role in ('heat-supply','heat-return'):
            # Heating: supply red, return blue dashed, drawn at the owner's Ø.
            pen=QPen(QColor(200,40,30) if p.role=='heat-supply' else QColor(30,80,200))
            pen.setWidthF(max(.012,float(dict(p.meta).get('diameter',16))/1500.))
            if p.role=='heat-return':pen.setStyle(Qt.PenStyle.DashLine)
        if p.role in ('pool','pool-rim'):pen=QPen(QColor(20,120,170));pen.setWidthF(.03 if p.role=='pool-rim' else .015)
        if p.role=='pool-zone':
            # Electrical safety zones around the basin (HD 60364-7-702): dash-dot, zone 2 fainter.
            pen=QPen(QColor(200,60,140) if dict(p.meta).get('zone')==1 else QColor(200,60,140,110));pen.setWidthF(.015)
            pen.setStyle(Qt.PenStyle.DashDotLine)
        if p.role=='pool-pipe':pen=QPen(QColor(70,70,70));pen.setWidthF(max(.015,float(dict(p.meta).get('diameter',50))/2500.))
        if p.role=='pool-plant':pen=QPen(QColor(90,90,90));pen.setWidthF(.02);pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='heat-loop':pen=QPen(QColor(225,110,40,200));pen.setWidthF(.012)
        if p.role in ('heat-manifold','heat-fitting','heating-point'):pen=QPen(QColor(170,40,40));pen.setWidthF(.012)
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
        if p.role=='align-guide':
            # Where to stop for right angles: a thin dashed line to the corner it lines up with.
            pen=QPen(QColor(20,110,220));pen.setCosmetic(True);pen.setWidthF(1.2);pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='angle-arc':
            # Corner mark: blue on a magnet (90/45/15), grey for a free angle.
            pen=QPen(QColor(20,110,220) if dict(p.meta).get('magnet') else QColor(120,120,120));pen.setWidthF(.02)
        if p.role=='plot-boundary':
            # The plot's legal outline: dash-dot, like on the survey.
            pen=QPen(QColor(170,40,40));pen.setWidthF(.04);pen.setStyle(Qt.PenStyle.DashDotLine)
        if p.role=='contour':
            # Contour lines: thin brown, every 1 m (or the chosen step) a little stronger.
            z=float(dict(p.meta).get('z',0.));major=abs(z-round(z))<1e-6
            pen=QPen(QColor(150,110,60,200 if major else 120));pen.setWidthF(.02 if major else .01)
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
        if p.role in ('worktop','worktop-cutout','sink-symbol','hob-symbol','hood'):
            # Derived parts of a cabinet run: worktop edge, cut-outs, sink bowl, hob zones; the hood is above (dashed).
            pen=QPen(QColor(40,45,55) if p.role=='worktop' else QColor(70,80,95));pen.setWidthF(.016 if p.role=='worktop' else .009)
            if p.role=='hood':pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='cabinet-wall':
            pen=QPen(QColor(70,80,95));pen.setWidthF(.01);pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='library-object' and self._has_symbol(p.entity_id):
            # Footprint stays for picking; the symbol carries the drawing.
            pen=QPen(QColor(150,160,170,90));pen.setWidthF(.006)
        if p.role in ('drywall-ceiling','drywall-ceiling-step'):
            # Suspended ceiling: above the cut plane, dashed.
            pen=QPen(QColor(70,110,150));pen.setWidthF(.016 if p.role=='drywall-ceiling' else .01);pen.setStyle(Qt.PenStyle.DashLine)
        if p.role=='stair':pen=QPen(QColor(0,0,0,0));pen.setWidthF(.01)     # pick area only: the symbol is drawn below
        if p.role.startswith('stair-'):
            pen=QPen(QColor(45,55,65));pen.setWidthF({'stair-opening':.03,'stair-cut':.016,'stair-walk':.012,'stair-walk-hidden':.012}.get(p.role,.014))
            if p.role in ('stair-hidden','stair-walk-hidden'):pen.setStyle(Qt.PenStyle.DashLine)
        if p.role in ('slab-opening','slab-opening-cross'):
            # Void in the slab: thin cross; dashed when the void is in the slab above (roof only).
            pen=QPen(QColor(60,65,75));pen.setWidthF(.018 if p.role=='slab-opening' else .012)
            if dict(p.meta).get('above'):pen.setStyle(Qt.PenStyle.DashLine)
        wall_line=p.kind=='line' and p.role=='model' and bool(p.entity_id) and p.entity_id in self.doc.entities and self.doc.get(p.entity_id).kind=='wall'
        if wall_line:
            # The wall itself is drawn by the cut region (wall-poche); its axis line only picks, as wide as the wall.
            sel=p.entity_id in (self.doc.selection or ())
            shown=p.entity_id==getattr(self,'_indicated',None)       # one click: indicated, not selected
            pen=QPen(QColor(20,110,220,110) if sel else (QColor(240,140,30,90) if shown else QColor(0,0,0,0)));pen.setWidthF(float(dict(p.meta).get('thickness',.2)))
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        if p.role=='wall-poche':pen=QPen(QColor(40,45,55));pen.setWidthF(.02);pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        if p.kind=='polygon' and dict(p.meta).get('islands'):
            # Slab with openings / several parts: one path, holes left empty.
            path=QPainterPath();path.setFillRule(Qt.FillRule.OddEvenFill)
            for outer,holes in dict(p.meta)['islands']:
                for loop in (outer,)+tuple(holes):
                    path.moveTo(QPointF(*loop[0]))
                    for q in loop[1:]:path.lineTo(QPointF(*q))
                    path.closeSubpath()
            item=self._scene.addPath(path,pen,QBrush(QColor(205,200,190) if p.role=='wall-poche' else QColor(80,160,220,40)))
        elif p.kind=='line':a,b=p.points;item=self._scene.addLine(a[0],a[1],b[0],b[1],pen)
        elif p.kind=='polyline':
            if len(p.points)>=2:
                path=QPainterPath(QPointF(p.points[0][0],p.points[0][1]))
                for x,y in p.points[1:]:
                    path.lineTo(float(x),float(y))
                item=_OpenPathItem(path);item.setPen(pen);self._scene.addItem(item)
        elif p.kind=='polygon':
            from PySide6.QtGui import QPolygonF
            brush=QBrush(
                QColor(160,160,160,18)
                if context else
                (QColor(90,180,120,28) if room else (QColor(150,140,125,70) if p.role=='site-path' else (QColor(255,255,255,1) if p.role=='library-object' else (QColor(236,230,220,120) if p.role=='cabinet' else (QColor(0,0,0,0) if p.role in ('cabinet-wall','joists-area') else (QColor(70,110,150,14) if p.role=='drywall-ceiling' else (QColor(255,255,255,90) if p.role=='slab-opening' else (QColor(255,255,255,1) if p.role=='stair' else QColor(80,160,220,40)))))))))
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
            if p.role=='section-label':
                f=item.font();f.setBold(True);f.setPointSizeF(f.pointSizeF()*1.4);item.setFont(f);item.setDefaultTextColor(QColor(200,40,40))
            if p.role=='wall-move-label':
                # Distance of a dragged wall: blue and bold, like the angle mark.
                f=item.font();f.setBold(True);f.setPointSizeF(f.pointSizeF()*1.25);item.setFont(f)
                item.setDefaultTextColor(QColor(210,40,40) if text.startswith('⚠') else QColor(20,110,220))
            item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True);item.setPos(cx,cy);item.setTransformOriginPoint(item.boundingRect().center());item.setScale(1.0);item.setZValue(8);
            if p.role=='dimension-label':
                # Along its dimension line, just above it (screen y is the plan's −y, so the angle turns over).
                from PySide6.QtGui import QTransform
                f=item.font();f.setPointSizeF(f.pointSizeF()*.9);item.setFont(f);item.setDefaultTextColor(QColor(30,90,170))
                r=item.boundingRect();item.setTransform(QTransform().rotate(-float(meta.get('angle',0.))).translate(-r.width()/2,-r.height()+4))
                if p.entity_id:self._entity_items[item]=p.entity_id
                meta.pop('align',None)
            if meta.get('align'):
                # Placed label (plan_scene.place_labels): this point of the text box sits on the anchor.
                from PySide6.QtGui import QTransform
                hx,vy=meta['align'];r=item.boundingRect();item.setTransform(QTransform.fromTranslate(-hx*r.width(),-vy*r.height()))
            if meta.get('min_scale'):
                # Hidden while zoomed out past the scale where it would overlap another label.
                self._scaled_labels.append((item,float(meta['min_scale'])));item.setVisible(self._label_scale()>=float(meta['min_scale']))
            if dict(p.meta).get('layer_dim'):item.setOpacity(.3)
            return
        if item is not None:
            container=bool(p.entity_id) and p.entity_id in self.doc.entities and self.doc.get(p.entity_id).kind in self.CONTAINER_KINDS
            item.setZValue(-30 if p.role=='contour' else -20 if context else (-10 if room else (10 if opening else (20 if preview else (-5 if container else (-1 if p.role=='wall-poche' else (1 if wall_line else 0)))))))
            if p.entity_id and not preview:self._entity_items[item]=p.entity_id
            if p.entity_id and p.entity_id==getattr(self,'_indicated',None) and not wall_line and hasattr(item,'setPen'):
                ind=QPen(QColor(240,140,30));ind.setWidthF(.03);ind.setCosmetic(False);item.setPen(ind)
            if preview and p.kind=='polygon' and dict(p.meta).get('fits') is False:item.setBrush(QBrush(QColor(210,40,40,45)))
            if preview and p.kind=='polygon' and dict(p.meta).get('semantic')=='wall-body-preview':
                # The wall being drawn looks like a wall: its cut fill, a green edge (not yet placed).
                item.setBrush(QBrush(QColor(205,200,190,235)));edge=QPen(QColor(40,150,70));edge.setWidthF(.025)
                edge.setJoinStyle(Qt.PenJoinStyle.MiterJoin);item.setPen(edge)
            # Dim layer (Layers panel / environment): a faint reference under the work.
            if dict(p.meta).get('layer_dim'):item.setOpacity(.28);item.setZValue(-30)
    def _draw_rotate_dial(self,preview):
        # Live rotation: dial round the pivot, a ray at the new angle and the angle in degrees.
        hud=preview.hud;px,py=float(hud.get('pivot_x',0.)),float(hud.get('pivot_y',0.));a=float(hud.get('angle_deg',0.))
        pen=QPen(QColor(230,120,20));pen.setWidthF(.025);pen.setStyle(Qt.PenStyle.DashLine);r=.6
        self._scene.addEllipse(px-r,py-r,2*r,2*r,pen).setZValue(55)
        for k in range(24):
            t=math.radians(k*15);q=.08 if k%6==0 else .04
            tick=QPen(QColor(230,120,20));tick.setWidthF(.015 if k%6 else .03)
            self._scene.addLine(px+math.cos(t)*(r-q),py+math.sin(t)*(r-q),px+math.cos(t)*r,py+math.sin(t)*r,tick).setZValue(55)
        ray=QPen(QColor(230,120,20));ray.setWidthF(.03)
        t=math.radians(float(getattr(self.controller,'_rotate_start_angle',-90.))+a);self._scene.addLine(px,py,px+math.cos(t)*r,py+math.sin(t)*r,ray).setZValue(56)
        label=self._scene.addText(f'{a:+.0f}°');label.setDefaultTextColor(QColor(200,90,10))
        f=label.font();f.setBold(True);f.setPointSizeF(f.pointSizeF()*1.3);label.setFont(f)
        label.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True);label.setPos(px+r*.75,py+r*.95);label.setZValue(57)
    def _draw_handle(self,h):
        if h.handle=='rotate':
            # Rotation handle: orange ring with an arrow mark (drag = turn).
            r=.13;pen=QPen(QColor(230,120,20));pen.setWidthF(.03)
            it=self._scene.addEllipse(h.x-r,h.y-r,2*r,2*r,pen,QBrush(QColor(255,240,220)));it.setZValue(52);self._handle_items[it]=h
            arc=QPainterPath();arc.arcMoveTo(h.x-r*.6,h.y-r*.6,r*1.2,r*1.2,30);arc.arcTo(h.x-r*.6,h.y-r*.6,r*1.2,r*1.2,30,270)
            deco=self._scene.addPath(arc,pen);deco.setZValue(53);self._handle_items[deco]=h   # the arrow is part of the handle
            from PySide6.QtGui import QPolygonF
            end=arc.currentPosition();head=QPolygonF([QPointF(end.x()-.045,end.y()+.01),QPointF(end.x()+.045,end.y()+.01),QPointF(end.x(),end.y()-.05)])
            tip=self._scene.addPolygon(head,pen,QBrush(QColor(230,120,20)));tip.setZValue(53);self._handle_items[tip]=h;return
        if h.handle=='flip_swing':
            # Swing flip: small blue diamond on the arc side (click = other way).
            from PySide6.QtGui import QPolygonF
            r=.09;pen=QPen(QColor(20,90,180));pen.setWidthF(.02)
            it=self._scene.addPolygon(QPolygonF([QPointF(h.x,h.y-r),QPointF(h.x+r,h.y),QPointF(h.x,h.y+r),QPointF(h.x-r,h.y)]),pen,QBrush(QColor(210,230,255)))
            it.setZValue(52);self._handle_items[it]=h;return
        r=.09;it=self._scene.addEllipse(h.x-r,h.y-r,2*r,2*r,QPen(QColor(20,90,180),0),QBrush(QColor(255,255,255)));it.setZValue(50);self._handle_items[it]=h
    def _draw_snap(self,s):
        r=.08
        angle_lock=str(s.get('kind','')).startswith('angle')
        color=QColor(50,110,220) if angle_lock else QColor(220,80,40)
        self._scene.addEllipse(
            s['x']-r,s['y']-r,2*r,2*r,QPen(color,0)
        ).setZValue(70)
    def _draw_hud(self,hud):
        # The live measures are painted over the view in Greek (plan_overlay.hud_text), not as raw keys.
        self.viewport().update()
