from __future__ import annotations
import math
from typing import Dict, List, Tuple, Any, Optional
from archforge.core.model import Document, Entity


class ArborealCore:
    """
    Central structural core (Ο Πυρήνας).

    This object describes architectural intent only.  It is not structural-analysis
    evidence; the document geometry may later be handed to a dedicated engineering
    solver without changing the semantic tree relationships.
    """
    def __init__(
        self,
        core_id: str,
        cx: float = 0.0,
        cy: float = 0.0,
        base_z: float = 0.0,
        radius: float = 1.8,
        height: float = 12.0,
        material: str = "geopolymer_concrete"
    ):
        self.core_id = core_id
        self.cx = cx
        self.cy = cy
        self.base_z = base_z
        self.radius = radius
        self.height = height
        self.material = material
        self.branches: List[ArborealBranch] = []

    def top_z(self) -> float:
        return self.base_z + self.height


class ArborealBranch:
    """
    Parametric branch intent extending from the central core toward a pod.

    Radius values used by the preview are geometric design parameters, not verified
    member sizes.  Structural adequacy remains explicitly outside this module.
    """
    def __init__(
        self,
        branch_id: str,
        core_id: str,
        elevation_z: float,
        azimuth_deg: float,
        length: float = 5.0,
        slope_deg: float = 12.0,
        mounted_pod_id: Optional[str] = None
    ):
        self.branch_id = branch_id
        self.core_id = core_id
        self.elevation_z = elevation_z
        self.azimuth_deg = azimuth_deg
        self.length = length
        self.slope_deg = slope_deg
        self.mounted_pod_id = mounted_pod_id

    def compute_tip_coordinate(self, core_cx: float, core_cy: float) -> Tuple[float, float, float]:
        rad = math.radians(self.azimuth_deg)
        slope_rad = math.radians(self.slope_deg)
        horizontal_span = self.length * math.cos(slope_rad)
        vertical_rise = self.length * math.sin(slope_rad)

        tip_x = core_cx + horizontal_span * math.cos(rad)
        tip_y = core_cy + horizontal_span * math.sin(rad)
        tip_z = self.elevation_z + vertical_rise
        return (round(tip_x, 4), round(tip_y, 4), round(tip_z, 4))


def arboreal_branch_geometry(doc: Document, branch_or_id) -> Dict[str, Any]:
    """Resolve live preview geometry for one persistent arboreal branch entity."""
    branch = doc.get(branch_or_id) if isinstance(branch_or_id, str) else branch_or_id
    if branch.kind != 'arboreal_branch':
        raise ValueError('expected arboreal_branch')
    p = branch.params
    core_id = str(p.get('core_id', ''))
    if core_id not in doc.entities:
        raise ValueError('arboreal branch core is missing')
    core = doc.get(core_id)
    if core.kind != 'box':
        raise ValueError('arboreal branch core must be a box entity')

    cx = float(core.params['x']) + float(core.params['width']) / 2.0
    cy = float(core.params['y']) + float(core.params['depth']) / 2.0
    elevation = float(p['elevation_z'])
    length = float(p['length'])
    azimuth = float(p['azimuth_deg'])
    slope = float(p.get('slope_deg', 0.0))
    root_radius = float(p.get('root_radius', 0.4))
    tip_radius = float(p.get('tip_radius', root_radius * 0.7))
    if length <= 0.0:
        raise ValueError('arboreal branch length must be > 0')
    if root_radius <= 0.0 or tip_radius <= 0.0:
        raise ValueError('arboreal branch preview radii must be > 0')

    az = math.radians(azimuth)
    sl = math.radians(slope)
    horizontal = length * math.cos(sl)
    start = (cx, cy, elevation)
    end = (
        cx + horizontal * math.cos(az),
        cy + horizontal * math.sin(az),
        elevation + length * math.sin(sl),
    )
    return {
        'start': start,
        'end': end,
        'root_radius': root_radius,
        'tip_radius': tip_radius,
        'core_id': core_id,
        'mounted_pod_id': p.get('mounted_pod_id'),
    }


