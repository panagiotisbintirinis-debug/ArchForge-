"""Project tree derived from the Document: only things that actually exist.

``project_outline(doc)`` returns plain nested nodes so the tree widget, tests
and any other view share one truth:

    {"label": str, "entity_id": str|None, "level": str|None, "children": [...]}

Storeys come from ``doc.levels`` (sorted by elevation), rooms from the room
topology of each storey, and every entity is listed once under its storey and
category.  Empty categories are omitted.
"""
from __future__ import annotations

CATEGORIES = (
    ("Τοίχοι", ("wall",)),
    ("Ανοίγματα", ("door", "window", "opening")),
    ("Σκάλες & ράμπες", ("stair", "ramp")),
    ("Δομικά", ("structural_column", "structural_beam", "structural_support", "structural_load")),
    ("Πλάκες & στέγες", ("floor", "room_floor", "room_ceiling", "room_foundation", "room_roof")),
    ("Ντουλάπια & κουζίνα", ("cabinet", "kitchen_part")),
    ("Έπιπλα", ("library_object", "box")),
    ("Μηχανολογικά", ("mep_terminal", "mechanical_part", "mechanical_joint", "mechanical_mount", "mesh")),
    ("Οργανικά", ("pod", "arboreal_branch", "organic_junction", "organic_opening_patch")),
)
SITE = ("terrain", "plant", "site_path")
KIND_LABELS = {
    "wall": "Τοίχος", "door": "Πόρτα", "window": "Παράθυρο", "opening": "Άνοιγμα", "stair": "Σκάλα",
    "ramp": "Ράμπα", "structural_column": "Κολόνα", "structural_beam": "Δοκός", "floor": "Πλάκα",
    "room_floor": "Δάπεδο", "room_ceiling": "Οροφή", "room_foundation": "Θεμέλιο", "room_roof": "Στέγη",
    "cabinet": "Ντουλάπι", "kitchen_part": "Κομμάτι κουζίνας", "library_object": "Αντικείμενο",
    "box": "Κουτί", "terrain": "Έδαφος", "plant": "Φυτό", "site_path": "Μονοπάτι", "pod": "Pod",
}


def _levels(doc):
    """Storeys as the floor selector shows them (same source of truth)."""
    try:
        from archforge.architecture.stairs import discover_building_levels
        found = [(str(i["name"]), float(i["elevation"])) for i in discover_building_levels(doc)]
    except Exception:
        found = []
    if not found:
        found = [(str(n), float(z)) for n, z in doc.levels.items()]
    return sorted(found, key=lambda t: t[1]) or [("Ground", 0.0)]


def _owner(levels, z, tol=1e-4):
    """Name of the highest storey at or below ``z`` (the lowest storey otherwise)."""
    below = [n for n, lz in levels if lz <= z + tol]
    return below[-1] if below else levels[0][0]


def entity_level(doc, entity, levels=None):
    """Storey name an entity belongs to, or None for site items."""
    levels = levels or _levels(doc)
    p, k = entity.params, entity.kind
    if k in SITE:
        return None
    if k in ("door", "window", "opening") and entity.parent_id in doc.entities:
        return entity_level(doc, doc.get(entity.parent_id), levels)
    names = {n for n, _z in levels}
    if k == "structural_column" and p.get("base_level") in names:
        return str(p["base_level"])
    if k == "structural_beam" and p.get("level") in names:
        return str(p["level"])
    if k == "structural_support" and entity.parent_id in doc.entities:
        return entity_level(doc, doc.get(entity.parent_id), levels)
    for key in ("z", "floor_level", "level_z", "lower_z", "elevation_z"):
        if key in p:
            try:
                return _owner(levels, float(p[key]))
            except (TypeError, ValueError):
                break
    return levels[0][0]


def _label(entity):
    if entity.name:
        return entity.name
    p, k = entity.params, entity.kind
    base = KIND_LABELS.get(k, k)
    if k == "wall":
        import math
        length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
        return f"{base} {length:.2f} m"
    if k in ("cabinet", "library_object", "box") and "width" in p:
        return f"{base} {float(p['width']) * 100:.0f} cm"
    return base


def _natural(text):
    """Sort key so that Κ2 comes before Κ10."""
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text)]


def _node(label, entity_id=None, level=None, children=None):
    return {"label": label, "entity_id": entity_id, "level": level, "children": children or []}


