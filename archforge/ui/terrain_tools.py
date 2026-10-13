"""Mouse-first terrain shapes. Preview lives here; edits use UpdateEntity.

Rectangle/circle: press, drag, release. Polygon: click vertices and close.
Edit: select an outline, drag a corner/body, edit elevation/transition in
Properties; right-click offers edit/delete. Legacy elevation points remain.
"""
from __future__ import annotations
import copy
import math
import uuid

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QColor, QPen, QBrush, QPolygonF
from PySide6.QtWidgets import QInputDialog, QMenu, QLabel, QDoubleSpinBox, QPushButton, QGraphicsTextItem

from archforge.core.commands import AddEntity, UpdateEntity
from archforge.core.model import Entity
from archforge.site.terrain import default_terrain_params, terrain_height
from archforge.site.elevation_regions import SHAPES, shape_points, distance_to_region
from archforge.geometry.regions import signed_area

BLUE=QColor(30,110,200)
BROWN=QColor(125,75,25)


def mark(z):
    return ('±0,00' if abs(z)<.0005 else f'{z:+.2f}'.replace('.',','))+' m'


class TerrainTools:
    def __init__(self, window):
        self.window=window
        self.mode=None
        self.selected=None        # ('region', stable id) or ('point', index): selection only
        self.draft=None
        self.anchor=None
        self.cursor=None
        self.drag=None

    def cancel(self):
        self.draft=self.anchor=self.cursor=self.drag=None
        self.mode=None; self.selected=None
        if str(self.window.plan_view.controller.tool).startswith('terrain_region_'):
            self.window.plan_view.controller.set_tool('select')

    def start(self, shape):
        self.cancel(); self.mode=shape
        tool='select' if shape=='edit' else 'terrain_region_'+shape
        self.window._start_site_tool(tool, 'Υψομετρική περιοχή: '+
            ('κλικ στο περίγραμμα ή σε σημείο · σύρε σώμα/κορυφή · δεξί κλικ για επεξεργασία · Esc τέλος' if shape=='edit'
             else ('κλικ στις κορυφές · κλικ στην πρώτη / διπλό κλικ / Enter κλείσιμο · Esc ακύρωση' if shape=='polygon'
                   else 'σύρε το σχήμα και δώσε υψόμετρο · Esc ακύρωση')))
        self.window.plan_view.redraw()

    def _active(self, view):
        return self.mode is not None and (str(view.controller.tool).startswith('terrain_region_') or view.controller.tool=='select')

    def _xy(self, view, event):
        pos=event.pos() if hasattr(event,'globalPos') and not hasattr(event,'position') else event.position().toPoint()
        p=view._scene_to_plane(pos); x,y=float(p.a),float(p.b)
        if view.controller.snap_enabled and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            grid=float(view.controller.grid)
            if grid>0: x,y=round(x/grid)*grid,round(y/grid)*grid
        return x,y

    def _current(self):
        e=self.window._terrain_entity()
        if not e or not self.selected: return None,None
        kind,key=self.selected
        if kind=='region': return e,next((r for r in e.params.get('regions',()) if r['id']==key),None)
        points=e.params.get('points') or ()
        return e,points[key] if isinstance(key,int) and 0<=key<len(points) else None

    def _change(self, changes):
        e=self.window._terrain_entity()
        if e is None: return False
        # A moved control must remain inside the site, in the same undo step.
        if 'regions' in changes or 'points' in changes:
            points=[p for r in changes.get('regions',e.params.get('regions') or ()) for p in r['points']]
            points+=list(changes.get('points',e.params.get('points') or ()))
            if points:
                changes=dict(changes,x0=min(e.params['x0'],min(p[0] for p in points)),
                             y0=min(e.params['y0'],min(p[1] for p in points)),
                             x1=max(e.params['x1'],max(p[0] for p in points)),
                             y1=max(e.params['y1'],max(p[1] for p in points)))
        if all(e.params.get(key)==value for key,value in changes.items()): return True
        try:
            self.window.stack.execute(UpdateEntity(e.id,changes))
        except (ValueError,RuntimeError,PermissionError) as exc:
            self.window.statusBar().showMessage(str(exc),7000); return False
        self.window._redraw_views(all_views=True); self.window.refresh_inspector()
        return True

    def place_shape(self, points, shape):
        if len(points)<3 or abs(signed_area(points))<.04:
            self.window.statusBar().showMessage('Το σχήμα χρειάζεται επιφάνεια τουλάχιστον 0,04 m²',5000); return False
        e=self.window._terrain_entity(); p=e.params if e else default_terrain_params(self.window.doc)
        x,y=points[0]
        z,ok=QInputDialog.getDouble(self.window,'Υψομετρική περιοχή','Υψόμετρο περιοχής ως προς ±0,00 ισογείου (m):',
                                   terrain_height(p,x,y),-1000.,1000.,3)
        if not ok: return False
        r=dict(id=uuid.uuid4().hex,shape=shape,points=[list(q) for q in points],elevation=float(z),transition=5.)
        changes=copy.deepcopy(p); changes['regions']=list(p.get('regions') or ())+[r]
        # Expand the terrain to contain the shape; points themselves are never moved.
        changes.update(x0=min(float(p['x0']),min(q[0] for q in points)),
                       y0=min(float(p['y0']),min(q[1] for q in points)),
                       x1=max(float(p['x1']),max(q[0] for q in points)),
                       y1=max(float(p['y1']),max(q[1] for q in points)))
        try:
            if e is None:
                e=Entity('terrain',changes,name='Έδαφος'); self.window.stack.execute(AddEntity(e))
            else: self.window.stack.execute(UpdateEntity(e.id,changes))
        except (ValueError,RuntimeError,PermissionError) as exc:
            self.window.statusBar().showMessage(str(exc),7000); return False
        self.mode='edit'; self.selected=('region',r['id'])
        self.window.plan_view.controller.set_tool('select')
        self.window.doc.select([e.id]); self.window._redraw_views(all_views=True); self.window.refresh_inspector()
        self.window.statusBar().showMessage(f'{SHAPES[shape]}: {mark(z)} · σύρε κορυφή/σώμα · Ιδιότητες για υψόμετρο/μετάβαση · Ctrl+Z αναίρεση',8000)
        return True

    def _hit(self, view, x, y):
        e=self.window._terrain_entity()
        if not e: return None
        from archforge.core.layers import editable
        if not e.visible or e.locked or not editable(view.doc,e.id): return None
        tol=9/max(1.,abs(view.transform().m11()))
        for i,p in enumerate(e.params.get('points') or ()):
            if math.dist((x,y),p[:2])<=tol: return ('point',i,None)
        for r in reversed(e.params.get('regions') or ()):
            for i,p in enumerate(r['points']):
                if r['shape']=='circle' and i%12: continue
                if math.dist((x,y),p)<=tol: return ('region',r['id'],i)
            if distance_to_region(x,y,r['points'])<=tol: return ('region',r['id'],None)
        return None

    def update_selected(self, key, value):
        e,current=self._current()
        if current is None: return False
        if self.selected[0]=='point':
            pts=copy.deepcopy(e.params.get('points') or []); i=self.selected[1]
            pts[i][{'x':0,'y':1,'elevation':2}[key]]=float(value)
            return self._change({'points':pts})
        regs=copy.deepcopy(e.params.get('regions') or [])
        for r in regs:
            if r['id']==self.selected[1]: r[key]=float(value)
        return self._change({'regions':regs})

    def delete_selected(self):
        e,current=self._current()
        if current is None or self.mode!='edit' or e.id not in self.window.doc.selection: return False
        if self.selected[0]=='point':
            pts=copy.deepcopy(e.params.get('points') or []); del pts[self.selected[1]]; changes={'points':pts}
        else: changes={'regions':[r for r in e.params.get('regions') or () if r['id']!=self.selected[1]]}
        if self._change(changes):
            self.selected=None; self.window.plan_view.redraw(); self.window.refresh_inspector()
        return True

    def edit_elevation(self):
        e,c=self._current()
        if c is None: return
        z=c[2] if self.selected[0]=='point' else c['elevation']
        value,ok=QInputDialog.getDouble(self.window,'Υψόμετρο','Υψόμετρο ως προς ±0,00 ισογείου (m):',z,-1000.,1000.,3)
        if ok: self.update_selected('elevation',value)

    def _finish_polygon(self):
        points=self.draft or []; self.draft=self.anchor=self.cursor=None
        if len(points)>=3: self.place_shape(points,'polygon')
        self.window.plan_view.redraw()

    def handle(self, view, kind, event):
        if not self._active(view): return False
        if kind=='key':
            if event.key()==Qt.Key.Key_Escape: self.cancel(); view.redraw(); return True
            if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self.mode=='polygon': self._finish_polygon(); return True
            if event.key()==Qt.Key.Key_Delete: return self.delete_selected()
            return False
        if kind=='context':
            x,y=self._xy(view,event); hit=self._hit(view,x,y)
            if not hit: return False
            self.selected=hit[:2]; self.mode='edit'; self.window.doc.select([self.window._terrain_entity().id])
            self.window.refresh_inspector(); view.redraw()
            menu=QMenu(view); edit=menu.addAction('Αλλαγή υψομέτρου…'); delete=menu.addAction('Διαγραφή περιοχής' if hit[0]=='region' else 'Διαγραφή σημείου')
            chosen=menu.exec(event.globalPos())
            if chosen==edit: self.edit_elevation()
            elif chosen==delete: self.delete_selected()
            return True
        if kind=='dclick':
            if self.mode=='polygon': self._finish_polygon(); return True
            x,y=self._xy(view,event); hit=self._hit(view,x,y)
            if not hit: return False
            self.selected=hit[:2]
            self.edit_elevation(); return self.selected is not None
        if kind not in ('press','move','release'): return False
        if kind in ('press','release') and event.button()!=Qt.MouseButton.LeftButton: return False
        x,y=self._xy(view,event); self.cursor=(x,y)
        if self.mode in SHAPES:
            if self.mode=='polygon':
                if kind=='press':
                    pts=self.draft or []
                    tol=9/max(1.,abs(view.transform().m11()))
                    if len(pts)>=3 and math.dist(pts[0],(x,y))<=tol: self._finish_polygon()
                    elif not pts or math.dist(pts[-1],(x,y))>1e-6: self.draft=pts+[(x,y)]
                view._long_press=None; view.redraw(); return True
            if kind=='press': self.anchor=(x,y); view._long_press=None
            if kind=='release' and self.anchor is not None:
                shape=self.mode; points=shape_points(shape,self.anchor,(x,y)); self.anchor=self.cursor=None
                self.place_shape(points,shape)
            view.redraw(); return True
        if kind=='press':
            hit=self._hit(view,x,y)
            if not hit: self.selected=None; self.window.refresh_inspector(); return False
            self.selected=hit[:2]; e,current=self._current()
            if e.locked: return False
            view._long_press=None
            self.window.doc.select([e.id]); self.window.refresh_inspector()
            self.drag=dict(hit=hit,start=(x,y),original=copy.deepcopy(current),preview=copy.deepcopy(current),moved=False)
            view.redraw(); return True
        if self.drag is None: return False
        hit=self.drag['hit']; dx,dy=x-self.drag['start'][0],y-self.drag['start'][1]
        original=self.drag['original']; preview=copy.deepcopy(original)
        if hit[0]=='point': preview[:2]=[original[0]+dx,original[1]+dy]
        else:
            if hit[2] is None:
                preview['points']=[[a+dx,b+dy] for a,b in original['points']]
            elif original['shape']=='rectangle':
                opposite=original['points'][(hit[2]+2)%4]
                preview['points']=shape_points('rectangle',opposite,(x,y))
            elif original['shape']=='circle':
                center=tuple(sum(p[k] for p in original['points'])/len(original['points']) for k in (0,1))
                preview['points']=shape_points('circle',center,(x,y))
            else:
                preview['points'][hit[2]]=[x,y]
        self.drag['preview']=preview; self.drag['moved']=math.hypot(dx,dy)>1e-6
        if kind=='release':
            e=self.window._terrain_entity()
            if self.drag['moved']:
                if hit[0]=='point':
                    pts=copy.deepcopy(e.params['points']); pts[hit[1]]=preview; self._change({'points':pts})
                else:
                    regs=[preview if r['id']==hit[1] else r for r in e.params['regions']]; self._change({'regions':regs})
            self.drag=None
        view.redraw(); return True

    def add_rows(self, form, entity):
        e,c=self._current()
        if not e or e.id!=entity.id or c is None or self.mode!='edit': return False
        point=self.selected[0]=='point'
        form.addRow('Έδαφος',QLabel('Υψομετρικό σημείο' if point else SHAPES[c['shape']]))
        for key,label,value in ([('x','X (m)',c[0]),('y','Y (m)',c[1]),('elevation','Υψόμετρο (m)',c[2])] if point else
                                [('elevation','Υψόμετρο (m)',c['elevation']),('transition','Μετάβαση έξω από περίγραμμα (m)',c['transition'])]):
            spin=QDoubleSpinBox(); spin.setDecimals(3); spin.setRange(.1 if key=='transition' else -1000.,1000.); spin.setValue(value); spin.setSingleStep(.1)
            spin.editingFinished.connect(lambda k=key,w=spin:self.update_selected(k,w.value())); form.addRow(label,spin)
        if not point: form.addRow('Επιφάνεια',QLabel(f"{abs(signed_area(c['points'])):.2f} m²"))
        hint=QLabel('Σύρε το σώμα για μετακίνηση ή μια κορυφή για αλλαγή σχήματος.\nCtrl+Z / Ctrl+Y: αναίρεση / επανάληψη.'); hint.setWordWrap(True); form.addRow(hint)
        button=QPushButton('Διαγραφή σημείου' if point else 'Διαγραφή περιοχής'); button.clicked.connect(self.delete_selected); form.addRow(button)
        return True

    def paint(self, view):
        if view.structural_only: return
        e=self.window._terrain_entity()
        from archforge.core.layers import entity_state
        if e is not None and (not e.visible or not entity_state(view.doc,e.id)['visible']): return
        params=e.params if e is not None else {}
        radius=5/max(1.,abs(view.transform().m11()))
        def label(text,x,y,color):
            item=view._scene.addText(text); item.setDefaultTextColor(color)
            item.setHtml(f'<span style="background-color:#ffffff;font-weight:bold">{text}</span>')
            item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations,True); item.setPos(x,y); item.setZValue(42)
        def draw(points,color,selected=False,dashed=True,shape='polygon'):
            pen=QPen(color); pen.setCosmetic(True); pen.setWidthF(2. if selected else 1.2)
            if dashed: pen.setStyle(Qt.PenStyle.DashLine)
            item=view._scene.addPolygon(QPolygonF([QPointF(*p) for p in points]),pen,QBrush(QColor(color.red(),color.green(),color.blue(),25)))
            item.setZValue(2)
            handles=points[::12] if shape=='circle' else points
            for x,y in handles:
                view._scene.addEllipse(x-radius,y-radius,2*radius,2*radius,QPen(color,0),QBrush(QColor('white'))).setZValue(41)
        if e is not None:
            # A graded plane has no control points, but its levels must still be visible.
            for x,y in ((params['x0'],params['y0']),(params['x1'],params['y0']),
                        (params['x1'],params['y1']),(params['x0'],params['y1'])):
                label(mark(terrain_height(params,x,y)),x,y,BROWN)
        for r in params.get('regions') or ():
            if self.drag and self.drag['hit'][0]=='region' and self.drag['hit'][1]==r['id']: r=self.drag['preview']
            sel=self.selected==('region',r['id']) and self.mode=='edit'
            draw(r['points'],BLUE if sel else BROWN,sel,shape=r['shape'])
            x=sum(p[0] for p in r['points'])/len(r['points']); y=sum(p[1] for p in r['points'])/len(r['points'])
            label(mark(r['elevation']),x,y,BLUE if sel else BROWN)
        native_points=any(p.role=='terrain-label' for p in getattr(view,'_frame',()).primitives) if hasattr(getattr(view,'_frame',None),'primitives') else False
        for i,p in enumerate(params.get('points') or ()):
            if self.drag and self.drag['hit'][:2]==('point',i): p=self.drag['preview']
            x,y,z=p; sel=self.selected==('point',i) and self.mode=='edit'
            view._scene.addEllipse(x-radius,y-radius,2*radius,2*radius,QPen(BLUE if sel else BROWN,0),QBrush(QColor('white'))).setZValue(41)
            if not native_points: label(mark(z),x+.15,y+.15,BROWN)
        preview=None
        if self.mode in ('rectangle','circle') and self.anchor is not None and self.cursor is not None:
            preview=shape_points(self.mode,self.anchor,self.cursor)
        elif self.mode=='polygon' and self.draft:
            preview=self.draft+([self.cursor] if self.cursor else [])
        if preview and len(preview)>=2: draw(preview,BLUE,True,shape=self.mode)


