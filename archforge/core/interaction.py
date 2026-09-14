from __future__ import annotations
from dataclasses import dataclass
from math import hypot,atan2,degrees
from typing import Optional,Tuple,Dict,Any
from .model import Document,Entity
from .commands import CommandStack,AddEntity,UpdateEntity
from .snapping import best_snap

@dataclass
class HUD:
    values: Dict[str,float]

class WallDrawTransaction:
    def __init__(self,doc:Document,stack:CommandStack,start:Tuple[float,float],z=0.0,height=2.7,thickness=0.15,grid=0.1,snap_tol=0.15):
        self.doc,self.stack=doc,stack;self.start=start;self.end=start;self.z=z;self.height=height;self.thickness=thickness;self.grid=grid;self.snap_tol=snap_tol;self.cancelled=False
    def update(self,x,y):
        sp=best_snap(self.doc,x,y,self.snap_tol,self.grid)
        self.end=(sp.x,sp.y) if sp else (x,y)
        dx=self.end[0]-self.start[0];dy=self.end[1]-self.start[1]
        return HUD({'length':hypot(dx,dy),'angle_deg':degrees(atan2(dy,dx)),'x':self.end[0],'y':self.end[1],'z':self.z})
    def commit(self,exact_length:Optional[float]=None)->str:
        if self.cancelled:raise RuntimeError('transaction cancelled')
        sx,sy=self.start;ex,ey=self.end;dx,dy=ex-sx,ey-sy;L=hypot(dx,dy)
        if exact_length is not None:
            if exact_length<=0:raise ValueError('length must be > 0')
            if L==0:raise ValueError('cannot set exact length for zero direction')
            ex=sx+dx/L*exact_length;ey=sy+dy/L*exact_length;L=exact_length
        if L==0:raise ValueError('zero-length wall')
        e=Entity('wall',{'x1':sx,'y1':sy,'x2':ex,'y2':ey,'z':self.z,'height':self.height,'thickness':self.thickness},name='Wall')
        self.stack.execute(AddEntity(e));return e.id
    def cancel(self):self.cancelled=True

class BoxStretchTransaction:
    def __init__(self,doc,stack,eid,handle):
        self.doc,self.stack,self.eid,self.handle=doc,stack,eid,handle;self.before=doc.get(eid).params.copy();self.preview=self.before.copy()
    def update(self,x=None,y=None,z=None):
        p=self.before.copy();cx,cy=p['x'],p['y'];w,d,h=p['width'],p['depth'],p['height'];left,right=cx-w/2,cx+w/2;bottom,top=cy-d/2,cy+d/2
        if 'right' in self.handle and x is not None:right=x
        if 'left' in self.handle and x is not None:left=x
        if 'top' in self.handle and y is not None:top=y
        if 'bottom' in self.handle and y is not None:bottom=y
        if right<=left or top<=bottom:raise ValueError('stretch inverted object')
        p['x']=(left+right)/2;p['y']=(bottom+top)/2;p['width']=right-left;p['depth']=top-bottom
        if 'height' in self.handle and z is not None:
            if z<=p['z']:raise ValueError('height must remain above base')
            p['height']=z-p['z']
        self.preview=p;return HUD({'width':p['width'],'depth':p['depth'],'height':p['height'],'x':p['x'],'y':p['y'],'z':p['z']})
    def commit(self):self.stack.execute(UpdateEntity(self.eid,self.preview))
    def cancel(self):self.preview=self.before.copy()

