"""Unified geometry evaluation layer for ArchForge.

Semantic architecture remains the source of truth. Backends consume EvaluationPlan and
stable semantic surfaces so architectural, organic, sculpted and mechanical geometry can
share one evaluation/fabrication path without destructive conversion to anonymous meshes.
"""

from .plan import EvaluationNode, EvaluationPlan, build_evaluation_plan, fabrication_candidates
from .surfaces import SurfaceDescriptor, surface_catalog, surface_roles, resolve_surface
from .backend import GeometryBackend, GeometryBody, GeometryEvaluation, GeometryIssue, ContractBackend
from .preview import PreviewBackend, PreviewPayload

__all__ = [
    'EvaluationNode','EvaluationPlan','build_evaluation_plan','fabrication_candidates',
    'SurfaceDescriptor','surface_catalog','surface_roles','resolve_surface',
    'GeometryBackend','GeometryBody','GeometryEvaluation','GeometryIssue','ContractBackend',
    'PreviewBackend','PreviewPayload',
]
