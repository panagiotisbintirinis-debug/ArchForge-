"""Small reusable task drawings, attached to the *existing* QAction objects.

No command is cloned or reconnected.  Missing icons are filled by work type;
purpose-designed icons already on commands win.  The starter row is only a
personal-menu configuration, editable/removable like every other user menu.
"""
from __future__ import annotations

from archforge.ui import menu_icons, toolbar_custom


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
    return len(decorated)
