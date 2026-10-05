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


def _mesh_metadata(v):
    if not isinstance(v, dict):
        raise ValueError('mesh metadata must be a dictionary')
    return copy.deepcopy(v)


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
    out = [_vec3(point) for point in v]
    for a, b in zip(out, out[1:]):
        if math.dist(a, b) <= 1e-9:
            raise ValueError('conduit path_vertices must not contain zero-length segments')
    return out


def _conduit_system_type(v):
    value = str(v).lower()
    if value not in ('hydraulic', 'electrical', 'hvac'):
        raise ValueError('conduit system_type must be hydraulic, electrical, or hvac')
    return value


def _stair_layout(v):
    value = str(v).lower()
    if value not in ('straight', 'l', 'u', 'spiral', 'custom'):
        raise ValueError('unsupported stair layout')
    return value


def _wall_type(v):
    from archforge.architecture.wall_types import WALL_TYPES
    v = str(v)
    if v not in WALL_TYPES:
        raise ValueError(f'wall type must be one of {", ".join(WALL_TYPES)}')
    return v


def _plumbing_type(v):
    from archforge.mep.plumbing import POINT_TYPES
    v = str(v)
    if v not in POINT_TYPES:
        raise ValueError(f'plumbing point must be one of {", ".join(POINT_TYPES)}')
    return v


def _electrical_type(v):
    from archforge.mep.electrical import POINT_TYPES
    v = str(v)
    if v not in POINT_TYPES:
        raise ValueError(f'electrical point must be one of {", ".join(POINT_TYPES)}')
    return v


def _roof_form(v):
    from archforge.structure.timber_roof import FORMS
    v = str(v)
    if v not in FORMS:
        raise ValueError(f'roof form must be one of {", ".join(FORMS)}')
    return v


def _roof_tile(v):
    from archforge.structure.timber_roof import TILES
    v = str(v)
    if v not in TILES:
        raise ValueError(f'tile must be one of {", ".join(TILES)}')
    return v


def _roof_insulation(v):
    from archforge.structure.timber_roof import INSULATIONS
    v = str(v)
    if v not in INSULATIONS:
        raise ValueError(f'insulation must be one of {", ".join(INSULATIONS)}')
    return v


def _insulation_thickness(v):
    v = _finite(v)
    if not 0.0 <= v <= 0.30:
        raise ValueError('insulation thickness must be between 0 and 0.30 m')
    return v


def _snow_zone(v):
    v = int(round(float(v)))
    if v not in (1, 2, 3):
        raise ValueError('snow zone must be 1, 2 or 3')
    return v


def _pitch(v):
    v = _finite(v)
    if not 5.0 <= v <= 60.0:
        raise ValueError('roof pitch must be between 5 and 60 degrees')
    return v


def _rafter_spacing(v):
    v = _finite(v)
    if not 0.3 <= v <= 1.2:
        raise ValueError('rafter spacing must be between 0.30 and 1.20 m')
    return v


def _count(v):
    value = int(round(float(v)))
    if not 0 <= value <= 20:
        raise ValueError('count must be between 0 and 20')
    return value


def _cabinet_type(v):
    from archforge.kitchen.cabinets import TYPES
    v = str(v)
    if v not in TYPES:
        raise ValueError(f'cabinet type must be one of {", ".join(TYPES)}')
    return v


def _cabinet_handle(v):
    from archforge.kitchen.cabinets import HANDLES
    v = str(v)
    if v not in HANDLES:
        raise ValueError(f'handle must be one of {", ".join(HANDLES)}')
    return v


def _positive_int(v):
    value = int(v)
    if value <= 0:
        raise ValueError('value must be a positive integer')
    return value


def _turn_direction(v):
    value = int(v)
    if value == 0:
        raise ValueError('turn direction must be -1 or 1')
    return 1 if value > 0 else -1


def _opening_shape(v):
    value = str(v).lower()
    if value not in ('rectangle', 'arch'):
        raise ValueError('opening shape must be rectangle or arch')
    return value


