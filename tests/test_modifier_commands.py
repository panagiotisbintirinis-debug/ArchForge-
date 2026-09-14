from archforge.core.commands import CommandStack
from archforge.core.model import Document,Entity
from archforge.core.modifiers import SurfaceModifier,SurfaceRef
from archforge.core.modifier_commands import AddSurfaceModifier,UpdateSurfaceModifier,RemoveSurfaceModifier


def setup():
    doc=Document();w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':5,'y2':0,'height':3,'thickness':0.2});doc.add(w);return doc,w


def test_add_sculpt_is_one_undoable_command():
    doc,w=setup();stack=CommandStack(doc);m=SurfaceModifier(SurfaceRef(w.id,'exterior',{}),'pull',{'amount':0.2})
    stack.execute(AddSurfaceModifier(m));assert m.id in doc.surface_modifiers
    stack.undo();assert m.id not in doc.surface_modifiers
    stack.redo();assert doc.surface_modifiers[m.id].params['amount']==0.2


def test_update_sculpt_undo_restores_previous_amount():
    doc,w=setup();m=SurfaceModifier(SurfaceRef(w.id,'exterior',{}),'pull',{'amount':0.2});doc.add_surface_modifier(m);stack=CommandStack(doc)
    stack.execute(UpdateSurfaceModifier(m.id,{'params':{'amount':0.8}}));assert doc.surface_modifiers[m.id].params['amount']==0.8
    stack.undo();assert doc.surface_modifiers[m.id].params['amount']==0.2
    stack.redo();assert doc.surface_modifiers[m.id].params['amount']==0.8


def test_remove_sculpt_can_be_undone_without_changing_wall_semantics():
    doc,w=setup();original=dict(w.params);m=SurfaceModifier(SurfaceRef(w.id,'exterior',{}),'pull',{'amount':0.2});doc.add_surface_modifier(m);stack=CommandStack(doc)
    stack.execute(RemoveSurfaceModifier(m.id));assert m.id not in doc.surface_modifiers
    stack.undo();assert m.id in doc.surface_modifiers
    assert doc.get(w.id).params==original
