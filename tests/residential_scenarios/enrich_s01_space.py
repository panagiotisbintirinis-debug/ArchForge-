"""Our S01 foundation-review variant: reclaim stair space without changing its frame."""
from pathlib import Path
import shutil
from archforge.project.persistence import load_project,save_project
from archforge.core.commands import CommandStack,DeleteEntities,UpdateEntity,SetRoomMetadata,AddEntity
from archforge.core.model import Entity
from archforge.architecture.topology import room_faces
from archforge.architecture.stair_options import railing_command
from archforge.architecture.roof_need import attic_ceiling_entities
from archforge.library.catalog import specs
from archforge.library.builder import build
from archforge.library.assets import store_asset,asset_dir
from archforge.ui.library_instance_integration import library_instance_params
from tests.residential_scenarios.space_economy import add_under_stair_storage,protect_upper_opening
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'docs/scenarios/foundation_review/S01_strip_comparison.archforge'
TARGET=ROOT/'docs/scenarios/residential_review/S01_details/S01_space_economy.archforge'


def enrich():
    loaded=load_project(SOURCE);assert loaded.ok,loaded.message()
    doc=loaded.doc;stack=CommandStack(doc)
    # Open the south half on both levels. Existing north kitchen/bedroom and
    # bathroom stay private. No changed structural sections or foundations.
    for k in (0,1):
        stack.execute(DeleteEntities([f's01-opening-{k}-0']))
        stack.execute(UpdateEntity(f's01-opening-{k}-1',{'offset':1.2}))
        stack.execute(UpdateEntity(f's01-part-{k}-a',{'y1':4.}))
    stack.execute(UpdateEntity('s01-stair',{'structure':'timber','x':1.6,'y':1.5}))
    stack.execute(DeleteEntities([e.id for e in doc.entities.values() if e.id.startswith('s01-attic-ceiling-')]))
    for z in (0.,3.):
        for face in room_faces(doc,z=z):
            cx=sum(p[0] for p in face.polygon)/len(face.polygon);cy=sum(p[1] for p in face.polygon)/len(face.polygon)
            if cy<4:name,use=('Καθιστικό — τραπεζαρία με ανοιχτή σκάλα','living') if z==0 else ('Πολυχώρος γραφείου — ανοιχτό πλατύσκαλο','office')
            elif cx<5:name,use=('Κουζίνα','kitchen') if z==0 else ('Υπνοδωμάτιο','bedroom')
            else:name,use='Λουτρό','bathroom'
            rid=f's01-space-{z:g}-{face.signature}'
            doc.room_bindings[rid]={'signature':face.signature,'polygon':[list(p) for p in face.polygon],'z':z,'status':'enclosed'}
            stack.execute(SetRoomMetadata(face.signature,dict(name=name,use=use)))
    for i,e in enumerate(attic_ceiling_entities(doc)):
        e.id=f's01-space-attic-{i}';stack.execute(AddEntity(e))
    command=railing_command(doc,'s01-stair','both')
    for cmd in command.commands:
        for i,e in enumerate(getattr(cmd,'entities',[])):e.id=f's01-stair-flight-rail-{i}'
    stack.execute(command)
    add_under_stair_storage(doc,stack,'s01-stair')
    protect_upper_opening(doc,stack,'s01-stair',2.82)
    # Put the former south bedroom into its proper private north room; the
    # released floor beside the landing becomes a furnished work / reading area.
    stack.execute(UpdateEntity('s01-library-2',{'x':2.4,'y':6.4}))
    stack.execute(UpdateEntity('s01-library-0',{'x':9.25,'y':1.4,'rotation':90.}))
    stack.execute(UpdateEntity('s01-library-1',{'x':6.75,'y':2.5}))
    stack.execute(DeleteEntities(['s01-library-3']))
    catalogue={s['name']:s for s in specs()}
    choices=[('Γραφείο εργασίας 140',7.1,1.4,3.,0),('Καρέκλα γραφείου',7.1,2.3,3.,180),
        ('Βιβλιοθήκη με ράφια',8.8,3.65,3.,0),('Πολυθρόνα',2.25,.6,3.,180),
        ('Βιβλιοθήκη με ράφια',8.8,3.65,0.,0),
        ('Καρέκλα τραπεζαρίας',5.8,2.5,0.,90),('Καρέκλα τραπεζαρίας',7.7,2.5,0.,270),
        ('Καρέκλα τραπεζαρίας',6.75,1.65,0.,0),('Καρέκλα τραπεζαρίας',6.75,3.35,0.,180)]
    for i,(name,x,y,z,rotation) in enumerate(choices):
        spec=catalogue[name];tri,col,names=build(spec)
        aid,size=store_asset(name,tri,{'source':'archforge-core','license':'project','redistributable':True},colors=col,category=spec['category'],part_names=names)
        p=library_instance_params({'id':aid,'size':size},x=x,y=y,z=z);p['rotation']=rotation
        stack.execute(AddEntity(Entity('library_object',p,name=name,id=f's01-space-library-{i}')))
    from tests.residential_scenarios.facade_finish import finish_facade_joints
    finish_facade_joints(doc,stack)
    return doc


def main():
    doc=enrich();TARGET.parent.mkdir(parents=True,exist_ok=True);save_project(doc,TARGET)
    assets=TARGET.parent/'library_assets';assets.mkdir(exist_ok=True)
    for e in doc.entities.values():
        if e.kind=='library_object':
            aid=e.params['asset'];shutil.copyfile(asset_dir()/(aid+'.json'),assets/(aid+'.json'))
    print(TARGET,len(doc.entities))
if __name__=='__main__':main()
