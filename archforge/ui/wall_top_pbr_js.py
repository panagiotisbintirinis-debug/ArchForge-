from __future__ import annotations

import json
from typing import Mapping, Any


def wall_top_handle_scene_script(payload: Mapping[str, Any]) -> str:
    """Return the JS call that updates only the view-owned wall-top handle root.

    The payload is intentionally separate from the authoritative model scene.  The
    renderer receives only handle descriptors and cannot use this path to create or
    mutate design entities.
    """
    handles = payload.get("wall_top_handles", [])
    if not isinstance(handles, list):
        raise ValueError("wall_top_handles must be a list")
    compact = json.dumps({"wall_top_handles": handles}, separators=(",", ":"))
    return (
        "window.__archforgePendingWallTopHandles = "
        + compact
        + "; if (window.archforgeSetWallTopHandles) "
        "window.archforgeSetWallTopHandles(window.__archforgePendingWallTopHandles);"
    )


def wall_top_handle_root_js() -> str:
    """Three.js contract for a separate, disposable, pick-only handle root.

    This fragment is designed to be embedded in the active PBR viewport.  Handles
    live outside ``modelRoot`` so normal model selection, opening placement and
    sculpt raycasts cannot accidentally treat a gizmo as authoritative geometry.
    """
    return r'''
const wallTopHandleRoot = new THREE.Group();
wallTopHandleRoot.name = "wall-top-handles";
scene.add(wallTopHandleRoot);
let wallTopDragging = false;

function disposeWallTopHandles() {
  while (wallTopHandleRoot.children.length) {
    const child = wallTopHandleRoot.children.pop();
    if (child.geometry) child.geometry.dispose();
    if (child.material) child.material.dispose();
  }
}

window.archforgeSetWallTopHandles = function(payload) {
  disposeWallTopHandles();
  const handles = (payload && payload.wall_top_handles) || [];
  for (const item of handles) {
    const radius = Math.max(0.025, Number(item.radius || 0.11));
    const geometry = new THREE.SphereGeometry(radius, 18, 12);
    const material = new THREE.MeshStandardMaterial({
      color: item.preview ? 0xffb020 : 0x2563eb,
      roughness: 0.45,
      metalness: 0.0,
      depthTest: false
    });
    const mesh = new THREE.Mesh(geometry, material);
    const p = item.position || [0, 0, 0];
    mesh.position.set(Number(p[0]), Number(p[1]), Number(p[2]));
    mesh.userData.handleId = String(item.handle_id || "");
    mesh.renderOrder = 1000;
    wallTopHandleRoot.add(mesh);
  }
};

function pointerRay(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  const mouse = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1
  );
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, camera);
  return raycaster;
}

function pickWallTopHandle(event) {
  const raycaster = pointerRay(event);
  const hits = raycaster.intersectObjects(wallTopHandleRoot.children, false);
  return hits.length ? hits[0] : null;
}

function wallTopRayPayload(event) {
  const ray = pointerRay(event).ray;
  return JSON.stringify({
    origin: [ray.origin.x, ray.origin.y, ray.origin.z],
    direction: [ray.direction.x, ray.direction.y, ray.direction.z]
  });
}
'''.strip()
