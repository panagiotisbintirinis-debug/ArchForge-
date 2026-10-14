"""3D check of the walk-through house (stair, slab openings, balcony) with the real PBR page.

    python scripts/user_drive/scene3d.py out/scene.json walls|none
    python scripts/look_shot/dump_page.py out/page.html
    VIEW="1,1,4,7,12" node scripts/look_shot/shot.mjs out/page.html out/scene.json out/eye.png 40 200 eye   # or orbit / top / cutaway
"""
import json, sys, copy
sys.path.insert(0, __import__('os').path.abspath(__import__('os').path.join(__import__('os').path.dirname(__file__), '..', '..')))
from archforge.core.commands import AddEntity, AddEntities, CommandStack, CreateFloorLevel, SetWorkPlane
from archforge.core.model import Document, Entity
from archforge.core.interaction import StairPlaceTransaction
from archforge.geometry.incremental import IncrementalEvaluationCache
from archforge.geometry.sculpt import SculptedPreviewBackend
from archforge.rendering.scene import build_pbr_scene_payload
from archforge.architecture.balcony import balcony_entities
import archforge.architecture.storey_slabs as S
upper_walls = sys.argv[2] == 'walls'
doc = Document(); stack = CommandStack(doc)
def walls(z, extra=()):
    for a, b in (((0,0),(10,0)),((10,0),(10,8)),((10,8),(0,8)),((0,8),(0,0)),((6,0),(6,8))) + tuple(extra):
        stack.execute(AddEntity(Entity('wall', {'x1':a[0],'y1':a[1],'x2':b[0],'y2':b[1],'z':z,'height':2.7,'thickness':0.25,'material_id':'plaster_white'})))
walls(0.0, (((6,3),(10,3)),((6,5.5),(10,5.5))))
plane = copy.deepcopy(doc.work_plane)
stack.execute(CreateFloorLevel('Floor 2', 3.0)); stack.execute(SetWorkPlane(plane))
if upper_walls: walls(3.0, (((0,4),(6,4)),))
tx = StairPlaceTransaction(doc, stack, (5.9, 7.0)); tx.update(1.5, 7.0); tx.commit()
print('stair', tx.active_candidate.layout, tx.active_candidate.origin, 'fits', tx.preview['fits'])
stack.execute(S.missing_storey_slabs_command(doc))
if upper_walls:
    stack.execute(AddEntities(balcony_entities(doc, [(1,0),(5,0),(5,-1.5),(1,-1.5)], 3.0)))
ev = IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc)
payload = build_pbr_scene_payload(ev, [], doc=doc)
json.dump(payload, open(sys.argv[1], 'w'))
print(len(payload['objects']), sorted({o['kind'] for o in payload['objects']}))
