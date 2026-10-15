from __future__ import annotations

import json


def _lighting_js() -> str:
    return r'''
// ArchForge architectural lighting -------------------------------------------------
// One renderer, one scene.  Project lights live in their own root so they can be
// rebuilt independently from geometry/material redraws.
const archLightRoot = new THREE.Group();
archLightRoot.name = "ArchForgeArchitecturalLights";
scene.add(archLightRoot);
let architecturalLightingMode = "day";

function afKelvinColor(kelvin) {
  // Practical black-body approximation, adequate for architectural 1800–10000 K.
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
  const c = afKelvinColor(spec.kelvin);
  const light = new THREE.PointLight(c, Number(spec.intensity || 400), Number(spec.range || 10), 2.0);
  light.position.set(position[0], position[1], position[2]);
  afConfigureShadow(light, spec);
  return light;
}

function afSpotLight(spec) {
  const c = afKelvinColor(spec.kelvin);
  const angle = THREE.MathUtils.degToRad(Math.max(1, Math.min(89, Number(spec.angle_deg || 35))));
  const light = new THREE.SpotLight(c, Number(spec.intensity || 700), Number(spec.range || 14), angle, Number(spec.penumbra ?? 0.35), 2.0);
  const p = spec.position || [0, 0, 2.4];
  const target = spec.target || [p[0], p[1] + 1, 0];
  light.position.set(p[0], p[1], p[2]);
  light.target.position.set(target[0], target[1], target[2]);
  archLightRoot.add(light.target);
  afConfigureShadow(light, spec);
  return light;
}

function afStripLights(spec) {
  // A hidden linear emitter is represented by a short row of physically-falling
  // point lights.  This gives cove/under-cabinet lighting without exposing a
  // visible bulb object.  Segment count is bounded for predictable GPU cost.
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
    const childSpec = Object.assign({}, spec, {intensity: total / n, shadows: false});
    group.add(afPointLight(childSpec, p));
  }
  return group;
}

window.setArchitecturalLights = function(payload) {
  afDisposeLightRoot();
  const lights = (payload && payload.lights) || [];
  for (const spec of lights) {
    if (!spec || spec.enabled === false) continue;
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
};

window.setArchitecturalLightingMode = function(mode) {
  mode = String(mode || "day").toLowerCase();
  if (!["day", "afternoon", "night"].includes(mode)) mode = "day";
  architecturalLightingMode = mode;
  window.__archforgeLightingMode = mode;
  if (typeof applySunAndSky === "function") applySunAndSky();
};
'''


def _install_html_patch(pbr_module) -> None:
    html = pbr_module._PBR_HTML
    marker = "// ArchForge architectural lighting -------------------------------------------------"
    if marker in html:
        return

    # Insert runtime after modelRoot exists so the light group belongs to the same scene.
    anchor = "const previewRoot = new THREE.Group();\nscene.add(previewRoot);"
    if anchor not in html:
        raise RuntimeError("PBR lighting install point changed")
    html = html.replace(anchor, anchor + "\n" + _lighting_js(), 1)

    # Extend the existing sun/sky function rather than creating another environment.
    old = '''  const useSky = !!sunState && activeTechnique === "pbr";\n  const technical = activeTechnique === "technical";\n  sky.visible = useSky;\n  scene.background = useSky ? lookCubeTarget.texture : new THREE.Color(technical ? 0xf4f5f7 : 0xd9dee5);'''
    new = '''  const night = architecturalLightingMode === "night" && activeTechnique === "pbr";\n  const afternoon = architecturalLightingMode === "afternoon" && activeTechnique === "pbr";\n  const useSky = !!sunState && activeTechnique === "pbr" && !night;\n  const technical = activeTechnique === "technical";\n  sky.visible = useSky;\n  scene.background = night ? new THREE.Color(0x07101d) :\n      (useSky ? lookCubeTarget.texture : new THREE.Color(technical ? 0xf4f5f7 : 0xd9dee5));'''
    if old not in html:
        raise RuntimeError("PBR sun/sky block changed")
    html = html.replace(old, new, 1)

    old2 = '''  scene.environment = useSky && lookSkyEnvironment ? lookSkyEnvironment : studioEnvironment;\n  scene.environmentIntensity = useSky ? 1.0 : 0.25;\n  // Distance haze into the horizon colour: the ground has no visible edge.\n  scene.fog = useSky ? new THREE.Fog(lookHorizon.clone(), 140, 1400) : null;\n  ground.visible = !technical;\n  ambient.intensity = useSky ? 0.0 : 0.12;'''
    new2 = '''  scene.environment = useSky && lookSkyEnvironment ? lookSkyEnvironment : studioEnvironment;\n  scene.environmentIntensity = night ? 0.035 : (afternoon ? 0.72 : (useSky ? 1.0 : 0.25));\n  // Distance haze into the horizon colour: the ground has no visible edge.\n  scene.fog = night ? new THREE.Fog(new THREE.Color(0x07101d), 95, 750) :\n      (useSky ? new THREE.Fog(lookHorizon.clone(), 140, 1400) : null);\n  ground.visible = !technical;\n  ambient.intensity = night ? 0.018 : (useSky ? 0.0 : 0.12);'''
    if old2 not in html:
        raise RuntimeError("PBR environment block changed")
    html = html.replace(old2, new2, 1)

    old3 = '''  if (useSky) {\n    // Low sun: warmer and weaker; below the horizon: no direct light.'''
    new3 = '''  if (night) {\n    key.intensity = 0.0;\n    fill.intensity = 0.025;\n    fill.color.set(0x6f86ad);\n  } else if (useSky) {\n    // Low sun: warmer and weaker; below the horizon: no direct light.'''
    if old3 not in html:
        raise RuntimeError("PBR direct-light block changed")
    html = html.replace(old3, new3, 1)

    pbr_module._PBR_HTML = html