def _group(title, ids, doc, level, labels, extra=""):
    return _node(f"{title} ({len(ids)}){extra}", None, level,
                 [_node(labels.get(i) or _label(doc.get(i)), i, level) for i in ids])


def _categorise(ids, doc):
    """[(category title, ids)] in CATEGORIES order, then the rest."""
    out, listed = [], set()
    for title, kinds in CATEGORIES + (("Υδραυλικά", ("plumbing_point",)), ("Ηλεκτρολογικά", ("electrical_point",)),
                                      ("Εξαερισμοί", ("ventilation_point",)), ("Δοκίδες", ("ceiling_joists",)),
                                      ("Στέγες", ("pitched_roof",)), ("Στοιχεία στατικής", ("structural_design",))):
        group = [i for i in ids if doc.get(i).kind in kinds]
        listed.update(group)
        if group:
            out.append((title, group))
    rest = [i for i in ids if i not in listed]
    if rest:
        out.append(("Άλλα", rest))
    return out


def _labels_from_analysis(doc):
    """Member names (Κ1, Δ1 …) shared with the structural analysis, plus its results when up to date."""
    labels = {}
    if not any(e.kind in ("structural_column", "structural_beam") for e in doc.entities.values()):
        return labels
    from archforge.structure.analysis import fresh_result
    from archforge.structure.analysis.building import read_members
    members, _excluded = read_members(doc)
    result = fresh_result(doc) or {}
    for mid, m in members.items():
        info = result.get("members", {}).get(mid)
        if info:
            bars = info.get("bars") or info.get("bottom")
            extra = f" {bars['n']}Ø{bars['d']}" if bars and m.kind == "column" else ""
            labels[mid] = (f"{info['name']} {info.get('section', '')}{extra} · {min(info.get('utilisation', 0), 9.99):.0%}"
                           + ("" if info.get("ok", True) else " ⚠"))
        else:
            size = m.profile or f"{m.b * 100:.0f}/{m.h * 100:.0f}"
            labels[mid] = f"{m.name} {size}"
    return labels


def _mep_summary(doc):
    """One line per derived network, keyed by kind (no layers: these are the networks themselves)."""
    out = {}
    kinds = {e.kind for e in doc.entities.values()}
    if "plumbing_point" in kinds:
        from archforge.mep.plumbing import route_plumbing_cached
        r = route_plumbing_cached(doc)["report"]
        out["plumbing_point"] = f" · κρύο {r['cold_m']:.1f} m, ζεστό {r['hot_m']:.1f} m"
    if "electrical_point" in kinds:
        from archforge.mep.electrical import route_cables_cached
        out["electrical_point"] = f" · {len(route_cables_cached(doc)['circuits'])} κυκλώματα"
    if "ventilation_point" in kinds:
        from archforge.mep.ventilation import route_ventilation_cached
        out["ventilation_point"] = f" · αεραγωγοί {route_ventilation_cached(doc)['report']['duct_m']:.1f} m"
    return out


