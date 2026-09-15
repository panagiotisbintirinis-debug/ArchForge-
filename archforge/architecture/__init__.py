"""Semantic architectural systems for ArchForge."""

from . import design_agent as _design_agent
from .proposal_safety import harden_design_agent

# AI-generated design values are proposal heuristics until a real validator supplies
# traceable engineering evidence.  Patch the public proposal type before re-exporting
# the design-agent API so direct submodule imports receive the same safety contract.
harden_design_agent(_design_agent)

from .design_agent import (
    AIAssistantProposal,
    propose_mechanical_dishwasher_arm,
    propose_timber_ceiling_beams,
    propose_gypsum_drop_ceiling,
    propose_linear_sliding_pergola,
    propose_rotational_facade_louvers,
    apply_ai_proposal,
)

__all__ = [
    'AIAssistantProposal',
    'propose_mechanical_dishwasher_arm',
    'propose_timber_ceiling_beams',
    'propose_gypsum_drop_ceiling',
    'propose_linear_sliding_pergola',
    'propose_rotational_facade_louvers',
    'apply_ai_proposal',
]
