"""Unified geometry evaluation layer for ArchForge."""
from .plan import EvaluationNode, EvaluationPlan, build_evaluation_plan, fabrication_candidates
from .surfaces import SurfaceDescriptor, surface_catalog, surface_roles, resolve_surface
from .backend import GeometryBackend, GeometryBody, GeometryEvaluation, GeometryIssue, ContractBackend
from .preview import PreviewBackend, PreviewPayload
from .fabrication import FabricationFinding, FabricationReport, assess_fabrication, require_fabrication_ready

__all__=[
 'EvaluationNode','EvaluationPlan','build_evaluation_plan','fabrication_candidates',
 'SurfaceDescriptor','surface_catalog','surface_roles','resolve_surface',
 'GeometryBackend','GeometryBody','GeometryEvaluation','GeometryIssue','ContractBackend',
 'PreviewBackend','PreviewPayload','FabricationFinding','FabricationReport',
 'assess_fabrication','require_fabrication_ready',
]
