"""Walls worked in the 3D view: draw, stretch, move parallel, height, and the door/window ghost.

The 3D view only reports where the pointer meets the floor of the active storey (or a
wall, for openings).  Every rule is the plan's own: drawing runs the same
``PointerController`` wall tool (type from the project questions, interior walls,
dimension reference when a space closes), an end handle runs the plan's stretch
(``ConnectedWallEndpointStretchTransaction`` — joined walls follow), the middle handle
moves the wall with the plan's ``WallMoveTransaction`` -> ``MoveWall`` (perpendicular to
its axis; joined walls stretch, openings and objects against it ride along), the top handle sets the height
with ``VerticalStretchTransaction``.  One gesture = one command = one undo; previews are
plain dicts for the WebGL overlay and never touch the Document.

No Qt here: the PBR viewport hands JSON events to ``Wall3DEditor.handle_event`` and draws
the returned ghost (``archforge/ui/wall_edit_3d_js.py``).
"""
from __future__ import annotations

import copy
import json
import math

from archforge.architecture.wall_edit import WallMoveTransaction
from archforge.core.interaction import OpeningPlaceTransaction, VerticalStretchTransaction
from archforge.core.snapping import best_snap
from archforge.core.viewport import PointerController, PointerEvent
from archforge.core.wall_top_3d import vertical_height_from_ray

# Snap radius on screen: 12 px at the cursor, never under the plan's 10 cm nor over 60 cm.
SNAP_PIXELS = 12.0
MIN_SNAP_TOL, MAX_SNAP_TOL = 0.10, 0.60
# Parallel move and height go in 5 cm steps with snap on (Shift = free).
MOVE_STEP = 0.05
HEIGHT_STEP = 0.05
MIN_HEIGHT = 0.10
HANDLES = ("endpoint1", "endpoint2", "mid", "top")
OPENING_TOOLS = {"door": ("door", "rectangle"), "window": ("window", "rectangle"),
                 "opening_rect": ("opening", "rectangle"), "opening_arch": ("opening", "arch")}
OPENING_NAMES = {"door": "Πόρτα", "window": "Παράθυρο", "opening": "Άνοιγμα"}


def metres(value):
    """'3,45 m' — Greek decimal comma."""
    return f"{float(value):.2f}".replace(".", ",") + " m"


def _wall_box(p, color="draw"):
    return {"x1": float(p["x1"]), "y1": float(p["y1"]), "x2": float(p["x2"]), "y2": float(p["y2"]),
            "z": float(p.get("z", 0.0)), "height": float(p.get("height", 2.7)),
            "thickness": float(p.get("thickness", 0.15)), "color": color}


def _changed(before, after):
    return any(before.get(k) != after.get(k) for k in set(before) | set(after))


