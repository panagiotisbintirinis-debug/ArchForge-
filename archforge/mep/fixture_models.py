"""A library housing on an electrical point: one persistent entity and one control state.

Only ``fixture_asset`` is stored. Mesh and emitters share the derived transform;
the temporary library-shaped entity below is never inserted into the Document.
Reference emitter data remain visual DESIGN_DEFAULT, never electrical loads.
"""
import copy
import math

from archforge.core.model import Entity
from archforge.library.assets import load_asset
from archforge.library.lighting import capabilities, instance_light_specs


def light_mount_z(doc, params):
    """Existing electrical light height, bounded below the walls as in the PBR light path."""
    from archforge.mep.electrical import mount_z
    z = float(mount_z(doc, params))
    floor = float(params.get('z', 0))
    tops = [float(e.params.get('z', 0)) + float(e.params.get('height', 0))
            for e in doc.entities.values() if e.kind == 'wall'
            and abs(float(e.params.get('z', 0))-floor) <= .05]
    # Keep the pre-existing ceiling-light clearance, not an engineering mounting rule.
    return min(z, max(tops)-.05) if tops else z


def model_record(entity):
    if entity.kind != 'electrical_point' or not entity.params.get('fixture_asset'):
        return None
    from archforge.mep.lighting import is_luminaire, LINE_TYPES
    if not is_luminaire(entity) or entity.params.get('point_type') in LINE_TYPES:
        return None
    r = load_asset(str(entity.params['fixture_asset']))
    return r if r and r.get('lights') else None


def model_capabilities(entity):
    record = model_record(entity)
    if record is None:
        return None
    proxy = Entity('library_object', {'asset': record['id'], 'light_sources': record['lights']})
    return capabilities(proxy)


def attached_instance(doc, entity):
    """Transient render description, sharing the electrical point's ID, never a second design object."""
    r = model_record(entity)
    if r is None:
        return None
    p = entity.params
    w, d, h = map(float, r['size'])
    z = light_mount_z(doc, p)
    mount = (r.get('light_capabilities') or {}).get('mount')
    if mount == 'ceiling':
        z -= h                              # housing top meets the existing electrical mount
    elif mount == 'wall':
        z -= h/2                            # housing centre meets the existing electrical mount
    q = dict(asset=r['id'], source_size=[w,d,h], width=w,depth=d,height=h,
             x=float(p['x']),y=float(p['y']),z=z,rotation=float(p.get('rotation',0)),
             light_sources=copy.deepcopy(r['lights']), light_level=float(p.get('dim_level',1)),
             light_enabled=float(p.get('light_on',1)),light_shadows=1)
    if p.get('kelvin'):
        q['light_kelvin'] = float(p['kelvin'])
    if model_capabilities(entity)['aimable']:
        q.update({k:p[k] for k in ('aim_tilt_deg','aim_azimuth_deg') if k in p})
    if p.get('beam_deg'):
        for source in q['light_sources']:
            if source['kind'] == 'spot':
                ratio=source.get('inner_cone_rad',0)/source['outer_cone_rad']
                source['outer_cone_rad']=math.radians(float(p['beam_deg'])/2)
                source['inner_cone_rad']=source['outer_cone_rad']*ratio
    if p.get('lumen'):
        # The same uniform point/cone approximation already used by mep.lighting.
        flux=sum(float(s['intensity_cd'])*(4*math.pi if s['kind']=='point' else
                 2*math.pi*(1-math.cos(s['outer_cone_rad']))) for s in q['light_sources'])
        if flux>0:
            for source in q['light_sources']:
                source['intensity_cd'] *= float(p['lumen'])/flux
    return Entity('library_object',q,id=entity.id,name=entity.name,visible=entity.visible)


def attached_light_specs(doc, entity):
    instance = attached_instance(doc, entity)
    if instance is None:
        return []
    specs = instance_light_specs(instance)
    if model_capabilities(entity)['aimable'] and entity.params.get('direction') == 'up':
        for spec in specs:
            if 'target' in spec:
                spec['target'][2]=spec['position'][2]+abs(spec['target'][2]-spec['position'][2])
    return specs
