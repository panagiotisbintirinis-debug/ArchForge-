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
                out.append((str(m.get("name", "")), round(float(m.get("area", 0.0)), 2)))
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
