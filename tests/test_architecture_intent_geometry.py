from archforge.core.model import Document,Entity
from archforge.architecture.intent import infer_architecture
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.surfaces import surface_roles
from archforge.geometry.selection import SurfaceHit,BrushSpec,sculpt_modifier_from_hit
from archforge.geometry.sculpt import SculptedPreviewBackend


def _house():
 d=Document()
 for a,b in [((0,0),(5,0)),((5,0),(5,4)),((5,4),(0,4)),((0,4),(0,0))]:d.add(Entity('wall',{'x1':a[0],'y1':a[1],'x2':b[0],'y2':b[1],'z':0,'height':2.8,'thickness':.2}))
 infer_architecture(d);return d

def test_inferred_house_elements_have_real_preview_geometry():
 d=_house();ev=TessellatedPreviewBackend().evaluate(d)
 for e in d.entities.values():
  if e.kind.startswith('room_'):
   b=ev.body(e.id);assert b.payload.vertices and b.payload.triangles

def test_ceiling_and_roof_are_sculptable_not_locked_assumptions():
 d=_house();ceiling=next(e for e in d.entities.values() if e.kind=='room_ceiling');roof=next(e for e in d.entities.values() if e.kind=='room_roof')
 assert 'bottom' in surface_roles(d,ceiling.id) and 'top' in surface_roles(d,roof.id)
 hit=SurfaceHit(ceiling.id,'bottom',(2.5,2,2.68),(0,0,-1));mod=sculpt_modifier_from_hit(d,hit,BrushSpec(1.5),'recess',.2);d.add_surface_modifier(mod)
 body=SculptedPreviewBackend().evaluate(d).body(ceiling.id);assert body.modifiers_applied is True and body.modifier_ids==(mod.id,)
