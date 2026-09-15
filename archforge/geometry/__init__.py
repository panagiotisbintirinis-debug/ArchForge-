"""Unified geometry evaluation layer for ArchForge."""
from .plan import EvaluationNode, EvaluationPlan, build_evaluation_plan, fabrication_candidates
from .surfaces import SurfaceDescriptor, surface_catalog, surface_roles, resolve_surface
from .backend import GeometryBackend, GeometryBody, GeometryEvaluation, GeometryIssue, ContractBackend
from .preview import PreviewBackend, PreviewPayload
from .mesh import MeshPayload, TessellatedPreviewBackend
from .incremental import IncrementalEvaluationCache
from .sculpt import SculptedPreviewBackend, apply_brush_modifier
from .sculpt_transaction import SculptTransaction, begin_sculpt_from_ray
from .picking import MeshRayHit, raycast_mesh, raycast_evaluation, surface_hit_from_raycast
from .fabrication import FabricationFinding, FabricationReport, assess_fabrication, require_fabrication_ready
from .selection import SurfaceHit, BrushSpec, sculpt_modifier_from_hit

__all__=[
 'EvaluationNode','EvaluationPlan','build_evaluation_plan','fabrication_candidates',
 'SurfaceDescriptor','surface_catalog','surface_roles','resolve_surface',
 'GeometryBackend','GeometryBody','GeometryEvaluation','GeometryIssue','ContractBackend',
 'PreviewBackend','PreviewPayload','MeshPayload','TessellatedPreviewBackend','IncrementalEvaluationCache',
 'SculptedPreviewBackend','apply_brush_modifier','SculptTransaction','begin_sculpt_from_ray',
 'MeshRayHit','raycast_mesh','raycast_evaluation','surface_hit_from_raycast',
 'FabricationFinding','FabricationReport','assess_fabrication','require_fabrication_ready',
 'SurfaceHit','BrushSpec','sculpt_modifier_from_hit',
]
