from __future__ import annotations

import json


def _lighting_js() -> str:
    return r'''
// ArchForge architectural lighting -------------------------------------------------
const archLightRoot = new THREE.Group();
archLightRoot.name = "ArchForgeArchitecturalLights";
scene.add(archLightRoot);
let architecturalLightingMode = "day";

function afKelvinColor(kelvin) {
  let t = Math.max(18, Math.min(100, Number(kelvin || 3000) / 100));
  let r, g, b;
  if (t <= 66) {
    r = 255;
    g = 99.4708025861 * Math.log(t) - 161.1195681661;
    b = t <= 19 ? 0 : 138.5177312231 * Math.log(t - 10) - 305.0447927307;
  } else {
    r = 329.698727446 * Math.pow(t - 60, -0.1332047592);
    g = 288.1221695283 * Math.pow(t - 60, -0.0755148492);
    b = 255;
  }
  const clamp = (v) => Math.max(0, Math.min(255, v)) / 255;
  return new THREE.Color(clamp(r), clamp(g), clamp(b));
}

function afDisposeLightRoot() {
  while (archLightRoot.children.length) {
    const child = archLightRoot.children.pop();
    if (child.target && child.target.parent) child.target.parent.remove(child.target);
    if (child.geometry) child.geometry.dispose();
    if (child.material) child.material.dispose();
    if (child.dispose) child.dispose();
  }
}

function afConfigureShadow(light, spec) {
  if (!spec.shadows) return;
  light.castShadow = true;
  if (light.shadow && light.shadow.mapSize) light.shadow.mapSize.set(1024, 1024);
  if (light.shadow) {
    light.shadow.bias = -0.00025;
    light.shadow.normalBias = 0.025;
    if (light.shadow.camera) light.shadow.camera.far = Math.max(8, Number(spec.range || 12));
  }
}

function afPointLight(spec, position) {
  const light = new THREE.PointLight(
    afKelvinColor(spec.kelvin), Number(spec.intensity || 400), Number(spec.range || 10), 2.0
  );
  light.position.set(position[0], position[1], position[2]);
  afConfigureShadow(light, spec);
  return light;
}

function afSpotLight(spec) {
  const angle = THREE.MathUtils.degToRad(Math.max(1, Math.min(89, Number(spec.angle_deg || 35))));
  const light = new THREE.SpotLight(
    afKelvinColor(spec.kelvin), Number(spec.intensity || 700), Number(spec.range || 14),
    angle, Number(spec.penumbra ?? 0.35), 2.0
  );
  const p = spec.position || [0, 0, 2.4];
  const target = spec.target || [p[0], p[1] + 1, 0];
  light.position.set(p[0], p[1], p[2]);
  light.target.position.set(target[0], target[1], target[2]);
  archLightRoot.add(light.target);
  afConfigureShadow(light, spec);
  return light;
}

function afStripLights(spec) {
  // Hidden LED/cove emitter: bounded row of point emitters so the source itself
  // need not be visible.  The bound keeps night scenes predictable on laptops.
  const a = spec.start || spec.position || [0, 0, 2.4];
  const b = spec.end || [a[0] + 1, a[1], a[2]];
  const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2];
  const length = Math.hypot(dx, dy, dz);
  const n = Math.max(2, Math.min(12, Math.ceil(length / 0.65)));
  const total = Number(spec.intensity || 900);
  const group = new THREE.Group();
  for (let i = 0; i < n; i++) {
    const t = n === 1 ? 0.5 : i / (n - 1);
    const p = [a[0] + dx * t, a[1] + dy * t, a[2] + dz * t];
    group.add(afPointLight(Object.assign({}, spec, {intensity: total / n, shadows: false}), p));
  }
  return group;
}

// Owner 25/10 («μεσημέρι και τα φώτα αναμμένα — πού τα κλείνω;»): the project's lights shine only at night unless
// the menu «Φώτα του έργου» says always on / off.
let architecturalLightsSwitch = "auto";
function afUpdateLightVisibility() {
  archLightRoot.visible = architecturalLightsSwitch === "on" ||
      (architecturalLightsSwitch === "auto" && architecturalLightingMode === "night");
  window.__archforgeProjectLightsOn = archLightRoot.visible;
}

window.setArchitecturalLights = function(payload) {
  afDisposeLightRoot();
  const wanted = String((payload && payload.project_lights) || "auto");
  architecturalLightsSwitch = ["auto", "on", "off"].includes(wanted) ? wanted : "auto";
  let shadowBudget = 16;          // a point light's shadow is 6 extra renders: bounded for laptops
  for (const raw of ((payload && payload.lights) || [])) {
    if (!raw || raw.enabled === false) continue;
    const spec = Object.assign({}, raw, {shadows: !!raw.shadows && shadowBudget > 0});
    if (spec.shadows) shadowBudget--;
    const kind = String(spec.kind || "point");
    let light = null;
    if (kind === "spot") light = afSpotLight(spec);
    else if (kind === "strip" || kind === "linear") light = afStripLights(spec);
    else light = afPointLight(spec, spec.position || [0, 0, 2.4]);
    if (light) {
      light.userData.entityId = String(spec.id || "");
      light.userData.archLight = true;
      archLightRoot.add(light);
    }
  }
  afUpdateLightVisibility();
};

window.setArchitecturalLightingMode = function(mode) {
  mode = String(mode || "day").toLowerCase();
  if (!["day", "afternoon", "night"].includes(mode)) mode = "day";
  architecturalLightingMode = mode;
  window.__archforgeLightingMode = mode;
  afUpdateLightVisibility();
  if (typeof applySunAndSky === "function") applySunAndSky();
};
'''