class RotateTransaction:
    def __init__(self,doc,stack,eid,pivot=None,angle_increment=15.0):
        self.doc,self.stack,self.eid=doc,stack,eid;self.before=doc.get(eid).params.copy();self.preview=self.before.copy();self.angle_increment=float(angle_increment) if angle_increment else None;e=doc.get(eid);p=e.params
        if pivot is not None:self.pivot=pivot
        elif e.kind=='box':self.pivot=(p['x'],p['y'])
        elif e.kind=='pod':self.pivot=(p['cx'],p['cy'])
        elif e.kind=='wall':self.pivot=((p['x1']+p['x2'])/2,(p['y1']+p['y2'])/2)
        else:raise ValueError('rotation unsupported for entity kind')
    def update_angle(self,angle_deg,snap=True):
        a=float(angle_deg)
        if snap and self.angle_increment:a=round(a/self.angle_increment)*self.angle_increment
        from math import radians,cos,sin
        r=radians(a);c,s=cos(r),sin(r);px,py=self.pivot;p=self.before.copy();e=self.doc.get(self.eid)
        if e.kind=='box':p['rotation']=p.get('rotation',0.0)+a
        elif e.kind=='wall':
            def rot(x,y):dx,dy=x-px,y-py;return px+dx*c-dy*s,py+dx*s+dy*c
            p['x1'],p['y1']=rot(p['x1'],p['y1']);p['x2'],p['y2']=rot(p['x2'],p['y2'])
        elif e.kind=='pod':p['rotation']=p.get('rotation',0.0)+a
        self.preview=p;return HUD({'angle_deg':a,'pivot_x':px,'pivot_y':py})
    def update_pointer(self,x,y,start_angle_deg=0.0,snap=True):return self.update_angle(degrees(atan2(y-self.pivot[1],x-self.pivot[0]))-float(start_angle_deg),snap)
    def commit(self):self.stack.execute(UpdateEntity(self.eid,self.preview))
    def cancel(self):self.preview=self.before.copy()

class WallEndpointStretchTransaction:
    def __init__(self,doc,stack,eid,endpoint,grid=0.1,snap_tol=0.15):
        if endpoint not in (1,2):raise ValueError('endpoint must be 1 or 2')
        self.doc,self.stack,self.eid,self.endpoint=doc,stack,eid,endpoint;self.before=doc.get(eid).params.copy();self.preview=self.before.copy();self.grid=grid;self.snap_tol=snap_tol
    def update(self,x,y):
        sp=best_snap(self.doc,x,y,self.snap_tol,self.grid,{self.eid});x,y=(sp.x,sp.y) if sp else (x,y);p=self.before.copy();p[f'x{self.endpoint}']=x;p[f'y{self.endpoint}']=y;L=hypot(p['x2']-p['x1'],p['y2']-p['y1'])
        if L<=1e-9:raise ValueError('zero-length wall')
        self.preview=p;return HUD({'length':L,'angle_deg':degrees(atan2(p['y2']-p['y1'],p['x2']-p['x1'])),'x':x,'y':y,'z':p['z']})
    def commit(self):self.stack.execute(UpdateEntity(self.eid,self.preview))
    def cancel(self):self.preview=self.before.copy()

class PodStretchTransaction:
    def __init__(self,doc,stack,eid,handle):
        if handle not in ('left','right','top','bottom','height'):raise ValueError('invalid pod handle')
        self.doc,self.stack,self.eid,self.handle=doc,stack,eid,handle;self.before=doc.get(eid).params.copy();self.preview=self.before.copy()
    def update(self,x=None,y=None,z=None):
        p=self.before.copy();cx,cy=p['cx'],p['cy'];rx,ry=p['diameter_x']/2,p['diameter_y']/2;left,right=cx-rx,cx+rx;bottom,top=cy-ry,cy+ry
        if self.handle=='left' and x is not None:left=x
        elif self.handle=='right' and x is not None:right=x
        elif self.handle=='bottom' and y is not None:bottom=y
        elif self.handle=='top' and y is not None:top=y
        elif self.handle=='height' and z is not None:
            if z<=p['floor_level']:raise ValueError('pod top must remain above floor')
            p['height']=z-p['floor_level']
        if right<=left or top<=bottom:raise ValueError('stretch inverted pod')
        p['cx']=(left+right)/2;p['cy']=(bottom+top)/2;p['diameter_x']=right-left;p['diameter_y']=top-bottom;self.preview=p
        return HUD({'diameter_x':p['diameter_x'],'diameter_y':p['diameter_y'],'height':p['height'],'cx':p['cx'],'cy':p['cy'],'floor_level':p['floor_level']})
    def commit(self):self.stack.execute(UpdateEntity(self.eid,self.preview))
    def cancel(self):self.preview=self.before.copy()

