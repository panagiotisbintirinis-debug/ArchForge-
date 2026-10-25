"""Light emitters belong to the placed library object, never a second entity.

glTF KHR_lights_punctual uses metres, linear RGB, candela and cone half-angles
in radians: https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_lights_punctual
This is the existing viewport's analytic point/spot lighting, not IES photometry.
"""
from __future__ import annotations

import copy
import math


def _number(value, minimum=0):
    value = float(value)
    if not math.isfinite(value) or value < minimum:
        raise ValueError('invalid library light value')
    return value


def _vector(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError('library light needs a 3-vector')
    return [_number(v, -math.inf) for v in value]


def validate_sources(sources):
    if not isinstance(sources, list) or len(sources) > 64:
        raise ValueError('library lights must be a list of at most 64 emitters')
    result = copy.deepcopy(sources)
    for source in result:
        if not isinstance(source, dict) or source.get('kind') not in ('point', 'spot'):
            raise ValueError('library lights support point and spot emitters')
        source['position'] = _vector(source['position'])
        source['direction'] = _vector(source.get('direction', [0,0,-1]))
        if math.sqrt(sum(v*v for v in source['direction'])) <= 1e-12:
            raise ValueError('library light direction is zero')
        source['intensity_cd'] = _number(source['intensity_cd'])
        source['range_m'] = _number(source.get('range_m', 0))
        source['color'] = _vector(source.get('color', [1,1,1]))
        if min(source['color']) < 0 or max(source['color']) > 1:
            raise ValueError('library light color must be linear RGB in [0,1]')
        if source['kind'] == 'spot':
            outer = _number(source.get('outer_cone_rad', math.pi/4))
            inner = _number(source.get('inner_cone_rad', 0))
            if not 0 <= inner < outer <= math.pi/2:
                raise ValueError('invalid library spotlight cones')
            source.update(outer_cone_rad=outer, inner_cone_rad=inner)
    return result


def read_gltf_lighting(path):
    """Read lights in the active scene with exactly the geometry reader's transforms."""
    from archforge.library.gltf import _load, _matrix, _mul, _apply
    doc, _buffers = _load(path)
    definitions = doc.get('extensions', {}).get('KHR_lights_punctual', {}).get('lights', [])
    sources = []
    identity = [[int(i == j) for j in range(4)] for i in range(4)]
    def zup(v): return [v[0], -v[2], v[1]]
    def visit(index, parent):
        node = doc['nodes'][index]
        matrix = _mul(parent, _matrix(node))
        binding = node.get('extensions', {}).get('KHR_lights_punctual')
        if binding is not None:
            light = definitions[binding['light']]
            if light['type'] not in ('point', 'spot'):
                raise ValueError('fixture import supports point/spot lights; directional light is not a fixture')
            origin = _apply(matrix, [0,0,0]); end = _apply(matrix, [0,0,-1])
            source = dict(kind=light['type'], position=zup(origin),
                          direction=zup([end[i]-origin[i] for i in range(3)]),
                          intensity_cd=light.get('intensity',1), color=light.get('color',[1,1,1]),
                          range_m=light.get('range',0), provenance=copy.deepcopy(light.get('extras',{})))
            if light['type']=='spot':
                cone = light.get('spot',{})
                source.update(inner_cone_rad=cone.get('innerConeAngle',0),
                              outer_cone_rad=cone.get('outerConeAngle',math.pi/4))
            sources.append(source)
        for child in node.get('children',[]): visit(child,matrix)
    roots = (doc.get('scenes') or [{'nodes':list(range(len(doc.get('nodes',[]))))}])[doc.get('scene',0)].get('nodes',[])
    for root in roots: visit(root,identity)
    emissive = {}
    for mat in doc.get('materials',[]):
        rgb = mat.get('emissiveFactor',[0,0,0])
        if mat.get('name') and any(float(c)>0 for c in rgb):
            emissive[mat['name']] = '#'+''.join(f'{round(max(0,min(1,float(c)))**(1/2.2)*255):02x}' for c in rgb)
    return dict(sources=validate_sources(sources), emissive_materials=emissive)


def instance_light_specs(entity):
    """Derive world-space emitters from the same transform used by its mesh."""
    if entity.kind != 'library_object' or not entity.visible:
        return []
    p = entity.params
    sources = p.get('light_sources',[])
    if not sources or not p.get('light_enabled',1) or float(p.get('light_level',1)) <= 0:
        return []
    native = p.get('source_size')
    if not native:
        from archforge.library.assets import load_asset
        record = load_asset(str(p.get('asset','')))
        if not record: return []
        native = record['size']
    scales = [float(p[k])/float(v) for k,v in zip(('width','depth','height'),native)]
    if float(p.get('mirror',0)) >= .5: scales[0] *= -1
    angle=math.radians(float(p.get('rotation',0))); c,s=math.cos(angle),math.sin(angle)
    def vector(v):
        x,y,z=[a*b for a,b in zip(v,scales)]
        return [c*x-s*y,s*x+c*y,z]
    def point(v): return [a+float(p.get(k,0)) for a,k in zip(vector(v),('x','y','z'))]
    specs=[]
    for i,source in enumerate(sources):
        pos=point(source['position']); direction=vector(source.get('direction',[0,0,-1]))
        length=math.sqrt(sum(v*v for v in direction))
        spec=dict(id=f'{entity.id}:light:{i}', owner_id=entity.id,kind=source['kind'],
                  position=pos, intensity=float(source['intensity_cd'])*float(p.get('light_level',1)),
                  range=source.get('range_m',0), shadows=bool(p.get('light_shadows',1)),
                  enabled=True,color=list(source.get('color',[1,1,1])))
        if p.get('light_kelvin'):
            spec.pop('color'); spec['kelvin']=float(p['light_kelvin'])
        if source['kind']=='spot':
            outer=float(source.get('outer_cone_rad',math.pi/4));inner=float(source.get('inner_cone_rad',0))
            spec.update(target=[pos[j]+direction[j]/length for j in range(3)],angle_deg=math.degrees(outer),
                        penumbra=1-inner/outer)
        specs.append(spec)
    return specs