def _structural_role(v):
    value = str(v).lower()
    if value not in ('structural', 'pergola', 'architectural'):
        raise ValueError('role must be structural, pergola, or architectural')
    return value


def _construction_system(v):
    value = str(v).lower()
    if value not in ('reinforced_concrete', 'steel', 'timber', 'aluminium', 'generic'):
        raise ValueError('unsupported construction system')
    return value


def _structural_section(v):
    value = str(v).lower()
    if value not in ('rectangular',):
        raise ValueError('only rectangular structural sections are currently supported')
    return value


def _structural_support_type(v):
    value = str(v).lower()
    if value not in ('fixed', 'pinned', 'roller'):
        raise ValueError('support type must be fixed, pinned, or roller')
    return value


def _member_end(v):
    value = str(v).lower()
    if value not in ('start', 'end'):
        raise ValueError('member end must be start or end')
    return value


def _structural_load_type(v):
    value = str(v).lower()
    if value not in ('point', 'distributed'):
        raise ValueError('load type must be point or distributed')
    return value


def _unit_interval(v):
    value = _finite(v)
    if value < 0.0 or value > 1.0:
        raise ValueError('position must be between 0 and 1')
    return value


def _path_style(v):
    value = str(v).strip().lower()
    if value not in ('path', 'sidewalk', 'road'):
        raise ValueError("path style must be 'path', 'sidewalk' or 'road'")
    return value


def _plant_species(v):
    value = str(v).strip().lower()
    if value not in ('tree', 'shrub'):
        raise ValueError("plant species must be 'tree' or 'shrub'")
    return value


def _terrain_points(v):
    out = []
    for item in v or ():
        if len(item) != 3:
            raise ValueError('terrain elevation point must be [x, y, z]')
        out.append([_finite(item[0]), _finite(item[1]), _finite(item[2])])
    return out


def _wall_surface_role(v):
    # Wall-hosted MEP mounts use the signed-offset roles; mechanical mounts
    # keep using the semantic surface catalog roles (interior, exterior, ...).
    # The host-specific check stays with the surface catalog.
    from archforge.geometry.surfaces import _KIND_ROLES
    value = str(v).lower().strip()
    catalog = {role for roles in _KIND_ROLES.values() for role, *_ in roles}
    if value not in ('positive_face', 'negative_face', 'centerline') and value not in catalog:
        raise ValueError(
            'mount surface role must be positive_face, negative_face, centerline, '
            'or a semantic surface role'
        )
    return value


def _kitchen_role(v):
    return _nonempty(v)


def _load_direction(v):
    vec = _vec3(v)
    length = math.sqrt(sum(float(x) * float(x) for x in vec))
    if length <= 1e-12:
        raise ValueError('load direction must be non-zero')
    return [float(x) / length for x in vec]


