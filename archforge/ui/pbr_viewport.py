from __future__ import annotations

import json

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from archforge.geometry.incremental import IncrementalEvaluationCache
from archforge.geometry.sculpt import SculptedPreviewBackend
from archforge.rendering.scene import build_pbr_scene_payload

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ModuleNotFoundError:  # pragma: no cover - depends on optional Qt module packaging
    QWebEngineView = None


_PBR_HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: #d9dee5; }
#stage { width: 100%; height: 100%; }
#notice { position: absolute; left: 12px; bottom: 10px; font: 12px sans-serif; color: #4b5563; }
</style>
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"
  }
}
</script>
</head>
<body>
<div id="stage"></div>
<div id="notice">ArchForge PBR Preview · derived from authoritative geometry</div>
<script type="module">
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const container = document.getElementById("stage");
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xd9dee5);

const camera = new THREE.PerspectiveCamera(48, 1, 0.02, 2000);
camera.up.set(0, 0, 1);
camera.position.set(8, -10, 8);

const renderer = new THREE.WebGLRenderer({antialias: true, alpha: false, powerPreference: "high-performance"});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;
container.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.target.set(0, 0, 1.4);
controls.update();

scene.add(new THREE.AmbientLight(0xffffff, 0.42));
const key = new THREE.DirectionalLight(0xfff4df, 3.2);
key.position.set(9, -11, 15);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.bias = -0.00035;
key.shadow.normalBias = 0.035;
key.shadow.camera.left = -30;
key.shadow.camera.right = 30;
key.shadow.camera.top = 30;
key.shadow.camera.bottom = -30;
key.shadow.camera.near = 0.5;
key.shadow.camera.far = 80;
scene.add(key);
scene.add(key.target);

const fill = new THREE.DirectionalLight(0xbfd8ff, 1.0);
fill.position.set(-8, 5, 9);
scene.add(fill);

const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(120, 120),
  new THREE.MeshStandardMaterial({color: 0xcbd1d7, roughness: 0.96, metalness: 0.0})
);
ground.position.z = -0.025;
ground.receiveShadow = true;
scene.add(ground);

const modelRoot = new THREE.Group();
scene.add(modelRoot);
let activeTechnique = "pbr";

function resize() {
  const w = Math.max(1, container.clientWidth);
  const h = Math.max(1, container.clientHeight);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
}
window.addEventListener("resize", resize);
resize();

function disposeModel() {
  while (modelRoot.children.length) {
    const child = modelRoot.children.pop();
    if (child.geometry) child.geometry.dispose();
    if (child.material) child.material.dispose();
  }
}

function materialFor(spec) {
  return new THREE.MeshStandardMaterial({
    color: new THREE.Color(spec.color || "#bdc5ce"),
    roughness: Number(spec.roughness ?? 0.65),
    metalness: Number(spec.metalness ?? 0.02),
    side: THREE.DoubleSide
  });
}

function applyTechnique() {
  const technical = activeTechnique === "technical";
  const glass = activeTechnique === "glass";
  scene.background.set(technical ? 0xf4f5f7 : 0xd9dee5);
  renderer.shadowMap.enabled = !technical;
  modelRoot.traverse((obj) => {
    if (!obj.isMesh) return;
    obj.material.wireframe = technical;
    obj.material.transparent = glass;
    obj.material.opacity = glass ? 0.34 : 1.0;
    obj.material.depthWrite = !glass;
    obj.castShadow = !technical && !glass;
    obj.receiveShadow = !technical;
    obj.material.needsUpdate = true;
  });
}

function fitCamera() {
  const box = new THREE.Box3().setFromObject(modelRoot);
  if (box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.length() * 0.62, 2.0);
  controls.target.copy(center);
  camera.position.set(center.x + radius, center.y - radius * 1.25, center.z + radius * 0.85);
  camera.near = Math.max(0.02, radius / 500.0);
  camera.far = Math.max(200.0, radius * 40.0);
  camera.updateProjectionMatrix();
  controls.update();
}

