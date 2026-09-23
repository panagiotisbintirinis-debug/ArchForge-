from __future__ import annotations

import math
from typing import Dict, Optional, Tuple, List

from PySide6.QtCore import Qt, QPointF, QTimer, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
)

from archforge.core.model import Document
from archforge.core.commands import CommandStack
from archforge.geometry.incremental import IncrementalEvaluationCache
from archforge.geometry.mesh import TessellatedPreviewBackend, MeshPayload
from archforge.geometry.picking import raycast_mesh, MeshRayHit
from archforge.geometry.selection import BrushSpec, SurfaceHit
from archforge.geometry.sculpt_transaction import SculptTransaction

Vec3 = Tuple[float, float, float]
Bounds = Tuple[Vec3, Vec3]


class OrbitCamera:
    def __init__(self, cx: float = 0.0, cy: float = 0.0, cz: float = 0.0,
                 distance: float = 12.0, yaw: float = 0.7, pitch: float = 0.5):
        self.target = (cx, cy, cz)
        self.distance = distance
        self.yaw = yaw
        self.pitch = pitch

    def eye_position(self) -> Vec3:
        cpitch = math.cos(self.pitch)
        spitch = math.sin(self.pitch)
        cyaw = math.cos(self.yaw)
        syaw = math.sin(self.yaw)
        ex = self.target[0] + self.distance * cpitch * syaw
        ey = self.target[1] - self.distance * cpitch * cyaw
        ez = self.target[2] + self.distance * spitch
        return (ex, ey, ez)

    def forward_ray(self) -> Vec3:
        eye = self.eye_position()
        fx = self.target[0] - eye[0]
        fy = self.target[1] - eye[1]
        fz = self.target[2] - eye[2]
        fnorm = math.sqrt(fx*fx + fy*fy + fz*fz)
        if fnorm <= 1e-12:
            return (0.0, 1.0, 0.0)
        return (fx/fnorm, fy/fnorm, fz/fnorm)

    def project(self, p: Vec3, width: float, height: float) -> Optional[Tuple[float, float, float]]:
        eye = self.eye_position()
        fx, fy, fz = self.forward_ray()
        wx, wy, wz = 0.0, 0.0, 1.0
        rx = fy*wz - fz*wy
        ry = fz*wx - fx*wz
        rz = fx*wy - fy*wx
        rnorm = math.sqrt(rx*rx + ry*ry + rz*rz)
        if rnorm <= 1e-6:
            rx, ry, rz = 1.0, 0.0, 0.0
        else:
            rx, ry, rz = rx/rnorm, ry/rnorm, rz/rnorm
        ux = ry*fz - rz*fy
        uy = rz*fx - rx*fz
        uz = rx*fy - ry*fx
        px, py, pz = p[0] - eye[0], p[1] - eye[1], p[2] - eye[2]
        cam_r = px*rx + py*ry + pz*rz
        cam_u = px*ux + py*uy + pz*uz
        cam_f = px*fx + py*fy + pz*fz
        if cam_f <= 0.05:
            return None
        fov = 1.0
        focal = (height / 2.0) / math.tan(fov / 2.0)
        sx = (width / 2.0) + (cam_r / cam_f) * focal
        sy = (height / 2.0) - (cam_u / cam_f) * focal
        return (sx, sy, cam_f)

    def unproject_ray(self, sx: float, sy: float, width: float, height: float) -> Tuple[Vec3, Vec3]:
        eye = self.eye_position()
        fx, fy, fz = self.forward_ray()
        wx, wy, wz = 0.0, 0.0, 1.0
        rx = fy*wz - fz*wy
        ry = fz*wx - fx*wz
        rz = fx*wy - fy*wx
        rnorm = math.sqrt(rx*rx + ry*ry + rz*rz)
        if rnorm <= 1e-6:
            rx, ry, rz = 1.0, 0.0, 0.0
        else:
            rx, ry, rz = rx/rnorm, ry/rnorm, rz/rnorm
        ux = ry*fz - rz*fy
        uy = rz*fx - rx*fz
        uz = rx*fy - ry*fx
        fov = 1.0
        focal = (height / 2.0) / math.tan(fov / 2.0)
        ndc_x = (sx - width / 2.0) / focal
        ndc_y = -(sy - height / 2.0) / focal
        dx = fx + ndc_x * rx + ndc_y * ux
        dy = fy + ndc_x * ry + ndc_y * uy
        dz = fz + ndc_x * rz + ndc_y * uz
        dnorm = math.sqrt(dx*dx + dy*dy + dz*dz)
        return eye, (dx/dnorm, dy/dnorm, dz/dnorm)


