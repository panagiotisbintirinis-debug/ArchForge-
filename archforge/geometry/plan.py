from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple
import copy

from archforge.core.modifiers import ordered_modifiers, modifier_to_dict
from archforge.kinematics.evaluation import base_part_matrix, evaluate_assembly

Matrix4 = Tuple[Tuple[float,float,float,float],Tuple[float,float,float,float],Tuple[float,float,float,float],Tuple[float,float,float,float]]

NON_GEOMETRY_KINDS = {'mechanical_joint','mechanical_mount'}
FABRICATION_KINDS = {'box','wall','pod','floor','room_floor','mechanical_part'}


@dataclass(frozen=True)
class EvaluationNode:
    entity_id: str
    semantic_kind: str
    params: Dict[str,Any]
    parent_id: Optional[str]
    transform: Optional[Matrix4]
    modifiers: Tuple[Dict[str,Any],...]
    role: str = 'geometry'


@dataclass(frozen=True)
class EvaluationPlan:
    nodes: Tuple[EvaluationNode,...]
    joint_values: Dict[str,float]

    def node(self,entity_id:str)->EvaluationNode:
        for n in self.nodes:
            if n.entity_id==entity_id:return n
        raise KeyError(entity_id)

    def geometry_nodes(self)->Tuple[EvaluationNode,...]:
        return tuple(n for n in self.nodes if n.role=='geometry')


def _mechanical_transforms(doc,joint_values:Mapping[str,float])->Dict[str,Matrix4]:
    parts={eid for eid,e in doc.entities.items() if e.kind=='mechanical_part'}
    incoming={}
    for jid,e in doc.entities.items():
        if e.kind!='mechanical_joint':continue
        child=str(e.params['child_part'])
        if child in incoming:raise ValueError('mechanical part cannot have multiple incoming joints')
        incoming[child]=jid
    roots=sorted(parts-set(incoming))
    transforms:Dict[str,Matrix4]={}
    for root in roots:
        evaluated=evaluate_assembly(doc,root,joint_values)
        for pid,ep in evaluated.items():
            if pid in transforms:raise ValueError('mechanical part reached from multiple assembly roots')
            transforms[pid]=ep.matrix
    unresolved=parts-set(transforms)
    if unresolved:
        # In a valid joint forest this means a cycle or otherwise disconnected cyclic component.
        raise ValueError('unresolved mechanical parts in kinematic evaluation: '+', '.join(sorted(unresolved)))
    for pid in parts:
        transforms.setdefault(pid,base_part_matrix(doc.get(pid).params))
    return transforms


def build_evaluation_plan(doc,joint_values:Optional[Mapping[str,float]]=None)->EvaluationPlan:
    """Compile semantic document state into deterministic backend-neutral geometry intent.

    Order of responsibility is explicit:
      1. semantic entity parameters remain untouched,
      2. kinematic transforms are evaluated separately for rigid mechanical parts,
      3. ordered surface modifiers are attached to their semantic owners,
      4. relationship-only entities (joints/mounts) remain in the plan as metadata nodes.

    The plan is an intermediate representation, not tessellation or boolean geometry.
    A mesh/OCC backend can consume it without changing the architectural source model.
    """
    values={str(k):float(v) for k,v in (joint_values or {}).items()}
    mech=_mechanical_transforms(doc,values)
    nodes:List[EvaluationNode]=[]
    for eid in sorted(doc.entities):
        e=doc.get(eid)
        mods=tuple(modifier_to_dict(m) for m in ordered_modifiers(doc,eid))
        transform=mech.get(eid)
        role='relationship' if e.kind in NON_GEOMETRY_KINDS else 'geometry'
        nodes.append(EvaluationNode(
            entity_id=eid,
            semantic_kind=e.kind,
            params=copy.deepcopy(e.params),
            parent_id=e.parent_id,
            transform=transform,
            modifiers=mods,
            role=role,
        ))
    return EvaluationPlan(tuple(nodes),values)


def fabrication_candidates(plan:EvaluationPlan)->Tuple[EvaluationNode,...]:
    """Return entities eligible to enter a future fabrication geometry pipeline.

    Eligibility is intentionally weaker than 'printable'. Watertightness, minimum wall
    thickness, manifold validation and final STL export belong to the evaluated geometry
    backend and must pass before an object can be called 3D-printable.
    """
    return tuple(n for n in plan.nodes if n.role=='geometry' and n.semantic_kind in FABRICATION_KINDS)
