from types import SimpleNamespace

from archforge.ui import pbr_viewport
from archforge.ui.rendering_quality_upgrade import install_rendering_quality_upgrade
from archforge.ui.lighting_system import _entity_light_spec, install_lighting_system


def test_lighting_runtime_installs_once_and_exposes_night_mode():
    install_rendering_quality_upgrade()
    install_lighting_system()
    first = pbr_viewport._PBR_HTML
    install_lighting_system()
    assert pbr_viewport._PBR_HTML == first
    assert "ArchForge architectural lighting" in first
    assert "setArchitecturalLightingMode" in first
    assert 'architecturalLightingMode === "night"' in first
    assert "setArchitecturalLights" in first
    assert "THREE.PointLight" in first
    assert "THREE.SpotLight" in first
    assert "afStripLights" in first
    assert "scene.environmentIntensity = night ? 0.035" in first


def test_project_light_entity_maps_to_runtime_spec():
    entity = SimpleNamespace(
        id="light-1",
        kind="light_spot",
        params={
            "x": 1.0,
            "y": 2.0,
            "z": 0.25,
            "target_x": 1.0,
            "target_y": 2.0,
            "target_z": 3.0,
            "intensity": 850.0,
            "kelvin": 2700.0,
            "range": 9.0,
            "angle_deg": 28.0,
            "penumbra": 0.5,
            "shadows": True,
        },
    )
    spec = _entity_light_spec(entity)
    assert spec["kind"] == "spot"
    assert spec["position"] == [1.0, 2.0, 0.25]
    assert spec["target"] == [1.0, 2.0, 3.0]
    assert spec["intensity"] == 850.0
    assert spec["kelvin"] == 2700.0
    assert spec["angle_deg"] == 28.0
    assert spec["shadows"] is True


def test_hidden_strip_is_a_project_light_with_two_endpoints():
    entity = SimpleNamespace(
        id="strip-1",
        kind="light_strip",
        params={
            "x": 0.0,
            "y": 0.0,
            "z": 2.55,
            "x2": 4.2,
            "y2": 0.0,
            "z2": 2.55,
            "intensity": 1200.0,
            "kelvin": 3000.0,
        },
    )
    spec = _entity_light_spec(entity)
    assert spec["kind"] == "strip"
    assert spec["start"] == [0.0, 0.0, 2.55]
    assert spec["end"] == [4.2, 0.0, 2.55]
    assert spec["kelvin"] == 3000.0
