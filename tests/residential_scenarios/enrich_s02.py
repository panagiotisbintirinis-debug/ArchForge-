"""Complete S02 through shared commands, with explicit software-fixture choices.

No engineering certification: existing stair/wall assembly options keep their
original provenance. Geometry/layout values are editable test-project choices.
"""
from pathlib import Path
import json, shutil
from archforge.core.model import Document, Entity
from archforge.core.commands import AddEntity, CommandStack, DeleteEntities, UpdateEntity, SetRoomMetadata
from archforge.architecture.stairs import solve_stair_candidates, stair_wall_conflicts, stair_centerline
from archforge.architecture.storey_slabs import storey_slab_command
from archforge.architecture.stair_options import railing_command
from archforge.architecture.wall_types import total_thickness
from archforge.architecture.topology import room_faces
from archforge.architecture.railings import default_params
from archforge.library.catalog import specs
from archforge.library.builder import build
from archforge.library.assets import store_asset, asset_dir
from archforge.ui.library_instance_integration import library_instance_params
from archforge.project.persistence import save_project
from tests.residential_scenarios.generate_projects import build_project, MANIFEST, ROOT

OUT=ROOT.parents[1]/'docs/scenarios/residential_review/S02_details'


def enriched_s02(project=None):
    spec=next(s for s in json.loads(MANIFEST.read_text()) if s['id']=='S02')
    doc=Document.from_dict(project if project is not None else build_project(spec,complete=False));stack=CommandStack(doc)
    def add(kind,params,eid,name,parent=None):
        stack.execute(AddEntity(Entity(kind,params,id=eid,name=name,parent_id=parent)));return eid
    def wall(eid,a,b,z,h,assembly='brick_partition'):
        add('wall',dict(x1=a[0],y1=a[1],x2=b[0],y2=b[1],z=z,height=h,
                       thickness=total_thickness(assembly),wall_type=assembly),eid,eid)
    def opening(kind,eid,host,offset,width,height,sill=0):
        add(kind,dict(offset=offset,width=width,height=height,sill=sill),eid,eid,host)
    # Clear placeholders, duplicate upper kitchen and the old cross-shaped partitions.
    stack.execute(DeleteEntities([e.id for e in doc.entities.values() if e.kind=='box']+
        [f's02-part-{k}-{a}' for k in (0,1) for a in ('a','b')]+['s02-cab-1-0','s02-cab-1-1','s02-plumb-1-3']))
    # A full-width circulation hall, with the existing centre column integrated in its south edge.
    for k,z,h in ((0,0.,3.02),(1,3.2,2.8)):
        wall(f's02-hall-south-{k}',(0,3.5),(11 if k==0 else 8.5,3.5),z,h)
        wall(f's02-hall-north-{k}',(0,4.8),(11 if k==0 else 8.5,4.8),z,h,
             'brick_partition' if k==0 else 'drywall_double_125')
        wall(f's02-part-south-{k}',(5.5,0),(5.5,3.5),z,h,
             'brick_partition' if k==0 else 'drywall_double_125')
        wall(f's02-part-north-{k}',(5.5,4.8),(5.5,7),z,h,
             'brick_partition' if k==0 else 'drywall_double_125')
        for j,(host,offset) in enumerate(((f's02-hall-south-{k}',1.1),(f's02-hall-south-{k}',6.1),
                                         (f's02-hall-north-{k}',.8),(f's02-hall-north-{k}',6.1))):
            opening('door',f's02-door-{k}-{j}',host,offset,.9,2.1)
        # Entry to the hall; on the upper floor the balcony opens from the study.
        if k==0:opening('door','s02-entrance',f's02-wall-{k}-3',2.85,.95,2.1)
        else:opening('door','s02-balcony-door',f's02-wall-{k}-0',7.8,1.5,2.1)
        for j,(host,offset,width) in enumerate(((f's02-wall-{k}-0',1.8,1.4),
               (f's02-wall-{k}-0',6.1,1.2),(f's02-wall-{k}-2',1.7,1.4),
               (f's02-wall-{k}-2',7.2,1.4),(f's02-wall-{k}-1',.8,1.4))):
            opening('window',f's02-window-{k}-{j}',host,offset,width,1.2,.9)
    stack.execute(UpdateEntity('s02-balcony-door',{'offset':7.4,'width':1.2}))
    # Upper occupied volume is narrower than Ground; the east bay becomes a terrace.
    for eid,ch in {'s02-wall-1-0':{'x2':8.5},'s02-wall-1-1':{'x1':8.5,'x2':8.5},
                   's02-wall-1-2':{'x1':8.5},'s02-roof':{'x1':8.5}}.items():
        stack.execute(UpdateEntity(eid,ch))
    stack.execute(UpdateEntity('s02-door-1-1',{'offset':7.6}))
    stack.execute(UpdateEntity('s02-balcony-door',{'offset':7.4,'width':1.2}))
    opening('door','s02-terrace-entry','s02-wall-1-1',4.15,.95,2.1)
    stack.execute(UpdateEntity('s02-window-1-4',{'sill':2.2,'height':.5}))
    # Keep the hip roof, use an actual flat roof over the separate raised annex.
    opening('door','s02-annex-entry','s02-split-wall-0',2.0,1.0,2.1)
    opening('window','s02-annex-window-east','s02-split-wall-1',2.4,1.4,1.2,.9)
    opening('window','s02-annex-window-north','s02-split-wall-2',1.2,1.4,1.2,.9)
    base=dict(doc.get('s02-cab-0-0').params,x=3.6)
    add('cabinet',base,'s02-cab-worktop','Πάγκος προετοιμασίας')
    # Owner 18 October: paid living area must not become an oversized stair
    # room plus a full-width corridor. Keep the stair dimensions, remove the
    # two unnecessary enclosures and use one open living / working space.
    stack.execute(DeleteEntities([f's02-{part}-{k}' for k in (0,1)
        for part in ('hall-south','part-south')]))
    # Real room uses drive surface and wet-room measurement.
    for z in (0.,1.4,3.2):
        for face in room_faces(doc,z=z):
            cx=sum(p[0] for p in face.polygon)/len(face.polygon);cy=sum(p[1] for p in face.polygon)/len(face.polygon)
            if z==1.4:name,use='Ξενώνας ημιορόφου','bedroom'
            elif cy<4.8:name,use=('Ενιαίος χώρος καθιστικού — τραπεζαρίας','living') if z==0 else ('Γραφείο — βιβλιοθήκη με ανοιχτό πλατύσκαλο','office')
            elif cx<5.5:name,use=('Κουζίνα','kitchen') if z==0 else ('Υπνοδωμάτιο 1','bedroom')
            else:name,use=('Μπάνιο','bathroom') if z==0 else ('Μπάνιο ορόφου','bathroom')
            rid=f's02-{z:g}-{face.signature}'
            doc.room_bindings[rid]={'signature':face.signature,'polygon':[list(p) for p in face.polygon],'z':z,'status':'enclosed'}
            stack.execute(SetRoomMetadata(face.signature,dict(name=name,use=use)))
    # Upstairs WC/shower move to the ground-floor bathroom as a single serviced core.
    for j,(x,y) in enumerate(((6.2,6.35),(7.15,6.35),(7.75,5.4))):
        stack.execute(UpdateEntity(f's02-plumb-1-{j}',dict(x=x,y=y)))
    for j,x in enumerate((6.7,8.0,10.0)):
        stack.execute(UpdateEntity(f's02-plumb-0-{j}',dict(x=x,y=6.35)))
    stack.execute(UpdateEntity('s02-plumb-0-3',dict(x=1.8,y=6.45)))
    add('plumbing_point',dict(x=9.,y=6.5,z=0.,point_type='water_heater'),'s02-water-heater','Θερμοσίφωνας — δοκιμαστική θέση')
    # Interior U stair: two flights, open space below, no intersected walls.
    c=next(c for c in solve_stair_candidates(0.,3.2,(1.3,1.5),(4.9,1.5),
          upper_floor_z=3.02,upper_slab_thickness=.18) if c.layout=='u' and c.turn_direction==1)
    assert not stair_wall_conflicts(doc,c),stair_wall_conflicts(doc,c)
    add('stair',dict(c.to_params(),structure='timber'),'s02-stair-main','Ξύλινη σκάλα U — ισόγειο/όροφος')
    # Annex stair remains outside both building envelopes; a real landing leads to its entrance.
    c2=next(c for c in solve_stair_candidates(0.,1.4,(14.,-2.13),(14.,-.1),
          upper_floor_z=1.22,upper_slab_thickness=.18) if c.layout=='straight')
    assert not stair_wall_conflicts(doc,c2),stair_wall_conflicts(doc,c2)
    add('stair',dict(c2.to_params(),structure='steel'),'s02-stair-annex','Μεταλλική εξωτερική σκάλα ημιορόφου')
    end=stair_centerline(c2)[-1]
    add('floor',dict(points=[[13.35,end[1]],[14.65,end[1]],[14.65,1.15],[13.35,1.15]],z=1.22,thickness=.18),
        's02-annex-landing','Πλατύσκαλο εισόδου ημιορόφου')
    for sid in ('s02-stair-main','s02-stair-annex'):
        command=railing_command(doc,sid,'both')
        for cmd in command.commands:
            for i,e in enumerate(getattr(cmd,'entities',[])):e.id=f'{sid}-rail-{i}'
        stack.execute(command)
    from tests.residential_scenarios.space_economy import add_under_stair_storage, protect_upper_opening
    add_under_stair_storage(doc,stack,'s02-stair-main')
    protect_upper_opening(doc,stack,'s02-stair-main',3.02)
    add('railing',default_params('balusters',[[13.35,end[1]],[13.35,1.0]],z=1.4,height=1.05),
        's02-annex-landing-rail-left','Κάγκελο πλατύσκαλου — αριστερά')
    add('railing',default_params('balusters',[[14.65,end[1]],[14.65,1.0]],z=1.4,height=1.05),
        's02-annex-landing-rail-right','Κάγκελο πλατύσκαλου — δεξιά')
    # Full-width structural floor outlines meet exterior wall faces. The shared
    # polygon-floor evaluator cuts the actual stair opening in these solids.
    stack.execute(DeleteEntities(['s02-floor-0','s02-floor-1','s02-split-floor']))
    for z,eid,pts in ((0.,'s02-floor-0',[[-.125,-.125],[11.125,-.125],[11.125,7.125],[-.125,7.125]]),
                     (3.2,'s02-floor-1',[[-.125,-.125],[11.125,-.125],[11.125,7.125],[-.125,7.125]]),
                     (1.4,'s02-split-floor',[[11.9,.9],[16.1,.9],[16.1,6.1],[11.9,6.1]])):
        add('floor',dict(points=pts,z=z-.18,thickness=.18),eid,'Πλάκα δαπέδου')
    command,e=storey_slab_command(doc,'room_roof',1.4,'Ξενώνας',thickness=.18);e.id='s02-annex-flat-roof';stack.execute(command)
    # The wider lower-storey plate forms a real roof terrace next to the upper volume.
    add('railing',default_params('glass_channel',[[8.5,0],[11,0],[11,7],[8.5,7]],z=3.2,height=1.05),
        's02-terrace-rail','Γυάλινο κιγκλίδωμα δώματος — προς μελέτη')
    from archforge.architecture.pergola import pergola_entities
    # The exposed original RC frame already surrounds the terrace. Do not
    # add a second set of timber columns and perimeter beams inside it.
    # Retain canonical rafters only: inner ends at the upper wall, outer ends
    # at the existing edge beam; their underside meets the existing top at 6.
    # Connections/bearing capacity remain ENGINEER_REVIEW, not a sized design.
    pergola,_report=pergola_entities(doc,8.5,0.,11.,7.,z=3.2,material='timber',level='Level 1')
    pergola=[e for e in pergola if e.name=='Τεγίδα πέργκολας']
    from archforge.core.commands import AddEntities
    for i,e in enumerate(pergola):e.id=f's02-terrace-pergola-{i}'
    stack.execute(AddEntities(pergola))
    # Cove ceilings and their actual editable strip entities; catalogue power/flux remain unset.
    from archforge.construction.drywall import default_params as ceiling_params
    from archforge.mep.lighting import cove_strips
    for i,(rid,binding) in enumerate(list(doc.room_bindings.items())):
        if binding['z']!=0:continue
        meta=doc.room_metadata(binding['signature'])
        if meta.get('use') not in ('kitchen','living'):continue
        p=ceiling_params(room_id=rid,level_z=0,board='moisture' if meta['use']=='kitchen' else 'standard');p['cove']=1
        if meta['use']=='living':
            # The living room now includes the stair. Zone the drawn cove
            # over the furnished east side; no uncut ceiling over the flights.
            p.pop('room_id',None)
            p['points']=[[5.7,.2],[10.8,.2],[10.8,4.55],[5.7,4.55]]
        eid=f's02-cove-{i}';add('drywall_ceiling',p,eid,'Κρυφός φωτισμός — '+meta['name'])
        for j,strip in enumerate(cove_strips(doc,doc.get(eid))):
            add('electrical_point',strip,f'{eid}-led-{j}','Ταινία LED εσοχής — στοιχεία προϊόντος εκκρεμούν')
    # Library geometry, not boxes named after furniture. Native catalogue dimensions are retained.
    catalogue={s['name']:s for s in specs()}
    furniture=[
        ('Καναπές τριθέσιος',9.1,.85,0.,0),('Τραπέζι τραπεζαρίας 4θέσιο',7.0,2.2,0.,0),
        ('Καρέκλα τραπεζαρίας',6.1,2.2,0.,90),('Καρέκλα τραπεζαρίας',7.9,2.2,0.,270),
        ('Καρέκλα τραπεζαρίας',7.,1.4,0.,0),('Καρέκλα τραπεζαρίας',7.,3.0,0.,180),
        ('Ντουλάπα-αρμάρι κλασική',5.0,5.85,3.2,90),
        ('Κουζίνα με φούρνο 60',2.8,6.5,0.,0),('Ψυγείο ρετρό',4.6,6.45,0.,0),
        ('Λεκάνη WC με καζανάκι',6.7,6.35,0.,0),('Νιπτήρας με έπιπλο 80',8.0,6.35,0.,0),
        ('Ντουζιέρα 90×90',10.,6.35,0.,0),
        ('Μονό κρεβάτι 90×200',2.3,5.75,3.2,90),
        ('Γραφείο εργασίας 140',6.4,2.7,3.2,0),('Καρέκλα γραφείου',6.4,1.8,3.2,0),
        ('Ντουλάπα-αρμάρι κλασική',7.9,1.95,3.2,90),
        ('Διπλό κρεβάτι 160×200',14.5,4.65,1.4,0),
        ('Γραφείο εργασίας 140',13.0,2.5,1.4,90),('Καρέκλα γραφείου',14.0,2.5,1.4,90),
        ('Λεκάνη WC με καζανάκι',6.2,6.35,3.2,0),('Νιπτήρας με έπιπλο 80',7.15,6.35,3.2,0),
        ('Ντουζιέρα 90×90',7.75,5.4,3.2,0),
        ('Βιβλιοθήκη με ράφια',3.2,4.45,0.,0),
        ('Πολυθρόνα',4.9,4.1,0.,0),
        ('Βιβλιοθήκη με ράφια',3.2,4.45,3.2,0),
        ('Πολυθρόνα',2.3,.6,3.2,180)]
    asset_ids=set()
    for i,(name,x,y,z,rotation) in enumerate(furniture):
        sp=catalogue[name];triangles,colors,names=build(sp)
        aid,size=store_asset(name,triangles,{'source':'archforge-core','license':'project','redistributable':True},colors=colors,category=sp['category'],part_names=names)
        asset_ids.add(aid);p=library_instance_params({'id':aid,'size':size},x=x,y=y,z=z);p['rotation']=rotation
        add('library_object',p,f's02-library-{i}',name)
    # Explicit controls for each existing luminaire group. These are editable
    # fixture locations, without invented luminaire ratings or catalogue data.
    stack.execute(DeleteEntities(['s02-elec-0-3','s02-elec-1-3']))
    for z,tag in ((0.,'ground'),(3.2,'upper')):
        for j,(x,y,lx,ly) in enumerate(((1.45,3.25,2.75,1.75),
                (7.2,3.25,8.,2.),(1.15,5.05,2.75,5.9),(6.4,5.05,7.5,5.9))):
            group=f's02-{tag}-room-{j}'
            # Existing two central lights are repositioned; the other two added.
            if j<2:
                stack.execute(UpdateEntity(f's02-elec-{0 if z==0 else 1}-{j+1}',
                    dict(x=lx,y=ly,automation_group=group)))
            else:
                add('electrical_point',dict(x=lx,y=ly,z=z,point_type='light',automation_group=group),
                    f'{group}-light','Φωτιστικό — '+group)
            add('electrical_point',dict(x=x,y=y,z=z,point_type='switch',automation_group=group),
                f'{group}-switch','Διακόπτης — '+group)
    # Cove strips follow the same kitchen/living controls, independently of
    # the locations of their segment endpoints on the room perimeter.
    for e in list(doc.entities.values()):
        if e.kind!='drywall_ceiling':continue
        binding=doc.room_bindings.get(e.params.get('room_id'))
        use=doc.room_metadata(binding['signature']).get('use') if binding else 'living'
        group='s02-ground-room-'+('2' if use=='kitchen' else '1')
        for strip in list(doc.entities.values()):
            if strip.id.startswith(e.id+'-led-'):
                stack.execute(UpdateEntity(strip.id,{'automation_group':group}))
    add('electrical_point',dict(x=2.8,y=6.7,z=0.,point_type='cooker'),
        's02-cooker-supply','Παροχή κουζίνας')
    add('electrical_point',dict(x=4.6,y=6.7,z=0.,point_type='kitchen_socket'),
        's02-fridge-supply','Πρίζα ψυγείου')
    add('electrical_point',dict(x=14.5,y=3.5,z=1.4,point_type='light',automation_group='s02-annex'),
        's02-annex-light','Φωτιστικό ξενώνα')
    add('electrical_point',dict(x=13.8,y=1.25,z=1.4,point_type='switch',automation_group='s02-annex'),
        's02-annex-switch','Διακόπτης ξενώνα')
    # Synthetic site plateau meets the existing raised wing floor underside.
    # This demonstrates terrain geometry, not a retaining/foundation design.
    from archforge.site.terrain import default_terrain_params
    site=default_terrain_params(doc)
    site['regions']=[dict(id='s02-annex-plateau',shape='rectangle',points=[[11.9,.9],[16.1,.9],[16.1,6.1],[11.9,6.1]],elevation=1.22,transition=2.)]
    add('terrain',site,'s02-terrain','Δοκιμαστικό κεκλιμένο οικόπεδο — προς μελέτη')
    from archforge.core.commands import RenameEntities
    names={};counts={}
    labels=dict(wall='Τοίχος',door='Πόρτα',window='Παράθυρο',pitched_roof='Κεραμοσκεπή',
                cabinet='Ντουλάπι βάσης',electrical_point='Ηλεκτρικό σημείο',plumbing_point='Σημείο ύδρευσης',railing='Κάγκελο')
    for e in doc.entities.values():
        if e.kind=='cabinet' and e.params.get('cabinet_type')=='sink':names[e.id]='Ντουλάπι νεροχύτη'
        elif e.name and all(ord(c)<128 for c in e.name):
            counts[e.kind]=counts.get(e.kind,0)+1;names[e.id]=f"{labels.get(e.kind,e.kind)} {counts[e.kind]}"
    stack.execute(RenameEntities(names))
    from tests.residential_scenarios.facade_finish import finish_facade_joints
    finish_facade_joints(doc,stack)
    return doc,stack,asset_ids


def main():
    doc,stack,assets=enriched_s02();save_project(doc,ROOT/'S02_split_level_hillside_house.archforge')
    OUT.mkdir(parents=True,exist_ok=True);bundle=OUT/'library_assets';bundle.mkdir(exist_ok=True)
    for aid in assets:shutil.copyfile(asset_dir()/(aid+'.json'),bundle/(aid+'.json'))
    print('S02 entities',len(doc.entities),'assets',len(assets),'commands',len(stack.undo_stack) if hasattr(stack,'undo_stack') else 'shared')
if __name__=='__main__':main()