class EntityRenderProxy:
    """Long-lived QGraphics items owned by one semantic entity."""

    _BOX_EDGES = (
        (0,1),(0,2),(0,4),(1,3),(1,5),(2,3),
        (2,6),(3,7),(4,5),(4,6),(5,7),(6,7),
    )

    def __init__(self, scene: QGraphicsScene, entity_id: str):
        self.scene = scene
        self.entity_id = entity_id
        self.kind = ''
        self.bounds: Optional[Bounds] = None
        self.mesh_items: List[QGraphicsPolygonItem] = []
        self.proxy_items: List[QGraphicsLineItem] = []

    def ensure_mesh_items(self, count: int) -> None:
        while len(self.mesh_items) < count:
            item = QGraphicsPolygonItem()
            self.scene.addItem(item)
            self.mesh_items.append(item)
        for index, item in enumerate(self.mesh_items):
            item.setVisible(index < count)

    def ensure_proxy_items(self) -> None:
        while len(self.proxy_items) < len(self._BOX_EDGES):
            item = QGraphicsLineItem()
            item.setPen(QPen(QColor(80, 105, 135), 1))
            item.setZValue(1000)
            self.scene.addItem(item)
            self.proxy_items.append(item)

    def hide_mesh(self) -> None:
        for item in self.mesh_items:
            item.hide()

    def hide_proxy(self) -> None:
        for item in self.proxy_items:
            item.hide()

    def remove(self) -> None:
        for item in self.mesh_items:
            self.scene.removeItem(item)
        for item in self.proxy_items:
            self.scene.removeItem(item)
        self.mesh_items.clear()
        self.proxy_items.clear()


