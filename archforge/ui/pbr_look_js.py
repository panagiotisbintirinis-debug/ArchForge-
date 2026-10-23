"""The look of the 3D Scene: sky with clouds, ground to the horizon, surface grain.

Everything here is generated in the page (no image files, no downloads) and
is render state only; it reads the derived scene and never the Document.

- Sky: an analytic daylight sky (zenith/horizon gradient, sun disc and glow,
  procedural clouds) drawn once per sun change into a cube map that is both
  the background and, prefiltered (PMREM), the image-based light.  A cube
  background has no far-plane trick, so it shows on every GPU/driver.
- Ground: one large disc with a dry Mediterranean soil/grass texture in
  metres (the same material as a site terrain, so they join without a seam)
  fading into the horizon colour through fog: no visible edge or "box".
- Grain: tileable colour-variation, normal and roughness maps per surface
  family (plaster, concrete, timber, roof tiles, metal, ...), at real size
  through the metric UVs of the mesh (archforge/rendering/grain.py).
"""
from __future__ import annotations


def pbr_look_js() -> str:
    return r'''
// --- Look: sky, ground, surface grain (archforge/ui/pbr_look_js.py) ---------
// Tileable value noise on a W x H grid; ``cells`` lattice cells per side.
function lookRandom(seed) {
  let a = seed >>> 0;
  return function() {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function lookNoise(W, H, cx, cy, seed) {
  const rnd = lookRandom(seed);
  const lat = new Float32Array(cx * cy);
  for (let i = 0; i < lat.length; i++) lat[i] = rnd();
  const out = new Float32Array(W * H);
  for (let y = 0; y < H; y++) {
    const fy = y / H * cy, y0 = Math.floor(fy), ty = fy - y0;
    const sy = ty * ty * (3 - 2 * ty);
    const r0 = (y0 % cy) * cx, r1 = ((y0 + 1) % cy) * cx;
    for (let x = 0; x < W; x++) {
      const fx = x / W * cx, x0 = Math.floor(fx), tx = fx - x0;
      const sx = tx * tx * (3 - 2 * tx);
      const c0 = x0 % cx, c1 = (x0 + 1) % cx;
      const a = lat[r0 + c0] + (lat[r0 + c1] - lat[r0 + c0]) * sx;
      const b = lat[r1 + c0] + (lat[r1 + c1] - lat[r1 + c0]) * sx;
      out[y * W + x] = a + (b - a) * sy;
    }
  }
  return out;
}
// Fractal sum, normalised to 0..1; cells double per octave (stays tileable).
function lookFbm(W, H, cx, cy, octaves, seed, gain = 0.5) {
  const out = new Float32Array(W * H);
  let amp = 1, total = 0;
  for (let o = 0; o < octaves; o++) {
    const n = lookNoise(W, H, cx << o, cy << o, seed + o * 1013);
    for (let i = 0; i < out.length; i++) out[i] += n[i] * amp;
    total += amp; amp *= gain;
  }
  for (let i = 0; i < out.length; i++) out[i] /= total;
  return out;
}
function lookCanvas(W, H, pixel) {
  const canvas = document.createElement("canvas");
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext("2d");
  const img = ctx.createImageData(W, H);
  const d = img.data;
  for (let i = 0, p = 0; i < W * H; i++, p += 4) {
    const c = pixel(i);
    d[p] = c[0]; d[p + 1] = c[1]; d[p + 2] = c[2]; d[p + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  return canvas;
}
// Tangent-space normal map from a height field (wraps at the edges).
function lookNormalCanvas(h, W, H, strength) {
  return lookCanvas(W, H, (i) => {
    const x = i % W, y = (i / W) | 0;
    const l = h[y * W + (x + W - 1) % W], r = h[y * W + (x + 1) % W];
    const u = h[((y + H - 1) % H) * W + x], dn = h[((y + 1) % H) * W + x];
    let nx = (l - r) * strength, ny = (dn - u) * strength, nz = 1.0;
    const len = Math.hypot(nx, ny, nz);
    return [(nx / len * 0.5 + 0.5) * 255, (ny / len * 0.5 + 0.5) * 255, (nz / len * 0.5 + 0.5) * 255];
  });
}
const lookClamp = (v) => Math.max(0, Math.min(255, v));

// Each family: size of one tile in metres and the maps.  ``tint`` maps are
// near-white and multiply the material colour; ``full`` maps carry the colour.
const GRAIN_SPECS = {
  plaster: {size: 2.0, build(W) {
    const sand = lookNoise(W, W, 256, 256, 11), grit = lookNoise(W, W, 96, 96, 12);
    const trowel = lookFbm(W, W, 4, 4, 4, 13), blot = lookFbm(W, W, 3, 3, 4, 14);
    const h = new Float32Array(W * W);
    for (let i = 0; i < h.length; i++) h[i] = 0.55 * sand[i] + 0.30 * grit[i] + 0.35 * trowel[i];
    return {
      map: lookCanvas(W, W, (i) => { const v = 247 - 16 * blot[i] - 7 * sand[i] + 6 * trowel[i]; return [v, v, v * 0.995]; }),
      normal: lookNormalCanvas(h, W, W, 2.2),
      rough: lookCanvas(W, W, (i) => { const v = 225 + 30 * grit[i] - 20 * trowel[i]; return [v, v, v]; }),
      normalScale: 0.9,
    };
  }},
  concrete: {size: 2.4, build(W) {
    const pores = lookNoise(W, W, 320, 320, 21), fine = lookNoise(W, W, 128, 128, 22);
    const mottle = lookFbm(W, W, 4, 4, 5, 23), cloud = lookFbm(W, W, 2, 2, 3, 24);
    const h = new Float32Array(W * W);
    for (let i = 0; i < h.length; i++) h[i] = 0.5 * fine[i] + 0.3 * mottle[i] - (pores[i] > 0.80 ? (pores[i] - 0.80) * 4.0 : 0);
    return {
      map: lookCanvas(W, W, (i) => {
        let v = 236 - 34 * mottle[i] - 16 * cloud[i] + 10 * fine[i];
        if (pores[i] > 0.80) v -= (pores[i] - 0.80) * 260;
        return [v, v * 0.995, v * 0.985];
      }),
      normal: lookNormalCanvas(h, W, W, 2.0),
      rough: lookCanvas(W, W, (i) => { const v = 200 + 50 * mottle[i]; return [v, v, v]; }),
      normalScale: 0.8,
    };
  }},
  wood: {size: 1.2, build(W) {
    // Grain runs along u (the length of a board, a wall, a rafter).
    const warp = lookFbm(W, W, 2, 8, 4, 31), fine = lookNoise(W, W, 8, 256, 32);
    const knots = lookFbm(W, W, 3, 6, 3, 33), plank = lookNoise(W, W, 1, 12, 34);
    const h = new Float32Array(W * W), ring = new Float32Array(W * W);
    for (let i = 0; i < h.length; i++) {
      const y = ((i / W) | 0) / W;
      const r = 0.5 + 0.5 * Math.sin((y * 46 + warp[i] * 7 + knots[i] * 3) * Math.PI);
      ring[i] = Math.pow(r, 3.0);
      h[i] = 0.6 * ring[i] + 0.4 * fine[i];
    }
    return {
      map: lookCanvas(W, W, (i) => {
        const v = 238 - 46 * ring[i] - 22 * fine[i] - 26 * plank[i];
        return [v, v * 0.97, v * 0.93];
      }),
      normal: lookNormalCanvas(h, W, W, 1.4),
      rough: lookCanvas(W, W, (i) => { const v = 190 + 50 * ring[i]; return [v, v, v]; }),
      normalScale: 0.6,
    };
  }},
  roof_tile: {size: 2.0, build(W) {
    // Curved (roman/byzantine) tiles: 10 channels of 0.20 m across u,
    // 5 courses of 0.40 m up the slope (v); each course laps the next one.
    const age = lookFbm(W, W, 6, 6, 5, 41), fine = lookNoise(W, W, 192, 192, 42);
    const rnd = lookRandom(43), tone = [];
    for (let k = 0; k < 50; k++) tone.push(rnd());
    const h = new Float32Array(W * W), shade = new Float32Array(W * W), id = new Uint8Array(W * W);
    for (let i = 0; i < h.length; i++) {
      const x = (i % W) / W, y = ((i / W) | 0) / W;
      const cu = x * 10, cv = (1 - y) * 5;           // canvas y runs down, v up the slope
      const across = cu - Math.floor(cu), up = cv - Math.floor(cv);
      const arch = Math.sin(across * Math.PI);        // rounded tile, troughs between
      const lap = 1 - up;                             // thick lower edge, thin under the course above
      h[i] = 0.70 * arch + 0.45 * lap + 0.05 * fine[i];
      // Dark gap where the course above overlaps, soft shade in the troughs.
      shade[i] = (0.55 + 0.45 * arch) * (up > 0.94 ? 0.55 : 1.0) * (0.85 + 0.15 * Math.min(1, lap * 3));
      id[i] = (Math.floor(cu) + 10 * Math.floor(cv)) % 50;
    }
    return {
      map: lookCanvas(W, W, (i) => {
        const t = tone[id[i]];
        const v = (210 + 45 * t - 40 * age[i]) * shade[i];
        return [v * 1.02, v * (0.96 + 0.05 * t), v * (0.90 + 0.08 * age[i])];
      }),
      normal: lookNormalCanvas(h, W, W, 6.0),
      rough: lookCanvas(W, W, (i) => { const v = 175 + 60 * age[i]; return [v, v, v]; }),
      normalScale: 1.0,
    };
  }},
  metal: {size: 1.0, build(W) {
    const brush = lookNoise(W, W, 4, 384, 51), soft = lookFbm(W, W, 3, 3, 3, 52);
    return {
      map: lookCanvas(W, W, (i) => { const v = 244 - 10 * brush[i] - 8 * soft[i]; return [v, v, v]; }),
      normal: lookNormalCanvas(brush, W, W, 0.8),
      rough: lookCanvas(W, W, (i) => { const v = 205 + 40 * brush[i] + 10 * soft[i]; return [v, v, v]; }),
      normalScale: 0.25,
    };
  }},
  fabric: {size: 0.25, build(W) {
    const fine = lookNoise(W, W, 64, 64, 61);
    const weave = new Float32Array(W * W);
    for (let i = 0; i < weave.length; i++) {
      const x = (i % W) / W * 96, y = ((i / W) | 0) / W * 96;
      weave[i] = 0.5 + 0.25 * Math.sin(x * Math.PI * 2) * Math.sign(Math.sin(y * Math.PI)) + 0.25 * fine[i];
    }
    return {
      map: lookCanvas(W, W, (i) => { const v = 238 - 22 * weave[i]; return [v, v, v]; }),
      normal: lookNormalCanvas(weave, W, W, 1.5),
      rough: lookCanvas(W, W, () => [255, 255, 255]),
      normalScale: 0.5,
    };
  }},
  smooth: {size: 1.0, build(W) {
    const soft = lookFbm(W, W, 4, 4, 4, 71);
    return {
      map: lookCanvas(W, W, (i) => { const v = 250 - 6 * soft[i]; return [v, v, v]; }),
      normal: null,
      rough: lookCanvas(W, W, (i) => { const v = 230 + 25 * soft[i]; return [v, v, v]; }),
      normalScale: 0,
    };
  }},
  soil: {size: 4.0, full: true, build(W) {
    // Bare dry Mediterranean soil, fine detail only: ochre earth, clods, grit
    // and a few small pebbles.  The large patches (soil / dry grass) come
    // from a world-space mask in the shader, so nothing repeats every tile.
    const clod = lookFbm(W, W, 24, 24, 4, 81), grit = lookNoise(W, W, 256, 256, 84);
    const fine = lookNoise(W, W, 96, 96, 82), stone = lookNoise(W, W, 72, 72, 85);
    const h = new Float32Array(W * W), col = new Array(W * W);
    const soil = [146, 124, 94], pale = [178, 162, 132], pebble = [184, 176, 160];
    for (let i = 0; i < h.length; i++) {
      const isStone = stone[i] > 0.90 ? Math.min(1, (stone[i] - 0.90) * 22) : 0;
      const t = Math.max(0, Math.min(1, (clod[i] - 0.35) * 1.6));
      let c = [0, 1, 2].map((k) => soil[k] + (pale[k] - soil[k]) * t);
      const shade = 0.86 + 0.16 * fine[i] + 0.12 * grit[i];
      c = c.map((v, k) => v * shade + (pebble[k] * (0.9 + 0.2 * grit[i]) - v * shade) * isStone);
      col[i] = c;
      h[i] = 0.45 * grit[i] + 0.35 * clod[i] + 0.25 * fine[i] + 0.6 * isStone;
    }
    return {
      map: lookCanvas(W, W, (i) => col[i].map(lookClamp)),
      normal: lookNormalCanvas(h, W, W, 3.0),
      rough: lookCanvas(W, W, () => [255, 255, 255]),
      normalScale: 1.0,
    };
  }},
  dry_grass: {size: 3.0, full: true, build(W) {
    // Straw-coloured grass with olive-green tufts; blended over the soil.
    const tuft = lookFbm(W, W, 16, 16, 4, 86), blade = lookNoise(W, W, 384, 96, 83);
    const blade2 = lookNoise(W, W, 96, 384, 87), grit = lookNoise(W, W, 256, 256, 88);
    const straw = [166, 150, 108], olive = [104, 112, 84], earth = [140, 116, 86];
    const h = new Float32Array(W * W), col = new Array(W * W);
    for (let i = 0; i < h.length; i++) {
      const b = 0.5 * blade[i] + 0.5 * blade2[i];
      const green = Math.min(1, Math.max(0, (tuft[i] - 0.55) * 3.5));
      const gap = Math.min(1, Math.max(0, (0.42 - b) * 4.0));   // soil between blades
      let c = [0, 1, 2].map((k) => straw[k] + (olive[k] - straw[k]) * green);
      c = c.map((v, k) => (v + (earth[k] - v) * gap) * (0.80 + 0.35 * b + 0.06 * grit[i]));
      col[i] = c;
      h[i] = b;
    }
    return {
      map: lookCanvas(W, W, (i) => col[i].map(lookClamp)),
      normal: lookNormalCanvas(h, W, W, 2.5),
      rough: lookCanvas(W, W, () => [255, 255, 255]),
      normalScale: 0.8,
    };
  }},
  grass: {size: 4.0, full: true, build(W) {
    const patch = lookFbm(W, W, 4, 4, 5, 91), blade = lookNoise(W, W, 512, 128, 92);
    const blade2 = lookNoise(W, W, 128, 512, 93), dry = lookFbm(W, W, 6, 6, 3, 94);
    const h = new Float32Array(W * W);
    for (let i = 0; i < h.length; i++) h[i] = 0.5 * blade[i] + 0.5 * blade2[i];
    return {
      map: lookCanvas(W, W, (i) => {
        const s = 0.70 + 0.45 * h[i] - 0.15 * patch[i];
        const d = Math.max(0, (dry[i] - 0.6) * 2.0);
        return [lookClamp((70 + 70 * d) * s), lookClamp((108 + 30 * d) * s), lookClamp((48 + 20 * d) * s)];
      }),
      normal: lookNormalCanvas(h, W, W, 2.5),
      rough: lookCanvas(W, W, () => [255, 255, 255]),
      normalScale: 0.8,
    };
  }},
};
const grainTextures = new Map();

function grainTexturesFor(name) {
  if (grainTextures.has(name)) return grainTextures.get(name);
  const spec = GRAIN_SPECS[name];
  if (!spec) return null;
  const W = name === "roof_tile" || name === "soil" || name === "dry_grass" ? 1024 : 512;
  const maps = spec.build(W);
  const aniso = renderer.capabilities.getMaxAnisotropy();
  const make = (canvas, srgb) => {
    if (!canvas) return null;
    const t = new THREE.CanvasTexture(canvas);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(1 / spec.size, 1 / spec.size);   // metric UVs: one tile = size x size m
    t.anisotropy = aniso;
    if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    t.needsUpdate = true;
    return t;
  };
  const out = {
    map: make(maps.map, true), normal: make(maps.normal, false), rough: make(maps.rough, false),
    normalScale: maps.normalScale, full: !!spec.full,
  };
  grainTextures.set(name, out);
  return out;
}

// Large-scale variation in world space so a repeated tile never reads as a grid.
const LOOK_NOISE_GLSL = `
float lookHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float lookVNoise(vec2 p) {
  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(lookHash(i), lookHash(i + vec2(1.0, 0.0)), f.x),
             mix(lookHash(i + vec2(0.0, 1.0)), lookHash(i + vec2(1.0, 1.0)), f.x), f.y);
}
float lookFbm2(vec2 p) {
  float s = 0.0, a = 0.5;
  for (int k = 0; k < 4; k++) { s += a * lookVNoise(p); p = p * 2.03 + 17.1; a *= 0.5; }
  return s / 0.9375;
}`;

function lookMacroVariation(material, amount, scale, ground, blend = null) {
  material.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vLookWorld;")
      .replace("#include <project_vertex>", "#include <project_vertex>\nvLookWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    let body = "float lookM = lookFbm2(vLookWorld.xy * " + scale.toFixed(4) + " + vLookWorld.z * 0.05);\n" +
      "diffuseColor.rgb *= mix(" + (1 - amount).toFixed(3) + ", " + (1 + amount * 0.6).toFixed(3) + ", lookM);\n";
    if (ground) {
      // Second, coarser sample of the same map: breaks the repetition of the tile.
      body += "#ifdef USE_MAP\nvec3 lookCoarse = texture2D(map, vMapUv * 0.137 + 0.31).rgb;\n" +
        "diffuseColor.rgb = mix(diffuseColor.rgb, lookCoarse * 1.05, 0.30 * lookFbm2(vLookWorld.xy * 0.011));\n#endif\n";
    }
    if (blend) {
      // Soil: two samples of each map (scale + rotation picked by a world
      // noise) so the tile never repeats; dry grass over the soil in
      // patches from a world-space mask (metres, not tiles).
      shader.uniforms.lookGrassMap = {value: blend.map};
      body = `
        vec2 lw = vLookWorld.xy;
        mat2 lr = mat2(0.8, -0.6, 0.6, 0.8);
        float lsel = smoothstep(0.35, 0.65, lookFbm2(lw * 0.06 + 5.3));
        vec3 ls = mix(texture2D(map, lw / ${blend.soilSize.toFixed(2)}).rgb,
                      texture2D(map, lr * lw / ${(blend.soilSize * 1.37).toFixed(2)} + 0.41).rgb, lsel);
        vec3 lg = mix(texture2D(lookGrassMap, lw / ${blend.grassSize.toFixed(2)}).rgb,
                      texture2D(lookGrassMap, lr * lw / ${(blend.grassSize * 1.29).toFixed(2)} + 0.17).rgb, lsel);
        float lmask = lookFbm2(lw * 0.045) + 0.30 * (lookFbm2(lw * 0.35 + 9.1) - 0.5);
        lmask = smoothstep(0.38, 0.54, lmask);
        diffuseColor.rgb = mix(ls, lg, lmask);
      ` + body;
    }
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vLookWorld;\n" +
               (blend ? "uniform sampler2D lookGrassMap;\n" : "") + LOOK_NOISE_GLSL)
      .replace("#include <map_fragment>", "#include <map_fragment>\n" + body);
  };
  material.customProgramCacheKey = () => "look-macro-" + amount + "-" + scale + "-" + (ground ? 1 : 0) + (blend ? "-blend-" + material.uuid : "");
  // (A shared program would skip onBeforeCompile and leave lookGrassMap unbound.)
}

const GRAIN_MACRO = {plaster: [0.06, 0.25], concrete: [0.12, 0.30], wood: [0.08, 0.6],
                     roof_tile: [0.14, 0.18], soil: [0.22, 0.045], grass: [0.18, 0.06]};

// Called from materialFor(): give a plain PBR material its grain.
function lookApplyGrain(material, grain) {
  const tex = grainTexturesFor(grain);
  if (!tex) return false;
  material.map = tex.map;
  if (tex.full) material.color.set(0xffffff);
  if (tex.normal) {
    material.normalMap = tex.normal;
    material.normalScale = new THREE.Vector2(tex.normalScale, tex.normalScale);
  }
  if (tex.rough) material.roughnessMap = tex.rough;
  const macro = GRAIN_MACRO[grain];
  if (grain === "soil") {
    const grass = grainTexturesFor("dry_grass");
    const blend = {map: grass.map, soilSize: GRAIN_SPECS.soil.size, grassSize: GRAIN_SPECS.dry_grass.size};
    lookMacroVariation(material, macro[0], macro[1], false, blend);
  } else if (macro) lookMacroVariation(material, macro[0], macro[1], grain === "grass");
  material.userData.grain = grain;
  return true;
}

// ---- Sky ------------------------------------------------------------------
const lookSkyMaterial = new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false, depthTest: false, fog: false,
  uniforms: {
    sunDir: {value: new THREE.Vector3(0.3, -0.5, 0.8).normalize()},
    zenith: {value: new THREE.Color()}, horizon: {value: new THREE.Color()},
    groundCol: {value: new THREE.Color()}, sunCol: {value: new THREE.Color()},
    warm: {value: new THREE.Color()}, warmth: {value: 0.0},
    cloudCover: {value: 0.42}, cloudLight: {value: 1.0}, sunDisc: {value: 1.0},
  },
  vertexShader: `
    varying vec3 vDir;
    void main() {
      vDir = position;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`,
  fragmentShader: `
    varying vec3 vDir;
    uniform vec3 sunDir, zenith, horizon, groundCol, sunCol, warm;
    uniform float warmth, cloudCover, cloudLight, sunDisc;
    ` + LOOK_NOISE_GLSL + `
    float cloudField(vec2 p) {
      float s = 0.0, a = 0.5;
      for (int k = 0; k < 6; k++) { s += a * lookVNoise(p); p = p * 2.07 + vec2(13.7, 7.3); a *= 0.5; }
      return s / 0.984;
    }
    void main() {
      vec3 d = normalize(vDir);
      float h = d.z;
      float cosA = dot(d, sunDir);
      vec2 dxy = normalize(d.xy + 1e-5), sxy = normalize(sunDir.xy + 1e-5);
      float toward = max(dot(dxy, sxy), 0.0);
      vec3 hor = mix(horizon, warm, warmth * pow(toward, 2.0) * (1.0 - smoothstep(0.0, 0.35, h)));
      vec3 col = mix(hor, zenith, pow(smoothstep(0.0, 1.0, max(h, 0.0)), 0.55));
      // Haze band and sun glow (forward scattering).
      col += sunCol * (0.30 * pow(max(cosA, 0.0), 10.0) + 0.10 * pow(max(cosA, 0.0), 2.5));
      if (h > 0.0) {
        vec2 p = d.xy / (h + 0.10) * 1.3;
        float n = cloudField(p + vec2(3.1, 1.7));
        float cover = smoothstep(0.62 - cloudCover * 0.35, 0.86 - cloudCover * 0.30, n);
        float nSun = cloudField(p + vec2(3.1, 1.7) + sxy * 0.08);
        float lit = clamp(0.55 + (n - nSun) * 6.0, 0.0, 1.0);
        vec3 shadowCol = mix(hor, zenith, 0.25) * 0.85 + vec3(0.06);
        vec3 cloud = mix(shadowCol, (vec3(1.0) + sunCol * 0.35) * cloudLight, lit);
        cloud += sunCol * 0.25 * pow(max(cosA, 0.0), 6.0);
        cover *= smoothstep(0.0, 0.18, h);
        col = mix(col, cloud, cover * 0.92);
        float disc = smoothstep(0.99985, 0.99995, cosA) * (1.0 - cover);
        col += sunCol * disc * 30.0 * sunDisc;
      } else {
        col = mix(hor, groundCol, smoothstep(0.0, 0.12, -h));
      }
      gl_FragColor = vec4(col, 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,
});
const lookSkyScene = new THREE.Scene();
lookSkyScene.add(new THREE.Mesh(new THREE.SphereGeometry(10, 64, 32), lookSkyMaterial));
const lookCubeTarget = new THREE.WebGLCubeRenderTarget(768, {type: THREE.HalfFloatType, generateMipmaps: false});
const lookCubeCamera = new THREE.CubeCamera(0.1, 100, lookCubeTarget);
lookSkyScene.add(lookCubeCamera);
let lookSkyEnvironment = null;
const lookHorizon = new THREE.Color();

function lookSmooth(a, b, x) { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); }
function lookMix(c1, c2, t) { return new THREE.Color().copy(c1).lerp(c2, t); }

// Paint the sky for a sun at elevation/azimuth (degrees) into the cube map.
function lookPaintSky(elevation, dir) {
  const u = lookSkyMaterial.uniforms;
  const day = lookSmooth(-6, 12, elevation), low = 1 - lookSmooth(2, 30, elevation);
  u.sunDir.value.copy(dir);
  u.zenith.value.copy(lookMix(new THREE.Color(0.004, 0.007, 0.020), new THREE.Color(0.075, 0.25, 0.75), day));
  u.horizon.value.copy(lookMix(new THREE.Color(0.020, 0.025, 0.045), new THREE.Color(0.70, 0.80, 0.92), day));
  u.groundCol.value.copy(lookMix(new THREE.Color(0.01, 0.01, 0.012), new THREE.Color(0.30, 0.27, 0.22), day));
  u.warm.value.setRGB(1.10, 0.55, 0.28);
  u.warmth.value = low * day;
  u.sunCol.value.copy(lookMix(new THREE.Color(1.0, 0.95, 0.88), new THREE.Color(1.0, 0.55, 0.25), low)).multiplyScalar(day);
  u.cloudLight.value = 0.15 + 0.85 * day;
  u.sunDisc.value = elevation > -1 ? 1 : 0;
  lookHorizon.copy(u.horizon.value);
  // Cube background in linear HDR; tone mapping happens when it is drawn.
  const tm = renderer.toneMapping, target = renderer.getRenderTarget();
  renderer.toneMapping = THREE.NoToneMapping;
  lookCubeCamera.update(renderer, lookSkyScene);
  renderer.toneMapping = tm;
  renderer.setRenderTarget(target);
  if (lookSkyEnvironment) lookSkyEnvironment.dispose();
  lookSkyEnvironment = pmrem.fromCubemap(lookCubeTarget.texture).texture;
}

// ---- Ground ---------------------------------------------------------------
const lookGroundMaterial = new THREE.MeshStandardMaterial({color: 0xffffff, roughness: 1.0, metalness: 0.0});
lookApplyGrain(lookGroundMaterial, "soil");
function lookGroundGeometry(hole = null) {
  // Under a site terrain the terrain is the ground: the disk to the horizon has a hole there, so a pool or a
  // dug-in building at the terrain's lowest level is not lidded by it (owner 22/10: the OLD VILLA pool).
  let g = new THREE.CircleGeometry(1500, 128);
  if (hole) {
    const shape = new THREE.Shape();
    shape.absarc(0, 0, 1500, 0, Math.PI * 2, false);
    const h = new THREE.Path();
    h.moveTo(hole[0], hole[1]); h.lineTo(hole[0], hole[3]); h.lineTo(hole[2], hole[3]); h.lineTo(hole[2], hole[1]); h.lineTo(hole[0], hole[1]);
    shape.holes.push(h);
    g = new THREE.ShapeGeometry(shape, 64);
  }
  const pos = g.attributes.position, uv = g.attributes.uv;
  for (let i = 0; i < pos.count; i++) uv.setXY(i, pos.getX(i), pos.getY(i));   // metres, as a terrain top
  return g;
}
'''
