from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

Matrix4 = Tuple[Tuple[float,float,float,float],Tuple[float,float,float,float],Tuple[float,float,float,float],Tuple[float,float,float,float]]
Vec3 = Tuple[float,float,float]


def identity_matrix() -> Matrix4:
    return ((1.0,0.0,0.0,0.0),(0.0,1.0,0.0,0.0),(0.0,0.0,1.0,0.0),(0.0,0.0,0.0,1.0))


def multiply(a: Matrix4, b: Matrix4) -> Matrix4:
    return tuple(tuple(sum(a[r][k]*b[k][c] for k in range(4)) for c in range(4)) for r in range(4))  # type: ignore[return-value]


def translation_matrix(x: float,y: float,z: float) -> Matrix4:
    return ((1.0,0.0,0.0,float(x)),(0.0,1.0,0.0,float(y)),(0.0,0.0,1.0,float(z)),(0.0,0.0,0.0,1.0))


def rotation_z_matrix(angle_deg: float) -> Matrix4:
    a=radians(float(angle_deg));c=cos(a);s=sin(a)
    return ((c,-s,0.0,0.0),(s,c,0.0,0.0),(0.0,0.0,1.0,0.0),(0.0,0.0,0.0,1.0))


def axis_rotation_matrix(axis: Sequence[float], angle_deg: float) -> Matrix4:
    x,y,z=(float(v) for v in axis);n=(x*x+y*y+z*z)**.5
    if n<=1e-12:raise ValueError('rotation axis cannot be zero')
    x,y,z=x/n,y/n,z/n;a=radians(float(angle_deg));c=cos(a);s=sin(a);t=1.0-c
    return (
        (t*x*x+c,t*x*y-s*z,t*x*z+s*y,0.0),
        (t*x*y+s*z,t*y*y+c,t*y*z-s*x,0.0),
        (t*x*z-s*y,t*y*z+s*x,t*z*z+c,0.0),
        (0.0,0.0,0.0,1.0),
    )


def transform_point(m: Matrix4, p: Sequence[float]) -> Vec3:
    x,y,z=(float(v) for v in p)
    return (
        m[0][0]*x+m[0][1]*y+m[0][2]*z+m[0][3],
        m[1][0]*x+m[1][1]*y+m[1][2]*z+m[1][3],
        m[2][0]*x+m[2][1]*y+m[2][2]*z+m[2][3],
    )


def transform_vector(m: Matrix4, v: Sequence[float]) -> Vec3:
    x,y,z=(float(q) for q in v)
    return (
        m[0][0]*x+m[0][1]*y+m[0][2]*z,
        m[1][0]*x+m[1][1]*y+m[1][2]*z,
        m[2][0]*x+m[2][1]*y+m[2][2]*z,
    )


def base_part_matrix(params: Mapping[str,object]) -> Matrix4:
    return multiply(translation_matrix(float(params['x']),float(params['y']),float(params['z'])),rotation_z_matrix(float(params.get('rotation',0.0))))


def joint_delta_matrix(params: Mapping[str,object], value: Optional[float]=None) -> Matrix4:
    from .model import clamp_joint_value
    jtype=str(params['joint_type']);v=float(params.get('value',0.0)) if value is None else clamp_joint_value(dict(params),float(value))
    anchor=tuple(float(q) for q in params.get('anchor',(0,0,0)));axis=tuple(float(q) for q in params.get('axis',(0,0,1)))
    if jtype=='fixed':return identity_matrix()
    if jtype=='prismatic':
        n=(axis[0]**2+axis[1]**2+axis[2]**2)**.5
        if n<=1e-12:raise ValueError('joint axis cannot be zero')
        return translation_matrix(axis[0]/n*v,axis[1]/n*v,axis[2]/n*v)
    if jtype=='revolute':
        return multiply(translation_matrix(*anchor),multiply(axis_rotation_matrix(axis,v),translation_matrix(-anchor[0],-anchor[1],-anchor[2])))
    raise ValueError('unsupported joint type')