class VerticalStretchTransaction:
    def __init__(self,doc,stack,eid):
        self.doc,self.stack,self.eid=doc,stack,eid;self.before=doc.get(eid).params.copy();self.preview=self.before.copy()
        if doc.get(eid).kind not in ('wall','box','pod'):raise ValueError('vertical stretch unsupported for entity kind')
    def update(self,z):
        p=self.before.copy();e=self.doc.get(self.eid);z=float(z);base=p['z'] if e.kind in ('wall','box') else p['floor_level']
        if z<=base:raise ValueError('top must remain above base')
        p['height']=z-base;self.preview=p;return HUD({'height':p['height'],'base_z':base,'top_z':z})
    def commit(self):self.stack.execute(UpdateEntity(self.eid,self.preview))
    def cancel(self):self.preview=self.before.copy()

class OpeningPlaceTransaction:
    """Attach a conventional door/window to the nearest wall or organic pod shell."""
    def __init__(self,doc,stack,kind,x,y,tolerance=0.35,width=None,height=None,sill=None,flat_margin=0.25):
        if kind not in ('door','window'):raise ValueError('opening kind must be door or window')
        self.doc,self.stack,self.kind=doc,stack,kind;self.tolerance=float(tolerance);self.cancelled=False;self.width=float(width if width is not None else (.9 if kind=='door' else 1.2));self.height=float(height if height is not None else (2.1 if kind=='door' else 1.2));self.sill=float(sill if sill is not None else (0.0 if kind=='door' else .9));self.flat_margin=float(flat_margin);self.host_id=None;self.host_kind=None;self.preview={};self.update(x,y)
    def update(self,x,y):
        from archforge.architecture.openings import nearest_opening_host,validate_opening,validate_pod_opening
        hit=nearest_opening_host(self.doc,x,y,self.tolerance)
        if hit is None:self.host_id=None;self.host_kind=None;self.preview={};return HUD({'valid':0.0})
        host=self.doc.get(hit['host_id']);self.host_id=hit['host_id'];self.host_kind=hit['host_kind']
        if host.kind=='wall':
            p={'offset':hit['offset'],'width':self.width,'height':self.height,'sill':self.sill}
            try:validate_opening(host.params,p,self.kind);valid=1.0
            except ValueError:valid=0.0
            self.preview=p;return HUD({'offset':p['offset'],'width':p['width'],'height':p['height'],'sill':p['sill'],'distance':hit['distance'],'valid':valid})
        p={'surface_u':hit['surface_u'],'width':self.width,'height':self.height,'sill':self.sill,'flat_margin':self.flat_margin}
        try:validate_pod_opening(host.params,p,self.kind);valid=1.0
        except ValueError:valid=0.0
        self.preview=p;return HUD({'surface_u':p['surface_u'],'width':p['width'],'height':p['height'],'sill':p['sill'],'distance':hit['distance'],'valid':valid})
    def preview_segment(self):
        if not self.host_id or not self.preview:return None
        from archforge.architecture.openings import plan_segment,pod_opening_plan_segment
        host=self.doc.get(self.host_id)
        return plan_segment(host.params,self.preview) if host.kind=='wall' else pod_opening_plan_segment(host.params,{**self.preview,'_kind':self.kind})
    def commit(self):
        if self.cancelled:raise RuntimeError('transaction cancelled')
        if not self.host_id or not self.preview:raise ValueError('opening must be placed on a wall or pod')
        host=self.doc.get(self.host_id)
        from archforge.architecture.openings import validate_opening,validate_pod_opening
        if host.kind=='wall':validate_opening(host.params,self.preview,self.kind)
        elif host.kind=='pod':validate_pod_opening(host.params,self.preview,self.kind)
        else:raise ValueError('opening host must be a wall or pod')
        e=Entity(self.kind,dict(self.preview),name=self.kind.title(),parent_id=self.host_id)
        if host.kind=='pod':
            from .opening_commands import AddOpeningEntity
            self.stack.execute(AddOpeningEntity(e))
        else:self.stack.execute(AddEntity(e))
        return e.id
    def cancel(self):self.cancelled=True

