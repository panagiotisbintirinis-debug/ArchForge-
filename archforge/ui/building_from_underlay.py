"""From the engineer's drawings to a model to work on (owner 22/10: «εισαγωγή δύο-τριών PDF … ένα σχέδιο 3Δ
που να μπορούμε να δουλέψουμε· το terrain, ειδικά εδώ που είναι επικλινές, πρέπει να αποτυπωθεί»).

* «Κτίριο από το υπόβαθρο» (Ιδιότητες υποβάθρου / Τοίχοι & δωμάτια): on the active storey, the plan's walls, its
  doors and windows («w: … | h: …», with «s:» a window) and its room names, then the floor — one undo.
* «Έδαφος από τα υψόμετρα του σχεδίου»: every altitude written on the drawing (+111.80m, 126.00m …, read where it
  is written) is a ground point; ±0,00 = the altitude given (the ground floor's F.L.) — the existing terrain tool.

Another sheet of the same building goes on another storey (Όροφοι), another building on its own storeys; a
masterplan is placed over the buildings with «Ταίριασμα με 2 σημεία» (scale, turn and place at once).
"""
from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

ALTITUDE_MIN = 10.0          # written altitudes (absolute) vs levels relative to a building's ±0,00


def _busy(fn):
    def run(*a, **k):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            return fn(*a, **k)
        finally:
            QApplication.restoreOverrideCursor()
    return run


@_busy
def analyse(window, eid):
    """Walls (with openings' pieces joined), openings, room labels and levels of underlay ``eid``."""
    from archforge.architecture.building_from_drawing import tidy
    from archforge.architecture.walls_from_lines import find_walls
    from archforge.project.drawing_text import model_labels
    from archforge.project.underlay import underlay_model_segments
    p = window.doc.get(eid).params
    segs = underlay_model_segments(p, dark_only=True) or underlay_model_segments(p)
    labels = model_labels(p)
    from archforge.architecture.building_from_drawing import glass_strips
    walls, openings, missing = tidy(find_walls(segs), labels["openings"])
    return {"walls": walls, "openings": openings, "missing": missing, "rooms": labels["rooms"], "levels": labels["levels"],
            "items": underlay_items(p), "glass": glass_strips(underlay_glass(p))}


