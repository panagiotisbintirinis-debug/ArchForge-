from __future__ import annotations

from .commands import UpdateEntity


def opening_elevation_handles(doc,eid,axis,override_params=None):
    """Return [(handle, x_or_y, z), ...] for a selected opening in XZ/YZ."""
    if axis not in ('XZ','YZ'): raise ValueError('axis must be XZ or YZ')
    e=doc.get(eid)
    if e.kind not in ('door','window') or not e.parent_id or e.parent_id not in doc.entities:return []
    p=override_params if override_params is not None else e.params
    host=doc.get(e.parent_id).params
    from archforge.architecture.openings import elevation_rect
    rect=elevation_rect(host,p,axis)
    xs=[q[0] for q in rect];mid=(min(xs)+max(xs))/2
    base=float(host['z']);bottom=base+float(p.get('sill',0.0));top=bottom+float(p['height'])
    out=[('top',mid,top)]
    if e.kind=='window':out.append(('bottom',mid,bottom))
    return out


class OpeningVerticalEditTransaction:
    """Edit top/bottom edges of an attached opening in elevation.

    `top` changes opening height while preserving sill. `bottom` is available only for
    windows and moves the sill while preserving the opening top elevation.
    """
    def __init__(self, doc, stack, eid, handle='top'):
        e=doc.get(eid)
        if e.kind not in ('door','window'):
            raise ValueError('vertical opening edit requires door/window')
        if handle not in ('top','bottom'):
            raise ValueError('opening elevation handle must be top or bottom')
        if e.kind=='door' and handle=='bottom':
            raise ValueError('door bottom is fixed to wall base')
        if not e.parent_id or e.parent_id not in doc.entities or doc.get(e.parent_id).kind!='wall':
            raise ValueError('opening has no valid host wall')
        self.doc=doc;self.stack=stack;self.eid=eid;self.kind=e.kind;self.host_id=e.parent_id;self.handle=handle
        self.before=e.params.copy();self.preview=e.params.copy();self.cancelled=False

    def update(self, z):
        from archforge.architecture.openings import validate_opening
        wall=self.doc.get(self.host_id).params
        z=float(z);base=float(wall['z']);p=self.before.copy()
        if self.handle=='top':
            height=z-(base+p['sill'])
            if height<=0: raise ValueError('opening height must remain positive')
            p['height']=height
        else:
            old_top=base+p['sill']+p['height']
            sill=z-base
            height=old_top-z
            if sill<0: raise ValueError('window sill cannot be below wall base')
            if height<=0: raise ValueError('window height must remain positive')
            p['sill']=sill;p['height']=height
        validate_opening(wall,p,self.kind)
        self.preview=p
        return {'height':p['height'],'sill':p['sill'],'bottom_z':base+p['sill'],'top_z':base+p['sill']+p['height']}

    def commit(self):
        if self.cancelled: raise RuntimeError('transaction cancelled')
        self.stack.execute(UpdateEntity(self.eid,self.preview))
        return self.eid

    def cancel(self):
        self.cancelled=True;self.preview=self.before.copy()
