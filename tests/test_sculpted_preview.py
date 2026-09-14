from archforge.core.model import Document, Entity
from archforge.geometry.selection import SurfaceHit, BrushSpec, sculpt_modifier_from_hit
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.sculpt import SculptedPreviewBackend


def _wall_doc():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2});d.add(w);return d,w


def test_pull_moves_only_evaluated_mesh_not_semantic_wall():
    d,w=_wall_doc();before=dict(w.params)
    hit=SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0))
    mod=sculpt_modifier_from_hit(d,hit,BrushSpec(2.0,1.0,'constant'),'pull',.5);d.add_surface_modifier(mod)
    base=TessellatedPreviewBackend().evaluate(d).body(w.id).payload
    sculpt=SculptedPreviewBackend().evaluate(d).body(w.id)
    assert d.get(w.id).params==before
    assert sculpt.modifiers_applied is True
    assert sculpt.modifier_ids==(mod.id,)
    assert sculpt.payload.vertices!=base.vertices
    assert sculpt.payload.vertices[0][1] > base.vertices[0][1]


def test_push_moves_opposite_surface_normal():
    d,w=_wall_doc()
    hit=SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0))
    mod=sculpt_modifier_from_hit(d,hit,BrushSpec(2.0,1.0,'constant'),'push',.25);d.add_surface_modifier(mod)
    base=TessellatedPreviewBackend().evaluate(d).body(w.id).payload
    sculpt=SculptedPreviewBackend().evaluate(d).body(w.id).payload
    # exterior is y=+thickness/2 for this wall; push moves inward (-y)
    assert sculpt.vertices[0][1] < base.vertices[0][1]


def test_disabling_modifier_restores_base_geometry():
    d,w=_wall_doc();hit=SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0))
    mod=sculpt_modifier_from_hit(d,hit,BrushSpec(2.0,1.0,'constant'),'pull',.4);d.add_surface_modifier(mod)
    changed=SculptedPreviewBackend().evaluate(d).body(w.id).payload.vertices
    d.update_surface_modifier(mod.id,enabled=False)
    restored=SculptedPreviewBackend().evaluate(d).body(w.id).payload.vertices
    base=TessellatedPreviewBackend().evaluate(d).body(w.id).payload.vertices
    assert changed!=base and restored==base


def test_unsupported_modifier_is_reported_without_claiming_completion():
    d,w=_wall_doc();hit=SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0))
    mod=sculpt_modifier_from_hit(d,hit,BrushSpec(1.0),'inflate',.2);d.add_surface_modifier(mod)
    result=SculptedPreviewBackend().evaluate(d);body=result.body(w.id)
    assert body.modifiers_applied is False
    assert any(i.code=='preview_modifier_unapplied' for i in result.issues)
