"""Live proposals: rules over the assistant's reading of the Document.

Each proposal says what was found, why (rule + source) and, when it can be
solved automatically, which commands would solve it.  Nothing is applied
without the user: ``apply()`` runs the proposal's commands through the
CommandStack as ONE undoable step.

Rules:

* V-1  Wet room (bathroom / WC) without an extract fan → add one.  A wet
       room without a window has no natural ventilation, so the proposal is
       a warning there, a hint otherwise.
* V-2  Kitchen (sink / cooker) without a hood → add one over the cooker
       point, else over the sink.
* V-3  Ventilation duct findings (length, wall penetrations, shafts).
* J-1  Room under a pitched roof (top storey) without ceiling joists → lay
       them out with the solver.
* J-2  Joists that no listed section carries → technical proposals; when a
       closer spacing solves it, apply that spacing.
* M-1  Plumbing fixtures without a source, circuit warnings: reported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from archforge.assistant.understanding import USE_LABELS, inside, read_drawing


@dataclass
class Proposal:
    key: str
    severity: str                      # 'warning' | 'hint' | 'info'
    title: str
    detail: str
    source: str
    targets: Tuple[str, ...] = ()
    build: Optional[Callable] = field(default=None, repr=False)   # doc -> Command
    run: Optional[str] = None          # non-document action handled by the UI (e.g. 'analyze')

    @property
    def actionable(self):
        return self.build is not None or self.run is not None


def _vent_entity(kind, x, y, z):
    from archforge.core.model import Entity
    from archforge.mep.ventilation import POINT_TYPES
    return Entity("ventilation_point", {"x": float(x), "y": float(y), "z": float(z), "point_type": kind,
                                        "outlet": "auto", "airflow": POINT_TYPES[kind][1]}, name=POINT_TYPES[kind][0])


def _add(entity):
    from archforge.core.commands import AddEntity
    return lambda _doc: AddEntity(entity)


def joists_entity(room_polygon, z, spacing=0.50, usage="ceiling", direction="auto", name="Δοκίδες ταβανιού"):
    from archforge.core.model import Entity
    return Entity("ceiling_joists", {"points": [tuple(p) for p in room_polygon], "z": float(z), "spacing": float(spacing),
                                     "usage": usage, "direction": direction}, name=name)


def _best_spot(doc, room, preferred):
    """A device position: the first preferred point inside the room, else its centroid."""
    for kind, ptypes in preferred:
        for eid in room[kind]:
            e = doc.get(eid)
            if e.params["point_type"] in ptypes:
                return float(e.params["x"]), float(e.params["y"])
    return room["centroid"]


def propose(doc, reading=None):
    reading = reading or read_drawing(doc)
    out: List[Proposal] = []
    for storey in reading["storeys"]:
        z = storey["z"]
        for room in storey["rooms"]:
            name, use = room["name"], room["use"]
            if use in ("bathroom", "wc") and not room["ventilation"]:
                kind = "bath_fan" if use == "bathroom" else "wc_fan"
                x, y = _best_spot(doc, room, (("plumbing", {"shower", "bathtub", "wc"}),))
                no_window = not room["windows"]
                out.append(Proposal(
                    f"V-1:{room['signature']}", "warning" if no_window else "hint",
                    f"{name}: {USE_LABELS[use]} χωρίς απαγωγή",
                    ("Δεν έχει παράθυρο, άρα ούτε φυσικό αερισμό· " if no_window else "Έχει παράθυρο, αλλά ") +
                    f"προτείνεται ανεμιστήρας Ø100 ({'90' if kind == 'bath_fan' else '60'} m³/h) με αεραγωγό προς τα έξω.",
                    "Υγρός χώρος: μηχανική απαγωγή (τάξη μεγέθους DIN 18017-3) — προς έλεγχο μηχανολόγου",
                    (room["signature"],), _add(_vent_entity(kind, x, y, z))))
            if use == "kitchen" and not any(doc.get(i).params["point_type"] == "hood" for i in room["ventilation"]):
                x, y = _best_spot(doc, room, (("electrical", {"cooker"}), ("plumbing", {"kitchen_sink"})))
                out.append(Proposal(
                    f"V-2:{room['signature']}", "hint", f"{name}: κουζίνα χωρίς απορροφητήρα",
                    "Προτείνεται απορροφητήρας 400 m³/h με αεραγωγό Ø125 προς τον πλησιέστερο εξωτερικό τοίχο "
                    "(πάνω από την εστία, αν υπάρχει σημείο κουζίνας/φούρνου).",
                    "Απαγωγή μαγειρείου προς τα έξω — προς έλεγχο μηχανολόγου", (room["signature"],),
                    _add(_vent_entity("hood", x, y, z))))
            if storey["top"] and room["under_pitched_roof"] and not room["joists"]:
                from archforge.structure.joists import size_joists
                ent = joists_entity(room["polygon"], z)
                rep = size_joists(ent.params)
                sec = rep["section"]
                what = (f"{rep['count']} δοκίδες {sec['b'] * 100:.0f}/{sec['h'] * 100:.0f} C24 ανά {rep['spacing_m'] * 100:.0f} cm, "
                        f"άνοιγμα {rep['span_m']:.2f} m (αξιοποίηση {sec['utilisation']:.0%})" if sec else
                        "Καμία τυπική διατομή δεν αρκεί: " + "; ".join(rep.get("proposals", [])))
                out.append(Proposal(f"J-1:{room['signature']}", "hint", f"{name}: ταβάνι κάτω από στέγη χωρίς δοκίδες",
                                    what, rep["provenance"], (room["signature"],), _add(ent)))
    for e in doc.entities.values():
        if e.kind != "ceiling_joists":
            continue
        from archforge.structure.joists import size_joists
        rep = size_joists(e.params)
        if rep["ok"]:
            continue
        fix = None
        for s in (0.40, 0.30):
            if size_joists(dict(e.params, spacing=s))["ok"]:
                from archforge.core.commands import UpdateEntity
                fix = (lambda spacing: lambda _doc: UpdateEntity(e.id, {"spacing": spacing}))(s)
                break
        out.append(Proposal(f"J-2:{e.id}", "warning", f"{e.name or 'Δοκίδες'}: άνοιγμα {rep['span_m']:.2f} m χωρίς επαρκή διατομή",
                            "Τεχνικές προτάσεις: " + "; ".join(rep["proposals"]), rep["provenance"], (e.id,), fix))
    out += _brief(doc)
    out += _interior_walls(doc)
    out += _isotex(doc)
    out += _icf(doc)
    out += _structural(doc)
    out += _roofs(doc)
    if any(e.kind == "ventilation_point" for e in doc.entities.values()):
        from archforge.mep.ventilation import route_ventilation_cached
        for w in route_ventilation_cached(doc)["report"]["warnings"]:
            out.append(Proposal(f"V-3:{w}", "info", w, "Από τη χάραξη των αεραγωγών.", "Βλ. Εξαερισμοί"))
    if any(e.kind == "plumbing_point" for e in doc.entities.values()):
        from archforge.mep.plumbing import route_plumbing_cached
        unserved = route_plumbing_cached(doc)["report"]["unserved"]
        if unserved:
            out.append(Proposal("M-1", "warning", f"Υδραυλικά: {len(unserved)} συνδέσεις χωρίς πηγή",
                                "Πρόσθεσε παροχή κρύου νερού ή θερμοσίφωνα:<br>" + "<br>".join(unserved), "Βλ. Υδραυλικά"))
    if any(e.kind == "electrical_point" for e in doc.entities.values()):
        from archforge.mep.electrical import route_cables_cached
        for w in route_cables_cached(doc)["report"]["warnings"]:
            out.append(Proposal(f"M-2:{w}", "warning", w, "Από τα κυκλώματα.", "Βλ. Πίνακας κυκλωμάτων"))
    # LAY-1: a kitchen / bath laid out by the assistant whose walls moved → re-fit it.
    from archforge.assistant.room_layout import refit_proposals
    out += refit_proposals(doc)
    order = {"warning": 0, "hint": 1, "info": 2}
    return sorted(out, key=lambda p: (order[p.severity], p.key))


def _structural(doc):
    """S-0 run / refresh the analysis; S-1 members that fail, with the section that passes; S-2 drift."""
    from archforge.structure.analysis import fresh_result, has_structure
    from archforge.project.brief import load_bearing_walls
    if load_bearing_walls(doc):
        if any(e.kind == "wall" for e in doc.entities.values()):
            from archforge.project.brief import get_brief
            timber = get_brief(doc)["floor_system"] == "timber"
            isotex = str(get_brief(doc)["wall_system"]).startswith(("isotex_", "icf_"))
            system = "ICF" if str(get_brief(doc)["wall_system"]).startswith("icf_") else "Isotex"
            return [Proposal("S-4", "info", f"{system} = φέρων οργανισμός: χωρίς κολόνες" if isotex else "Φέρουσα τοιχοποιία: χωρίς κολόνες",
                             (("Τα ICF είναι τοιχώματα οπλισμένου σκυροδέματος σε μόνιμο καλούπι EPS" if system == "ICF" else
                               "Τα Isotex είναι τοιχώματα οπλισμένου σκυροδέματος σε μόνιμο καλούπι ξυλοτσιμέντου") + ": φέρουν τα βάρη "
                              "και τον σεισμό· οπλισμός τοιχωμάτων, πρέκια και σενάζ από τη στατική μελέτη. " if isotex else
                              "Οι πέτρινοι/συμπαγείς τοίχοι φέρουν τα βάρη. ") + (
                                 "Πατώματα ξύλινα: δοκίδες ανά χώρο (Βοηθός → Διανομή δοκίδων)." if timber else
                                 "«Εφαρμογή» = οπλισμός πλάκας ανά χώρο (Marcus)."),
                             "Στοιχεία έργου", (), None, run=None if timber else "slabs")]
        return []
    if not has_structure(doc):
        if any(e.kind == "wall" for e in doc.entities.values()):
            from archforge.structure.layout import propose_frame
            entities, report = propose_frame(doc)
            if entities:
                return [Proposal("S-3", "hint", f"Φέρων οργανισμός: {report['columns']} κολόνες, {report['beams']} δοκοί από τους τοίχους",
                                 "Κολόνες σε γωνίες/συναντήσεις τοίχων και ανά ≤ 6 m (όχι σε ανοίγματα), δοκοί πάνω στους τοίχους· "
                                 "«Εφαρμογή» = σκελετός + στατική: διατομές, οπλισμοί, βάσεις (πέδιλα, συνδετήριες) — ένα undo.",
                                 "Προμελέτη φέροντος — προς έλεγχο στατικού", (), None, run="design")]
        return []
    result = fresh_result(doc)
    if result is None:
        return [Proposal("S-0", "hint", "Στατική ανάλυση: χρειάζεται (επαν)υπολογισμός",
                         "Ο φέρων οργανισμός άλλαξε. «Εφαρμογή» = υπολογισμός φορτίων, σεισμού, οπλισμών/διατομών.",
                         "Βλ. Δομικά → Στατική ανάλυση", (), None, run="analyze")]
    out = []
    if result.get("error"):
        out.append(Proposal("S-E", "warning", f"Στατική: {result['error']}", "", result["provenance"]))
    for e in result["members"].values():
        prop = e.get("proposal")
        if not e.get("ok", True):
            what = (f"Πρόταση: διατομή {prop['width'] * 100:.0f}/{prop.get('height', prop.get('depth', 0)) * 100:.0f}"
                    if prop and "profile" not in prop else "Δεν βρέθηκε επαρκής τυπική διατομή — επανεξέταση φορέα")
            out.append(Proposal(f"S-1:{e['id']}", "warning", f"{e['name']}: ανεπαρκής διατομή",
                                "; ".join(e.get("checks", [])) + f"<br>{what}", result["provenance"], (e["id"],),
                                _update(e["id"], prop) if prop else None))
        elif prop and "profile" in prop:
            out.append(Proposal(f"S-1:{e['id']}", "hint", f"{e['name']}: διατομή {prop['profile']} από τον υπολογισμό",
                                f"Καταχώριση της ελαφρύτερης επαρκούς διατομής ({e.get('text', '')}).",
                                result["provenance"], (e["id"],), _update(e["id"], prop)))
    for d in ("Ex", "Ey"):
        info = (result.get("seismic") or {}).get(d)
        if info and not info["drift_ok"]:
            out.append(Proposal(f"S-2:{d}", "warning", f"Σεισμός {d}: σχετική μετακίνηση ορόφου {info['drift_ratio'] * 1000:.1f} ‰ > 5 ‰",
                                "Το κτίριο είναι πολύ εύκαμπτο: μεγαλύτερες κολώνες ή τοιχώματα.", result["provenance"]))
    return out


def _brief(doc):
    """B-0: the project questions are not answered — every later choice depends on them."""
    from archforge.project.brief import get_brief
    if get_brief(doc) is not None:
        return []
    return [Proposal("B-0", "hint", "Στοιχεία έργου: απάντησε στις ερωτήσεις",
                     "Νέο ή ανακαίνιση; Τι τοίχοι; Εξωτερικές ή εσωτερικές διαστάσεις; Τι πατώματα; "
                     "Οι απαντήσεις ορίζουν πάχος/τύπο τοίχων, φέροντα οργανισμό και επιμέτρηση.",
                     "Αρχή έργου", (), None, run="brief")]


def _roofs(doc):
    """R-1: a roof slab under an upper storey is not needed. R-2: an uncovered room has no roof."""
    from archforge.architecture.roof_need import COVERED, coverage, room_face_of, roof_plan
    out = []
    if any(e.kind in ("room_roof", "pitched_roof") for e in doc.entities.values()):
        # Only once the user has started roofing: before that, every room is "open" on purpose.
        missing = roof_plan(doc)["add"]
        if missing:
            from archforge.core.commands import CreateRoomRoofs
            out.append(Proposal("R-2", "warning", f"Στέγη: {len(missing)} χώρος/οι χωρίς στέγη και χωρίς όροφο από πάνω",
                                "Π.χ. ισόγεια προέκταση έξω από τον πάνω όροφο. «Εφαρμογή» = επίπεδη στέγη (δώμα) εκεί· "
                                "για κεραμοσκεπή: Κατασκευή → Στέγη → Με κεραμίδια.", "Κανόνας στέγης: κάθε ακάλυπτος χώρος στεγάζεται",
                                tuple(missing), lambda _doc, m=tuple(missing): CreateRoomRoofs(list(m), thickness=.20, roof_type="flat")))
    # S-0: per-room slabs whose room is gone (walls moved/removed): nothing shows them, they only confuse.
    orphans = tuple(e.id for e in doc.entities.values()
                    if e.kind in ("room_floor", "room_roof", "room_ceiling", "room_foundation")
                    and e.params.get("scope") != "storey" and room_face_of(doc, e) is None)
    if orphans:
        from archforge.core.commands import DeleteEntities
        out.append(Proposal("S-0", "warning", f"Πλάκες χωρίς χώρο: {len(orphans)}",
                            "Ο χώρος τους δεν υπάρχει πια (μετακινήθηκαν ή σβήστηκαν τοίχοι). «Εφαρμογή» = διαγραφή τους· "
                            "μετά Αυτόματα → Δάπεδα/Δώμα για νέες πλάκες στους σημερινούς χώρους.",
                            "Καθαρισμός πλακών", orphans, lambda _doc, ids=orphans: DeleteEntities(list(ids))))
    for e in doc.entities.values():
        if e.kind != "room_roof":
            continue
        found = room_face_of(doc, e)
        if found is None:
            continue
        face, base_z = found
        c = coverage(doc, face.polygon, base_z)
        if c >= COVERED:
            from archforge.core.commands import DeleteEntities
            out.append(Proposal(f"R-1:{e.id}", "warning", f"{e.name or 'Στέγη'}: κάτω από τον όροφο — δεν χρειάζεται",
                                f"Ο όροφος από πάνω καλύπτει το {c:.0%} του χώρου· η στέγη μπαίνει μόνο όπου δεν υπάρχει τίποτα από πάνω. "
                                "«Εφαρμογή» = αφαίρεση της στέγης.", "Κανόνας στέγης: μόνο ακάλυπτοι χώροι", (e.id,),
                                lambda _doc, i=e.id: DeleteEntities([i])))
    return out


def _add_all(entities):
    from archforge.core.commands import AddEntities
    return lambda _doc: AddEntities(list(entities))


def _interior_walls(doc):
    """W-1: interior walls declared load-bearing must be at least 25 cm thick; the fix sets the bearing type."""
    from archforge.project.brief import MIN_BEARING_THICKNESS, get_brief, interior_wall_defaults, interior_walls
    brief = get_brief(doc)
    if brief is None or brief["interior_walls"] != "bearing":
        return []
    itype, ithick, _b = interior_wall_defaults(doc)
    thin = [w for w in interior_walls(doc) if float(w.params.get("thickness", 0.0)) < MIN_BEARING_THICKNESS - 1e-6]
    if not thin:
        return []
    from archforge.core.commands import CompositeCommand, UpdateEntity
    ids = tuple(w.id for w in thin)
    return [Proposal("W-1", "warning", f"Φέροντες εσωτερικοί τοίχοι κάτω από 25 cm: {len(thin)}",
                     "Στα Στοιχεία έργου οι εσωτερικοί τοίχοι είναι φέρων οργανισμός (ελάχιστο 25 cm). "
                     f"«Εφαρμογή» = φέρουσα τοιχοποιία 25 cm + σοβάδες ({ithick * 100:.0f} cm).",
                     "Στοιχεία έργου", ids,
                     lambda _doc: CompositeCommand([UpdateEntity(i, {"wall_type": itype, "thickness": ithick, "load_bearing": True})
                                                    for i in ids], "Φέροντες εσωτερικοί τοίχοι"))]


def _isotex(doc):
    """I-1: Isotex walls drawn — the pieces they need (take-off), shown on «Εφαρμογή»."""
    if not any(e.kind == "wall" and str(e.params.get("wall_type", "")).startswith("isotex_") for e in doc.entities.values()):
        return []
    from archforge.construction.isotex import take_off_isotex
    r = take_off_isotex(doc)
    t = r["totals"]
    detail = ", ".join(f"{c}: {v['blocks']} τεμ." for c, v in r["by_code"].items())
    return [Proposal("I-1", "info", f"Isotex: {t['blocks']} τεμάχια, {t['concrete_m3']} m³ σκυρόδεμα",
                     f"{detail} · {t['net_m2']} m² καθαρού τοίχου σε {t['walls']} τοίχους. «Εφαρμογή» = αναλυτικά ανά τοίχο/όροφο.",
                     r["source"], tuple(w["wall"] for w in r["walls"]), None, run="isotex")]



def _icf(doc):
    """I-2: ICF walls drawn — straight / corner blocks and concrete (take-off), shown on «Εφαρμογή»."""
    if not any(e.kind == "wall" and str(e.params.get("wall_type", "")).startswith("icf_") for e in doc.entities.values()):
        return []
    from archforge.construction.icf import take_off_icf
    r = take_off_icf(doc)
    t = r["totals"]
    return [Proposal("I-2", "info", f"ICF: {int(t['blocks'])} ευθέα + {int(t['corner_blocks'])} γωνιακά, {t['concrete_m3']} m³ σκυρόδεμα",
                     f"{t['net_m2']} m² καθαρού τοίχου σε {t['walls']} τοίχους, κλεισίματα {t['closures_m']} m. "
                     "«Εφαρμογή» = αναλυτικά ανά τοίχο/όροφο.",
                     r["source"], tuple(w["wall"] for w in r["walls"]), None, run="icf")]


def _update(entity_id, params):
    from archforge.core.commands import UpdateEntity
    return lambda _doc: UpdateEntity(entity_id, dict(params))


def apply(stack, proposal):
    """Run the proposal's command through the stack (one undo step); returns the command."""
    if proposal.run == "analyze":
        from archforge.structure.analysis import analyze_cached
        return analyze_cached(stack.doc)
    if proposal.build is None:
        raise ValueError("this proposal has no automatic solution")
    command = proposal.build(stack.doc)
    stack.execute(command)
    return command


def room_at(doc, x, y, z=None):
    """The room (from the reading) containing a plan point on the given / active storey."""
    level = float(doc.work_plane.origin[2]) if z is None else float(z)
    for storey in read_drawing(doc)["storeys"]:
        if abs(storey["z"] - level) > 1e-6:
            continue
        for room in storey["rooms"]:
            if inside(room["polygon"], x, y):
                return room
    return None