class OpeningEditTransaction:
    """Move/stretch an opening in its host's semantic frame."""
    def __init__(self,doc,stack,eid,handle='move'):
        e=doc.get(eid)
        if e.kind not in ('door','window'):raise ValueError('opening edit requires door/window')
        if not e.parent_id or e.parent_id not in doc.entities or doc.get(e.parent_id).kind not in ('wall','pod'):raise ValueError('opening has no valid wall/pod host')
        if handle not in ('move','left','right'):raise ValueError('opening handle must be move, left or right')
        self.doc,self.stack,self.eid,self.handle=doc,stack,eid,handle
        self.kind=e.kind;self.host_id=e.parent_id;self.before=e.params.copy();self.preview=e.params.copy();self.cancelled=False
    def update(self,x,y):
        host=self.doc.get(self.host_id);p=self.before.copy()
        if host.kind=='pod':
            from archforge.architecture.openings import project_to_pod,validate_pod_opening
            u,px,py,distance=project_to_pod(host.params,x,y)
            if self.handle=='move':p['surface_u']=u
            else:
                from archforge.architecture.openings import pod_opening_plan_segment
                a,b=pod_opening_plan_segment(host.params,{**self.before,'_kind':self.kind});fixed=b if self.handle=='left' else a
                width=hypot(float(x)-fixed[0],float(y)-fixed[1])
                if width<=1e-9:raise ValueError('opening width must remain positive')
                p['width']=width
                mu,_,_,_=project_to_pod(host.params,(float(x)+fixed[0])/2.0,(float(y)+fixed[1])/2.0);p['surface_u']=mu
            validate_pod_opening(host.params,p,self.kind);self.preview=p
            return HUD({'surface_u':p['surface_u'],'width':p['width'],'height':p['height'],'sill':p['sill'],'distance':distance,'x':px,'y':py,'valid':1.0})
        from archforge.architecture.openings import project_to_wall,validate_opening
        wall=host.params;projected,px,py,distance=project_to_wall(wall,x,y)
        if self.handle=='move':p['offset']=projected
        else:
            left=self.before['offset']-self.before['width']/2;right=self.before['offset']+self.before['width']/2
            if self.handle=='left':left=projected
            else:right=projected
            if right-left<=1e-9:raise ValueError('opening width must remain positive')
            p['offset']=(left+right)/2;p['width']=right-left
        validate_opening(wall,p,self.kind);self.preview=p
        return HUD({'offset':p['offset'],'width':p['width'],'height':p['height'],'sill':p['sill'],'distance':distance,'x':px,'y':py,'valid':1.0})
    def preview_segment(self):
        from archforge.architecture.openings import plan_segment,pod_opening_plan_segment
        host=self.doc.get(self.host_id)
        return plan_segment(host.params,self.preview) if host.kind=='wall' else pod_opening_plan_segment(host.params,{**self.preview,'_kind':self.kind})
    def commit(self):
        if self.cancelled:raise RuntimeError('transaction cancelled')
        self.stack.execute(UpdateEntity(self.eid,self.preview));return self.eid
    def cancel(self):self.cancelled=True;self.preview=self.before.copy()
