from __future__ import annotations
import math
from typing import Dict, Optional, Tuple, List, Any

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene

from archforge.core.model import Document
from archforge.core.commands import CommandStack
from archforge.geometry.mesh import TessellatedPreviewBackend, MeshPayload
from archforge.geometry.picking import raycast_mesh, MeshRayHit
from archforge.geometry.selection import BrushSpec, SurfaceHit, sculpt_modifier_from_hit
from archforge.geometry.sculpt_transaction import SculptTransaction

Vec3 = Tuple[float, float, float]

class OrbitCamera:
    def __init__(self, cx: float = 0.0, cy: float = 0.0, cz: float = 0.0,
                 distance: float = 12.0, yaw: float = 0.7, pitch: float = 0.5):
        self.target = (cx, cy, cz)
        self.distance = distance
        self.yaw = yaw       # Azimuth angle in radians around Z
        self.pitch = pitch   # Elevation angle above XY plane

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
        """Project 3D world coordinate to 2D view screen coordinate (sx, sy, depth)."""
        eye = self.eye_position()
        fx, fy, fz = self.forward_ray()
        wx, wy, wz = 0.0, 0.0, 1.0
        # Right vector = F x W
        rx = fy*wz - fz*wy
        ry = fz*wx - fx*wz
        rz = fx*wy - fy*wx
        rnorm = math.sqrt(rx*rx + ry*ry + rz*rz)
        if rnorm <= 1e-6:
            rx, ry, rz = 1.0, 0.0, 0.0
        else:
            rx, ry, rz = rx/rnorm, ry/rnorm, rz/rnorm

        # True Up vector = R x F
        ux = ry*fz - rz*fy
        uy = rz*fx - rx*fz
        uz = rx*fy - ry*fx

        # Point relative to eye
        px, py, pz = p[0] - eye[0], p[1] - eye[1], p[2] - eye[2]
        cam_r = px*rx + py*ry + pz*rz
        cam_u = px*ux + py*uy + pz*uz
        cam_f = px*fx + py*fy + pz*fz

        if cam_f <= 0.05:
            return None # Behind or too close to lens

        fov = 1.0 # ~57.3 degrees field of view
        focal = (height / 2.0) / math.tan(fov / 2.0)
        sx = (width / 2.0) + (cam_r / cam_f) * focal
        sy = (height / 2.0) - (cam_u / cam_f) * focal
        return (sx, sy, cam_f)

    def unproject_ray(self, sx: float, sy: float, width: float, height: float) -> Tuple[Vec3, Vec3]:
        """Convert 2D screen coordinate to 3D world ray (origin, normalized_direction)."""
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


