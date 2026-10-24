from __future__ import annotations

from math import atan2, cos, degrees, hypot, radians, sin
import copy

from .commands import UpdateEntities
from .interaction import HUD
from .snapping import best_snap


class ConnectedWallEndpointStretchTransaction:
    """Move a wall endpoint and all coincident wall endpoints as one junction.

    Source wall entities remain independent semantic objects, but a visually joined node
    behaves as one editing unit. The operation previews non-destructively and commits as
    one atomic undo step.
    """
    def __init__(self, doc, stack, eid, endpoint, grid=0.1, snap_tol=0.15, join_tol=1e-5):
        if endpoint not in (1,2):
            raise ValueError('endpoint must be 1 or 2')
        if eid not in doc.entities or doc.get(eid).kind!='wall':
            raise ValueError('connected endpoint stretch requires a wall')
        self.doc=doc;self.stack=stack;self.eid=eid;self.endpoint=endpoint
        self.grid=grid;self.snap_tol=snap_tol;self.join_tol=float(join_tol)
        primary=doc.get(eid).params
        self.anchor=(primary[f'x{endpoint}'],primary[f'y{endpoint}'])
        self.z=primary['z']
        self.linked=[]
        for wid,e in doc.entities.items():
            if e.kind!='wall' or not e.visible or abs(e.params['z']-self.z)>self.join_tol:
                continue
            for ep in (1,2):
                q=(e.params[f'x{ep}'],e.params[f'y{ep}'])
                if hypot(q[0]-self.anchor[0],q[1]-self.anchor[1])<=self.join_tol:
                    self.linked.append((wid,ep))
        if (eid,endpoint) not in self.linked:
            self.linked.append((eid,endpoint))
        self.before={wid:copy.deepcopy(doc.get(wid).params) for wid,_ in self.linked}
        self.previews=copy.deepcopy(self.before)
        self.preview=copy.deepcopy(self.before[eid])
        self.cancelled=False
        # A free end (nothing joined there) is lengthened, not swung (owner 24/10: «προσπαθούσα να μεγαλώσω τον
        # τοίχο που είχε μείνει στην άκρη» — it turned to −111°): the direction holds to the wall's own line and to
        # 90°/45°, as when drawing. Shift (angle_enabled=False) = free. A corner joined to other walls moves freely.
        self.angle_enabled=True
        self.angle_snapped=False
        p=primary;other=3-endpoint
        self.fixed=(float(p[f'x{other}']),float(p[f'y{other}']))
        self.own_deg=degrees(atan2(self.anchor[1]-self.fixed[1],self.anchor[0]-self.fixed[0]))

    OWN_LINE_DEG=12.0            # the wall's own line pulls from this far (deg)

    def _held_direction(self,x,y):
        """The point along a held direction from the fixed end, or None when the pointer is not near one."""
        from .interaction import MAGNET_STEPS
        fx,fy=self.fixed;L=hypot(x-fx,y-fy)
        if L<1e-9:return None
        a=degrees(atan2(y-fy,x-fx))
        def off(t):return abs((a-t+180.0)%360.0-180.0)
        targets=[(self.own_deg,self.OWN_LINE_DEG),(self.own_deg+180.0,self.OWN_LINE_DEG)]
        targets+=[(round(a/step)*step,tol) for step,tol in MAGNET_STEPS[:2]]
        held=min((t for t,tol in targets if off(t)<=tol),key=off,default=None)
        if held is None:return None
        r=radians(held);L=round(L*(cos(radians(a-held))),2)    # whole centimetres along the held line
        return fx+L*cos(r),fy+L*sin(r)

    def update(self,x,y):
        exclude={wid for wid,_ in self.linked}
        sp=best_snap(self.doc,x,y,self.snap_tol,self.grid,exclude)
        held=None;self.angle_snapped=False
        if self.angle_enabled and len(self.linked)==1 and (sp is None or sp.kind=='construction_grid'):
            held=self._held_direction(float(x),float(y))
        if held is not None:
            x,y=held;self.angle_snapped=True
        else:
            x,y=(sp.x,sp.y) if sp else (float(x),float(y))
        previews=copy.deepcopy(self.before)
        for wid,ep in self.linked:
            p=previews[wid]
            p[f'x{ep}']=x;p[f'y{ep}']=y
            if hypot(p['x2']-p['x1'],p['y2']-p['y1'])<=1e-9:
                raise ValueError('junction move would create a zero-length wall')
        self.previews=previews;self.preview=copy.deepcopy(previews[self.eid])
        p=self.preview
        return HUD({'length':hypot(p['x2']-p['x1'],p['y2']-p['y1']),
                    'angle_deg':degrees(atan2(p['y2']-p['y1'],p['x2']-p['x1'])),
                    'x':x,'y':y,'z':p['z'],'joined_walls':float(len(self.previews))})

    def commit(self):
        if self.cancelled:
            raise RuntimeError('transaction cancelled')
        self.stack.execute(UpdateEntities(copy.deepcopy(self.previews)))
        return self.eid

    def cancel(self):
        self.cancelled=True
        self.previews=copy.deepcopy(self.before)
        self.preview=copy.deepcopy(self.before[self.eid])
