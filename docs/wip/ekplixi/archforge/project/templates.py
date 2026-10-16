"""Ready project templates («Πρότυπα έργων»): a believable Greek home in seconds.

A contractor or a real-estate agent picks a template on an EMPTY project and
gets walls (exterior / interior), doors and windows on their walls, named
rooms, floors, the upper storey with its stair and a tiled roof where it makes
sense — everything through the shared commands, as ONE undo step.  From there
everything stays editable («όλα είναι ρευστά»): move a partition, change a
window, ask the structural proposal.

Coordinates are wall axes in metres (x east, y north, the south façade at
y = 0).  Rooms close on the axes, so ``doc.active_room_faces()`` finds every
room; the areas quoted are axis areas (gross per room).

Wall types follow the project questions when they have been answered
(``brief.wall_defaults`` / ``interior_wall_defaults``); without answers the
exterior walls are 25 cm and the partitions plasterboard 10 cm.  The
renovation template marks every wall «Υφιστάμενο» (phase ``existing``) and,
when the questions are still open, answers «Ανακαίνιση» with interior
dimensions — the take-off then works on the existing building.
"""
from __future__ import annotations

import copy

from archforge.core.commands import (AddEntities, AddEntity, Command, CompositeCommand, CreateFloorLevel,
                                     CreateRoomFloors, SetWorkPlane, _restore_document_state)
from archforge.core.model import Entity

# key -> (title, description); the order is the menu order.
TEMPLATES = {
    "apartment_2br": ("Διαμέρισμα 2 υπνοδωματίων ~80 m²",
                      "Ένας όροφος: σαλόνι-κουζίνα, 2 υπνοδωμάτια, μπάνιο, WC, είσοδος, διάδρομος και μπαλκόνι."),
    "house_3br": ("Μονοκατοικία ισόγεια ~110 m² 3 υπνοδωματίων",
                  "Σαλόνι-τραπεζαρία, κουζίνα, 3 υπνοδωμάτια, μπάνιο, διάδρομος· τετράρριχτη κεραμοσκεπή."),
    "maisonette": ("Διώροφη μονοκατοικία / μεζονέτα ~150 m²",
                   "Ισόγειο: σαλόνι, κουζίνα, WC, αποθήκη, είσοδος με σκάλα· όροφος: 3 υπνοδωμάτια, μπάνιο· δίρριχτη κεραμοσκεπή."),
    "shop": ("Κατάστημα ισογείου ~60 m²",
             "Ενιαίος χώρος καταστήματος με βιτρίνες, WC και αποθήκη."),
    "renovation_apartment": ("Ανακαίνιση διαμερίσματος (υφιστάμενα)",
                             "Το διαμέρισμα 2 υπνοδωματίων ως υφιστάμενο: όλοι οι τοίχοι «Υφιστάμενο», έτοιμο για καθαιρέσεις και νέα."),
}

UPPER_LEVEL = "Floor 2"          # the app's name for the first upper storey (PDF: «1ος όροφος»)
STOREY_HEIGHT = 3.0              # floor to floor (m); walls run floor to slab
EXTERIOR_T = 0.25
INTERIOR_T = 0.10
INTERIOR_TYPE = "drywall_100"


def templates_for_menu():
    """``[(key, title)]`` in menu order."""
    return [(key, title) for key, (title, _desc) in TEMPLATES.items()]


# ---------------------------------------------------------------- the layouts
# Each storey: exterior walls (closed outline), interior walls (ending on other
# axes), openings ``(kind, wall index, centre offset along the wall, width,
# height, sill)`` on the storey's wall list (exterior first, then interior),
# rooms ``(name, probe point)``.  Low walls (``parapet``) close balconies.

