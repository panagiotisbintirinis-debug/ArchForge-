"""Σενάριο 1 — ισόγεια μονοκατοικία ~100 m² με δίρριχτη κεραμοσκεπή (σχέδιο δοκιμής).

Περίγραμμα 12,00 × 8,50 m στους άξονες, εξωτερικοί τοίχοι 25 cm, εσωτερικοί 10 cm, ύψος 2,70 m
(η προεπιλογή του εργαλείου τοίχου).  Σαλόνι-κουζίνα αριστερά, δεξιά υπνοδωμάτιο πάνω και
μπάνιο / δεύτερο υπνοδωμάτιο κάτω.  Είσοδος στη νότια πλευρά.
"""
from __future__ import annotations

from archforge.scenarios.common import Scenario

KEY = "01"
TITLE = "Ισόγεια μονοκατοικία ~100 m², δίρριχτη στέγη"
EXT, INT = 0.25, 0.10


def build(window):
    s = Scenario(KEY, TITLE, window)
    # 1. Outline, drawn as a chain like the wall tool: every wall starts where the last one ended.
    corners = [(0.0, 0.0), (12.0, 0.0), (12.0, 8.5), (0.0, 8.5), (0.0, 0.0)]
    for a, b in zip(corners, corners[1:]):
        s.wall(a, b, EXT)
    # 2. Interior walls.
    s.wall((6.5, 0.0), (6.5, 8.5), INT)
    s.wall((6.5, 4.2), (12.0, 4.2), INT)
    s.wall((9.0, 0.0), (9.0, 4.2), INT)
    # 3. Openings (door/window tool on the wall axis).
    s.opening("door", 3.0, 0.0, 1.00, label="Πόρτα εισόδου")
    s.opening("window", 1.2, 0.0, 1.40, label="Παράθυρο σαλονιού (Ν)")
    s.opening("window", 3.2, 8.5, 1.60, label="Παράθυρο σαλονιού (Β)")
    s.opening("window", 5.6, 8.5, 1.00, label="Παράθυρο κουζίνας (Β)")
    s.opening("window", 12.0, 6.3, 1.40, label="Παράθυρο υπνοδωματίου 1 (Α)")
    s.opening("window", 12.0, 2.0, 1.20, label="Παράθυρο υπνοδωματίου 2 (Α)")
    s.opening("window", 7.75, 0.0, 0.60, height=0.60, sill=1.50, label="Παράθυρο μπάνιου (Ν)")
    s.opening("door", 6.5, 6.3, 0.80, label="Πόρτα υπνοδωματίου 1")
    s.opening("door", 6.5, 2.0, 0.80, label="Πόρτα μπάνιου")
    s.opening("door", 10.5, 4.2, 0.80, label="Πόρτα υπνοδωματίου 2")
    # 4. Roof from the menu action («Κεραμοσκεπή δίρριχτη»).
    def roof():
        made = window._create_pitched_roof("gable")
        if not made:
            raise ValueError("δεν δημιουργήθηκε στέγη")
        return f"{len(made) if isinstance(made, (list, tuple)) else 1} στέγη/ες"
    s.step("Κεραμοσκεπή δίρριχτη (μενού)", roof)
    return s