def validate_conduit_spec(start_node, end_node, diameter, system_type, path_vertices):
    return {
        'start_node': _conduit_node(start_node),
        'end_node': _conduit_node(end_node),
        'diameter': _conduit_diameter(diameter),
        'system_type': _conduit_system_type(system_type),
        'path_vertices': _conduit_path(path_vertices),
    }


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
_ARCH_OPENING = {**_OPENING, 'shape': _opening_shape, 'arch_rise': _positive}
SCHEMAS = {
    'box': {'x': _finite, 'y': _finite, 'z': _finite, 'width': _positive, 'depth': _positive, 'height': _positive, 'rotation': _finite},
    'wall': {'x1': _finite, 'y1': _finite, 'z': _finite, 'x2': _finite, 'y2': _finite, 'height': _positive, 'thickness': _positive, 'wall_type': _wall_type},
    'pod': {'cx': _finite, 'cy': _finite, 'floor_level': _finite, 'diameter_x': _positive, 'diameter_y': _positive, 'height': _positive, 'shell_thickness': _positive, 'rotation': _finite},
    'stair': {
        'x': _finite,
        'y': _finite,
        'lower_z': _finite,
        'upper_z': _finite,
        'upper_floor_z': _finite,
        'upper_slab_thickness': _nonnegative,
        'layout': _stair_layout,
        'angle_deg': _finite,
        'width': _positive,
        'riser_count': _positive_int,
        'riser_height': _positive,
        'tread_depth': _positive,
        'landing_depth': _positive,
        'turn_direction': _turn_direction,
        'opening_margin': _nonnegative,
    },
    'ramp': {
        'x': _finite,
        'y': _finite,
        'lower_z': _finite,
        'upper_z': _finite,
        'upper_floor_z': _finite,
        'upper_slab_thickness': _nonnegative,
        'angle_deg': _finite,
        'width': _positive,
        'slope_pct': _positive,
        'run_length': _positive,
        'thickness': _positive,
        'opening_margin': _nonnegative,
    },
    'mesh': {'vertices': _mesh_vertices, 'faces': _mesh_faces, 'matrix': _matrix16, 'metadata': _mesh_metadata},
    'arboreal_branch': {'core_id': _nonempty, 'elevation_z': _finite, 'azimuth_deg': _finite, 'length': _positive, 'slope_deg': _finite, 'root_radius': _positive, 'tip_radius': _positive, 'mounted_pod_id': _nonempty},
    'floor': {'points': _polygon, 'z': _finite, 'thickness': _positive},
    'room': {'points': _polygon, 'z': _finite, 'height': _positive},
    'room_floor': _ROOM_SLAB,
    'room_ceiling': _ROOM_SLAB,
    'room_foundation': _ROOM_SLAB,
    'room_roof': {**_ROOM_SLAB, 'roof_type': _nonempty, 'overhang': _nonnegative},
    'door': _OPENING,
    'window': _OPENING,
    'opening': _ARCH_OPENING,
    'organic_opening_patch': {'opening_id': _nonempty, 'host_id': _nonempty, 'status': _nonempty},
    'structural_column': {
        'x': _finite, 'y': _finite, 'z': _finite,
        'width': _positive, 'depth': _positive, 'height': _positive,
        'rotation': _finite,
        'role': _structural_role,
        'construction': _construction_system,
        'section': _structural_section,
        'base_level': _nonempty,
        'top_level': _nonempty,
    },
    'structural_beam': {
        'x1': _finite, 'y1': _finite, 'x2': _finite, 'y2': _finite,
        'z': _finite, 'width': _positive, 'height': _positive,
        'role': _structural_role,
        'construction': _construction_system,
        'section': _structural_section,
        'level': _nonempty,
    },
    'structural_support': {
        'member_end': _member_end,
        'support_type': _structural_support_type,
    },
    'structural_load': {
        'load_type': _structural_load_type,
        'magnitude': _finite,
        'direction': _load_direction,
        'position': _unit_interval,
        'load_case': _nonempty,
        'unit': _nonempty,
        'source': _nonempty,
    },
    'mechanical_part': {'x': _finite, 'y': _finite, 'z': _finite, 'width': _positive, 'depth': _positive, 'height': _positive, 'rotation': _finite},
    'mep_terminal': {
        'x': _finite,
        'y': _finite,
        'level_z': _finite,
        'elevation': _finite,
        'system_type': _conduit_system_type,
        'diameter': _conduit_diameter,
    },
    'mechanical_joint': {'joint_type': _nonempty, 'parent_part': _nonempty, 'child_part': _nonempty, 'anchor': _vec3, 'axis': _vec3, 'min_value': _finite, 'max_value': _finite, 'value': _finite},
    'mechanical_mount': {
        'host_id': _nonempty, 'part_id': _nonempty,
        'surface_u': _unit_interval, 'elevation': _finite,
        'surface_role': _wall_surface_role, 'normal_offset': _finite,
        'clearance': _nonnegative, 'embed_depth': _nonnegative,
    },
    'terrain': {
        'x0': _finite, 'y0': _finite, 'x1': _finite, 'y1': _finite,
        'elevation': _finite, 'slope_x': _finite, 'slope_y': _finite, 'thickness': _positive,
        'points': _terrain_points, 'blend_radius': _positive,
    },
    'site_path': {
        'x1': _finite, 'y1': _finite, 'x2': _finite, 'y2': _finite, 'z': _finite,
        'width': _positive, 'thickness': _positive, 'style': _path_style,
    },
    'plant': {
        'x': _finite, 'y': _finite, 'z': _finite, 'height': _positive, 'canopy': _positive,
        'species': _plant_species,
    },
    'pitched_roof': {'x0': _finite, 'y0': _finite, 'x1': _finite, 'y1': _finite, 'eave_z': _finite,
                     'pitch': _pitch, 'overhang': _nonnegative, 'rafter_spacing': _rafter_spacing,
                     'roof_form': _roof_form, 'tile': _roof_tile, 'snow_zone': _snow_zone, 'altitude': _nonnegative,
                     'insulation': _roof_insulation, 'insulation_thickness': _insulation_thickness},
    'electrical_point': {'x': _finite, 'y': _finite, 'z': _finite, 'point_type': _electrical_type, 'power_w': _nonnegative},
    'plumbing_point': {'x': _finite, 'y': _finite, 'z': _finite, 'point_type': _plumbing_type},
    'cabinet': {
        'x': _finite, 'y': _finite, 'z': _finite, 'rotation': _finite,
        'width': _positive, 'depth': _positive, 'height': _positive, 'plinth': _nonnegative,
        'cabinet_type': _cabinet_type, 'doors': _count, 'drawers': _count, 'shelves': _count,
        'worktop': _unit_interval, 'handle': _cabinet_handle,
    },
    'library_object': {
        'x': _finite, 'y': _finite, 'z': _finite, 'rotation': _finite,
        'width': _positive, 'depth': _positive, 'height': _positive,
        'uniform': _unit_interval, 'asset': _nonempty,
    },
    'kitchen_part': {
        'x': _finite, 'y': _finite, 'z': _finite,
        'width': _positive, 'depth': _positive, 'height': _positive,
        'rotation': _finite, 'role': _kitchen_role, 'run_id': _nonempty,
        'roughness': _unit_interval, 'metallic': _unit_interval,
    },
}