def project_outline(doc, title="Έργο"):
    """The construction tree: storeys → rooms (with what is in them), walls (with their openings),
    load-bearing structure, then everything else — every entity exactly once, all from one reading."""
    from archforge.assistant.understanding import USE_LABELS, read_drawing

    import math
    reading = read_drawing(doc)
    labels = _labels_from_analysis(doc)
    mep = _mep_summary(doc)
    placed = set()
    children = []
    for storey in reading["storeys"]:
        name, z = storey["name"], storey["z"]
        groups = []
        # Rooms and what is inside them.
        if storey["rooms"]:
            rooms = []
            for r in storey["rooms"]:
                use = f" · {USE_LABELS[r['use']]}" if r["use"] else ""
                inner = []
                for cat, ids in _categorise([i for i in r["contents"] if i not in placed], doc):
                    placed.update(ids)
                    inner.append(_group(cat, ids, doc, name, labels))
                rooms.append(_node(f"{r['name']}{use} · {r['size_m'][0]:.2f}×{r['size_m'][1]:.2f} m · {r['area_m2']:.2f} m²",
                                   None, name, inner))
            groups.append(_node(f"Δωμάτια ({len(rooms)})", None, name, rooms))
        # Walls, exterior / interior, each with its openings.
        walls = [e for e in doc.entities.values() if e.kind == "wall" and entity_level(doc, e) == name]
        if walls:
            ext = set(storey["exterior_walls"])
            sub = []
            for title_, part in (("Εξωτερικοί", [w for w in walls if w.id in ext]),
                                 ("Εσωτερικοί", [w for w in walls if w.id not in ext])):
                if not part:
                    continue
                length = sum(math.hypot(float(w.params["x2"]) - float(w.params["x1"]),
                                        float(w.params["y2"]) - float(w.params["y1"])) for w in part)
                nodes = []
                for w in part:
                    openings = [e.id for e in doc.entities.values()
                                if e.kind in ("door", "window", "opening") and e.parent_id == w.id]
                    placed.update(openings)
                    label = _label(w) + f" · {float(w.params['thickness']) * 100:.0f} cm"
                    nodes.append(_node(label, w.id, name, [_node(_label(doc.get(o)) + f" {float(doc.get(o).params.get('width', 0)):.2f} m", o, name)
                                                           for o in openings]))
                    placed.add(w.id)
                sub.append(_node(f"{title_} ({len(part)}) · {length:.2f} m", None, name, nodes))
            groups.append(_node(f"Τοίχοι ({len(walls)})", None, name, sub))
        # Load-bearing structure, with the analysis names and results.
        cols = [i for i in storey["columns"] if i not in placed]
        beams = [i for i in storey["beams"] if i not in placed]
        structure = [i for i, e in doc.entities.items() if e.kind in ("structural_support", "structural_load")
                     and i not in placed and entity_level(doc, e) == name]
        if cols or beams or structure:
            sub = []
            for title_, ids in (("Κολώνες", cols), ("Δοκοί", beams), ("Στηρίξεις & φορτία", structure)):
                if ids:
                    ids = sorted(ids, key=lambda i: _natural(labels.get(i, _label(doc.get(i)))))
                    sub.append(_group(title_, ids, doc, name, labels))
                    placed.update(ids)
            groups.append(_node(f"Φέρων οργανισμός ({len(cols) + len(beams) + len(structure)})", None, name, sub))
        # Everything else on this storey (outside rooms).
        rest = [i for i, e in doc.entities.items() if i not in placed and e.kind not in SITE
                and entity_level(doc, e) == name and e.kind != "structural_design"]
        for cat, ids in _categorise(rest, doc):
            placed.update(ids)
            groups.append(_group(cat, ids, doc, name, labels))
        summary = f"{storey['walls']} τοίχοι {storey['wall_length_m']:.1f} m · {len(storey['rooms'])} χώροι"
        if storey["columns"] or storey["beams"]:
            summary += f" · {len(storey['columns'])} κολώνες · {len(storey['beams'])} δοκοί"
        children.append(_node(f"{name}  ({z:+.2f} m) · {summary}" if storey["walls"] or storey["columns"] else f"{name}  ({z:+.2f} m)",
                              None, name, groups))
    # Derived networks (whole building): one line each, from the same points.
    if mep:
        names = {"plumbing_point": "Υδραυλικό δίκτυο", "electrical_point": "Ηλεκτρολογικό δίκτυο",
                 "ventilation_point": "Αεραγωγοί"}
        children.append(_node("Η/Μ δίκτυα", None, None, [_node(names[k] + v, None, None) for k, v in mep.items()]))
    site = [i for i, e in doc.entities.items() if e.kind in SITE]
    if site:
        children.append(_node(f"Οικόπεδο ({len(site)})", None, None, [_node(_label(doc.get(i)), i, None) for i in site]))
    design = [i for i, e in doc.entities.items() if e.kind == "structural_design"]
    if design:
        children.append(_node("Στοιχεία στατικής", design[0], None))
    return _node(title, None, None, children)


def used_materials(doc):
    """Palette materials actually assigned in the project: ``[(id, name, count)]``."""
    from archforge.rendering.materials import MATERIAL_PRESETS
    counts = {}
    for e in doc.entities.values():
        ids = [e.params.get("material_id")] + list((e.params.get("surface_materials") or {}).values())
        for mid in {m for m in ids if m}:
            counts[mid] = counts.get(mid, 0) + 1
    return sorted(((m, MATERIAL_PRESETS.get(m, {}).get("name", m), n) for m, n in counts.items()), key=lambda t: t[1])
