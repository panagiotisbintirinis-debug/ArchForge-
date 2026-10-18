"""Our S03 urban house: three distinct storeys and a north roof terrace.

Editable layout choices; no engineering sizing/certification is introduced.
"""
from pathlib import Path
import json,shutil
from archforge.core.model import Document,Entity
from archforge.core.commands import CommandStack,AddEntity,DeleteEntities,UpdateEntity,SetRoomMetadata,AddEntities
from archforge.architecture.topology import room_faces
from archforge.architecture.stairs import solve_stair_candidates,stair_wall_conflicts
from archforge.architecture.stair_options import railing_command
from archforge.architecture.railings import default_params
from archforge.library.catalog import specs
from archforge.library.builder import build
from archforge.library.assets import store_asset,asset_dir
from archforge.ui.library_instance_integration import library_instance_params
from archforge.kitchen.cabinets import default_params as cabinet_params
from archforge.project.persistence import save_project
from tests.residential_scenarios.generate_projects import build_project,MANIFEST,ROOT
from tests.residential_scenarios.space_economy import add_under_stair_storage,protect_upper_opening
from tests.residential_scenarios.facade_finish import finish_facade_joints
OUT=ROOT.parents[1]/'docs/scenarios/residential_review/S03_details'


def enriched_s03(project=None):
    spec=next(s for s in json.loads(MANIFEST.read_text()) if s['id']=='S03')
    doc=Document.from_dict(project if project is not None else build_project(spec,complete=False));stack=CommandStack(doc)
    def add(kind,p,eid,name,parent=None):
        e=Entity(kind,p,id=eid,name=name,parent_id=parent);stack.execute(AddEntity(e));return e
    def wall(eid,a,b,z,h):
        return add('wall',dict(x1=a[0],y1=a[1],x2=b[0],y2=b[1],z=z,height=h,thickness=.12,wall_type='generic'),eid,'Εσωτερικό χώρισμα')
    def opening(kind,eid,host,offset,width=.9,height=2.1,sill=0.):
        return add(kind,dict(offset=offset,width=width,height=height,sill=sill),eid,'Πόρτα' if kind=='door' else 'Παράθυρο',host)
    remove=[e.id for e in doc.entities.values() if e.kind in ('box','cabinet','plumbing_point','electrical_point','price_list') or '-part-' in e.id]
    stack.execute(DeleteEntities(remove))
    # The top floor is shallower: its real full-width lower plate becomes a north terrace.
    for eid,p in {'s03-wall-2-1':{'y2':7.},'s03-wall-2-2':{'y1':7.,'y2':7.},
                  's03-wall-2-3':{'y1':7.},'s03-roof':{'y1':7.}}.items():stack.execute(UpdateEntity(eid,p))
    for k,z in enumerate((0.,3.,6.)):
        h=2.82 if k<2 else 2.9
        if k<2:
            wall(f's03-north-{k}',(0,6),(9,6),z,h)
            wall(f's03-wet-{k}',(6,6),(6,9),z,h)
            opening('door',f's03-inner-{k}-0',f's03-north-{k}',1.2)
            opening('door',f's03-inner-{k}-1',f's03-north-{k}',6.8)
        else:
            wall('s03-master-wall',(5.25,0),(5.25,7),z,h)
            wall('s03-north-2',(0,4.9),(5.25,4.9),z,h)
            wall('s03-wet-2',(3.3,4.9),(3.3,7),z,h)
            opening('door','s03-master-door','s03-master-wall',3.8)
            opening('door','s03-bath-door','s03-north-2',1.2,.8)
            opening('door','s03-dressing-door','s03-north-2',4.3,.8)
        depth=9. if k<2 else 7.
        for j,(host,offset,width) in enumerate(((f's03-wall-{k}-0',2.7,1.4),
              (f's03-wall-{k}-0',7.5,1.4),(f's03-wall-{k}-1',3.9,1.5),
              (f's03-wall-{k}-2',6.5 if k<2 else 7.,1.4),
              (f's03-wall-{k}-3',depth-4.,1.2))):
            opening('window',f's03-window-{k}-{j}',host,offset,width,1.2,.95)
        if k==0:opening('door','s03-main-entrance','s03-wall-0-0',5.65,1.)
        elif k==1:opening('door','s03-balcony-entry','s03-wall-1-0',5.8,1.)
        else:opening('door','s03-terrace-entry','s03-wall-2-2',1.8,1.2)
    # Stable room identities; each storey has a deliberately different use.
    uses={}
    for z in (0.,3.,6.):
        for face in room_faces(doc,z=z):
            cx=sum(p[0] for p in face.polygon)/len(face.polygon);cy=sum(p[1] for p in face.polygon)/len(face.polygon)
            if z<6:
                if cy<6:name,use=('Υποδοχή — εργασία από το σπίτι','office') if z==0 else ('Καθιστικό — τραπεζαρία','living')
                elif cx<6:name,use=('Ξενώνας','bedroom') if z==0 else ('Κουζίνα','kitchen')
                else:name,use='Μπάνιο','bathroom'
            elif cx>5.25:name,use='Κύριο υπνοδωμάτιο','bedroom'
            elif cy<4.9:name,use='Γραφείο — βιβλιοθήκη με ανοιχτή σκάλα','office'
            elif cx<3.3:name,use='Μπάνιο ορόφου','bathroom'
            else:name,use='Ιματιοθήκη','other'
            rid=f's03-{z:g}-{face.signature}'
            doc.room_bindings[rid]={'signature':face.signature,'polygon':[list(p) for p in face.polygon],'z':z,'status':'enclosed'}
            stack.execute(SetRoomMetadata(face.signature,dict(name=name,use=use)));uses[(z,use)]=rid
    for i,z in enumerate((0.,3.)):
        c=next(c for c in solve_stair_candidates(z,z+3.,(1.65,1.7),(5.1,1.7),
            upper_floor_z=z+2.82,upper_slab_thickness=.18) if c.layout=='u' and c.turn_direction==1)
        assert not stair_wall_conflicts(doc,c),stair_wall_conflicts(doc,c)
        sid=f's03-stair-{i}';add('stair',dict(c.to_params(),structure='timber' if i==0 else 'steel'),sid,'Εσωτερική σκάλα '+str(i+1))
        command=railing_command(doc,sid,'both')
        for cmd in command.commands:
            for j,e in enumerate(getattr(cmd,'entities',[])):e.id=f'{sid}-flight-rail-{j}'
        stack.execute(command);add_under_stair_storage(doc,stack,sid);protect_upper_opening(doc,stack,sid,z+2.82)
    # Kitchen is only on the living storey; no duplicate kitchen on every floor.
    for j,(x,kind,width) in enumerate(((1.,'base',.6),(1.65,'base',.6),(2.45,'sink',.8),(3.35,'base',.6))):
        add('cabinet',cabinet_params(kind,x,8.5,3.,0.,width),f's03-kitchen-{j}','Ντουλάπι νεροχύτη' if kind=='sink' else 'Πάγκος κουζίνας')
    furniture=[('Διπλό κρεβάτι 160×200',2.9,7.6,0.,0),('Γραφείο εργασίας 140',4.8,8.4,0.,0),('Καρέκλα γραφείου',4.8,7.5,0.,0),
        ('Καναπές τριθέσιος',7.4,1.1,0.,0),('Γραφείο εργασίας 140',7.3,4.8,0.,0),('Καρέκλα γραφείου',7.3,3.9,0.,0),
        ('Βιβλιοθήκη με ράφια',4.9,5.7,0.,0),
        ('Καναπές τριθέσιος',7.6,1.1,3.,0),('Τραπέζι τραπεζαρίας 4θέσιο',6.8,4.3,3.,0),
        ('Καρέκλα τραπεζαρίας',5.85,4.3,3.,90),('Καρέκλα τραπεζαρίας',7.75,4.3,3.,270),
        ('Καρέκλα τραπεζαρίας',6.8,3.45,3.,0),('Καρέκλα τραπεζαρίας',6.8,5.15,3.,180),
        ('Κουζίνα με φούρνο 60',4.25,8.5,3.,0),('Ψυγείο ρετρό',5.3,8.45,3.,0),
        ('Διπλό κρεβάτι 160×200',7.,2.3,6.,0),('Ντουλάπα-αρμάρι κλασική',8.45,5.3,6.,90),
        ('Γραφείο εργασίας 140',2.65,4.45,6.,0),('Καρέκλα γραφείου',2.65,3.9,6.,0),
        ('Βιβλιοθήκη με ράφια',.4,4.2,6.,90),('Ντουλάπα-αρμάρι κλασική',4.2,6.45,6.,0)]
    plumbing=[]
    for z in (0.,3.):
        plumbing += [('wc',6.65,8.2,z),('basin',7.7,8.2,z),('shower',8.25,6.9,z)]
        furniture += [('Λεκάνη WC με καζανάκι',6.65,8.2,z,0),('Νιπτήρας με έπιπλο 80',7.7,8.2,z,0),('Ντουζιέρα 90×90',8.25,6.9,z,0)]
    plumbing += [('wc',.7,6.2,6.),('basin',1.75,6.4,6.),('shower',2.6,5.55,6.),('kitchen_sink',2.45,8.5,3.)]
    furniture += [('Λεκάνη WC με καζανάκι',.7,6.2,6.,0),('Νιπτήρας με έπιπλο 80',1.75,6.4,6.,0),('Ντουζιέρα 90×90',2.6,5.55,6.,0)]
    cat={s['name']:s for s in specs()};assets=set()
    for i,(name,x,y,z,rotation) in enumerate(furniture):
        sp=cat[name];tri,col,names=build(sp);aid,size=store_asset(name,tri,{'source':'archforge-core','license':'project','redistributable':True},colors=col,category=sp['category'],part_names=names)
        assets.add(aid);p=library_instance_params({'id':aid,'size':size},x=x,y=y,z=z);p['rotation']=rotation
        add('library_object',p,f's03-library-{i}',name)
    add('plumbing_point',dict(x=.7,y=.7,z=0.,point_type='water_supply',pipe_system='copper'),'s03-supply','Παροχή ύδρευσης')
    add('plumbing_point',dict(x=8.4,y=8.4,z=0.,point_type='water_heater'),'s03-heater','Θερμοσίφωνας — θέση προς μελέτη')
    for i,(kind,x,y,z) in enumerate(plumbing):add('plumbing_point',dict(x=x,y=y,z=z,point_type=kind),f's03-plumb-{i}','Σημείο '+kind)
    add('electrical_point',dict(x=5.7,y=.25,z=0.,point_type='panel'),'s03-panel','Ηλεκτρικός πίνακας')
    for i,(z,use) in enumerate(uses):
        rid=uses[(z,use)];poly=doc.room_bindings[rid]['polygon'];x=sum(p[0] for p in poly)/len(poly);y=sum(p[1] for p in poly)/len(poly);group=f's03-light-room-{i}'
        add('electrical_point',dict(x=x,y=y,z=z,point_type='light',automation_group=group),group+'-light','Φωτιστικό '+use)
        positions={(0.,'office'):(5.05,.25),(0.,'bedroom'):(1.7,6.2),(0.,'bathroom'):(7.3,6.2),
            (3.,'living'):(4.3,4.5),(3.,'kitchen'):(1.7,6.2),(3.,'bathroom'):(7.3,6.2),
            (6.,'office'):(4.3,4.5),(6.,'bedroom'):(5.5,4.2),(6.,'bathroom'):(1.65,5.1),(6.,'other'):(4.75,5.1)}
        sx,sy=positions[(z,use)]
        add('electrical_point',dict(x=sx,y=sy,z=z,point_type='switch',automation_group=group),group+'-switch','Διακόπτης '+use)
        if use!='bathroom':
            add('electrical_point',dict(x=max(p[0] for p in poly)-.25,y=y,z=z,point_type='socket'),group+'-socket','Πρίζα '+use)
    # A drawn cove confined to the north kitchen, away from both stair openings.
    from archforge.construction.drywall import default_params as ceiling_params
    from archforge.mep.lighting import cove_strips
    cp=ceiling_params(points=[[.2,6.2],[5.8,6.2],[5.8,8.8],[.2,8.8]],level_z=3.,board='moisture');cp['cove']=1
    ceiling=add('drywall_ceiling',cp,'s03-kitchen-cove','Εσοχή κρυφού φωτισμού κουζίνας')
    kitchen_group=next(e.params['automation_group'] for e in doc.entities.values() if e.name=='Διακόπτης kitchen')
    for i,p in enumerate(cove_strips(doc,ceiling)):
        p['automation_group']=kitchen_group
        add('electrical_point',p,f's03-kitchen-cove-strip-{i}','Ταινία LED — στοιχεία προϊόντος εκκρεμούν')
    add('electrical_point',dict(x=4.25,y=8.7,z=3.,point_type='cooker'),'s03-cooker-supply','Παροχή κουζίνας')
    add('electrical_point',dict(x=5.3,y=8.7,z=3.,point_type='kitchen_socket'),'s03-fridge-supply','Πρίζα ψυγείου')
    # North terrace reuses the original outer concrete frame, with no second set of posts.
    from archforge.architecture.pergola import pergola_entities
    members,_=pergola_entities(doc,0,7,9,9,z=6.,material='timber',height=2.7,level='Level 2')
    rafters=[e for e in members if e.name=='Τεγίδα πέργκολας']
    for i,e in enumerate(rafters):e.id=f's03-terrace-rafter-{i}'
    stack.execute(AddEntities(rafters))
    add('railing',default_params('balusters',[[0,7],[0,9],[9,9],[9,7]],z=6.),'s03-north-terrace-rail','Προστατευτικό βόρειου δώματος')
    finish_facade_joints(doc,stack)
    from archforge.core.commands import RenameEntities
    labels={'wall':'Τοίχος','floor':'Πλάκα','pitched_roof':'Κεραμοσκεπή'}
    renames={e.id:labels.get(e.kind,'Στοιχείο')+' '+e.id for e in doc.entities.values()
        if e.name and all(ord(c)<128 for c in e.name)}
    stack.execute(RenameEntities(renames))
    return doc,assets


def main():
    doc,assets=enriched_s03();save_project(doc,ROOT/'S03_three_storey_urban_residence.archforge')
    OUT.mkdir(parents=True,exist_ok=True);save_project(doc,OUT/'S03_urban_terrace.archforge')
    target=OUT/'library_assets';target.mkdir(exist_ok=True)
    for aid in assets:shutil.copyfile(asset_dir()/(aid+'.json'),target/(aid+'.json'))
    print('S03',len(doc.entities),'entities',len(assets),'assets')
if __name__=='__main__':main()
