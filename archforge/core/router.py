from __future__ import annotations

import math
from heapq import heappop, heappush
from itertools import count
from typing import Iterable, Optional, Sequence, Tuple

Vec3 = Tuple[float, float, float]
Voxel = Tuple[int, int, int]
Direction = Tuple[int, int, int]


class MEPPathRouter:
    """Deterministic 3D A* router over structural obstacle voxels."""

    _DIRECTIONS: Tuple[Direction, ...] = (
        (1, 0, 0),
        (-1, 0, 0),
        (0, 1, 0),
        (0, -1, 0),
        (0, 0, 1),
        (0, 0, -1),
    )

    def __init__(
        self,
        doc,
        grid_resolution: float = 0.05,
        *,
        clearance: float = 0.0,
        ignore_entity_ids: Optional[Iterable[str]] = None,
    ):
        self.doc = doc
        self.res = float(grid_resolution)
        if not math.isfinite(self.res) or self.res <= 0.0:
            raise ValueError('grid_resolution must be a finite value > 0')
        self.clearance = float(clearance)
        if not math.isfinite(self.clearance) or self.clearance < 0.0:
            raise ValueError('clearance must be a finite value >= 0')
        self.ignore_entity_ids = {str(eid) for eid in (ignore_entity_ids or ())}
        self.obstacles: set[Voxel] = set()
        self._build_collision_grid()

    def _world_to_grid(self, point: Sequence[float]) -> Voxel:
        if len(point) != 3:
            raise ValueError('route point must have exactly three coordinates')
        values = tuple(float(v) for v in point)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('route coordinates must be finite')
        return tuple(int(round(v / self.res)) for v in values)

    def _grid_to_world(self, voxel: Voxel) -> Vec3:
        return tuple(float(v) * self.res for v in voxel)

    def _grid_range(self, lo: float, hi: float) -> range:
        a = int(math.floor(float(lo) / self.res))
        b = int(math.ceil(float(hi) / self.res))
        return range(a, b + 1)

    def _voxelize_wall(self, params) -> None:
        x1 = float(params['x1'])
        y1 = float(params['y1'])
        x2 = float(params['x2'])
        y2 = float(params['y2'])
        z0 = float(params['z'])
        z1 = z0 + float(params['height'])
        radius = float(params['thickness']) / 2.0 + self.clearance
        min_x, max_x = min(x1, x2) - radius, max(x1, x2) + radius
        min_y, max_y = min(y1, y2) - radius, max(y1, y2) + radius
        dx, dy = x2 - x1, y2 - y1
        length2 = dx * dx + dy * dy
        if length2 <= 1e-18:
            raise ValueError('wall obstacle has zero length')

        for ix in self._grid_range(min_x, max_x):
            x = ix * self.res
            for iy in self._grid_range(min_y, max_y):
                y = iy * self.res
                t = ((x - x1) * dx + (y - y1) * dy) / length2
                t = max(0.0, min(1.0, t))
                qx, qy = x1 + t * dx, y1 + t * dy
                if math.hypot(x - qx, y - qy) > radius + 1e-12:
                    continue
                for iz in self._grid_range(z0 - self.clearance, z1 + self.clearance):
                    self.obstacles.add((ix, iy, iz))

    def _voxelize_box(self, params) -> None:
        cx, cy = float(params['x']), float(params['y'])
        z0 = float(params['z'])
        z1 = z0 + float(params['height'])
        half_w = float(params['width']) / 2.0 + self.clearance
        half_d = float(params['depth']) / 2.0 + self.clearance
        angle = math.radians(float(params.get('rotation', 0.0)))
        c, s = math.cos(angle), math.sin(angle)
        extent_x = abs(c) * half_w + abs(s) * half_d
        extent_y = abs(s) * half_w + abs(c) * half_d

        for ix in self._grid_range(cx - extent_x, cx + extent_x):
            x = ix * self.res
            for iy in self._grid_range(cy - extent_y, cy + extent_y):
                y = iy * self.res
                dx, dy = x - cx, y - cy
                local_x = c * dx + s * dy
                local_y = -s * dx + c * dy
                if abs(local_x) > half_w + 1e-12 or abs(local_y) > half_d + 1e-12:
                    continue
                for iz in self._grid_range(z0 - self.clearance, z1 + self.clearance):
                    self.obstacles.add((ix, iy, iz))

    def _voxelize_pod(self, params) -> None:
        cx, cy = float(params['cx']), float(params['cy'])
        z0 = float(params['floor_level'])
        z1 = z0 + float(params['height'])
        rx = float(params['diameter_x']) / 2.0 + self.clearance
        ry = float(params['diameter_y']) / 2.0 + self.clearance
        angle = math.radians(float(params.get('rotation', 0.0)))
        c, s = math.cos(angle), math.sin(angle)
        extent_x = math.sqrt((rx * c) ** 2 + (ry * s) ** 2)
        extent_y = math.sqrt((rx * s) ** 2 + (ry * c) ** 2)

        for ix in self._grid_range(cx - extent_x, cx + extent_x):
            x = ix * self.res
            for iy in self._grid_range(cy - extent_y, cy + extent_y):
                y = iy * self.res
                dx, dy = x - cx, y - cy
                local_x = c * dx + s * dy
                local_y = -s * dx + c * dy
                if (local_x / rx) ** 2 + (local_y / ry) ** 2 > 1.0 + 1e-12:
                    continue
                for iz in self._grid_range(z0 - self.clearance, z1 + self.clearance):
                    self.obstacles.add((ix, iy, iz))

    def _build_collision_grid(self) -> None:
        """Voxelize structural wall, box and pod volumes from authoritative document state."""
        self.obstacles.clear()
        for eid in sorted(self.doc.entities):
            if eid in self.ignore_entity_ids:
                continue
            entity = self.doc.entities[eid]
            if not entity.visible:
                continue
            if entity.kind == 'wall':
                self._voxelize_wall(entity.params)
            elif entity.kind in ('box', 'mechanical_part'):
                self._voxelize_box(entity.params)
            elif entity.kind == 'pod':
                self._voxelize_pod(entity.params)

    @staticmethod
    def _heuristic(a: Voxel, b: Voxel) -> float:
        # 0.95 is the lowest possible straight-continuation step cost.
        return 0.95 * math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))

    @staticmethod
    def _add(a: Voxel, b: Direction) -> Voxel:
        return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

    def _search_bounds(self, start: Voxel, goal: Voxel):
        points = [start, goal]
        if self.obstacles:
            xs = [p[0] for p in self.obstacles]
            ys = [p[1] for p in self.obstacles]
            zs = [p[2] for p in self.obstacles]
            points.extend(((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))))
        margin = max(4, int(math.ceil((self.clearance + 0.15) / self.res)))
        lo = tuple(min(p[i] for p in points) - margin for i in range(3))
        hi = tuple(max(p[i] for p in points) + margin for i in range(3))
        return lo, hi

    @staticmethod
    def _inside_bounds(node: Voxel, lo: Voxel, hi: Voxel) -> bool:
        return all(lo[i] <= node[i] <= hi[i] for i in range(3))

    @staticmethod
    def _simplify_voxel_path(path: Sequence[Voxel]) -> list[Voxel]:
        if len(path) <= 2:
            return list(path)
        out = [path[0]]
        previous_direction = (
            path[1][0] - path[0][0],
            path[1][1] - path[0][1],
            path[1][2] - path[0][2],
        )
        for index in range(1, len(path) - 1):
            direction = (
                path[index + 1][0] - path[index][0],
                path[index + 1][1] - path[index][1],
                path[index + 1][2] - path[index][2],
            )
            if direction != previous_direction:
                out.append(path[index])
                previous_direction = direction
        out.append(path[-1])
        return out

    def compute_route(self, start_xyz, end_xyz) -> list[Vec3]:
        """Compute a collision-free deterministic 3D A* route on the configured voxel grid."""
        start_world = tuple(float(v) for v in start_xyz)
        end_world = tuple(float(v) for v in end_xyz)
        start = self._world_to_grid(start_world)
        goal = self._world_to_grid(end_world)
        if start == goal:
            return [start_world, end_world] if start_world != end_world else [start_world]

        # Connection anchors themselves are legal even if they touch a structural boundary.
        blocked = self.obstacles - {start, goal}
        lo, hi = self._search_bounds(start, goal)

        serial = count()
        start_state = (start, None)
        open_heap = []
        heappush(open_heap, (self._heuristic(start, goal), 0.0, next(serial), start, None))
        best_cost = {start_state: 0.0}
        came_from = {}
        final_state = None

        while open_heap:
            _f, g, _order, node, previous_direction = heappop(open_heap)
            state = (node, previous_direction)
            if g > best_cost.get(state, math.inf) + 1e-12:
                continue
            if node == goal:
                final_state = state
                break

            for direction in self._DIRECTIONS:
                nxt = self._add(node, direction)
                if not self._inside_bounds(nxt, lo, hi) or nxt in blocked:
                    continue
                step_cost = 0.95 if previous_direction == direction else 1.0
                candidate = g + step_cost
                next_state = (nxt, direction)
                if candidate + 1e-12 >= best_cost.get(next_state, math.inf):
                    continue
                best_cost[next_state] = candidate
                came_from[next_state] = state
                h = self._heuristic(nxt, goal)
                heappush(open_heap, (candidate + h, candidate, next(serial), nxt, direction))

        if final_state is None:
            raise ValueError('no collision-free MEP route exists inside the bounded search volume')

        voxels = []
        cursor = final_state
        while True:
            voxels.append(cursor[0])
            if cursor == start_state:
                break
            cursor = came_from[cursor]
        voxels.reverse()
        voxels = self._simplify_voxel_path(voxels)

        route = [self._grid_to_world(v) for v in voxels]
        route[0] = start_world
        route[-1] = end_world
        return route

    def entity_anchor(self, entity_id: str) -> Vec3:
        """Resolve one deterministic physical connection anchor from authoritative entity state."""
        entity = self.doc.get(str(entity_id))
        p = entity.params

        if entity.kind in ('box', 'mechanical_part'):
            return (float(p['x']), float(p['y']), float(p['z']) + float(p['height']) / 2.0)
        if entity.kind == 'wall':
            return (
                (float(p['x1']) + float(p['x2'])) / 2.0,
                (float(p['y1']) + float(p['y2'])) / 2.0,
                float(p['z']) + float(p['height']) / 2.0,
            )
        if entity.kind == 'pod':
            return (
                float(p['cx']),
                float(p['cy']),
                float(p['floor_level']) + float(p['height']) / 2.0,
            )
        if entity.kind == 'mesh':
            metadata = p.get('metadata', {})
            explicit = metadata.get('mep_anchor')
            if isinstance(explicit, (list, tuple)) and len(explicit) == 3:
                return tuple(float(v) for v in explicit)
            matrix = [float(v) for v in p['matrix']]
            world = []
            for x, y, z in p['vertices']:
                world.append((
                    matrix[0] * x + matrix[1] * y + matrix[2] * z + matrix[3],
                    matrix[4] * x + matrix[5] * y + matrix[6] * z + matrix[7],
                    matrix[8] * x + matrix[9] * y + matrix[10] * z + matrix[11],
                ))
            if not world:
                raise ValueError('mesh endpoint has no vertices')
            return tuple(sum(point[i] for point in world) / len(world) for i in range(3))

        raise ValueError(f'no MEP connection anchor resolver for entity kind {entity.kind!r}')
