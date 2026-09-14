from __future__ import annotations

from itertools import product
from typing import Dict, List, Mapping, Optional, Tuple

from .evaluation import evaluate_assembly, evaluated_part_bounds

Vec3 = Tuple[float,float,float]


def _assembly_joint_ids(doc, root_part_id: str) -> List[str]:
    evaluated = evaluate_assembly(doc, root_part_id)
    parts = set(evaluated)
    return sorted(
        jid for jid,e in doc.entities.items()
        if e.kind=='mechanical_joint' and e.params.get('parent_part') in parts and e.params.get('child_part') in parts
    )


def _sample_values(params: Mapping[str,object], samples_per_joint: int) -> List[float]:
    jtype=str(params['joint_type'])
    if jtype=='fixed':return [0.0]
    n=int(samples_per_joint)
    if n<2:raise ValueError('samples_per_joint must be >= 2')
    lo=float(params['min_value']);hi=float(params['max_value']);current=float(params.get('value',0.0))
    if lo>hi:raise ValueError('joint minimum exceeds maximum')
    if abs(hi-lo)<=1e-12:return [lo]
    values=[lo+(hi-lo)*i/(n-1) for i in range(n)]
    if all(abs(current-v)>1e-12 for v in values):values.append(current)
    return sorted(set(values))


def sampled_motion_envelope(doc, root_part_id: str, samples_per_joint: int=5, clearance: float=0.0, max_states: int=4096) -> Tuple[Vec3,Vec3]:
    """Approximate the swept assembly envelope by sampling joint ranges.

    This is intentionally named *sampled*: it is a conservative workflow aid only when
    sampling is dense enough for the mechanism. It is not a collision solver or exact
    swept-volume boolean. The later geometry/physics backend may replace it with exact
    swept solids while keeping this API's semantic inputs.
    """
    clearance=float(clearance)
    if clearance<0:raise ValueError('clearance must be >= 0')
    if int(max_states)<1:raise ValueError('max_states must be >= 1')
    joint_ids=_assembly_joint_ids(doc,root_part_id)
    value_lists=[_sample_values(doc.get(jid).params,samples_per_joint) for jid in joint_ids]
    state_count=1
    for values in value_lists:state_count*=len(values)
    if state_count>int(max_states):
        raise ValueError(f'motion sampling requires {state_count} states; limit is {int(max_states)}')
    combinations=product(*value_lists) if value_lists else [()]
    global_lo=[float('inf')]*3;global_hi=[float('-inf')]*3
    for combo in combinations:
        overrides=dict(zip(joint_ids,combo))
        evaluated=evaluate_assembly(doc,root_part_id,overrides)
        for ep in evaluated.values():
            lo,hi=evaluated_part_bounds(doc,ep)
            for i in range(3):
                global_lo[i]=min(global_lo[i],lo[i]);global_hi[i]=max(global_hi[i],hi[i])
    return tuple(v-clearance for v in global_lo),tuple(v+clearance for v in global_hi)


def sampled_joint_states(doc, root_part_id: str, samples_per_joint: int=5, max_states: int=4096) -> List[Dict[str,float]]:
    """Return deterministic sampled joint-value states for previews/tests."""
    joint_ids=_assembly_joint_ids(doc,root_part_id)
    value_lists=[_sample_values(doc.get(jid).params,samples_per_joint) for jid in joint_ids]
    count=1
    for values in value_lists:count*=len(values)
    if count>int(max_states):raise ValueError(f'motion sampling requires {count} states; limit is {int(max_states)}')
    return [dict(zip(joint_ids,combo)) for combo in (product(*value_lists) if value_lists else [()])]
