from __future__ import annotations

from dataclasses import dataclass
from math import dist
from typing import Dict, List, Tuple

Point3 = Tuple[float, float, float]


@dataclass(frozen=True)
class StructuralNode:
    """One derived analysis node.

    Nodes are not authoritative Document entities. They are regenerated from the
    current building geometry so manual edits and AI edits always feed the same
    structural interpretation.
    """
    index: int
    point: Point3


@dataclass(frozen=True)
class StructuralMember:
    """One derived member backed by exactly one authoritative building entity."""
    entity_id: str
    kind: str
    start_node: int
    end_node: int
    role: str
    construction: str
    section: str


@dataclass(frozen=True)
class StructuralGraph:
    nodes: Tuple[StructuralNode, ...]
    members: Tuple[StructuralMember, ...]

    def member(self, entity_id: str) -> StructuralMember:
        for member in self.members:
            if member.entity_id == entity_id:
                return member
        raise KeyError(entity_id)

    def degree(self, node_index: int) -> int:
        node_index = int(node_index)
        return sum(
            1
            for member in self.members
            if member.start_node == node_index or member.end_node == node_index
        )


def build_structural_graph(doc, tolerance: float = 1e-5) -> StructuralGraph:
    """Derive a node/member graph from structural-role Columns and Beams.

    The graph is intentionally solver-neutral. It does not invent supports, loads,
    stiffness, releases, or forces. Those are explicit later inputs/results.

    Beam analytical nodes lie on the beam top/level plane. The default Column/Beam
    authoring workflow aligns a column top with that same level plane, so connected
    architectural geometry produces a shared graph node without a shadow model.
    """
    tolerance = float(tolerance)
    if tolerance <= 0:
        raise ValueError('tolerance must be > 0')

    points: List[Point3] = []
    members: List[StructuralMember] = []

    def node_for(point: Point3) -> int:
        p = tuple(float(v) for v in point)
        for i, existing in enumerate(points):
            if dist(existing, p) <= tolerance:
                return i
        points.append(p)
        return len(points) - 1

    for entity_id in sorted(doc.entities):
        entity = doc.entities[entity_id]
        if entity.kind not in ('structural_column', 'structural_beam'):
            continue
        params = entity.params
        if str(params.get('role', 'structural')) != 'structural':
            continue

        if entity.kind == 'structural_column':
            x, y, z = map(float, (params['x'], params['y'], params['z']))
            start = (x, y, z)
            end = (x, y, z + float(params['height']))
        else:
            level_z = float(params['z']) + float(params['height'])
            start = (float(params['x1']), float(params['y1']), level_z)
            end = (float(params['x2']), float(params['y2']), level_z)

        a = node_for(start)
        b = node_for(end)
        if a == b:
            raise ValueError(f'structural member {entity_id} collapses to one node')

        members.append(
            StructuralMember(
                entity_id=str(entity_id),
                kind=str(entity.kind),
                start_node=a,
                end_node=b,
                role=str(params.get('role', 'structural')),
                construction=str(params.get('construction', 'generic')),
                section=str(params.get('section', 'rectangular')),
            )
        )

    nodes = tuple(StructuralNode(index=i, point=point) for i, point in enumerate(points))
    return StructuralGraph(nodes=nodes, members=tuple(members))
