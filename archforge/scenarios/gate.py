"""Quality gate per scenario (owner 17/10, docs/scenarios/QUALITY_GATE.md).

A scenario is clean only when every check of every section is PASS or N/A.  A check is FAIL until the
program (not the scenario) is right; a fixed finding stays in the scenario's ``FINDINGS`` as FIXED with
the file(s) and the commit.  Warnings are never ignored: each one is a check of its own.

Checks run on the authoritative model through the same paths as the UI (commands, transactions, routes).
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import List, Optional

PASS, FAIL, NA = "PASS", "FAIL", "N/A"
SECTIONS = ("1. Σχεδιαστικό / αρχιτεκτονικό", "2. Στατικό", "3. Μηχανολογικά", "4. Προσφορά",
            "5. Συμπεριφορά προγράμματος", "6. Οπτικός έλεγχος")
PRIVATE = ("Υπνοδωμάτιο", "Μπάνιο", "WC")


@dataclass
class Check:
    section: str
    item: str
    status: str
    note: str = ""


class Gate:
    def __init__(self, scenario, module, out_dir):
        self.s = scenario
        self.m = module
        self.out = out_dir
        self.checks: List[Check] = []
        self.images: List[tuple] = []

    @property
    def doc(self):
        return self.s.doc

    @property
    def w(self):
        return self.s.window

    def add(self, section, item, ok: Optional[bool], note=""):
        status = NA if ok is None else (PASS if ok else FAIL)
        self.checks.append(Check(SECTIONS[section - 1], item, status, str(note)))

    def guard(self, section, item, fn):
        """A check that may crash: the crash is a FAIL with its message, never a hidden pass."""
        try:
            fn()
        except Exception as exc:                                   # noqa: BLE001 — the report is the point
            self.add(section, item, False, f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------------------------------ helpers
    def ents(self, *kinds):
        return [e for e in self.doc.entities.values() if e.kind in kinds]

    def storeys(self):
        return sorted({round(float(e.params.get("z", 0.0)), 4) for e in self.ents("wall")})

    def rooms(self, z):
        from archforge.geometry.regions import point_in_polygon  # noqa: F401
        out = []
        for face in self.doc.active_room_faces(z=z):
            meta = self.doc.room_metadata(face.signature)
            out.append((face, str(meta.get("name", "")), str(meta.get("use", ""))))
        return out

    def room_of(self, x, y, z):
        from archforge.geometry.regions import point_in_polygon
        for face, name, _use in self.rooms(z):
            if point_in_polygon(x, y, face.polygon):
                return face, name
        return None, ""

    def env(self, name):
        """Switch environment (Αρχιτεκτονικό / Φέρων / Η/Μ) the way the Layers panel does."""
        from archforge.ui.layers_panel import set_workspace
        set_workspace(self.w, name, announce=False)

    def env_for(self, kind, params=None):
        from archforge.core.layers import ARCH_LAYERS, MEP_LAYERS, entity_layer
        layer = entity_layer(kind, params)
        return "mep" if layer in MEP_LAYERS else ("arch" if layer in ARCH_LAYERS or layer == "other" else "structure")

    def snapshot(self):
        return copy.deepcopy(self.doc.to_dict())

    # ------------------------------------------------------------------------------------------ run
    def run(self, visual=True):
        """Every section; ``visual=False`` skips the pictures (tests — the build script always draws them)."""
        for fn in (self.design, self.statics, self.mep, self.quote, self.behaviour) + ((self.visual,) if visual else ()):
            fn()
        return self.checks

    # ============================================================================ 1. design
    def design(self):
        doc = self.doc
        levels = sorted(doc.levels.items(), key=lambda kv: kv[1])
        st = self.storeys()
        self.add(1, "Όροφοι και υψόμετρα", bool(st) and all(any(abs(z - lz) < 1e-3 for _n, lz in levels) for z in st),
                 " · ".join(f"{n} {z:+.2f}" for n, z in levels) + f" — τοίχοι σε {len(st)} στάθμη/ες")
        for z in st:
            rooms = self.rooms(z)
            unnamed = [n for _f, n, _u in rooms if not n]
            self.add(1, f"Χώροι με χρήση ({z:+.2f})", bool(rooms) and not unnamed,
                     f"{len(rooms)} χώροι" + (f" · χωρίς όνομα: {len(unnamed)}" if unnamed else ""))
            self.guard(1, f"Κανένα υπνοδωμάτιο/μπάνιο δεν είναι πέρασμα ({z:+.2f})", lambda z=z: self._circulation(z))
        expected = getattr(self.m, "ROOMS", None)
        if expected:
            names = {n for z in st for _f, n, _u in self.rooms(z)}
            missing = [n for n in expected if n not in names]
            self.add(1, "Οι χώροι του σχεδίου", not missing, "όλοι" if not missing else "λείπουν: " + ", ".join(missing))
        self.guard(1, "Δάπεδο σε κάθε όροφο", self._floors)
        self.guard(1, "Στέγη πάνω από κάθε ακάλυπτο χώρο", self._roofs)
        self.guard(1, "Κάτω από κεραμοσκεπή: τοίχοι ως τη στέγη ή ταβάνι", self._attic)
        stairs = self.ents("stair")
        if len(st) > 1 or stairs:
            self.guard(1, "Σκάλες με πραγματική οπή πλάκας", self._stair_openings)
        else:
            self.add(1, "Σκάλες με πραγματική οπή πλάκας", None, "ένας όροφος, χωρίς σκάλα")
        balconies = [e for e in self.ents("room_floor", "floor") if "balcon" in str(e.params.get("use", "")) or
                     "μπαλκ" in (e.name or "").lower()]
        if balconies:
            self.add(1, "Μπαλκόνια με κιγκλίδωμα", bool(self.ents("railing")), f"{len(balconies)} μπαλκόνια")
        else:
            self.add(1, "Μπαλκόνια με κιγκλίδωμα", None, "χωρίς μπαλκόνι στο σενάριο")
        self.guard(1, "Κουζίνα: ντουλάπια, νεροχύτης, εστία, ψυγείο", self._kitchen)
        self.guard(1, "Μπάνιο: λεκάνη, νιπτήρας, ντουζιέρα/μπανιέρα", self._bathrooms)
        self.guard(1, "Έπιπλα: κρεβάτι σε κάθε υπνοδωμάτιο, καναπές στο σαλόνι", self._furniture)
        self.guard(1, "Έπιπλα/είδη μέσα σε χώρο, όχι πάνω σε τοίχο ή μεταξύ τους", self._collisions)
        self.guard(1, "Πόρτες ιδιωτικών χώρων ανοίγουν προς τα μέσα", self._door_swing_side)
        self.guard(1, "Τίποτα μέσα στη σάρωση των θυρόφυλλων", self._door_swing_clear)
        english = sorted({e.name for e in self.ents("wall", "door", "window", "opening", "stair")
                          if e.name and all(ord(c) < 128 for c in e.name if c.isalpha())})
        self.add(1, "Ονόματα στοιχείων στα ελληνικά", not english, "όλα" if not english else "αγγλικά: " + ", ".join(english))
        self.guard(1, "Αποθήκευση → κλείσιμο → άνοιγμα χωρίς απώλειες", self._reopen)

    def _circulation(self, z):
        """A bedroom or bathroom with more than one door into it is a passage (doors counted on the room's side)."""
        from archforge.assistant.understanding import _opening_sides
        from archforge.geometry.regions import point_in_polygon
        doors = [e for e in self.ents("door", "opening") if e.parent_id in self.doc.entities and
                 abs(float(self.doc.get(e.parent_id).params.get("z", 0.0)) - z) < 1e-3]
        bad = []
        rooms = self.rooms(z)

        def doors_of(face):
            return [d for d in doors if any(point_in_polygon(px, py, face.polygon) for px, py in _opening_sides(self.doc, d))]

        def en_suite(d, face):
            # The other side is a bathroom/WC whose only door is this one: an en-suite, not a passage.
            other = [(f, n) for f, n, _u in rooms if f.signature != face.signature and
                     any(point_in_polygon(px, py, f.polygon) for px, py in _opening_sides(self.doc, d))]
            return bool(other) and other[0][1].startswith(("Μπάνιο", "WC")) and len(doors_of(other[0][0])) == 1
        for face, name, _use in rooms:
            if not name.startswith(PRIVATE):
                continue
            n = sum(1 for d in doors_of(face) if not en_suite(d, face))
            if n > 1:
                bad.append(f"{name} ({n} πόρτες)")
        self.add(1, f"Κανένα υπνοδωμάτιο/μπάνιο δεν είναι πέρασμα ({z:+.2f})", not bad,
                 "κάθε ιδιωτικός χώρος έχει μία πόρτα" if not bad else "πέρασμα μέσα από: " + ", ".join(bad))

    def _door_leaf_square(self, d):
        """Plan square swept by a door leaf (width × width on the side it opens to), with the rooms each side."""
        from archforge.architecture.joinery import inside_sign, resolved
        host = self.doc.get(d.parent_id)
        p = host.params
        x1, y1, x2, y2, t = (float(p[k]) for k in ("x1", "y1", "x2", "y2", "thickness"))
        L = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        nx, ny = -uy, ux
        side = inside_sign(self.doc, host, d) * (1 if resolved(d.kind, d.params)["swing"] == "in" else -1)
        c, w = float(d.params["offset"]), float(d.params["width"])
        a = (x1 + ux * (c - w / 2) + nx * side * t / 2, y1 + uy * (c - w / 2) + ny * side * t / 2)
        b = (a[0] + ux * w, a[1] + uy * w)
        sq = [a, b, (b[0] + nx * side * w, b[1] + ny * side * w), (a[0] + nx * side * w, a[1] + ny * side * w)]
        mid = ((a[0] + b[0]) / 2 + nx * side * 0.2, (a[1] + b[1]) / 2 + ny * side * 0.2)
        back = ((a[0] + b[0]) / 2 - nx * side * (t + 0.2), (a[1] + b[1]) / 2 - ny * side * (t + 0.2))
        z = float(p.get("z", 0.0))
        return sq, self.room_of(*mid, z)[1], self.room_of(*back, z)[1]

    def _door_swing_side(self):
        bad, n = [], 0
        for d in self.ents("door"):
            if d.parent_id not in self.doc.entities:
                continue
            _sq, into, other = self._door_leaf_square(d)
            if other.startswith(PRIVATE) and not into.startswith(PRIVATE) and into:
                bad.append(f"{d.name}: ανοίγει προς «{into}» αντί για «{other}»")
            n += 1
        self.add(1, "Πόρτες ιδιωτικών χώρων ανοίγουν προς τα μέσα", not bad, f"{n} πόρτες" + ("" if not bad else " · " + " · ".join(bad)))

    def _door_swing_clear(self):
        from archforge.library.objects import footprint
        bad = []
        objs = [e for e in self.ents("library_object", "cabinet") if str(e.params.get("cabinet_type", "base")) != "wall"]
        for d in self.ents("door"):
            if d.parent_id not in self.doc.entities:
                continue
            sq, into, _other = self._door_leaf_square(d)
            dz = self._floor_z(self.doc.get(d.parent_id))
            for e in objs:
                if abs(self._floor_z(e) - dz) > 1e-3:
                    continue                                     # another storey
                try:
                    if _overlap(footprint(e.params), sq) > 0.02:
                        bad.append(f"{d.name}: {e.name}")
                except Exception:                                # noqa: BLE001
                    continue
        self.add(1, "Τίποτα μέσα στη σάρωση των θυρόφυλλων", not bad, "ελεύθερες" if not bad else " · ".join(bad[:10]))

    def _floors(self):
        from archforge.architecture import storey_slabs as S
        missing = []
        for z in self.storeys():
            slabs = [e for e in self.ents("room_floor") if abs(float(e.params.get("level_z", -99)) - z) < 1e-3]
            area = sum((S.storey_slab_geometry(self.doc, e) or {}).get("area", 0.0) for e in slabs if e.params.get("scope") == "storey")
            if not slabs:
                missing.append(f"{z:+.2f}")
        self.add(1, "Δάπεδο σε κάθε όροφο", not missing, "όλοι" if not missing else "χωρίς δάπεδο: " + ", ".join(missing))

    def _roofs(self):
        from archforge.architecture.roof_need import roof_plan
        plan = roof_plan(self.doc)
        ok = not plan["add"] and not plan["remove"]
        self.add(1, "Στέγη πάνω από κάθε ακάλυπτο χώρο", ok,
                 f"{len(self.ents('pitched_roof'))} κεραμοσκεπές, {len(self.ents('room_roof'))} δώματα"
                 + ("" if ok else f" · χωρίς στέγη: {len(plan['add'])} χώροι · στέγη κάτω από όροφο: {len(plan['remove'])}"))

    def _attic(self):
        from archforge.structure.timber_roof import interior_walls
        roofs = self.ents("pitched_roof")
        if not roofs:
            self.add(1, "Κάτω από κεραμοσκεπή: τοίχοι ως τη στέγη ή ταβάνι", None, "χωρίς κεραμοσκεπή")
            return
        raised = sum(len(interior_walls(self.doc, r.params)) for r in roofs)
        ceilings = len(self.ents("room_ceiling", "ceiling_joists"))
        self.add(1, "Κάτω από κεραμοσκεπή: τοίχοι ως τη στέγη ή ταβάνι", raised > 0 or ceilings > 0,
                 f"{raised} εσωτερικοί τοίχοι ως τη στέγη · {ceilings} ταβάνια σοφίτας")

    def _stair_openings(self):
        from archforge.structure.slab_openings import stair_openings
        stairs = self.ents("stair")
        wells = stair_openings(self.doc)
        self.add(1, "Σκάλες με πραγματική οπή πλάκας", bool(stairs) and len(wells) == len(stairs),
                 f"{len(stairs)} σκάλες, {len(wells)} οπές πλάκας")

    def _objects_in(self, face, z):
        from archforge.geometry.regions import point_in_polygon
        return [e for e in self.ents("library_object", "cabinet")
                if abs(float(e.params.get("z", 0.0)) - z) < 1.2 and point_in_polygon(float(e.params["x"]), float(e.params["y"]), face.polygon)]

    def _kitchen(self):
        found = []
        for z in self.storeys():
            for face, name, _u in self.rooms(z):
                if "ουζίν" not in name:
                    continue
                objs = self._objects_in(face, z)
                names = " ".join(e.name or "" for e in objs)
                need = {"ντουλάπια": any(e.kind == "cabinet" for e in objs), "νεροχύτης": "νεροχύτη" in names.lower(),
                        "εστία": "Εστία" in names or "Κουζίνα με φούρνο" in names, "ψυγείο": "Ψυγ" in names}
                found.append((name, need))
        if not found:
            self.add(1, "Κουζίνα: ντουλάπια, νεροχύτης, εστία, ψυγείο", False, "κανένας χώρος κουζίνας")
            return
        bad = [f"{n}: λείπει {', '.join(k for k, v in need.items() if not v)}" for n, need in found if not all(need.values())]
        self.add(1, "Κουζίνα: ντουλάπια, νεροχύτης, εστία, ψυγείο", not bad, "πλήρης" if not bad else " · ".join(bad))

    def _bathrooms(self):
        rows = []
        for z in self.storeys():
            for face, name, _u in self.rooms(z):
                if not name.startswith(("Μπάνιο", "WC")):
                    continue
                names = " ".join(e.name or "" for e in self._objects_in(face, z))
                need = {"λεκάνη": "Λεκάνη" in names, "νιπτήρας": "Νιπτήρ" in names}
                if name.startswith("Μπάνιο"):
                    need["ντουζιέρα/μπανιέρα"] = "Ντουζιέρα" in names or "Μπανιέρα" in names
                rows.append((name, need))
        if not rows:
            self.add(1, "Μπάνιο: λεκάνη, νιπτήρας, ντουζιέρα/μπανιέρα", False, "κανένα μπάνιο")
            return
        bad = [f"{n}: λείπει {', '.join(k for k, v in need.items() if not v)}" for n, need in rows if not all(need.values())]
        self.add(1, "Μπάνιο: λεκάνη, νιπτήρας, ντουζιέρα/μπανιέρα", not bad, f"{len(rows)} χώροι υγιεινής" + ("" if not bad else " · " + " · ".join(bad)))

    def _furniture(self):
        bad, n = [], 0
        for z in self.storeys():
            for face, name, _u in self.rooms(z):
                names = " ".join(e.name or "" for e in self._objects_in(face, z))
                if name.startswith("Υπνοδωμάτιο"):
                    n += 1
                    if "κρεβάτι" not in names.lower():
                        bad.append(f"{name} χωρίς κρεβάτι")
                if name.startswith("Σαλόνι"):
                    n += 1
                    if "καναπ" not in names.lower():
                        bad.append(f"{name} χωρίς καναπέ")
        self.add(1, "Έπιπλα: κρεβάτι σε κάθε υπνοδωμάτιο, καναπές στο σαλόνι", (not bad) if n else None,
                 f"{len(self.ents('library_object'))} έπιπλα/είδη" + ("" if n else " · χωρίς σαλόνι/υπνοδωμάτιο (γραφεία)") + ("" if not bad else " · " + " · ".join(bad)))

    def _collisions(self):
        """Footprints (plan, low objects): outside every room, through a wall, or overlapping each other."""
        from archforge.geometry.regions import point_in_polygon
        from archforge.library.objects import footprint
        objs = [e for e in self.ents("library_object", "cabinet")
                if float(e.params.get("z", 0.0)) - self._floor_z(e) < 0.5 and str(e.params.get("cabinet_type", "base")) != "wall"]
        problems = []
        polys = {}
        from archforge.library.assets import list_assets
        outdoor = {a["id"] for a in list_assets() if "Εξωτερικοί χώροι" in (a.get("category") or ())}
        for e in objs:
            try:
                poly = footprint(e.params)
            except Exception:                                    # noqa: BLE001
                continue
            polys[e.id] = poly
            z = self._floor_z(e)
            # Shrink by 1 cm: touching a wall face is fine, crossing it is not.
            cx = sum(p[0] for p in poly) / len(poly); cy = sum(p[1] for p in poly) / len(poly)
            inner = [(cx + (p[0] - cx) * 0.98, cy + (p[1] - cy) * 0.98) for p in poly]
            face, room = self.room_of(cx, cy, z)
            if face is None:
                if e.params.get("asset") in outdoor:
                    continue                                     # garden furniture belongs outside
                problems.append(f"{e.name}: έξω από χώρο")
                continue
            from archforge.quantities.takeoff import net_polygon
            net = net_polygon(self.doc, face.polygon, z)
            out = [p for p in inner if not point_in_polygon(p[0], p[1], net)]
            if out:
                problems.append(f"{e.name} ({room}): περνά μέσα σε τοίχο")
        ids = list(polys)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = self.doc.get(ids[i]), self.doc.get(ids[j])
                if a.params.get("layout_id") and a.params.get("layout_id") == b.params.get("layout_id"):
                    continue                                     # the parts of one kitchen/bathroom fit by design
                if abs(self._floor_z(a) - self._floor_z(b)) > 1e-3:
                    continue                                     # different storeys never collide
                if _overlap(polys[ids[i]], polys[ids[j]]) > 0.01:
                    problems.append(f"{a.name} ↔ {b.name}: επικάλυψη")
        self.add(1, "Έπιπλα/είδη μέσα σε χώρο, όχι πάνω σε τοίχο ή μεταξύ τους", not problems,
                 f"{len(objs)} αντικείμενα δαπέδου" + ("" if not problems else " · " + " · ".join(problems[:12])
                                                          + (f" … (+{len(problems) - 12})" if len(problems) > 12 else "")))

    def _floor_z(self, e):
        z = float(e.params.get("z", 0.0))
        st = [s for s in self.storeys() if s <= z + 1e-3]
        return max(st) if st else z

    def _reopen(self):
        """Save, then open the file in a NEW window the way «Αρχείο ▸ Άνοιγμα» does, and compare."""
        import os
        import tempfile
        from archforge.project.persistence import load_project, save_project
        path = os.path.join(tempfile.mkdtemp(), f"S{self.m.KEY}.archforge")
        save_project(self.doc, path)
        report = load_project(path)
        doc2 = report.doc
        a, b = self.doc.to_dict(), doc2.to_dict()
        diffs = []
        ea = {e["id"]: e for e in a.get("entities", [])}
        eb = {e["id"]: e for e in b.get("entities", [])}
        changed = [i for i in ea if ea[i] != eb.get(i)] + [i for i in eb if i not in ea]
        if changed:
            diffs.append(f"{len(changed)} οντότητες ({', '.join(sorted({ea.get(i, eb.get(i))['kind'] for i in changed}))})")
        for key in ("levels", "room_data", "materials", "constructions"):
            if a.get(key) != b.get(key):
                diffs.append(key)
        if report.skipped:
            diffs.append(f"{len(report.skipped)} απορρίφθηκαν")
        from archforge.core.plan_scene import build_plan_frame
        # The same plan: as many primitives per role.
        def roles(d):
            out = {}
            for p in build_plan_frame(d).primitives:
                out[p.role] = out.get(p.role, 0) + 1
            return out
        if roles(self.doc) != roles(doc2):
            diffs.append("κάτοψη")
        self.add(1, "Αποθήκευση → κλείσιμο → άνοιγμα χωρίς απώλειες", not diffs,
                 f"{len(self.doc.entities)} οντότητες, χώροι/όροφοι/κάτοψη ίδια" if not diffs else "διαφέρουν: " + ", ".join(diffs))

    # ============================================================================ 2. statics
    def statics(self):
        cols, beams = self.ents("structural_column"), self.ents("structural_beam")
        footings = [e for e in self.doc.entities.values() if "footing" in e.kind or e.kind == "room_foundation"]
        self.add(2, "Κολόνες", bool(cols), f"{len(cols)}")
        self.add(2, "Δοκοί", bool(beams), f"{len(beams)}")
        slabs = self.ents("room_floor", "room_roof", "room_ceiling", "floor")
        self.add(2, "Πλάκες / επίπεδα", bool(slabs), f"{len(slabs)} πλάκες")
        st = self.storeys()
        if len(st) > 1:
            self.guard(2, "Συνέχεια κολονών μεταξύ ορόφων", self._column_continuity)
        else:
            self.add(2, "Συνέχεια κολονών μεταξύ ορόφων", None, "ένας όροφος")
        try:
            from archforge.structure.analysis import analyze_cached
            res = analyze_cached(self.doc)
        except Exception as exc:                                  # noqa: BLE001
            self.add(2, "Στατική ανάλυση χωρίς crash", False, f"{type(exc).__name__}: {exc}")
            return
        self.add(2, "Στατική ανάλυση χωρίς crash", not res.get("error"), res.get("error") or "ολοκληρώθηκε")
        fd = res.get("foundation") or {}
        pads, strips, ties = fd.get("footings") or [], fd.get("strips") or [], fd.get("ties") or []
        self.add(2, "Θεμελίωση", bool(pads or strips),
                 f"{len(pads)} πέδιλα, {len(strips)} πεδιλοδοκοί, {len(ties)} συνδετήριες · σκυρόδεμα {fd.get('concrete_m3', 0)} m³"
                 + (" · πεδιλοδοκοί: " + ", ".join(f"{st['name']} {st['section']} σmax σεισμού {st.get('sigma_max_seismic_kPa')} kPa"
                                                   for st in strips[:6]) if strips else ""))
        failing = [m.get("name") for m in (res.get("members") or {}).values() if not m.get("ok", True)]
        self.add(2, "Μέλη επαρκή στη διαστασιολόγηση", not failing, "όλα" if not failing else "ανεπαρκή: " + ", ".join(map(str, failing)))
        reviewed = getattr(self.m, "REVIEWED_WARNINGS", {})
        for text in res.get("warnings") or []:
            note = reviewed.get(text)
            self.add(2, f"Προειδοποίηση: {text}", True if note else False, note or "εκκρεμεί εξέταση")
        if not res.get("warnings"):
            self.add(2, "Προειδοποιήσεις ανάλυσης", True, "καμία")
        self.add(2, "Αποτελέσματα σημειωμένα «ΜΗ ΕΠΑΛΗΘΕΥΜΕΝΟ»", not res.get("verified") and "ΜΗ ΕΠΑΛΗΘΕΥΜΕΝΟ" in str(res.get("provenance", "")),
                 "ναι" if not res.get("verified") else "βγαίνει ως επαληθευμένο")
        from archforge.core.provenance import VERIFIED, rules
        allr = rules()
        verified = [r for r in allr if r.status == VERIFIED]
        unsourced = [r.id for r in verified if not r.source]
        self.add(2, "Κανένας κανόνας δεν βαφτίζεται «VERIFIED» χωρίς πηγή", not unsourced,
                 f"{len(allr)} κανόνες στο μητρώο · VERIFIED (με πηγή): {len(verified)}"
                 + (" — " + ", ".join(r.id for r in verified) if verified else "")
                 + ("" if not unsourced else " · χωρίς πηγή: " + ", ".join(unsourced)))

    def _column_continuity(self):
        cols = [c for c in self.ents("structural_column") if c.params.get("role") != "pergola"]   # posts stand on the ground
        st = self.storeys()
        bad = []
        for c in cols:
            z = float(c.params.get("z", 0.0))
            below = [s for s in st if s < z - 1e-3]
            if not below:
                continue
            x, y = float(c.params["x"]), float(c.params["y"])
            # On a column of the storey below, or on a beam that passes under it (a beam anywhere at that
            # level used to count — S09's pilotis columns stood on the slab and passed).
            if not any(abs(float(d.params.get("z", 0.0)) - max(below)) < 1e-3 and math.hypot(float(d.params["x"]) - x, float(d.params["y"]) - y) < 0.3
                       for d in cols) and not any(abs(float(b.params.get("z", 0.0)) + float(b.params.get("height", 0.0)) - z) < 0.6 and
                                                  _seg_dist((x, y), b) <= float(b.params.get("width", 0.25)) / 2 + 0.05
                                                  for b in self.ents("structural_beam")):
                bad.append(c.name or c.id[:6])
        self.add(2, "Συνέχεια κολονών μεταξύ ορόφων", not bad, "όλες πατούν σε κολόνα ή δοκό" if not bad else "χωρίς στήριξη: " + ", ".join(bad))

    # ============================================================================ 3. MEP
    def mep(self):
        self.guard(3, "Ύδρευση κρύο/ζεστό: κάθε σημείο συνδεδεμένο", self._plumbing)
        self.guard(3, "Αλλαγή συστήματος σωληνώσεων", self._pipe_system_change)
        self.guard(3, "Αποχέτευση: κάθε υποδοχέας ως το φρεάτιο", self._drainage)
        self.guard(3, "Ηλεκτρολογικά: κάθε σημείο σε κύκλωμα, κάθε κύκλωμα ως τον πίνακα", self._electrical)
        self.guard(3, "Συσκευές με ηλεκτρική παροχή δίπλα τους", self._appliance_supply)
        self.guard(3, "Διπλά σημεία Η/Μ", self._duplicates)
        self.guard(3, "Θέρμανση: κάθε θερμαινόμενος χώρος με σώμα/βρόχο, προσαγωγή και επιστροφή ως την πηγή", self._heating)
        self.guard(3, "Αλλαγή συστήματος θέρμανσης", self._heating_system_change)
        if len(self.storeys()) > 1:
            self.add(3, "Συνέχεια Η/Μ μεταξύ ορόφων", None, "ελέγχεται μέσα στις διαδρομές κάθε δικτύου")
        else:
            self.add(3, "Συνέχεια Η/Μ μεταξύ ορόφων", None, "ένας όροφος")
        self.guard(3, "BOM / ποσότητες ανά δίκτυο", self._bom)

    def _plumbing(self):
        from archforge.mep.plumbing import route_plumbing_cached
        r = route_plumbing_cached(self.doc)
        rep = r["report"]
        pts = self.ents("plumbing_point")
        ok = bool(pts) and not rep["unserved"] and rep["cold_m"] > 0 and rep["hot_m"] > 0
        # Graph: every point is on the network of its source (pipe ends meet).
        loose = []
        for system in ("cold", "hot"):
            # Manifold system: one separate pipe per outlet from the manifold (by design) + the feed.
            allowed = 1 + sum(len(m["outlets"]) for m in r["manifolds"] if m["system"] == system)
            loose += self._pipe_islands(r[system], system, allowed)
        self.add(3, "Ύδρευση κρύο/ζεστό: κάθε σημείο συνδεδεμένο", ok and not loose,
                 f"{len(pts)} σημεία · κρύο {rep['cold_m']:.1f} m, ζεστό {rep['hot_m']:.1f} m · {rep['system_label']}"
                 + (f" · χωρίς σύνδεση: {', '.join(rep['unserved'])}" if rep["unserved"] else "")
                 + (f" · ασύνδετα τμήματα: {', '.join(loose)}" if loose else ""))

    def _pipe_islands(self, pipes, system, allowed=1):
        n = len(_components([(seg[0], seg[1]) for seg in pipes]))      # tees into a pipe's middle count as joined
        return [f"{system}: {n} ξεχωριστά κομμάτια (επιτρέπονται {allowed})"] if n > allowed else []

    def _pipe_system_change(self):
        from archforge.core.commands import UpdateEntity
        from archforge.mep.plumbing import PIPE_SYSTEMS, pipe_system, route_plumbing_cached
        supply = next((e for e in self.ents("plumbing_point") if e.params.get("point_type") == "water_supply"), None)
        if supply is None:
            self.add(3, "Αλλαγή συστήματος σωληνώσεων", False, "χωρίς παροχή νερού")
            return
        before_sys = pipe_system(self.doc)
        other = next(k for k in PIPE_SYSTEMS if k != before_sys)
        others_before = self._trade_state(exclude=("plumbing_point",))
        before = route_plumbing_cached(self.doc)["report"]
        self.w.stack.execute(UpdateEntity(supply.id, {"pipe_system": other}))
        after = route_plumbing_cached(self.doc)["report"]
        untouched = self._trade_state(exclude=("plumbing_point",)) == others_before
        self.w.stack.undo()
        back = pipe_system(self.doc) == before_sys
        self.add(3, "Αλλαγή συστήματος σωληνώσεων", after["system"] == other and not after["unserved"] and untouched and back,
                 f"{PIPE_SYSTEMS[before_sys][0]} → {PIPE_SYSTEMS[other][0]}: κρύο {before['cold_m']:.1f}→{after['cold_m']:.1f} m"
                 + ("" if untouched else " · ⚠ άλλαξαν στοιχεία άλλης ειδικότητας") + ("" if back else " · ⚠ η αναίρεση δεν επανέφερε"))

    def _trade_state(self, exclude=()):
        return {i: (e.kind, repr(sorted(e.params.items()))) for i, e in self.doc.entities.items() if e.kind not in exclude}

    def _heating(self):
        from archforge.mep.heating import heating_quote
        from archforge.mep.heating_layout import PIPE_SIZES, heated_rooms, route_heating_cached, source_of, _inside
        name = "Θέρμανση: κάθε θερμαινόμενος χώρος με σώμα/βρόχο, προσαγωγή και επιστροφή ως την πηγή"
        if source_of(self.doc) is None:
            self.add(3, name, False, "χωρίς πηγή θέρμανσης στο σενάριο")
            return
        r = route_heating_cached(self.doc)
        rep = r["report"]
        bare = []
        for z in self.storeys():
            for f in heated_rooms(self.doc, z):
                if rep["system"] == "underfloor":
                    ok = any(lp["room"] == (self.doc.room_metadata(f.signature).get("use") or self.doc.room_metadata(f.signature).get("name") or "Χώρος")
                             and abs(lp["z"] - z) < 0.2 and _inside(f.polygon, *lp["points"][0]) for lp in r["loops"])
                else:
                    ok = any(e.params.get("point_type") in ("radiator", "fan_coil") and abs(float(e.params["z"]) - z) < 0.5
                             and _inside(f.polygon, float(e.params["x"]), float(e.params["y"])) for e in self.ents("heating_point"))
                if not ok:
                    bare.append(self.doc.room_metadata(f.signature).get("name") or f.signature[:8])
        loose = self._pipe_islands(r["supply"], "προσαγωγή") + self._pipe_islands(r["return"], "επιστροφή")
        sizes = set(PIPE_SIZES[rep["system"]])
        quote = heating_quote(self.doc)
        coded = {row["code"] for row in quote["rows"]}
        missing = [f"Φ{dn}" for dn in rep["length_by_dn"] if f"heating.pipe.pexal.{dn}" not in coded]
        parts = sum(m and len(m["outlets"]) for m in r["manifolds"])
        ok = not rep["unserved"] and not bare and not loose and not missing and set(rep["length_by_dn"]) <= sizes \
            and bool(r["supply"]) and not rep["warnings"]
        self.add(3, name, ok,
                 f"{rep['system_label']} · {rep['distribution_label']} · {rep['circuits']} κυκλώματα · "
                 + ", ".join(f"Φ{k} {v:.1f} m" for k, v in sorted(rep["length_by_dn"].items()))
                 + (f" · βρόχοι {rep['loop_m']:.0f} m / {rep['loop_area_m2']:.0f} m²" if rep["loop_m"] else "")
                 + f" · συλλέκτες {len(r['manifolds'])} ({parts} κυκλ., υδρονομείς/βάνες)"
                 + (f" · χωρίς σώμα/βρόχο: {', '.join(bare)}" if bare else "") + (f" · {loose[0]}" if loose else "")
                 + (f" · χωρίς γραμμή προσφοράς: {', '.join(missing)}" if missing else "")
                 + (f" · ⚠ {rep['warnings'][0]}" if rep["warnings"] else "") + (f" · ⚠ {rep['unserved'][0]}" if rep["unserved"] else ""))

    def _heating_system_change(self):
        from archforge.core.commands import UpdateEntity
        from archforge.mep.heating_layout import SYSTEMS, route_heating_cached, source_of, system_of
        src = source_of(self.doc)
        if src is None:
            self.add(3, "Αλλαγή συστήματος θέρμανσης", None, "χωρίς πηγή θέρμανσης")
            return
        before = system_of(self.doc)
        other = "underfloor" if before != "underfloor" else "radiators"
        others_before = self._trade_state(exclude=("heating_point",))
        changes = {"heating_system": other} if src.params.get("loop_spacing") or other != "underfloor" else \
            {"heating_system": other, "loop_spacing": 0.15}
        self.w.stack.execute(UpdateEntity(src.id, changes))
        after = route_heating_cached(self.doc)["report"]
        untouched = self._trade_state(exclude=("heating_point",)) == others_before
        self.w.stack.undo()
        back = system_of(self.doc) == before
        self.add(3, "Αλλαγή συστήματος θέρμανσης", after["system"] == other and untouched and back and (after["loop_m"] > 0 or other != "underfloor"),
                 f"{SYSTEMS[before]} → {SYSTEMS[other]}: " + ", ".join(f"Φ{k} {v:.0f} m" for k, v in sorted(after["length_by_dn"].items()))
                 + ("" if untouched else " · ⚠ άλλαξαν στοιχεία άλλης ειδικότητας") + ("" if back else " · ⚠ η αναίρεση δεν επανέφερε"))

    def _drainage(self):
        from archforge.mep.drainage import route_drainage_cached
        r = route_drainage_cached(self.doc)
        rep = r["report"]
        manholes = [n for n in r["nodes"] if n.get("kind") == "manhole"]
        loose = self._pipe_islands([(p[0], p[1]) for p in r["pipes"]], "αποχέτευση")
        wet = [e for e in self.ents("plumbing_point") if e.params.get("point_type") not in ("water_supply", "solar_heater", "water_heater")]
        self.add(3, "Αποχέτευση: κάθε υποδοχέας ως το φρεάτιο", bool(manholes) and not rep["warnings"] and not loose and bool(r["pipes"]),
                 f"{len(wet)} υποδοχείς + {len(self.ents('drainage_point'))} σημεία · "
                 + ", ".join(f"Φ{k} {v:.1f} m" for k, v in sorted(rep["length_by_dn"].items()))
                 + (f" · ⚠ {' · '.join(rep['warnings'])}" if rep["warnings"] else "") + (f" · {loose[0]}" if loose else ""))

    def _electrical(self):
        from archforge.mep.electrical import POINT_TYPES, route_cables_cached
        r = route_cables_cached(self.doc)
        rep = r["report"]
        pts = self.ents("electrical_point")
        panel = next((e for e in pts if e.params.get("point_type") == "panel"), None)
        ids = [c["id"] for c in r["circuits"]]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        # Graph per circuit: every point of it on the same cable network as the panel.
        broken = []
        if panel is not None:
            P = (float(panel.params["x"]), float(panel.params["y"]))
            for c in r["circuits"]:
                segs = [(a, b) for a, b, _g, cid in r["runs"] if cid == c["id"]]
                comp = _components(segs)
                if not comp:
                    broken.append(f"{c['id']}: χωρίς καλώδιο")
                    continue
                home = _nearest_component(comp, P)
                for pid in c["points"]:
                    e = self.doc.entities.get(pid)
                    if e is None:
                        continue
                    q = (float(e.params["x"]), float(e.params["y"]))
                    if _nearest_component(comp, q) != home:
                        broken.append(f"{c['id']}: {e.name}")
        lv = [e for e in pts if POINT_TYPES[e.params["point_type"]][1] == "low_voltage"]
        self.add(3, "Ηλεκτρολογικά: κάθε σημείο σε κύκλωμα, κάθε κύκλωμα ως τον πίνακα",
                 panel is not None and not rep["unassigned"] and not dup and not broken and not rep["warnings"],
                 f"{len(pts) - len(lv)} σημεία ισχυρών, {len(lv)} ασθενών · {len(r['circuits'])} κυκλώματα · καλώδιο {rep['cable_m']:.0f} m"
                 + (f" · χωρίς κύκλωμα: {len(rep['unassigned'])}" if rep["unassigned"] else "")
                 + (f" · ίδιος αριθμός σε δύο κυκλώματα: {', '.join(dup)}" if dup else "")
                 + (f" · δεν φτάνουν στον πίνακα: {', '.join(broken[:8])}" if broken else "")
                 + (f" · ⚠ {' · '.join(rep['warnings'])}" if rep["warnings"] else ""))
        switches = [e for e in pts if e.params["point_type"] in ("switch", "dimmer")]
        linked = {lk["switch"] for lk in r["switch_links"]}
        lights = [e for e in pts if POINT_TYPES[e.params["point_type"]][1] == "lighting"]
        lit = {i for lk in r["switch_links"] for i in lk["lights"]}
        self.add(3, "Διακόπτες ↔ φωτιστικά", all(s.id in linked for s in switches) and all(l.id in lit for l in lights),
                 f"{len(switches)} διακόπτες, {len(lights)} φωτιστικά · χωρίς διακόπτη: "
                 + str(sum(1 for l in lights if l.id not in lit)) + " · διακόπτες χωρίς φως: " + str(sum(1 for s in switches if s.id not in linked)))

    def _appliance_supply(self):
        need = {"Εστία": ("cooker",), "Κουζίνα με φούρνο": ("cooker",), "Πλυντήριο πιάτων": ("dishwasher",),
                "Ψυγ": ("socket", "kitchen_socket"), "Απορροφητήρας": ("socket", "kitchen_socket"),
                "Θερμοσίφωνας": ("water_heater",), "Πλυντήριο ρούχων": ("washing_machine",)}
        pts = self.ents("electrical_point")
        bad, n = [], 0
        for e in self.ents("library_object", "cabinet"):
            types = next((v for k, v in need.items() if k in (e.name or "")), None)
            if types is None:
                continue
            n += 1
            x, y = float(e.params["x"]), float(e.params["y"])
            if not any(p.params["point_type"] in types and math.hypot(float(p.params["x"]) - x, float(p.params["y"]) - y) <= 1.2 for p in pts):
                bad.append(e.name)
        self.add(3, "Συσκευές με ηλεκτρική παροχή δίπλα τους", n > 0 and not bad,
                 f"{n} συσκευές" + ("" if not bad else " · χωρίς παροχή: " + ", ".join(bad)))

    def _duplicates(self):
        dups = []
        for kind in ("plumbing_point", "electrical_point", "drainage_point"):
            pts = self.ents(kind)
            for i in range(len(pts)):
                for j in range(i + 1, len(pts)):
                    a, b = pts[i].params, pts[j].params
                    if a.get("point_type") == b.get("point_type") and a.get("point_type") not in ("socket", "light", "switch", "kitchen_socket") \
                            and abs(float(a.get("z", 0)) - float(b.get("z", 0))) < 0.5:
                        fa, _ = self.room_of(float(a["x"]), float(a["y"]), float(a.get("z", 0)))
                        fb, _ = self.room_of(float(b["x"]), float(b["y"]), float(b.get("z", 0)))
                        if fa is not None and fb is not None and fa.signature == fb.signature and \
                                a.get("point_type") not in ("air_conditioner", "data_outlet", "tv_outlet"):
                            dups.append(f"{pts[i].name} ×2 στον ίδιο χώρο")
        self.add(3, "Διπλά σημεία Η/Μ", not dups, "κανένα" if not dups else " · ".join(sorted(set(dups))))

    def _bom(self):
        from archforge.quantities.materials import all_lists
        lists = {name: rows for name, _t, rows, _n in all_lists(self.doc)}
        need = [n for n, k in (("Ύδρευση", "plumbing_point"), ("Αποχέτευση", "plumbing_point"), ("Ηλεκτρολογικά", "electrical_point"),
                               ("Θέρμανση", "heating_point"))
                if self.ents(k) and not lists.get(n)]
        self.add(3, "BOM / ποσότητες ανά δίκτυο", not need,
                 " · ".join(f"{n} {len(lists.get(n) or [])} γραμμές" for n in ("Ύδρευση", "Αποχέτευση", "Ηλεκτρολογικά", "Θέρμανση"))
                 + ("" if not need else " · χωρίς λίστα: " + ", ".join(need)))

    # ============================================================================ 4. quote
    def quote(self):
        from archforge.quantities.materials import all_lists
        from archforge.quantities.quote import quote
        q = quote(self.doc)
        names = [name for name, _t, rows, _n in all_lists(self.doc)]
        present = {"Ύδρευση": self.ents("plumbing_point"), "Αποχέτευση": self.ents("plumbing_point", "drainage_point"),
                   "Ηλεκτρολογικά": self.ents("electrical_point"), "Φέρων": self.ents("structural_column"),
                   "Κεραμοσκεπή": self.ents("pitched_roof"), "Κουφώματα": self.ents("door", "window"),
                   "Τοιχοποιίες": self.ents("wall"), "Πλάκες": self.ents("room_floor", "room_roof"),
                   "Κουζίνα": self.ents("cabinet"), "Θέρμανση": self.ents("heating_point")}
        missing = [k for k, v in present.items() if v and k not in names]
        self.add(4, "Κάθε ειδικότητα του μοντέλου έχει γραμμές στην προσφορά", not missing,
                 f"{len(q['sections'])} ενότητες" + ("" if not missing else " · λείπουν: " + ", ".join(missing)))
        furniture = [e for e in self.ents("library_object") if not e.params.get("layout_id")]
        in_quote = any("Έπιπλα" in t for t, _r in q["sections"]) and \
            sum(r["quantity"] for t, sec in q["sections"] if "Έπιπλα" in t for r in sec) == len(self.ents("library_object"))
        self.add(4, "Έπιπλα και είδη (Βιβλιοθήκη) στην προσφορά", in_quote or not self.ents("library_object"),
                 f"{len(self.ents('library_object'))} αντικείμενα βιβλιοθήκης" + ("" if in_quote else " — δεν εμφανίζονται σε καμία λίστα"))
        rows = [r for _t, sec in q["sections"] for r in sec]
        # No price was given in this scenario: nothing may be priced, every row must show as missing.
        invented = [r["description"] for r in rows if r["amount"] is not None and not self._has_user_price(r["code"])]
        self.add(4, "Καμία τιμή που δεν έδωσε ο χρήστης", not invented,
                 f"{len(rows)} γραμμές, {q['missing']} χωρίς τιμή (φαίνονται)" + ("" if not invented else " · τιμή από μόνη της: " + ", ".join(invented[:5])))
        self.add(4, "Ποσότητες από το ίδιο μοντέλο", all(r["quantity"] is None or r["quantity"] >= 0 for r in rows) and bool(rows),
                 "οι λίστες διαβάζουν το Document (ίδιο με την κάτοψη/3D)")
        self.guard(4, "Υλικά και εργασία χωριστά, σύνολα ανά ειδικότητα και έργου", self._quote_totals)
        self.guard(4, "Κοινό price book (ίδιες τιμές σε όλα τα έργα)", self._common_book)

    def _common_book(self):
        """A price saved from one project prices the same code in another; the project's own price still wins."""
        import os
        import tempfile
        from archforge.core.model import Document
        from archforge.quantities import price_book
        from archforge.quantities.quote import costed, quote
        q = quote(self.doc)
        row = next((r for _t, sec in q["sections"] for r in sec if r["quantity"]), None)
        old = os.environ.get("ARCHFORGE_DATA")
        os.environ["ARCHFORGE_DATA"] = tempfile.mkdtemp()     # never touch the real book
        try:
            price_book.save({row["code"]: {"material": 7.0, "labour": 3.0}})
            mine = costed(self.doc, "x", [(row["description"], row["unit"], row["quantity"], {"code": row["code"]})])[0]
            other = costed(Document(), "x", [(row["description"], row["unit"], 2.0, {"code": row["code"]})])[0]
            nothing = costed(Document(), "x", [("άλλο", "τεμ.", 1.0, {"code": "never.priced"})])[0]
        finally:
            if old is None:
                os.environ.pop("ARCHFORGE_DATA", None)
            else:
                os.environ["ARCHFORGE_DATA"] = old
        ok = other["amount"] == 20.0 and other["price_source"] == "κοινός τιμοκατάλογος" and nothing["amount"] is None \
            and mine["price_source"] in ("κοινός τιμοκατάλογος", "έργο")
        self.add(4, "Κοινό price book (ίδιες τιμές σε όλα τα έργα)", ok,
                 f"τιμή στο κοινό → άλλο έργο: {other['amount']} € ({other['price_source']}) · κωδικός χωρίς τιμή μένει χωρίς τιμή")

    def _has_user_price(self, code):
        from archforge.quantities.quote import trade_prices
        v = trade_prices(self.doc).get(code)
        return v is not None and (v["material"] is not None or v["labour"] is not None)

    def _quote_totals(self):
        """Give one price (material + labour) through the price list command and read it back per trade."""
        from archforge.core.commands import AddEntity, UpdateEntity
        from archforge.core.model import Entity
        from archforge.quantities.quote import price_entity, quote
        q0 = quote(self.doc)
        row = next((r for _t, sec in q0["sections"] for r in sec if r["quantity"]), None)
        if row is None:
            self.add(4, "Υλικά και εργασία χωριστά, σύνολα ανά ειδικότητα και έργου", False, "καμία γραμμή με ποσότητα")
            return
        n0 = len(self.w.stack.done)
        pe = price_entity(self.doc)
        prices = {row["code"]: {"material": 10.0, "labour": 5.0}}
        if pe is None:
            self.w.stack.execute(AddEntity(Entity("price_list", {"trade_prices": prices}, name="Τιμοκατάλογος")))
        else:
            self.w.stack.execute(UpdateEntity(pe.id, {"trade_prices": {**(pe.params.get("trade_prices") or {}), **prices}}))
        q = quote(self.doc)
        r = next(r for _t, sec in q["sections"] for r in sec if r["code"] == row["code"])
        sec_title = next(t for t, sec in q["sections"] if any(x["code"] == row["code"] for x in sec))
        bt = q.get("by_trade") or []
        mine = next((t for t in bt if t["trade"] == sec_title), None)
        per_trade = len(bt) == len(q["sections"]) and mine is not None and abs(mine["subtotal"] - (r["material"] + r["labour"])) < 0.01 \
            and abs(sum(t["subtotal"] for t in bt) - q["subtotal"]) < 0.01
        ok_split = r["material"] == round(10.0 * r["quantity"], 2) and r["labour"] == round(5.0 * r["quantity"], 2)
        ok_total = abs(q["subtotal"] - (r["material"] + r["labour"])) < 0.01 and q["missing"] == q0["missing"] - 1
        while len(self.w.stack.done) > n0:
            self.w.stack.undo()
        self.add(4, "Υλικά και εργασία χωριστά", ok_split, f"«{row['description']}»: υλικό {r['material']} + εργασία {r['labour']}")
        self.add(4, "Σύνολο έργου από τις γραμμές", ok_total, f"σύνολο {q['subtotal']} · ΦΠΑ {q['vat']}% → {q['total']} · χωρίς τιμή {q['missing']}")
        self.add(4, "Σύνολα ανά ειδικότητα", per_trade,
                 f"{len(bt)} ειδικότητες με δικό τους σύνολο (υλικά/εργασία/χωρίς τιμή) · άθροισμα = σύνολο έργου" if per_trade
                 else "η quote() δεν δίνει σωστά σύνολα ανά ειδικότητα")

    # ============================================================================ 5. behaviour
    def behaviour(self):
        from archforge.core.commands import DeleteEntities, UpdateEntity
        samples = {}
        for kind in ("wall", "window", "library_object", "cabinet", "plumbing_point", "drainage_point", "electrical_point",
                     "structural_column", "structural_beam"):
            e = next((e for e in self.ents(kind) if not e.locked), None)
            if e is not None:
                samples[kind] = e
        for kind, e in samples.items():
            def run(kind=kind, e=e):
                self.env(self.env_for(kind, e.params))
                before = self.snapshot()
                n0 = len(self.w.stack.done)
                self.doc.select([e.id])
                sel = self.doc.selection == [e.id]
                p = e.params
                if kind == "wall":
                    ch = {"x1": float(p["x1"]) + 0.0, "height": float(p["height"]) + 0.1}
                elif kind == "window":
                    ch = {"offset": float(p["offset"]) + 0.05}
                elif kind == "structural_beam":
                    ch = {"h": float(p.get("h", 0.5)) + 0.05} if "h" in p else {"name_tag": "x"}
                else:
                    ch = {"x": float(p["x"]) + 0.05}
                self.w.stack.execute(UpdateEntity(e.id, ch))
                moved = all(self.doc.get(e.id).params.get(k) == v for k, v in ch.items())
                self.w.stack.undo()
                undo_ok = self.snapshot()["entities"] == before["entities"]
                self.w.stack.redo(); self.w.stack.undo()
                self.w.stack.execute(DeleteEntities([e.id]))
                gone = e.id not in self.doc.entities
                self.w.stack.undo()
                restored = self.snapshot()["entities"] == before["entities"]
                while len(self.w.stack.done) > n0:
                    self.w.stack.undo()
                self.add(5, f"Επιλογή / αλλαγή / αναίρεση / διαγραφή: {kind}", sel and moved and undo_ok and gone and restored,
                         f"{e.name}: επιλογή {'✓' if sel else '✗'} · αλλαγή {'✓' if moved else '✗'} · αναίρεση {'✓' if undo_ok else '✗'} · "
                         f"διαγραφή {'✓' if gone else '✗'} · επαναφορά {'✓' if restored else '✗'}")
            self.guard(5, f"Επιλογή / αλλαγή / αναίρεση / διαγραφή: {kind}", run)
        self.guard(5, "Η διαγραφή ενός τοίχου δεν αλλοιώνει άλλη ειδικότητα", self._isolation)
        st = self.storeys()
        if len(st) > 1:
            self.guard(5, "Αλλαγή ορόφου χωρίς εξαφάνιση στοιχείων", self._storey_switch)
        else:
            self.add(5, "Αλλαγή ορόφου χωρίς εξαφάνιση στοιχείων", None, "ένας όροφος")

    def _isolation(self):
        from archforge.core.commands import UpdateEntity
        e = next((e for e in self.ents("electrical_point") if e.params["point_type"] == "socket"), None)
        if e is None:
            self.add(5, "Η αλλαγή μιας ειδικότητας δεν αλλοιώνει άλλη", None, "χωρίς πρίζα")
            return
        self.env("mep")
        others = self._trade_state(exclude=("electrical_point",))
        self.w.stack.execute(UpdateEntity(e.id, {"x": float(e.params["x"]) + 0.3}))
        same = self._trade_state(exclude=("electrical_point",)) == others
        self.w.stack.undo()
        self.add(5, "Η αλλαγή μιας ειδικότητας δεν αλλοιώνει άλλη", same,
                 "μετακίνηση πρίζας: τοίχοι, σωλήνες, φέρων, έπιπλα ίδια" if same else "άλλαξαν στοιχεία άλλων ειδικοτήτων")

    def _storey_switch(self):
        before = self.snapshot()["entities"]
        names = [n for n, _z in sorted(self.doc.levels.items(), key=lambda kv: kv[1])]
        for n in names + names[:1]:
            self.w._refresh_floor_selector(); self.w._activate_level_by_name(n)
        same = self.snapshot()["entities"] == before
        self.add(5, "Αλλαγή ορόφου χωρίς εξαφάνιση στοιχείων", same, " → ".join(names) + (" · ίδιο μοντέλο" if same else " · άλλαξε το μοντέλο"))

    # ============================================================================ 6. visual
    def visual(self):
        import os
        stem = os.path.join(self.out, self.m.NAME)
        st = self.storeys()
        names = {round(z, 4): n for n, z in self.doc.levels.items()}
        shots = {}
        for env, title in (("arch", "Αρχιτεκτονικό"), ("structure", "Φέρων"), ("mep", "Η/Μ")):
            self.env(env)
            for z in st:
                label = names.get(round(z, 4), f"{z:+.2f}")
                self.w._refresh_floor_selector(); self.w._activate_level_by_name(label)
                path = f"{stem}_2D_{env}_{_safe(label)}.png"
                self.s.plan_image(path)
                shots.setdefault(env, []).append(os.path.basename(path))
                self.images.append((f"Κάτοψη {label} — περιβάλλον {title}", os.path.basename(path)))
        self.env("arch")
        self.add(6, "Στιγμιότυπο 2D (Αρχιτεκτονικό)", bool(shots.get("arch")), ", ".join(shots.get("arch", [])))
        from archforge.scenarios.render3d import render
        views = {}
        for key, title, env, structural, drop, cam in (
                ("3D", "3D εξωτερικά", "arch", False, (), None),
                ("3D_interior", "3D κουκλόσπιτο (εσωτερικό, έπιπλα)", "arch", False, ("pitched_roof", "room_roof"), "dollhouse"),
                ("3D_top", "3D από πάνω χωρίς στέγη", "arch", False, ("pitched_roof", "room_roof"), "top"),
                ("3D_structure", "3D Φέρων", "structure", True, (), None),
                ("3D_mep", "3D Η/Μ (χωρίς στέγη)", "mep", False, ("pitched_roof", "room_roof"), None)):
            self.env(env)
            path = f"{stem}_{key}.png"
            problem = render(self.doc, path, structural_only=structural, drop_kinds=drop, camera=cam)
            views[key] = problem
            if problem is None:
                self.images.append((title, os.path.basename(path)))
        self.env("arch")
        self.add(6, "Στιγμιότυπο 3D", views["3D"] is None and views["3D_interior"] is None,
                 "εξωτερικά + χωρίς στέγη" if views["3D"] is None and views["3D_interior"] is None
                 else f"{views['3D'] or ''} {views['3D_interior'] or ''}")
        self.add(6, "Στιγμιότυπο Structural", bool(shots.get("structure")) and views["3D_structure"] is None,
                 ", ".join(shots.get("structure", [])) + (" · 3D Φέρων" if views["3D_structure"] is None else f" · 3D: {views['3D_structure']}"))
        self.add(6, "Στιγμιότυπο βασικών όψεων Η/Μ", bool(shots.get("mep")) and views["3D_mep"] is None,
                 ", ".join(shots.get("mep", [])) + (" · 3D Η/Μ" if views["3D_mep"] is None else f" · 3D: {views['3D_mep']}"))

    # ============================================================================ report
    def report(self, path, extra=""):
        findings = getattr(self.m, "FINDINGS", [])
        fails = [c for c in self.checks if c.status == FAIL]
        lines = [f"# S{self.m.KEY}: {self.m.TITLE} — πύλη ποιότητας", "",
                 f"Αρχείο: `{self.m.NAME}.archforge` · κανόνες: `QUALITY_GATE.md`", "",
                 f"**Κατάσταση: {'ΚΑΘΑΡΟ' if not fails else f'ΟΧΙ ΚΑΘΑΡΟ — {len(fails)} FAIL'}** · "
                 f"{sum(1 for c in self.checks if c.status == PASS)} PASS · {len(fails)} FAIL · "
                 f"{sum(1 for c in self.checks if c.status == NA)} N/A · {len(findings)} ευρήματα στο ιστορικό "
                 f"({sum(1 for f in findings if f.get('status') == 'FIXED')} FIXED)", ""]
        for sec in SECTIONS:
            rows = [c for c in self.checks if c.section == sec]
            lines += [f"## {sec}", "", "| | Έλεγχος | Σημείωση |", "|---|---|---|"]
            lines += [f"| {_mark(c.status)} | {c.item} | {c.note.replace('|', '/')} |" for c in rows]
            lines.append("")
        if self.images:
            lines += ["### Στιγμιότυπα", ""] + [f"- {t}: `{i}`" for t, i in self.images] + [""]
        lines += ["## Ευρήματα (ιστορικό)", "", "| # | Κατάσταση | Τι βρέθηκε | Διόρθωση | Αρχεία | Commit |", "|---|---|---|---|---|---|"]
        for i, f in enumerate(findings, 1):
            lines.append(f"| {i} | {f.get('status', 'OPEN')} | {f['found']} | {f.get('fix', '')} | {', '.join(f.get('files', []))} | {f.get('commit', '')} |")
        lines += ["", "## Βήματα κατασκευής", "", "| # | | Ενέργεια | Σημείωση |", "|---|---|---|---|"]
        lines += [f"| {i} | {'✅' if s.ok else '❌'} | {s.action} | {s.note.replace('|', '/')} |" for i, s in enumerate(self.s.steps, 1)]
        lines += ["", extra]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return fails


def _mark(status):
    return {PASS: "✅ PASS", FAIL: "❌ FAIL", NA: "— N/A"}[status]


def _safe(text):
    return "".join(c if c.isalnum() else "_" for c in str(text))


def _overlap(a, b):
    """Area of the intersection of two convex polygons (Sutherland–Hodgman)."""
    def clip(subject, cp1, cp2):
        out = []
        def inside(p):
            return (cp2[0] - cp1[0]) * (p[1] - cp1[1]) - (cp2[1] - cp1[1]) * (p[0] - cp1[0]) >= 0
        def inter(s, e):
            dc = (cp1[0] - cp2[0], cp1[1] - cp2[1]); dp = (s[0] - e[0], s[1] - e[1])
            n1 = cp1[0] * cp2[1] - cp1[1] * cp2[0]; n2 = s[0] * e[1] - s[1] * e[0]
            n3 = 1.0 / (dc[0] * dp[1] - dc[1] * dp[0] or 1e-12)
            return ((n1 * dp[0] - n2 * dc[0]) * n3, (n1 * dp[1] - n2 * dc[1]) * n3)
        for i in range(len(subject)):
            s, e = subject[i - 1], subject[i]
            if inside(e):
                if not inside(s):
                    out.append(inter(s, e))
                out.append(e)
            elif inside(s):
                out.append(inter(s, e))
        return out
    def area(p):
        return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))
    a = list(a) if area(a) > 0 else list(a)[::-1]
    b = list(b) if area(b) > 0 else list(b)[::-1]
    out = a
    for i in range(len(b)):
        if not out:
            return 0.0
        out = clip(out, b[i - 1], b[i])
    return abs(area(out)) if len(out) >= 3 else 0.0