class Wall3DEditor:
    """Translate 3D pointer events into the plan's wall / opening transactions."""

    def __init__(self, doc, stack):
        self.doc, self.stack = doc, stack
        self.snap_enabled = True
        self._reset_draw()
        self._edit = None          # {'handle', 'eid', 'tx', 'origin', 'normal', ...}
        self._last_ev = None

    # -- state ------------------------------------------------------------------
    def _reset_draw(self):
        self.draw = PointerController(self.doc, self.stack)
        self.draw.set_tool("wall")
        self.draw.snap_enabled = self.snap_enabled
        self.chain_start = None

    def rebind(self, doc, stack):
        self.cancel_all()
        self.doc, self.stack = doc, stack
        self._reset_draw()

    def set_snap_enabled(self, enabled):
        self.snap_enabled = bool(enabled)
        self.draw.snap_enabled = self.snap_enabled

    @property
    def drawing(self):
        return self.draw.active is not None

    @property
    def editing(self):
        return self._edit is not None

    @property
    def floor_z(self):
        return float(self.doc.work_plane.origin[2])

    def _ev(self, x, y, shift=False):
        a, b = self.doc.work_plane.project((float(x), float(y), self.floor_z))
        return PointerEvent(a, b, shift=bool(shift))

    def _tolerance(self, pxm):
        """Snap radius (m) from the metres-per-pixel at the cursor."""
        try:
            pxm = float(pxm)
        except (TypeError, ValueError):
            return MIN_SNAP_TOL
        if not math.isfinite(pxm) or pxm <= 0:
            return MIN_SNAP_TOL
        return max(MIN_SNAP_TOL, min(MAX_SNAP_TOL, pxm * SNAP_PIXELS))

    def _ghost(self, walls=(), marker=None, label=None, status=None, **extra):
        out = {"walls": list(walls), "marker": marker, "label": label, "floor_z": self.floor_z,
               "drawing": self.drawing, "editing": self.editing}
        if status:
            out["status"] = status
        out.update(extra)
        return out

    # -- drawing ----------------------------------------------------------------
    def hover(self, x, y, shift=False, pxm=None):
        self.draw.snap_tolerance = self._tolerance(pxm)
        ev = self._ev(x, y, shift)
        if self.drawing:
            self.draw.pointer_move(ev)
            return self._draw_ghost()
        # Before the first click: where the wall would start (corner, wall, grid).
        sx, sy = float(x), float(y)
        kind = "free"
        if self.snap_enabled and not shift:
            sp = best_snap(self.doc, sx, sy, self.draw.snap_tolerance, self.draw.grid)
            if sp is not None:
                sx, sy, kind = float(sp.x), float(sp.y), str(sp.kind)
            else:
                g = self.draw.grid
                sx, sy, kind = round(sx / g) * g, round(sy / g) * g, "grid"
        return self._ghost(marker={"pos": [sx, sy, self.floor_z], "kind": kind},
                           status="Τοίχος στο 3D: κλικ = αρχή · Shift = ελεύθερα")

    def click(self, x, y, shift=False, pxm=None):
        self.draw.snap_tolerance = self._tolerance(pxm)
        ev = self._ev(x, y, shift)
        if not self.drawing:
            self.draw.pointer_down(ev)
            self.chain_start = tuple(self.draw.active.start)
            return self._draw_ghost(status="Τοίχος: κλικ = επόμενο σημείο · διπλό κλικ / δεξί κλικ / Esc = τέλος")
        try:
            result = self.draw.pointer_up(ev)
        except ValueError:
            # A second click on the same point (double click) or a too short wall: keep drawing.
            return self._draw_ghost()
        wid = result.entity_id
        if not wid or wid not in self.doc.entities:
            return self._ghost()
        p = self.doc.get(wid).params
        end = (float(p["x2"]), float(p["y2"]))
        length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
        start = self.chain_start
        if start is not None and math.hypot(end[0] - start[0], end[1] - start[1]) <= 1e-6:
            # The outline closed on its first point: the chain is done.
            self.chain_start = None
            return self._ghost(committed=wid,
                               status=f"Τοίχος {metres(length)} — κλειστό περίγραμμα · Ctrl+Z = αναίρεση")
        # The next wall starts where this one ended (corner).
        a, b = self.doc.work_plane.project((end[0], end[1], self.floor_z))
        self.draw.pointer_down(PointerEvent(a, b))
        return self._draw_ghost(committed=wid,
                                status=f"Τοίχος {metres(length)} — συνέχισε · διπλό κλικ / δεξί κλικ / Esc = τέλος")

    def finish(self):
        """Double click, right click or Esc: drop the live segment, keep the walls already made."""
        was = self.drawing
        self.draw.cancel()
        self.chain_start = None
        return self._ghost(status="Τέλος τοίχων" if was else None)

    def _draw_ghost(self, **extra):
        tx = self.draw.active
        if tx is None:
            return self._ghost(**extra)
        g = self.draw.preview.geometry or {}
        hud = self.draw.preview.hud or {}
        sx, sy = tx.start
        ex, ey = (float(g.get("x2", sx)), float(g.get("y2", sy))) if g else (sx, sy)
        params = {"x1": sx, "y1": sy, "x2": ex, "y2": ey, "z": tx.z, "height": tx.height, "thickness": tx.thickness}
        length = math.hypot(ex - sx, ey - sy)
        walls = [_wall_box(params)] if length > 1e-6 else []
        text = metres(length)
        if "corner_deg" in hud:
            text += f" · {float(hud['corner_deg']):.0f}°"
        label = {"text": text, "pos": [(sx + ex) / 2, (sy + ey) / 2, tx.z + tx.height + 0.25]} if walls else None
        snap = self.draw.preview.snap
        marker = {"pos": [ex, ey, tx.z], "kind": str(snap.get("kind", ""))} if snap else {"pos": [ex, ey, tx.z], "kind": "free"}
        return self._ghost(walls, marker, label, **extra)

    # -- handles of the selected wall -------------------------------------------
    def selected_wall(self):
        ids = [eid for eid in self.doc.selection if eid in self.doc.entities]
        if len(ids) != 1 or self.doc.get(ids[0]).kind != "wall":
            return None
        return self.doc.get(ids[0])

    def handles(self):
        """End, middle (on the floor) and top handles of the one selected wall."""
        wall = self.selected_wall()
        if wall is None:
            return []
        p = wall.params
        z = float(p.get("z", 0.0))
        mx, my = (float(p["x1"]) + float(p["x2"])) / 2, (float(p["y1"]) + float(p["y2"])) / 2
        out = [{"id": "endpoint1", "kind": "end", "pos": [float(p["x1"]), float(p["y1"]), z]},
               {"id": "endpoint2", "kind": "end", "pos": [float(p["x2"]), float(p["y2"]), z]},
               {"id": "mid", "kind": "mid", "pos": [mx, my, z]}]
        # A sloped top (per-end heights) is edited by its own wall-top handles, not here.
        if "start_height" not in p and "end_height" not in p:
            out.append({"id": "top", "kind": "top", "pos": [mx, my, z + float(p.get("height", 2.7))]})
        return out

    def handles_payload(self):
        wall = self.selected_wall()
        ids = [eid for eid in self.doc.selection if eid in self.doc.entities]
        # 'selected': what Delete removes when the key lands in the 3D page.
        return {"handles": self.handles(), "entity_id": wall.id if wall is not None else "", "floor_z": self.floor_z,
                "selected": ids[0] if len(ids) == 1 else ""}

    def handle_down(self, handle, x, y, pxm=None):
        if self._edit is not None:
            self.handle_cancel()
        handle = str(handle)
        wall = self.selected_wall()
        if handle not in HANDLES or wall is None or handle not in {h["id"] for h in self.handles()}:
            raise ValueError("η λαβή δεν ανήκει πια στον επιλεγμένο τοίχο")
        p = wall.params
        edit = {"handle": handle, "eid": wall.id}
        if handle in ("endpoint1", "endpoint2"):
            # The plan's own stretch: the joined walls follow, one undo.
            ctl = PointerController(self.doc, self.stack)
            ctl.snap_tolerance = self._tolerance(pxm)
            ctl.set_tool("stretch")
            ctl.set_target(wall.id, handle)
            edit["ctl"] = ctl
            self._edit = edit
            ctl.pointer_down(self._ev(x, y))
        elif handle == "mid":
            # The plan's own wall move (W2): one MoveWall, everything joined follows.
            edit["tx"] = WallMoveTransaction(self.doc, self.stack, wall.id, float(x), float(y), step=MOVE_STEP)
            self._edit = edit
        else:
            edit["tx"] = VerticalStretchTransaction(self.doc, self.stack, wall.id)
            self._edit = edit
        return self._edit_ghost()

    def handle_move(self, x, y, shift=False, origin=None, direction=None):
        edit = self._edit
        if edit is None:
            return self._ghost()
        snap = self.snap_enabled and not shift
        handle = edit["handle"]
        try:
            if handle in ("endpoint1", "endpoint2"):
                ev = self._ev(x, y, shift)
                edit["ctl"].pointer_move(ev)
            elif handle == "mid":
                edit["tx"].step = MOVE_STEP if snap else 0.01
                edit["tx"].update(x, y)
            else:
                p = self.doc.get(edit["eid"]).params
                base = float(p.get("z", 0.0))
                mx, my = (float(p["x1"]) + float(p["x2"])) / 2, (float(p["y1"]) + float(p["y2"])) / 2
                height = vertical_height_from_ray(base, (mx, my), origin, direction)
                if snap:
                    height = round(height / HEIGHT_STEP) * HEIGHT_STEP
                edit["tx"].update(base + max(MIN_HEIGHT, height))
        except ValueError as exc:
            return self._edit_ghost(status=str(exc))
        return self._edit_ghost()

    def handle_up(self):
        edit = self._edit
        self._edit = None
        if edit is None:
            return self._ghost()
        handle, eid = edit["handle"], edit["eid"]
        if handle in ("endpoint1", "endpoint2"):
            ctl = edit["ctl"]
            tx = ctl.active
            if tx is None or not any(_changed(tx.before[w], tx.previews[w]) for w in tx.before):
                ctl.cancel()
                return self._ghost()
            ctl.active.commit()
            ctl.active = None
            p = self.doc.get(eid).params
            text = f"Μήκος {metres(math.hypot(p['x2'] - p['x1'], p['y2'] - p['y1']))}"
        elif handle == "mid":
            tx = edit["tx"]
            if abs(tx.distance) < 1e-9 or tx.problem:
                tx.cancel()
                return self._ghost(status=f"⚠ {tx.problem}" if tx.problem else None)
            tx.commit()
            text = f"Παράλληλη μετακίνηση {metres(abs(tx.distance))}"
        else:
            tx = edit["tx"]
            if not _changed(tx.before, tx.preview):
                tx.cancel()
                return self._ghost()
            tx.commit()
            text = f"Ύψος {metres(tx.preview['height'])}"
        return self._ghost(committed=eid, status=f"{text} — Ctrl+Z = αναίρεση")

    def handle_cancel(self):
        edit = self._edit
        self._edit = None
        if edit is not None:
            if "ctl" in edit:
                edit["ctl"].cancel()
            else:
                edit["tx"].cancel()
        return self._ghost()

    def _edit_ghost(self, status=None):
        edit = self._edit
        if edit is None:
            return self._ghost()
        handle = edit["handle"]
        if handle in ("endpoint1", "endpoint2"):
            tx = edit["ctl"].active
            if tx is None:
                return self._ghost()
            walls = [_wall_box(p, "edit") for p in tx.previews.values()]
            p = tx.preview
            n = 1 if handle == "endpoint1" else 2
            label = {"text": f"Μήκος {metres(math.hypot(p['x2'] - p['x1'], p['y2'] - p['y1']))}",
                     "pos": [p[f"x{n}"], p[f"y{n}"], float(p["z"]) + float(p["height"]) + 0.25]}
            marker = {"pos": [p[f"x{n}"], p[f"y{n}"], float(p["z"])], "kind": "end"}
            return self._ghost(walls, marker, label, status=status)
        tx = edit["tx"]
        if handle == "mid":
            plan = tx.preview()
            walls = []
            for wid, q in plan["walls"].items():
                full = dict(self.doc.get(wid).params)
                full.update(q)
                walls.append(_wall_box(full, "bad" if plan["problem"] else "edit"))
            p = self.doc.get(edit["eid"]).params
            text = f"Μετατόπιση {metres(abs(plan['distance']))}" + (f" — {plan['problem']}" if plan["problem"] else "")
            label = {"text": text, "pos": [plan["to"][0], plan["to"][1], float(p["z"]) + float(p["height"]) + 0.25]}
            return self._ghost(walls, None, label, status=status)
        p = tx.preview
        mx, my = (p["x1"] + p["x2"]) / 2, (p["y1"] + p["y2"]) / 2
        top = float(p["z"]) + float(p["height"])
        text = f"Ύψος {metres(p['height'])}"
        return self._ghost([_wall_box(p, "edit")], None, {"text": text, "pos": [mx, my, top + 0.25]}, status=status)

    # -- door / window ghost on a wall ------------------------------------------
    def opening_ghost(self, tool, entity_id, point, preset=None):
        """Where a click would put the door/window (same transaction as the click), never committed."""
        spec = OPENING_TOOLS.get(str(tool))
        entity_id = str(entity_id or "")
        if spec is None or entity_id not in self.doc.entities:
            return {"opening": None}
        kind, shape = spec
        host = self.doc.get(entity_id)
        if host.kind != "wall":
            return {"opening": None}
        preset = preset if preset and preset.get("kind") == kind else {}
        x, y = float(point[0]), float(point[1])
        tx = OpeningPlaceTransaction(
            self.doc, self.stack, kind, x, y,
            tolerance=max(0.5, float(host.params.get("thickness", 0.0)) + 0.25), shape=shape,
            width=preset.get("width"), height=preset.get("height"), sill=preset.get("sill"),
            extra=preset.get("params"), name=preset.get("name"),
        )
        seg = tx.preview_segment()
        if tx.host_id != entity_id or not tx.preview or not seg:
            return {"opening": None}
        from archforge.architecture.openings import validate_opening
        try:
            validate_opening(host.params, tx.preview, kind)
            valid = True
        except ValueError:
            valid = False
        p = host.params
        sill, height, width = float(tx.preview["sill"]), float(tx.preview["height"]), float(tx.preview["width"])
        box = {"x1": seg[0][0], "y1": seg[0][1], "x2": seg[1][0], "y2": seg[1][1],
               "z": float(p.get("z", 0.0)) + sill, "height": height,
               "thickness": float(p.get("thickness", 0.15)) + 0.04, "color": "ok" if valid else "bad"}
        name = preset.get("name") or OPENING_NAMES[kind]
        text = f"{name} {metres(width)} × {metres(height)}" + ("" if valid else " — δεν χωράει εδώ")
        mid = [(seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2, box["z"] + height + 0.2]
        return {"opening": {"box": box, "label": {"text": text, "pos": mid}, "valid": valid,
                            "offset": float(tx.preview["offset"])}}

    # -- one entry point for the WebGL channel ----------------------------------
    def handle_event(self, payload, preset=None):
        """``payload`` is the JSON object the 3D page sends; returns the ghost to draw."""
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            raise ValueError("wall 3D event must be an object")
        kind = str(payload.get("type", ""))
        x, y = payload.get("x", 0.0), payload.get("y", 0.0)
        shift, pxm = bool(payload.get("shift", False)), payload.get("pxm")
        if kind == "hover":
            return self.hover(x, y, shift, pxm)
        if kind == "click":
            return self.click(x, y, shift, pxm)
        if kind == "finish":
            return self.finish()
        if kind == "handle_down":
            return self.handle_down(payload.get("handle"), x, y, pxm)
        if kind == "handle_move":
            return self.handle_move(x, y, shift, payload.get("origin"), payload.get("direction"))
        if kind == "handle_up":
            return self.handle_up()
        if kind == "handle_cancel":
            return self.handle_cancel()
        if kind == "opening_hover":
            return self.opening_ghost(payload.get("tool"), payload.get("entity_id"), payload.get("point") or (x, y), preset)
        if kind == "opening_leave":
            return {"opening": None}
        raise ValueError(f"unknown wall 3D event: {kind}")

    def cancel_all(self):
        self.handle_cancel()
        return self.finish()


def ghost_script(ghost):
    """The JS call that draws a ghost (view-only; never authoritative geometry)."""
    return ("if (window.archforgeSetWallGhost) window.archforgeSetWallGhost("
            + json.dumps(copy.deepcopy(ghost), separators=(",", ":")) + ");")


def handles_script(payload):
    return ("if (window.archforgeSetWallHandles) window.archforgeSetWallHandles("
            + json.dumps(payload, separators=(",", ":")) + ");")


def opening_script(ghost):
    return ("if (window.archforgeSetOpeningGhost) window.archforgeSetOpeningGhost("
            + json.dumps(ghost.get("opening"), separators=(",", ":")) + ");")
