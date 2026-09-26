from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import copy
from .model import Document, Entity, WorkPlane

class Command:
    def do(self,doc:Document): raise NotImplementedError
    def undo(self,doc:Document): raise NotImplementedError

@dataclass
class AddEntity(Command):
    entity: Entity
    def do(self,doc): doc.add(self.entity.clone())
    def undo(self,doc): doc.remove(self.entity.id)

@dataclass
class UpdateEntity(Command):
    eid:str; changes:Dict[str,Any]; before:Dict[str,Any]|None=None
    def do(self,doc):
        if self.before is None:self.before=copy.deepcopy(doc.get(self.eid).params)
        doc.update(self.eid,self.changes)
    def undo(self,doc):
        if self.before is not None:doc.update(self.eid,copy.deepcopy(self.before))

@dataclass
class UpdateEntities(Command):
    """Apply several semantic parameter updates as one undo/redo step."""
    changes:Dict[str,Dict[str,Any]]
    before:Dict[str,Dict[str,Any]]|None=None
    before_revisions:Dict[str,int]|None=None
    before_state:Optional[Dict[str,Any]]=None
    before_selection:Optional[List[str]]=None
    def do(self,doc):
        if self.before is None:
            self.before={eid:copy.deepcopy(doc.get(eid).params) for eid in self.changes}
            self.before_revisions={eid:doc.get(eid).revision for eid in self.changes}
            self.before_state=copy.deepcopy(doc.to_dict())
            self.before_selection=list(doc.selection)
        try:
            for eid,delta in self.changes.items():doc.update(eid,delta)
        except Exception:
            if self.before_state is not None:_restore_document_state(doc,self.before_state,self.before_selection or [])
            raise
    def undo(self,doc):
        if self.before_state is not None:_restore_document_state(doc,self.before_state,self.before_selection or [])


def _legacy_world_modifier(mod):
    """True only for pre-parametric modifier state that still needs command-time translation."""
    region=mod.target.subregion or {}
    return (
        mod.params.get('mode')!='mechanism_clearance'
        and 'uv_center' not in region
        and 'world_center' in region
        and isinstance(region.get('world_center'),(list,tuple))
        and len(region['world_center'])==3
    )

@dataclass
class MoveEntities(Command):
    ids:List[str]; dx:float;dy:float;dz:float=0.0;before:Dict[str,Dict[str,Any]]|None=None;before_modifiers:Dict[str,Any]|None=None
    def do(self,doc):
        if self.before is None:
            self.before={i:copy.deepcopy(doc.get(i).params) for i in self.ids}
            self.before_modifiers={mid:copy.deepcopy(m) for mid,m in doc.surface_modifiers.items() if m.target.owner_id in self.ids and _legacy_world_modifier(m)}
        for i in self.ids:
            e=doc.get(i); p=e.params
            if e.kind in ('box','mechanical_part'):doc.update(i,{'x':p['x']+self.dx,'y':p['y']+self.dy,'z':p['z']+self.dz})
            elif e.kind=='wall':doc.update(i,{'x1':p['x1']+self.dx,'x2':p['x2']+self.dx,'y1':p['y1']+self.dy,'y2':p['y2']+self.dy,'z':p['z']+self.dz})
            elif e.kind=='pod':doc.update(i,{'cx':p['cx']+self.dx,'cy':p['cy']+self.dy,'floor_level':p['floor_level']+self.dz})
            elif e.kind in ('floor','room'):
                doc.update(i,{'points':[(x+self.dx,y+self.dy) for x,y in p['points']], 'z':p['z']+self.dz})
            elif e.kind=='stair':
                if abs(float(self.dz))>1e-12:
                    raise ValueError('stairs can only move in XY; floor elevations remain linked')
                doc.update(i,{'x':p['x']+self.dx,'y':p['y']+self.dy})
        # Compatibility only: modern UV/local attachments are immutable semantic intent.
        # Old project files may still contain world-only sculpt centers, so translate those
        # until they can be migrated to an intrinsic surface frame.
        for mid,m in doc.surface_modifiers.items():
            if m.target.owner_id not in self.ids or not _legacy_world_modifier(m):continue
            c=m.target.subregion['world_center']
            m.target.subregion['world_center']=[c[0]+self.dx,c[1]+self.dy,c[2]+self.dz]
            doc.mark_dirty(m.target.owner_id)
    def undo(self,doc):
        for i,p in self.before.items():doc.update(i,copy.deepcopy(p))
        if self.before_modifiers:
            for mid,m in self.before_modifiers.items():
                doc.surface_modifiers[mid]=copy.deepcopy(m);doc.mark_dirty(m.target.owner_id)