def _apartment():
    ext = [(0, 0, 10, 0), (10, 0, 10, 8), (10, 8, 0, 8), (0, 8, 0, 0)]
    inner = [(5.0, 0, 5.0, 8),        # 4  living | night zone
             (5.0, 3.6, 10, 3.6),     # 5  bedroom 1 | corridor
             (5.0, 4.8, 10, 4.8),     # 6  corridor | bath, bedroom 2
             (7.0, 4.8, 7.0, 8),      # 7  bath | bedroom 2
             (0, 6.4, 5.0, 6.4),      # 8  living | entrance, WC
             (1.6, 6.4, 1.6, 8)]      # 9  WC | entrance
    parapet = [(0, 0, 0, -1.6), (0, -1.6, 5.0, -1.6), (5.0, -1.6, 5.0, 0)]
    openings = [
        ("door", 0, 2.5, 1.8, 2.2, 0.0),       # balcony door of the living room
        ("window", 0, 7.5, 1.6, 1.4, 0.9),     # bedroom 1, south
        ("window", 1, 1.8, 1.2, 1.4, 0.9),     # bedroom 1, east
        ("window", 1, 6.4, 1.2, 1.4, 0.9),     # bedroom 2, east
        ("window", 2, 2.0, 0.6, 0.6, 1.5),     # bath, north (small)
        ("door", 2, 6.7, 0.9, 2.1, 0.0),       # entrance door (from the stairwell of the block)
        ("window", 3, 3.6, 1.4, 1.4, 0.9),     # kitchen, west
        ("window", 3, 5.6, 1.4, 1.4, 0.9),     # living, west
        ("door", 4, 4.2, 0.9, 2.1, 0.0),       # living -> corridor
        ("door", 5, 0.7, 0.9, 2.1, 0.0),       # bedroom 1
        ("door", 6, 1.0, 0.8, 2.1, 0.0),       # bath
        ("door", 6, 2.6, 0.9, 2.1, 0.0),       # bedroom 2
        ("door", 8, 3.6, 0.9, 2.1, 0.0),       # entrance -> living
        ("door", 9, 0.8, 0.8, 2.1, 0.0),       # WC
    ]
    rooms = [("Σαλόνι - Κουζίνα", (2.5, 3.0)), ("Υπνοδωμάτιο 1", (7.5, 1.8)), ("Υπνοδωμάτιο 2", (8.5, 6.4)),
             ("Μπάνιο", (6.0, 6.4)), ("WC", (0.8, 7.2)), ("Είσοδος", (3.3, 7.2)), ("Διάδρομος", (7.5, 4.2)),
             ("Μπαλκόνι", (2.5, -0.8))]
    return [dict(z=0.0, ext=ext, inner=inner, parapet=parapet, openings=openings, rooms=rooms)]


def _house():
    ext = [(0, 0, 12.4, 0), (12.4, 0, 12.4, 9.0), (12.4, 9.0, 0, 9.0), (0, 9.0, 0, 0)]
    inner = [(8.0, 0, 8.0, 4.6),       # 4  living | master bedroom
             (0, 4.6, 12.4, 4.6),      # 5  day zone | kitchen, corridor
             (3.6, 4.6, 3.6, 9.0),     # 6  kitchen | corridor, bedroom 2
             (3.6, 5.8, 12.4, 5.8),    # 7  corridor | bedrooms, bath
             (7.0, 5.8, 7.0, 9.0),     # 8  bedroom 2 | bath
             (9.2, 5.8, 9.2, 9.0)]     # 9  bath | bedroom 3
    openings = [
        ("door", 0, 1.4, 1.0, 2.2, 0.0),       # entrance (front door)
        ("door", 0, 4.6, 2.0, 2.2, 0.0),       # living -> veranda (balcony door)
        ("window", 0, 6.9, 1.4, 1.4, 0.9),     # living, south
        ("window", 0, 10.2, 1.6, 1.4, 0.9),    # master bedroom, south
        ("window", 1, 2.3, 1.2, 1.4, 0.9),     # master bedroom, east
        ("window", 1, 7.4, 1.2, 1.4, 0.9),     # bedroom 3, east
        ("window", 2, 4.5, 0.6, 0.6, 1.5),     # bath, north (small)
        ("window", 2, 7.1, 1.4, 1.4, 0.9),     # bedroom 2, north
        ("window", 2, 10.6, 1.2, 1.2, 1.0),    # kitchen, north
        ("window", 3, 6.9, 1.4, 1.4, 0.9),     # kitchen, west
        ("window", 3, 2.3, 1.4, 1.4, 0.9),     # living, west
        ("door", 4, 2.3, 0.9, 2.1, 0.0),       # living -> master bedroom? no: from corridor below
        ("door", 5, 2.0, 0.9, 2.1, 0.0),       # living -> kitchen
        ("door", 5, 5.6, 0.9, 2.1, 0.0),       # living -> corridor
        ("door", 6, 0.6, 0.9, 2.1, 0.0),       # kitchen -> corridor
        ("door", 7, 1.6, 0.9, 2.1, 0.0),       # bedroom 2
        ("door", 7, 4.4, 0.8, 2.1, 0.0),       # bath
        ("door", 7, 6.9, 0.9, 2.1, 0.0),       # bedroom 3
    ]
    rooms = [("Σαλόνι - Τραπεζαρία", (4.0, 2.3)), ("Υπνοδωμάτιο 1", (10.2, 2.3)), ("Κουζίνα", (1.8, 6.8)),
             ("Διάδρομος", (8.0, 5.2)), ("Υπνοδωμάτιο 2", (5.3, 7.4)), ("Μπάνιο", (8.1, 7.4)),
             ("Υπνοδωμάτιο 3", (10.8, 7.4))]
    return [dict(z=0.0, ext=ext, inner=inner, openings=openings, rooms=rooms, roof="hip")]


