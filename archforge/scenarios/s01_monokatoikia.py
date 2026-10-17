"""S01 — ισόγεια μονοκατοικία ~100 m² με δίρριχτη εμφανή κεραμοσκεπή (σχέδιο δοκιμής).

Περίγραμμα 12,00 × 8,50 m στους άξονες, εξωτερικοί τοίχοι 25 cm, εσωτερικοί 10 cm, ύψος 2,70 m.
Σαλόνι με ανοιχτή κουζίνα αριστερά (0–6,50)· δεξιά διάδρομος 3,60–4,80 που οδηγεί σε υπνοδωμάτιο 1 (βόρεια),
μπάνιο και υπνοδωμάτιο 2 (νότια) — κανένα δωμάτιο δεν περνιέται μέσα από άλλο. Είσοδος στη νότια πλευρά.
Περιέχει κουζίνα, μπάνιο, έπιπλα, ύδρευση, αποχέτευση, ηλεκτρολογικά, φέροντα οργανισμό και προσφορά.
"""
from __future__ import annotations

from archforge.scenarios.common import Scenario

KEY = "01"
NAME = "S01_monokatoikia"
TITLE = "Ισόγεια μονοκατοικία ~100 m², δίρριχτη εμφανής κεραμοσκεπή"
EXT, INT = 0.25, 0.10
ROOMS = {"Σαλόνι – κουζίνα": (3.0, 4.0), "Διάδρομος": (9.0, 4.2), "Υπνοδωμάτιο 1": (9.0, 6.6),
         "Μπάνιο": (7.75, 1.8), "Υπνοδωμάτιο 2": (10.5, 1.8)}