@dataclass
class RotateEntities(Command):
    """Rotate supported semantic entities around their centroid or an explicit pivot."""
    ids: List[str]
    angle: float
    pivot: Optional[Tuple[float, float]] = None
    before: Dict[str, Dict[str, Any]] | None = None

    def do(self, doc: Document):
        if self.before is None:
            self.before = {i: copy.deepcopy(doc.get(i).params) for i in self.ids}
        import math
        r = math.radians(self.angle)
        c, s = math.cos(r), math.sin(r)
        for i in self.ids:
            e = doc.get(i)
            p = e.params
            if e.kind == 'pod':
                px, py = self.pivot if self.pivot is not None else (p['cx'], p['cy'])
                if self.pivot is not None:
                    dx, dy = p['cx'] - px, p['cy'] - py
                    ncx, ncy = px + dx * c - dy * s, py + dx * s + dy * c
                    doc.update(i, {'cx': ncx, 'cy': ncy, 'rotation': (p.get('rotation', 0.0) + self.angle) % 360.0})
                else:
                    doc.update(i, {'rotation': (p.get('rotation', 0.0) + self.angle) % 360.0})
            elif e.kind == 'box':
                px, py = self.pivot if self.pivot is not None else (p['x'], p['y'])
                if self.pivot is not None:
                    dx, dy = p['x'] - px, p['y'] - py
                    nx, ny = px + dx * c - dy * s, py + dx * s + dy * c
                    doc.update(i, {'x': nx, 'y': ny, 'rotation': (p.get('rotation', 0.0) + self.angle) % 360.0})
                else:
                    doc.update(i, {'rotation': (p.get('rotation', 0.0) + self.angle) % 360.0})
            elif e.kind == 'wall':
                px, py = self.pivot if self.pivot is not None else ((p['x1'] + p['x2']) / 2, (p['y1'] + p['y2']) / 2)
                def rot(x, y):
                    dx, dy = x - px, y - py
                    return px + dx * c - dy * s, py + dx * s + dy * c
                nx1, ny1 = rot(p['x1'], p['y1'])
                nx2, ny2 = rot(p['x2'], p['y2'])
                doc.update(i, {'x1': nx1, 'y1': ny1, 'x2': nx2, 'y2': ny2})

    def undo(self, doc: Document):
        if self.before is not None:
            for i, p in self.before.items():
                doc.update(i, copy.deepcopy(p))



def _restore_document_state(doc:Document,state:Dict[str,Any],selection:List[str]):
    """Restore a serialized semantic snapshot without replacing the live Document object."""
    restored=Document.from_dict(copy.deepcopy(state))
    doc.entities=restored.entities
    doc.children=restored.children
    doc.dependencies=restored.dependencies
    doc.levels=restored.levels
    doc.work_plane=restored.work_plane
    doc.materials=restored.materials
    doc.constructions=restored.constructions
    doc.room_data=restored.room_data
    doc.room_bindings=restored.room_bindings
    doc.surface_modifiers=restored.surface_modifiers
    doc.selection=[eid for eid in selection if eid in doc.entities]
    # Force derived geometry to rebuild after an undo restoration.
    doc.dirty=set(doc.entities)

@dataclass
class DeleteEntities(Command):
    """Delete semantic entities transactionally, including all cascade side effects."""
    ids:List[str]
    before_state:Optional[Dict[str,Any]]=None
    before_selection:Optional[List[str]]=None
    def do(self,doc):
        requested=list(dict.fromkeys(self.ids))
        if not requested:raise ValueError('delete requires at least one entity')
        if self.before_state is None:
            missing=[eid for eid in requested if eid not in doc.entities]
            if missing:raise KeyError(f"delete entity does not exist: {missing[0]}")
            self.before_state=copy.deepcopy(doc.to_dict())
            self.before_selection=list(doc.selection)
        for eid in requested:
            if eid in doc.entities:doc.remove(eid)
    def undo(self,doc):
        if self.before_state is None:return
        _restore_document_state(doc,self.before_state,self.before_selection or [])

