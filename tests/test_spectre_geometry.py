import math
import pytest
from archforge.organic.spectre import (
    get_spectre_polygon,
    get_spectre_aperture,
    generate_spectre_tiling_patch,
    spectre_extrusion_mesh,
    NEUROARCHITECTURE_AQUA_PROPERTIES,
)

def test_spectre_polygon_unit_edges():
    # 14 vertices with split collinear
    pts14 = get_spectre_polygon(scale=1.0, split_collinear=True, center_at_origin=True)
    assert len(pts14) == 14
    
    # Every edge must be unit length 1.0 (within 1e-4)
    for i in range(14):
        p1 = pts14[i]
        p2 = pts14[(i + 1) % 14]
        dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        assert abs(dist - 1.0) < 1e-4

def test_spectre_polygon_13_gon():
    # 13 vertices with un-split collinear edge (length 2.0)
    pts13 = get_spectre_polygon(scale=1.0, split_collinear=False, center_at_origin=True)
    assert len(pts13) == 13
    lengths = [
        math.hypot(pts13[(i+1)%13][0] - pts13[i][0], pts13[(i+1)%13][1] - pts13[i][1])
        for i in range(13)
    ]
    # Twelve edges of 1.0 and one edge of 2.0
    assert sum(1 for l in lengths if abs(l - 1.0) < 1e-4) == 12
    assert sum(1 for l in lengths if abs(l - 2.0) < 1e-4) == 1

def test_spectre_aperture_bounds():
    ap = get_spectre_aperture(width=2.0, height=3.0)
    assert len(ap) == 14
    min_x = min(p[0] for p in ap)
    max_x = max(p[0] for p in ap)
    min_y = min(p[1] for p in ap)
    max_y = max(p[1] for p in ap)
    assert abs((max_x - min_x) - 2.0) < 1e-4
    assert abs((max_y - min_y) - 3.0) < 1e-4

def test_spectre_extrusion_mesh():
    mesh = spectre_extrusion_mesh(scale=1.5, thickness=0.018, elevation=0.5)
    assert mesh['num_vertices'] > 28
    assert mesh['num_faces'] > 28
    assert mesh['thickness'] == 0.018

def test_spectre_tiling_patch():
    patch = generate_spectre_tiling_patch(cols=3, rows=3, tile_scale=0.4)
    assert len(patch) == 9
    assert any(t['is_photoluminescent'] for t in patch)
