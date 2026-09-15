from __future__ import annotations
import math
from typing import Dict, List, Tuple, Any, Optional
from archforge.core.model import Document, Entity
from archforge.organic.biospectre import (
    overlap,
    junction_plane,
    junction_key_for_pods,
    shell_top,
)
from archforge.organic.materials import register_biospectre_presets


def compute_cluster_reorganization(doc: Document) -> Dict[str, Any]:
    """
    Fluidly analyze all pods in the document and compute automatic reorganization
    of shared walls, inter-pod boundaries, and upper-level roof/ceiling intersections.
    Follows Plateau's laws of soap-bubble geometry:
    - When two pods touch horizontally, curved surfaces flatten into planar vertical partitions.
    - When an upper pod sits atop lower pods, the lower roofs flatten at the contact interface.
    """
    pods = [e for e in doc.entities.values() if e.kind == 'pod' and e.visible]
    
    horizontal_junctions = []
    vertical_stack_junctions = []
    
    for i in range(len(pods)):
        for j in range(i + 1, len(pods)):
            p1 = pods[i]
            p2 = pods[j]
            
            # Check for horizontal or vertical overlap
            p1_z0 = p1.params['floor_level']
            p1_z1 = shell_top(p1.params)
            p2_z0 = p2.params['floor_level']
            p2_z1 = shell_top(p2.params)
            
            # Are they approximately on the same level (horizontal cluster)?
            z_overlap = max(0.0, min(p1_z1, p2_z1) - max(p1_z0, p2_z0))
            floor_diff = abs(p1_z0 - p2_z0)
            
            if floor_diff > 1.5:
                # Vertical stacked intersection (upper dome on top of lower pods)
                lower = p1 if p1_z0 <= p2_z0 else p2
                upper = p2 if p1_z0 <= p2_z0 else p1
                
                dist_xy = math.hypot(upper.params['cx'] - lower.params['cx'], upper.params['cy'] - lower.params['cy'])
                reach = (lower.params['diameter_x'] + upper.params['diameter_x']) / 2.0
                if dist_xy < reach:
                    contact_z = upper.params['floor_level']
                    vertical_stack_junctions.append({
                        'lower_pod': lower.id,
                        'upper_pod': upper.id,
                        'contact_elevation': contact_z,
                        'interface_type': 'roof_to_floor_reorganization',
                        'horizontal_distance': dist_xy,
                    })
            else:
                plane = junction_plane(p1.params, p2.params)
                if plane is not None and z_overlap > 0.3:
                    # Horizontal wall junction
                    horizontal_junctions.append({
                        'key': junction_key_for_pods(p1.id, p2.id),
                        'pod_a': p1.id,
                        'pod_b': p2.id,
                        'plane': plane,
                        'wall_type': 'flat_shared_partition',
                    })

    return {
        'total_pods': len(pods),
        'horizontal_junctions': horizontal_junctions,
        'vertical_stack_junctions': vertical_stack_junctions,
        'reorganized': True,
    }


def add_upper_dome(
    doc: Document,
    cx: float = 0.0,
    cy: float = 0.0,
    diameter: float = 5.0,
    height: float = 3.2,
    name: str = "Upper Sky Dome"
) -> str:
    """
    Place an upper dome on top of existing lower bubble pods.
    Automatically calculates the resting elevation so it sits snugly on the lower roofs,
    reorganizing ceilings and walls without manual Boolean clipping.
    """
    lower_pods = [e for e in doc.entities.values() if e.kind == 'pod' and e.visible]
    
    # Calculate resting elevation based on highest underlying pod roof
    highest_roof = 0.0
    for p in lower_pods:
        # Distance to center
        dist = math.hypot(cx - p.params['cx'], cy - p.params['cy'])
        radius = (p.params['diameter_x'] + p.params['diameter_y']) / 4.0
        if dist < radius * 1.3:
            roof_z = shell_top(p.params)
            # Pod nests slightly into the valley (e.g. 15% nesting)
            nesting_z = roof_z - 0.5
            if nesting_z > highest_roof:
                highest_roof = nesting_z
                
    resting_elevation = max(2.8, highest_roof)
    
    pod_entity = Entity(
        kind='pod',
        name=name,
        params={
            'cx': cx,
            'cy': cy,
            'floor_level': resting_elevation,
            'diameter_x': diameter,
            'diameter_y': diameter,
            'height': height,
            'shell_thickness': 0.018,  # 18mm Bio-Spectre shell
            'rotation': 0.0,
        }
    )
    
    pod_id = doc.add(pod_entity)
    compute_cluster_reorganization(doc)
    return pod_id


