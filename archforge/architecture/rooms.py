from __future__ import annotations

from math import hypot
from typing import Optional

from archforge.core.model import Entity
from archforge.architecture.topology import room_faces
from archforge.architecture.room_identity import reconcile_room_bindings, room_id_for_signature


ROOM_SLAB_KINDS=frozenset({'room_floor','room_ceiling','room_foundation','room_roof'})


def find_room_face(doc, signature: str, tolerance: float = 1e-5):
    """Find an active topological room face by its current signature."""
    levels=sorted({float(e.params['z']) for e in doc.entities.values() if e.kind=='wall' and e.visible})
    for z in levels:
        for face in room_faces(doc,tolerance=tolerance,z=z):
            if face.signature==signature:
                return face,z
    return None


def find_room_face_by_id(doc, room_id: str, tolerance: float = 1e-5):
    """Resolve a persistent semantic room ID to its currently enclosed topology face."""
    levels=sorted({float(e.params['z']) for e in doc.entities.values() if e.kind=='wall' and e.visible})
    if not levels:
        levels=[float(doc.work_plane.origin[2])]
    for z in levels:
        for face,rid in reconcile_room_bindings(doc,z=z,tolerance=tolerance):
            if rid==room_id:
                return face,z
    return None


def create_room_floor(doc, signature: str, thickness: float = 0.15, offset_z: float = 0.0, name: str = 'Auto Floor') -> Entity:
    """Create a semantic floor linked to a persistent room identity."""
    found=find_room_face(doc,signature)
    if found is None:
        raise ValueError('room signature is not currently active')
    face,z=found
    room_id=room_id_for_signature(doc,signature,z=z)
    params={'room_signature':signature,'thickness':float(thickness),'offset_z':float(offset_z)}
    if room_id is not None:params['room_id']=room_id
    e=Entity('room_floor',params,name=name)
    doc.add(e)
    for wid in face.wall_ids:
        if wid in doc.entities and e.id not in doc.dependencies.get(wid,set()):
            doc.add_dependency(wid,e.id)
    return e


def _flat_roof_outer_polygon(doc, face, tolerance: float):
    """Offset each room boundary edge to its wall's exterior face and miter corners."""
    polygon=[tuple(q) for q in face.polygon]
    if len(polygon)<3:
        return polygon
    signed_area=.5*sum(
        polygon[i][0]*polygon[(i+1)%len(polygon)][1]
        - polygon[(i+1)%len(polygon)][0]*polygon[i][1]
        for i in range(len(polygon))
    )
    if abs(signed_area)<=tolerance:
        return polygon
    orientation=1.0 if signed_area>0 else -1.0
    boundary_walls=[doc.get(wid) for wid in face.wall_ids if wid in doc.entities]
    lines=[]
    for i,a in enumerate(polygon):
        b=polygon[(i+1)%len(polygon)]
        dx=b[0]-a[0];dy=b[1]-a[1];length=hypot(dx,dy)
        if length<=tolerance:
            return polygon
        wall=None
        for candidate in boundary_walls:
            p=candidate.params
            wx=float(p['x2'])-float(p['x1']);wy=float(p['y2'])-float(p['y1'])
            wlen=hypot(wx,wy)
            if wlen<=tolerance:
                continue
            cross=abs(dx*wy-dy*wx)/(length*wlen)
            distance=abs((a[0]-float(p['x1']))*wy-(a[1]-float(p['y1']))*wx)/wlen
            if cross<=tolerance and distance<=tolerance:
                wall=candidate;break
        if wall is None:
            return polygon
        half=.5*float(wall.params.get('thickness',0.0))
        nx=orientation*dy/length;ny=-orientation*dx/length
        lines.append(((a[0]+nx*half,a[1]+ny*half),(dx,dy)))

    out=[]
    for i in range(len(lines)):
        p0,d0=lines[i-1];p1,d1=lines[i]
        den=d0[0]*d1[1]-d0[1]*d1[0]
        if abs(den)<=tolerance:
            out.append(p1);continue
        qx=p1[0]-p0[0];qy=p1[1]-p0[1]
        t=(qx*d1[1]-qy*d1[0])/den
        out.append((p0[0]+t*d0[0],p0[1]+t*d0[1]))
    return out


def room_slab_geometry(doc, slab_entity: Entity, tolerance: float = 1e-5) -> Optional[dict]:
    """Resolve any inferred room slab against the room's current live topology."""
    if slab_entity.kind not in ROOM_SLAB_KINDS:
        raise ValueError('entity is not a derived room slab')
    p=slab_entity.params
    room_id=p.get('room_id')
    found=find_room_face_by_id(doc,room_id,tolerance=tolerance) if room_id else find_room_face(doc,p['room_signature'],tolerance=tolerance)
    if found is None:
        return None
    face,base_z=found
    z=base_z+float(p.get('offset_z',0.0))
    points=[tuple(q) for q in face.polygon]
    if slab_entity.kind=='room_roof' and p.get('roof_type','flat')=='flat':
        points=_flat_roof_outer_polygon(doc,face,tolerance)
    return {'points':points,
            'z':z,
            'thickness':float(p['thickness']),
            'room_id':room_id,
            'room_signature':face.signature,
            'wall_ids':tuple(face.wall_ids)}


def room_floor_geometry(doc, floor_entity: Entity, tolerance: float = 1e-5) -> Optional[dict]:
    """Resolve a room floor's live polygon; return None while its room is not closed."""
    if floor_entity.kind!='room_floor':
        raise ValueError('entity is not a room_floor')
    return room_slab_geometry(doc,floor_entity,tolerance=tolerance)
