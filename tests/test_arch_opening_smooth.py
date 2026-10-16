import math

from archforge.geometry.mesh import MeshPayload
from archforge.geometry.mesh_validation import validate_mesh
from archforge.geometry.wall_detail import detailed_wall_geometry

WALL = {'x1': 0.0, 'y1': 0.0, 'x2': 5.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2}
ARCH = {'kind': 'opening', 'shape': 'arch', 'offset': 1.6, 'width': 1.0, 'height': 2.2,
        'sill': 0.0, 'arch_rise': 0.5}


def _mesh(*openings):
    p = dict(WALL, _opening_intents=list(openings))
    return detailed_wall_geometry(p, target_step=0.5)


def _arch_reveal_edges(verts, tris, roles, opening):
    u0 = opening['offset'] - opening['width'] / 2
    u1 = opening['offset'] + opening['width'] / 2
    top = opening['sill'] + opening['height']
    spring = top - opening['arch_rise']
    flat = upright = 0
    for tri, role in zip(tris, roles):
        if role != 'opening_reveal':
            continue
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            (ax, _, az), (bx, _, bz) = verts[a], verts[b]
            inside = u0 + 1e-6 < min(ax, bx) and max(ax, bx) < u1 - 1e-6
            in_band = spring + 1e-6 < min(az, bz) and max(az, bz) < top - 1e-6
            if not (inside and in_band):
                continue
            if abs(az - bz) < 1e-9 and abs(ax - bx) > 1e-6:
                flat += 1
            if abs(ax - bx) < 1e-9 and abs(az - bz) > 1e-6:
                upright += 1
    return flat, upright


def test_arch_opening_has_a_smooth_curve_not_steps():
    verts, tris, roles = _mesh(ARCH)
    flat, upright = _arch_reveal_edges(verts, tris, roles, ARCH)
    assert flat == 0, 'horizontal soffit steps inside the arch curve'
    assert upright == 0, 'vertical risers inside the arch curve'


def test_arch_soffit_vertices_lie_on_the_arch_curve():
    verts, tris, roles = _mesh(ARCH)
    u0, u1 = 1.1, 2.1
    spring, rise = 1.7, 0.5
    on_curve = set()
    for tri, role in zip(tris, roles):
        if role != 'opening_reveal':
            continue
        for v in tri:
            x, _, z = verts[v]
            if u0 - 1e-9 <= x <= u1 + 1e-9 and z > spring + 1e-6:
                t = (x - (u0 + u1) / 2) / ((u1 - u0) / 2)
                assert abs(z - (spring + rise * math.sqrt(max(0.0, 1 - t * t)))) < 1e-9
                on_curve.add(round(x, 9))
    assert len(on_curve) >= 12


def test_wall_with_arch_and_door_stays_a_closed_shell():
    door = {'kind': 'door', 'offset': 3.8, 'width': 0.9, 'height': 2.1, 'sill': 0.0}
    for openings in ((ARCH,), (ARCH, door), (dict(ARCH, sill=0.4, height=1.6),)):
        verts, tris, roles = _mesh(*openings)
        report = validate_mesh(MeshPayload(verts, tris, roles))
        assert report.watertight, report.findings[:3]
