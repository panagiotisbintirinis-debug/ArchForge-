import archforge.core.commands as commands
from archforge.core.model import Document, Entity
from archforge.core.modifiers import SurfaceModifier, SurfaceRef


def _delete_command():
    cls=getattr(commands,'DeleteEntities',None)
    assert cls is not None, 'transactional DeleteEntities command is required'
    return cls


def test_delete_undo_redo_restores_child_opening_modifier_and_selection():
    doc=Document();stack=commands.CommandStack(doc)
    wall=Entity('wall',{'x1':0,'y1':0,'x2':5,'y2':0,'z':0,'height':2.8,'thickness':.2});doc.add(wall)
    door=Entity('door',{'offset':2.5,'width':.9,'height':2.1,'sill':0},parent_id=wall.id);doc.add(door)
    modifier=SurfaceModifier(
        SurfaceRef(wall.id,'exterior',{'world_center':[2.5,.1,1.2],'radius':.5,'strength':1.0,'falloff':'smooth'}),
        'pull',{'amount':.1},
    )
    mid=doc.add_surface_modifier(modifier)
    doc.select([wall.id,door.id])
    before=doc.to_dict()

    stack.execute(_delete_command()([wall.id]))
    assert wall.id not in doc.entities
    assert door.id not in doc.entities
    assert mid not in doc.surface_modifiers

    stack.undo()
    assert doc.to_dict()==before
    assert doc.selection==[wall.id,door.id]
    assert mid in doc.surface_modifiers
    assert door.id in doc.children.get(wall.id,())
    assert door.id in doc.dependencies.get(wall.id,set())

    stack.redo()
    assert wall.id not in doc.entities
    assert door.id not in doc.entities
    assert mid not in doc.surface_modifiers


def test_delete_undo_restores_mechanical_relationship_entities_and_dependencies():
    doc=Document();stack=commands.CommandStack(doc)
    wall=Entity('wall',{'x1':0,'y1':0,'x2':5,'y2':0,'z':0,'height':3,'thickness':.3});doc.add(wall)
    parent=Entity('mechanical_part',{'x':0,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0});doc.add(parent)
    child=Entity('mechanical_part',{'x':2,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0});doc.add(child)
    joint=Entity('mechanical_joint',{
        'joint_type':'revolute','parent_part':parent.id,'child_part':child.id,
        'anchor':[0,0,0],'axis':[0,0,1],'min_value':-90,'max_value':90,'value':0,
    });doc.add(joint)
    mount=Entity('mechanical_mount',{
        'host_id':wall.id,'part_id':child.id,'surface_role':'interior','clearance':.02,'embed_depth':.1,
    });doc.add(mount)
    before=doc.to_dict()

    stack.execute(_delete_command()([child.id]))
    assert child.id not in doc.entities
    assert joint.id not in doc.entities
    assert mount.id not in doc.entities
    assert parent.id in doc.entities and wall.id in doc.entities

    stack.undo()
    assert doc.to_dict()==before
    assert joint.id in doc.dependencies.get(parent.id,set())
    assert joint.id in doc.dependencies.get(child.id,set())
    assert mount.id in doc.dependencies.get(wall.id,set())
    assert mount.id in doc.dependencies.get(child.id,set())