window.archforgeSetScene = function(payload) {
  disposeModel();
  const objects = (payload && payload.objects) || [];
  for (const item of objects) {
    const positions = [];
    for (const v of item.vertices) positions.push(v[0], v[1], v[2]);
    const indices = [];
    for (const t of item.triangles) indices.push(t[0], t[1], t[2]);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();
    const mesh = new THREE.Mesh(geometry, materialFor(item.material || {}));
    mesh.name = item.id || item.kind || "entity";
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    modelRoot.add(mesh);
  }
  applyTechnique();
  fitCamera();
};

window.setTechnique = function(mode) {
  if (mode === "pbr" || mode === "technical" || mode === "glass") {
    activeTechnique = mode;
    applyTechnique();
  }
};

if (window.__archforgePendingTechnique) window.setTechnique(window.__archforgePendingTechnique);
if (window.__archforgePendingScene) window.archforgeSetScene(window.__archforgePendingScene);

function animate() {
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
animate();
</script>
</body>
</html>
"""


class PBRViewport(QWidget):
    """GPU/WebGL derived preview of the current authoritative ArchForge geometry.

    This first integration deliberately does not replace Viewport3D interaction. It reads
    the same evaluated MeshPayloads and owns no design state of its own.
    """

    selectionChangedByView = Signal()
    statusChanged = Signal(str)

    def __init__(self, doc, stack, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.stack = stack
        self._evaluation_cache = IncrementalEvaluationCache(SculptedPreviewBackend())
        self._technique = "pbr"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = None
        self._layout = layout
        self._placeholder = QLabel(
            "PBR Preview initializes when this tab becomes active."
            if QWebEngineView is not None
            else "PBR Preview unavailable: Qt WebEngine is not installed.\n"
                 "The normal ArchForge 3D viewport remains fully available."
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._placeholder)

    def activate(self) -> None:
        """Lazily create the WebEngine surface only when the user opens this view."""
        if self.web_view is not None or QWebEngineView is None:
            return
        self._placeholder.hide()
        self.web_view = QWebEngineView(self)
        self._layout.addWidget(self.web_view)
        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.setHtml(_PBR_HTML, QUrl("https://cdn.jsdelivr.net/"))

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            self.statusChanged.emit("PBR Preview HTML failed to load")
            return
        self.statusChanged.emit("PBR Preview ready")
        self.set_render_technique(self._technique)
        self.redraw(force_full=True)

    def rebind(self, doc, stack) -> None:
        self.doc = doc
        self.stack = stack
        self._evaluation_cache.clear()
        self.redraw(force_full=True)

    def set_tool(self, tool: str) -> None:
        self.statusChanged.emit(
            "PBR Preview is display-only in this integration; edit in Plan/Front/Side/3D Perspective"
        )

    def set_render_technique(self, technique: str) -> None:
        if technique not in ("pbr", "technical", "glass"):
            raise ValueError(f"unsupported render technique: {technique}")
        self._technique = technique
        if self.web_view is None:
            return
        script = (
            "window.__archforgePendingTechnique = "
            + json.dumps(technique)
            + "; if (window.setTechnique) window.setTechnique(window.__archforgePendingTechnique);"
        )
        self.web_view.page().runJavaScript(script)

    def refresh_selection(self) -> None:
        self.redraw(force_full=False)

    def redraw(self, force_full=False) -> None:
        if self.web_view is None:
            return
        evaluation = self._evaluation_cache.sync(self.doc)
        payload = build_pbr_scene_payload(evaluation, self.doc.selection)
        script = (
            "window.__archforgePendingScene = "
            + json.dumps(payload, separators=(",", ":"))
            + "; if (window.archforgeSetScene) window.archforgeSetScene(window.__archforgePendingScene);"
        )
        self.web_view.page().runJavaScript(script)