def _maisonette():
    ext = [(0, 0, 9.4, 0), (9.4, 0, 9.4, 8.0), (9.4, 8.0, 0, 8.0), (0, 8.0, 0, 0)]
    ground_inner = [(0, 5.0, 9.4, 5.0),      # 4  living, kitchen | hall, WC, storage
                    (5.8, 0, 5.8, 5.0),      # 5  living | kitchen
                    (6.2, 5.0, 6.2, 8.0),    # 6  hall | WC
                    (7.8, 5.0, 7.8, 8.0)]    # 7  WC | storage
    ground_openings = [
        ("door", 0, 3.0, 2.0, 2.2, 0.0),       # living -> garden (balcony door)
        ("window", 0, 1.0, 1.2, 1.4, 0.9),     # living, south
        ("window", 0, 7.6, 1.4, 1.4, 0.9),     # kitchen, south
        ("window", 1, 2.5, 1.2, 1.2, 1.0),     # kitchen, east
        ("window", 2, 1.6, 0.6, 0.6, 1.5),     # storage, north (small)
        ("window", 2, 2.4, 0.6, 0.6, 1.5),     # WC, north (small)
        ("door", 2, 3.6, 1.0, 2.2, 0.0),       # entrance (north)
        ("window", 2, 7.2, 1.2, 1.4, 0.9),     # hall, north
        ("window", 3, 5.5, 1.4, 1.4, 0.9),     # living, west
        ("door", 4, 5.4, 0.9, 2.1, 0.0),       # hall -> living
        ("door", 4, 8.6, 0.8, 2.1, 0.0),       # kitchen -> storage
        ("door", 5, 4.0, 0.9, 2.1, 0.0),       # living -> kitchen
        ("door", 6, 0.6, 0.8, 2.1, 0.0),       # WC
    ]
    ground_rooms = [("Σαλόνι - Τραπεζαρία", (2.9, 2.5)), ("Κουζίνα", (7.6, 2.5)),
                    ("Είσοδος - Κλιμακοστάσιο", (5.6, 6.5)), ("WC", (7.0, 6.5)), ("Αποθήκη", (8.6, 6.5))]
    upper_inner = [(0, 4.6, 9.4, 4.6),       # 4  bedrooms | hall
                   (3.4, 0, 3.4, 4.6),       # 5  bedroom 1 | bedroom 2
                   (6.4, 0, 6.4, 4.6),       # 6  bedroom 2 | bedroom 3
                   (5.2, 5.8, 9.4, 5.8),     # 7  corridor | bath, linen
                   (5.2, 5.8, 5.2, 8.0),     # 8  hall | bath
                   (7.8, 5.8, 7.8, 8.0)]     # 9  bath | linen
    upper_openings = [
        ("window", 0, 1.7, 1.4, 1.4, 0.9),     # bedroom 1, south
        ("door", 0, 4.9, 1.6, 2.2, 0.0),       # bedroom 2 -> balcony door
        ("window", 0, 7.9, 1.4, 1.4, 0.9),     # bedroom 3, south
        ("window", 1, 2.3, 1.2, 1.4, 0.9),     # bedroom 3, east
        ("window", 2, 2.6, 0.6, 0.6, 1.5),     # bath, north (small)
        ("window", 2, 5.4, 1.2, 1.4, 0.9),     # hall, north (over the stair)
        ("window", 3, 5.6, 1.2, 1.4, 0.9),     # hall, west
        ("window", 3, 2.3, 1.2, 1.4, 0.9),     # bedroom 1, west
        ("door", 4, 2.2, 0.9, 2.1, 0.0),       # bedroom 1
        ("door", 4, 4.0, 0.9, 2.1, 0.0),       # bedroom 2
        ("door", 4, 7.2, 0.9, 2.1, 0.0),       # bedroom 3
        ("door", 7, 1.3, 0.8, 2.1, 0.0),       # bath
        ("door", 7, 3.4, 0.8, 2.1, 0.0),       # linen cupboard
    ]
    upper_rooms = [("Υπνοδωμάτιο 1", (1.7, 2.3)), ("Υπνοδωμάτιο 2", (4.9, 2.3)), ("Υπνοδωμάτιο 3", (7.9, 2.3)),
                   ("Χολ - Διάδρομος", (2.6, 5.2)), ("Μπάνιο", (6.5, 6.9)), ("Λινοθήκη", (8.6, 6.9))]
    # U stair in the hall: first flight from the hall's landing area westwards, back east on the north side.
    stair = dict(origin=(4.4, 5.8), angle=180.0, layout="u", turn=-1, width=1.0)
    return [dict(z=0.0, ext=ext, inner=ground_inner, openings=ground_openings, rooms=ground_rooms, stair=stair),
            dict(z=STOREY_HEIGHT, ext=ext, inner=upper_inner, openings=upper_openings, rooms=upper_rooms, roof="gable")]


