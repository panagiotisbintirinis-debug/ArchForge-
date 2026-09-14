from __future__ import annotations

from archforge.core.modifiers import SurfaceModifier, SurfaceRef
from .model import mechanism_envelope, validate_mount
from .motion import sampled_motion_envelope


def cavity_modifier_for_mount(doc, mount_id: str, extra_clearance: float = 0.0, order: int = 0, *, include_motion: bool = True, samples_per_joint: int = 5, max_states: int = 4096) -> SurfaceModifier:
    """Build a non-destructive cavity request for an embedded mechanism.

    By default the cavity is based on a sampled swept envelope over joint limits rather
    than only the stored/rest pose. This is intentionally an approximation until an exact
    swept-solid backend exists; the semantic mount and joint limits remain the source of
    truth so the implementation can later be upgraded without changing project intent.
    """
    if mount_id not in doc.entities:raise KeyError(mount_id)
    mount=doc.get(mount_id);validate_mount(doc,mount)
    extra_clearance=float(extra_clearance)
    if extra_clearance<0:raise ValueError('extra_clearance must be >= 0')
    p=mount.params;clearance=float(p.get('clearance',0.0))+extra_clearance
    if include_motion:
        lo,hi=sampled_motion_envelope(doc,p['part_id'],samples_per_joint=samples_per_joint,clearance=clearance,max_states=max_states)
        envelope_mode='sampled_motion'
    else:
        lo,hi=mechanism_envelope(doc,p['part_id'],clearance=clearance);envelope_mode='rest_pose'
    target=SurfaceRef(p['host_id'],p['surface_role'],{
        'selector':'mechanism_cavity','mount_id':mount_id,
        'envelope_min':list(lo),'envelope_max':list(hi),
    })
    return SurfaceModifier(
        target=target,operation='cut',
        params={
            'mode':'mechanism_clearance','mount_id':mount_id,'clearance':clearance,
            'embed_depth':float(p.get('embed_depth',0.0)),'envelope_mode':envelope_mode,
            'samples_per_joint':int(samples_per_joint) if include_motion else 0,
        },
        name=f'Cavity for {mount.name or mount.id[:8]}',order=int(order),
    )


def ensure_mount_cavity(doc, mount_id: str, extra_clearance: float = 0.0, order: int = 0, *, include_motion: bool = True, samples_per_joint: int = 5, max_states: int = 4096) -> str:
    """Create or refresh the sculpt modifier linked to a mechanical mount."""
    fresh=cavity_modifier_for_mount(doc,mount_id,extra_clearance=extra_clearance,order=order,include_motion=include_motion,samples_per_joint=samples_per_joint,max_states=max_states)
    existing=None
    for mid,mod in doc.surface_modifiers.items():
        if mod.operation=='cut' and mod.params.get('mode')=='mechanism_clearance' and mod.params.get('mount_id')==mount_id:
            existing=mid;break
    if existing is None:return doc.add_surface_modifier(fresh)
    doc.update_surface_modifier(existing,target=fresh.target,params=fresh.params,name=fresh.name,order=fresh.order,enabled=True)
    return existing
