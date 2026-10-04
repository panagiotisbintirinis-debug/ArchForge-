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

    def commit(self):
        if self.cancelled: raise RuntimeError('transaction cancelled')
        e=Entity('kitchen_part',dict(self.preview),name=str(self.definition['name']))
        self.stack.execute(AddEntity(e));return e.id

    def cancel(self): self.cancelled=True
