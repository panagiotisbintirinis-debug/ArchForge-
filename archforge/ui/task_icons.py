"""Small reusable task drawings, attached to the *existing* QAction objects.

No command is cloned or reconnected.  Missing icons are filled by work type;
purpose-designed icons already on commands win.  The starter row is only a
personal-menu configuration, editable/removable like every other user menu.
"""
from __future__ import annotations

from archforge.ui import menu_icons, toolbar_custom


# Owner 04/11: an icon on *every* command of the menus.  These specific names are matched before LEAF_ICONS
# (a «Τοίχοι από το υπόβαθρο» is an import, not a wall; the drawings are menu_icons._MORE).
SPECIFIC_ICONS = (
    ("Νέο έργο", "new"), ("Άνοιγμα έργου", "open"), ("Άνοιγμα δείγματος", "open"), ("Ανάκτηση", "recover"),
    ("Αρχική σελίδα", "home"), ("Τοίχοι από το υπόβαθρο", "import"), ("Σχέδιο μηχανικού", "import"),
    ("Σύνολο σχεδίων", "import"), ("Εισαγωγή", "import"),
    ("= Υφιστάμενα", "phase_existing"), ("→ Καθαίρεση", "phase_demolish"), ("→ Νέα", "phase_new"),
    ("Δέντρο έργου", "tree"), ("Διαστάσεις δωματίου", "tape"),
    ("Κάγκελα κάθετα", "railing"), ("Οριζόντιες ράβδοι", "railing"), ("Τζάμι με ορθοστάτες", "railing"),
    ("Τζάμι σε χωνευτό", "railing"), ("Πάνελ συμπαγές", "railing"), ("Πάνελ διάτρητο", "railing"),
    ("Συρματόσχοινο", "railing"), ("Κτιστό στηθαίο", "railing"), ("Ξύλινο", "railing"),
    ("Υδραυλικά", "water"), ("Εξάρτημα", "part"), ("Άρθρωση", "hinge"),
    ("Τοποθέτηση αντικειμένου", "place"), ("Επεξεργασία αντικειμένου", "edit"), ("Υλικό στο επιλεγμένο", "materials"),
    ("Γλυπτική", "sculpt"), ("Εξαγωγή PDF", "pdf"), ("Φύλλο ξυλοτύπου", "sheet"),
    ("IFC", "export"), ("DXF κατόψεις", "export"), ("STL", "export"), ("Εικόνα 3D", "export"),
    ("Μεζούρα", "tape"), ("Αυτόματες διαστάσεις", "autodim"),
    ("Πολυγραμμή", "polyline"), ("Γραμμή", "line"), ("Ορθογώνιο", "rect"), ("Κύκλος", "circle"),
    ("Τόξο (3", "arc"), ("Σημείωση με βέλος", "leader"), ("Σημείωση", "note"),
    ("Τομή", "section"), ("Εσωτερική όψη", "elevation"), ("Τεμάχια", "wall"), ("Τιμές", "price"),
    ("3D Προοπτική", "view3d"), ("Ορθογραφική", "ortho"), ("Πάνω", "top"), ("Πρόσοψη", "front"),
    ("Πλάγια", "side"), ("Ρεαλιστική", "realistic"), ("Από εδώ που κοιτάζω", "camera"), ("Κάμερες", "camera"),
    ("Ταυτόχρονα 2D + 3D", "split"), ("Σκιές επαφής", "ao"),
    ("Πρωί", "sun"), ("Μεσημέρι", "sun"), ("Απόγευμα", "sun"), ("Δειλινό", "sun"), ("Νύχτα", "moon"),
    ("Χωρίς ουρανό", "studio"), ("σβηστά", "bulb_off"), ("αναμμένα", "bulb_on"), ("Φώτα του έργου", "bulb_on"),
    ("Ώρα και μήνας", "clock"), ("Αποχετεύσεις στο 3D", "water"), ("Εξαερισμοί στο 3D", "fan"),
    ("Μηχανολογικά στο 3D", "part"), ("Ανοιχτά κουφώματα", "door"),
    ("Αρχιτεκτονικό", "wall"), ("Η/Μ", "power"), ("Layers", "layers"),
    ("ενημερώσεις", "update"), ("Μονάδες", "units"), ("ποντικιού", "mouse"),
    ("Σχετικά", "info"), ("Έργο / Βιβλιοθήκη", "panel"), ("Κοινά (παλέτα)", "panel"),
    ("Μικρά", "size_s"), ("Μεσαία", "size_m"), ("Μεγάλα", "size_l"), ("Όνομα κάτω", "text_below"),
    ("Κλείδωμα θέσης", "lock"), ("Γραμμή κατάστασης", "status"), ("Επαναφορά διάταξης", "reset"),
    ("Κατασκευή", "toolbar"), ("Βιβλιοθήκη", "toolbar"), ("Όροφος", "toolbar"), ("Περιβάλλον", "toolbar"),
)