PROJECT_LIGHTS = {"auto": "αυτόματα (μόνο τη νύχτα)", "on": "πάντα αναμμένα", "off": "σβηστά"}


def _replace_one_of(text: str, candidates: tuple[str, ...], new: str, label: str) -> str:
    for old in candidates:
        if old in text:
            return text.replace(old, new, 1)
    raise RuntimeError(f"PBR lighting patch point changed: {label}")


def _install_html_patch(pbr_module) -> None:
    html = pbr_module._PBR_HTML
    marker = "// ArchForge architectural lighting -------------------------------------------------"
    if marker in html:
        return

    anchor = "const previewRoot = new THREE.Group();\nscene.add(previewRoot);"
    if anchor not in html:
        raise RuntimeError("PBR lighting install point changed")
    html = html.replace(anchor, anchor + "\n" + _lighting_js(), 1)

    html = _replace_one_of(
        html,
        ('''  const useSky = !!sunState && activeTechnique === "pbr";\n  const technical = activeTechnique === "technical";\n  sky.visible = useSky;\n  scene.background = useSky ? lookCubeTarget.texture : new THREE.Color(technical ? 0xf4f5f7 : 0xd9dee5);''',),
        '''  const night = architecturalLightingMode === "night" && activeTechnique === "pbr";\n  const afternoon = architecturalLightingMode === "afternoon" && activeTechnique === "pbr";\n  const useSky = !!sunState && activeTechnique === "pbr" && !night;\n  const technical = activeTechnique === "technical";\n  sky.visible = useSky;\n  scene.background = night ? new THREE.Color(0x07101d) :\n      (useSky ? lookCubeTarget.texture : new THREE.Color(technical ? 0xf4f5f7 : 0xd9dee5));''',
        "sun/sky",
    )

    base_environment = '''  scene.environment = useSky && lookSkyEnvironment ? lookSkyEnvironment : studioEnvironment;\n  scene.environmentIntensity = useSky ? 1.0 : 0.25;\n  // Distance haze into the horizon colour: the ground has no visible edge.\n  scene.fog = useSky ? new THREE.Fog(lookHorizon.clone(), 140, 1400) : null;\n  ground.visible = !technical;\n  ambient.intensity = useSky ? 0.0 : 0.12;'''
    quality_environment = '''  scene.environment = useSky && lookSkyEnvironment ? lookSkyEnvironment : studioEnvironment;\n  scene.environmentIntensity = useSky ? 0.88 : 0.42;\n  hemisphere.intensity = technical ? 0.0 : (useSky ? 0.18 : 0.30);\n  // Distance haze into the horizon colour: the ground has no visible edge.\n  scene.fog = useSky ? new THREE.Fog(lookHorizon.clone(), 140, 1400) : null;\n  ground.visible = !technical;\n  ambient.intensity = useSky ? 0.0 : 0.055;'''
    environment_new = '''  scene.environment = useSky && lookSkyEnvironment ? lookSkyEnvironment : studioEnvironment;\n  scene.environmentIntensity = night ? 0.035 : (afternoon ? 0.72 : (useSky ? 0.88 : 0.42));\n  if (typeof hemisphere !== "undefined") hemisphere.intensity = technical ? 0.0 : (night ? 0.035 : (useSky ? 0.18 : 0.30));\n  // Distance haze into the horizon colour: the ground has no visible edge.\n  scene.fog = night ? new THREE.Fog(new THREE.Color(0x07101d), 95, 750) :\n      (useSky ? new THREE.Fog(lookHorizon.clone(), 140, 1400) : null);\n  ground.visible = !technical;\n  ambient.intensity = night ? 0.018 : (useSky ? 0.0 : 0.055);'''
    html = _replace_one_of(html, (quality_environment, base_environment), environment_new, "environment")

    html = _replace_one_of(
        html,
        ('''  if (useSky) {\n    // Low sun: warmer and weaker; below the horizon: no direct light.''',),
        '''  if (night) {\n    key.intensity = 0.0;\n    fill.intensity = 0.025;\n    fill.color.set(0x6f86ad);\n  } else if (useSky) {\n    // Low sun: warmer and weaker; below the horizon: no direct light.''',
        "direct light",
    )
    pbr_module._PBR_HTML = html