class CreateRoomFloors(Command):
    """Create one topology-linked floor per persistent semantic room as one undo step."""
    def __init__(self,signatures:List[str],thickness:float=.15,offset_z:float=0.0):
        self.signatures=list(dict.fromkeys(signatures));self.thickness=float(thickness);self.offset_z=float(offset_z);self.entities:Dict[str,Entity]={}
    def do(self,doc):
        from archforge.architecture.rooms import find_room_face
        from archforge.architecture.room_identity import room_id_for_signature
        created=[]
        try:
            for sig in self.signatures:
                found=find_room_face(doc,sig)
                if found is None:raise ValueError('room signature is not currently active')
                face,z=found;room_id=room_id_for_signature(doc,sig,z=z)
                if any(e.kind=='room_floor' and (e.params.get('room_id')==room_id or e.params.get('room_signature')==sig) for e in doc.entities.values()):continue
                key=room_id or sig;e=self.entities.get(key)
                if e is None:
                    params={'room_signature':sig,'thickness':self.thickness,'offset_z':self.offset_z}
                    if room_id is not None:params['room_id']=room_id
                    e=Entity('room_floor',params,name='Auto Floor');self.entities[key]=e
                else:
                    e=e.clone();e.params['room_signature']=sig
                    if room_id is not None:e.params['room_id']=room_id
                doc.add(e);created.append(e.id)
                for wid in face.wall_ids:
                    if wid in doc.entities and e.id not in doc.dependencies.get(wid,set()):doc.add_dependency(wid,e.id)
        except Exception:
            for eid in reversed(created):
                if eid in doc.entities:doc.remove(eid)
            raise
    def undo(self,doc):
        for e in self.entities.values():
            if e.id in doc.entities:doc.remove(e.id)

class CreateRoomRoofs(Command):
    """Create topology-linked flat roof slabs at the common wall top elevation."""
    def __init__(
        self,
        signatures:List[str],
        thickness:float=.20,
        roof_type:str='flat',
        tolerance:float=1e-4,
    ):
        self.signatures=list(dict.fromkeys(signatures))
        self.thickness=float(thickness)
        self.roof_type=str(roof_type)
        self.tolerance=float(tolerance)
        self.entities:Dict[str,Entity]={}

    def do(self,doc):
        from archforge.architecture.rooms import find_room_face
        from archforge.architecture.room_identity import room_id_for_signature

        if self.roof_type != 'flat':
            raise ValueError('CreateRoomRoofs currently supports flat roofs only')

        created=[]
        try:
            for sig in self.signatures:
                found=find_room_face(doc,sig)
                if found is None:
                    raise ValueError('room signature is not currently active')
                face,base_z=found
                room_id=room_id_for_signature(doc,sig,z=base_z)

                if any(
                    e.kind=='room_roof'
                    and e.params.get('roof_type')=='flat'
                    and (
                        e.params.get('room_id')==room_id
                        or e.params.get('room_signature')==sig
                    )
                    for e in doc.entities.values()
                ):
                    continue

                tops=[]
                for wid in face.wall_ids:
                    wall=doc.get(wid)
                    tops.append(float(wall.params['z'])+float(wall.params['height']))
                if not tops:
                    raise ValueError('flat roof requires boundary walls')
                if max(tops)-min(tops)>self.tolerance:
                    raise ValueError(
                        'flat roof requires boundary walls with a common top elevation'
                    )

                top_z=sum(tops)/len(tops)
                offset_z=top_z-float(base_z)
                key=room_id or sig
                e=self.entities.get(key)
                if e is None:
                    params={
                        'room_signature':sig,
                        'thickness':self.thickness,
                        'offset_z':offset_z,
                        'roof_type':'flat',
                    }
                    if room_id is not None:
                        params['room_id']=room_id
                    e=Entity('room_roof',params,name='Flat Roof')
                    self.entities[key]=e
                else:
                    e=e.clone()
                    e.params['room_signature']=sig
                    e.params['offset_z']=offset_z
                    e.params['roof_type']='flat'
                    if room_id is not None:
                        e.params['room_id']=room_id

                doc.add(e)
                created.append(e.id)
                for wid in face.wall_ids:
                    if wid in doc.entities and e.id not in doc.dependencies.get(wid,set()):
                        doc.add_dependency(wid,e.id)
        except Exception:
            for eid in reversed(created):
                if eid in doc.entities:
                    doc.remove(eid)
            raise

    def undo(self,doc):
        for e in self.entities.values():
            if e.id in doc.entities:
                doc.remove(e.id)