def build(window):
    s = Scenario(KEY, TITLE, window)
    # 1. Outline, drawn as a chain like the wall tool.
    corners = [(0.0, 0.0), (12.0, 0.0), (12.0, 8.5), (0.0, 8.5), (0.0, 0.0)]
    for a, b in zip(corners, corners[1:]):
        s.wall(a, b, EXT)
    # 2. Interior walls: living | corridor between the two bedroom sides.
    s.wall((6.5, 0.0), (6.5, 8.5), INT)
    s.wall((6.5, 4.8), (12.0, 4.8), INT)
    s.wall((6.5, 3.6), (12.0, 3.6), INT)
    s.wall((9.0, 0.0), (9.0, 3.6), INT)
    # 3. Openings (door/window tool on the wall axis).
    s.opening("door", 3.0, 0.0, 1.00, label="Πόρτα εισόδου")
    s.opening("window", 1.2, 0.0, 1.40, label="Παράθυρο σαλονιού (Ν)")
    s.opening("window", 5.0, 0.0, 1.60, label="Μπαλκονόπορτα σαλονιού (Ν)", height=2.20, sill=0.0)
    s.opening("window", 2.0, 8.5, 1.20, label="Παράθυρο κουζίνας (Β)")
    s.opening("window", 0.0, 4.0, 1.40, label="Παράθυρο σαλονιού (Δ)")
    s.opening("window", 12.0, 6.6, 1.40, label="Παράθυρο υπνοδωματίου 1 (Α)")
    s.opening("window", 9.2, 8.5, 1.20, label="Παράθυρο υπνοδωματίου 1 (Β)")
    s.opening("window", 12.0, 1.8, 1.20, label="Παράθυρο υπνοδωματίου 2 (Α)")
    s.opening("window", 7.75, 0.0, 0.60, height=0.60, sill=1.50, label="Παράθυρο μπάνιου (Ν)")
    s.opening("door", 6.5, 4.2, 0.90, label="Πόρτα σαλονιού – διαδρόμου")
    s.opening("door", 8.0, 4.8, 0.80, label="Πόρτα υπνοδωματίου 1")
    s.opening("door", 7.75, 3.6, 0.80, label="Πόρτα μπάνιου")
    s.opening("door", 10.5, 3.6, 0.80, label="Πόρτα υπνοδωματίου 2")
    # 4. Room use (right click in the room ▸ Χρήση χώρου): the kitchen is open to the living room.
    for name, xy in ROOMS.items():
        s.name_room(*xy, name)
    # 5. Floor slab («Δάπεδα (αυτόματα)») and the tiled roof, exposed (no attic ceiling — owner 17/10).
    def floors():
        slab = window._create_auto_floors()
        if slab is None:
            raise ValueError("δεν δημιουργήθηκε δάπεδο")
        from archforge.architecture import storey_slabs as S
        g = S.storey_slab_geometry(window.doc, slab)
        return f"πλάκα δαπέδου {g['area']:.2f} m²" if g else "πλάκα δαπέδου (χωρίς γεωμετρία)"
    s.step("Δάπεδα (αυτόματα)", floors)

    def roof():
        if not window._create_pitched_roof("gable"):
            raise ValueError("δεν δημιουργήθηκε στέγη")
        return "δίρριχτη κεραμοσκεπή, εμφανής"
    s.step("Κεραμοσκεπή δίρριχτη (μενού)", roof)
    # 6. Kitchen and bathroom («Κουζίνα εδώ» / «Μπάνιο εδώ»).
    s.layout("kitchen", 3.0, 7.5)
    s.layout("bath", 7.75, 1.8, wet="shower")
    # 7. Furniture from the Library (dragged in, backs snap to the walls).
    for name, x, y, turn in (("Έπιπλο TV", 0.4, 2.2, 0.0), ("Καναπές τριθέσιος", 3.3, 2.2, 90.0),
                             ("Τραπεζάκι σαλονιού", 2.0, 2.2, 0.0), ("Τραπέζι τραπεζαρίας 6θέσιο", 4.6, 5.0, 0.0),
                             ("Διπλό κρεβάτι 160×200", 10.4, 7.4, 0.0), ("Κομοδίνο", 9.3, 7.9, 0.0),
                             ("Κομοδίνο", 11.5, 7.9, 0.0), ("Συρταριέρα 3 συρτάρια", 7.4, 6.4, 90.0),
                             ("Μονό κρεβάτι 90×200", 11.3, 1.2, 0.0), ("Γραφείο εργασίας 140", 9.35, 2.3, 0.0)):
        s.furniture(name, x, y, turn)
    # 8. Plumbing: the kitchen and bathroom layouts already put their points at the fixtures; add the supply,
    #    the electric water heater and the washing machine.
    for tool, x, y in (("plumb_water_supply", 3.6, 0.2), ("plumb_water_heater", 8.6, 3.3),
                       ("plumb_washing_machine", 8.6, 2.2)):
        s.point(tool, x, y)
    # 9. Drainage: floor drain in the bathroom, manhole outside.
    s.point("drain_floor_drain", 7.6, 1.5)
    s.point("drain_manhole", 7.75, -1.5)
    # 10. Electrical: panel in the corridor, lights, switches by the doors, sockets, appliances, network.
    for tool, x, y in (("elec_panel", 11.9, 4.2), ("elec_network_rack", 11.9, 4.6),
                       ("elec_light", 3.2, 4.2), ("elec_light", 3.2, 7.0), ("elec_light", 9.2, 4.2),
                       ("elec_light", 9.2, 6.6), ("elec_light", 7.75, 1.8), ("elec_light", 10.5, 1.8),
                       ("elec_switch", 3.6, 0.15), ("elec_switch", 6.4, 3.6), ("elec_switch", 7.0, 4.7),
                       ("elec_switch", 8.5, 4.9), ("elec_switch", 7.25, 3.5), ("elec_switch", 10.0, 3.5),
                       ("elec_socket", 0.15, 1.2), ("elec_socket", 0.15, 6.0), ("elec_socket", 2.0, 3.9),
                       ("elec_socket", 9.0, 8.35), ("elec_socket", 11.85, 7.9), ("elec_socket", 11.85, 0.9),
                       ("elec_socket", 9.15, 0.3), ("elec_kitchen_socket", 1.0, 8.3), ("elec_kitchen_socket", 3.4, 8.3),
                       ("elec_water_heater", 8.7, 3.45), ("elec_washing_machine", 8.85, 2.4),
                       ("elec_air_conditioner", 0.15, 2.5), ("elec_air_conditioner", 11.85, 6.0),
                       ("elec_data_outlet", 2.0, 3.95), ("elec_tv_outlet", 2.3, 3.95), ("elec_wifi_ap", 4.0, 4.2)):
        s.point(tool, x, y)
    # Appliances placed by the kitchen layout get their supply on the wall behind them.
    for appliance, tool in (("Εστία", "elec_cooker"), ("Πλυντήριο πιάτων", "elec_dishwasher"),
                            ("Ψυγειοκαταψύκτης", "elec_socket"), ("Απορροφητήρας", "elec_socket")):
        xy = s.at_wall_behind(appliance)
        if xy is None:
            s.step(f"Παροχή για «{appliance}»", lambda a=appliance: (_ for _ in ()).throw(ValueError(f"δεν βρέθηκε {a}")))
        else:
            s.point(tool, *xy)
    # 11. Foundation (owner 17/10): strip footings in every column line — they share the base moments with the
    #     footings and take the most of them (dialog «Στοιχεία κτιρίου για στατική» ▸ Θεμελίωση).
    def foundation():
        from archforge.structure.analysis.settings import get_settings
        params = {**get_settings(window.doc), "foundation_type": "strips"}
        window._apply_structural_settings(params)
        return "Πεδιλοδοκοί σε όλους τους άξονες (εσχάρα)"
    s.step("Θεμελίωση: πεδιλοδοκοί (Στοιχεία κτιρίου για στατική)", foundation)
    # 12. Load-bearing frame: columns, beams, footings in one go, then the analysis.
    def structure():
        out = window._design_structure()
        res = out.get("result") or {}
        if res.get("error"):
            raise ValueError(res["error"])
        from archforge.structure.design_all import summary
        return summary(out)
    s.step("Φέρων οργανισμός: κολόνες, δοκοί, πέδιλα (μενού Δομικά)", structure)
    return s


