from archforge.mep.heating_rules import (
    DESIGN_RULES,
    ENGINEER_REVIEW,
    STANDARD_REFERENCES,
    VERIFIED_STANDARD,
    has_verified_automatic_sizing,
    heating_rule_audit,
)


def test_no_heating_sizing_rule_is_verified_without_source():
    assert STANDARD_REFERENCES == {}
    assert DESIGN_RULES
    assert all(rule.status == ENGINEER_REVIEW for rule in DESIGN_RULES.values())
    assert not any(rule.status == VERIFIED_STANDARD for rule in DESIGN_RULES.values())
    assert has_verified_automatic_sizing() is False


def test_heating_audit_exposes_engineer_review_rules():
    audit = heating_rule_audit()
    assert ENGINEER_REVIEW in audit
    keys = {rule.key for rule in audit[ENGINEER_REVIEW]}
    assert "heat_loss_method" in keys
    assert "pipe_sizing" in keys
    assert "pump_selection" in keys
    assert "heat_source_sizing" in keys
