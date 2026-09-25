from archforge.core.model import Document, Entity
from archforge.geometry.selection import SurfaceHit, BrushSpec, sculpt_modifier_from_hit
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.sculpt import SculptedPreviewBackend


def _wall_doc():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2});d.add(w);return d,w


def test_pull_moves_only_evaluated_mesh_not_semantic_wall():
    d,w=_wall_doc();before=dict(w.params);hit=SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0))
    mod=sculpt_modifier_from_hit(d,hit,BrushSpec(2.0,1.0,'constant'),'pull',.5);d.add_surface_modifier(mod)
    base=TessellatedPreviewBackend().evaluate(d).body(w.id).payload; sculpt=SculptedPreviewBackend().evaluate(d).body(w.id)
    assert d.get(w.id).params==before and sculpt.modifiers_applied is True and sculpt.modifier_ids==(mod.id,)
    assert sculpt.payload.vertices!=base.vertices and sculpt.payload.vertices[0][1]>base.vertices[0][1]


def test_small_brush_deforms_local_region_not_whole_wall():
    d,w=_wall_doc()
    hit=SurfaceHit(w.id,'exterior',(2,.1,1.5),(0,1,0))
    mod=sculpt_modifier_from_hit(d,hit,BrushSpec(.65,1.0,'smooth'),'pull',.35)
    d.add_surface_modifier(mod)

    # Active wall sculpting intentionally uses a denser preview mesh than the ordinary
    # viewport mesh. Compare like-for-like dense geometry instead of relying on stale
    # coarse-mesh vertex indices.
    dense_base=SculptedPreviewBackend(
        dense_entity_ids={w.id},
        wall_target_step=.15,
    )
    raw=d.surface_modifiers[mod.id].to_dict()
    d.remove_surface_modifier(mod.id)
    base=dense_base.evaluate(d).body(w.id).payload
    d.add_surface_modifier(mod)
    sculpt=SculptedPreviewBackend().evaluate(d).body(w.id).payload

    assert len(base.vertices)==len(sculpt.vertices)
    exterior={
        i
        for ti,t in enumerate(base.triangles)
        if base.triangle_surfaces[ti]=='exterior'
        for i in t
    }
    moved=[i for i in exterior if sculpt.vertices[i]!=base.vertices[i]]
    unchanged=[i for i in exterior if sculpt.vertices[i]==base.vertices[i]]
    assert moved and unchanged
    assert max(
        ((base.vertices[i][0]-2.0)**2 + (base.vertices[i][2]-1.5)**2)**0.5
        for i in moved
    ) < .65 + 1e-9


def test_push_moves_opposite_surface_normal():
    d,w=_wall_doc();hit=SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0));mod=sculpt_modifier_from_hit(d,hit,BrushSpec(2.0,1.0,'constant'),'push',.25);d.add_surface_modifier(mod)
    base=TessellatedPreviewBackend().evaluate(d).body(w.id).payload;sculpt=SculptedPreviewBackend().evaluate(d).body(w.id).payload
    assert sculpt.vertices[0][1]<base.vertices[0][1]


def test_disabling_modifier_restores_base_geometry():
    d,w=_wall_doc();hit=SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0));mod=sculpt_modifier_from_hit(d,hit,BrushSpec(2.0,1.0,'constant'),'pull',.4);d.add_surface_modifier(mod)
    changed=SculptedPreviewBackend().evaluate(d).body(w.id).payload.vertices;d.update_surface_modifier(mod.id,enabled=False)
    restored=SculptedPreviewBackend().evaluate(d).body(w.id).payload.vertices;base=TessellatedPreviewBackend().evaluate(d).body(w.id).payload.vertices
    assert changed!=base and restored==base


def test_inflate_is_now_evaluated_without_losing_semantic_wall():
    d,w=_wall_doc();before=dict(w.params);hit=SurfaceHit(w.id,'exterior',(2,.1,1.5),(0,1,0));mod=sculpt_modifier_from_hit(d,hit,BrushSpec(1.2),'inflate',.2);d.add_surface_modifier(mod)
    result=SculptedPreviewBackend().evaluate(d);body=result.body(w.id)
    assert body.modifiers_applied is True and body.modifier_ids==(mod.id,) and d.get(w.id).params==before
    assert not any(i.code=='preview_modifier_unapplied' for i in result.issues)


def test_still_unsupported_cut_is_reported_without_claiming_completion():
    d,w=_wall_doc();hit=SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0));mod=sculpt_modifier_from_hit(d,hit,BrushSpec(1.0),'cut',.2);d.add_surface_modifier(mod)
    result=SculptedPreviewBackend().evaluate(d);body=result.body(w.id)
    assert body.modifiers_applied is False and any(i.code=='preview_modifier_unapplied' for i in result.issues)