def _shop():
    ext = [(0, 0, 6.0, 0), (6.0, 0, 6.0, 10.0), (6.0, 10.0, 0, 10.0), (0, 10.0, 0, 0)]
    inner = [(0, 8.0, 6.0, 8.0),       # 4  shop | WC, storage
             (1.8, 8.0, 1.8, 10.0)]    # 5  WC | storage
    openings = [
        ("window", 0, 1.1, 1.6, 2.2, 0.4),     # shop window (vitrine)
        ("door", 0, 3.0, 1.6, 2.4, 0.0),       # glass entrance door
        ("window", 0, 4.9, 1.6, 2.2, 0.4),     # shop window (vitrine)
        ("window", 2, 2.0, 1.2, 0.8, 1.8),     # storage, high window
        ("window", 2, 5.1, 0.6, 0.6, 1.8),     # WC, high window (small)
        ("door", 4, 0.9, 0.8, 2.1, 0.0),       # WC
        ("door", 4, 4.0, 0.9, 2.1, 0.0),       # storage
    ]
    rooms = [("Κατάστημα", (3.0, 4.0)), ("WC", (0.9, 9.0)), ("Αποθήκη", (3.9, 9.0))]
    return [dict(z=0.0, ext=ext, inner=inner, openings=openings, rooms=rooms, height=3.4)]


_LAYOUTS = {"apartment_2br": _apartment, "house_3br": _house, "maisonette": _maisonette, "shop": _shop,
            "renovation_apartment": _apartment}


def _fix_house_openings(storeys):
    # Master bedroom door: from the corridor (wall 5), not through the living-room partition.
    s = storeys[0]
    s["openings"] = [o for o in s["openings"] if o[1] != 4] + [("door", 5, 9.0, 0.9, 2.1, 0.0)]
    return storeys


