from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple
import copy
import json
import math
import uuid

Vec3 = Tuple[float, float, float]


def _finite(v):
    v = float(v)
    if not math.isfinite(v):
        raise ValueError('value must be finite')
    return v


def _positive(v):
    v = _finite(v)
    if v <= 0:
        raise ValueError('dimension must be > 0')
    return v


def _nonnegative(v):
    v = _finite(v)
    if v < 0:
        raise ValueError('value must be >= 0')
    return v


def _nonempty(v):
    v = str(v)
    if not v:
        raise ValueError('value must be a non-empty string')
    return v


def _vec3(v):
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise ValueError('value must be a 3-vector')
    return [_finite(x) for x in v]


def _room_signature(v):
    v = str(v)
    if not v.startswith('room-') or len(v) < 8:
        raise ValueError('invalid room signature')
    return v


def _polygon(v):
    from archforge.architecture.floors import validate_polygon
    return validate_polygon(v)



def _mesh_vertices(v):
    if not isinstance(v, list) or not v:
        raise ValueError('mesh vertices must be a non-empty list')
    out = []
    for point in v:
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            raise ValueError('each mesh vertex must be a 3-vector')
        out.append([_finite(x) for x in point])
    return out


def _mesh_faces(v):
    if not isinstance(v, list) or not v:
        raise ValueError('mesh faces must be a non-empty list')
    out = []
    for face in v:
        if not isinstance(face, (list, tuple)) or len(face) < 3:
            raise ValueError('each mesh face must contain at least three vertex indices')
        indices = [int(i) for i in face]
        if any(i < 0 for i in indices):
            raise ValueError('mesh face indices must be non-negative')
        out.append(indices)
    return out


def _matrix16(v):
    if not isinstance(v, (list, tuple)) or len(v) != 16:
        raise ValueError('mesh matrix must contain 16 values')
    return [_finite(x) for x in v]


def _conduit_diameter(v):
    value = _finite(v)
    if value < 0.005 or value > 0.5:
        raise ValueError('conduit diameter must be between 0.005 m and 0.5 m')
    return value


def _conduit_node(v):
    if not isinstance(v, str) or not v:
        raise ValueError('conduit node must be a non-empty string')
    return v


def _conduit_path(v):
    if not isinstance(v, list) or len(v) < 2:
        raise ValueError('conduit path_vertices must contain at least two 3D points')
    return [_vec3(point) for point in v]


def _conduit_system_type(v):
    if v not in ('hydraulic', 'electrical', 'hvac'):
        raise ValueError('conduit system_type must be hydraulic, electrical, or hvac')
    return v


@dataclass
class WorkPlane:
    name: str = 'XY'
    origin: Vec3 = (0.0, 0.0, 0.0)
    u: Vec3 = (1.0, 0.0, 0.0)
    v: Vec3 = (0.0, 1.0, 0.0)

    def normal(self):
        ux, uy, uz = self.u
        vx, vy, vz = self.v
        return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)

    def world_delta(self, da, db):
        return tuple(da * self.u[i] + db * self.v[i] for i in range(3))

    def project(self, p):
        d = tuple(p[i] - self.origin[i] for i in range(3))
        return (sum(d[i] * self.u[i] for i in range(3)), sum(d[i] * self.v[i] for i in range(3)))

    def unproject(self, a, b):
        return tuple(self.origin[i] + a * self.u[i] + b * self.v[i] for i in range(3))


@dataclass
class Entity:
    kind: str
    params: Dict[str, Any]
    name: str = ''
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    locked: bool = False
    visible: bool = True
    revision: int = 0

    def clone(self):
        return copy.deepcopy(self)


