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


def test_electrical_spot_is_the_same_object_used_by_the_renderer():
    entity = SimpleNamespace(
        id="el-spot-1",
        kind="electrical_point",
        params={
            "point_type": "spot_light",
            "x": 2.0,
            "y": 3.0,
            "z": 2.7,
            "target_x": 2.0,
            "target_y": 4.2,
            "target_z": 0.8,
            "power_w": 12.0,
            "intensity": 900.0,
            "dimmer": 0.5,
            "kelvin": 3000.0,
            "beam_angle_deg": 24.0,
            "automation_group": "garden-stone",
        },
    )
    spec = _entity_light_spec(entity)
    assert spec["kind"] == "spot"
    assert spec["electrical_point_type"] == "spot_light"
    assert spec["power_w"] == 12.0
    assert spec["intensity"] == 450.0
    assert spec["angle_deg"] == 24.0
    assert spec["automation_group"] == "garden-stone"
    assert spec["target"] == [2.0, 4.2, 0.8]


def test_electrical_hidden_led_carries_geometry_power_and_controls():
    entity = SimpleNamespace(
        id="el-strip-1",
        kind="electrical_point",
        params={
            "point_type": "hidden_light",
            "x": 0.0,
            "y": 0.0,
            "z": 2.62,
            "x2": 5.0,
            "y2": 0.0,
            "z2": 2.62,
            "power_w": 48.0,
            "watts_per_m": 9.6,
            "intensity": 1400.0,
            "dimming": 0.75,
            "kelvin": 2700.0,
            "automation_group": "living-cove",
        },
    )
    spec = _entity_light_spec(entity)
    assert spec["kind"] == "strip"
    assert spec["start"] == [0.0, 0.0, 2.62]
    assert spec["end"] == [5.0, 0.0, 2.62]
    assert spec["length_m"] == 5.0
    assert spec["watts_per_m"] == 9.6
    assert spec["power_w"] == 48.0
    assert spec["intensity"] == 1050.0
    assert spec["dimmer"] == 0.75
    assert spec["automation_group"] == "living-cove"


def test_non_lighting_electrical_point_is_not_rendered_as_a_light():
    entity = SimpleNamespace(
        id="socket-1",
        kind="electrical_point",
        params={"point_type": "socket", "x": 1.0, "y": 1.0, "z": 0.3},
    )
    assert _entity_light_spec(entity) is None
