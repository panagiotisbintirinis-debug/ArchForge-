from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from archforge.core.model import Entity
from .biospectre import all_pod_junctions


@dataclass(frozen=True)
class JunctionIntentResult:
    active_ids: Tuple[str,...]
    created_ids: Tuple[str,...]
    dormant_ids: Tuple[str,...]


def _existing_by_key(doc, key: str):
    matches=[e for e in doc.entities.values()
             if e.kind=='organic_junction' and e.params.get('junction_key')==key]
    if len(matches)>1:
        raise ValueError(f'duplicate organic junction identity for {key}')
    return matches[0] if matches else None


def _sync_dependencies(doc, junction_id: str, source_ids):
    # Dependency edges are dirty-propagation relationships, not geometry ownership.
    # The semantic junction entity survives temporary separation so its identity can heal.
    for deps in doc.dependencies.values():
        deps.discard(junction_id)
    for source_id in source_ids:
        if source_id in doc.entities:
            doc.add_dependency(source_id,junction_id)


def infer_organic_junctions(doc) -> JunctionIntentResult:
    """Reconcile transient pod overlap into persistent semantic organic junction entities.

    Junction identity is keyed by the stable source entity pair, never by generated mesh
    triangles. When the sources stop intersecting the entity becomes dormant rather than
    being destroyed, allowing semantic/material data to survive later reconnection.
    Geometry backends recompute the actual planar section from the live source shapes.
    """
    current=all_pod_junctions(doc)
    active=[];created=[]

    for key in sorted(current):
        raw=current[key]
        source_ids=tuple(sorted((str(raw['pod_a']),str(raw['pod_b']))))
        entity=_existing_by_key(doc,key)
        params={
            'junction_key':key,
            'component_a':source_ids[0],
            'component_b':source_ids[1],
            'status':'active',
            'auto_inferred':True,
        }
        if entity is None:
            entity=Entity('organic_junction',params,name='Auto Organic Junction')
            doc.add(entity);created.append(entity.id)
        else:
            changes={k:v for k,v in params.items() if entity.params.get(k)!=v}
            if changes:doc.update(entity.id,changes)
        _sync_dependencies(doc,entity.id,source_ids)
        active.append(entity.id)

    active_set=set(active);dormant=[]
    for entity in list(doc.entities.values()):
        if entity.kind!='organic_junction' or entity.id in active_set:
            continue
        if entity.params.get('status')!='dormant':
            doc.update(entity.id,{'status':'dormant'})
        source_ids=(entity.params.get('component_a'),entity.params.get('component_b'))
        _sync_dependencies(doc,entity.id,source_ids)
        dormant.append(entity.id)

    return JunctionIntentResult(tuple(active),tuple(created),tuple(sorted(dormant)))
