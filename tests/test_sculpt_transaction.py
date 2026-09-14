import pytest
from archforge.core.model import Document, Entity
from archforge.core.commands import CommandStack
from archforge.geometry.selection import SurfaceHit, BrushSpec
from archforge.geometry.sculpt_transaction import SculptTransaction, begin_sculpt_from_ray
from archforge.geometry.mesh import TessellatedPreviewBackend


def _setup():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2});d.add(w)
    return d,w,CommandStack(d)


def test_live_preview_does_not_mutate_document_or_history():
    d,w,stack=_setup();base=TessellatedPreviewBackend().evaluate(d).body(w.id).payload.vertices
    tx=SculptTransaction(d,stack,SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0)),BrushSpec(2,1,'constant'),'pull',.3)
    preview=tx.preview_mesh().vertices
    assert preview!=base
    assert d.surface_modifiers=={} and stack.done==[]


def test_numeric_adjustment_then_commit_is_one_undoable_action():
    d,w,stack=_setup();tx=SculptTransaction(d,stack,SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0)),BrushSpec(1),'pull',.1)
    hud=tx.update(amount=.45,radius=2.2,strength=.7)
    assert hud.values=={'amount':.45,'radius':2.2,'strength':.7}
    mid=tx.commit();assert mid in d.surface_modifiers and len(stack.done)==1
    assert d.surface_modifiers[mid].params['amount']==.45
    stack.undo();assert mid not in d.surface_modifiers
    stack.redo();assert mid in d.surface_modifiers


def test_cancel_leaves_no_modifier():
    d,w,stack=_setup();tx=SculptTransaction(d,stack,SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0)),BrushSpec(1),'push',.2)
    tx.cancel();assert d.surface_modifiers=={} and stack.done==[]
    with pytest.raises(RuntimeError):tx.commit()


def test_transaction_rejects_unsupported_live_operation():
    d,w,stack=_setup()
    with pytest.raises(ValueError):SculptTransaction(d,stack,SurfaceHit(w.id,'exterior',(0,.1,0),(0,1,0)),BrushSpec(1),'cut',.2)


def test_viewport_ray_can_begin_preview_and_commit_semantic_sculpt():
    d,w,stack=_setup()
    # Approach +normal side of wall from above Y and shoot inward.
    tx=begin_sculpt_from_ray(d,stack,(2,2,1.5),(0,-1,0),BrushSpec(.7,1,'smooth'),'pull',.25)
    assert tx is not None
    assert tx.hit.owner_id==w.id and tx.hit.surface_role=='exterior'
    assert tx.preview_mesh().vertices!=TessellatedPreviewBackend().evaluate(d).body(w.id).payload.vertices
    mid=tx.commit()
    assert d.surface_modifiers[mid].target.owner_id==w.id
    assert d.surface_modifiers[mid].target.surface_role=='exterior'


def test_viewport_ray_miss_does_not_create_transaction_or_history():
    d,w,stack=_setup()
    tx=begin_sculpt_from_ray(d,stack,(20,20,20),(0,0,1),BrushSpec(1),'pull',.2)
    assert tx is None
    assert not d.surface_modifiers and not stack.done