def validate_params(kind, params):
    out = copy.deepcopy(params)
    # Backward compatibility: columns authored before structural section and
    # top-level semantics were introduced must remain loadable/editable.
    # Explicit values are still validated by the normal schema below.
    if kind == 'structural_column':
        out.setdefault('section', 'rectangular')
        out.setdefault('top_level', 'Unassigned')
    for key, fn in SCHEMAS.get(kind, {}).items():
        if key in out:
            out[key] = fn(out[key])
    if kind == 'terrain':
        if float(out.get('x1', 0)) - float(out.get('x0', 0)) <= 1e-6 or float(out.get('y1', 0)) - float(out.get('y0', 0)) <= 1e-6:
            raise ValueError('terrain extent must be positive (x1 > x0, y1 > y0)')
        if abs(float(out.get('slope_x', 0))) > 100 or abs(float(out.get('slope_y', 0))) > 100:
            raise ValueError('terrain slope must be within ±100 %')
    if kind == 'structural_column':
        required = {
            'x','y','z','width','depth','height','rotation',
            'role','construction','section','base_level','top_level',
        }
        missing = required - set(out)
        if missing:
            raise ValueError('structural column is missing required fields: ' + ', '.join(sorted(missing)))
    if kind == 'structural_beam':
        required = {
            'x1','y1','x2','y2','z','width','height',
            'role','construction','section','level',
        }
        missing = required - set(out)
        if missing:
            raise ValueError('structural beam is missing required fields: ' + ', '.join(sorted(missing)))
        if math.hypot(float(out['x2'])-float(out['x1']), float(out['y2'])-float(out['y1'])) <= 1e-9:
            raise ValueError('structural beam must have non-zero plan length')
    if kind == 'mesh':
        required = {'vertices', 'faces', 'matrix'}
        missing = required - set(out)
        if missing:
            raise ValueError('mesh is missing required fields: ' + ', '.join(sorted(missing)))
        n = len(out['vertices'])
        if any(index >= n for face in out['faces'] for index in face):
            raise ValueError('mesh face references a missing vertex')
    if kind == 'stair':
        required = {
            'x', 'y', 'lower_z', 'upper_z', 'layout', 'angle_deg', 'width',
            'riser_count', 'riser_height', 'tread_depth', 'landing_depth',
            'turn_direction', 'opening_margin',
        }
        missing = required - set(out)
        if missing:
            raise ValueError('stair is missing required fields: ' + ', '.join(sorted(missing)))
        height = float(out['upper_z']) - float(out['lower_z'])
        if height <= 0:
            raise ValueError('stair upper_z must be above lower_z')
        solved = float(out['riser_count']) * float(out['riser_height'])
        if abs(solved - height) > 1e-4:
            raise ValueError('stair riser count/height must match floor-to-floor height')
    if kind == 'ramp':
        required = {
            'x', 'y', 'lower_z', 'upper_z', 'angle_deg', 'width',
            'slope_pct', 'run_length', 'thickness', 'opening_margin',
        }
        missing = required - set(out)
        if missing:
            raise ValueError('ramp is missing required fields: ' + ', '.join(sorted(missing)))
        rise = float(out['upper_z']) - float(out['lower_z'])
        if rise <= 0:
            raise ValueError('ramp upper_z must be above lower_z')
        expected_run = rise / (float(out['slope_pct']) / 100.0)
        if abs(float(out['run_length']) - expected_run) > 1e-4:
            raise ValueError('ramp run_length must match rise and slope')
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
            if entity.kind in ('door', 'window', 'opening') and entity.parent_id:
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
        if entity.kind in ('door', 'window', 'opening') and entity.parent_id:
            ids = self._openings_by_host.setdefault(entity.parent_id, [])
            if entity.id not in ids:
                ids.append(entity.id)

    def _deindex_entity(self, entity: Entity) -> None:
        if entity.kind in ('door', 'window', 'opening') and entity.parent_id:
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
        if entity.kind in ('door', 'window', 'opening') and entity.parent_id:
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
        elif entity.kind == 'terrain':
            # Plants (and other site elements) stand on the ground surface.
            for related in self.entities.values():
                if related.kind in ('plant', 'site_path'):
                    self.mark_dirty(related.id)
        elif entity.kind in ('stair', 'ramp'):
            # Vertical circulation geometry can cut any slab occupying the
            # upper-floor plane. In legacy/current projects this may include
            # both an upper room_floor and a lower room_roof/room_ceiling.
            for related in self.entities.values():
                if related.kind in ('room_floor', 'room_roof', 'room_ceiling', 'floor'):
                    self.mark_dirty(related.id)

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
            if not other or other.kind not in ('door', 'window', 'opening'):
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
        if entity.kind in ('door', 'window', 'opening'):
            if not entity.parent_id or entity.parent_id not in self.entities:
                raise ValueError('opening object must be attached to an existing host')
            host = self.entities[entity.parent_id]
            if host.kind == 'wall':
                from archforge.architecture.openings import validate_opening
                validate_opening(host.params, entity.params, entity.kind)
                self._validate_wall_opening_conflicts(entity)
            elif host.kind == 'pod' and entity.kind in ('door', 'window'):
                from archforge.architecture.openings import validate_pod_opening
                validate_pod_opening(host.params, entity.params, entity.kind)
            elif entity.kind == 'opening':
                raise ValueError('free architectural opening must be attached to a wall')
            else:
                raise ValueError('door/window host must be a wall or pod')
        elif entity.kind == 'structural_support':
            if not entity.parent_id or entity.parent_id not in self.entities:
                raise ValueError('structural support must be attached to a Column or Beam')
            host = self.entities[entity.parent_id]
            if host.kind not in ('structural_column','structural_beam'):
                raise ValueError('structural support host must be a Column or Beam')
            if str(host.params.get('role','structural')) != 'structural':
                raise ValueError('supports can only be attached to structural-role members')
            for cid in self.children.get(entity.parent_id, ()):
                other = self.entities.get(cid)
                if (
                    other is not None
                    and other.kind == 'structural_support'
                    and other.id != entity.id
                    and str(other.params.get('member_end')) == str(entity.params.get('member_end'))
                ):
                    raise ValueError('that structural member end already has a support')
        elif entity.kind == 'structural_load':
            if not entity.parent_id or entity.parent_id not in self.entities:
                raise ValueError('structural load must be attached to a Column or Beam')
            host = self.entities[entity.parent_id]
            if host.kind not in ('structural_column','structural_beam'):
                raise ValueError('structural load host must be a Column or Beam')
            if str(host.params.get('role','structural')) != 'structural':
                raise ValueError('loads can only be attached to structural-role members')
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
        if entity.parent_id and entity.kind in ('door', 'window', 'opening', 'structural_support', 'structural_load'):
            self.add_dependency(entity.parent_id, entity.id)
        if entity.kind == 'arboreal_branch':
            self.add_dependency(entity.params['core_id'], entity.id)
        elif entity.kind == 'mechanical_joint':
            self.add_dependency(entity.params['parent_part'], entity.id)
            self.add_dependency(entity.params['child_part'], entity.id)
        elif entity.kind == 'mechanical_mount':
            self.add_dependency(entity.params['host_id'], entity.id)
            self.add_dependency(entity.params['part_id'], entity.id)

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

    def active_level_name(self, tolerance=1e-5):
        """Name of the storey the work plane sits on.

        A fresh document keeps the generic 'XY' work-plane name at z=0, which
        is the Ground storey; resolve such planes by elevation.
        """
        name = str(self.work_plane.name)
        if name in self.levels:
            return name
        z = float(self.work_plane.origin[2])
        for level_name, level_z in self.levels.items():
            if abs(float(level_z) - z) <= tolerance:
                return str(level_name)
        return name

    def update(self, eid, changes):
        entity = self.get(eid)
        if entity.locked:
            raise PermissionError('entity is locked')
        params = entity.params.copy()
        params.update(changes)
        params = validate_params(entity.kind, params)
        candidate = entity.clone()
        candidate.params = params
        if entity.kind in ('door', 'window', 'opening', 'structural_support', 'structural_load', 'arboreal_branch', 'mechanical_joint', 'mechanical_mount'):
            self._validate_links(candidate)
        elif entity.kind in ('structural_column','structural_beam'):
            if str(params.get('role','structural')) != 'structural':
                attached=[
                    self.entities.get(cid) for cid in self.children.get(eid, ())
                    if cid in self.entities
                ]
                if any(child and child.kind in ('structural_support','structural_load') for child in attached):
                    raise ValueError('remove structural supports/loads before changing member Role away from Structural')
        elif entity.kind == 'wall':
            from archforge.architecture.openings import validate_opening
            for cid in self.children.get(eid, ()):
                child = self.entities.get(cid)
                if child and child.kind in ('door', 'window', 'opening'):
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
                elif entity.kind == 'mesh':
                    metadata = entity.params.get('metadata', {})
                    if metadata.get('semantic_type') == 'conduit':
                        refs = [metadata.get('start_node'), metadata.get('end_node')]
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
            if raw.get('kind') in ('door', 'window', 'opening', 'structural_support', 'structural_load', 'organic_opening_patch', 'mechanical_joint', 'mechanical_mount'):
                deferred.append(raw)
            else:
                doc.add(Entity(**raw))
        for raw in [r for r in deferred if r.get('kind') in ('door', 'window', 'opening', 'structural_support', 'structural_load')]:
            doc.add(Entity(**raw))
        for raw in [r for r in deferred if r.get('kind') not in ('door', 'window', 'opening', 'structural_support', 'structural_load')]:
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