# ---------------------------------------------------------------- commands
class SetRoomNames(Command):
    """Names of the rooms found at ``(z, probe point)`` as one undo step."""

    def __init__(self, names):
        self.names = [(float(z), (float(p[0]), float(p[1])), str(n)) for z, p, n in names]
        self.before = None

    def do(self, doc):
        from archforge.assistant.understanding import inside
        if self.before is None:
            self.before = copy.deepcopy(doc.room_data)
        for z, (x, y), name in self.names:
            face = next((f for f in doc.active_room_faces(z=z) if inside(f.polygon, x, y)), None)
            if face is None:
                raise ValueError(f"Πρότυπο: ο χώρος «{name}» δεν κλείνει")
            doc.set_room_metadata(face.signature, name=name)

    def undo(self, doc):
        if self.before is not None:
            doc.room_data = copy.deepcopy(self.before)


class TemplateCommand(CompositeCommand):
    """A template as ONE undo step.

    The later steps need the earlier ones in the Document (floors need the
    closed rooms, the stair needs the upper slab, the roof reads the plan), so
    the first ``do`` builds each step on the live Document and keeps it; redo
    replays the same commands (same entity ids).  Undo restores the state
    from before the template (rooms, levels and work plane included).
    """

    def __init__(self, key, steps, label):
        super().__init__([], label)
        self.key = key
        self._steps = list(steps)
        self._built = False
        self._before = None

    def do(self, doc):
        self._before = (copy.deepcopy(doc.to_dict()), list(doc.selection))
        if self._built:
            return super().do(doc)
        done = []
        try:
            for step in self._steps:
                command = step(doc)
                if command is None:
                    continue
                command.do(doc)
                done.append(command)
        except Exception:
            _restore_document_state(doc, *self._before)
            raise
        self.commands = done
        self._built = True

    def undo(self, doc):
        if self._before is not None:
            _restore_document_state(doc, *self._before)


# ---------------------------------------------------------------- building
def _wall_kinds(doc, key):
    """((type, thickness), (type, thickness)) for exterior and interior walls."""
    from archforge.project.brief import get_brief, interior_wall_defaults, wall_defaults
    if get_brief(doc) is None and key != "renovation_apartment":
        return (None, EXTERIOR_T), (INTERIOR_TYPE, INTERIOR_T)
    if get_brief(doc) is None:
        from archforge.project.brief import DEFAULTS
        from archforge.architecture.wall_types import total_thickness
        from archforge.project.brief import INTERIOR_WALLS, WALL_SYSTEMS
        et = WALL_SYSTEMS[DEFAULTS["wall_system"]][1]
        it = INTERIOR_WALLS[DEFAULTS["interior_walls"]][1]
        return (et, round(total_thickness(et), 4)), (it, round(total_thickness(it), 4))
    ext = wall_defaults(doc)
    inner = interior_wall_defaults(doc)
    return ext, (inner[0], inner[1])


def _wall(seg, z, height, kind, phase=None, name="Τοίχος"):
    wall_type, thickness = kind
    p = {"x1": float(seg[0]), "y1": float(seg[1]), "x2": float(seg[2]), "y2": float(seg[3]),
         "z": float(z), "height": float(height), "thickness": float(thickness)}
    if wall_type:
        p["wall_type"] = wall_type
    if phase:
        p["phase"] = phase
    return Entity("wall", p, name=name)


def _storey_entities(storey, ext_kind, int_kind, phase):
    z = storey["z"]
    h = float(storey.get("height", STOREY_HEIGHT))
    walls = [_wall(s, z, h, ext_kind, phase, "Εξωτερικός τοίχος") for s in storey["ext"]]
    walls += [_wall(s, z, h, int_kind, phase, "Εσωτερικός τοίχος") for s in storey["inner"]]
    parapets = [_wall(s, z, 1.0, (None, INTERIOR_T), phase, "Στηθαίο μπαλκονιού") for s in storey.get("parapet", ())]
    openings = []
    names = {"door": "Πόρτα", "window": "Παράθυρο"}
    for kind, idx, offset, width, height, sill in storey["openings"]:
        params = {"offset": float(offset), "width": float(width), "height": float(height), "sill": float(sill)}
        if phase:
            params["phase"] = phase
        openings.append(Entity(kind, params, name=names[kind], parent_id=walls[idx].id))
    return walls + parapets + openings


