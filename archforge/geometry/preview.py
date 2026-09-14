from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, List, Tuple

from .backend import ContractBackend, GeometryBackend, GeometryBody, GeometryEvaluation, GeometryIssue


Vec3 = Tuple[float, float, float]
Bounds = Tuple[Vec3, Vec3]
ROOM_SLAB_KINDS = {'room_floor', 'room_ceiling', 'room_foundation', 'room_roof'}


@dataclass(frozen=True)
class PreviewPayload:
    primitive: str
    bounds: Bounds


def _bounds(points: Iterable[Vec3]) -> Bounds:
    pts = list(points)
    if not pts:
        raise ValueError('cannot bound empty geometry')
    return (
        tuple(min(p[i] for p in pts) for i in range(3)),
        tuple(max(p[i] for p in pts) for i in range(3)),
    )


def _transform_point(matrix, p: Vec3) -> Vec3:
    x, y, z = p
    return tuple(
        matrix[r][0] * x + matrix[r][1] * y + matrix[r][2] * z + matrix[r][3]
        for r in range(3)
    )


def _box_corners(width, depth, height):
    return [(x, y, z) for x in (0.0, width) for y in (0.0, depth) for z in (0.0, height)]


def _room_slab_payload(doc, node) -> PreviewPayload:
    from archforge.architecture.rooms import find_room_face

    found = find_room_face(doc, node.params['room_signature'])
    if found is None:
        raise ValueError('derived room element has no currently closed room')

    face, base_z = found
    z = float(base_z) + float(node.params.get('offset_z', 0.0))
    thickness = float(node.params['thickness'])
    pts = [(float(x), float(y), z) for x, y in face.polygon]
    return PreviewPayload(
        'polygon_prism',
        _bounds(pts + [(x, y, z + thickness) for x, y, _ in pts]),
    )


def _payload(doc, node) -> PreviewPayload:
    p = node.params
    kind = node.semantic_kind

    if kind in ('box', 'mechanical_part'):
        corners = _box_corners(float(p['width']), float(p['depth']), float(p['height']))
        if node.transform is not None:
            corners = [_transform_point(node.transform, q) for q in corners]
        else:
            angle = math.radians(float(p.get('rotation', 0.0)))
            c, s = math.cos(angle), math.sin(angle)
            ox, oy, oz = float(p['x']), float(p['y']), float(p['z'])
            corners = [
                (ox + c * x - s * y, oy + s * x + c * y, oz + z)
                for x, y, z in corners
            ]
        return PreviewPayload('box', _bounds(corners))

    if kind == 'wall':
        x1, y1, z, x2, y2 = map(float, (p['x1'], p['y1'], p['z'], p['x2'], p['y2']))
        h, t = float(p['height']), float(p['thickness'])
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            raise ValueError('wall has zero length')
        nx, ny = -dy / length * t / 2.0, dx / length * t / 2.0
        footprint = [
            (x1 + nx, y1 + ny, z),
            (x1 - nx, y1 - ny, z),
            (x2 + nx, y2 + ny, z),
            (x2 - nx, y2 - ny, z),
        ]
        return PreviewPayload(
            'wall_prism',
            _bounds(footprint + [(x, y, z + h) for x, y, _ in footprint]),
        )

    if kind == 'pod':
        cx, cy, z = float(p['cx']), float(p['cy']), float(p['floor_level'])
        rx = float(p['diameter_x']) / 2
        ry = float(p['diameter_y']) / 2
        return PreviewPayload(
            'upper_ellipsoid',
            ((cx - rx, cy - ry, z), (cx + rx, cy + ry, z + float(p['height']))),
        )

    if kind in ('floor', 'room'):
        pts = [(float(x), float(y), float(p['z'])) for x, y in p['points']]
        top = float(p['z']) + float(p.get('thickness', p.get('height', 0.0)))
        return PreviewPayload(
            'polygon_prism' if kind == 'floor' else 'room_volume',
            _bounds(pts + [(x, y, top) for x, y, _ in pts]),
        )

    if kind in ROOM_SLAB_KINDS:
        return _room_slab_payload(doc, node)

    raise ValueError(f'preview backend does not support {kind}')


class PreviewBackend(GeometryBackend):
    """Fast viewport geometry; explicitly not evidence of printability."""

    name = 'preview'

    def evaluate_plan(self, doc, plan) -> GeometryEvaluation:
        contract = ContractBackend().evaluate_plan(doc, plan)
        issues = list(contract.issues)
        bodies: List[GeometryBody] = []
        for node in plan.geometry_nodes():
            base = contract.body(node.entity_id)
            try:
                payload = _payload(doc, node)
                bodies.append(
                    GeometryBody(
                        node.entity_id,
                        node.semantic_kind,
                        base.surface_keys,
                        base.modifier_ids,
                        payload,
                        quality='preview',
                        modifiers_applied=False,
                    )
                )
            except Exception as exc:
                issues.append(
                    GeometryIssue('error', 'preview_geometry_failed', str(exc), node.entity_id)
                )
        return GeometryEvaluation(self.name, tuple(bodies), tuple(issues))
