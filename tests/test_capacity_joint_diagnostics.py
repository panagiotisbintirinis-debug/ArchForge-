"""Informative joint flags must reach the same summary as other analysis warnings."""
from archforge.structure.analysis import analyze
from tests.test_residential_scenario_gate import generated_s01


def test_s01_joint_flags_have_provenance_and_are_not_hidden_by_empty_warnings():
    result = analyze(generated_s01())
    flagged = [j for j in result['capacity_joints'] if not j['meets']]
    assert len(flagged) == 6
    assert all(j['top'] for j in flagged)
    for joint in flagged:
        assert joint['rule_id'] == 'structure.capacity_joints'
        assert joint['rule_status'] == 'UNVERIFIED'
        assert joint['applicability'] == 'ENGINEER_REVIEW'
        assert joint['factor'] == 1.30  # existing software comparison, not verified regulation
        assert any(joint['joint'] in w and joint['axis'] in w
                   and 'μη επαληθευμένο' in w and 'κορυφή' in w
                   for w in result['warnings'])
    # Diagnostics must not reclassify the members or silently waive the raw comparison.
    assert result['verified'] is False
    assert all(m.get('ok', True) for m in result['members'].values())