class Viewport3D(QGraphicsView):
    """Persistent-item 3D viewport with deferred heavy geometry evaluation."""

    selectionChangedByView = Signal()
    statusChanged = Signal(str)

    def __init__(self, doc: Document, stack: CommandStack, parent=None):
        self._scene = QGraphicsScene()
        super().__init__(self._scene, parent)
        self.doc = doc
        self.stack = stack
        self.camera = OrbitCamera()
        self.active_tool = 'orbit'
        self.sculpt_brush = BrushSpec(radius=1.0, strength=0.8, falloff='smooth')
        self.sculpt_op = 'pull'
        self._sculpt_tx: Optional[SculptTransaction] = None
        self._drag_start_pos: Optional[QPointF] = None
        self._last_mouse_pos: Optional[QPointF] = None
        self._is_panning = False
        self._is_orbiting = False
        self._interaction_active = False
        self._render_cache: Dict[str, EntityRenderProxy] = {}
        self._evaluation_cache = IncrementalEvaluationCache(TessellatedPreviewBackend())
        self._evaluation = None
        self._grid_items: List[QGraphicsLineItem] = []
        self._last_selection = set()
        self._styles = {
            'selected': (QPen(QColor(40, 110, 200), 1), QBrush(QColor(110, 180, 245, 210))),
            'wall': (QPen(QColor(140, 150, 160), 1), QBrush(QColor(230, 235, 240, 230))),
            'floor': (QPen(QColor(120, 140, 130), 1), QBrush(QColor(210, 220, 215, 220))),
            'default': (QPen(QColor(100, 110, 125), 1), QBrush(QColor(200, 205, 215, 200))),
        }
        self._view_settle_timer = QTimer(self)
        self._view_settle_timer.setSingleShot(True)
        self._view_settle_timer.timeout.connect(self._finish_deferred_view_change)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setMouseTracking(True)
        self.setBackgroundBrush(QColor(238, 240, 243))
        self.stack.subscribe(self.on_document_modified)
        self.on_document_modified(None)

    def rebind(self, doc: Document, stack: CommandStack):
        self.stack.unsubscribe(self.on_document_modified)
        self.doc = doc
        self.stack = stack
        self.stack.subscribe(self.on_document_modified)
        self._sculpt_tx = None
        self._interaction_active = False
        self._evaluation_cache.clear()
        for proxy in self._render_cache.values():
            proxy.remove()
        self._render_cache.clear()
        self._last_selection.clear()
        self.on_document_modified(None)

    def set_tool(self, tool: str):
        self.active_tool = tool
        self.statusChanged.emit(f"3D Viewport Tool: {tool}")

    def on_document_modified(self, modified_ids):
        # Reactively invalidate only what changed or force clean repaint
        self._evaluation_cache.invalidate(modified_ids)
        self.update()

    def _style_for(self, entity_id: str, kind: str):
        if entity_id in self.doc.selection:
            return self._styles['selected']
        if kind == 'wall':
            return self._styles['wall']
        if kind in ('floor', 'room_floor'):
            return self._styles['floor']
        return self._styles['default']

    def _bounds_from_mesh(self, mesh: MeshPayload) -> Optional[Bounds]:
        if not mesh.vertices:
            return None
        return (
            tuple(min(p[i] for p in mesh.vertices) for i in range(3)),
            tuple(max(p[i] for p in mesh.vertices) for i in range(3)),
        )

    def _proxy(self, entity_id: str) -> EntityRenderProxy:
        proxy = self._render_cache.get(entity_id)
        if proxy is None:
            proxy = EntityRenderProxy(self._scene, entity_id)
            self._render_cache[entity_id] = proxy
        return proxy

    def _ensure_grid(self) -> None:
        needed = (8 * 2 + 1) * 2
        pen = QPen(QColor(215, 218, 222), 1)
        while len(self._grid_items) < needed:
            item = QGraphicsLineItem()
            item.setPen(pen)
            item.setZValue(-1000)
            self._scene.addItem(item)
            self._grid_items.append(item)

    def _update_grid(self) -> None:
        self._ensure_grid()
        w = max(100, self.width())
        h = max(100, self.height())
        grid_extent = 8
        cursor = 0
        for i in range(-grid_extent, grid_extent + 1):
            pairs = (
                ((float(i), -float(grid_extent), 0.0), (float(i), float(grid_extent), 0.0)),
                ((-float(grid_extent), float(i), 0.0), (float(grid_extent), float(i), 0.0)),
            )
            for a, b in pairs:
                item = self._grid_items[cursor]
                cursor += 1
                p1 = self.camera.project(a, w, h)
                p2 = self.camera.project(b, w, h)
                if p1 and p2:
                    item.setLine(p1[0], p1[1], p2[0], p2[1])
                    item.show()
                else:
                    item.hide()

    def _bbox_corners(self, bounds: Bounds):
        lo, hi = bounds
        return [
            (x, y, z)
            for x in (lo[0], hi[0])
            for y in (lo[1], hi[1])
            for z in (lo[2], hi[2])
        ]

    def _update_interaction_proxies(self) -> None:
        w = max(100, self.width())
        h = max(100, self.height())
        self._scene.setSceneRect(0, 0, w, h)
        self._update_grid()
        for proxy in self._render_cache.values():
            proxy.hide_mesh()
            if proxy.bounds is None:
                proxy.hide_proxy()
                continue
            proxy.ensure_proxy_items()
            corners = self._bbox_corners(proxy.bounds)
            projected = [self.camera.project(point, w, h) for point in corners]
            for item, (a, b) in zip(proxy.proxy_items, proxy._BOX_EDGES):
                p1, p2 = projected[a], projected[b]
                if p1 and p2:
                    item.setLine(p1[0], p1[1], p2[0], p2[1])
                    item.show()
                else:
                    item.hide()

    def _begin_interaction(self) -> None:
        self._interaction_active = True
        self._update_interaction_proxies()

    def _finish_deferred_view_change(self) -> None:
        if self._is_orbiting or self._is_panning or self._sculpt_tx is not None:
            return
        self._interaction_active = False
        self.redraw(force_full=True)

    def refresh_selection(self) -> None:
        selected = set(self.doc.selection)
        changed = selected ^ self._last_selection
        for entity_id in changed:
            proxy = self._render_cache.get(entity_id)
            if proxy is None:
                continue
            pen, brush = self._style_for(entity_id, proxy.kind)
            for item in proxy.mesh_items:
                item.setPen(pen)
                item.setBrush(brush)
        self._last_selection = selected

    def wheelEvent(self, event):
        zoom_factor = 0.88 if event.angleDelta().y() > 0 else 1.14
        self.camera.distance = max(0.5, min(200.0, self.camera.distance * zoom_factor))
        self._begin_interaction()
        self._view_settle_timer.start(120)

    def mousePressEvent(self, event):
        pos = event.position()
        self._last_mouse_pos = pos
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton
            and (event.modifiers() & Qt.KeyboardModifier.AltModifier)
        ):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._is_panning = True
            else:
                self._is_orbiting = True
            self._begin_interaction()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            ray_orig, ray_dir = self.camera.unproject_ray(pos.x(), pos.y(), self.width(), self.height())
            eval_res = self._evaluation
            best_hit: Optional[Tuple[float, str, MeshRayHit]] = None
            for body in eval_res.bodies:
                if not isinstance(body.payload, MeshPayload):
                    continue
                hit = raycast_mesh(body.entity_id, body.payload, ray_orig, ray_dir)
                if hit is not None and (best_hit is None or hit.distance < best_hit[0]):
                    best_hit = (hit.distance, body.entity_id, hit)

            if best_hit is not None:
                _, eid, mesh_hit = best_hit
                if self.active_tool == 'sculpt':
                    try:
                        surf_hit = SurfaceHit(eid, mesh_hit.surface_role, mesh_hit.world_point, mesh_hit.world_normal)
                        surf_hit.validate(self.doc)
                        self._sculpt_tx = SculptTransaction(
                            self.doc, self.stack, surf_hit, self.sculpt_brush, self.sculpt_op, 0.0
                        )
                        self._drag_start_pos = pos
                        self._begin_interaction()
                        self.statusChanged.emit(f"Sculpting {eid} ({mesh_hit.surface_role})")
                    except Exception as exc:
                        self.statusChanged.emit(f"Cannot sculpt surface: {exc}")
                else:
                    self.doc.select([eid], add=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
                    self.selectionChangedByView.emit()
                    self.refresh_selection()
            else:
                if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                    self.doc.select([])
                    self.selectionChangedByView.emit()
                    self.refresh_selection()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._last_mouse_pos is not None:
            dx = pos.x() - self._last_mouse_pos.x()
            dy = pos.y() - self._last_mouse_pos.y()
            if self._is_orbiting:
                self.camera.yaw += dx * 0.008
                self.camera.pitch = max(
                    -math.pi/2 + 0.05,
                    min(math.pi/2 - 0.05, self.camera.pitch + dy * 0.008),
                )
                self._update_interaction_proxies()
                self._last_mouse_pos = pos
                return
            if self._is_panning:
                speed = self.camera.distance * 0.002
                self.camera.target = (
                    self.camera.target[0] - dx * speed * math.cos(self.camera.yaw),
                    self.camera.target[1] - dx * speed * math.sin(self.camera.yaw),
                    self.camera.target[2] + dy * speed,
                )
                self._update_interaction_proxies()
                self._last_mouse_pos = pos
                return

        if self._sculpt_tx is not None and self._drag_start_pos is not None:
            delta_y = (self._drag_start_pos.y() - pos.y()) * 0.01
            amount = max(0.0, float(delta_y))
            self._sculpt_tx.update(amount=amount)
            self.statusChanged.emit(f"Sculpt Amount: {amount:.3f}")
            self._update_interaction_proxies()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            was_camera_drag = self._is_orbiting or self._is_panning
            self._is_orbiting = False
            self._is_panning = False
            had_sculpt = self._sculpt_tx is not None
            if self._sculpt_tx is not None:
                if self._sculpt_tx.amount > 0.001:
                    try:
                        self._sculpt_tx.commit()
                        self.statusChanged.emit(f"Applied sculpt modifier ({self.sculpt_op})")
                    except Exception as exc:
                        self.statusChanged.emit(f"Sculpt commit error: {exc}")
                self._sculpt_tx = None
                self._drag_start_pos = None
                self.selectionChangedByView.emit()
            if was_camera_drag or had_sculpt:
                self._interaction_active = False
                if was_camera_drag:
                    self.redraw(force_full=True)
                return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, '_view_settle_timer'):
            return
        self._begin_interaction()
        self._view_settle_timer.start(120)

    def redraw(self, force_full=False):
        if self._interaction_active and not force_full:
            self._update_interaction_proxies()
            return

        self._interaction_active = False
        w = max(100, self.width())
        h = max(100, self.height())
        self._scene.setSceneRect(0, 0, w, h)
        self._update_grid()
        evaluation = self._evaluation
        live_ids = set()

        for body in evaluation.bodies:
            mesh = body.payload
            if not isinstance(mesh, MeshPayload):
                continue
            live_ids.add(body.entity_id)
            proxy = self._proxy(body.entity_id)
            proxy.kind = body.semantic_kind
            proxy.bounds = self._bounds_from_mesh(mesh)
            proxy.hide_proxy()
            proxy.ensure_mesh_items(len(mesh.triangles))
            pen, brush = self._style_for(body.entity_id, body.semantic_kind)

            for item, tri in zip(proxy.mesh_items, mesh.triangles):
                v0, v1, v2 = mesh.vertices[tri[0]], mesh.vertices[tri[1]], mesh.vertices[tri[2]]
                p0 = self.camera.project(v0, w, h)
                p1 = self.camera.project(v1, w, h)
                p2 = self.camera.project(v2, w, h)
                if not (p0 and p1 and p2):
                    item.hide()
                    continue
                item.setPolygon(QPolygonF([
                    QPointF(p0[0], p0[1]),
                    QPointF(p1[0], p1[1]),
                    QPointF(p2[0], p2[1]),
                ]))
                item.setPen(pen)
                item.setBrush(brush)
                item.setZValue(-((p0[2] + p1[2] + p2[2]) / 3.0))
                item.show()

        for entity_id in list(self._render_cache):
            if entity_id not in live_ids:
                self._render_cache.pop(entity_id).remove()

        self._last_selection = set(self.doc.selection)