def _entity_light_spec(entity):
    kind = str(getattr(entity, "kind", ""))
    if kind not in {"light", "light_point", "light_spot", "light_strip", "light_linear"}:
        return None
    p = dict(getattr(entity, "params", {}) or {})
    light_kind = str(p.get("light_kind") or kind.replace("light_", "") or "point")
    if light_kind == "light":
        light_kind = "point"
    spec = {
        "id": str(getattr(entity, "id", "")),
        "kind": light_kind,
        "enabled": bool(p.get("enabled", True)),
        "intensity": float(p.get("intensity", 700.0)),
        "kelvin": float(p.get("kelvin", 3000.0)),
        "range": float(p.get("range", 12.0)),
        "angle_deg": float(p.get("angle_deg", 35.0)),
        "penumbra": float(p.get("penumbra", 0.35)),
        "shadows": bool(p.get("shadows", light_kind == "spot")),
        "position": [float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("z", 2.4))],
    }
    if light_kind == "spot":
        spec["target"] = [
            float(p.get("target_x", p.get("x", 0.0))),
            float(p.get("target_y", float(p.get("y", 0.0)) + 1.0)),
            float(p.get("target_z", 0.0)),
        ]
    if light_kind in {"strip", "linear"}:
        spec["start"] = [
            float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("z", 2.4))
        ]
        spec["end"] = [
            float(p.get("x2", float(p.get("x", 0.0)) + 1.0)),
            float(p.get("y2", p.get("y", 0.0))),
            float(p.get("z2", p.get("z", 2.4))),
        ]
    return spec


def install_lighting_system() -> None:
    """Install architectural lighting on the existing PBR viewport.

    This is deliberately a presentation/integration layer: light entities remain
    ordinary project entities, so CommandStack/save-load can own them without a
    second lighting model.
    """
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

    def _lighting_payload(self):
        lights = []
        for entity in self.doc.entities.values():
            spec = _entity_light_spec(entity)
            if spec is not None:
                lights.append(spec)
        return {"lights": lights}

    def _push_architectural_lights(self):
        if self.web_view is None:
            return
        payload = json.dumps(self._lighting_payload(), separators=(",", ":"))
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
        # Afternoon gets a low warm sun; day keeps the user's current solar state.
        if mode == "afternoon":
            self.set_sun(17.0)
        self._push_architectural_lights()
        labels = {"day": "Ημέρα", "afternoon": "Απόγευμα", "night": "Νύχτα"}
        self.statusChanged.emit("Φωτισμός: " + labels[mode])

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
    cls._on_load_finished = _on_load_finished
    cls.redraw = redraw
    cls._arch_lighting_installed = True