def glass_walls(window, walls, strips, z):
    """Walls drawn on a glass strip (the drawing's glass blue between two lines), cut where the glass begins and
    ends, each glass piece told by what is beside it along its whole length: next to a named indoor room it is
    glazing — a wall whose length is one fixed pane from the floor; with outdoor ground on both sides (veranda,
    terrace) it is a glass railing (owner 23/10).  The rest of the wall stays a wall with its openings.  Folded
    into the build's undo.  ``(glazed wall ids, railing ids)``."""
    from archforge.architecture.building_from_drawing import glass_spans
    from archforge.architecture.railings import default_params as railing_params
    from archforge.architecture.roof_need import OPEN_AIR_USES
    from archforge.core.commands import AddEntities, DeleteEntities
    from archforge.core.model import Entity
    from archforge.geometry.regions import point_in_polygon
    import math
    doc = window.doc
    if not strips:
        return [], []
    faces = doc.active_room_faces(z=z)

    def indoor(x, y):
        for f in faces:
            if point_in_polygon(x, y, f.polygon):
                meta = doc.room_metadata(f.signature)
                return bool(meta.get("name")) and meta.get("use") not in OPEN_AIR_USES
        return False
    glazed, rails, gone, new = [], [], [], []
    for w in walls:
        if w.id not in doc.entities:
            continue
        p = w.params
        a, b, t = (float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"])), float(p["thickness"])
        L = math.dist(a, b)
        spans = glass_spans(a, b, t, strips) if L >= 0.3 else []
        if not spans:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        at = lambda s_: (a[0] + ux * s_, a[1] + uy * s_)
        hosted = [o for o in doc.entities.values() if o.parent_id == w.id]
        # The pieces along the wall: masonry between the glass spans, the glass spans themselves.
        cuts, pos = [], 0.0
        for s0, s1 in spans:
            if s0 - pos >= 0.05:
                cuts.append((pos, s0, False))
            cuts.append((s0, s1, True))
            pos = s1
        if L - pos >= 0.05:
            cuts.append((pos, L, False))
        gone.append(w.id)
        for s0, s1, glass in cuts:
            piece = dict(p, x1=at(s0)[0], y1=at(s0)[1], x2=at(s1)[0], y2=at(s1)[1])
            if glass:
                side = t / 2 + 0.3
                inside = any(indoor(at(s0 + (s1 - s0) * k / 4)[0] + sgn * -uy * side, at(s0 + (s1 - s0) * k / 4)[1] + sgn * ux * side)
                             for k in range(5) for sgn in (1, -1))
                if not inside:
                    rails.append(Entity("railing", railing_params("glass_channel", [list(at(s0)), list(at(s1))], z=z),
                                        name=f"Γυάλινο κάγκελο {len(rails) + 1}"))
                    continue
                wall = Entity("wall", piece, name=f"{w.name} (τζάμι)")
                new.append(wall)
                new.append(Entity("window", {"offset": (s1 - s0) / 2, "width": round(s1 - s0 - 0.10, 3),
                                             "height": round(float(p["height"]) - 0.05, 3), "sill": 0.0},
                                  parent_id=wall.id, name=f"Υαλοπέτασμα {len(glazed) + 1}"))
                glazed.append(wall.id)
            else:
                wall = Entity("wall", piece, name=w.name)
                new.append(wall)
                for o in hosted:               # its doors / windows stay where the drawing put them
                    off, half = float(o.params.get("offset", 0.0)), float(o.params.get("width", 0.0)) / 2
                    if s0 <= off - half and off + half <= s1:      # whole in this piece (not across the glass)
                        new.append(Entity(o.kind, dict(o.params, offset=off - s0), parent_id=wall.id, name=o.name))
    if gone:
        gone += [o.id for o in doc.entities.values() if o.parent_id in gone]
        window.stack.amend(DeleteEntities(gone))
    if new or rails:
        window.stack.amend(AddEntities(new + rails))
    return glazed, [r.id for r in rails]


def underlay_glass(p):
    """The glass-blue fills of a PDF underlay as model polygons (glass railings, pools)."""
    if p.get("source") != "pdf":
        return []
    from archforge.project.drawing_set import water_fills
    from archforge.project.underlay import to_model
    try:
        return [[to_model(p, x, y) for x, y in poly] for poly in water_fills(p["path"], p.get("page", 0))]
    except Exception as exc:
        from archforge.core.notices import not_computed
        not_computed("pdf.water_fills", "Σχέδιο PDF: δεν διαβάστηκαν τα γαλάζια γεμίσματα (τζάμια, πισίνες)", exc=exc)
        return []


def underlay_items(p):
    """Beds, tables, toilets, baths and kitchen / room-height words of a PDF underlay, in model metres — so a plan
    that writes no room names (OLD VILLA upper floor) gets them here as in a drawing set (drawing_contents.py)."""
    if p.get("source") != "pdf":
        return []
    from archforge.project import drawing_contents as C
    from archforge.project.drawing_text import pdf_texts
    from archforge.project.underlay import to_model
    k = float(p["m_per_unit"])                       # metres per drawing unit (PDF point) at the drawing's scale
    try:
        blocks = [(kind, x / k, y / k) for kind, x, y in C.read_items(p["path"], p.get("page", 0), k)]
        raw = blocks + C.words(pdf_texts(p["path"], p.get("page", 0)))
    except Exception as exc:
        from archforge.core.notices import not_computed
        not_computed("pdf.contents", "Σχέδιο PDF: δεν διαβάστηκαν σύμβολα και λέξεις (έπιπλα, είδη υγιεινής, χώροι) — "
                     "δεν σημαίνει ότι δεν υπάρχουν", exc=exc)
        return []
    return [(kind, *to_model(p, x, y)) for kind, x, y in raw]


def build(window, eid, found=None, ask=True):
    """The storey from the drawing on the active storey: one undoable step.  Returns the summary dict."""
    from archforge.architecture.building_from_drawing import host_of
    from archforge.architecture.storey_slabs import auto_floor_command
    from archforge.core.commands import AddEntities, SetRoomMetadata
    from archforge.core.interaction import next_name
    from archforge.core.model import Entity
    from archforge.geometry.regions import point_in_polygon
    from archforge.project.drawing_text import greek_room
    doc = window.doc
    found = found or analyse(window, eid)
    if not found["walls"]:
        if ask:
            QMessageBox.information(window, "Κτίριο από το υπόβαθρο", "Δεν βρέθηκαν τοίχοι (ζεύγη σκούρων γραμμών) στο σχέδιο.")
        return None
    z = float(doc.work_plane.origin[2])
    above = sorted(float(v) for v in doc.levels.values() if float(v) > z + 1e-6)
    height = (above[0] - z) if above else 3.0
    walls = [Entity("wall", {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1], "z": z, "height": height, "thickness": float(t)},
                    name=next_name(doc, "wall")) for a, b, t in found["walls"]]
    # next_name counts the document: number them ourselves so they stay unique in one batch.
    base = sum(1 for e in doc.entities.values() if e.kind == "wall")
    for k, w in enumerate(walls, 1):
        w.name = f"Τοίχος {base + k}"
    openings, unplaced = [], list(found["missing"])
    taken = {}                                   # wall index → [(from, to)] along it: openings never overlap
    for o in found["openings"]:
        host = host_of(found["walls"], o.centre)
        if host is None:
            unplaced.append(o.label or o); continue
        k, offset = host
        wall = walls[k]
        length = ((wall.params["x2"] - wall.params["x1"]) ** 2 + (wall.params["y2"] - wall.params["y1"]) ** 2) ** 0.5
        if o.sill + o.height > height or offset - o.width / 2 < -1e-6 or offset + o.width / 2 > length + 1e-6:
            unplaced.append(o.label or o); continue
        span = (offset - o.width / 2, offset + o.width / 2)
        if any(span[0] < b - 0.02 and a < span[1] - 0.02 for a, b in taken.get(k, ())):
            if o.label is not None:
                unplaced.append(o.label)
            continue                             # labelled ones come first: an unlabelled gap there is the same opening
        taken.setdefault(k, []).append(span)
        name = {"door": "Πόρτα", "window": "Παράθυρο"}.get(o.kind, "Άνοιγμα") + f" {len(openings) + 1}"
        openings.append(Entity(o.kind, {"offset": offset, "width": o.width, "height": o.height, "sill": o.sill},
                               parent_id=wall.id, name=name))
    window.stack.execute(AddEntities(walls + openings))
    floor = auto_floor_command(doc, z)
    if floor is not None:
        window.stack.amend(floor)
    named = 0
    for r in found["rooms"]:
        face = next((f for f in doc.active_room_faces(z=z) if point_in_polygon(r.x, r.y, f.polygon)), None)
        if face is not None:
            name, use = greek_room(r.name)
            window.stack.amend(SetRoomMetadata(face.signature, {"name": name, "use": use}))
            named += 1
    if found.get("items"):
        # A plan that writes no room names (OLD VILLA upper floor): the rooms by what is drawn in them.
        from archforge.project.drawing_contents import name_rooms
        faces = doc.active_room_faces(z=z)
        for k, label in name_rooms([f.polygon for f in faces], found["items"]).items():
            if doc.room_metadata(faces[k].signature).get("name"):
                continue
            name, use = greek_room(label)
            window.stack.amend(SetRoomMetadata(faces[k].signature, {"name": name, "use": use}))
            named += 1
    glazed, rails = glass_walls(window, walls, found.get("glass", ()), z)
    doc.select([w.id for w in walls if w.id in doc.entities])
    window._redraw_views(all_views=True)
    window._refresh_project_tree()
    window.refresh_inspector()
    fl = Counter(round(l.value, 2) for l in found["levels"] if not l.ceiling and l.value >= ALTITUDE_MIN).most_common(1)
    summary = {"walls": len(walls), "doors": sum(o.kind == "door" for o in openings),
               "windows": sum(o.kind == "window" for o in openings), "unplaced": len(unplaced),
               "rooms": named, "room_labels": len(found["rooms"]), "floor_level": fl[0][0] if fl else None,
               "railings": len(rails), "glazed": len(glazed)}
    text = (f"Τοίχοι: {summary['walls']} · πόρτες: {summary['doors']} · παράθυρα: {summary['windows']}"
            f" · χώροι με όνομα: {named} από {len(found['rooms'])}")
    if unplaced:
        text += f"\nΚουφώματα χωρίς θέση (χωρίς κενό στον τοίχο δίπλα στην ετικέτα): {len(unplaced)} — " + ", ".join(
            f"{u.width:.2f}×{u.height:.2f}".replace(".", ",") for u in unplaced[:8])
    if summary["floor_level"] is not None:
        text += f"\nΤο σχέδιο γράφει στάθμη δαπέδου +{summary['floor_level']:.2f} m [F.L.]".replace(".", ",")
    text += "\n\nΟι τοίχοι είναι επιλεγμένοι: Delete όσους δεν είναι τοίχοι (κράσπεδα, σκαλοπάτια, έπιπλα) · Ctrl+Z όλα."
    window.statusBar().showMessage(text.split("\n")[0] + " — Ctrl+Z αναιρεί", 15000)
    if ask:
        QMessageBox.information(window, "Κτίριο από το υπόβαθρο", text)
    return summary


