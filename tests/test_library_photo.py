"""Photo-built core library (catalog_photo) and the extra builder solids it needs."""
import math
from types import SimpleNamespace

import pytest

from archforge.geometry.mesh_validation import validate_mesh
from archforge.library import builder


def _mesh(tris):
    index, verts, faces = {}, [], []
    for t in tris:
        face = []
        for v in t:
            k = tuple(round(c, 7) for c in v)
            if k not in index:
                index[k] = len(verts)
                verts.append(k)
            face.append(index[k])
        faces.append(tuple(face))
    return SimpleNamespace(vertices=verts, triangles=faces)


def _volume(tris):
    return sum((a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6 for a, b, c in tris)


SOLIDS = {
    "beam_slanted": ({"shape": "beam", "a": [0, 0, 0], "b": [0, 20, 40], "width": 30, "thickness": 3}, 30 * 3 * math.dist((0, 0, 0), (0, 20, 40))),
    "beam_vertical": ({"shape": "beam", "a": [5, 5, 0], "b": [5, 5, 70], "width": 4, "thickness": 4}, 4 * 4 * 70),
    "beam_splayed": ({"shape": "beam", "a": [0, 0, 0], "b": [15, 0, 70], "width": 8, "thickness": 4}, 8 * 4 * math.dist((0, 0, 0), (15, 0, 70))),
    "torus_ring": ({"shape": "torus", "center": [0, 0, 10], "radius": 20, "tube": 2}, 2 * math.pi ** 2 * 20 * 4),
    "torus_handle": ({"shape": "torus", "center": [0, 0, 30], "radius": 15, "tube": 1, "axis": "y", "arc": 180}, math.pi ** 2 * 15),
    "lathe_vase": ({"shape": "lathe", "base": [0, 0, 0], "profile": [[6, 0], [12, 15], [5, 30], [7, 34]]}, None),
}


@pytest.mark.parametrize("name", sorted(SOLIDS))
def test_new_builder_solids_are_closed_and_face_outward(name):
    part, volume = SOLIDS[name]
    tris = builder.part_triangles(part)
    check = validate_mesh(_mesh(tris))
    assert check.watertight, (name, check.findings[:3])
    got = _volume(tris)
    assert got > 0, name                                  # outward winding
    if volume:
        assert got == pytest.approx(volume, rel=0.1), name


def test_beam_runs_from_a_to_b_with_width_horizontal():
    tris = builder.beam((0, 0, 0), (0, 0, 100), 10, 2)
    xs = [v[0] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    assert max(xs) - min(xs) == pytest.approx(10) and max(zs) == pytest.approx(100) and min(zs) == pytest.approx(0)
