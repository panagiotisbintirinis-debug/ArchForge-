from __future__ import annotations


def _renderer_specs_from_mep(doc):
    """Return renderer specs from the authoritative MEP lighting model.

    This adapter deliberately does not invent missing photometric values.
    Luminaires that are valid electrical objects but do not yet have enough
    data-sheet photometry stay in the electrical/plan model and are omitted
    from physically interpreted PBR emission until those values exist.
    """
    from archforge.mep.lighting import light_specs

    specs = light_specs(doc)
    renderable = []
    for spec in specs:
        if spec.get("enabled") is False:
            continue
        if spec.get("kelvin") is None:
            continue
        if spec.get("intensity") is None:
            continue
        renderable.append(spec)
    return renderable


def install_mep_lighting_bridge() -> None:
    """Make the PBR viewport consume ``mep.lighting.light_specs`` directly.

    ``install_lighting_system`` still owns the Three.js scene and day/afternoon/
    night modes.  This bridge changes only the source of luminaire data so the
    renderer never maintains a parallel lighting model.
    """
    from archforge.ui import pbr_viewport as pbr
    from archforge.ui.lighting_system import install_lighting_system

    install_lighting_system()
    cls = pbr.PBRViewport
    if getattr(cls, "_arch_mep_lighting_bridge_installed", False):
        return

    fallback_payload = cls._lighting_payload

    def _lighting_payload(self):
        try:
            lights = _renderer_specs_from_mep(self.doc)
        except ModuleNotFoundError:
            # Transitional branch before archforge.mep.lighting is merged.
            return fallback_payload(self)
        return {"lights": lights}

    cls._lighting_payload = _lighting_payload
    cls._arch_mep_lighting_bridge_installed = True