_ROOM_SLAB = {'room_signature': _room_signature, 'thickness': _positive, 'offset_z': _finite}
_OPENING = {'offset': _finite, 'surface_u': _finite, 'width': _positive, 'height': _positive, 'sill': _finite, 'flat_margin': _nonnegative}
SCHEMAS = {
    'box': {'x': _finite, 'y': _finite, 'z': _finite, 'width': _positive, 'depth': _positive, 'height': _positive, 'rotation': _finite},
    'wall': {'x1': _finite, 'y1': _finite, 'z': _finite, 'x2': _finite, 'y2': _finite, 'height': _positive, 'thickness': _positive},
    'pod': {'cx': _finite, 'cy': _finite, 'floor_level': _finite, 'diameter_x': _positive, 'diameter_y': _positive, 'height': _positive, 'shell_thickness': _positive, 'rotation': _finite},
    'mesh': {'vertices': _mesh_vertices, 'faces': _mesh_faces, 'matrix': _matrix16},
    'conduit': {
        'start_node': _conduit_node,
        'end_node': _conduit_node,
        'diameter': _conduit_diameter,
        'path_vertices': _conduit_path,
        'system_type': _conduit_system_type,
    },
    'arboreal_branch': {'core_id': _nonempty, 'elevation_z': _finite, 'azimuth_deg': _finite, 'length': _positive, 'slope_deg': _finite, 'root_radius': _positive, 'tip_radius': _positive, 'mounted_pod_id': _nonempty},
    'floor': {'points': _polygon, 'z': _finite, 'thickness': _positive},
    'room': {'points': _polygon, 'z': _finite, 'height': _positive},
    'room_floor': _ROOM_SLAB,
    'room_ceiling': _ROOM_SLAB,
    'room_foundation': _ROOM_SLAB,
    'room_roof': {**_ROOM_SLAB, 'roof_type': _nonempty},
    'door': _OPENING,
    'window': _OPENING,
    'organic_opening_patch': {'opening_id': _nonempty, 'host_id': _nonempty, 'status': _nonempty},
    'mechanical_part': {'x': _finite, 'y': _finite, 'z': _finite, 'width': _positive, 'depth': _positive, 'height': _positive, 'rotation': _finite},
    'mechanical_joint': {'joint_type': _nonempty, 'parent_part': _nonempty, 'child_part': _nonempty, 'anchor': _vec3, 'axis': _vec3, 'min_value': _finite, 'max_value': _finite, 'value': _finite},
    'mechanical_mount': {'host_id': _nonempty, 'part_id': _nonempty, 'surface_role': _nonempty, 'clearance': _nonnegative, 'embed_depth': _nonnegative},
}


def validate_params(kind, params):
    out = copy.deepcopy(params)
    for key, fn in SCHEMAS.get(kind, {}).items():
        if key in out:
            out[key] = fn(out[key])
    if kind == 'mesh':
        required = {'vertices', 'faces', 'matrix'}
        missing = required - set(out)
        if missing:
            raise ValueError('mesh is missing required fields: ' + ', '.join(sorted(missing)))
        n = len(out['vertices'])
        if any(index >= n for face in out['faces'] for index in face):
            raise ValueError('mesh face references a missing vertex')
    if kind == 'conduit':
        required = {'start_node', 'end_node', 'diameter', 'path_vertices', 'system_type'}
        missing = required - set(out)
        if missing:
            raise ValueError('conduit is missing required fields: ' + ', '.join(sorted(missing)))
    return out


