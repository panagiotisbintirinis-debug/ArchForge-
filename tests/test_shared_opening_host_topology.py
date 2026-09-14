from archforge.core.model import Document, Entity
from archforge.geometry.plan import build_evaluation_plan
from archforge.geometry.preview import PreviewBackend
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.mesh_validation import validate_mesh


def _wall():
    return Entity('wall', {
        'x1': 0.0, 'y1': 0.0, 'z': 0.0,
        'x2': 5.0, 'y2': 0.0,
        'height': 3.0, 'thickness': 0.2,
    })


def _door(parent_id):
    return Entity('door', {
        'offset': 1.5, 'width': 0.9, 'height': 2.1, 'sill': 0.0,
    }, parent_id=parent_id)


def _window(parent_id):
    return Entity('window', {
        'offset': 3.5, 'width': 1.2, 'height': 1.0, 'sill': 1.0,
    }, parent_id=parent_id)


def _centroid(mesh, tri):
    pts=[mesh.vertices[i] for i in tri]
    return tuple(sum(p[k] for p in pts)/3.0 for k in range(3))


def _inside_opening(c, opening, eps=1e-6):
    x, _, z = c
    lo=float(opening.params['offset'])-float(opening.params['width'])/2.0
    hi=float(opening.params['offset'])+float(opening.params['width'])/2.0
    z0=float(opening.params.get('sill',0.0));z1=z0+float(opening.params['height'])
    return lo+eps < x < hi-eps and z0+eps < z < z1-eps


def test_door_and_window_are_relationship_intent_not_standalone_geometry():
    doc=Document();wall=_wall();doc.add(wall);door=_door(wall.id);window=_window(wall.id);doc.add(door);doc.add(window)
    plan=build_evaluation_plan(doc)
    assert plan.node(door.id).role=='relationship'
    assert plan.node(window.id).role=='relationship'
    ids={n.entity_id for n in plan.geometry_nodes()}
    assert door.id not in ids and window.id not in ids
    assert PreviewBackend().evaluate(doc).ok


def test_tessellated_wall_contains_real_door_and_window_voids_with_reveals():
    doc=Document();wall=_wall();doc.add(wall);door=_door(wall.id);window=_window(wall.id);doc.add(door);doc.add(window)
    mesh=TessellatedPreviewBackend().evaluate(doc).body(wall.id).payload

    assert 'opening_reveal' in set(mesh.triangle_surfaces)
    for tri,role in zip(mesh.triangles,mesh.triangle_surfaces):
        if role not in ('exterior','interior'):
            continue
        c=_centroid(mesh,tri)
        assert not _inside_opening(c,door)
        assert not _inside_opening(c,window)

    validation=validate_mesh(mesh)
    assert validation.watertight
    assert validation.manifold


def test_wall_opening_geometry_updates_when_window_moves_without_changing_wall_identity():
    doc=Document();wall=_wall();doc.add(wall);window=_window(wall.id);doc.add(window)
    before=TessellatedPreviewBackend().evaluate(doc).body(wall.id).payload
    wall_id=wall.id

    doc.update(window.id,{'offset':2.5})
    after=TessellatedPreviewBackend().evaluate(doc).body(wall.id).payload

    assert wall.id==wall_id
    assert before.vertices != after.vertices or before.triangles != after.triangles
    validation=validate_mesh(after)
    assert validation.watertight and validation.manifold
