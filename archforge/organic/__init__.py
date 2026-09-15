"""Organic architectural and Bio-Spectre systems for ArchForge."""

from .biospectre import (
    shell_top,
    profile_radius,
    overlap,
    junction_plane,
    junction_section_polygon,
    junction_key_for_pods,
    find_pod_junctions,
    all_pod_junctions,
)
from .junctions import JunctionIntentResult, infer_organic_junctions
from .spectre import (
    get_spectre_polygon,
    get_spectre_aperture,
    generate_spectre_tiling_patch,
    spectre_extrusion_mesh,
    NEUROARCHITECTURE_AQUA_PROPERTIES,
)
from .materials import (
    BIOSPECTRE_MATERIALS,
    BIOSPECTRE_CONSTRUCTIONS,
    register_biospectre_presets,
)
from .bubble_cluster import (
    compute_cluster_reorganization,
    add_upper_dome,
    create_bio_spectre_cluster,
)
from .arboreal import (
    ArborealCore,
    ArborealBranch,
    create_arboreal_tree,
)

__all__ = [
    'shell_top',
    'profile_radius',
    'overlap',
    'junction_plane',
    'junction_section_polygon',
    'junction_key_for_pods',
    'find_pod_junctions',
    'all_pod_junctions',
    'JunctionIntentResult',
    'infer_organic_junctions',
    'get_spectre_polygon',
    'get_spectre_aperture',
    'generate_spectre_tiling_patch',
    'spectre_extrusion_mesh',
    'NEUROARCHITECTURE_AQUA_PROPERTIES',
    'BIOSPECTRE_MATERIALS',
    'BIOSPECTRE_CONSTRUCTIONS',
    'register_biospectre_presets',
    'compute_cluster_reorganization',
    'add_upper_dome',
    'create_bio_spectre_cluster',
    'ArborealCore',
    'ArborealBranch',
    'create_arboreal_tree',
]