# Leaf names are matched first, so a door under Construction still gets a door.
# Rules are deliberately restricted to recognisable tasks, not generic dots.
LEAF_ICONS = (
    ("Ρυθμίσεις ορόφων", "level"),
    ("Αναίρεση", "undo"), ("Επανάληψη", "undo"),
    ("Αποθήκευση", "save"),
    ("Μετακίνηση", "move"), ("Περιστροφή", "rotate"),
    ("Τέντωμα", "stretch"), ("Διπλασιασμός", "duplicate"),
    ("Διαγραφή", "delete"), ("Σβήσε", "delete"),
    ("Γωνία", "corner"), ("Πόρτα", "door"), ("Παράθυρο", "window"),
    ("Άνοιγμα", "opening"), ("Κούφωμα", "window"),
    ("Τοίχ", "wall"), ("Τοιχ", "wall"),
    ("Δωμάτιο", "room"), ("χώρο", "room"),
    ("Σκάλα", "stair"), ("Ράμπα", "ramp"),
    ("Μπαλκόνι", "balcony"), ("Πλάκ", "slab"), ("Δάπεδ", "slab"),
    ("Δώμα", "roof"), ("Στέγ", "roof"), ("Κεραμ", "roof"),
    ("οροφή", "ceiling"), ("Οροφή", "ceiling"), ("Ψευδοροφή", "ceiling"),
    ("Κολών", "column"), ("Κολόν", "column"),
    ("Δοκό", "beam"), ("Δοκάρ", "beam"),
    ("Βάσεις", "footing"), ("Θεμελί", "footing"),
    ("Φέρον", "statics"), ("Στατικ", "statics"),
    ("Φωτισ", "lighting"), ("Σποτ", "lighting"),
    ("Πρίζ", "power"), ("Διακόπτ", "power"),
    ("Πλυντήρ", "appliance"), ("Θερμοσίφ", "appliance"),
    ("Νεροχύτ", "bath"), ("Νιπτήρ", "bath"), ("Λεκάν", "bath"),
    ("Ντουζ", "bath"), ("Μπανιέρ", "bath"),
    ("Παροχή κρύου νερού", "water"), ("Ύδρευσ", "water"),
    ("Πισίνα", "pool"), ("Φυτό", "plant"),
    ("Μονοπάτι", "road"), ("Πεζοδρόμιο", "road"), ("Δρόμος", "road"),
    ("Ντουλάπ", "cabinet"), ("Συρτάρ", "cabinet"), ("Κουζίν", "cabinet"),
    ("Υλικ", "materials"), ("Χρωματ", "materials"),
    ("Κάμερα", "camera"), ("Περιήγη", "camera"),
    ("Επιλογή", "select"), ("Ιδιότητ", "properties"),
    ("Βοηθ", "assist"), ("Έλεγχος ποιότητας", "properties"),
    ("Συντομεύσεις", "properties"), ("Μέγεθος εικονιδίων", "properties"),
)
SECTION_ICONS = (
    ("Ύδρευση", "water"), ("Αποχέτευ", "bath"),
    ("Ηλεκτρολογ", "power"), ("Θέρμανση", "appliance"),
    ("Αερισμό", "appliance"), ("Φωτισμό", "lighting"),
    ("Ασθενή", "appliance"), ("Φέρων", "statics"),
    ("Πέργκολα", "roof"), ("Περιβάλλων χώρος", "room"),
    ("Έδαφος", "slab"), ("Κουζίνα", "cabinet"),
    ("Όροφοι", "level"), ("Στέγη", "roof"),
    ("Κέλυφος", "wall"), ("Ανοίγματα", "opening"),
    ("Σκάλα", "stair"), ("Πλάκες", "slab"),
)

