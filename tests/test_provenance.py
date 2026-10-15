"""Every technical rule carries a status; only VERIFIED ones are requirements (owner 15/10)."""
import pytest

from archforge.core.provenance import (MANUFACTURER_DATA, STATUSES, UNVERIFIED, VERIFIED, Rule, rule, rules)


def test_every_rule_has_a_known_status_and_verified_ones_name_their_source():
    found = rules()
    assert len(found) >= 20
    for r in found:
        assert r.status in STATUSES
        if r.status == VERIFIED:
            assert r.source and ('http' in r.source or '§' in r.source or 'Πίν' in r.source), r.id
    with pytest.raises(ValueError):
        Rule('x.y', 'test', VERIFIED)                      # verified without a source is refused


def test_withdrawn_hd_384_is_never_cited_as_the_basis():
    assert rule('standards.elot_hd_384').status == VERIFIED
    from archforge.mep.electrical import PROVENANCE
    assert 'αποσυρμένο ΕΛΟΤ HD 384' in PROVENANCE and 'HD 60364' in PROVENANCE and 'ΜΗ ΕΠΑΛΗΘΕΥΜΕΝΟΥΣ' in PROVENANCE
    for r in rules('electrical.'):
        assert r.status != VERIFIED                         # nothing in the circuit rules is verified yet
        assert 'HD 384' not in r.source


def test_led_strip_power_is_manufacturer_data_without_a_default():
    assert rule('lighting.strip_w_per_m').status == MANUFACTURER_DATA
    import archforge.mep.electrical as E
    assert not hasattr(E, 'STRIP_W_PER_M')
    assert E.point_load_w({'point_type': 'led_strip', 'x': 0, 'y': 0, 'x2': 2, 'y2': 0}) == 0.0


def test_board_lists_every_rule_that_is_not_a_requirement():
    from archforge.mep.electrical_board import unverified_lines
    lines = unverified_lines()
    assert len(lines) == len([r for r in rules('electrical.') + rules('board.') + rules('lighting.') + rules('practice.')
                              if r.status != VERIFIED])
    assert any(l.startswith('[Μη επαληθευμένο') for l in lines) and any('30 mA' in l for l in lines)


def test_program_rules_that_disagree_with_installer_practice_are_listed_not_changed():
    from archforge.mep.electrical import CIRCUIT_RULES
    from archforge.mep.practice import conflicts
    found = dict(conflicts())
    # cooker 32 A / 6 mm² vs practice 40 A / 10 mm²; water heater 20 A on 2.5 mm² vs practice 4 mm² (and 2.5 mm² ≤ 16 A)
    assert 'cooker' in found and 'water_heater' in found
    assert CIRCUIT_RULES['cooker'][1:3] == (32, 6.0)            # nothing changed automatically
    assert rule('practice.circuits').status != VERIFIED and rule('standards.keee_replaced').status != VERIFIED