def ground_points(levels):
    """(x, y, altitude) of the written altitudes (absolute, ≥ 10 m) — not the relative ±0 levels of a building."""
    return [(l.x, l.y, l.value) for l in levels if not l.ceiling and l.value >= ALTITUDE_MIN]


@_busy
def _levels(window, eid):
    from archforge.project.drawing_text import model_labels
    return model_labels(window.doc.get(eid).params)["levels"]


def terrain(window, eid, altitude=None):
    """Terrain from the drawing's altitudes; ±0,00 = ``altitude`` (asked; default the most written floor level)."""
    from archforge.core.commands import AddEntity, UpdateEntity
    from archforge.core.model import Entity
    from archforge.site.survey import terrain_from_survey
    pts = ground_points(_levels(window, eid))
    if len(pts) < 3:
        QMessageBox.information(window, "Έδαφος από το σχέδιο",
                                f"Βρέθηκαν {len(pts)} υψόμετρα (+111.80m κ.λπ.) — χρειάζονται τουλάχιστον 3.")
        return None
    if altitude is None:
        common = Counter(round(z, 2) for _x, _y, z in pts).most_common(1)[0][0]
        altitude, ok = QInputDialog.getDouble(window, "Έδαφος από το σχέδιο",
                                              f"{len(pts)} υψόμετρα από {min(p[2] for p in pts):.2f} έως {max(p[2] for p in pts):.2f} m.\n"
                                              "Ποιο απόλυτο υψόμετρο είναι το ±0,00 του έργου (δάπεδο ισογείου);",
                                              common, -500.0, 9000.0, 2)
        if not ok:
            return None
    params = terrain_from_survey(window.doc, pts, in_place=True, altitude_ref=float(altitude))
    existing = next((e for e in window.doc.entities.values() if e.kind == "terrain"), None)
    if existing is None:
        window.stack.execute(AddEntity(Entity("terrain", params, name="Έδαφος")))
    else:
        window.stack.execute(UpdateEntity(existing.id, params))
    window._redraw_views(all_views=True)
    window._refresh_project_tree()
    window.statusBar().showMessage(f"Έδαφος από {len(pts)} υψόμετρα του σχεδίου · ±0,00 = +{float(altitude):.2f} m"
                                   .replace(".", ",") + " — Ctrl+Z αναιρεί", 12000)
    return params
