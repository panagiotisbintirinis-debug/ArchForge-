"""Kinematic design foundations for movable architectural assemblies."""

from .model import JOINT_TYPES, assembly_parts, clamp_joint_value, joint_state, mechanism_envelope
from .evaluation import (
    EvaluatedPart,
    evaluate_assembly,
    evaluated_mechanism_envelope,
    transform_point,
)
from .motion import sampled_joint_states, sampled_motion_envelope
from .integration import cavity_modifier_for_mount, ensure_mount_cavity

__all__ = [
    'JOINT_TYPES','assembly_parts','clamp_joint_value','joint_state','mechanism_envelope',
    'EvaluatedPart','evaluate_assembly','evaluated_mechanism_envelope','transform_point',
    'sampled_joint_states','sampled_motion_envelope',
    'cavity_modifier_for_mount','ensure_mount_cavity',
]
