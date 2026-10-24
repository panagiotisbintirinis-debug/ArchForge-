import sys
from types import ModuleType, SimpleNamespace

from archforge.ui.lighting_mep_bridge import _renderer_specs_from_mep


def _install_fake_mep_specs(monkeypatch, specs):
    module = ModuleType("archforge.mep.lighting")
    module.light_specs = lambda _doc: specs
    monkeypatch.setitem(sys.modules, "archforge.mep.lighting", module)


def test_renderer_uses_mep_specs_without_second_mapping(monkeypatch):
    spec = {
        "id": "spot-1",
        "kind": "spot",
        "kelvin": 3000.0,
        "intensity": 540.0,
        "angle_deg": 12.0,
        "position": [1.0, 2.0, 2.6],
        "target": [1.0, 3.0, 1.0],
        "circuit": "K1",
        "dimmer": True,
        "automation_group": "living",
    }
    _install_fake_mep_specs(monkeypatch, [spec])

    out = _renderer_specs_from_mep(SimpleNamespace())

    assert out == [spec]
    assert out[0]["circuit"] == "K1"
    assert out[0]["automation_group"] == "living"


def test_missing_photometry_does_not_create_fake_pbr_light(monkeypatch):
    specs = [
        {"id": "no-k", "kind": "point", "kelvin": None, "intensity": 100.0},
        {"id": "no-i", "kind": "spot", "kelvin": 3000.0, "intensity": None},
        {"id": "off", "kind": "point", "kelvin": 3000.0, "intensity": 100.0, "enabled": False},
        {"id": "ok", "kind": "strip", "kelvin": 2700.0, "intensity": 220.0, "enabled": True},
    ]
    _install_fake_mep_specs(monkeypatch, specs)

    out = _renderer_specs_from_mep(SimpleNamespace())

    assert [s["id"] for s in out] == ["ok"]
