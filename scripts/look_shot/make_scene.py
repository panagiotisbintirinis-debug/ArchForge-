import json, sys
sys.path.insert(0, '/home/user/ArchForge-')
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.core.viewport import PointerController, PointerEvent
from archforge.geometry.incremental import IncrementalEvaluationCache
from archforge.geometry.sculpt import SculptedPreviewBackend
from archforge.rendering.scene import build_pbr_scene_payload
from archforge.site.terrain import default_terrain_params
from archforge.structure.timber_roof import default_params

doc = Document(); stack = CommandStack(doc)
ids = []
for a, b in (((0, 0), (8, 0)), ((8, 0), (8, 6)), ((8, 6), (0, 6)), ((0, 6), (0, 0))):
    e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 2.8,
                        'thickness': 0.25, 'material_id': 'plaster_white'})
    stack.execute(AddEntity(e)); ids.append(e.id)
c = PointerController(doc, stack)
for tool, x, y in (('door', 2.0, 0), ('window', 5.5, 0), ('window', 8, 3)):
    c.set_tool(tool); c.pointer_down(PointerEvent(x, y)); c.pointer_up(PointerEvent(x, y))
stack.execute(AddEntity(Entity('pitched_roof', default_params(doc))))
stack.execute(AddEntity(Entity('terrain', default_terrain_params(doc), name='Έδαφος')))
ev = IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc)
payload = build_pbr_scene_payload(ev, [], doc=doc)
json.dump(payload, open(sys.argv[1], 'w'))
print(len(payload['objects']), sorted({o['kind'] for o in payload['objects']}))
