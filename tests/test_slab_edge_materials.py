from types import SimpleNamespace
import pytest
from archforge.core.model import Document,Entity
from archforge.geometry.mesh import _payload
from archforge.rendering.scene import build_pbr_scene_payload


@pytest.mark.parametrize('kind,params',[
    ('floor',dict(points=[[0,0],[4,0],[4,3],[0,3]],z=2.82,thickness=.18)),
    ('room_floor',dict(scope='storey',level_z=3.,thickness=.18,offset_z=0.)),
    ('room_roof',dict(scope='storey',level_z=0.,thickness=.3,offset_z=2.7,roof_type='flat',overhang=0.)),
])
def test_slab_edge_finish_is_rendered_without_repainting_walkable_top(kind,params):
    d=Document()
    for z in (0.,3.):
        for a,b in (((0,0),(4,0)),((4,0),(4,3)),((4,3),(0,3)),((0,3),(0,0))):
            d.add(Entity('wall',dict(x1=a[0],y1=a[1],x2=b[0],y2=b[1],z=z,height=2.7,thickness=.25)))
    e=Entity(kind,dict(params,surface_materials={'edge':'plaster_white'}));d.add(e)
    mesh=_payload(d,SimpleNamespace(semantic_kind=kind,params=e.params,entity_id=e.id,transform=None))
    body=SimpleNamespace(entity_id=e.id,semantic_kind=kind,payload=mesh)
    rendered=build_pbr_scene_payload(SimpleNamespace(bodies=[body]),doc=d)['objects']
    objects=[o for o in rendered if o['id']==e.id]
    edge=[o for o in objects if 'edge' in o['surfaces']]
    top=[o for o in objects if 'top' in o['surfaces']]
    assert edge and top
    assert all(o['material'].get('material_id')=='plaster_white' for o in edge)
    assert all(o['material'].get('material_id')!='plaster_white' for o in top)
    assert sum(len(o['triangles']) for o in objects)==len(mesh.triangles)
    assert all(o['vertices']==[list(v) for v in mesh.vertices] for o in objects)