class RouteAndConnectInfrastructure(Command):
    """Route between semantic endpoint anchors, then commit one authoritative mesh."""
    def __init__(
        self,
        start_entity_id,
        end_entity_id,
        diameter,
        system_type,
        *,
        grid_resolution=0.05,
    ):
        self.start_id = str(start_entity_id)
        self.end_id = str(end_entity_id)
        self.diameter = float(diameter)
        self.system_type = str(system_type)
        self.grid_resolution = float(grid_resolution)
        self.generated_id = f"mep_{self.start_id}_{self.end_id}"
        self.ids = [self.generated_id]
        self.route = None
        self._connect_command = None

    def do(self, doc):
        from archforge.core.router import MEPPathRouter
        if self.start_id not in doc.entities or self.end_id not in doc.entities:
            raise ValueError('MEP endpoints must exist in the authoritative Document')
        if self.route is None:
            router = MEPPathRouter(
                doc,
                grid_resolution=self.grid_resolution,
                clearance=max(0.0, self.diameter / 2.0),
                ignore_entity_ids={self.start_id, self.end_id},
            )
            start = router.entity_anchor(self.start_id)
            end = router.entity_anchor(self.end_id)
            self.route = router.compute_route(start, end)

        self._connect_command = ConnectInfrastructure(
            self.start_id,
            self.end_id,
            self.diameter,
            self.system_type,
            copy.deepcopy(self.route),
        )
        self._connect_command.do(doc)
        entity = doc.get(self.generated_id)
        metadata = copy.deepcopy(entity.params.get('metadata', {}))
        metadata['routing'] = {
            'algorithm': 'astar-3d',
            'grid_resolution': self.grid_resolution,
            'route_nodes': len(self.route),
        }
        doc.update(self.generated_id, {'metadata': metadata})

    def undo(self, doc):
        if self._connect_command is not None:
            self._connect_command.undo(doc)


class ConnectInfrastructure(Command):
    """Commit an MEP centerline as authoritative editable mesh topology."""
    def __init__(self, start_entity_id, end_entity_id, diameter, system_type, path_vertices):
        self.start_id = str(start_entity_id)
        self.end_id = str(end_entity_id)
        self.diameter = float(diameter)
        self.system_type = str(system_type)
        self.path = copy.deepcopy(path_vertices)
        self.generated_id = f"mep_{self.start_id}_{self.end_id}"
        self.ids = [self.generated_id]

    def do(self, doc):
        from archforge.core.model import validate_conduit_spec
        from archforge.geometry.mesh import generate_conduit_topology

        if self.start_id not in doc.entities or self.end_id not in doc.entities:
            raise ValueError('MEP endpoints must exist in the authoritative Document')
        if self.generated_id in doc.entities:
            raise ValueError('MEP connection already exists')

        spec = validate_conduit_spec(
            self.start_id,
            self.end_id,
            self.diameter,
            self.system_type,
            self.path,
        )
        segments = 12
        vertices, faces = generate_conduit_topology(
            spec['path_vertices'],
            spec['diameter'],
            segments=segments,
        )
        mesh_params = {
            'vertices': [list(vertex) for vertex in vertices],
            'faces': [list(face) for face in faces],
            'matrix': [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ],
            'metadata': {
                'semantic_type': 'conduit',
                'system_type': spec['system_type'],
                'diameter': spec['diameter'],
                'start_node': spec['start_node'],
                'end_node': spec['end_node'],
                'source_path_vertices': copy.deepcopy(spec['path_vertices']),
                'sweep_segments': segments,
            },
        }
        mesh_entity = Entity(
            kind='mesh',
            params=mesh_params,
            name=f"{spec['system_type']}_line",
            id=self.generated_id,
        )
        doc.add(mesh_entity)
        doc.add_dependency(self.start_id, self.generated_id)
        doc.add_dependency(self.end_id, self.generated_id)

    def undo(self, doc):
        if self.generated_id in doc.entities:
            doc.remove(self.generated_id)