# Checks waiting on an owner decision (S01_REPORT.md says which): the gate test lets only these fail.
# Θέρμανση: no tool yet (owner decides). Κόμβοι: Codex's capacity-joint flags (ΣMRc/ΣMRb < 1,30, an UNVERIFIED
# criterion) became warnings on merge — examined by an engineer, never waived or «fixed» by resizing here.
OWNER_PENDING = ("Θέρμανση/HVAC", "Προειδοποίηση: Κόμβος")

C1 = "d49c98f"          # walls with both faces, opening symbols
C2 = "278d361"          # the gate's first round of fixes
C3 = "8535f4b"          # strip footings sharing the base moments
FINDINGS = [
    {"status": "FIXED", "found": "Τοίχοι στην κάτοψη ως γραμμή στον άξονα — 25 και 10 cm ίδιοι (απόφαση ιδιοκτήτη 3)",
     "fix": "Δύο παρειές + γέμισμα, ενώσεις κλειστές, ανοίγματα κομμένα", "files": ["core/plan_scene.py", "ui/plan_view.py"], "commit": C1},
    {"status": "FIXED", "found": "Βασικές πόρτες/παράθυρα χωρίς σύμβολο στην κάτοψη (μόνο γραμμή)",
     "fix": "Προεπιλεγμένο σύμβολο (φύλλο + τόξο, φύλλα παραθύρου)", "files": ["architecture/joinery.py", "core/plan_scene.py"], "commit": C1},
    {"status": "FIXED", "found": "Σχέδιο S01: υπνοδωμάτιο 2 μόνο μέσα από υπνοδωμάτιο 1",
     "fix": "Διάδρομος 3,60–4,80· έλεγχος «κανένα ιδιωτικό δωμάτιο πέρασμα»", "files": ["scenarios/s01_monokatoikia.py", "scenarios/gate.py"], "commit": C2},
    {"status": "FIXED", "found": "Πόρτα μπάνιου άνοιγε προς τον διάδρομο (φορά από τη φορά σχεδίασης του τοίχου)",
     "fix": "Εσωτερική πόρτα ανοίγει προς τον χώρο που εξυπηρετεί (ιδιωτικό, αλλιώς τον μικρότερο)",
     "files": ["architecture/joinery.py", "rendering/fixtures.py", "core/plan_scene.py"], "commit": C2},
    {"status": "FIXED", "found": "Ζεστό νερό: τα τμήματα μετατοπίζονταν χωριστά — κενό 5–10 cm σε κάθε γωνία (10 κομμάτια)",
     "fix": "Μία μετατόπιση για όλο το δίκτυο· στους συλλέκτες ο κατακόρυφος ακολουθεί τον δικό του σωλήνα", "files": ["mep/plumbing.py"], "commit": C2},
    {"status": "FIXED", "found": "Ετικέτες Η/Μ η μία πάνω στην άλλη (νεροχύτης, σιφώνι, πίνακας)",
     "fix": "Τοποθέτηση χωρίς επικάλυψη· όποια δεν χωρά φαίνεται από το ζουμ που χωρά", "files": ["core/plan_scene.py"], "commit": C2},
    {"status": "FIXED", "found": "Ονόματα «Wall», «Door», «Window», «Stair»", "fix": "«Τοίχος 3», «Πόρτα 2» …",
     "files": ["core/interaction.py"], "commit": C2},
    {"status": "FIXED", "found": "Έπιπλα/είδη υγιεινής/συσκευές δεν έμπαιναν στην προσφορά",
     "fix": "Λίστα «Έπιπλα» (κωδικός asset:… ίδιος σε κάθε έργο)", "files": ["quantities/materials.py"], "commit": C2},
    {"status": "FIXED", "found": "Προσφορά χωρίς σύνολα ανά ειδικότητα", "fix": "quote()['by_trade'] + γραμμή συνόλου ανά ειδικότητα στο PDF",
     "files": ["quantities/quote.py", "output/pdf.py"], "commit": C2},
    {"status": "FIXED", "found": "Χωρίς κοινό τιμοκατάλογο — οι τιμές ζούσαν μόνο μέσα σε κάθε έργο",
     "fix": "price_book.json στον φάκελο χρήστη· κουμπί «Στον κοινό τιμοκατάλογο»· η τιμή του έργου υπερισχύει· πηγή τιμής σε κάθε γραμμή",
     "files": ["quantities/price_book.py", "quantities/quote.py", "ui/trades_tab.py"], "commit": C2},
    {"status": "FIXED", "found": "Σελίδα 3D: σκηνή που έφτανε πριν φορτώσει η σελίδα σταματούσε το script στο «walkMode»",
     "fix": "Οι εκκρεμείς κλήσεις εφαρμόζονται στο τέλος της σελίδας", "files": ["ui/pbr_viewport.py"], "commit": C2},
    {"status": "FIXED", "found": "Στιγμιότυπα 3D/Φέροντος δεν έβγαιναν στο cloud",
     "fix": "Η ίδια σελίδα 3D σε headless Chromium (SwiftShader)", "files": ["scenarios/render3d.py", "ui/pbr_viewport.py"], "commit": C2},
    {"status": "FIXED", "found": "Πέδιλα Κ1, Κ4, Κ8: στον σεισμό η συνισταμένη βγαίνει έξω από το πέδιλο (ανατροπή)",
     "fix": "Απόφαση ιδιοκτήτη: πεδιλοδοκοί που μοιράζονται τις ροπές με τα πέδιλα και παίρνουν τις περισσότερες — "
            "έλεγχος ανατροπής/πίεσης σε κάθε πεδιλοδοκό, το πέλμα φαρδαίνει όσο χρειάζεται (S01: 6 πεδιλοδοκοί, όλοι ευσταθείς, "
            "σmax 41–56 kPa· σκυρόδεμα 33 m³ αντί 15,4 με πέδιλα)",
     "files": ["structure/foundation.py", "structure/analysis/__init__.py"], "commit": C3},
    {"status": "OPEN", "found": "Θέρμανση: mep/heating.py μόνο απογραφή — κανένα εργαλείο στο UI, καμία όδευση",
     "fix": "Απόφαση ιδιοκτήτη για το εύρος", "files": [], "commit": ""},
]

NOTES = """## Τι να ελέγξετε εσείς (Windows)

1. Ανοίξτε `docs/scenarios/S01_monokatoikia.archforge` (Αρχείο ▸ Άνοιγμα) — ανοίγει στο Αρχιτεκτονικό περιβάλλον.
2. **Κάτοψη:** τοίχοι με το πάχος τους, σύμβολα κουφωμάτων, χώροι με ονόματα και καθαρά εμβαδά, κουζίνα, μπάνιο,
   έπιπλα· κάτι λάθος ή άσχημο;
3. **3D:** εμφανής κεραμοσκεπή με εσωτερικούς τοίχους ως τη στέγη, δάπεδο, κουζίνα/έπιπλα.
4. **Η/Μ:** σωληνώσεις, αποχέτευση, καλώδια — διαβάζονται;
5. Γράψτε μου ό,τι δυσκόλεψε ή φάνηκε λάθος.
"""