def _light_z(doc, kind, p):
    """Height of the light: an electrical point at its real mount (ceiling / mounting height, as the electrical
    drawings place it) — its ``z`` is the floor it stands on, so a ceiling light sat on the floor and lit the
    ground and the slab from below. Native light entities keep their own ``z``."""
    if kind == "electrical_point" and doc is not None:
        try:
            from archforge.mep.electrical import mount_z
            z = float(mount_z(doc, p))
        except (KeyError, TypeError, ValueError, ImportError):
            return float(p.get("z", 2.4))
        # Never above the walls of its storey: with no storey above, the electrical «ceiling» is floor + 2,80 m, inside
        # the roof of 2,70 m walls — the light then lit the eaves. (The same 2,80 for the ceiling conduits is noted
        # in HANDOFF for the electrical side.)
        floor = float(p.get("z", 0.0))
        tops = [float(e.params.get("z", 0.0)) + float(e.params.get("height", 0.0)) for e in doc.entities.values()
                if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - floor) <= 0.05]
        return min(z, max(tops) - 0.05) if tops else z
    return float(p.get("z", 2.4))


def _entity_light_spec(entity, doc=None):
    """Map both native ArchForge lights and electrical lighting points to one PBR spec.

    Electrical points remain the authoritative project objects.  Photometric
    fields are optional params on the same entity, so circuit/switch/automation
    data and the rendered light never drift into parallel models.
    """
    kind = str(getattr(entity, "kind", ""))
    p = dict(getattr(entity, "params", {}) or {})

    electrical_point_type = ""
    if kind == "electrical_point":
        electrical_point_type = str(p.get("point_type", ""))
        electrical_kinds = {
            "light": "point",
            "wall_light": "spot",
            "spot": "spot",
            "spot_light": "spot",
            "downlight": "spot",
            "wall_washer": "spot",
            "hidden_light": "strip",
            "linear_light": "strip",
            "led_strip": "strip",
        }
        if electrical_point_type not in electrical_kinds:
            return None
        light_kind = str(p.get("light_kind") or electrical_kinds[electrical_point_type])
    else:
        if kind not in {"light", "light_point", "light_spot", "light_strip", "light_linear"}:
            return None
        light_kind = str(p.get("light_kind") or kind.replace("light_", "") or "point")
        if light_kind == "light":
            light_kind = "point"

    # Renderer intensity is deliberately separate from electrical watts.
    # power_w remains available to circuit/load calculations; dimming affects
    # the visible output without silently rewriting the electrical design load.
    # Per luminaire (Ιδιότητες, mep/lighting.py): the dimmer slider «dim_level», «Αναμμένο», lumen → candela, the
    # beam and the aim of an adjustable head.  ``dimming`` there is the driver protocol (text), not a level.
    intensity = float(p.get("intensity", p.get("render_intensity", 700.0)))
    level = p.get("dim_level", p.get("dimmer", p.get("dimming", 1.0)))
    try:
        dimmer = max(0.0, min(1.0, float(level)))
    except (TypeError, ValueError):
        dimmer = 1.0
    mep = None
    if electrical_point_type and doc is not None:
        from archforge.mep.lighting import is_luminaire, light_spec
        if is_luminaire(entity):
            mep = light_spec(doc, entity)
    if mep is not None and mep.get("intensity") is not None:
        intensity = float(mep["intensity"])        # from the data sheet's lumen, already dimmed
    else:
        intensity *= dimmer

    spec = {
        "id": str(getattr(entity, "id", "")),
        "kind": light_kind,
        "enabled": bool(p.get("enabled", True)) and bool(int(p.get("light_on", 1))) and dimmer > 0,
        "intensity": intensity,
        "kelvin": float(p.get("kelvin", 3000.0)),
        "range": float(p.get("range", 12.0)),
        # The data sheet's beam is the full cone; the renderer's angle is half of it.
        "angle_deg": (float(p["beam_deg"]) / 2 if "beam_deg" in p
                      else float(p.get("angle_deg", p.get("beam_angle_deg", 35.0)))),
        "penumbra": float(p.get("penumbra", 0.35)),
        # Walls and roof stop the light: a ceiling light without shadows lit the eaves and the ground through
        # them (owner 25/10: «το φως έπρεπε να φαίνεται μόνο από τα παράθυρα»).
        "shadows": bool(p.get("shadows", light_kind in ("point", "spot"))),
        "position": [float(p.get("x", 0.0)), float(p.get("y", 0.0)), _light_z(doc, kind, p)],
        "electrical_point_type": electrical_point_type,
        "power_w": float(p.get("power_w", 0.0)),
        "dimmer": dimmer,
        "automation_group": str(p.get("automation_group", "")),
    }
    if mep is not None and mep.get("kelvin"):
        spec["kelvin"] = float(mep["kelvin"])
    aimed = None
    if light_kind == "spot" and electrical_point_type:
        from archforge.mep.lighting import aim_target
        position = spec["position"]
        aimed = aim_target(doc, p, *position)
    if aimed is not None:
        spec["target"] = [float(v) for v in aimed]
    elif light_kind == "spot":
        spec["target"] = [
            float(p.get("target_x", p.get("x", 0.0))),
            float(p.get("target_y", float(p.get("y", 0.0)) + 1.0)),
            float(p.get("target_z", 0.0)),
        ]
    if light_kind in {"strip", "linear"}:
        spec["start"] = [float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("z", 2.4))]
        spec["end"] = [
            float(p.get("x2", float(p.get("x", 0.0)) + 1.0)),
            float(p.get("y2", p.get("y", 0.0))),
            float(p.get("z2", p.get("z", 2.4))),
        ]
        dx = spec["end"][0] - spec["start"][0]
        dy = spec["end"][1] - spec["start"][1]
        dz = spec["end"][2] - spec["start"][2]
        spec["length_m"] = (dx * dx + dy * dy + dz * dz) ** 0.5
        spec["watts_per_m"] = float(p.get("watts_per_m", 0.0))
    return spec


