from __future__ import annotations

from archforge.core.interaction import HUD
from archforge.core.modifier_commands import AddSurfaceModifier
from .selection import BrushSpec, SurfaceHit, sculpt_modifier_from_hit
from .mesh import TessellatedPreviewBackend
from .sculpt import SculptedPreviewBackend, apply_brush_modifier
from .picking import raycast_evaluation

LIVE_SCULPT_OPERATIONS=('pull','push','inflate','recess','smooth','crease')


class SculptTransaction:
    """Modal begin/preview/adjust/confirm/cancel transaction for surface sculpting.

    The semantic document is untouched while dragging. Commit is one undoable command.
    """
    def __init__(self, doc, stack, hit: SurfaceHit, brush: BrushSpec,
                 operation: str='pull', amount: float=0.0):
        hit.validate(doc); brush.validate()
        if operation not in LIVE_SCULPT_OPERATIONS:
            raise ValueError(f'live sculpt transaction does not yet support {operation}')
        self.doc,self.stack,self.hit,self.brush=doc,stack,hit,brush
        self.operation=operation;self.amount=float(amount);self.cancelled=False;self.committed=False
        if self.amount<0: raise ValueError('amount must be >= 0')

    def update(self, *, amount=None, radius=None, strength=None, falloff=None):
        if self.cancelled or self.committed: raise RuntimeError('transaction is no longer active')
        if amount is not None:
            amount=float(amount)
            if amount<0: raise ValueError('amount must be >= 0')
            self.amount=amount
        values={'radius':self.brush.radius,'strength':self.brush.strength,'falloff':self.brush.falloff}
        if radius is not None: values['radius']=float(radius)
        if strength is not None: values['strength']=float(strength)
        if falloff is not None: values['falloff']=str(falloff)
        self.brush=BrushSpec(**values);self.brush.validate()
        return HUD({'amount':self.amount,'radius':self.brush.radius,'strength':self.brush.strength})

    def modifier(self):
        return sculpt_modifier_from_hit(self.doc,self.hit,self.brush,self.operation,self.amount)

    def preview_mesh(self):
        """Evaluate current drag state without altering Document or undo history."""
        # Preview on top of already committed modifiers, while keeping
        # the in-progress brush transient until commit.
        body=SculptedPreviewBackend(
            dense_entity_ids={self.hit.owner_id},
            wall_target_step=.15,
        ).evaluate(self.doc).body(self.hit.owner_id)
        raw={
            'operation':self.operation,
            'target':{'owner_id':self.hit.owner_id,'surface_role':self.hit.surface_role,
                      'subregion':{'world_center':list(self.hit.world_point),'radius':self.brush.radius,
                                   'strength':self.brush.strength,'falloff':self.brush.falloff}},
            'params':{'amount':self.amount},'enabled':True,
        }
        return apply_brush_modifier(body.payload,raw)

    def commit(self):
        if self.cancelled: raise RuntimeError('transaction cancelled')
        if self.committed: raise RuntimeError('transaction already committed')
        modifier=self.modifier();self.stack.execute(AddSurfaceModifier(modifier));self.committed=True
        return modifier.id

    def cancel(self):
        if self.committed: raise RuntimeError('cannot cancel committed transaction')
        self.cancelled=True


def begin_sculpt_from_ray(doc, stack, origin, direction, brush: BrushSpec,
                          operation: str='pull', amount: float=0.0,
                          evaluation=None):
    """Bridge a 3D viewport ray directly into a semantic sculpt transaction."""
    if evaluation is None:
        evaluation=TessellatedPreviewBackend().evaluate(doc)
    hit=raycast_evaluation(doc,evaluation,origin,direction)
    if hit is None:
        return None
    return SculptTransaction(doc,stack,hit,brush,operation,amount)
