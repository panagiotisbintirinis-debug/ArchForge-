"""Σενάριο 2 — σύνθετο κτίριο: υπόγειο, ισόγειο σε Γ, όροφος, δύο σκάλες, τετράρριχτη (σχέδιο δοκιμής).

Υπόγειο −3,00 κάτω από το κυρίως σώμα 9,00 × 11,00 m. Ισόγειο σε σχήμα Γ: κυρίως σώμα + πτέρυγα γραφείου
9,00–14,00 × 0–6,00. Όροφος +3,00 μόνο πάνω από το κυρίως σώμα — η πτέρυγα μένει με δώμα. Κλιμακοστάσιο στο ίδιο
σημείο σε όλους τους ορόφους (4,50–9,00 × 6,00–11,00). Εξωτερικοί τοίχοι 25 cm, εσωτερικοί 10 cm, ύψος 2,70 m.
"""
from __future__ import annotations

from archforge.scenarios.common import Scenario

KEY = "02"
TITLE = "Σύνθετο κτίριο: υπόγειο, ισόγειο σε Γ, όροφος, σκάλες, τετράρριχτη"
EXT, INT = 0.25, 0.10
MAIN = [(0.0, 0.0), (9.0, 0.0), (9.0, 11.0), (0.0, 11.0), (0.0, 0.0)]
GAMMA = [(0.0, 0.0), (14.0, 0.0), (14.0, 6.0), (9.0, 6.0), (9.0, 11.0), (0.0, 11.0), (0.0, 0.0)]
STAIR = ((5.2, 6.6), (5.2, 10.4))           # click at the start, pointer along the run
LEVELS = (("Basement", -3.0), ("Ground", 0.0), ("Floor 1", 3.0))


def _chain(s, corners, thickness):
    for a, b in zip(corners, corners[1:]):
        s.wall(a, b, thickness)


def _floors(s, window, name):
    def run():
        slab = window._create_auto_floors()
        if slab is None:
            raise ValueError("δεν δημιουργήθηκε δάπεδο")
        from archforge.architecture import storey_slabs as S
        g = S.storey_slab_geometry(window.doc, slab)
        return f"πλάκα δαπέδου {g['area']:.2f} m²" if g else "πλάκα δαπέδου (χωρίς γεωμετρία)"
    s.step(f"Δάπεδα (αυτόματα) — {name}", run)


