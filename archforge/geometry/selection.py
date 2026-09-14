from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import math

from archforge.core.modifiers import SurfaceModifier, SurfaceRef
from .surfaces import validate_surface_role
from .surface_frame import project_surface_point

Vec2=Tuple[float,float]; Vec3=Tuple[float,float,float]


def _finite_vec(values,n,name):
    if len(values)!=n or not all(math.isfinite(float(v)) for v in values): raise ValueError(f'{name} must contain {n} finite values')
    return tuple(float(v) for v in values)

@dataclass(frozen=True)
class SurfaceHit:
    """One 3D pick resolved back to stable semantic surface coordinates."""
    owner_id:str
    surface_role:str
    world_point:Vec3
    world_normal:Vec3
    uv:Optional[Vec2]=None

    def validate(self,doc):
        validate_surface_role(doc,self.owner_id,self.surface_role,require_deformable=True)
        _finite_vec(self.world_point,3,'world_point');n=_finite_vec(self.world_normal,3,'world_normal')
        if math.sqrt(sum(v*v for v in n))<=1e-12: raise ValueError('world_normal cannot be zero')
        if self.uv is not None:_finite_vec(self.uv,2,'uv')

@dataclass(frozen=True)
class BrushSpec:
    radius:float
    strength:float=1.0
    falloff:str='smooth'

    def validate(self):
        if not math.isfinite(float(self.radius)) or float(self.radius)<=0:raise ValueError('brush radius must be > 0')
        if not math.isfinite(float(self.strength)) or not 0<=float(self.strength)<=1:raise ValueError('brush strength must be between 0 and 1')
        if self.falloff not in ('constant','linear','smooth','sharp'):raise ValueError('unsupported brush falloff')


def sculpt_modifier_from_hit(doc,hit:SurfaceHit,brush:BrushSpec,operation:str,amount:float,*,order:int=0,name:str='')->SurfaceModifier:
    """Create persistent sculpt intent from a transient viewport hit.

    Intrinsic surface coordinates are authoritative whenever the semantic surface exposes
    a stable frame. In that case the pick's world position is retained only as
    ``world_hint`` for diagnostics/recovery; ``world_center`` is materialized later in an
    evaluation copy. Legacy/unsupported surfaces retain world_center until migrated.
    """
    hit.validate(doc);brush.validate()
    amount=float(amount)
    if not math.isfinite(amount) or amount<0:raise ValueError('sculpt amount must be >= 0')
    subregion={'world_hint':list(hit.world_point),'radius':float(brush.radius),'falloff':brush.falloff,'strength':float(brush.strength)}
    uv=hit.uv if hit.uv is not None else project_surface_point(doc,hit.owner_id,hit.surface_role,hit.world_point)
    if uv is not None:
        subregion['uv_center']=list(uv);subregion['coord_system']='surface_uv'
    else:
        subregion['world_center']=list(hit.world_point);subregion['coord_system']='world_legacy'
    return SurfaceModifier(SurfaceRef(hit.owner_id,hit.surface_role,subregion),operation,{'amount':amount},name=name,order=order)