def checks(s):
    walls = [e for e in s.doc.entities.values() if e.kind == "wall"]
    s.check("Τοίχοι στο έργο", len(walls) >= 7, f"{len(walls)} τοίχοι (7 σχεδιάστηκαν· οι διασταυρώσεις μπορεί να τους χωρίζουν)")
    rooms = s.rooms()
    s.check("Χώροι που αναγνωρίστηκαν από τους τοίχους", len(rooms) == 4,
            " · ".join(f"{n or '—'} {a:.2f} m²" for n, a in rooms))
    # Clear areas between wall faces (ext 25, int 10 cm): the four rooms of the design.
    expected = sorted([(6.5 - 0.125 - 0.05) * (8.5 - 0.25), (12.0 - 6.5 - 0.05 - 0.125) * (8.5 - 4.2 - 0.05 - 0.125),
                       (9.0 - 6.5 - 0.10) * (4.2 - 0.125 - 0.05), (12.0 - 9.0 - 0.05 - 0.125) * (4.2 - 0.125 - 0.05)],
                      reverse=True)
    got = [a for _n, a in rooms]
    if len(got) == 4:
        worst = max(abs(g - e) for g, e in zip(got, expected))
        s.check("Εμβαδά χώρων = καθαρά εμβαδά ανάμεσα στις παρειές", worst < 0.15,
                "αναμενόμενα " + " / ".join(f"{e:.2f}" for e in expected) + f" m² · μέγιστη διαφορά {worst:.2f} m²")
    openings = [e for e in s.doc.entities.values() if e.kind in ("door", "window")]
    s.check("Κουφώματα στο έργο", len(openings) == 10, f"{len(openings)} από 10")
    roofs = [e for e in s.doc.entities.values() if e.kind == "pitched_roof"]
    s.check("Στέγη", len(roofs) >= 1, f"{len(roofs)} στέγη/ες")
    undo_ok = True
    n = len(s.doc.entities)
    try:
        s.stack.undo(); s.stack.redo()
    except Exception:                                     # noqa: BLE001
        undo_ok = False
    s.check("Αναίρεση / επανάληψη της τελευταίας ενέργειας", undo_ok and len(s.doc.entities) == n)


NOTES = """## Ευρήματα του agent (προς απόφαση / έλεγχο από τον ιδιοκτήτη)

1. **Εμβαδά χώρων στην κάτοψη = στους άξονες των τοίχων, όχι καθαρά.** Το σαλόνι γράφει 55,25 m² (6,50 × 8,50 στους
   άξονες)· το καθαρό ανάμεσα στις παρειές είναι ~52,18 m². Η επιμέτρηση (`quantities/takeoff.py`) χρησιμοποιεί καθαρά —
   άρα κάτοψη και επιμέτρηση δείχνουν διαφορετικό εμβαδό για τον ίδιο χώρο. **Απόφαση:** καθαρό στην ετικέτα (και το
   «στους άξονες» στις Ιδιότητες), ή και τα δύο;
2. **Ο τοίχος στην κάτοψη σχεδιάζεται ως μία γραμμή 3,5 cm στον άξονα, όχι με το πάχος του** (25 cm εξωτερικοί, 10 cm
   εσωτερικοί φαίνονται ίδιοι). Σε μεγέθυνση δεν ξεχωρίζουν παρειές, γωνίες, ενώσεις. **Ελέγξτε στα Windows** αν το
   βλέπετε κι εσείς έτσι· αν ναι, προτείνω σχεδίαση με τις δύο παρειές και γέμισμα (όπως σε κάθε αρχιτεκτονικό σχέδιο).
3. Οι τοίχοι παίρνουν όνομα «Wall» (αγγλικά) — να γίνει «Τοίχος Τn»;
4. Οι χώροι μένουν «Χώρος 1…4» μέχρι να τους δώσει όνομα ο χρήστης — αναμενόμενο, απλώς σημειώνεται.

## Τι να ελέγξετε εσείς (Windows)

1. Ανοίξτε `docs/scenarios/01_monokatoikia.archforge` (Αρχείο ▸ Άνοιγμα).
2. **Κάτοψη:** 4 χώροι; πόρτες/παράθυρα στη σωστή θέση και φορά; πάχος τοίχων (εύρημα 2);
3. **3D:** τοίχοι, κουφώματα, δίρριχτη στέγη πάνω στο περίγραμμα — κάτι λάθος ή άσχημο;
4. **Επεξεργασία:** μετακινήστε έναν εσωτερικό τοίχο, αλλάξτε ένα παράθυρο, μετονομάστε έναν χώρο — ακολουθούν οι χώροι
   και η στέγη; δουλεύει η αναίρεση;
5. Γράψτε μου ό,τι δυσκόλεψε ή φάνηκε λάθος, με αριθμό βήματος από εδώ αν γίνεται.
"""