def build(window):
    s = Scenario(KEY, TITLE, window)
    # 1. Ground floor in Γ: outline, wing wall, living / kitchen / stair hall.
    _chain(s, GAMMA, EXT)
    s.wall((9.0, 0.0), (9.0, 6.0), INT)
    s.wall((0.0, 6.0), (9.0, 6.0), INT)
    s.wall((4.5, 6.0), (4.5, 11.0), INT)
    s.opening("door", 3.0, 0.0, 1.00, label="Πόρτα εισόδου")
    s.opening("window", 1.2, 0.0, 1.40, label="Παράθυρο σαλονιού (Ν)")
    s.opening("window", 6.5, 0.0, 2.00, label="Μπαλκονόπορτα σαλονιού (Ν)", height=2.20, sill=0.0)
    s.opening("window", 0.0, 3.0, 1.40, label="Παράθυρο σαλονιού (Δ)")
    s.opening("window", 2.2, 11.0, 1.20, label="Παράθυρο κουζίνας (Β)")
    s.opening("window", 11.5, 0.0, 1.60, label="Παράθυρο γραφείου (Ν)")
    s.opening("window", 14.0, 3.0, 1.20, label="Παράθυρο γραφείου (Α)")
    s.opening("door", 12.0, 6.0, 0.90, label="Πόρτα γραφείου προς αυλή (Β)")
    s.opening("door", 9.0, 3.0, 0.80, label="Πόρτα σαλονιού–γραφείου")
    s.opening("door", 2.2, 6.0, 0.80, label="Πόρτα κουζίνας")
    s.opening("door", 7.0, 6.0, 1.00, label="Άνοιγμα κλιμακοστασίου (ισόγειο)")
    _floors(s, window, "ισόγειο")
    # 2. Basement −3,00 under the main body: storage + stair hall.
    s.level("Basement", -3.0)
    _chain(s, MAIN, EXT)
    s.wall((0.0, 6.0), (9.0, 6.0), INT)
    s.wall((4.5, 6.0), (4.5, 11.0), INT)
    s.opening("window", 2.2, 0.0, 1.00, height=0.50, sill=1.90, label="Φεγγίτης υπογείου (Ν)")
    s.opening("window", 6.5, 0.0, 1.00, height=0.50, sill=1.90, label="Φεγγίτης υπογείου (Ν) 2")
    s.opening("door", 7.0, 6.0, 1.00, label="Άνοιγμα κλιμακοστασίου (υπόγειο)")
    _floors(s, window, "υπόγειο")
    # 3. First floor +3,00 over the main body only: two bedrooms, bath, stair hall.
    s.level("Floor 1", 3.0)
    _chain(s, MAIN, EXT)
    s.wall((0.0, 6.0), (9.0, 6.0), INT)
    s.wall((4.5, 0.0), (4.5, 11.0), INT)
    s.opening("window", 2.2, 0.0, 1.40, label="Παράθυρο υπνοδωματίου 1 (Ν)")
    s.opening("window", 6.7, 0.0, 1.40, label="Παράθυρο υπνοδωματίου 2 (Ν)")
    s.opening("window", 9.0, 3.0, 1.20, label="Μπαλκονόπορτα υπνοδωματίου 2 προς δώμα (Α)", height=2.20, sill=0.0)
    s.opening("window", 2.2, 11.0, 0.60, height=0.60, sill=1.50, label="Παράθυρο μπάνιου (Β)")
    s.opening("window", 9.0, 8.5, 1.00, label="Παράθυρο κλιμακοστασίου (Α)")
    s.opening("door", 2.2, 6.0, 0.80, label="Πόρτα υπνοδωματίου 1")
    s.opening("door", 7.0, 6.0, 0.80, label="Πόρτα υπνοδωματίου 2")
    s.opening("door", 4.5, 8.5, 0.80, label="Πόρτα μπάνιου")
    _floors(s, window, "όροφος")
    # 4. Two stairs at the same place: basement → ground, ground → first floor.
    s.level("Basement")
    s.stair(*STAIR)
    s.level("Ground")
    s.stair(*STAIR)
    # 5. Hip roof over the top storey; the uncovered ground-floor wing gets its terrace in the same step.
    s.level("Floor 1")

    def roof():
        made = window._create_pitched_roof("hip")
        if not made:
            raise ValueError("δεν δημιουργήθηκε στέγη")
        return "τετράρριχτη κεραμοσκεπή"
    s.step("Κεραμοσκεπή τετράρριχτη (μενού)", roof)

    def ceilings():
        n = window._attic_ceilings("slab")
        if not n:
            raise ValueError("δεν βρέθηκε χώρος κάτω από κεραμοσκεπή χωρίς οροφή")
        return f"οροφή (πλάκα) σε {n} χώρους στο ύψος των τοίχων"
    s.step("Οροφή κάτω από την κεραμοσκεπή — πλάκα (μενού)", ceilings)
    return s


