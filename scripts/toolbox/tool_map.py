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
and what is missing there.  The homes are ``RULES`` of ``archforge/ui/menu_map.py`` — since 30/10 (owner «ναι στο 4»)
the program builds its menus from the same table, so a change there moves the command in the program too.

Run (cloud):  QTWEBENGINE_DISABLE_SANDBOX=1 QT_QPA_PLATFORM=offscreen python scripts/toolbox/tool_map.py --markdown out.md
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from archforge.ui.menu_map import RULES, TOP, home  # noqa: E402,F401 — the one table of homes


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



def collect(project=None):
    import tempfile
    os.environ["ARCHFORGE_DATA"] = os.path.join(tempfile.mkdtemp(prefix="tool_map_"), "data")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import menu_smoke
    from archforge.ui.main_menus import old_menu_path
    menu_smoke._patch_dialogs()
    import archforge.ui.app  # noqa: F401  — every startup layer
    from archforge.ui.main_window import MainWindow
    w = MainWindow(); w.resize(1500, 950); w.show(); app.processEvents()
    rows, where = [], {}
    for top in w.menuBar().actions():
        if top.menu() is None:
            continue
        for path, action in menu_smoke._leaves(top.menu(), (top.text().replace("&", ""),)):
            # The homes are written against the old menus: read each command's old path (main_menus).
            p = old_menu_path(action) or " / ".join(path)
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
           f"{len(rows)} εντολές μενού · {len(groups)} κουμπιά στις ορατές ομάδες. Θέση = πίνακας `RULES` "
           "στο `archforge/ui/menu_map.py` (από αυτόν χτίζονται και τα μενού του προγράμματος).", ""]
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
