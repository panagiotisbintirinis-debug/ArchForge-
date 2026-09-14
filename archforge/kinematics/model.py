from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

JOINT_TYPES = {'fixed', 'revolute', 'prismatic'}
Vec3 = Tuple[float, float, float]


def _vec3(value, name: str) -> Vec3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f'{name} must be a 3-vector')
    return tuple(float(v) for v in value)


def _unit_axis(value) -> Vec3:
    x, y, z = _vec3(value, 'axis')
    length = (x*x + y*y + z*z) ** 0.5
    if length <= 1e-12:
        raise ValueError('joint axis cannot be zero')
    return (x/length, y/length, z/length)


def validate_part(doc, entity) -> None:
    if entity.kind != 'mechanical_part':
        raise ValueError('expected mechanical_part')
    p = entity.params
    for key in ('x','y','z','width','depth','height','rotation'):
        if key not in p:
            raise ValueError(f'mechanical_part missing {key}')
    for key in ('width','depth','height'):
        if float(p[key]) <= 0:
            raise ValueError(f'{key} must be > 0')


def validate_joint(doc, entity) -> None:
    if entity.kind != 'mechanical_joint':
        raise ValueError('expected mechanical_joint')
    p = entity.params
    jtype = str(p.get('joint_type',''))
    if jtype not in JOINT_TYPES:
        raise ValueError('unsupported joint type')
    parent = str(p.get('parent_part',''))
    child = str(p.get('child_part',''))
    if not parent or not child or parent == child:
        raise ValueError('joint requires two different parts')
    for pid in (parent, child):
        if pid not in doc.entities or doc.get(pid).kind != 'mechanical_part':
            raise ValueError('joint references missing mechanical part')
    _vec3(p.get('anchor',(0,0,0)), 'anchor')
    _unit_axis(p.get('axis',(0,0,1)))
    lo = float(p.get('min_value',0.0))
    hi = float(p.get('max_value',0.0))
    value = float(p.get('value',0.0))
    if lo > hi:
        raise ValueError('joint minimum exceeds maximum')
    if value < lo or value > hi:
        raise ValueError('joint value outside limits')
    if jtype == 'fixed' and (abs(lo) > 1e-12 or abs(hi) > 1e-12 or abs(value) > 1e-12):
        raise ValueError('fixed joint must remain at zero')


def validate_mount(doc, entity) -> None:
    if entity.kind != 'mechanical_mount':
        raise ValueError('expected mechanical_mount')
    p = entity.params
    host = str(p.get('host_id',''))
    part = str(p.get('part_id',''))
    if host not in doc.entities:
        raise ValueError('mount host does not exist')
    if part not in doc.entities or doc.get(part).kind != 'mechanical_part':
        raise ValueError('mount part does not exist')
    role = str(p.get('surface_role',''))
    if not role:
        raise ValueError('mount surface_role is required')
    if float(p.get('clearance',0.0)) < 0:
        raise ValueError('mount clearance must be >= 0')
    if float(p.get('embed_depth',0.0)) < 0:
        raise ValueError('mount embed_depth must be >= 0')


def clamp_joint_value(params: Dict[str, object], value: float) -> float:
    lo = float(params.get('min_value',0.0))
    hi = float(params.get('max_value',0.0))
    if lo > hi:
        raise ValueError('joint minimum exceeds maximum')
    return min(max(float(value), lo), hi)


def joint_state(doc, joint_id: str, value: Optional[float] = None) -> Dict[str, object]:
    e = doc.get(joint_id)
    validate_joint(doc, e)
    p = e.params
    v = float(p.get('value',0.0)) if value is None else clamp_joint_value(p, value)
    axis = _unit_axis(p.get('axis',(0,0,1)))
    anchor = _vec3(p.get('anchor',(0,0,0)), 'anchor')
    jtype = p['joint_type']
    if jtype == 'fixed':
        return {'type':'fixed','anchor':anchor,'axis':axis,'value':0.0,'translation':(0.0,0.0,0.0),'rotation_deg':0.0}
    if jtype == 'prismatic':
        translation = tuple(c*v for c in axis)
        return {'type':jtype,'anchor':anchor,'axis':axis,'value':v,'translation':translation,'rotation_deg':0.0}
    return {'type':jtype,'anchor':anchor,'axis':axis,'value':v,'translation':(0.0,0.0,0.0),'rotation_deg':v}


def joint_children(doc, parent_part_id: str) -> List[str]:
    out = []
    for eid, e in doc.entities.items():
        if e.kind == 'mechanical_joint' and e.params.get('parent_part') == parent_part_id:
            out.append(str(e.params.get('child_part')))
    return out


def assembly_parts(doc, root_part_id: str) -> List[str]:
    if root_part_id not in doc.entities or doc.get(root_part_id).kind != 'mechanical_part':
        raise ValueError('root must be a mechanical_part')
    ordered: List[str] = []
    seen: Set[str] = set()
    stack = [root_part_id]
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        ordered.append(pid)
        stack.extend(reversed(joint_children(doc, pid)))
    return ordered


def _part_bounds(params: Dict[str, object]) -> Tuple[Vec3, Vec3]:
    x,y,z = float(params['x']),float(params['y']),float(params['z'])
    w,d,h = float(params['width']),float(params['depth']),float(params['height'])
    a = radians(float(params.get('rotation',0.0)))
    # Axis-aligned XY envelope of a Z-vertical rotated box.
    ex = abs(cos(a))*w/2 + abs(sin(a))*d/2
    ey = abs(sin(a))*w/2 + abs(cos(a))*d/2
    return ((x-ex,y-ey,z),(x+ex,y+ey,z+h))


def mechanism_envelope(doc, root_part_id: str, clearance: float = 0.0) -> Tuple[Vec3, Vec3]:
    clearance = float(clearance)
    if clearance < 0:
        raise ValueError('clearance must be >= 0')
    parts = assembly_parts(doc, root_part_id)
    bounds = [_part_bounds(doc.get(pid).params) for pid in parts]
    lo = tuple(min(b[0][i] for b in bounds)-clearance for i in range(3))
    hi = tuple(max(b[1][i] for b in bounds)+clearance for i in range(3))
    return lo, hi


@dataclass(frozen=True)
class MechanicalMount:
    host_id: str
    part_id: str
    surface_role: str
    clearance: float = 0.01
    embed_depth: float = 0.0

    def to_params(self) -> Dict[str, object]:
        return {
            'host_id': self.host_id,
            'part_id': self.part_id,
            'surface_role': self.surface_role,
            'clearance': float(self.clearance),
            'embed_depth': float(self.embed_depth),
        }