def checks(s):
    ents = list(s.doc.entities.values())
    s.check("Όροφοι", all(n in s.doc.levels for n, _z in LEVELS),
            " · ".join(f"{n} {z:+.2f}" for n, z in sorted(s.doc.levels.items(), key=lambda kv: kv[1])))
    for name, z in LEVELS:
        walls = [e for e in ents if e.kind == "wall" and abs(float(e.params["z"]) - z) < 1e-4]
        s.check(f"Τοίχοι — {name}", len(walls) >= 6, f"{len(walls)} τοίχοι στα {z:+.2f}")
    for name, z in LEVELS:
        floors = [e for e in ents if e.kind == "room_floor" and abs(float(e.params.get("level_z", -99)) - z) < 1e-4]
        s.check(f"Δάπεδο — {name}", len(floors) >= 1, f"{len(floors)} πλάκα/ες")
    stairs = [e for e in ents if e.kind == "stair"]
    s.check("Σκάλες", len(stairs) == 2, f"{len(stairs)} από 2")
    openings = [e for e in ents if e.kind in ("door", "window")]
    s.check("Κουφώματα στο έργο", len(openings) == 22, f"{len(openings)} από 22")
    roofs = [e for e in ents if e.kind == "pitched_roof"]
    s.check("Κεραμοσκεπή", len(roofs) >= 1, f"{len(roofs)} κομμάτια")
    terraces = [e for e in ents if e.kind == "room_roof"]
    s.check("Δώμα πάνω από την πτέρυγα του ισογείου", len(terraces) >= 1, f"{len(terraces)} δώμα/τα")
    ceilings = [e for e in ents if e.kind == "room_ceiling"]
    top = len(s.doc.active_room_faces(z=3.0))
    s.check("Οροφή κάτω από την κεραμοσκεπή μόνο στους χώρους του ορόφου", len(ceilings) == top,
            f"{len(ceilings)} οροφές για {top} χώρους του ορόφου (όχι στο ισόγειο/υπόγειο: εκεί είναι η πλάκα από πάνω)")
    undo_ok = True
    n = len(s.doc.entities)
    try:
        s.stack.undo(); s.stack.redo()
    except Exception:                                     # noqa: BLE001
        undo_ok = False
    s.check("Αναίρεση / επανάληψη της τελευταίας ενέργειας", undo_ok and len(s.doc.entities) == n)


NOTES = """## Ευρήματα του agent

1. **Διορθώθηκε:** η «Οροφή σοφίτας κάτω από κεραμοσκεπή» έβαζε ταβάνι και στους χώρους του ισογείου και του
   υπογείου (ό,τι βρισκόταν κάτω από τη στέγη σε κάτοψη) — 10 οροφές αντί για 4. Τώρα μόνο σε χώρους χωρίς όροφο από
   πάνω (`roof_need.attic_rooms`, ίδιος κανόνας κάλυψης με το «Διόρθωση στεγών»).
2. **Προς έλεγχο:** η κάτοψη του ορόφου (`02_syntheto_katopsi.png`) δεν δείχνει ούτε τη σκάλα που ανεβαίνει από το
   ισόγειο ούτε οπή στην πλάκα. Να δούμε στα Windows αν στο 3D η πλάκα του ορόφου είναι κομμένη πάνω από τη σκάλα.
3. Τα ονόματα ορόφων στο αρχείο είναι «Basement», «Ground», «Floor 1» (ίδια με τα εργαλεία)· η ετικέτα στο UI τα
   μεταφράζει — αν κάπου εμφανίζονται στα αγγλικά, σημειώστε το.

## Τι να ελέγξετε εσείς (Windows)

1. Ανοίξτε `docs/scenarios/02_syntheto.archforge` (Αρχείο ▸ Άνοιγμα).
2. **Επιλογέας ορόφων:** Υπόγειο −3,00 · Ισόγειο 0,00 · Όροφος +3,00 — αλλάζει σωστά η κάτοψη;
3. **Κάτοψη ανά όροφο:** χώροι, κουφώματα, σκάλα στο ίδιο σημείο σε κάθε όροφο, οπή στην πλάκα πάνω από τη σκάλα;
4. **3D:** τετράρριχτη πάνω στο κυρίως σώμα, δώμα πάνω από την πτέρυγα του γραφείου, υπόγειο κάτω από το έδαφος —
   κάτι λάθος ή άσχημο;
5. **Επεξεργασία:** μετακινήστε τον τοίχο της πτέρυγας (x = 14) — ακολουθεί το δώμα; δουλεύει η αναίρεση;
6. Γράψτε μου ό,τι δυσκόλεψε ή φάνηκε λάθος, με αριθμό βήματος από εδώ αν γίνεται.
"""
