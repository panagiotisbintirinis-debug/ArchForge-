from __future__ import annotations

import json

from PySide6.QtCore import Qt, QUrl, Signal, Slot, QObject
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QMenu
from PySide6.QtWebChannel import QWebChannel

from archforge.geometry.incremental import IncrementalEvaluationCache
from archforge.geometry.sculpt import SculptedPreviewBackend
from archforge.geometry.selection import BrushSpec, SurfaceHit
from archforge.geometry.sculpt_transaction import SculptTransaction
from archforge.core.interaction import OpeningPlaceTransaction
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
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
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

if (typeof QWebChannel !== "undefined" && typeof qt !== "undefined") {
  new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.renderBridge;
  });
}

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
const axesHelper = new THREE.AxesHelper(2.5);
axesHelper.visible = false;
scene.add(axesHelper);
let activeTechnique = "pbr";
let activeCameraPreset = "orbit";
let cutawayEnabled = false;
let activeTool = "orbit";
let bridge = null;
let sculpting = false;
let sculptStartY = 0;

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

function sceneBounds() {
  const box = new THREE.Box3().setFromObject(modelRoot);
  if (box.isEmpty()) return null;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.length() * 0.62, 2.0);
  return {box, center, size, radius};
}

function setCameraPreset(mode) {
  const bounds = sceneBounds();
  if (!bounds) return;
  const {center, radius} = bounds;
  activeCameraPreset = mode;
  controls.enabled = activeTool !== "sculpt";
  camera.up.set(0, 0, 1);
  camera.near = Math.max(0.02, radius / 500.0);
  camera.far = Math.max(200.0, radius * 40.0);

  if (mode === "top") {
    camera.up.set(0, 1, 0);
    camera.position.set(center.x, center.y, center.z + radius * 1.9);
    controls.target.set(center.x, center.y, center.z);
  } else if (mode === "front") {
    camera.position.set(center.x, center.y - radius * 1.8, center.z + radius * 0.05);
    controls.target.set(center.x, center.y, center.z);
  } else if (mode === "side") {
    camera.position.set(center.x + radius * 1.8, center.y, center.z + radius * 0.05);
    controls.target.set(center.x, center.y, center.z);
  } else if (mode === "iso30" || mode === "cutaway") {
    const elev = Math.PI / 6;
    const horizontal = radius * 1.55;
    camera.position.set(
      center.x + horizontal * Math.cos(Math.PI / 4),
      center.y - horizontal * Math.sin(Math.PI / 4),
      center.z + horizontal * Math.tan(elev)
    );
    controls.target.set(center.x, center.y, center.z);
  } else if (mode === "eye") {
    camera.position.set(center.x, center.y - radius * 1.7, 1.7);
    controls.target.set(center.x, center.y, Math.min(center.z + 0.3, 1.7));
  } else {
    camera.position.set(center.x + radius, center.y - radius * 1.25, center.z + radius * 0.85);
    controls.target.copy(center);
  }
  camera.updateProjectionMatrix();
  camera.lookAt(controls.target);
  controls.update();
}

function fitCamera() {
  setCameraPreset(activeCameraPreset || "orbit");
}

window.archforgeSetScene = function(payload, fit = true) {
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
    mesh.userData.entityId = item.id || "";
    mesh.userData.kind = item.kind || "";
    mesh.userData.surfaceRoles = item.surfaces || [];
    mesh.visible = !(cutawayEnabled && item.kind === "room_roof");
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    modelRoot.add(mesh);
  }
  applyTechnique();
  if (fit) fitCamera();
};

window.setTechnique = function(mode) {
  if (mode === "pbr" || mode === "technical" || mode === "glass") {
    activeTechnique = mode;
    applyTechnique();
  }
};



window.setCameraPreset = function(mode) {
  const allowed = ["cutaway", "top", "front", "side", "iso30", "eye", "orbit"];
  if (!allowed.includes(mode)) return;
  if (mode === "cutaway") {
    cutawayEnabled = true;
    modelRoot.children.forEach((mesh) => {
      if (mesh.userData && mesh.userData.kind === "room_roof") mesh.visible = false;
    });
  } else {
    cutawayEnabled = false;
    modelRoot.children.forEach((mesh) => mesh.visible = true);
  }
  setCameraPreset(mode);
};

window.setAxesVisible = function(enabled) {
  axesHelper.visible = !!enabled;
};

window.setAutoRotate = function(enabled) {
  controls.autoRotate = !!enabled;
  controls.autoRotateSpeed = 1.25;
};