@dataclass
class MoveVertices(Command):
    """Move one authoritative mesh vertex as a reversible model mutation."""
    eid: str
    vertex_index: int
    dx: float
    dy: float
    dz: float = 0.0
    before: Optional[List[float]] = None

    @property
    def ids(self):
        return (self.eid,)

    def do(self, doc: Document):
        entity = doc.get(self.eid)
        if entity.kind != 'mesh':
            raise ValueError('MoveVertices requires a mesh entity')
        vertices = copy.deepcopy(entity.params['vertices'])
        index = int(self.vertex_index)
        if index < 0 or index >= len(vertices):
            raise IndexError('mesh vertex index out of range')
        if self.before is None:
            self.before = list(vertices[index])
        vertex = vertices[index]
        vertices[index] = [
            float(vertex[0]) + float(self.dx),
            float(vertex[1]) + float(self.dy),
            float(vertex[2]) + float(self.dz),
        ]
        doc.update(self.eid, {'vertices': vertices})

    def undo(self, doc: Document):
        if self.before is None:
            return
        entity = doc.get(self.eid)
        if entity.kind != 'mesh':
            raise ValueError('MoveVertices requires a mesh entity')
        vertices = copy.deepcopy(entity.params['vertices'])
        index = int(self.vertex_index)
        if index < 0 or index >= len(vertices):
            raise IndexError('mesh vertex index out of range')
        vertices[index] = list(self.before)
        doc.update(self.eid, {'vertices': vertices})


@dataclass
class FreezeToMesh(Command):
    """Freeze one standalone pod into authoritative editable mesh geometry."""
    eid: str
    before: Optional[Entity] = None

    @property
    def ids(self):
        return (self.eid,)

    def _assert_freezable(self, doc: Document):
        entity = doc.get(self.eid)
        if entity.kind != 'pod':
            raise ValueError('FreezeToMesh currently supports pod entities only')
        if doc.children.get(self.eid):
            raise ValueError('cannot freeze a pod that still hosts child entities')
        if doc.dependencies.get(self.eid):
            raise ValueError('cannot freeze a pod with active semantic dependents')
        if doc.modifier_ids_for_owner(self.eid):
            raise ValueError('cannot freeze a pod with active surface modifiers')
        return entity

    def do(self, doc: Document):
        from archforge.geometry.mesh import _pod_mesh
        from archforge.core.model import validate_params

        source = self._assert_freezable(doc)
        if self.before is None:
            self.before = source.clone()
        payload = _pod_mesh(source.params)
        params = {
            'vertices': [list(v) for v in payload.vertices],
            'faces': [list(face) for face in payload.triangles],
            'matrix': [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ],
            'metadata': {
                'semantic_type': 'frozen_mesh',
                'source_kind': 'pod',
            },
        }
        frozen = Entity(
            'mesh',
            validate_params('mesh', params),
            name=source.name,
            id=source.id,
            parent_id=source.parent_id,
            locked=source.locked,
            visible=source.visible,
            revision=source.revision + 1,
        )
        doc.entities[self.eid] = frozen
        doc.mark_dirty(self.eid)

    def undo(self, doc: Document):
        if self.before is None:
            return
        doc.entities[self.eid] = self.before.clone()
        doc.mark_dirty(self.eid)


@dataclass
class SetWorkPlane(Command):
    work_plane: WorkPlane
    before: Optional[WorkPlane] = None
    def do(self, doc: Document):
        if self.before is None:
            self.before = copy.deepcopy(doc.work_plane)
        doc.work_plane = copy.deepcopy(self.work_plane)
    def undo(self, doc: Document):
        if self.before is not None:
            doc.work_plane = copy.deepcopy(self.before)

@dataclass
class CreateFloorLevel(Command):
    """Create one named storey elevation and activate it as the current work plane."""
    name: str
    elevation: float
    before_levels: Optional[Dict[str, float]] = None
    before_work_plane: Optional[WorkPlane] = None

    def do(self, doc: Document):
        name = str(self.name).strip()
        if not name:
            raise ValueError('floor level name must not be empty')
        if self.before_levels is None:
            if name in doc.levels:
                raise ValueError(f"level '{name}' already exists")
            self.before_levels = copy.deepcopy(doc.levels)
            self.before_work_plane = copy.deepcopy(doc.work_plane)
        elevation = float(self.elevation)
        if any(abs(float(z) - elevation) <= 1e-6 for level_name, z in doc.levels.items() if level_name != name):
            raise ValueError('another floor level already uses this elevation')
        doc.levels[name] = elevation
        wp = doc.work_plane
        doc.work_plane = WorkPlane(
            name=name,
            origin=(float(wp.origin[0]), float(wp.origin[1]), elevation),
            u=tuple(wp.u),
            v=tuple(wp.v),
        )
        doc.selection = []

    def undo(self, doc: Document):
        if self.before_levels is None or self.before_work_plane is None:
            return
        doc.levels = copy.deepcopy(self.before_levels)
        doc.work_plane = copy.deepcopy(self.before_work_plane)
        doc.selection = []


