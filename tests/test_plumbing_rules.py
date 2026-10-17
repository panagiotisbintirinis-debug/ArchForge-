from archforge.mep.plumbing_rules import (
    CONNECTION_HEIGHT_RULES,
    ENGINEER_REVIEW,
    IMPLEMENTATION_RULES,
    STANDARD_REFERENCES,
    VERIFIED_STANDARD,
    plumbing_rule_audit,
    unverified_engineering_rules,
)


def test_only_authoritative_scope_references_are_verified():
    assert STANDARD_REFERENCES["backflow_protection"].status == VERIFIED_STANDARD
    assert STANDARD_REFERENCES["multilayer_fittings"].status == VERIFIED_STANDARD

    for rule in IMPLEMENTATION_RULES.values():
        assert rule.status != VERIFIED_STANDARD
    for rule in CONNECTION_HEIGHT_RULES.values():
        assert rule.status != VERIFIED_STANDARD


def test_current_pipe_sizing_rules_require_engineer_review():
    assert IMPLEMENTATION_RULES["multilayer_outlet_count_sizing"].status == ENGINEER_REVIEW
    assert IMPLEMENTATION_RULES["copper_outlet_count_sizing"].status == ENGINEER_REVIEW
    assert IMPLEMENTATION_RULES["manifold_outlet_count_sizing"].status == ENGINEER_REVIEW


def test_connection_heights_are_not_normative_requirements():
    assert CONNECTION_HEIGHT_RULES
    assert all(rule.status == ENGINEER_REVIEW for rule in CONNECTION_HEIGHT_RULES.values())


def test_audit_reports_unverified_rules_explicitly():
    audit = plumbing_rule_audit()
    assert VERIFIED_STANDARD in audit
    assert ENGINEER_REVIEW in audit

    unverified = unverified_engineering_rules()
    keys = {rule.key for rule in unverified}
    assert "multilayer_outlet_count_sizing" in keys
    assert "connection_height.basin" in keys
