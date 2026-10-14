"""Eyedropper and painter: the sampled finish is derived from the Document."""
import copy
import uuid
from archforge.core.commands import CompositeCommand, SetMaterial, UpdateEntity
from archforge.rendering.materials import material_spec


def canonical_role(entity, role=None, xy=None):
    role = str(role or '')
    if entity.kind in ('door', 'window') and role.startswith(entity.kind + '_'):
        role = role.split('_', 1)[1]
    if entity.kind == 'wall' and role not in ('exterior', 'interior') and xy:
        p=entity.params; x,y=xy
        role='exterior' if (p['x2']-p['x1'])*(y-p['y1'])-(p['y2']-p['y1'])*(x-p['x1'])>=0 else 'interior'
    return role if role not in ('', 'body', 'default', 'placeholder', 'marker', entity.kind) else None


class MaterialBrush:
    def __init__(self, window):
        self.window = window
        self.sampled = None
        self.whole_object = False

    def sample(self, eid, role=None, xy=None):
        w=self.window; e=w.doc.get(eid); role=canonical_role(e,role,xy)
        mid=(e.params.get('surface_materials') or {}).get(role) or e.params.get('material_id')
        spec=material_spec(mid,w.doc)
        if spec is None:
            # Use the same unselected, authoritative scene that renders the surface,
            # including a library object's original palette and roof/joinery defaults.
            from archforge.rendering.scene import build_pbr_scene_payload
            evaluation=w.pbr_view._evaluation_cache.sync(w.doc)
            objects=build_pbr_scene_payload(evaluation,(),doc=w.doc)['objects']
            matches=[o for o in objects if o['id']==eid and (not role
                or canonical_role(e, str(o.get('render_part', '')).split(':')[-1]) == role
                or any(canonical_role(e,r)==role for r in o.get('surfaces',()))) ]
            if not matches: raise ValueError('Δεν βρέθηκε επιφάνεια για λήψη δείγματος')
            spec=copy.deepcopy(matches[0]['material'])
            mid=spec.get('material_id')
            resolved=material_spec(mid,w.doc)
            spec=dict(resolved) if resolved else { k:v for k,v in spec.items() if k not in ('emissive','emissiveIntensity','pattern_key','material_id','material_name')}
            spec.setdefault('name','Δείγμα επιφάνειας '+str(spec.get('color','')))
            spec.setdefault('category','Δείγματα επιφανειών')
            spec.setdefault('use',['επιφάνεια'])
        self.sampled=(mid,copy.deepcopy(dict(spec)))
        w.statusBar().showMessage('Δείγμα: '+str(spec['name'])+' — κλικ για εφαρμογή · Esc για τέλος')
        return self.sampled

    def apply(self,eid,role=None,xy=None):
        if not self.sampled: raise ValueError('Πάρε πρώτα δείγμα από μια επιφάνεια')
        w=self.window; e=w.doc.get(eid)
        role=None if self.whole_object else canonical_role(e,role,xy)
        mid,spec=self.sampled
        commands=[]
        if not mid or material_spec(mid,w.doc)!=spec:
            mid='user_sample_'+uuid.uuid4().hex
            commands.append(SetMaterial(mid,dict(spec,user=True)))
        elif mid not in w.doc.materials:
            from archforge.rendering.user_materials import is_user_material
            if is_user_material(mid): commands.append(SetMaterial(mid,spec))
        if role:
            surfaces=dict(e.params.get('surface_materials') or {}); surfaces[role]=mid
            changes={'surface_materials':surfaces}
        else:
            changes={'material_id':mid,'surface_materials':{}}
        commands.append(UpdateEntity(eid,changes))
        w.stack.execute(CompositeCommand(commands,label='Βαφή υλικού'))
        w._redraw_views(all_views=True); w.refresh_inspector()
        w.statusBar().showMessage('Εφαρμόστηκε το δείγμα — Ctrl+Z για αναίρεση · Esc για τέλος')
        return mid

    def click(self,eid,role=None,xy=None):
        if not eid or eid not in self.window.doc.entities: return
        try:
            if self.sampled is None: self.sample(eid,role,xy)
            else: self.apply(eid,role,xy)
        except (KeyError,ValueError,PermissionError) as exc:
            self.window.statusBar().showMessage(str(exc),5000)
