from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
import copy

from archforge.core.modifiers import ordered_modifiers, modifier_to_dict
from archforge.kinematics.evaluation import base_part_matrix, evaluate_assembly

Matrix4 = Tuple[Tuple[float,float,float,float],Tuple[float,float,float,float],Tuple[float,float,float,float],Tuple[float,float,float,float]]

NON_GEOMETRY_KINDS = {'mechanical_joint','mechanical_mount','door','window'}
FABRICATION_KINDS = {'box','wall','pod','mesh','floor','room_floor','mechanical_part'}


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
        raise ValueError('unresolved mechanical parts in kinematic evaluation: '+', '.join(sorted(unresolved)))
    for pid in parts:
        transforms.setdefault(pid,base_part_matrix(doc.get(pid).params))
    return transforms


def _modifier_for_evaluation(doc,modifier):
    """Return backend-neutral modifier intent with derived caches refreshed."""
    if modifier.operation=='cut' and modifier.params.get('mode')=='mechanism_clearance':
        mount_id=modifier.params.get('mount_id') or modifier.target.subregion.get('mount_id')
        if mount_id in doc.entities and doc.get(mount_id).kind=='mechanical_mount':
            from archforge.kinematics.integration import cavity_modifier_for_mount
            mount=doc.get(mount_id)
            base_clearance=float(mount.params.get('clearance',0.0))
            stored_clearance=float(modifier.params.get('clearance',base_clearance))
            extra=max(0.0,stored_clearance-base_clearance)
            include_motion=modifier.params.get('envelope_mode','sampled_motion')=='sampled_motion'
            samples=max(1,int(modifier.params.get('samples_per_joint',5) or 5))
            fresh=cavity_modifier_for_mount(doc,mount_id,extra_clearance=extra,order=modifier.order,
                                            include_motion=include_motion,samples_per_joint=samples)
            fresh.id=modifier.id;fresh.enabled=modifier.enabled;fresh.name=modifier.name
            return modifier_to_dict(fresh)
    return modifier_to_dict(modifier)


def _opening_intents_for_host(doc,host_id:str)->List[Dict[str,Any]]:
    """Return deterministic child opening intent using the Document host index."""
    out=[]
    for oid in sorted(doc.opening_ids_for_host(host_id)):
        opening=doc.get(oid)
        if opening.kind not in ('door','window') or opening.parent_id!=host_id:
            continue
        intent=copy.deepcopy(opening.params)
        intent['id']=opening.id
        intent['kind']=opening.kind
        out.append(intent)
    return out


def build_evaluation_plan(
    doc,
    joint_values:Optional[Mapping[str,float]]=None,
    entity_ids:Optional[Iterable[str]]=None,
)->EvaluationPlan:
    """Compile deterministic geometry intent, optionally for an incremental entity subset.

    ``entity_ids`` is an evaluation filter only. Semantic dependencies remain resolved from
    the live document, so a dirty host can be rebuilt without deep-copying every unrelated
    entity in the model.
    """
    values={str(k):float(v) for k,v in (joint_values or {}).items()}
    selected=None if entity_ids is None else {str(eid) for eid in entity_ids if str(eid) in doc.entities}
    ids=sorted(doc.entities) if selected is None else sorted(selected)

    needs_mechanical=selected is None or any(doc.get(eid).kind=='mechanical_part' for eid in ids)
    mech=_mechanical_transforms(doc,values) if needs_mechanical else {}
    nodes:List[EvaluationNode]=[]
    for eid in ids:
        e=doc.get(eid)
        mods=tuple(_modifier_for_evaluation(doc,m) for m in ordered_modifiers(doc,eid))
        transform=mech.get(eid)
        role='relationship' if e.kind in NON_GEOMETRY_KINDS else 'geometry'
        params=copy.deepcopy(e.params)
        if e.kind in ('wall','pod'):
            openings=_opening_intents_for_host(doc,eid)
            if openings:
                params['_opening_intents']=openings
        nodes.append(EvaluationNode(
            entity_id=eid,
            semantic_kind=e.kind,
            params=params,
            parent_id=e.parent_id,
            transform=transform,
            modifiers=mods,
            role=role,
        ))
    return EvaluationPlan(tuple(nodes),values)


def fabrication_candidates(plan:EvaluationPlan)->Tuple[EvaluationNode,...]:
    return tuple(n for n in plan.nodes if n.role=='geometry' and n.semantic_kind in FABRICATION_KINDS)
