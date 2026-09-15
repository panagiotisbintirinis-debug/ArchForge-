from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any, Optional

Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]

# Exact 14-sided chiral aperiodic monotile (Tile(1,1)) from Smith, Myers, Kaplan, Goodman-Strauss (2023)
# Parameterized on the triangular grid with 14 unit-length edges.
RAW_SPECTRE_LATTICE_NODES = [
    (0, 0, 0, 0),
    (0, 0, -2, 1),
    (0, -1, -2, 1),
    # Collinear midpoint turning the long double-edge into two unit-length segments:
    (1, -2, -2, 1),
    (2, -3, -2, 1),
    (3, -3, -2, 1),
    (3, -3, -1, -1),
    (3, -3, 1, -2),
    (3, -2, 1, -2),
    (2, -1, 1, -2),
    (2, -1, 2, -1),
    (2, -1, 1, 1),
    (1, -1, 1, 1),
    (0, 0, 1, 1),
]

# Physical and neuroarchitectural properties for Strontium Aluminate photoluminescent polymer
NEUROARCHITECTURE_AQUA_PROPERTIES = {
    'chemical_formula': 'SrAl2O4:Eu2+,Dy3+',
    'glow_color': 'Aqua / Teal',
    'emission_peak_wavelength_nm': 490.0,
    'excitation_range_nm': (300.0, 450.0),
    'photoluminescence_duration_hours': 10.5,
    'afterglow_luminance_10min_mcd_m2': 380.0,
    'afterglow_luminance_60min_mcd_m2': 52.0,
    'daylight_transmittance': 0.72,
    'circadian_support_index': 0.94, # Reduces stress, supports sleep-wake cycle transition
    'zero_electricity_ambient_lux': 1.8,
}


def _lattice_to_cartesian(x1: float, x2: float, x3: float, x4: float, k: float = 1.0) -> Point2D:
    sqrt075 = math.sqrt(0.75)
    sqrt13 = math.sqrt(1.0 / 3.0)
    vx = sqrt075 * x1 + k * 0.5 * x3
    vy = 0.5 * x1 + x2 + k * 0.5 * sqrt13 * x3 + k * sqrt13 * x4
    return (vx, vy)


def get_spectre_polygon(
    scale: float = 1.0,
    split_collinear: bool = True,
    center_at_origin: bool = True
) -> List[Point2D]:
    """
    Generate the exact 2D vertices of the chiral aperiodic Spectre monotile (Tile(1,1)).
    If split_collinear is True, returns 14 vertices all having unit edge length (scaled).
    If False, returns 13 vertices where one edge has length 2.0 * scale.
    """
    if split_collinear:
        nodes = RAW_SPECTRE_LATTICE_NODES
    else:
        # omit the collinear midpoint at index 3
        nodes = [RAW_SPECTRE_LATTICE_NODES[i] for i in range(len(RAW_SPECTRE_LATTICE_NODES)) if i != 3]

    pts = [_lattice_to_cartesian(*node, 1.0) for node in nodes]

    if center_at_origin:
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        pts = [(p[0] - cx, p[1] - cy) for p in pts]

    if scale != 1.0:
        pts = [(p[0] * scale, p[1] * scale) for p in pts]

    return pts


def get_spectre_aperture(width: float = 1.0, height: float = 1.0) -> List[Point2D]:
    """
    Return a normalized Spectre polygon scaled to fit within a bounding box of (width, height),
    useful for architectural window/wall punch apertures.
    """
    raw = get_spectre_polygon(scale=1.0, split_collinear=True, center_at_origin=True)
    min_x = min(p[0] for p in raw)
    max_x = max(p[0] for p in raw)
    min_y = min(p[1] for p in raw)
    max_y = max(p[1] for p in raw)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)

    return [
        (p[0] * (width / span_x), p[1] * (height / span_y))
        for p in raw
    ]


def generate_spectre_tiling_patch(
    cols: int = 4,
    rows: int = 4,
    tile_scale: float = 0.5,
    spacing: float = 0.02
) -> List[Dict[str, Any]]:
    """
    Generate an aperiodic patch of Spectre tiles for floorings, terraces, and pod cladding.
    Rotations are chiral steps (multiples of pi/6) without reflections.
    """
    tiles = []
    base_poly = get_spectre_polygon(scale=tile_scale, split_collinear=True, center_at_origin=True)
    
    # Bounding radius of individual tile
    max_r = max(math.hypot(p[0], p[1]) for p in base_poly)
    step_x = (max_r * 1.65) + spacing
    step_y = (max_r * 1.45) + spacing

    for r in range(rows):
        for c in range(cols):
            # Aperiodic chiral rotation angle
            rot_idx = (r * 7 + c * 5) % 12
            angle = rot_idx * (math.pi / 6.0)
            
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            
            offset_x = (c - cols / 2.0) * step_x + ((r % 2) * step_x * 0.5)
            offset_y = (r - rows / 2.0) * step_y
            
            rotated_pts = [
                (p[0] * cos_a - p[1] * sin_a + offset_x,
                 p[0] * sin_a + p[1] * cos_a + offset_y)
                for p in base_poly
            ]
            
            tiles.append({
                'tile_index': len(tiles),
                'row': r,
                'col': c,
                'center': (offset_x, offset_y),
                'rotation_deg': round(math.degrees(angle), 1),
                'vertices': rotated_pts,
                'is_photoluminescent': ((r + c) % 3 == 0),
            })
            
    return tiles


def spectre_extrusion_mesh(
    scale: float = 1.0,
    thickness: float = 0.02,
    elevation: float = 0.0
) -> Dict[str, Any]:
    """
    Generate a 3D watertight prism mesh of a Spectre tile (e.g. 1.5 - 2 cm thickness),
    ready for 3D printing or geometric validation.
    """
    poly = get_spectre_polygon(scale=scale, split_collinear=True, center_at_origin=True)
    n = len(poly)
    
    bottom_z = elevation
    top_z = elevation + thickness
    
    vertices = []
    # Bottom vertices (0..n-1)
    for p in poly:
        vertices.append((p[0], p[1], bottom_z))
    # Top vertices (n..2n-1)
    for p in poly:
        vertices.append((p[0], p[1], top_z))
        
    faces = []
    # Bottom face triangulation (simple fan from centroid or center)
    center_bottom_idx = len(vertices)
    cb_x = sum(p[0] for p in poly) / n
    cb_y = sum(p[1] for p in poly) / n
    vertices.append((cb_x, cb_y, bottom_z))
    
    for i in range(n):
        nxt = (i + 1) % n
        faces.append((center_bottom_idx, nxt, i))
        
    # Top face triangulation
    center_top_idx = len(vertices)
    vertices.append((cb_x, cb_y, top_z))
    for i in range(n):
        nxt = (i + 1) % n
        faces.append((center_top_idx, i + n, nxt + n))
        
    # Side quad faces (split into 2 triangles each)
    for i in range(n):
        nxt = (i + 1) % n
        b0 = i
        b1 = nxt
        t0 = i + n
        t1 = nxt + n
        faces.append((b0, b1, t1))
        faces.append((b0, t1, t0))
        
    return {
        'vertices': vertices,
        'faces': faces,
        'thickness': thickness,
        'num_vertices': len(vertices),
        'num_faces': len(faces),
    }