window.setCutaway = function(enabled) {
  cutawayEnabled = !!enabled;
  modelRoot.children.forEach((mesh) => {
    if (mesh.userData && mesh.userData.kind === "room_roof") {
      mesh.visible = !cutawayEnabled;
    }
  });
};

window.setActiveTool = function(tool) {
  activeTool = tool || "orbit";
  if (!sculpting) controls.enabled = activeTool !== "sculpt";
};

function pickModel(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  const mouse = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1
  );
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(modelRoot.children, false);
  return hits.length ? hits[0] : null;
}

renderer.domElement.addEventListener("pointerdown", (event) => {
  if (!bridge) return;
  const hit = pickModel(event);
  if (!hit || !hit.face) return;

  if (activeTool === "door" || activeTool === "window") {
    const kind = hit.object.userData.kind || "";
    if (kind !== "wall" && kind !== "pod") return;
    const payload = {
      entity_id: hit.object.userData.entityId,
      point: [hit.point.x, hit.point.y, hit.point.z]
    };
    bridge.placeOpening(activeTool, JSON.stringify(payload));
    event.preventDefault();
    event.stopPropagation();
    return;
  }

  if (activeTool !== "sculpt") return;
  const roles = hit.object.userData.surfaceRoles || [];
  const surfaceRole = roles[hit.faceIndex] || hit.object.userData.kind || "default";
  const normal = hit.face.normal.clone();
  normal.applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(hit.object.matrixWorld)).normalize();
  const payload = {
    entity_id: hit.object.userData.entityId,
    surface_role: surfaceRole,
    point: [hit.point.x, hit.point.y, hit.point.z],
    normal: [normal.x, normal.y, normal.z]
  };
  sculpting = true;
  sculptStartY = event.clientY;
  controls.enabled = false;
  if (renderer.domElement.setPointerCapture) renderer.domElement.setPointerCapture(event.pointerId);
  bridge.beginSculpt(JSON.stringify(payload));
  event.preventDefault();
  event.stopPropagation();
}, true);

renderer.domElement.addEventListener("dblclick", (event) => {
  if (!bridge || sculpting) return;
  const hit = pickModel(event);
  if (!hit || !hit.face) return;
  bridge.selectEntity(hit.object.userData.entityId || "");
  event.preventDefault();
  event.stopPropagation();
}, true);

renderer.domElement.addEventListener("contextmenu", (event) => {
  event.preventDefault();
  if (!bridge || sculpting) return;
  const hit = pickModel(event);
  if (!hit || !hit.face) return;
  bridge.showContextMenu(hit.object.userData.entityId || "");
  event.stopPropagation();
}, true);

renderer.domElement.addEventListener("pointermove", (event) => {
  if (!sculpting || !bridge) return;
  const amount = Math.abs(event.clientY - sculptStartY) * 0.006;
  bridge.updateSculpt(amount);
  event.preventDefault();
  event.stopPropagation();
}, true);

renderer.domElement.addEventListener("pointerup", (event) => {
  if (!sculpting || !bridge) return;
  sculpting = false;
  controls.enabled = activeTool !== "sculpt";
  bridge.endSculpt();
  event.preventDefault();
  event.stopPropagation();
}, true);

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


class PBRInteractionBridge(QObject):
    """WebGL pointer bridge into ArchForge's existing semantic sculpt transaction."""

    def __init__(self, viewport):
        super().__init__(viewport)
        self.viewport = viewport

    @Slot(str)
    def beginSculpt(self, payload_json: str) -> None:
        self.viewport._begin_sculpt_from_web(payload_json)

    @Slot(float)
    def updateSculpt(self, amount: float) -> None:
        self.viewport._update_sculpt_from_web(amount)

    @Slot()
    def endSculpt(self) -> None:
        self.viewport._finish_sculpt_from_web()

    @Slot(str)
    def selectEntity(self, entity_id: str) -> None:
        self.viewport._select_entity_from_web(entity_id)

    @Slot(str)
    def showContextMenu(self, entity_id: str) -> None:
        self.viewport._show_context_menu(entity_id)

    @Slot(str, str)
    def placeOpening(self, kind: str, payload_json: str) -> None:
        self.viewport._place_opening_from_web(kind, payload_json)