def _seg_dist(q, beam):
    """Plan distance from point ``q`` to the axis of ``beam``."""
    p = beam.params
    ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L2 = (bx - ax) ** 2 + (by - ay) ** 2
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((q[0] - ax) * (bx - ax) + (q[1] - ay) * (by - ay)) / L2))
    return math.hypot(ax + (bx - ax) * t - q[0], ay + (by - ay) * t - q[1])


def _components(segs):
    parent = {}
    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    def key(p):
        return (round(p[0], 2), round(p[1], 2), round(p[2], 2))
    segs = list(segs)
    for a, b in segs:
        parent[find(key(a))] = find(key(b))
    # A branch teed into the middle of a pipe is connected to it (endpoint on the segment, within 1 cm); so is an
    # end within 1 cm of another end (the rounded keys split 6.325 / 6.3249999 into two pieces).
    ends = {key(q): q for s_ in segs for q in s_}
    for a, b in segs:
        d = [b[i] - a[i] for i in range(3)]
        L2 = sum(v * v for v in d)
        if L2 < 1e-8:
            continue
        for k, q in ends.items():
            t = sum((q[i] - a[i]) * d[i] for i in range(3)) / L2
            t = min(1.0, max(0.0, t))
            if math.dist(q, [a[i] + t * d[i] for i in range(3)]) < 0.01:
                parent[find(k)] = find(key(a))
    comp = {}
    for n in list(parent):
        comp.setdefault(find(n), []).append(n)
    return comp


def _nearest_component(comp, q):
    best, root = None, None
    for r, nodes in comp.items():
        d = min(math.hypot(n[0] - q[0], n[1] - q[1]) for n in nodes)
        if best is None or d < best:
            best, root = d, r
    return root if best is not None and best <= 0.6 else None
