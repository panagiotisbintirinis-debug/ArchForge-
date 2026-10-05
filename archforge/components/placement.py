"""Human-first placement transaction for reusable ArchForge components."""
from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.core.snapping import best_snap


class ComponentPlaceTransaction:
    """Place one semantic component with live plan preview and existing CAD snap."""
    def __init__(self,doc,stack,x,y,definition,*,z=0.0,grid=.10,snap_tol=.10):
        self.doc,self.stack=doc,stack
        self.definition=dict(definition)
        self.z=float(z);self.grid=grid;self.snap_tol=float(snap_tol)
        self.cancelled=False;self.last_snap=None;self.preview={}
        self.update(x,y)

    def update(self,x,y):
        if self.definition.get('entity')=='cabinet':
            return self._update_cabinet(float(x),float(y))
        sp=best_snap(self.doc,float(x),float(y),self.snap_tol,self.grid)
        if sp is not None:
            x,y=float(sp.x),float(sp.y);self.last_snap=sp
        else:
            x,y=float(x),float(y);self.last_snap=None
        self.preview={
            'x':x,'y':y,'z':self.z,
            'width':float(self.definition['width']),
            'depth':float(self.definition['depth']),
            'height':float(self.definition['height']),
            'rotation':float(self.definition.get('rotation',0.0)),
            'role':str(self.definition['role']),
            'run_id':str(self.definition.get('library_id','manual')),
            'roughness':float(self.definition.get('roughness',0.5)),
            'metallic':float(self.definition.get('metallic',0.0)),
        }
        return self.preview

    def _update_cabinet(self,x,y):
        """Cabinets back onto the nearest wall and butt against neighbours."""
        from archforge.kitchen.cabinets import default_params, snap_to_neighbours, wall_aligned
        d=self.definition
        p=default_params(d['cabinet_type'],x,y,rotation=float(d.get('rotation',0.0)),width=d.get('width'))
        for key in ('depth','height','plinth','doors','drawers','shelves','worktop','handle'):
            if key in d:p[key]=d[key]
        if p['cabinet_type']!='wall':p['z']=self.z
        else:p['z']=self.z+float(d.get('z',p['z']))
        aligned=wall_aligned(self.doc,x,y,float(p['depth']),z=self.z)
        self.last_snap=None
        if aligned is not None:
            p['x'],p['y'],p['rotation']=aligned
            p['x'],p['y']=snap_to_neighbours(self.doc,p['x'],p['y'],p['rotation'],float(p['width']),float(p['depth']))
        else:
            sp=best_snap(self.doc,x,y,self.snap_tol,self.grid)
            if sp is not None:p['x'],p['y']=float(sp.x),float(sp.y);self.last_snap=sp
        self.preview=p
        return self.preview

    def commit(self):
        if self.cancelled: raise RuntimeError('transaction cancelled')
        if self.definition.get('entity')=='cabinet':
            e=Entity('cabinet',dict(self.preview),name=str(self.definition['name']))
            self.stack.execute(AddEntity(e));return e.id
        e=Entity('kitchen_part',dict(self.preview),name=str(self.definition['name']))
        self.stack.execute(AddEntity(e));return e.id

    def cancel(self): self.cancelled=True
