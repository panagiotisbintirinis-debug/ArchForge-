"""Scenario harness: build with the UI's own transactions, log every step, check, save, report."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List


@dataclass
class Step:
    action: str
    ok: bool
    note: str = ""


@dataclass
class Scenario:
    key: str
    title: str
    window: object
    steps: List[Step] = field(default_factory=list)
    checks: List[Step] = field(default_factory=list)

    @property
    def doc(self):
        return self.window.doc

    @property
    def stack(self):
        return self.window.stack

    # ------------------------------------------------------------------------------------------- actions
    def step(self, action, fn):
        """Run one user action; a failure is logged (the scenario goes on), never hidden."""
        try:
            note = fn()
            self.steps.append(Step(action, True, "" if note is None else str(note)))
            return note
        except Exception as exc:                      # noqa: BLE001 — the log is the point
            self.steps.append(Step(action, False, f"{type(exc).__name__}: {exc}"))
            return None

    def wall(self, a, b, thickness, height=2.7, z=None):
        """One wall as the wall tool draws it (WallDrawTransaction, magnet angles, snapping on)."""
        from archforge.core.interaction import MAGNET, WallDrawTransaction

        def run():
            t = WallDrawTransaction(self.doc, self.stack, a, z=self.level_z() if z is None else z, height=height,
                                    thickness=thickness, angle_increment=MAGNET)
            t.update(*b)
            eid = t.commit()
            e = self.doc.get(eid).params
            end = (round(float(e["x2"]), 3), round(float(e["y2"]), 3))
            snapped = "" if math.dist(end, b) < 1e-6 else f" · το άκρο κόλλησε στο {end} αντί για {tuple(b)}"
            return f"τοίχος {thickness * 100:.0f} cm{snapped}"
        return self.step(f"Τοίχος {tuple(a)} → {tuple(b)}", run)

    def opening(self, kind, x, y, width, height=None, sill=None, label=""):
        from archforge.core.interaction import OpeningPlaceTransaction

        def run():
            t = OpeningPlaceTransaction(self.doc, self.stack, kind, x, y, width=width, height=height, sill=sill,
                                        level_z=self.level_z())
            if t.host_id is None:
                raise ValueError("δεν βρέθηκε τοίχος εκεί")
            eid = t.commit()
            return f"{label or kind} {width * 100:.0f} cm στον τοίχο {self.doc.get(t.host_id).name or t.host_id[:6]}"
        return self.step(f"{label or kind.capitalize()} στο ({x}, {y})", run)

    def level(self, name, elevation=None):
        """New storey («+ Όροφος» / «Υπόγειο») when the name is new, else switch to it from the floor selector."""
        def run():
            w = self.window
            if name not in self.doc.levels:
                from archforge.core.commands import CreateFloorLevel
                self.stack.execute(CreateFloorLevel(name, float(elevation)))
                w._refresh_floor_selector()
                w._redraw_views(all_views=True)
                return f"νέος όροφος στα {float(elevation):+.2f} m"
            w._refresh_floor_selector()
            w._activate_level_by_name(name)
            if self.doc.active_level_name() != name:
                raise ValueError(f"ο επιλογέας ορόφων δεν άλλαξε στο «{name}» (ενεργός: {self.doc.active_level_name()})")
            return f"ενεργός όροφος στα {self.level_z():+.2f} m"
        return self.step(f"Όροφος «{name}»", run)

    def stair(self, origin, pointer, width=1.0, layout=None):
        """Stair tool: click the start, move toward the run, click (StairPlaceTransaction)."""
        from archforge.core.interaction import StairPlaceTransaction

        def run():
            t = StairPlaceTransaction(self.doc, self.stack, origin, width=width, layout=layout)
            t.update(*pointer)
            if not t.preview.get('fits', False):
                raise ValueError("η σκάλα περνά από τοίχο — " + " · ".join(t.preview.get('suggestions', [])[:2]))
            c = t.active_candidate
            t.commit()
            return (f"{c.layout} · {c.riser_count} ρίχτια {c.riser_height * 100:.1f} cm · πάτημα {c.tread_depth * 100:.0f} cm"
                    f" · ως «{t.upper_level_name}»")
        return self.step(f"Σκάλα από {tuple(origin)} προς {tuple(pointer)}", run)

    def name_room(self, x, y, name):
        """Name / use of the room under (x, y) (right click on the room ▸ Χρήση χώρου)."""
        from archforge.core.commands import SetRoomMetadata
        from archforge.geometry.regions import point_in_polygon

        def run():
            face = next((f for f in self.doc.active_room_faces() if point_in_polygon(x, y, f.polygon)), None)
            if face is None:
                raise ValueError("δεν βρέθηκε κλειστός χώρος εκεί")
            self.stack.execute(SetRoomMetadata(face.signature, {"name": name, "use": name}))
            return name
        return self.step(f"Χρήση χώρου στο ({x}, {y}): {name}", run)

    def layout(self, kind, x, y, **options):
        """«Κουζίνα εδώ» / «Μπάνιο εδώ» (mouse menu in the room) → first proposal → ✓ Εφαρμογή."""
        from archforge.ui.layout_assist import run as layout_run

        def run():
            a = self.window._layout_assist
            for key, value in options.items():
                a.set_option(key, value)
            layout_run(self.window, kind, None, (x, y))
            p = a.proposal
            if p is None or not p.entities:
                raise ValueError("καμία πρόταση")
            label, problems, counts = p.label, list(p.problems), p.summary()
            layout_run(self.window, "apply")
            return f"{label} · {counts.get('cabinet', 0)} ντουλάπια, {counts.get('library_object', 0)} είδη" + \
                (" · ⚠ " + " · ".join(problems) if problems else "")
        return self.step(f"{'Κουζίνα' if kind == 'kitchen' else 'Μπάνιο'} εδώ ({x}, {y})", run)

    def furniture(self, name, x, y, turn=0.0):
        """Library item dragged into the plan (snaps its back to a near wall), dropped: one undo."""
        from archforge.library.assets import list_assets
        from archforge.library.catalog import seed_core_library
        from archforge.ui.library_drag import LibraryCarry

        def run():
            seed_core_library()
            ids = {a["name"]: a["id"] for a in list_assets()}
            if name not in ids:
                raise ValueError(f"δεν υπάρχει στη Βιβλιοθήκη: {name}")
            carry = LibraryCarry(self.window, ("asset", ids[name]))
            carry.turn = float(turn)
            done = carry.drop(x, y)
            if not done:
                raise ValueError("δεν τοποθετήθηκε")
            p = self.doc.get(done).params
            return f"στο ({float(p['x']):.2f}, {float(p['y']):.2f}) · {float(p.get('rotation', 0.0)) % 360:.0f}°"
        return self.step(f"Έπιπλο: {name}", run)

    def point(self, tool, x, y):
        """Η/Μ point tool click (plumb_*, drain_*, elec_*, vent_*): the same handler as the plan click."""
        def run():
            n = len(self.doc.entities)
            self.window._place_site_point(tool, float(x), float(y))
            if len(self.doc.entities) <= n:
                raise ValueError("δεν μπήκε σημείο")
            return self.window.statusBar().currentMessage()[:140]
        return self.step(f"Σημείο {tool} στο ({x}, {y})", run)

    def at_wall_behind(self, name_part):
        """Plan point on the wall face behind the first object (library object or cabinet) whose name contains
        ``name_part`` — where its supply point goes."""
        for e in self.doc.entities.values():
            if e.kind in ("library_object", "cabinet") and name_part in (e.name or ""):
                p = e.params
                a = math.radians(float(p.get("rotation", 0.0)))
                d = float(p.get("depth", 0.6)) / 2 - 0.02
                # Local +y is the back (the side snapped to the wall).
                return (round(float(p["x"]) - math.sin(a) * d, 3), round(float(p["y"]) + math.cos(a) * d, 3))
        return None

    def level_z(self):
        return float(self.doc.work_plane.origin[2])

    # -------------------------------------------------------------------------------------------- checks
    def check(self, what, ok, note=""):
        self.checks.append(Step(what, bool(ok), note))

    def rooms(self):
        """Derived rooms of the active storey: [(name, area m²)] as the plan shows them."""
        from archforge.core.plan_scene import build_plan_frame
        frame = build_plan_frame(self.doc)
        out = []
        for p in frame.primitives:
            if p.role == "derived-room":
                m = dict(p.meta)
                out.append((str(m.get("name", "")), round(float(m.get("net_area", m.get("area", 0.0))), 2)))
        return sorted(out, key=lambda r: -r[1])

    def check_save_load(self, path):
        from archforge.project.persistence import load_project, save_project
        save_project(self.doc, path)
        report = load_project(path)
        doc2 = report.doc
        if report.skipped:
            self.check("Φόρτωση χωρίς απορριφθείσες οντότητες", False, f"{len(report.skipped)} απορρίφθηκαν")
        same = sorted((e.kind, e.id) for e in self.doc.entities.values()) == \
            sorted((e.kind, e.id) for e in doc2.entities.values())
        params = all(doc2.entities[i].params == e.params for i, e in self.doc.entities.items() if i in doc2.entities)
        self.check("Αποθήκευση και ξανά άνοιγμα: ίδιες οντότητες και παράμετροι", same and params,
                   f"{len(self.doc.entities)} οντότητες")

    # ------------------------------------------------------------------------------------------- outputs
    def plan_image(self, path, size=(1100, 800)):
        from PySide6.QtCore import QRectF, Qt
        w = self.window
        pv = w.plan_view
        pv.resize(*size)
        w._redraw_views(all_views=True)
        xs, ys = [], []
        for e in self.doc.entities.values():
            if e.kind == "wall":
                xs += [float(e.params["x1"]), float(e.params["x2"])]
                ys += [float(e.params["y1"]), float(e.params["y2"])]
            elif e.kind == "pool":                         # the pool, its zones and equipment room are in the frame too
                from archforge.site.pool import ZONE1, plant_rect, rim
                for q in rim(e.params, ZONE1) + plant_rect(e.params):
                    xs.append(q[0]); ys.append(q[1])
        if xs:
            r = QRectF(min(xs) - 1.5, min(ys) - 1.5, max(xs) - min(xs) + 3.0, max(ys) - min(ys) + 3.0)
            pv.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)
        pv.grab().save(str(path))

    def report(self, path, extra=""):
        def table(rows):
            return "\n".join(f"| {i} | {'✅' if s.ok else '❌'} | {s.action} | {s.note} |" for i, s in enumerate(rows, 1))
        failed = [s for s in self.steps + self.checks if not s.ok]
        text = (f"# Σενάριο {self.key}: {self.title}\n\n"
                "Χτίστηκε με τις ίδιες ενέργειες που κάνει το UI (εργαλείο τοίχου, ανοίγματα, στέγη από το μενού). "
                "Η γεωμετρία είναι σχέδιο δοκιμής, όχι πραγματικό έργο.\n\n"
                f"**Αποτέλεσμα:** {len(self.steps)} βήματα, {len(self.checks)} έλεγχοι — "
                f"{'όλα εντάξει' if not failed else f'{len(failed)} προβλήματα (❌)'}.\n\n"
                "## Βήματα\n\n| # | | Ενέργεια | Σημείωση |\n|---|---|---|---|\n" + table(self.steps) +
                "\n\n## Έλεγχοι\n\n| # | | Έλεγχος | Σημείωση |\n|---|---|---|---|\n" + table(self.checks) +
                "\n\n" + extra)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return failed