@dataclass
class SetLevel(Command):
    name: str
    elevation: float
    before: Optional[float] = None
    had_before: bool = False
    def do(self, doc: Document):
        if not self.had_before and self.name in doc.levels:
            self.before = doc.levels[self.name]
            self.had_before = True
        doc.levels[self.name] = float(self.elevation)
    def undo(self, doc: Document):
        if self.had_before:
            doc.levels[self.name] = self.before
        else:
            doc.levels.pop(self.name, None)

@dataclass
class RemoveLevel(Command):
    name: str
    before: Optional[float] = None
    def do(self, doc: Document):
        if self.name not in doc.levels:
            raise KeyError(f"level '{self.name}' does not exist")
        self.before = doc.levels.pop(self.name)
    def undo(self, doc: Document):
        if self.before is not None:
            doc.levels[self.name] = self.before

@dataclass
class SetMaterial(Command):
    material_id: str
    properties: Dict[str, Any]
    before: Optional[Dict[str, Any]] = None
    had_before: bool = False
    def do(self, doc: Document):
        if not self.had_before and self.material_id in doc.materials:
            self.before = copy.deepcopy(doc.materials[self.material_id])
            self.had_before = True
        doc.materials[self.material_id] = copy.deepcopy(self.properties)
    def undo(self, doc: Document):
        if self.had_before:
            doc.materials[self.material_id] = copy.deepcopy(self.before)
        else:
            doc.materials.pop(self.material_id, None)

@dataclass
class SetConstruction(Command):
    construction_id: str
    properties: Dict[str, Any]
    before: Optional[Dict[str, Any]] = None
    had_before: bool = False
    def do(self, doc: Document):
        if not self.had_before and self.construction_id in doc.constructions:
            self.before = copy.deepcopy(doc.constructions[self.construction_id])
            self.had_before = True
        doc.constructions[self.construction_id] = copy.deepcopy(self.properties)
    def undo(self, doc: Document):
        if self.had_before:
            doc.constructions[self.construction_id] = copy.deepcopy(self.before)
        else:
            doc.constructions.pop(self.construction_id, None)

@dataclass
class AssignConstruction(Command):
    eid: str
    construction_id: Optional[str] = None
    material_id: Optional[str] = None
    before_construction: Optional[str] = None
    before_material: Optional[str] = None
    had_before: bool = False
    def do(self, doc: Document):
        e = doc.get(self.eid)
        if not self.had_before:
            self.before_construction = e.params.get('construction_id')
            self.before_material = e.params.get('material_id')
            self.had_before = True
        changes = {}
        if self.construction_id is not None:
            changes['construction_id'] = self.construction_id
        if self.material_id is not None:
            changes['material_id'] = self.material_id
        doc.update(self.eid, changes)
    def undo(self, doc: Document):
        changes = {}
        if self.construction_id is not None:
            if self.before_construction is not None:
                changes['construction_id'] = self.before_construction
            else:
                doc.get(self.eid).params.pop('construction_id', None)
        if self.material_id is not None:
            if self.before_material is not None:
                changes['material_id'] = self.before_material
            else:
                doc.get(self.eid).params.pop('material_id', None)
        if changes:
            doc.update(self.eid, changes)
        else:
            doc.mark_dirty(self.eid)

class CommandStack:
    def __init__(self,doc):self.doc=doc;self.done=[];self.undone=[]
    @property
    def can_undo(self) -> bool:
        return bool(self.done)
    @property
    def can_redo(self) -> bool:
        return bool(self.undone)
    def execute(self,c):c.do(self.doc);self.done.append(c);self.undone.clear()
    def undo(self):
        if not self.done:return
        c=self.done.pop();c.undo(self.doc);self.undone.append(c)
    def redo(self):
        if not self.undone:return
        c=self.undone.pop();c.do(self.doc);self.done.append(c)
