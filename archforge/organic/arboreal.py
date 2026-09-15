from __future__ import annotations
import math
from typing import Dict, List, Tuple, Any, Optional
from archforge.core.model import Document, Entity

class ArborealCore:
    """
    Central structural core (Ο Πυρήνας):
    The vertical spine of the building providing structural stability,
    vertical circulation (stairs/lift), and MEP utility routing.
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
    Cantilever structural branch (Το Κλαδί):
    Extends outward from the central core to support aerial Bio-Spectre pods.
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


def create_arboreal_tree(
    doc: Document,
    cx: float = 0.0,
    cy: float = 0.0,
    core_radius: float = 2.0,
    core_height: float = 14.0,
    branch_specs: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Construct a complete Arboreal building structure within the Document:
    1. Create central core box/column entity
    2. Create branches and mount Bio-Spectre pods at branch tips
    3. Ensure fluid parametric relationships
    """
    # Create the central structural core entity in Document
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
        # Default 3-branch spiraling tree layout
        branch_specs = [
            {'elevation_z': 3.5, 'azimuth_deg': 0.0, 'length': 5.5, 'pod_diameter': 5.0, 'name': 'Pod East Branch'},
            {'elevation_z': 6.5, 'azimuth_deg': 120.0, 'length': 5.2, 'pod_diameter': 4.8, 'name': 'Pod Northwest Branch'},
            {'elevation_z': 9.5, 'azimuth_deg': 240.0, 'length': 5.0, 'pod_diameter': 4.5, 'name': 'Pod Southwest Branch'},
        ]
        
    created_branches = []
    created_pods = []
    
    for idx, spec in enumerate(branch_specs):
        elevation = spec.get('elevation_z', 4.0)
        azimuth = spec.get('azimuth_deg', idx * 120.0)
        length = spec.get('length', 5.0)
        slope = spec.get('slope_deg', 10.0)
        pod_diam = spec.get('pod_diameter', 4.8)
        
        branch = ArborealBranch(
            branch_id=f"branch_{idx+1}",
            core_id=core_id,
            elevation_z=elevation,
            azimuth_deg=azimuth,
            length=length,
            slope_deg=slope
        )
        
        tip_x, tip_y, tip_z = branch.compute_tip_coordinate(cx, cy)
        
        # Create and mount the Bio-Spectre Pod at branch tip
        branch_pod = Entity(
            kind='pod',
            name=spec.get('name', f"Arboreal Pod {idx+1}"),
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
        branch.mounted_pod_id = pod_id
        
        created_branches.append({
            'branch_id': branch.branch_id,
            'elevation_z': elevation,
            'azimuth_deg': azimuth,
            'tip': (tip_x, tip_y, tip_z),
            'mounted_pod_id': pod_id,
        })
        created_pods.append(pod_id)

    return {
        'core_id': core_id,
        'core_center': (cx, cy),
        'core_height': core_height,
        'branches': created_branches,
        'pod_ids': created_pods,
        'is_arboreal_tree': True,
    }
