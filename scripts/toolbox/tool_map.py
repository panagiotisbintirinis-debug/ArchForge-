"""Every command of ArchForge on the new map (owner 30/10 with GPT: «πρώτα η οργάνωση των εργαλείων και μετά η
εμφάνισή τους» · «να μπορώ εύκολα να βρω αυτό που θέλω χωρίς να λέω πού είναι αυτό τώρα» · «οι σχέσεις των μενού
μετράνε πολύ»).

The map: five work menus (Έργο · Κατασκευή · Εγκαταστάσεις · Διαμόρφωση · Σχέδια), the view switch always at hand
(2D / 3D / Τομή + its ▾ display options), ⚙ Ρυθμίσεις apart from drawing, and the menu of the selected object
(Γεωμετρία · Σύνθεση · Ανοίγματα · Συνδέσεις · Εμφάνιση στα σχέδια).  One main home per command; the object menu
and right click are shortcuts to the same command.

Opens the program as ``menu_smoke.py`` does (nothing is saved), reads every leaf command of the menu bar and of the
visible tool groups, and writes: where each one is today → its proposed home; the commands that sit in two places or
under a heading that is not theirs; what the wall's object menu would hold (existing commands and Ιδιότητες rows)
and what is missing there.  The proposed homes are the ``RULES`` below — a table to argue over, not code to obey.

Run (cloud):  QTWEBENGINE_DISABLE_SANDBOX=1 QT_QPA_PLATFORM=offscreen python scripts/toolbox/tool_map.py --markdown out.md
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TOP = ("Έργο", "Κατασκευή", "Εγκαταστάσεις", "Διαμόρφωση", "Σχέδια", "Προβολή ▾", "⚙ Ρυθμίσεις", "Αντικείμενο")

# (prefix of today's path, proposed home).  First match wins — specific prefixes first.
RULES = (
    # ---- Έργο: files, storeys, project data, renovation phases
    ("Αρχείο / Εισαγωγή / Σχέδιο μηχανικού", "Έργο / Εισαγωγή / Υπόβαθρο PDF·DXF"),
    ("Αρχείο / Εισαγωγή / Σύνολο σχεδίων", "Έργο / Εισαγωγή / Σύνολο σχεδίων"),
    ("Αρχείο / Εισαγωγή / Εισαγωγή τοπογραφικού", "Έργο / Εισαγωγή / Τοπογραφικό"),
    ("Αρχείο / Εισαγωγή", "Έργο / Εισαγωγή"),
    ("Αρχείο / Εξαγωγή / Εξαγωγή PDF", "Σχέδια / Εκτύπωση·PDF"),
    ("Αρχείο / Εξαγωγή", "Σχέδια / Εξαγωγή"),
    ("Αρχείο / Αυτόματη αποθήκευση", "⚙ Ρυθμίσεις / Γενικά"),
    ("Αρχείο / Έλεγχος για ενημερώσεις", "⚙ Ρυθμίσεις / Γενικά"),
    ("Αρχείο / Στοιχεία έργου", "Έργο / Στοιχεία έργου"),
    ("Αρχείο", "Έργο / Αρχείο"),
    ("Κατασκευή / Όροφοι", "Έργο / Όροφοι"),
    ("Κατασκευή / Ανακαίνιση", "Έργο / Φάσεις (υφιστάμενα·καθαίρεση·νέα)"),
    # ---- editing: object menu + shortcuts (one home: the object), undo always at hand
    ("Επεξεργασία / Αναίρεση", "Γραμμή εργασίας (πάντα ορατό)"),
    ("Επεξεργασία / Επανάληψη", "Γραμμή εργασίας (πάντα ορατό)"),
    ("Επεξεργασία / Συντομεύσεις", "⚙ Ρυθμίσεις / Χειρισμός"),
    ("Επεξεργασία / Γωνία", "Αντικείμενο: Τοίχος / Συνδέσεις"),
    ("Επεξεργασία", "Αντικείμενο: κοινά (Μετακίνηση·Περιστροφή·Τέντωμα·Διπλασιασμός·Διαγραφή)"),
    # ---- CAD aids
    ("CAD / Βοηθήματα σχεδίασης", "Γραμμή εργασίας (Κάνναβος·Έλξη)"),
    ("CAD / Διαστάσεις", "Σχέδια / Διαστάσεις"),
    # ---- Κατασκευή: shell, openings, slabs, roofs, stairs, structure
    ("Κατασκευή / Τοίχοι  δωμάτια / Θόλοι", "Κατασκευή / Κέλυφος / Θόλοι Bio-Spectre"),
    ("Κατασκευή / Τοίχοι  δωμάτια / Τοίχοι από το υπόβαθρο", "Έργο / Εισαγωγή / Τοίχοι από υπόβαθρο"),
    ("Κατασκευή / Τοίχοι  δωμάτια / Γωνία επιλεγμένου", "Αντικείμενο: Τοίχος / Συνδέσεις"),
    ("Κατασκευή / Τοίχοι  δωμάτια / Διαστάσεις δωματίου", "Αντικείμενο: Χώρος / Γεωμετρία"),
    ("Κατασκευή / Τοίχοι  δωμάτια", "Κατασκευή / Κέλυφος / Τοίχος·Δωμάτιο"),
    ("Κατασκευή / Ολοκλήρωση κτιρίου", "Κατασκευή / Κέλυφος"),
    ("Κατασκευή / Κουφώματα", "Κατασκευή / Ανοίγματα"),
    ("Κατασκευή / Κάγκελα  μπαλκόνια / Κάγκελο σκάλας", "Κατασκευή / Σκάλα·Ράμπα"),
    ("Κατασκευή / Κάγκελα  μπαλκόνια / Μπαλκόνι", "Κατασκευή / Πλάκες"),
    ("Κατασκευή / Κάγκελα  μπαλκόνια", "Κατασκευή / Κάγκελα"),
    ("Κατασκευή / Πέργκολα", "Διαμόρφωση / Περιβάλλων χώρος"),
    ("Κατασκευή / Δάπεδα  πλάκες / Μπαλκόνι", "Κατασκευή / Πλάκες"),
    ("Κατασκευή / Δάπεδα  πλάκες", "Κατασκευή / Πλάκες"),
    ("Κατασκευή / Στέγη / Στέγη: ", "Προβολή ▾ / Στρώσεις στέγης"),
    ("Κατασκευή / Στέγη", "Κατασκευή / Στέγη"),
    ("Κατασκευή / Ψευδοροφή", "Κατασκευή / Πλάκες / Ψευδοροφή"),
    ("Κατασκευή / Σκάλα / Ράμπα", "Κατασκευή / Σκάλα·Ράμπα"),
    ("Κατασκευή / Ντουλάπια / κουζίνα", "Διαμόρφωση / Κουζίνα·ντουλάπια"),
    ("Κατασκευή / Δομικά / Φύλλο ξυλοτύπου", "Σχέδια / Φύλλα"),
    ("Κατασκευή / Δομικά", "Κατασκευή / Φέρων οργανισμός"),
    # ---- Εγκαταστάσεις
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Μηχανισμοί", "Διαμόρφωση / Μηχανισμοί"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Ασθενή στο 3D", "Προβολή ▾ / Εγκαταστάσεις στο 3D"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Θέρμανση στο 3D", "Προβολή ▾ / Εγκαταστάσεις στο 3D"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Υδραυλικά", "Εγκαταστάσεις / Ύδρευση"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Αποχετεύσεις", "Εγκαταστάσεις / Αποχέτευση"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Ηλεκτρολογικά σημεία / Φωτισμός", "Εγκαταστάσεις / Φωτισμός"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Κρυφός φωτισμός", "Εγκαταστάσεις / Φωτισμός"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Ηλεκτρολογικ", "Εγκαταστάσεις / Ηλεκτρολογικά"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Χάρτης σωληνώσεων", "Εγκαταστάσεις / Ηλεκτρολογικά"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Ασθενή", "Εγκαταστάσεις / Ασθενή (δίκτυο·TV)"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Θέρμανση", "Εγκαταστάσεις / Θέρμανση"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις / Εξαερισμοί", "Εγκαταστάσεις / Αερισμός"),
    ("Κατασκευή / Η/Μ εγκαταστάσεις", "Εγκαταστάσεις"),
    # ---- Διαμόρφωση: materials, kitchen, furniture, library, ground
    ("Κατασκευή / Έδαφος  περιβάλλον / Εισαγωγή τοπογραφικού", "Έργο / Εισαγωγή / Τοπογραφικό"),
    ("Κατασκευή / Έδαφος  περιβάλλον / Υψομετρικές περιοχές / σχήματα / Τομή", "Σχέδια / Τομές"),
    ("Κατασκευή / Έδαφος  περιβάλλον / Υψομετρικές περιοχές / σχήματα / Τοιχία", "Αντικείμενο: Τοίχος / Γεωμετρία"),
    ("Κατασκευή / Έδαφος  περιβάλλον / Πισίνα", "Διαμόρφωση / Περιβάλλων χώρος"),
    ("Κατασκευή / Έδαφος  περιβάλλον / Φυτό", "Διαμόρφωση / Περιβάλλων χώρος"),
    ("Κατασκευή / Έδαφος  περιβάλλον / Μονοπάτι", "Διαμόρφωση / Περιβάλλων χώρος"),
    ("Κατασκευή / Έδαφος  περιβάλλον / Πεζοδρόμιο", "Διαμόρφωση / Περιβάλλων χώρος"),
    ("Κατασκευή / Έδαφος  περιβάλλον / Δρόμος", "Διαμόρφωση / Περιβάλλων χώρος"),
    ("Κατασκευή / Έδαφος  περιβάλλον", "Διαμόρφωση / Έδαφος"),
    ("Κατασκευή / Επιμετρήσεις  τιμές / Εξαγωγή PDF", "Σχέδια / Εκτύπωση·PDF"),
    ("Κατασκευή / Επιμετρήσεις  τιμές", "Σχέδια / Επιμετρήσεις·τιμές"),
    ("Βιβλιοθήκη / Κουζίνα  μπάνιο", "Διαμόρφωση / Κουζίνα·ντουλάπια"),
    ("Βιβλιοθήκη / Υλικά", "Διαμόρφωση / Υλικά"),
    ("Βιβλιοθήκη", "Διαμόρφωση / Βιβλιοθήκη"),
    ("Εργαλεία / Υλικό στο επιλεγμένο", "Διαμόρφωση / Υλικά"),
    ("Εργαλεία / Γλυπτική", "Διαμόρφωση / Γλυπτική"),
    ("Εργαλεία / Βοηθός", "Γραμμή εργασίας (Βοηθός)"),
    ("Εργαλεία / Μενού ποντικιού", "⚙ Ρυθμίσεις / Περιβάλλον"),
    # ---- Σχέδια / Προβολή
    ("Προβολή / Τομή", "Σχέδια / Τομές"),
    ("Προβολή / Εσωτερική όψη", "Σχέδια / Όψεις"),
    ("Προβολή / Όψεις", "Προβολή ▾ / Κάμερα 3D"),
    ("Προβολή / Κάμερες / Εικόνα 3D", "Σχέδια / Εξαγωγή"),
    ("Προβολή / Κάμερες", "Προβολή ▾ / Κάμερα 3D"),
    ("Προβολή / Απεικόνιση / Ήλιος  ουρανός / Φώτα του έργου: ρύθμιση", "Εγκαταστάσεις / Φωτισμός"),
    ("Προβολή / Απεικόνιση", "Προβολή ▾ / Απεικόνιση"),
    ("Προβολή / Εμφάνιση στο 3D", "Προβολή ▾ / Στρώσεις·εγκαταστάσεις στο 3D"),
    ("Προβολή / Ασθενή στο 3D", "Προβολή ▾ / Εγκαταστάσεις στο 3D"),
    ("Προβολή / Θέρμανση στο 3D", "Προβολή ▾ / Εγκαταστάσεις στο 3D"),
    ("Προβολή / Φώτα του έργου", "Εγκαταστάσεις / Φωτισμός"),
    ("Προβολή / Ταυτόχρονα", "Προβολή ▾ (2D·3D·Τομή)"),
    ("Προβολή / Περιβάλλον", "Προβολή ▾ / Περιβάλλον (Αρχιτεκτονικό·Φέρων·Η/Μ)"),
    ("Προβολή / Layers", "Προβολή ▾ / Layers"),
    ("Προβολή / Έλεγχος ποιότητας", "Σχέδια / Έλεγχος"),
    ("Προβολή", "⚙ Ρυθμίσεις / Περιβάλλον"),
    ("Βοήθεια / Συντομεύσεις", "⚙ Ρυθμίσεις / Χειρισμός"),
    ("Βοήθεια", "⚙ Ρυθμίσεις / Σχετικά"),
)

# The wall's object menu (sections agreed 30/10) — what exists today for each and what is missing.
WALL_MENU = (
    ("Γεωμετρία", ("Μήκος, ύψος, πάχος, x/y άκρων — Ιδιότητες (αριθμοί)", "Γραμμή αναφοράς: άξονας / παρειά — "
                   "μόνο στη σχεδίαση (Σχεδίαση τοίχου από)", "Τοιχία: ύψος από το έδαφος", "Καμπύλος: ακτίνα, τμήματα"),
     ("Γραμμή αναφοράς ενός υπάρχοντος τοίχου", "Σύνδεση με όροφο (κορυφή ως την πλάκα του επάνω ορόφου)")),
    ("Σύνθεση", ("Τύπος τοίχου (στρώσεις, U) — Ιδιότητες", "Υλικό / Υλικά ανά όψη — δεξί κλικ ▸ Υλικά, Πινέλο",
                 "Φέρων / μη φέρων"),
     ("Εσωτερική / εξωτερική πλευρά (αναστροφή στρώσεων)",)),
    ("Ανοίγματα", ("Πόρτα, Παράθυρο, Άνοιγμα, Τοξωτό — Κατασκευή ▸ Κουφώματα (κλικ στον τοίχο)",),
     ("Λίστα των κουφωμάτων ΑΥΤΟΥ του τοίχου με μετάβαση σε καθένα",)),
    ("Συνδέσεις", ("Γωνία με άλλο τοίχο, Διαχωρισμός εδώ, Μετακίνηση κατά… — δεξί κλικ ▸ Επεξεργασία τοίχου",),
     ("Γειτονικοί τοίχοι (λίστα)", "Πλάκα επάνω / κάτω", "Στέγη επάνω", "Εκκρεμότητες σύνδεσης (π.χ. τοίχος που "
      "δεν κλείνει)", "Απομόνωση: μόνο αυτός και ό,τι τον αγγίζει")),
    ("Εμφάνιση στα σχέδια", ("Layer / Περιβάλλον (Αρχιτεκτονικό·Φέρων·Η/Μ)",),
     ("Γραμμές, διαγράμμιση ανά στρώση στην κάτοψη και στην τομή",)),
)


LEAF = {}


def leaf(p):
    return LEAF.get(p, p.split(" / ")[-1])


def home(path):
    for prefix, target in RULES:
        if path.startswith(prefix):
            return target
    return "— (χωρίς θέση)"


def collect(project=None):
    import tempfile
    os.environ["ARCHFORGE_DATA"] = os.path.join(tempfile.mkdtemp(prefix="tool_map_"), "data")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import menu_smoke
    menu_smoke._patch_dialogs()
    import archforge.ui.app  # noqa: F401  — every startup layer
    from archforge.ui.main_window import MainWindow
    w = MainWindow(); w.resize(1500, 950); w.show(); app.processEvents()
    rows, where = [], {}
    for top in w.menuBar().actions():
        if top.menu() is None:
            continue
        for path, action in menu_smoke._leaves(top.menu(), (top.text().replace("&", ""),)):
            p = " / ".join(path)
            rows.append(p)
            LEAF[p] = path[-1]                      # a name may hold « / » itself (DXF / σημεία X Y Z)
            where.setdefault(id(action), []).append(p)
    groups = []
    for key, group in getattr(w, "_tool_groups", {}).items():
        for text, button in group.labelled_buttons():
            groups.append((group.windowTitle() or key, text))
    w._mark_clean(); w.close(); app.processEvents()
    return rows, where, groups


def report(rows, where, groups):
    by_home = {}
    for p in rows:
        by_home.setdefault(home(p), []).append(p)
    out = ["# Χάρτης εργαλείων (tool_map)", "",
           f"{len(rows)} εντολές μενού · {len(groups)} κουμπιά στις ορατές ομάδες. Προτεινόμενη θέση = πίνακας `RULES` "
           "στο `scripts/toolbox/tool_map.py` (για συζήτηση).", ""]
    # 1. the new map, fully expanded
    out += ["## 1. Ο νέος χάρτης (ανεπτυγμένος)", ""]
    for top in TOP:
        keys = sorted(k for k in by_home if k.startswith(top) or (top == "Αντικείμενο" and k.startswith("Αντικείμενο")))
        if top == "Αντικείμενο":
            keys = sorted(k for k in by_home if k.startswith("Αντικείμενο"))
        if not keys:
            continue
        n = sum(len(by_home[k]) for k in keys)
        out += [f"### {top} ({n})", ""]
        for k in keys:
            sub = k[len(top):].lstrip(" /") or "(κορυφή)"
            names = [leaf(p) for p in by_home[k]]
            out.append(f"- **{sub}** ({len(names)}): " + " · ".join(names))
        out.append("")
    rest = sorted(k for k in by_home if not any(k.startswith(t) for t in TOP))
    if rest:
        out += ["### Πάντα ορατά / χωρίς θέση", ""]
        for k in rest:
            out.append(f"- **{k}**: " + " · ".join(leaf(p) for p in by_home[k]))
        out.append("")
    # 2. moves: today's heading → new heading, counted
    moves = {}
    for p in rows:
        old = " / ".join(p.split(" / ")[:2]) if p.count(" / ") >= 2 else p.split(" / ")[0]
        moves.setdefault((old, home(p)), 0)
        moves[(old, home(p))] += 1
    out += ["## 2. Από πού έρχονται (σημερινή ενότητα → νέα θέση)", "", "| Σήμερα | Νέα θέση | Εντολές |", "|---|---|---|"]
    out += [f"| {o} | {h} | {n} |" for (o, h), n in sorted(moves.items())]
    out.append("")
    # 3. duplicates and misplaced
    dup_same = [ps for ps in where.values() if len(ps) > 1]
    names = {}
    for p in rows:
        names.setdefault(leaf(p).rstrip("…"), []).append(p)
    dup_name = {n: ps for n, ps in names.items() if len(ps) > 1}
    out += ["## 3. Διπλές θέσεις", "", "Ίδια εντολή σε δύο μέρη (ίδια ενέργεια):", ""]
    out += [f"- " + " **και** ".join(ps) for ps in dup_same] or ["- καμία"]
    out += ["", "Ίδιο όνομα σε διαφορετικά μέρη (να ελεγχθεί αν κάνουν το ίδιο):", ""]
    out += [f"- «{n}»: " + " · ".join(ps) for n, ps in sorted(dup_name.items())] + [""]
    out += ["Σε ενότητα που δεν είναι δική τους (σήμερα):", ""]
    for p in rows:
        h = home(p)
        if p.startswith("Κατασκευή / Η/Μ") and not h.startswith("Εγκαταστάσεις"):
            out.append(f"- {p} → {h}")
        elif p.startswith("Προβολή") and h.startswith(("Εγκαταστάσεις", "Σχέδια")):
            out.append(f"- {p} → {h}")
        elif p.startswith("Κατασκευή / Έδαφος") and h.startswith(("Έργο", "Σχέδια", "Αντικείμενο")):
            out.append(f"- {p} → {h}")
    out.append("")
    # 4. the wall's object menu, fully expanded
    out += ["## 4. Μενού αντικειμένου: Τοίχος (ανεπτυγμένο)", "",
            "Επιλέγεις τοίχο → μικρό μενού δίπλα του → ενότητες. ✓ υπάρχει σήμερα (σε ποιο σημείο) · ✗ λείπει.", ""]
    for title, have, missing in WALL_MENU:
        out.append(f"**{title}**")
        out += [f"- ✓ {h}" for h in have] + [f"- ✗ {m}" for m in missing] + [""]
    extra = sorted(k for k in by_home if k.startswith("Αντικείμενο"))
    if extra:
        out += ["Εντολές της γραμμής μενού που πηγαίνουν στο μενού αντικειμένου:", ""]
        for k in extra:
            out.append(f"- {k}: " + " · ".join(leaf(p) for p in by_home[k]))
        out.append("")
    out += ["## 5. Ορατές ομάδες εργαλείων σήμερα", "", " · ".join(f"{g} ▸ {t}" for g, t in groups), ""]
    return "\n".join(out)


def as_tree(rows):
    """``{home menu: {section: [command, …]}}`` — every command once, for mockups and tests of the new map."""
    tree = {}
    for p in rows:
        h = home(p)
        top, _, section = h.partition(" / ")
        tree.setdefault(top, {}).setdefault(section or "", []).append(leaf(p))
    return tree


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown")
    ap.add_argument("--json", help="write the new map as {menu: {section: [commands]}}")
    args = ap.parse_args()
    collected = collect()
    if args.json:
        import json
        open(args.json, "w", encoding="utf-8").write(json.dumps(as_tree(collected[0]), ensure_ascii=False, indent=1))
    text = report(*collected)
    if args.markdown:
        open(args.markdown, "w", encoding="utf-8").write(text)
    print(text)