def create_arboreal_tree(
    doc: Document,
    cx: float = 0.0,
    cy: float = 0.0,
    core_radius: float = 2.0,
    core_height: float = 14.0,
    branch_specs: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Construct a persistent arboreal architectural tree in the Document.

    The core, branches and pods are all semantic entities.  Branches receive a tapered
    preview mesh in the geometry backend, but are deliberately not fabrication evidence
    or structural verification.
    """
    core_box = Entity(
        kind='box',
        name="Arboreal Structural Core (Κεντρικός Πυρήνας)",
        params={
            'x': cx - core_radius,
            'y': cy - core_radius,
            'z': 0.0,
            'width': core_radius * 2.0,
            'depth': core_radius * 2.0,
            'height': core_height,
            'rotation': 0.0,
        }
    )
    core_id = doc.add(core_box)

    if branch_specs is None:
        branch_specs = [
            {'elevation_z': 3.5, 'azimuth_deg': 0.0, 'length': 5.5, 'pod_diameter': 5.0, 'name': 'Pod East Branch'},
            {'elevation_z': 6.5, 'azimuth_deg': 120.0, 'length': 5.2, 'pod_diameter': 4.8, 'name': 'Pod Northwest Branch'},
            {'elevation_z': 9.5, 'azimuth_deg': 240.0, 'length': 5.0, 'pod_diameter': 4.5, 'name': 'Pod Southwest Branch'},
        ]

    created_branches = []
    created_pods = []

    for idx, spec in enumerate(branch_specs):
        elevation = float(spec.get('elevation_z', 4.0))
        azimuth = float(spec.get('azimuth_deg', idx * 120.0))
        length = float(spec.get('length', 5.0))
        slope = float(spec.get('slope_deg', 10.0))
        pod_diam = float(spec.get('pod_diameter', 4.8))
        root_radius = float(spec.get('root_radius', min(0.5, max(0.25, core_radius * 0.20))))
        tip_radius = float(spec.get('tip_radius', root_radius * 0.70))
        if length <= 0.0 or pod_diam <= 0.0:
            raise ValueError('arboreal branch length and pod diameter must be > 0')
        if root_radius <= 0.0 or tip_radius <= 0.0:
            raise ValueError('arboreal branch preview radii must be > 0')

        branch_entity = Entity(
            kind='arboreal_branch',
            name=f"Arboreal Branch {idx + 1}",
            parent_id=core_id,
            params={
                'core_id': core_id,
                'elevation_z': elevation,
                'azimuth_deg': azimuth,
                'length': length,
                'slope_deg': slope,
                'root_radius': root_radius,
                'tip_radius': tip_radius,
                'preview_only': True,
                'engineering_verified': False,
            },
        )
        branch_id = doc.add(branch_entity)
        doc.add_dependency(core_id, branch_id)
        branch_geometry = arboreal_branch_geometry(doc, branch_id)
        tip_x, tip_y, tip_z = branch_geometry['end']

        branch_pod = Entity(
            kind='pod',
            name=spec.get('name', f"Arboreal Pod {idx+1}"),
            parent_id=branch_id,
            params={
                'cx': tip_x,
                'cy': tip_y,
                'floor_level': tip_z,
                'diameter_x': pod_diam,
                'diameter_y': pod_diam,
                'height': pod_diam * 0.65,
                'shell_thickness': 0.018,
                'rotation': azimuth,
            }
        )
        pod_id = doc.add(branch_pod)
        doc.add_dependency(branch_id, pod_id)
        doc.update(branch_id, {'mounted_pod_id': pod_id})

        created_branches.append({
            'branch_id': branch_id,
            'elevation_z': elevation,
            'azimuth_deg': azimuth,
            'start': branch_geometry['start'],
            'tip': (tip_x, tip_y, tip_z),
            'root_radius': root_radius,
            'tip_radius': tip_radius,
            'mounted_pod_id': pod_id,
            'engineering_verified': False,
        })
        created_pods.append(pod_id)

    return {
        'core_id': core_id,
        'core_center': (cx, cy),
        'core_height': core_height,
        'branches': created_branches,
        'pod_ids': created_pods,
        'is_arboreal_tree': True,
        'engineering_verified': False,
    }
