from math import sqrt

from archforge.core.model import Document, Entity
from archforge.architecture.openings import infer_organic_opening_patches, pod_opening_patch_geometry
from archforge.geometry.mesh import TessellatedPreviewBackend


def _pod():
    return Entity('pod', {
        'cx': 0.0, 'cy': 0.0, 'floor_level': 0.0,
        'diameter_x': 8.0, 'diameter_y': 6.0, 'height': 4.0,
        'shell_thickness': 0.18, 'rotation': 17.0,
    })


def _opening(kind, parent_id, *, u=0.10):
    return Entity(kind, {
        'surface_u': u,
        'width': 1.0 if kind == 'door' else 1.4,
        'height': 2.1 if kind == 'door' else 1.2,
        'sill': 0.0 if kind == 'door' else 0.9,
        'flat_margin': 0.30,
    }, parent_id=parent_id)


def _area(mesh):
    total=0.0
    for tri in mesh.triangles:
        a,b,c=(mesh.vertices[i] for i in tri)
        ab=(b[0]-a[0],b[1]-a[1],b[2]-a[2]);ac=(c[0]-a[0],c[1]-a[1],c[2]-a[2])
        cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
        total += 0.5*sqrt(sum(v*v for v in cross))
    return total


def _local(point, geom):
    x,y,z=point;px,py=geom['plane']['point'];tx,ty=geom['plane']['tangent']
    return ((x-px)*tx+(y-py)*ty,z)


def _centroid(mesh, tri):
    pts=[mesh.vertices[i] for i in tri]
    return tuple(sum(p[k] for p in pts)/3.0 for k in range(3))


def _inside_opening(point, opening, geom, eps=1e-6):
    q,z=_local(point,geom)
    half=float(opening.params['width'])/2.0
    z0=float(geom['plane']['z_ref'])-float(opening.params['height'])/2.0
    z1=z0+float(opening.params['height'])
    return abs(q)<half-eps and z0+eps<z<z1-eps


def test_door_flat_patch_is_a_frame_with_floor_reaching_void():
    doc=Document();pod=_pod();doc.add(pod);door=_opening('door',pod.id);doc.add(door)
    patch_id=infer_organic_opening_patches(doc).active_ids[0]
    geom=pod_opening_patch_geometry(doc,door.id);assert geom is not None
    mesh=TessellatedPreviewBackend().evaluate(doc).body(patch_id).payload

    expected=float(geom['patch_width'])*float(geom['patch_height'])-float(door.params['width'])*float(door.params['height'])
    assert abs(_area(mesh)-expected)<1e-7
    assert not any(_inside_opening(_centroid(mesh,t),door,geom) for t in mesh.triangles)
    assert min(v[2] for v in mesh.vertices)==geom['z0']


def test_window_flat_patch_has_real_void_with_sill_and_header_regions():
    doc=Document();pod=_pod();doc.add(pod);window=_opening('window',pod.id,u=0.31);doc.add(window)
    patch_id=infer_organic_opening_patches(doc).active_ids[0]
    geom=pod_opening_patch_geometry(doc,window.id);assert geom is not None
    mesh=TessellatedPreviewBackend().evaluate(doc).body(patch_id).payload

    expected=float(geom['patch_width'])*float(geom['patch_height'])-float(window.params['width'])*float(window.params['height'])
    assert abs(_area(mesh)-expected)<1e-7
    assert not any(_inside_opening(_centroid(mesh,t),window,geom) for t in mesh.triangles)
    opening_z0=float(pod.params['floor_level'])+float(window.params['sill'])
    opening_z1=opening_z0+float(window.params['height'])
    assert geom['z0'] < opening_z0
    assert geom['z1'] > opening_z1
