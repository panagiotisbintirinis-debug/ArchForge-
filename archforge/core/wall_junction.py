from __future__ import annotations

from math import atan2, degrees, hypot
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

    def update(self,x,y):
        exclude={wid for wid,_ in self.linked}
        sp=best_snap(self.doc,x,y,self.snap_tol,self.grid,exclude)
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
