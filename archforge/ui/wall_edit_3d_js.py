"""The WebGL half of walls in 3D (see ``wall_edit_3d.py``).

Embedded in the PBR page before its own pointer listeners, so a wall gesture is seen
first.  It only raycasts and draws: the floor point (and, for the top handle, the camera
ray) goes to Python over the existing ``renderBridge`` channel as one JSON event
(``bridge.wallEvent``); Python answers with the ghost to draw.  Ghosts, handles and the
length label live in their own groups, outside ``modelRoot`` — never picked as model.
"""
from __future__ import annotations


def wall_edit_3d_js() -> str:
    return r'''
// --- Walls in 3D: draw / stretch / move / height, opening ghost (archforge/ui/wall_edit_3d.py) ---
const wallGhostRoot = new THREE.Group();
wallGhostRoot.name = "wall-ghost";
scene.add(wallGhostRoot);
const wallHandleRoot = new THREE.Group();
wallHandleRoot.name = "wall-handles";
scene.add(wallHandleRoot);
const wallLabel = document.createElement("div");
wallLabel.id = "wallLabel";
wallLabel.style.cssText = "position:fixed;display:none;transform:translate(-50%,-100%);padding:3px 9px;border-radius:9px;" +
  "background:rgba(32,41,53,.88);color:#fff;font:600 13px Segoe UI,Arial,sans-serif;white-space:nowrap;pointer-events:none;z-index:30";
document.body.appendChild(wallLabel);
const WALL_COLORS = {draw: 0x2f9cff, edit: 0xffa21f, ok: 0x35c26b, bad: 0xe0453a};
const OPENING_TOOLS = new Set(["door", "window", "opening_rect", "opening_arch"]);
let wallFloorZ = 0;
let wallDrawing = false;
let wallSelectedId = "";
let wallLabelPos = null;
let wallOpeningLabel = null;
let wallDrag = null;
let wallPress = null;
let wallHoverPending = null;
let wallHoverScheduled = false;

function wallSend(payload) {
  if (bridge && bridge.wallEvent) bridge.wallEvent(JSON.stringify(payload));
}

function wallFloorPoint(event) {
  const p = pointOnHorizontalPlane(event, wallFloorZ);
  if (!p) return null;
  // Metres per pixel at the cursor: Python turns it into a snap radius on screen.
  const q = pointOnHorizontalPlane({clientX: event.clientX + 10, clientY: event.clientY}, wallFloorZ);
  return {x: Number(p.x), y: Number(p.y), pxm: q ? p.distanceTo(q) / 10 : 0.01};
}

function wallEventAt(type, event) {
  const p = wallFloorPoint(event);
  if (!p) return null;
  return {type, x: p.x, y: p.y, pxm: p.pxm, shift: !!event.shiftKey};
}

function wallClearGroup(group) {
  while (group.children.length) {
    const child = group.children.pop();
    if (child.geometry) child.geometry.dispose();
    if (child.material) child.material.dispose();
  }
}

function wallBoxMesh(box, opacity) {
  const dx = box.x2 - box.x1, dy = box.y2 - box.y1;
  const length = Math.hypot(dx, dy);
  if (length < 1e-6) return null;
  const geometry = new THREE.BoxGeometry(length, Math.max(0.01, box.thickness), Math.max(0.01, box.height));
  const material = new THREE.MeshStandardMaterial({
    color: WALL_COLORS[box.color] || WALL_COLORS.draw, roughness: 0.5, metalness: 0.0,
    transparent: true, opacity: opacity, depthWrite: false,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2   // no flicker on the wall it covers
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set((box.x1 + box.x2) / 2, (box.y1 + box.y2) / 2, box.z + box.height / 2);
  mesh.rotation.z = Math.atan2(dy, dx);
  mesh.renderOrder = 900;
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry),
    new THREE.LineBasicMaterial({color: 0x1d4f80, transparent: true, opacity: 0.9}));
  mesh.add(edges);
  return mesh;
}

function wallMarker(marker) {
  const snapped = marker.kind && marker.kind !== "free";
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 10), new THREE.MeshBasicMaterial({
    color: snapped ? 0xff5a1f : 0x2f9cff, depthTest: false, transparent: true, opacity: 0.95
  }));
  mesh.position.set(marker.pos[0], marker.pos[1], marker.pos[2]);
  mesh.userData.screenRadius = snapped ? 7 : 5;
  mesh.renderOrder = 1001;
  return mesh;
}

window.archforgeSetWallGhost = function(payload) {
  wallClearGroup(wallGhostRoot);
  payload = payload || {};
  if (payload.floor_z !== undefined) wallFloorZ = Number(payload.floor_z) || 0;
  wallDrawing = !!payload.drawing;
  if (!payload.editing && !wallDrag) wallHandleRoot.visible = true;
  for (const box of payload.walls || []) {
    const mesh = wallBoxMesh(box, 0.55);
    if (mesh) wallGhostRoot.add(mesh);
  }
  if (payload.marker) wallGhostRoot.add(wallMarker(payload.marker));
  wallLabelPos = payload.label ? {text: payload.label.text, pos: payload.label.pos} : null;
};

window.archforgeSetOpeningGhost = function(opening) {
  wallClearGroup(wallGhostRoot);
  wallOpeningLabel = null;
  if (!opening || !opening.box) { wallLabelPos = null; return; }
  const mesh = wallBoxMesh(opening.box, 0.6);
  if (mesh) wallGhostRoot.add(mesh);
  wallLabelPos = opening.label || null;
};

window.archforgeSetWallHandles = function(payload) {
  wallClearGroup(wallHandleRoot);
  wallHandleRoot.visible = true;
  payload = payload || {};
  wallSelectedId = String(payload.selected || "");
  if (payload.floor_z !== undefined) wallFloorZ = Number(payload.floor_z) || 0;
  for (const h of payload.handles || []) {
    const top = h.kind === "top";
    const geometry = top ? new THREE.ConeGeometry(0.8, 1.8, 16) : new THREE.SphereGeometry(1, 18, 12);
    if (top) geometry.rotateX(Math.PI / 2);
    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
      color: h.kind === "mid" ? 0xffa21f : (top ? 0x35c26b : 0xffffff), depthTest: false
    }));
    const ring = new THREE.Mesh(new THREE.SphereGeometry(1.25, 18, 12), new THREE.MeshBasicMaterial({
      color: 0x1f5fae, depthTest: false, side: THREE.BackSide
    }));
    mesh.add(ring);
    mesh.position.set(h.pos[0], h.pos[1], h.pos[2] + (top ? 0.0 : 0.02));
    mesh.userData.handleId = String(h.id || "");
    mesh.userData.screenRadius = 8;
    mesh.renderOrder = 1002;
    ring.renderOrder = 1001;
    wallHandleRoot.add(mesh);
  }
};

// Handles, markers and the label keep a constant size on screen.
function wallScreenSize() {
  const h = Math.max(1, renderer.domElement.clientHeight);
  for (const group of [wallHandleRoot, wallGhostRoot]) {
    for (const obj of group.children) {
      const px = obj.userData.screenRadius;
      if (!px) continue;
      const d = camera.position.distanceTo(obj.position);
      const worldPerPx = 2 * d * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) / h;
      obj.scale.setScalar(px * worldPerPx);
    }
  }
  if (wallLabelPos && wallLabelPos.pos) {
    const v = new THREE.Vector3(wallLabelPos.pos[0], wallLabelPos.pos[1], wallLabelPos.pos[2]).project(camera);
    const rect = renderer.domElement.getBoundingClientRect();
    if (v.z < 1) {
      wallLabel.textContent = wallLabelPos.text;
      wallLabel.style.left = (rect.left + (v.x + 1) / 2 * rect.width) + "px";
      wallLabel.style.top = (rect.top + (1 - v.y) / 2 * rect.height) + "px";
      wallLabel.style.display = "block";
    } else wallLabel.style.display = "none";
  } else wallLabel.style.display = "none";
  requestAnimationFrame(wallScreenSize);
}
requestAnimationFrame(wallScreenSize);

// Floor point -> screen pixel (the harness clicks real points of the model).
window.__archforgeFloorToScreen = function(x, y, z) {
  const v = new THREE.Vector3(Number(x), Number(y), Number(z ?? wallFloorZ)).project(camera);
  const rect = renderer.domElement.getBoundingClientRect();
  return [rect.left + (v.x + 1) / 2 * rect.width, rect.top + (1 - v.y) / 2 * rect.height];
};

// The rendered frame as PNG (screenshots where the GPU surface cannot be grabbed).
window.__archforgeCanvasPng = function() {
  if (useComposer()) composer.render(); else renderer.render(scene, camera);
  return renderer.domElement.toDataURL("image/png");
};

function wallScheduleHover(payload) {
  wallHoverPending = payload;
  if (wallHoverScheduled) return;
  wallHoverScheduled = true;
  requestAnimationFrame(() => {
    wallHoverScheduled = false;
    const p = wallHoverPending;
    wallHoverPending = null;
    if (p) wallSend(p);
  });
}

function wallPickHandle(event) {
  if (!wallHandleRoot.children.length) return null;
  const rect = renderer.domElement.getBoundingClientRect();
  const mouse = new THREE.Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1,
                                  -((event.clientY - rect.top) / rect.height) * 2 + 1);
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(wallHandleRoot.children, true);
  if (!hits.length) return null;
  let obj = hits[0].object;
  while (obj && !obj.userData.handleId) obj = obj.parent;
  return obj ? obj.userData.handleId : null;
}

function wallRay(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  const mouse = new THREE.Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1,
                                  -((event.clientY - rect.top) / rect.height) * 2 + 1);
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, camera);
  const r = raycaster.ray;
  return {origin: [r.origin.x, r.origin.y, r.origin.z], direction: [r.direction.x, r.direction.y, r.direction.z]};
}

function wallStop(event) {
  event.preventDefault();
  event.stopImmediatePropagation();
}

renderer.domElement.addEventListener("pointerdown", (event) => {
  if (!bridge || walkMode) return;
  if (event.button === 0 && (activeTool === "orbit" || activeTool === "select" || activeTool === "wall")) {
    const handleId = wallPickHandle(event);
    if (handleId) {
      const p = wallFloorPoint(event);
      if (!p) return;
      hideMarkingMenu();
      wallDrag = {handle: handleId, pointerId: event.pointerId};
      wallHandleRoot.visible = false;          // the ghost shows the new place; handles come back after

      controls.enabled = false;
      if (renderer.domElement.setPointerCapture) renderer.domElement.setPointerCapture(event.pointerId);
      wallSend({type: "handle_down", handle: handleId, x: p.x, y: p.y, pxm: p.pxm});
      wallStop(event);
      return;
    }
  }
  // A click (no drag) draws in Wall, selects otherwise; a drag still orbits.
  if (event.button === 0) wallPress = {x: event.clientX, y: event.clientY};
}, true);

renderer.domElement.addEventListener("pointermove", (event) => {
  if (!bridge || walkMode) return;
  if (wallDrag) {
    const payload = wallEventAt("handle_move", event);
    if (payload) {
      Object.assign(payload, wallRay(event));
      wallScheduleHover(payload);
    }
    wallStop(event);
    return;
  }
  if (event.buttons & 7) return;
  if (activeTool === "wall") {
    const payload = wallEventAt("hover", event);
    if (payload) wallScheduleHover(payload);
    return;
  }
  if (OPENING_TOOLS.has(activeTool)) {
    const hit = pickModel(event);
    if (hit && hit.object.userData.kind === "wall") {
      wallScheduleHover({type: "opening_hover", tool: activeTool, entity_id: hit.object.userData.entityId,
                         point: [hit.point.x, hit.point.y, hit.point.z]});
    } else if (wallGhostRoot.children.length || wallLabelPos) {
      wallScheduleHover({type: "opening_leave"});
    }
  }
}, true);

renderer.domElement.addEventListener("pointerup", (event) => {
  if (!bridge) return;
  if (wallDrag) {
    const payload = wallEventAt("handle_move", event);
    if (payload) wallSend(Object.assign(payload, wallRay(event)));
    if (renderer.domElement.hasPointerCapture && renderer.domElement.hasPointerCapture(event.pointerId)) {
      renderer.domElement.releasePointerCapture(event.pointerId);
    }
    wallDrag = null;
    wallHoverPending = null;
    controls.enabled = true;
    wallSend({type: "handle_up"});
    wallStop(event);
    return;
  }
  const press = wallPress;
  wallPress = null;
  if (event.button !== 0 || !press || walkMode) return;
  if (Math.hypot(event.clientX - press.x, event.clientY - press.y) > 5) return;   // that was an orbit
  if (activeTool === "wall") {
    const payload = wallEventAt("click", event);
    if (payload) { wallHoverPending = null; wallSend(payload); }
    return;
  }
  if (activeTool === "orbit" || activeTool === "select") {
    const hit = pickForSelection(event);
    bridge.selectEntity((hit && hit.object.userData.entityId) || "");
  }
}, true);

renderer.domElement.addEventListener("dblclick", (event) => {
  if (activeTool !== "wall") return;
  if (bridge) wallSend({type: "finish"});
  wallStop(event);
}, true);

renderer.domElement.addEventListener("contextmenu", (event) => {
  if (activeTool === "wall" && wallDrawing) {
    if (bridge) wallSend({type: "finish"});
    wallStop(event);
  }
}, true);

window.addEventListener("keydown", (event) => {
  // Delete with the 3D page focused: the same Delete command as the menu (one undo).
  if (event.key === "Delete" && bridge && wallSelectedId && !wallDrag && !wallDrawing) {
    event.preventDefault();
    bridge.contextAction(wallSelectedId, "delete");
    wallSelectedId = "";
    return;
  }
  if (event.key !== "Escape" || !bridge) return;
  if (wallDrag) {
    wallDrag = null;
    controls.enabled = true;
    wallSend({type: "handle_cancel"});
  } else if (wallDrawing) {
    wallSend({type: "finish"});
  }
});
'''.strip()
