"""Editable appearance of the already-solid wall/slab joint in our fixtures.

This is a paint/finish assignment, not a cladding thickness or a replacement
for missing geometry. No roof/floor elevation or structural section is changed.
"""
from archforge.core.commands import UpdateEntity


def finish_facade_joints(doc,stack):
    for e in list(doc.entities.values()):
        face_map=dict(e.params.get('surface_materials') or {})
        if e.kind=='wall' and ('-wall-' in e.id or '-split-wall-' in e.id):
            face_map.update(exterior='plaster_white',interior='plaster_white')
        elif e.kind in ('floor','room_floor','room_roof','room_ceiling'):
            face_map['edge']='plaster_white'
        else:continue
        stack.execute(UpdateEntity(e.id,{'surface_materials':face_map}))