def _brief_step(key):
    def step(doc):
        from archforge.project.brief import DEFAULTS, brief_entity
        if key != "renovation_apartment" or brief_entity(doc) is not None:
            return None
        return AddEntity(Entity("project_brief", dict(DEFAULTS, project_type="renovation", measure="interior"),
                                name="Στοιχεία έργου"))
    return step


def _floors_step(z):
    def step(doc):
        sigs = [f.signature for f in doc.active_room_faces(z=z)]
        return CreateRoomFloors(sigs, thickness=.15) if sigs else None
    return step


def _stair_step(spec, z):
    def step(doc):
        from archforge.architecture.stairs import solve_stair_candidates, upper_floor_landing
        landing = upper_floor_landing(doc, z, spec["origin"])
        if landing is None:
            return None
        import math
        ox, oy = spec["origin"]
        a = math.radians(spec["angle"])
        pointer = (ox + math.cos(a) * 4.0, oy + math.sin(a) * 4.0)
        candidates = solve_stair_candidates(z, landing["landing_z"], spec["origin"], pointer, width=spec["width"],
                                            upper_floor_z=landing["floor_z"], upper_slab_thickness=landing["slab_thickness"])
        chosen = next(c for c in candidates if c.layout == spec["layout"] and c.turn_direction == spec["turn"])
        return AddEntity(Entity("stair", chosen.to_params(), name="Σκάλα"))
    return step


def _roof_step(form, z):
    def step(doc):
        from archforge.architecture.roof_choice import form_roofs
        from archforge.structure.timber_roof import FORMS
        roofs = [Entity("pitched_roof", p, name=f"Κεραμοσκεπή {FORMS[p['roof_form']].lower()}")
                 for p in form_roofs(doc, form, z)]
        return AddEntities(roofs) if roofs else None
    return step


def build_template(doc, key, force=False):
    """ONE command (a single undo) that draws the template ``key`` on ``doc``.

    Raises ``ValueError`` (in Greek) for an unknown template, or when the
    project already has walls (unless ``force=True``).
    """
    if key not in TEMPLATES:
        raise ValueError(f"Άγνωστο πρότυπο: «{key}»")
    if not force and any(e.kind == "wall" for e in doc.entities.values()):
        raise ValueError("Το έργο έχει ήδη τοίχους — τα πρότυπα μπαίνουν σε κενό έργο (Αρχείο → Νέο).")
    storeys = _LAYOUTS[key]()
    if key == "house_3br":
        storeys = _fix_house_openings(storeys)
    phase = "existing" if key == "renovation_apartment" else None
    title = TEMPLATES[key][0]
    ground_plane = copy.deepcopy(doc.work_plane)

    steps = [_brief_step(key)]

    def walls_step(doc):
        ext_kind, int_kind = _wall_kinds(doc, key)
        entities = []
        for storey in storeys:
            entities += _storey_entities(storey, ext_kind, int_kind, phase)
        return AddEntities(entities)
    steps.append(walls_step)
    for storey in storeys:
        if storey["z"] > 0 and not any(abs(float(v) - storey["z"]) < 1e-6 for v in doc.levels.values()):
            steps.append(lambda _doc, z=storey["z"]: CreateFloorLevel(UPPER_LEVEL, z))
    steps.append(lambda _doc: SetRoomNames([(s["z"], p, n) for s in storeys for n, p in s["rooms"]]))
    for storey in storeys:
        steps.append(_floors_step(storey["z"]))
    for storey in storeys:
        if storey.get("stair"):
            steps.append(_stair_step(storey["stair"], storey["z"]))
    for storey in storeys:
        if storey.get("roof"):
            steps.append(_roof_step(storey["roof"], storey["z"]))
    steps.append(lambda _doc: SetWorkPlane(ground_plane))
    return TemplateCommand(key, steps, f"Νέο από πρότυπο: {title}")