def install_lighting_system() -> None:
    """Install night mode and project lights on the existing PBR scene."""
    from archforge.ui import pbr_viewport as pbr

    if getattr(pbr.PBRViewport, "_arch_lighting_installed", False):
        return
    _install_html_patch(pbr)
    cls = pbr.PBRViewport
    original_init = cls.__init__
    original_on_load = cls._on_load_finished
    original_redraw = cls.redraw

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._architectural_lighting_mode = "day"
        self._project_lights = "auto"

    def _lighting_payload(self):
        lights = []
        for entity in self.doc.entities.values():
            spec = _entity_light_spec(entity, self.doc)
            if spec is not None:
                lights.append(spec)
        return {"lights": lights}

    def _push_architectural_lights(self):
        if self.web_view is None:
            return
        payload = dict(self._lighting_payload())
        payload["project_lights"] = getattr(self, "_project_lights", "auto")
        payload = json.dumps(payload, separators=(",", ":"))
        mode = json.dumps(str(self._architectural_lighting_mode))
        self.web_view.page().runJavaScript(
            "if(window.setArchitecturalLightingMode)window.setArchitecturalLightingMode(" + mode + ");"
            "if(window.setArchitecturalLights)window.setArchitecturalLights(" + payload + ");"
        )

    def set_lighting_mode(self, mode: str) -> None:
        mode = str(mode).lower()
        if mode not in {"day", "afternoon", "night"}:
            raise ValueError("lighting mode must be day, afternoon or night")
        self._architectural_lighting_mode = mode
        if mode == "afternoon":
            self.set_sun(17.0)
        self._push_architectural_lights()
        labels = {"day": "Ημέρα", "afternoon": "Απόγευμα", "night": "Νύχτα"}
        self.statusChanged.emit("Φωτισμός: " + labels[mode])

    def set_project_lights(self, mode: str) -> None:
        """The project's luminaires in 3D: «auto» = only at night, «on» = always, «off» = never (each one's own
        «Αναμμένο» still applies)."""
        mode = str(mode).lower()
        if mode not in PROJECT_LIGHTS:
            raise ValueError("project lights must be auto, on or off")
        self._project_lights = mode
        self._push_architectural_lights()
        self.statusChanged.emit("Φώτα του έργου: " + PROJECT_LIGHTS[mode])

    def _on_load_finished(self, ok: bool) -> None:
        original_on_load(self, ok)
        if ok:
            self._push_architectural_lights()

    def redraw(self, *args, **kwargs):
        result = original_redraw(self, *args, **kwargs)
        self._push_architectural_lights()
        return result

    cls.__init__ = __init__
    cls._lighting_payload = _lighting_payload
    cls._push_architectural_lights = _push_architectural_lights
    cls.set_lighting_mode = set_lighting_mode
    cls.set_project_lights = set_project_lights
    cls._on_load_finished = _on_load_finished
    cls.redraw = redraw
    cls._arch_lighting_installed = True
