"""High-quality PBR look for the embedded Three.js viewport.

This is deliberately an isolated presentation-layer upgrade.  It patches the
embedded HTML before a PBR viewport is instantiated; the authoritative model,
geometry and material ids remain untouched.
"""
from __future__ import annotations


def _replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"render quality patch point missing: {old[:80]!r}")
    return text.replace(old, new, 1)


def install_rendering_quality_upgrade() -> None:
    from archforge.ui import pbr_viewport as pbr

    if getattr(pbr, "_archforge_quality_upgrade_installed", False):
        return

    html = pbr._PBR_HTML

    # ACES stays the tone mapper, but lift exposure slightly so white walls keep
    # readable mid-tones while still retaining highlight roll-off.
    html = _replace_once(
        html,
        "renderer.toneMappingExposure = 0.95;",
        "renderer.toneMappingExposure = 1.04;",
    )

    # The old studio look used a relatively flat ambient term.  Keep PMREM for
    # reflections, reduce flat ambient and add sky/ground hemispherical fill so
    # upward and downward facing surfaces receive naturally different light.
    html = _replace_once(
        html,
        "scene.environmentIntensity = 0.25;\nconst ambient = new THREE.AmbientLight(0xffffff, 0.12);\nscene.add(ambient);\nconst studioEnvironment = scene.environment;",
        "scene.environmentIntensity = 0.42;\n"
        "const ambient = new THREE.AmbientLight(0xffffff, 0.055);\n"
        "scene.add(ambient);\n"
        "const hemisphere = new THREE.HemisphereLight(0xdde9ff, 0x6f604d, 0.30);\n"
        "scene.add(hemisphere);\n"
        "const studioEnvironment = scene.environment;",
    )

    # Less 'dirty' AO, more believable contact depth.  This keeps corners and
    # wall/floor junctions grounded without making large surfaces look grey.
    html = _replace_once(
        html,
        "gtao.updateGtaoMaterial({radius: 0.6, distanceExponent: 1.0, thickness: 1.0, scale: 1.0});\n"
        "gtao.blendIntensity = 1.0;",
        "gtao.updateGtaoMaterial({radius: 0.38, distanceExponent: 1.25, thickness: 0.82, scale: 1.12});\n"
        "gtao.blendIntensity = 0.76;",
    )

    # Reduce the cold fill that previously flattened forms.  The environment
    # and hemisphere now provide the broad fill; this light is only a subtle
    # modelling light in studio mode.
    html = _replace_once(
        html,
        "const fill = new THREE.DirectionalLight(0xbfd8ff, 1.0);",
        "const fill = new THREE.DirectionalLight(0xc9ddff, 0.48);",
    )

    # Softer, cleaner sun shadows while keeping the existing 4k shadow map.
    html = _replace_once(
        html,
        "key.shadow.normalBias = 0.035;",
        "key.shadow.normalBias = 0.028;\nkey.shadow.radius = 2.25;",
    )

    # Use the physical material model for actual scene finishes (not helper
    # ghosts).  Existing roughness/metalness behaviour is preserved; physical
    # parameters can now be used by current/future material specs.
    html = _replace_once(
        html,
        "function materialFor(spec) {\n  const opacity = Number(spec.opacity ?? 1.0);\n  const material = new THREE.MeshStandardMaterial({",
        "function materialFor(spec) {\n  const opacity = Number(spec.opacity ?? 1.0);\n  const material = new THREE.MeshPhysicalMaterial({",
    )

    # Set physically meaningful optional finish properties after construction.
    html = _replace_once(
        html,
        "  material.userData.baseOpacity = opacity;",
        "  material.ior = Number(spec.ior ?? 1.5);\n"
        "  material.clearcoat = Number(spec.clearcoat ?? 0.0);\n"
        "  material.clearcoatRoughness = Number(spec.clearcoatRoughness ?? 0.22);\n"
        "  material.envMapIntensity = Number(spec.envMapIntensity ?? 1.08);\n"
        "  material.userData.baseOpacity = opacity;",
    )

    # Keep outdoor scenes bright from the sky but avoid the previous overly
    # strong environment response.  Hemisphere light is disabled in technical
    # mode and gently retained in PBR sunlight mode for natural bounce.
    html = _replace_once(
        html,
        "scene.environmentIntensity = useSky ? 1.0 : 0.25;",
        "scene.environmentIntensity = useSky ? 0.88 : 0.42;\n"
        "  hemisphere.intensity = technical ? 0.0 : (useSky ? 0.18 : 0.30);",
    )
    html = _replace_once(
        html,
        "ambient.intensity = useSky ? 0.0 : 0.12;",
        "ambient.intensity = useSky ? 0.0 : 0.055;",
    )

    pbr._PBR_HTML = html
    pbr._archforge_quality_upgrade_installed = True