@dataclass(frozen=True)
class EvaluatedPart:
    part_id: str
    matrix: Matrix4
    base_matrix: Matrix4
    accumulated_delta: Matrix4
    parent_part: Optional[str] = None
    joint_id: Optional[str] = None


def _incoming_joints(doc) -> Dict[str,str]:
    incoming:Dict[str,str]={}
    for jid,e in doc.entities.items():
        if e.kind!='mechanical_joint':continue
        child=str(e.params['child_part'])
        if child in incoming:raise ValueError('mechanical part cannot have multiple incoming joints')
        incoming[child]=jid
    return incoming


def _detect_cycles(doc, incoming: Mapping[str,str]) -> None:
    for pid,e in doc.entities.items():
        if e.kind!='mechanical_part':continue
        seen=set();cur=pid
        while cur in incoming:
            if cur in seen:raise ValueError('kinematic joint cycle detected')
            seen.add(cur);j=doc.get(incoming[cur]);cur=str(j.params['parent_part'])


def evaluate_assembly(doc, root_part_id: str, joint_values: Optional[Mapping[str,float]]=None) -> Dict[str,EvaluatedPart]:
    """Evaluate rigid transforms for a joint tree without mutating semantic entities.

    Mechanical-part positions describe the rest/world pose. Joint anchor and axis are
    expressed in that same rest/world frame. Parent motion is accumulated and then each
    joint delta is applied to the child and all descendants. This deliberately separates
    kinematic preview/evaluation from editing the source-of-truth model.
    """
    if root_part_id not in doc.entities or doc.get(root_part_id).kind!='mechanical_part':raise ValueError('root must be a mechanical_part')
    incoming=_incoming_joints(doc);_detect_cycles(doc,incoming);joint_values=joint_values or {}
    if root_part_id in incoming:raise ValueError('requested assembly root has an incoming joint')
    children:Dict[str,List[str]]={}
    for jid,e in doc.entities.items():
        if e.kind=='mechanical_joint':children.setdefault(str(e.params['parent_part']),[]).append(jid)
    out:Dict[str,EvaluatedPart]={}
    def walk(pid:str,parent_delta:Matrix4,parent_part:Optional[str]=None,joint_id:Optional[str]=None):
        part=doc.get(pid);base=base_part_matrix(part.params);matrix=multiply(parent_delta,base)
        out[pid]=EvaluatedPart(pid,matrix,base,parent_delta,parent_part,joint_id)
        for jid in children.get(pid,()):
            j=doc.get(jid);value=joint_values.get(jid,float(j.params.get('value',0.0)))
            delta=joint_delta_matrix(j.params,value)
            walk(str(j.params['child_part']),multiply(parent_delta,delta),pid,jid)
    walk(root_part_id,identity_matrix())
    return out


def evaluated_part_bounds(doc, evaluated: EvaluatedPart) -> Tuple[Vec3,Vec3]:
    p=doc.get(evaluated.part_id).params;w=float(p['width']);d=float(p['depth']);h=float(p['height'])
    corners=[(sx*w/2,sy*d/2,z) for sx in (-1,1) for sy in (-1,1) for z in (0.0,h)]
    pts=[transform_point(evaluated.matrix,q) for q in corners]
    return tuple(min(q[i] for q in pts) for i in range(3)),tuple(max(q[i] for q in pts) for i in range(3))


def evaluated_mechanism_envelope(doc, root_part_id: str, joint_values: Optional[Mapping[str,float]]=None, clearance: float=0.0) -> Tuple[Vec3,Vec3]:
    clearance=float(clearance)
    if clearance<0:raise ValueError('clearance must be >= 0')
    evaluated=evaluate_assembly(doc,root_part_id,joint_values)
    bounds=[evaluated_part_bounds(doc,e) for e in evaluated.values()]
    lo=tuple(min(b[0][i] for b in bounds)-clearance for i in range(3));hi=tuple(max(b[1][i] for b in bounds)+clearance for i in range(3))
    return lo,hi