def create_bio_spectre_cluster(
    doc: Document,
    center_x: float = 0.0,
    center_y: float = 0.0,
    include_upper_dome: bool = True
) -> Dict[str, Any]:
    """
    Create the complete canonical Bio-Spectre Dome cluster according to the Patent Brief:
    1. Central Dome (Living / Kitchen): Large hub
    2. Master Bedroom Pod: Peripheral bubble with flat shared junction
    3. Studio / Bedroom 2 Pod: Peripheral bubble
    4. Wellness / Bathroom Pod: Peripheral bubble
    5. Upper Sky Dome (Observational Pod) placed on top
    6. Circular Cistern Foundation beneath the central floor
    """
    register_biospectre_presets(doc)
    
    created_ids = {}
    
    # 1. Central Living / Kitchen Pod (Large hub, diameter 8.0m, height 4.5m)
    p_central = Entity(
        kind='pod',
        name="Bio-Spectre Central Pod (Living & Kitchen)",
        params={
            'cx': center_x,
            'cy': center_y,
            'floor_level': 0.0,
            'diameter_x': 8.0,
            'diameter_y': 8.0,
            'height': 4.5,
            'shell_thickness': 0.018,
            'rotation': 0.0,
        }
    )
    created_ids['central_pod'] = doc.add(p_central)
    
    # 2. Master Bedroom Pod (Diameter 5.4m, height 3.6m, overlapping east)
    # Distance = 5.3m < (8.0 + 5.4)/2 = 6.7m => organic overlap with flat junction
    p_master = Entity(
        kind='pod',
        name="Master Bedroom Pod",
        params={
            'cx': center_x + 5.3,
            'cy': center_y + 0.8,
            'floor_level': 0.0,
            'diameter_x': 5.4,
            'diameter_y': 5.4,
            'height': 3.6,
            'shell_thickness': 0.018,
            'rotation': 15.0,
        }
    )
    created_ids['master_pod'] = doc.add(p_master)
    
    # 3. Studio / Guest Pod (Diameter 4.8m, height 3.3m, overlapping northwest)
    p_studio = Entity(
        kind='pod',
        name="Studio & Creative Pod",
        params={
            'cx': center_x - 4.8,
            'cy': center_y + 2.2,
            'floor_level': 0.0,
            'diameter_x': 4.8,
            'diameter_y': 4.8,
            'height': 3.3,
            'shell_thickness': 0.018,
            'rotation': -20.0,
        }
    )
    created_ids['studio_pod'] = doc.add(p_studio)
    
    # 4. Wellness & Bathroom Pod (Diameter 4.0m, height 3.0m, overlapping southwest)
    p_bath = Entity(
        kind='pod',
        name="Wellness & Bath Pod",
        params={
            'cx': center_x - 3.2,
            'cy': center_y - 4.2,
            'floor_level': 0.0,
            'diameter_x': 4.0,
            'diameter_y': 4.0,
            'height': 3.0,
            'shell_thickness': 0.018,
            'rotation': 45.0,
        }
    )
    created_ids['bath_pod'] = doc.add(p_bath)
    
    # 5. Optional Upper Sky Dome (Observational Mezzanine)
    if include_upper_dome:
        p_upper = Entity(
            kind='pod',
            name="Upper Sky Observational Dome",
            params={
                'cx': center_x + 1.2,
                'cy': center_y + 1.0,
                'floor_level': 3.2,
                'diameter_x': 4.6,
                'diameter_y': 4.6,
                'height': 3.2,
                'shell_thickness': 0.018,
                'rotation': 0.0,
            }
        )
        created_ids['upper_dome'] = doc.add(p_upper)

    # Calculate cluster reorganization
    reorg_info = compute_cluster_reorganization(doc)
    
    return {
        'created_pod_ids': created_ids,
        'reorganization': reorg_info,
        'total_pods_created': len(created_ids),
    }