class Document:
    @property
    def entities(self):
        return self._entities

    @entities.setter
    def entities(self, value):
        old_ids = set(getattr(self, '_entities', {}))
        self._entities = value
        self._openings_by_host.clear()
        for entity_id, entity in value.items():
            if entity.kind in ('door', 'window') and entity.parent_id:
                self._openings_by_host.setdefault(entity.parent_id, []).append(entity_id)
        if hasattr(self, '_change_serial') and hasattr(self, 'dirty'):
            self._change_serial += 1
            generation = self._change_serial
            for entity_id in old_ids | set(value.keys()):
                self.dirty.add(entity_id)
                self._dirty_generation[entity_id] = generation

    @property
    def surface_modifiers(self):
        return self._surface_modifiers

    @surface_modifiers.setter
    def surface_modifiers(self, value):
        old_owners = {
            str(modifier.target.owner_id)
            for modifier in getattr(self, '_surface_modifiers', {}).values()
        }
        self._surface_modifiers = value
        self._modifiers_by_owner.clear()
        new_owners = set()
        for modifier_id, modifier in value.items():
            owner_id = str(modifier.target.owner_id)
            new_owners.add(owner_id)
            self._modifiers_by_owner.setdefault(owner_id, []).append(modifier_id)
        if hasattr(self, '_change_serial') and hasattr(self, 'dirty'):
            for owner_id in old_owners | new_owners:
                self.mark_dirty(owner_id)

    def __init__(self):
        self._openings_by_host: Dict[str, List[str]] = {}
        self._modifiers_by_owner: Dict[str, List[str]] = {}
        self._entities: Dict[str, Entity] = {}
        self._surface_modifiers = {}
        self.entities = {}
        self.children: Dict[str, List[str]] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        self.selection: List[str] = []
        self.dirty: Set[str] = set()
        self.levels = {'Ground': 0.0}
        self.work_plane = WorkPlane()
        self.materials = {}
        self.constructions = {}
        self.room_data = {}
        self.room_bindings = {}
        self.surface_modifiers = {}
        self._change_serial = 0
        self._dirty_generation: Dict[str, int] = {}

    def opening_ids_for_host(self, host_id: str) -> Tuple[str, ...]:
        return tuple(self._openings_by_host.get(host_id, ()))

    def modifier_ids_for_owner(self, owner_id: str) -> Tuple[str, ...]:
        return tuple(self._modifiers_by_owner.get(owner_id, ()))

    def dirty_generation(self, entity_id: str) -> int:
        return int(self._dirty_generation.get(entity_id, 0))

    def _index_entity(self, entity: Entity) -> None:
        if entity.kind in ('door', 'window') and entity.parent_id:
            ids = self._openings_by_host.setdefault(entity.parent_id, [])
            if entity.id not in ids:
                ids.append(entity.id)

    def _deindex_entity(self, entity: Entity) -> None:
        if entity.kind in ('door', 'window') and entity.parent_id:
            ids = self._openings_by_host.get(entity.parent_id)
            if ids is not None:
                try:
                    ids.remove(entity.id)
                except ValueError:
                    pass
                if not ids:
                    self._openings_by_host.pop(entity.parent_id, None)

    def _index_modifier(self, modifier) -> None:
        owner_id = str(modifier.target.owner_id)
        ids = self._modifiers_by_owner.setdefault(owner_id, [])
        if modifier.id not in ids:
            ids.append(modifier.id)

    def _deindex_modifier(self, modifier_id: str, modifier=None) -> None:
        if modifier is None:
            modifier = self.surface_modifiers.get(modifier_id)
        if modifier is None:
            return
        owner_id = str(modifier.target.owner_id)
        ids = self._modifiers_by_owner.get(owner_id)
        if ids is None:
            return
        try:
            ids.remove(modifier_id)
        except ValueError:
            pass
        if not ids:
            self._modifiers_by_owner.pop(owner_id, None)

    def _mark_related_geometry_dirty(self, entity: Entity) -> None:
        if entity.kind in ('door', 'window') and entity.parent_id:
            self.mark_dirty(entity.parent_id)
        elif entity.kind == 'organic_opening_patch':
            host_id = entity.params.get('host_id')
            if host_id in self.entities:
                self.mark_dirty(str(host_id))
        elif entity.kind == 'organic_junction':
            for key in ('component_a', 'component_b'):
                component_id = entity.params.get(key)
                if component_id in self.entities:
                    self.mark_dirty(str(component_id))
        elif entity.kind == 'mechanical_joint':
            for key in ('parent_part', 'child_part'):
                part_id = entity.params.get(key)
                if part_id in self.entities:
                    self.mark_dirty(str(part_id))
        elif entity.kind == 'mechanical_mount':
            for key in ('host_id', 'part_id'):
                related_id = entity.params.get(key)
                if related_id in self.entities:
                    self.mark_dirty(str(related_id))

    def _validate_wall_opening_conflicts(self, entity, tolerance=1e-9):
        if not entity.parent_id:
            return
        p = entity.params
        u0 = float(p['offset']) - float(p['width']) / 2.0
        u1 = float(p['offset']) + float(p['width']) / 2.0
        z0 = float(p.get('sill', 0.0))
        z1 = z0 + float(p['height'])
        for cid in self.children.get(entity.parent_id, ()):
            if cid == entity.id:
                continue
            other = self.entities.get(cid)
            if not other or other.kind not in ('door', 'window'):
                continue
            q = other.params
            v0 = float(q['offset']) - float(q['width']) / 2.0
            v1 = float(q['offset']) + float(q['width']) / 2.0
            w0 = float(q.get('sill', 0.0))
            w1 = w0 + float(q['height'])
            horizontal = min(u1, v1) - max(u0, v0)
            vertical = min(z1, w1) - max(z0, w0)
            if horizontal > tolerance and vertical > tolerance:
                raise ValueError('wall openings must not overlap')

    def _validate_links(self, entity):
        if entity.kind in ('door', 'window'):
            if not entity.parent_id or entity.parent_id not in self.entities:
                raise ValueError('door/window must be attached to an existing wall or pod')
            host = self.entities[entity.parent_id]
            if host.kind == 'wall':
                from archforge.architecture.openings import validate_opening
                validate_opening(host.params, entity.params, entity.kind)
                self._validate_wall_opening_conflicts(entity)
            elif host.kind == 'pod':
                from archforge.architecture.openings import validate_pod_opening
                validate_pod_opening(host.params, entity.params, entity.kind)
            else:
                raise ValueError('door/window host must be a wall or pod')
        elif entity.kind == 'arboreal_branch':
            from archforge.organic.arboreal import validate_arboreal_branch
            validate_arboreal_branch(self, entity)
        elif entity.kind == 'mechanical_joint':
            from archforge.kinematics.model import validate_joint
            validate_joint(self, entity)
        elif entity.kind == 'mechanical_mount':
            from archforge.kinematics.model import validate_mount
            validate_mount(self, entity)

    def _register_links(self, entity):
        if entity.parent_id:
            self.children.setdefault(entity.parent_id, []).append(entity.id)
        self._index_entity(entity)
        if entity.parent_id and entity.kind in ('door', 'window'):
            self.add_dependency(entity.parent_id, entity.id)
        if entity.kind == 'arboreal_branch':
            self.add_dependency(entity.params['core_id'], entity.id)
        elif entity.kind == 'mechanical_joint':
            self.add_dependency(entity.params['parent_part'], entity.id)
            self.add_dependency(entity.params['child_part'], entity.id)
        elif entity.kind == 'mechanical_mount':
            self.add_dependency(entity.params['host_id'], entity.id)
            self.add_dependency(entity.params['part_id'], entity.id)
        elif entity.kind == 'conduit':
            for key in ('start_node', 'end_node'):
                source_id = entity.params[key]
                if source_id in self.entities:
                    self.add_dependency(source_id, entity.id)

    def add(self, entity):
        if entity.id in self.entities:
            raise ValueError('duplicate id')
        entity.params = validate_params(entity.kind, entity.params)
        self._validate_links(entity)
        self.entities[entity.id] = entity
        try:
            self._register_links(entity)
        except Exception:
            self._deindex_entity(entity)
            self.entities.pop(entity.id, None)
            raise
        self.mark_dirty(entity.id)
        self._mark_related_geometry_dirty(entity)
        return entity.id

    def get(self, eid):
        return self.entities[eid]

    def update(self, eid, changes):
        entity = self.get(eid)
        if entity.locked:
            raise PermissionError('entity is locked')
        params = entity.params.copy()
        params.update(changes)
        params = validate_params(entity.kind, params)
        candidate = entity.clone()
        candidate.params = params
        if entity.kind in ('door', 'window', 'arboreal_branch', 'mechanical_joint', 'mechanical_mount'):
            self._validate_links(candidate)
        elif entity.kind == 'wall':
            from archforge.architecture.openings import validate_opening
            for cid in self.children.get(eid, ()):
                child = self.entities.get(cid)
                if child and child.kind in ('door', 'window'):
                    validate_opening(params, child.params, child.kind)
        elif entity.kind == 'pod':
            from archforge.architecture.openings import validate_pod_opening
            for cid in self.children.get(eid, ()):
                child = self.entities.get(cid)
                if child and child.kind in ('door', 'window'):
                    validate_pod_opening(params, child.params, child.kind)
        if entity.kind == 'mechanical_joint' and (
            params['parent_part'] != entity.params['parent_part'] or params['child_part'] != entity.params['child_part']
        ):
            raise ValueError('joint part references require explicit relink')
        if entity.kind == 'mechanical_mount' and (
            params['host_id'] != entity.params['host_id'] or params['part_id'] != entity.params['part_id']
        ):
            raise ValueError('mount references require explicit relink')

        arboreal_snapshots = {}
        if entity.kind in ('arboreal_branch', 'box'):
            from archforge.organic.arboreal import arboreal_mounted_pod_ids
            pod_ids = set(arboreal_mounted_pod_ids(self, eid))
            if entity.kind == 'arboreal_branch' and params.get('mounted_pod_id') in self.entities:
                pod_ids.add(str(params['mounted_pod_id']))
            for pid in pod_ids:
                pod = self.entities.get(pid)
                if pod is not None:
                    arboreal_snapshots[pid] = (copy.deepcopy(pod.params), pod.revision)

        old_params = copy.deepcopy(entity.params)
        old_revision = entity.revision
        entity.params = params
        entity.revision += 1
        self.mark_dirty(eid)
        self._mark_related_geometry_dirty(entity)
        try:
            if entity.kind in ('arboreal_branch', 'box') and (arboreal_snapshots or entity.kind == 'arboreal_branch'):
                from archforge.organic.arboreal import sync_arboreal_mounted_pods
                sync_arboreal_mounted_pods(self, eid)
        except Exception:
            entity.params = old_params
            entity.revision = old_revision
            self.mark_dirty(eid)
            for pid, (saved_params, revision) in arboreal_snapshots.items():
                if pid in self.entities:
                    self.entities[pid].params = saved_params
                    self.entities[pid].revision = revision
                    self.mark_dirty(pid)
            raise

    def set_room_metadata(self, signature, **changes):
        from archforge.architecture.room_identity import resolve_room_metadata_key
        key = resolve_room_metadata_key(self, signature)
        allowed = {'name', 'use', 'floor_finish', 'ceiling_finish', 'notes'}
        data = copy.deepcopy(self.room_data.get(key, {}))
        if set(changes) - allowed:
            raise ValueError('unsupported room metadata')
        for k, v in changes.items():
            if v is None:
                data.pop(k, None)
            else:
                data[k] = str(v)
        if data:
            self.room_data[key] = data
        else:
            self.room_data.pop(key, None)

    def room_metadata(self, signature):
        from archforge.architecture.room_identity import resolve_room_metadata_key
        key = resolve_room_metadata_key(self, signature)
        return copy.deepcopy(self.room_data.get(key, self.room_data.get(signature, {})))

    def active_room_faces(self, z=None, tolerance=1e-5):
        from archforge.architecture.room_identity import reconcile_room_bindings
        level = self.work_plane.origin[2] if z is None else z
        return [face for face, _ in reconcile_room_bindings(self, z=level, tolerance=tolerance)]

    def add_surface_modifier(self, modifier):
        from .modifiers import add_modifier
        return add_modifier(self, modifier)

    def update_surface_modifier(self, modifier_id, **changes):
        from .modifiers import update_modifier
        return update_modifier(self, modifier_id, **changes)

    def remove_surface_modifier(self, modifier_id):
        from .modifiers import remove_modifier
        return remove_modifier(self, modifier_id)

    def mark_dirty(self, eid):
        self._change_serial += 1
        generation = self._change_serial
        stack = [eid]
        seen = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            self.dirty.add(current)
            self._dirty_generation[current] = generation
            stack.extend(self.dependencies.get(current, ()))

    def add_dependency(self, source, dependent):
        if source == dependent:
            raise ValueError('self dependency')
        self.dependencies.setdefault(source, set()).add(dependent)
        if self._reachable(dependent, source):
            self.dependencies[source].remove(dependent)
            raise ValueError('dependency cycle')

    def _reachable(self, a, b):
        stack = [a]
        seen = set()
        while stack:
            current = stack.pop()
            if current == b:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self.dependencies.get(current, ()))
        return False

    def remove(self, eid):
        ids = []

        def walk(current):
            for child_id in list(self.children.get(current, ())):
                walk(child_id)
            if current not in ids:
                ids.append(current)

        walk(eid)
        changed = True
        while changed:
            changed = False
            for rid, entity in list(self.entities.items()):
                if rid in ids:
                    continue
                refs = []
                if entity.kind == 'mechanical_joint':
                    refs = [entity.params.get('parent_part'), entity.params.get('child_part')]
                elif entity.kind == 'mechanical_mount':
                    refs = [entity.params.get('host_id'), entity.params.get('part_id')]
                elif entity.kind == 'conduit':
                    refs = [entity.params.get('start_node'), entity.params.get('end_node')]
                if any(ref in ids for ref in refs):
                    ids.append(rid)
                    changed = True

        snapshots = {item_id: self.entities[item_id].clone() for item_id in ids}
        for item_id in ids:
            entity = self.entities[item_id]
            self._mark_related_geometry_dirty(entity)
            self._deindex_entity(entity)
            self.entities.pop(item_id, None)
            self.children.pop(item_id, None)
            self.dependencies.pop(item_id, None)
            for dependents in self.dependencies.values():
                dependents.discard(item_id)
            self.selection = [x for x in self.selection if x != item_id]
            self.mark_dirty(item_id)

        for kids in self.children.values():
            kids[:] = [x for x in kids if x not in ids]

        for branch in self.entities.values():
            if branch.kind == 'arboreal_branch' and branch.params.get('mounted_pod_id') in ids:
                branch.params.pop('mounted_pod_id', None)
                branch.revision += 1
                self.mark_dirty(branch.id)

        for modifier_id, modifier in list(self.surface_modifiers.items()):
            if modifier.target.owner_id in ids:
                self._deindex_modifier(modifier_id, modifier)
                self.surface_modifiers.pop(modifier_id, None)
        return snapshots

    def select(self, ids, add=False):
        valid = [item_id for item_id in ids if item_id in self.entities]
        if add:
            for item_id in valid:
                if item_id not in self.selection:
                    self.selection.append(item_id)
        else:
            self.selection = valid

    def to_dict(self):
        from .modifiers import modifier_to_dict
        return {
            'format': 7,
            'entities': [asdict(entity) for entity in self.entities.values()],
            'dependencies': {k: sorted(v) for k, v in self.dependencies.items()},
            'levels': self.levels,
            'work_plane': asdict(self.work_plane),
            'materials': self.materials,
            'constructions': self.constructions,
            'room_data': copy.deepcopy(self.room_data),
            'room_bindings': copy.deepcopy(self.room_bindings),
            'surface_modifiers': [modifier_to_dict(m) for m in self.surface_modifiers.values()],
        }

    @classmethod
    def from_dict(cls, data):
        doc = cls()
        doc.levels = data.get('levels', {'Ground': 0.0})
        wp = data.get('work_plane')
        if wp:
            doc.work_plane = WorkPlane(
                name=wp.get('name', 'XY'),
                origin=tuple(wp.get('origin', (0, 0, 0))),
                u=tuple(wp.get('u', (1, 0, 0))),
                v=tuple(wp.get('v', (0, 1, 0))),
            )
        doc.materials = data.get('materials', {})
        doc.constructions = data.get('constructions', {})
        doc.room_data = copy.deepcopy(data.get('room_data', {}))
        doc.room_bindings = copy.deepcopy(data.get('room_bindings', {}))
        deferred = []
        for raw in data.get('entities', []):
            if raw.get('kind') in ('door', 'window', 'organic_opening_patch', 'mechanical_joint', 'mechanical_mount'):
                deferred.append(raw)
            else:
                doc.add(Entity(**raw))
        for raw in [r for r in deferred if r.get('kind') in ('door', 'window')]:
            doc.add(Entity(**raw))
        for raw in [r for r in deferred if r.get('kind') not in ('door', 'window')]:
            doc.add(Entity(**raw))
        for source, deps in data.get('dependencies', {}).items():
            for dep in deps:
                if source in doc.entities and dep in doc.entities and dep not in doc.dependencies.get(source, set()):
                    doc.add_dependency(source, dep)
        from .modifiers import modifier_from_dict
        for raw in data.get('surface_modifiers', []):
            doc.add_surface_modifier(modifier_from_dict(raw))
        doc.dirty.clear()
        doc._dirty_generation.clear()
        doc._change_serial = 0
        return doc

    def save(self, path):
        with open(path, 'w', encoding='utf8') as handle:
            json.dump(self.to_dict(), handle, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, encoding='utf8') as handle:
            return cls.from_dict(json.load(handle))
