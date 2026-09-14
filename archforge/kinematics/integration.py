from __future__ import annotations

from typing import Optional

from archforge.core.modifiers import SurfaceModifier, SurfaceRef
from .model import mechanism_envelope, validate_mount


def cavity_modifier_for_mount(doc, mount_id: str, extra_clearance: float = 0.0, order: int = 0) -> SurfaceModifier:
    """Build a non-destructive sculptural cavity request for an embedded mechanism.

    The result does not boolean-cut geometry immediately. It records a semantic cut
    modifier against the architectural host surface, carrying the mechanism envelope
    and mount identity so a future geometry backend can regenerate the cavity whenever
    the mechanism or wall changes.
    """
    if mount_id not in doc.entities:
        raise KeyError(mount_id)
    mount = doc.get(mount_id)
    validate_mount(doc, mount)
    extra_clearance = float(extra_clearance)
    if extra_clearance < 0:
        raise ValueError('extra_clearance must be >= 0')
    p = mount.params
    clearance = float(p.get('clearance',0.0)) + extra_clearance
    lo, hi = mechanism_envelope(doc, p['part_id'], clearance=clearance)
    target = SurfaceRef(
        p['host_id'],
        p['surface_role'],
        {
            'selector':'mechanism_cavity',
            'mount_id':mount_id,
            'envelope_min':list(lo),
            'envelope_max':list(hi),
        },
    )
    return SurfaceModifier(
        target=target,
        operation='cut',
        params={
            'mode':'mechanism_clearance',
            'mount_id':mount_id,
            'clearance':clearance,
            'embed_depth':float(p.get('embed_depth',0.0)),
        },
        name=f'Cavity for {mount.name or mount.id[:8]}',
        order=int(order),
    )


def ensure_mount_cavity(doc, mount_id: str, extra_clearance: float = 0.0, order: int = 0) -> str:
    """Create or refresh the sculpt modifier linked to a mechanical mount.

    Existing linked cavity modifiers are updated in-place rather than duplicated.
    """
    fresh = cavity_modifier_for_mount(doc,mount_id,extra_clearance=extra_clearance,order=order)
    existing = None
    for mid,mod in doc.surface_modifiers.items():
        if mod.operation=='cut' and mod.params.get('mode')=='mechanism_clearance' and mod.params.get('mount_id')==mount_id:
            existing = mid
            break
    if existing is None:
        return doc.add_surface_modifier(fresh)
    doc.update_surface_modifier(
        existing,
        target=fresh.target,
        params=fresh.params,
        name=fresh.name,
        order=fresh.order,
        enabled=True,
    )
    return existing
