"""Owner 17/10: footings and strip footings share the base moments, mostly the strips («πεδιλοδοκοί»)."""
from archforge.structure.analysis.settings import DEFAULTS
from archforge.structure.foundation import design_foundation
from archforge.structure.soil_pressure import contact_pressure, eccentricity


def _footing(x, y, n, seismic_my):
    # Reactions (Hx, Hy, N, Mx, My): G+Q centric, a seismic combination with a large base moment about y.
    return {"x": x, "y": y, "z": 0.0, "column": "", "column_m": 0.4, "N_sls_kN": n, "B_m": 1.0, "h_m": 0.5,
            "e_x_m": 0.0, "e_y_m": 0.0, "sigma_max_sls_kPa": n / 1.0, "pressure_ok": True,
            "reactions": [("G+Q", False, [0, 0, n, 0, 0]), ("E+x", True, [0, 0, n * 0.8, 0, seismic_my])]}


def test_moment_that_tips_a_pad_is_carried_by_the_strip():
    n, my = 60.0, 45.0
    ex, _ey = eccentricity(n * 0.8, 0, my, 0, 0, 0.5)
    assert not contact_pressure(n * 0.8, ex, 0.0, 1.0, 1.0)["stable"]          # a 1.0 m pad overturns
    settings = dict(DEFAULTS, foundation_type="strips")
    fd = design_foundation([_footing(0, 0, n, my), _footing(4, 0, n, my)], settings)
    [strip] = fd["strips"]
    assert strip["seismic_stable"] and strip["pressure_ok"]
    assert abs(strip["e_along_seismic_m"]) > 0.3                                # the moment went to the strip, over its length
    assert strip["sigma_max_seismic_kPa"] <= float(settings["soil_pressure"])


def test_flange_widens_for_a_moment_across_a_lone_strip():
    settings = dict(DEFAULTS, foundation_type="strips")
    big_mx = [("G+Q", False, [0, 0, 60.0, 0, 0]), ("E+y", True, [0, 0, 50.0, 40.0, 0])]
    f = [_footing(0, 0, 60.0, 0), _footing(4, 0, 60.0, 0)]
    for g in f:
        g["reactions"] = big_mx
    [strip] = design_foundation(f, settings)["strips"]
    assert strip["seismic_stable"] and strip["B_m"] > 0.80                      # no crossing strip: the flange takes it


def test_auto_joins_pads_that_would_overturn_into_a_strip():
    """Safety before material: in «Αυτόματα» a pad that tips in the earthquake becomes part of a strip."""
    settings = dict(DEFAULTS, foundation_type="auto")
    far = [_footing(0, 0, 60.0, 45.0), _footing(4, 0, 60.0, 45.0)]
    assert design_foundation(far, settings)["strips"] == []                    # no seismic verdict given: pads stay
    for f in far:
        f["seismic_stable"] = False
    fd = design_foundation(far, settings)
    assert len(fd["strips"]) == 1 and fd["strips"][0]["seismic_stable"]