class PBRViewport(QWidget):
    """GPU/WebGL derived preview of the current authoritative ArchForge geometry.

    This first integration deliberately does not replace Viewport3D interaction. It reads
    the same evaluated MeshPayloads and owns no design state of its own.
    """

    selectionChangedByView = Signal()
    deleteRequested = Signal(str)
    statusChanged = Signal(str)

    def __init__(self, doc, stack, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.stack = stack
        self._evaluation_cache = IncrementalEvaluationCache(SculptedPreviewBackend())
        self._technique = "pbr"
        self._camera_preset = "orbit"
        self._axes_visible = False
        self._auto_rotate = False
        self._cutaway = False
        self.active_tool = "orbit"
        self.sculpt_brush = BrushSpec(radius=0.35, strength=1.0, falloff="smooth")
        self.sculpt_op = "pull"
        self._sculpt_tx = None
        self.channel = None
        self.bridge = None
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
        self.channel = QWebChannel(self.web_view.page())
        self.bridge = PBRInteractionBridge(self)
        self.channel.registerObject("renderBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.setHtml(_PBR_HTML, QUrl("https://cdn.jsdelivr.net/"))

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            self.statusChanged.emit("PBR Preview HTML failed to load")
            return
        self.statusChanged.emit("PBR Preview ready")
        self.set_render_technique(self._technique)
        self.set_axes_visible(self._axes_visible)
        self.set_auto_rotate(self._auto_rotate)
        self.set_cutaway(self._cutaway)
        self.redraw(force_full=True)
        self.set_camera_preset(self._camera_preset)

    def rebind(self, doc, stack) -> None:
        self.doc = doc
        self.stack = stack
        self._evaluation_cache.clear()
        self.redraw(force_full=True)

    def set_tool(self, tool: str) -> None:
        self.active_tool = str(tool)
        if self.web_view is not None:
            script = (
                "if (window.setActiveTool) window.setActiveTool("
                + json.dumps(self.active_tool)
                + ");"
            )
            self.web_view.page().runJavaScript(script)
        if self.active_tool == "sculpt":
            self.statusChanged.emit(
                f"PBR Sculpt {self.sculpt_op}: click a surface and drag | brush {self.sculpt_brush.radius:.2f} m"
            )
        else:
            self.statusChanged.emit(f"PBR Viewport Tool: {self.active_tool}")

    def configure_sculpt(self, *, operation=None, radius=None, strength=None, falloff=None) -> None:
        operation = self.sculpt_op if operation is None else str(operation)
        if operation not in ("pull", "push", "inflate", "recess", "smooth", "crease"):
            raise ValueError(f"unsupported live sculpt operation: {operation}")
        brush = BrushSpec(
            radius=self.sculpt_brush.radius if radius is None else float(radius),
            strength=self.sculpt_brush.strength if strength is None else float(strength),
            falloff=self.sculpt_brush.falloff if falloff is None else str(falloff),
        )
        brush.validate()
        self.sculpt_op = operation
        self.sculpt_brush = brush
        if self.active_tool == "sculpt":
            self.statusChanged.emit(
                f"PBR Sculpt {self.sculpt_op}: click a surface and drag | brush {brush.radius:.2f} m"
            )

    def _select_entity_from_web(self, entity_id: str) -> None:
        entity_id = str(entity_id)
        if entity_id not in self.doc.entities:
            self.doc.select([])
            self.selectionChangedByView.emit()
            self.redraw(force_full=False)
            self.statusChanged.emit("Selection cleared")
            return
        self.doc.select([entity_id])
        self.selectionChangedByView.emit()
        self.redraw(force_full=False)
        entity = self.doc.get(entity_id)
        self.statusChanged.emit(
            f"Selected {entity.name or entity.kind.title()} — press Delete to remove"
        )

    def _show_context_menu(self, entity_id: str) -> None:
        entity_id = str(entity_id)
        if entity_id not in self.doc.entities:
            return
        self.doc.select([entity_id])
        self.selectionChangedByView.emit()
        self.redraw(force_full=False)

        entity = self.doc.get(entity_id)
        menu = QMenu(self)
        delete_action = menu.addAction(f"Delete {entity.name or entity.kind.title()}")
        chosen = menu.exec(QCursor.pos())
        if chosen is delete_action:
            self.deleteRequested.emit(entity_id)

    def _begin_sculpt_from_web(self, payload_json: str) -> None:
        if self.active_tool != "sculpt":
            return
        try:
            payload = json.loads(payload_json)
            hit = SurfaceHit(
                str(payload["entity_id"]),
                str(payload["surface_role"]),
                tuple(float(v) for v in payload["point"]),
                tuple(float(v) for v in payload["normal"]),
            )
            hit.validate(self.doc)
            self._sculpt_tx = SculptTransaction(
                self.doc,
                self.stack,
                hit,
                self.sculpt_brush,
                self.sculpt_op,
                0.0,
            )
            self.statusChanged.emit(
                f"PBR sculpt point locked on {hit.surface_role}; drag to deform locally"
            )
        except Exception as exc:
            self._sculpt_tx = None
            self.statusChanged.emit(f"Cannot sculpt PBR surface: {exc}")

    def _update_sculpt_from_web(self, amount: float) -> None:
        if self._sculpt_tx is None:
            return
        try:
            self._sculpt_tx.update(amount=float(amount), strength=self.sculpt_brush.strength)
            self.redraw(force_full=False)
            self.statusChanged.emit(
                f"PBR local sculpt displacement: {self._sculpt_tx.amount:.3f} m"
            )
        except Exception as exc:
            self.statusChanged.emit(f"PBR sculpt preview error: {exc}")

    def _finish_sculpt_from_web(self) -> None:
        if self._sculpt_tx is None:
            return
        tx = self._sculpt_tx
        self._sculpt_tx = None
        try:
            if tx.amount > 0.001:
                tx.commit()
                self._evaluation_cache.clear()
                self.statusChanged.emit(f"Applied sculpt modifier ({self.sculpt_op})")
            else:
                tx.cancel()
            self.selectionChangedByView.emit()
            self.redraw(force_full=False)
        except Exception as exc:
            self.statusChanged.emit(f"PBR sculpt commit error: {exc}")
            self.redraw(force_full=False)


    def set_camera_preset(self, mode: str) -> None:
        allowed = ("cutaway", "top", "front", "side", "iso30", "eye", "orbit")
        mode = str(mode)
        if mode not in allowed:
            raise ValueError(f"unsupported camera preset: {mode}")
        self._camera_preset = mode
        if mode == "cutaway":
            self._cutaway = True
        elif mode != "cutaway":
            self._cutaway = False
        if self.web_view is not None:
            self.web_view.page().runJavaScript(
                "if (window.setCameraPreset) window.setCameraPreset("
                + json.dumps(mode)
                + ");"
            )
        self.statusChanged.emit(f"PBR camera: {mode}")

    def set_axes_visible(self, enabled: bool) -> None:
        self._axes_visible = bool(enabled)
        if self.web_view is not None:
            self.web_view.page().runJavaScript(
                "if (window.setAxesVisible) window.setAxesVisible("
                + ("true" if self._axes_visible else "false")
                + ");"
            )

    def set_auto_rotate(self, enabled: bool) -> None:
        self._auto_rotate = bool(enabled)
        if self.web_view is not None:
            self.web_view.page().runJavaScript(
                "if (window.setAutoRotate) window.setAutoRotate("
                + ("true" if self._auto_rotate else "false")
                + ");"
            )

    def set_cutaway(self, enabled: bool) -> None:
        self._cutaway = bool(enabled)
        if self.web_view is not None:
            self.web_view.page().runJavaScript(
                "if (window.setCutaway) window.setCutaway("
                + ("true" if self._cutaway else "false")
                + ");"
            )


    def _place_opening_from_web(self, kind: str, payload_json: str) -> None:
        if kind not in ("door", "window"):
            return
        try:
            payload = json.loads(payload_json)
            entity_id = str(payload["entity_id"])
            point = tuple(float(v) for v in payload["point"])
            if entity_id not in self.doc.entities:
                raise ValueError("clicked host no longer exists")
            host = self.doc.get(entity_id)
            if host.kind not in ("wall", "pod"):
                raise ValueError("doors/windows require a wall or pod host")
            tx = OpeningPlaceTransaction(
                self.doc,
                self.stack,
                kind,
                point[0],
                point[1],
                tolerance=max(0.5, float(host.params.get("thickness", 0.0)) + 0.25),
            )
            if tx.host_id != entity_id:
                raise ValueError("opening placement resolved to a different nearby host")
            opening_id = tx.commit()
            self._evaluation_cache.clear()
            self.doc.select([opening_id])
            self.selectionChangedByView.emit()
            self.redraw(force_full=False)
            self.statusChanged.emit(f"Placed {kind} in 3D Studio")
        except Exception as exc:
            self.statusChanged.emit(f"Cannot place {kind} in 3D Studio: {exc}")

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
        overrides = None
        if self._sculpt_tx is not None:
            try:
                overrides = {self._sculpt_tx.hit.owner_id: self._sculpt_tx.preview_mesh()}
            except Exception as exc:
                self.statusChanged.emit(f"PBR sculpt preview error: {exc}")
        payload = build_pbr_scene_payload(
            evaluation,
            self.doc.selection,
            mesh_overrides=overrides,
        )
        fit = "true" if force_full and self._sculpt_tx is None else "false"
        script = (
            "window.__archforgePendingScene = "
            + json.dumps(payload, separators=(",", ":"))
            + "; if (window.archforgeSetScene) window.archforgeSetScene(window.__archforgePendingScene, "
            + fit
            + ");"
        )
        self.web_view.page().runJavaScript(script)