def install(window):
    tool=TerrainTools(window); window._terrain_tools=tool; window.plan_view.terrain_tool=tool
    menu=window._mockup_terrain_menu
    sub=QMenu('Υψομετρικές περιοχές / σχήματα',menu)
    for shape,text in [*SHAPES.items(),('edit','Επιλογή / επεξεργασία περιοχών και σημείων')]:
        a=QAction(text,window); a.triggered.connect(lambda _=False,s=shape:tool.start(s)); sub.addAction(a)
    menu.insertMenu(menu.actions()[menu.actions().index(next(a for a in menu.actions() if a.text()=='Υψομετρικά σημεία'))+1],sub)
    section=QAction('Τομή εδάφους / υπογείου',window)
    section.triggered.connect(lambda:window._start_site_tool('view_section','Σύρε γραμμή τομής από μπροστά έως πίσω στο οικόπεδο'))
    sub.addSeparator(); sub.addAction(section); window._terrain_regions_menu=sub
    rectangle=QAction('Υψομετρικό πλαίσιο',window)
    rectangle.setToolTip('Σύρε ορθογώνιο στην κάτοψη και δώσε υψόμετρο σε μέτρα')
    rectangle.triggered.connect(lambda:tool.start('rectangle'))
    # Keep the second row's camera/grid controls visible at 1280 px.
    window._mockup_ribbon.addAction(window._mockup_basement_action)
    window._mockup_ribbon.addAction(rectangle)
    window._terrain_rectangle_action=rectangle
