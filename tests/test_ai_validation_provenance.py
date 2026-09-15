from archforge.core.model import Document
from archforge.architecture.design_agent import (
    apply_ai_proposal,
    propose_gypsum_drop_ceiling,
    propose_linear_sliding_pergola,
    propose_mechanical_dishwasher_arm,
    propose_rotational_facade_louvers,
    propose_timber_ceiling_beams,
)


def _assert_advisory_only(proposal):
    data = proposal.to_dict()
    assert data['validation_provenance']['level'] == 'heuristic'
    assert data['validation_provenance']['engineering_verified'] is False
    assert proposal.physics_validation['verification_level'] == 'heuristic'
    assert proposal.physics_validation['engineering_verified'] is False


def test_all_generated_ai_proposals_are_explicitly_advisory_until_real_validator_runs():
    doc = Document()
    proposals = [
        propose_mechanical_dishwasher_arm(doc),
        propose_timber_ceiling_beams(doc),
        propose_gypsum_drop_ceiling(doc),
        propose_linear_sliding_pergola(doc),
        propose_rotational_facade_louvers(doc),
    ]
    for proposal in proposals:
        _assert_advisory_only(proposal)


def test_user_approval_does_not_turn_heuristic_claims_into_engineering_verification():
    doc = Document()
    proposal = propose_linear_sliding_pergola(doc)
    apply_ai_proposal(doc, proposal)

    assert proposal.status == 'approved'
    assert proposal.applied is True
    _assert_advisory_only(proposal)
