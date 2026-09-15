import pytest
from archforge.core.model import Document, Entity
from archforge.architecture.design_agent import (
    propose_mechanical_dishwasher_arm,
    propose_timber_ceiling_beams,
    propose_gypsum_drop_ceiling,
    apply_ai_proposal,
)

def test_dishwasher_arm_proposal():
    doc = Document()
    proposal = propose_mechanical_dishwasher_arm(doc, target_x=1.5, target_y=2.0, target_z=0.85)
    assert proposal.category == 'mechanical_integration'
    assert 'cavity' in proposal.geometric_changes
    assert proposal.physics_validation['clearance_envelope_ok'] is True
    assert proposal.physics_validation['collision_detected'] is False
    assert proposal.status == 'proposed'
    assert proposal.applied is False
    
    # User approves proposal
    created_ids = apply_ai_proposal(doc, proposal)
    assert len(created_ids) >= 3
    assert proposal.status == 'approved'
    assert proposal.applied is True
    for cid in created_ids:
        assert cid in doc.entities

def test_timber_beams_proposal_and_deflection():
    doc = Document()
    proposal = propose_timber_ceiling_beams(doc, center_x=0.0, center_y=0.0, room_width=4.0, room_depth=6.0, ceiling_z=2.8)
    assert proposal.category == 'ceiling_feature'
    assert proposal.physics_validation['deflection_ratio_ok'] is True
    assert proposal.geometric_changes['count'] >= 4
    
    created_ids = apply_ai_proposal(doc, proposal)
    assert len(created_ids) == proposal.geometric_changes['count']

def test_gypsum_drop_ceiling_proposal():
    doc = Document()
    proposal = propose_gypsum_drop_ceiling(doc, center_x=0.0, center_y=0.0, room_width=5.0, room_depth=4.0, ceiling_z=2.9)
    assert proposal.physics_validation['headroom_ok'] is True
    assert proposal.physics_validation['headroom_clearance_m'] >= 2.40


def test_linear_sliding_pergola_proposal():
    doc = Document()
    from archforge.architecture.design_agent import propose_linear_sliding_pergola
    prop = propose_linear_sliding_pergola(doc, target_x=-2.0, stroke_m=2.8)
    assert prop.category == 'kinematic_pergola'
    assert prop.physics_validation['clearance_envelope_ok'] is True
    assert prop.physics_validation['structural_load_transfer'] is True
    assert prop.physics_validation['stroke_length_m'] == 2.8

    created_ids = apply_ai_proposal(doc, prop)
    assert len(created_ids) >= 3
    assert prop.status == 'approved'
    for cid in created_ids:
        assert cid in doc.entities


def test_rotational_facade_louvers_proposal():
    doc = Document()
    from archforge.architecture.design_agent import propose_rotational_facade_louvers
    prop = propose_rotational_facade_louvers(doc, target_x=3.5, louver_count=5)
    assert prop.category == 'rotational_louvers'
    assert prop.physics_validation['clearance_envelope_ok'] is True
    assert prop.physics_validation['aerodynamic_drag_reduction_pct'] == 48.0
    assert len(prop.geometric_changes['louvers']) == 5

    created_ids = apply_ai_proposal(doc, prop)
    assert len(created_ids) >= 5
    assert prop.status == 'approved'
    for cid in created_ids:
        assert cid in doc.entities