STARTER_TASKS = (
    "Έργο / Όροφοι / Ρυθμίσεις ορόφων — στάθμη και καθαρό ύψος…",
    "Επεξεργασία / Μετακίνηση",
    "Επεξεργασία / Περιστροφή",
    "Κατασκευή / Κέλυφος / Τοίχος (κλικ στις γωνίες)",
    "Κατασκευή / Ανοίγματα / Πόρτα",
    "Κατασκευή / Ανοίγματα / Παράθυρο",
    "Κατασκευή / Πλάκες / Δάπεδα (αυτόματα)",
    "Κατασκευή / Σκάλα·Ράμπα / Σκάλα",
    "Κατασκευή / Στέγη / Με κεραμίδια (ξύλινη στέγη) / Δίρριχτη",
    "Κατασκευή / Φέρων οργανισμός / Δομικά: κολόνες, δοκάρια, βάσεις / Κολώνα",
    "Εγκαταστάσεις / Ύδρευση / Παροχή κρύου νερού",
    "Εγκαταστάσεις / Ηλεκτρολογικά / Πρίζες / Πρίζα σούκο",
    "Διαμόρφωση / Περιβάλλων χώρος / Φυτό: Δέντρο",
    "Επεξεργασία / Διαγραφή",
)


def _icon_for(path):
    leaf = path.split(toolbar_custom.SEP)[-1].casefold()
    for phrase, name in LEAF_ICONS:
        if phrase.casefold() in leaf:
            return name
    text = path.casefold()
    for phrase, name in SECTION_ICONS:
        if phrase.casefold() in text:
            return name
    return None


def icon_for_text(text):
    """The drawing for a command by its own text (SPECIFIC_ICONS, then LEAF_ICONS), or None."""
    leaf = str(text).replace("&&", "&").casefold()
    for phrase, name in SPECIFIC_ICONS + LEAF_ICONS:
        if phrase.casefold() in leaf:
            return name
    return None


def fill_menus(window):
    """Every command of the menu bar and of the first row without a picture gets one, read from its own text (the
    catalog's paths split names holding « / »).  Returns how many were drawn."""
    n, seen = 0, set()

    def walk(menu):
        nonlocal n
        for a in menu.actions():
            if a.isSeparator() or not a.text() or id(a) in seen:
                continue
            seen.add(id(a))
            if a.menu() is not None:
                walk(a.menu())
            elif a.icon().isNull():
                name = icon_for_text(a.text())
                if name:
                    a.setIcon(menu_icons.icon(name)); n += 1
    for top in window.menuBar().actions():
        if top.menu() is not None:
            walk(top.menu())
    return n


def install(window):
    actions = toolbar_custom.catalog(window)
    decorated = set()
    for path, action in actions.items():
        if action.isSeparator() or not action.icon().isNull():
            continue
        name = _icon_for(path)
        if name:
            action.setIcon(menu_icons.icon(name))
            decorated.add(id(action))
    p = toolbar_custom.prefs(window)
    if not p.get("task_icons_seeded", False):
        # A one-time helpful starting point.  Once removed or rearranged the
        # user's layout is never recreated behind their back.
        if not p.get("personal_menus"):
            chosen = [path for path in STARTER_TASKS if path in actions]
            p["personal_menus"] = [{
                "id": "starter_task_icons", "title": "Εργασίες", "mode": "docked",
                "size": 22, "width": 320, "height": 180,
                "show_labels": False, "commands": chosen,
            }]
        p["task_icons_seeded"] = True
        toolbar_custom.save(window)
    return len(decorated) + fill_menus(window)
