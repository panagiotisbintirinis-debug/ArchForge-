"""A colour variant belongs to the project; changing it is one undo command."""
import copy
import uuid
from archforge.core.commands import CompositeCommand, SetMaterial, UpdateEntity
from archforge.rendering.materials import material_spec
from archforge.rendering import user_materials as um


def apply_color(window, eid, color, role=None, base_id=None):
    e=window.doc.get(eid)
    color=um.normalise_color(color)
    if color is None: raise ValueError('Μη έγκυρο χρώμα')
    p=e.params
    roles = [role] if isinstance(role, str) else list(role or [])
    old=(p.get('surface_materials') or {}).get(roles[0]) if roles else None
    old=base_id or old or p.get('material_id')
    spec=copy.deepcopy(material_spec(old,window.doc) or um.build_spec('Χρώμα αντικειμένου'))
    spec.update(name=f"{spec['name']} · {color}", color=color, user=True)
    mid='user_color_'+uuid.uuid4().hex
    if roles:
        surfaces=dict(p.get('surface_materials') or {})
        for target in roles: surfaces[target]=mid
        changes={'surface_materials':surfaces}
    else:
        changes={'material_id':mid,'surface_materials':{}}
    window.stack.execute(CompositeCommand([SetMaterial(mid,spec),UpdateEntity(eid,changes)],label='Χρώμα'))
    window.doc.select([eid]); window._redraw_views(all_views=True); window.refresh_inspector()
    return mid
