from math import sqrt

from archforge.core.model import Document, Entity
from archforge.architecture.openings import infer_organic_opening_patches, pod_opening_patch_geometry
from archforge.geometry.mesh import TessellatedPreviewBackend


def _pod():
    return Entity('pod', {
        'cx': 0.0, 'cy': 0.0, 'floor_level': 0.0,
        'diameter_x': 8.0, 'diameter_y': 6.0, 'height': 4.0,
        'shell_thickness': 0.18, 'rotation': 23.0,
    })


def _door(parent_id, u=0.08):
    return Entity('door', {
        'surface_u': u, 'width': 1.0, 'height': 2.1, 'sill': 0.0,
        'flat_margin': 0.30,
    }, parent_id=parent_id)


def _inside_patch(point, geom, inset=1e-5):
    x, y, z = point
    px, py = geom['plane']['point']
    tx, ty = geom['plane']['tangent']
    q = (x-px)*tx + (y-py)*ty
    half = geom['patch_width']/2.0
    return abs(q) < half-inset and geom['z0']+inset < z < geom['z1']-inset


def _triangle_centroid(mesh, tri):
    pts=[mesh.vertices[i] for i in tri]
    return tuple(sum(p[k] for p in pts)/3.0 for k in range(3))


def _mesh_area(mesh):
    total=0.0
    for tri in mesh.triangles:
        a,b,c=(mesh.vertices[i] for i in tri)
        ab=(b[0]-a[0],b[1]-a[1],b[2]-a[2]);ac=(c[0]-a[0],c[1]-a[1],c[2]-a[2])
        cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
        total += 0.5*sqrt(sum(v*v for v in cross))
    return total


def test_active_flat_opening_patch_removes_curved_shell_inside_patch_footprint():
    doc=Document();pod=_pod();doc.add(pod)
    full=TessellatedPreviewBackend().evaluate(doc).body(pod.id).payload
    door=_door(pod.id);doc.add(door);infer_organic_opening_patches(doc)
    geom=pod_opening_patch_geometry(doc,door.id);assert geom is not None

    evaluation=TessellatedPreviewBackend().evaluate(doc)
    shell=evaluation.body(pod.id).payload
    assert _mesh_area(shell) < _mesh_area(full)
    assert not any(_inside_patch(_triangle_centroid(shell,t),geom) for t in shell.triangles)


def test_flattened_shell_boundary_is_closed_visually_by_planar_patch_body():
    doc=Document();pod=_pod();doc.add(pod);door=_door(pod.id);doc.add(door)
    patch_id=infer_organic_opening_patches(doc).active_ids[0]
    geom=pod_opening_patch_geometry(doc,door.id);assert geom is not None

    evaluation=TessellatedPreviewBackend().evaluate(doc)
    patch=evaluation.body(patch_id).payload
    assert patch.triangles
    assert set(patch.triangle_surfaces)=={'opening_patch'}
    px,py=geom['plane']['point'];nx,ny=geom['plane']['normal']
    assert all(abs((x-px)*nx+(y-py)*ny)<1e-8 for x,y,_ in patch.vertices)


def test_moving_pod_opening_restores_old_shell_and_flattens_new_location():
    doc=Document();pod=_pod();doc.add(pod);door=_door(pod.id,0.0);doc.add(door);infer_organic_opening_patches(doc)
    old_geom=pod_opening_patch_geometry(doc,door.id);assert old_geom is not None
    old_eval=TessellatedPreviewBackend().evaluate(doc).body(pod.id).payload
    assert not any(_inside_patch(_triangle_centroid(old_eval,t),old_geom) for t in old_eval.triangles)

    doc.update(door.id,{'surface_u':0.25});infer_organic_opening_patches(doc)
    new_geom=pod_opening_patch_geometry(doc,door.id);assert new_geom is not None
    moved=TessellatedPreviewBackend().evaluate(doc).body(pod.id).payload

    assert not any(_inside_patch(_triangle_centroid(moved,t),new_geom) for t in moved.triangles)
    assert any(_inside_patch(_triangle_centroid(moved,t),old_geom) for t in moved.triangles)
