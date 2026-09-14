"""Geometry evaluation intermediate representation for ArchForge.

The semantic document remains the source of truth. Geometry backends consume an
EvaluationPlan so architecture, sculpt modifiers and kinematic transforms are applied
in a deterministic order without forcing semantic entities into anonymous meshes.
"""

from .plan import (
    EvaluationNode,
    EvaluationPlan,
    build_evaluation_plan,
    fabrication_candidates,
)

__all__ = ['EvaluationNode','EvaluationPlan','build_evaluation_plan','fabrication_candidates']
