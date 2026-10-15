from archforge.ui import pbr_viewport as pbr
from archforge.ui.rendering_quality_upgrade import install_rendering_quality_upgrade


def test_realistic_pbr_quality_layer_is_installed_idempotently():
    install_rendering_quality_upgrade()
    first = pbr._PBR_HTML
    install_rendering_quality_upgrade()
    second = pbr._PBR_HTML

    assert first == second
    assert "renderer.toneMappingExposure = 1.04;" in first
    assert "new THREE.HemisphereLight(0xdde9ff, 0x6f604d, 0.30)" in first
    assert "radius: 0.38" in first
    assert "gtao.blendIntensity = 0.76;" in first
    assert "new THREE.MeshPhysicalMaterial({" in first
    assert "material.envMapIntensity = Number(spec.envMapIntensity ?? 1.08);" in first
    assert "scene.environmentIntensity = useSky ? 0.88 : 0.42;" in first
