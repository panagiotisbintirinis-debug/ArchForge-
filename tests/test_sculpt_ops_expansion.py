from archforge.core.model import Document, Entity
from archforge.core.commands import CommandStack
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.sculpt import apply_brush_modifier
from archforge.geometry.selection import SurfaceHit, BrushSpec
from archforge.geometry.sculpt_transaction import SculptTransaction


def _wall():
    d=Document(); w=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2}); d.add(w)
    return d,w


def _raw(role,op,center,amount=.3,radius=1.2):
    return {'operation':op,'target':{'surface_role':role,'subregion':{'world_center':center,'radius':radius,'strength':1,'falloff':'smooth'}},'params':{'amount':amount},'enabled':True}


def test_inflate_and_recess_are_opposite_normal_displacements():
    d,w=_wall(); base=TessellatedPreviewBackend().evaluate(d).body(w.id).payload
    inflate=apply_brush_modifier(base,_raw('exterior','inflate',(2,.1,1.5),.25,1.8))
    recess=apply_brush_modifier(base,_raw('exterior','recess',(2,.1,1.5),.25,1.8))
    moved=[i for i,(a,b) in enumerate(zip(base.vertices,inflate.vertices)) if a!=b]
    assert moved
    for i in moved:
        assert inflate.vertices[i][1] > base.vertices[i][1]
        assert recess.vertices[i][1] < base.vertices[i][1]


def test_smooth_is_local_and_preserves_semantic_triangle_roles():
    d,w=_wall(); base=TessellatedPreviewBackend().evaluate(d).body(w.id).payload
    pulled=apply_brush_modifier(base,_raw('exterior','pull',(2,.1,1.5),.7,1.2))
    smoothed=apply_brush_modifier(pulled,_raw('exterior','smooth',(2,.1,1.5),.8,1.5))
    assert smoothed.vertices!=pulled.vertices
    assert smoothed.triangles==base.triangles
    assert smoothed.triangle_surfaces==base.triangle_surfaces


def test_crease_live_transaction_previews_and_commits_non_destructively():
    d,w=_wall(); stack=CommandStack(d); before=dict(w.params)
    tx=SculptTransaction(d,stack,SurfaceHit(w.id,'exterior',(2,.1,1.5),(0,1,0)),BrushSpec(1.5),'crease',.35)
    preview=tx.preview_mesh(); assert preview.vertices!=TessellatedPreviewBackend().evaluate(d).body(w.id).payload.vertices
    mid=tx.commit()
    assert mid in d.surface_modifiers and d.get(w.id).params==before and len(stack.done)==1


def test_inflate_recess_smooth_are_accepted_live_operations():
    for op in ('inflate','recess','smooth'):
        d,w=_wall(); stack=CommandStack(d)
        tx=SculptTransaction(d,stack,SurfaceHit(w.id,'exterior',(2,.1,1.5),(0,1,0)),BrushSpec(1.5),op,.2)
        assert tx.preview_mesh().triangle_surfaces