class Viewport3D(QGraphicsView):
    """Interactive 3D Orbit Viewport for Freeform Sculpting & CAD Inspection.

    Supports:
      - Middle Mouse Button or Alt+LMB: Orbit Camera
      - Shift + MMB: Pan camera target
      - Mouse Wheel: Dolly/Zoom
      - Left Mouse Button: Raycast pick & interactive live surface sculpting transaction
    """
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

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setMouseTracking(True)
        self.setBackgroundBrush(QColor(238, 240, 243))
        self.redraw()

    def rebind(self, doc: Document, stack: CommandStack):
        self.doc = doc
        self.stack = stack
        self._sculpt_tx = None
        self.redraw()

    def set_tool(self, tool: str):
        self.active_tool = tool
        self.statusChanged.emit(f"3D Viewport Tool: {tool}")
        self.redraw()

    def wheelEvent(self, event):
        zoom_factor = 0.88 if event.angleDelta().y() > 0 else 1.14
        self.camera.distance = max(0.5, min(200.0, self.camera.distance * zoom_factor))
        self.redraw()

    def mousePressEvent(self, event):
        pos = event.position()
        self._last_mouse_pos = pos

        # Orbit: Middle button OR Alt+Left button
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and (event.modifiers() & Qt.KeyboardModifier.AltModifier)):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._is_panning = True
            else:
                self._is_orbiting = True
            return

        # Freeform Sculpting or Picking with Left Mouse Button
        if event.button() == Qt.MouseButton.LeftButton:
            ray_orig, ray_dir = self.camera.unproject_ray(pos.x(), pos.y(), self.width(), self.height())
            eval_res = TessellatedPreviewBackend().evaluate(self.doc)

            best_hit: Optional[Tuple[float, str, MeshRayHit]] = None
            for body in eval_res.bodies:
                if not isinstance(body.payload, MeshPayload):
                    continue
                hit = raycast_mesh(body.entity_id, body.payload, ray_orig, ray_dir)
                if hit is not None and (best_hit is None or hit.distance < best_hit[0]):
                    best_hit = (hit.distance, body.entity_id, hit)

            if best_hit is not None:
                _, eid, m_hit = best_hit
                if self.active_tool == 'sculpt':
                    try:
                        surf_hit = SurfaceHit(eid, m_hit.surface_role, m_hit.world_point, m_hit.world_normal)
                        surf_hit.validate(self.doc)
                        self._sculpt_tx = SculptTransaction(self.doc, self.stack, surf_hit, self.sculpt_brush, self.sculpt_op, 0.0)
                        self._drag_start_pos = pos
                        self.statusChanged.emit(f"Sculpting {eid} ({m_hit.surface_role})")
                    except Exception as exc:
                        self.statusChanged.emit(f"Cannot sculpt surface: {exc}")
                else:
                    self.doc.select([eid], add=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
                    self.selectionChangedByView.emit()
                    self.redraw()
            else:
                if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                    self.doc.select([])
                    self.selectionChangedByView.emit()
                    self.redraw()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._last_mouse_pos is not None:
            dx = pos.x() - self._last_mouse_pos.x()
            dy = pos.y() - self._last_mouse_pos.y()

            if self._is_orbiting:
                self.camera.yaw += dx * 0.008
                self.camera.pitch = max(-math.pi/2 + 0.05, min(math.pi/2 - 0.05, self.camera.pitch + dy * 0.008))
                self.redraw()
                self._last_mouse_pos = pos
                return
            elif self._is_panning:
                speed = self.camera.distance * 0.002
                # camera right vector in XY plane
                self.camera.target = (
                    self.camera.target[0] - dx * speed * math.cos(self.camera.yaw),
                    self.camera.target[1] - dx * speed * math.sin(self.camera.yaw),
                    self.camera.target[2] + dy * speed
                )
                self.redraw()
                self._last_mouse_pos = pos
                return

        if self._sculpt_tx is not None and self._drag_start_pos is not None:
            delta_y = (self._drag_start_pos.y() - pos.y()) * 0.01
            amount = max(0.0, float(delta_y))
            self._sculpt_tx.update(amount=amount)
            self.statusChanged.emit(f"Sculpt Amount: {amount:.3f}")
            self.redraw()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._is_orbiting = False
            self._is_panning = False
            if self._sculpt_tx is not None:
                if self._sculpt_tx.amount > 0.001:
                    try:
                        self._sculpt_tx.commit()
                        self.statusChanged.emit(f"Applied sculpt modifier ({self.sculpt_op})")
                    except Exception as exc:
                        self.statusChanged.emit(f"Sculpt commit error: {exc}")
                self._sculpt_tx = None
                self._drag_start_pos = None
                self.redraw()
                self.selectionChangedByView.emit()
                return

        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.redraw()

    def redraw(self):
        self._scene.clear()
        w = max(100, self.width())
        h = max(100, self.height())
        self._scene.setSceneRect(0, 0, w, h)

        # Draw 3D ground reference plane / grid
        pen_grid = QPen(QColor(215, 218, 222), 1)
        grid_extent = 8
        for i in range(-grid_extent, grid_extent + 1):
            p1 = self.camera.project((float(i), -float(grid_extent), 0.0), w, h)
            p2 = self.camera.project((float(i), float(grid_extent), 0.0), w, h)
            if p1 and p2:
                self._scene.addLine(p1[0], p1[1], p2[0], p2[1], pen_grid).setZValue(-1000)

            p3 = self.camera.project((-float(grid_extent), float(i), 0.0), w, h)
            p4 = self.camera.project((float(grid_extent), float(i), 0.0), w, h)
            if p3 and p4:
                self._scene.addLine(p3[0], p3[1], p4[0], p4[1], pen_grid).setZValue(-1000)

        # Render tessellated bodies
        eval_res = TessellatedPreviewBackend().evaluate(self.doc)
        selected_set = set(self.doc.selection)

        # Collect triangles with depth for Painter's Algorithm sorting
        depth_triangles = []
        for body in eval_res.bodies:
            mesh = body.payload
            if not isinstance(mesh, MeshPayload):
                continue

            # If this body is currently being sculpted in active transaction, substitute preview
            if self._sculpt_tx is not None and self._sculpt_tx.hit.owner_id == body.entity_id:
                try:
                    mesh = self._sculpt_tx.preview_mesh()
                except Exception:
                    pass

            is_sel = body.entity_id in selected_set
            for tri in mesh.triangles:
                v0, v1, v2 = mesh.vertices[tri[0]], mesh.vertices[tri[1]], mesh.vertices[tri[2]]
                p0 = self.camera.project(v0, w, h)
                p1 = self.camera.project(v1, w, h)
                p2 = self.camera.project(v2, w, h)
                if p0 and p1 and p2:
                    avg_depth = (p0[2] + p1[2] + p2[2]) / 3.0
                    depth_triangles.append((avg_depth, p0, p1, p2, is_sel, body.semantic_kind))

        # Sort descending by distance (farthest first)
        depth_triangles.sort(key=lambda x: x[0], reverse=True)

        for depth, p0, p1, p2, is_sel, kind in depth_triangles:
            poly = QPolygonF([QPointF(p0[0], p0[1]), QPointF(p1[0], p1[1]), QPointF(p2[0], p2[1])])
            if is_sel:
                brush = QBrush(QColor(110, 180, 245, 210))
                pen = QPen(QColor(40, 110, 200), 1)
            elif kind == 'wall':
                brush = QBrush(QColor(230, 235, 240, 230))
                pen = QPen(QColor(140, 150, 160), 1)
            elif kind in ('floor', 'room_floor'):
                brush = QBrush(QColor(210, 220, 215, 220))
                pen = QPen(QColor(120, 140, 130), 1)
            else:
                brush = QBrush(QColor(200, 205, 215, 200))
                pen = QPen(QColor(100, 110, 125), 1)

            item = self._scene.addPolygon(poly, pen, brush)
            item.setZValue(-depth)

