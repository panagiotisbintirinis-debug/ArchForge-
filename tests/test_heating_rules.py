from archforge.mep.heating_rules import (
    DESIGN_RULES,
    ENGINEER_REVIEW,
    STANDARD_REFERENCES,
    VERIFIED_STANDARD,
    has_verified_automatic_sizing,
    heating_rule_audit,
)


def test_verified_standard_metadata_does_not_promote_sizing_rules():
    assert STANDARD_REFERENCES
    assert all(rule.status == VERIFIED_STANDARD for rule in STANDARD_REFERENCES.values())
    assert STANDARD_REFERENCES["space_heating_load_standard"].source == "ELOT EN 12831-1:2017"
    assert STANDARD_REFERENCES["surface_heating_system_standard"].source == "ELOT EN 1264-1 E2:2021"

    assert DESIGN_RULES
    assert all(rule.status == ENGINEER_REVIEW for rule in DESIGN_RULES.values())
    assert not any(rule.status == VERIFIED_STANDARD for rule in DESIGN_RULES.values())
    assert has_verified_automatic_sizing() is False


def test_heating_audit_separates_verified_scope_from_engineer_review_rules():
    audit = heating_rule_audit()
    assert VERIFIED_STANDARD in audit
    assert ENGINEER_REVIEW in audit
    verified_keys = {rule.key for rule in audit[VERIFIED_STANDARD]}
    assert "space_heating_load_standard" in verified_keys
    assert "surface_heating_system_standard" in verified_keys
    review_keys = {rule.key for rule in audit[ENGINEER_REVIEW]}
    assert "heat_loss_method" in review_keys
    assert "pipe_sizing" in review_keys
    assert "pump_selection" in review_keys
    assert "heat_source_sizing" in review_keys
