"""ArchForge core library, second set (2026-10): more rooms, more types.

Built the same way as ``catalog.py``: generic types modelled from simple
solids with standard real-world dimensions; pictures are visual reference
only, never copied, no brands.  Each item states its size (``expect_cm``),
is checked against it and on a verification sheet (``asset_preview.py``).

The dimension each item is anchored to is noted next to it.
Front faces -Y, backs +Y, Z up, centimetres.
"""
from archforge.library.catalog import (APPLIANCE, BLACK, CERAMIC, CHROME, FABRIC_BLUE, FABRIC_GREY, FABRIC_SAND, GLASS,
                                       GLASS_DARK, GREEN, LAMP, MATTRESS, OAK, PINE, STEEL, STONE, TERRACOTTA, WALNUT,
                                       WHITE, B, C, E, R, T, appliance, bed, dining_table, legs)

BRICK, COPPER, WATER, LIGHT_GREY, TEAK = "#a0563b", "#b87333", "#6fa9bd", "#d9d9d6", "#8a6e55"


# ------------------------------------------------------------------ living room
def corner_sofa():
    # seat 42–52, back 85, chaise 90 deep on the right
    w, d, h, arm = 260, 180, 85, 18
    f = FABRIC_GREY
    return {"name": "Γωνιακός καναπές 260×180", "category": ("Σαλόνι",), "expect_cm": [w, d, h], "parts": [
        *legs(4, 94, w - 4, d - 4, 12, 5, BLACK), *legs(184, 4, w - 4, 90, 12, 5, BLACK),
        R((0, 90, 12), (w, d, 42), 4, f, "ύφασμα"), R((180, 0, 12), (w, 92, 42), 4, f, "ύφασμα"),
        R((arm, 92, 42), (w - arm, d - 22, 52), 6, f, "ύφασμα"), R((182, 4, 42), (w - arm, 94, 52), 6, f, "ύφασμα"),
        R((0, d - 22, 42), (w, d, h), 8, f, "ύφασμα"),
        R((0, 90, 42), (arm, d, 66), 6, f, "ύφασμα"), R((w - arm, 0, 42), (w, d, 66), 6, f, "ύφασμα")]}


def pouf():
    # seat height 42
    return {"name": "Πουφ 60×60", "category": ("Σαλόνι",), "expect_cm": [60, 60, 42], "parts": [
        *legs(4, 4, 56, 56, 8, 4, WALNUT, round_=True),
        R((0, 0, 8), (60, 60, 42), 8, FABRIC_BLUE, "ύφασμα")]}


def side_table():
    # side table 55 high, Ø45
    return {"name": "Βοηθητικό τραπεζάκι Ø45", "category": ("Σαλόνι",), "expect_cm": [45, 45, 55], "parts": [
        C((22.5, 22.5, 52), 22.5, 3, OAK, "ξύλο", segments=32),
        T((22.5, 22.5, 2), 2, 2, 50, BLACK, "βάση", 12),
        C((22.5, 22.5, 0), 15, 2, BLACK, "βάση", segments=24)]}


def fireplace():
    # firebox opening 70×65, mantel 110
    w, d, h = 120, 45, 110
    return {"name": "Τζάκι 120", "category": ("Σαλόνι",), "expect_cm": [w, d, h], "parts": [
        B((0, 0, 0), (w, d, 10), STONE, "βάση"),
        B((0, 5, 10), (25, d, 100), WHITE, "επένδυση"), B((95, 5, 10), (w, d, 100), WHITE, "επένδυση"),
        B((25, 5, 75), (95, d, 100), WHITE, "επένδυση"),
        B((25, 19, 10), (95, d, 75), GLASS_DARK, "εστία"),
        B((0, 0, 100), (w, d, h), OAK, "ράφι")]}


def television():
    # 55" screen: 124 × 71 cm
    return {"name": "Τηλεόραση 55\" με βάση", "category": ("Σαλόνι",), "expect_cm": [124, 25, 78], "parts": [
        B((40, 0, 0), (84, 25, 2), BLACK, "βάση"), B((60, 12, 2), (64, 16, 7), BLACK, "βάση"),
        B((0, 11, 7), (124, 15, 78), GLASS_DARK, "οθόνη")]}


def upright_piano():
    # upright piano: keyboard 74, height 125, 88 keys ≈ 122 cm
    w, d, h = 150, 60, 125
    return {"name": "Πιάνο όρθιο", "category": ("Σαλόνι",), "expect_cm": [w, d, h], "parts": [
        B((0, 30, 0), (w, d, h), BLACK, "σώμα"),
        B((0, 2, 62), (w, 30, 72), BLACK, "σώμα"),
        B((14, 4, 72), (136, 28, 74), WHITE, "πλήκτρα"),
        B((2, 2, 0), (8, 8, 62), BLACK, "σώμα"), B((142, 2, 0), (148, 8, 62), BLACK, "σώμα"),
        B((0, 0, 72), (14, 30, 80), BLACK, "σώμα"), B((136, 0, 72), (w, 30, 80), BLACK, "σώμα")]}


# ------------------------------------------------------------------ dining
def round_table_120():
    return {"name": "Τραπέζι στρογγυλό Ø120", "category": ("Τραπεζαρία",), "expect_cm": [120, 120, 75], "parts": [
        C((60, 60, 72), 60, 3, OAK, "ξύλο", segments=48),
        T((60, 60, 3), 5, 5, 69, BLACK, "βάση", 16),
        C((60, 60, 0), 30, 3, BLACK, "βάση", segments=32)]}


def sideboard():
    # sideboard 80 high, 45 deep
    w, d, h = 160, 45, 80
    parts = [*legs(3, 5, w - 3, d - 3, 12, 4, BLACK), B((0, 2.5, 12), (w, d, h), WALNUT, "ξύλο")]
    for k in range(3):
        x0 = 2 + k * 52
        parts += [B((x0, 2, 14), (x0 + 51, 2.5, h - 2), OAK, "πόρτες"),
                  B((x0 + 44, 0, 40), (x0 + 46, 2, 60), STEEL, "χερούλια")]
    return {"name": "Μπουφές 160", "category": ("Τραπεζαρία",), "expect_cm": [w, d, h], "parts": parts}


def vitrine():
    # display cabinet: closed base to 80, glass above
    w, d, h = 100, 40, 190
    parts = [B((0, 0, 0), (w, d, 8), BLACK, "βάση"),
             B((0, 0, 8), (3, d, h), WALNUT, "ξύλο"), B((w - 3, 0, 8), (w, d, h), WALNUT, "ξύλο"),
             B((3, 0, h - 3), (w - 3, d, h), WALNUT, "ξύλο"), B((3, d - 2, 8), (w - 3, d, h - 3), WALNUT, "ξύλο"),
             B((3, 1, 8), (w - 3, d - 2, 80), WALNUT, "ξύλο"),
             B((4, 0, 10), (49, 1, 78), OAK, "πόρτες"), B((51, 0, 10), (w - 4, 1, 78), OAK, "πόρτες"),
             B((3, 0, 80), (w - 3, 1, h - 3), GLASS, "γυαλί")]
    for z in (115, 150):
        parts.append(B((3, 2, z), (w - 3, d - 2, z + 1.5), WALNUT, "ξύλο"))
    return {"name": "Βιτρίνα 100", "category": ("Τραπεζαρία",), "expect_cm": [w, d, h], "parts": parts}


def dining_bench():
    # bench seat 45
    return {"name": "Πάγκος τραπεζαρίας 140", "category": ("Τραπεζαρία",), "expect_cm": [140, 35, 45], "parts": [
        *legs(4, 3, 136, 32, 41, 4, OAK), B((0, 0, 41), (140, 35, 45), OAK, "ξύλο")]}


# ------------------------------------------------------------------ bedroom
def bed_bench():
    return {"name": "Μπαούλο-πάγκος κρεβατιού 120", "category": ("Υπνοδωμάτιο",), "expect_cm": [120, 40, 45], "parts": [
        *legs(3, 3, 117, 37, 12, 4, WALNUT), R((0, 0, 12), (120, 40, 45), 4, FABRIC_SAND, "ύφασμα")]}


def dressing_table():
    # table 75, mirror to 150
    w, d = 100, 45
    return {"name": "Τουαλέτα με καθρέφτη 100", "category": ("Υπνοδωμάτιο",), "expect_cm": [w, d, 150], "parts": [
        *legs(2, 2, w - 2, d - 2, 62, 4, WHITE),
        B((0, 0, 62), (w, d, 75), WHITE, "ξύλο"),
        B((30, -0.0, 64), (70, 0.5, 72), OAK, "συρτάρι"),
        B((20, d - 5, 75), (80, d, 150), WHITE, "κορνίζα"),
        B((23, d - 5.5, 78), (77, d - 5, 147), GLASS, "καθρέφτης")]}


def vanity_stool():
    return {"name": "Σκαμπό τουαλέτας", "category": ("Υπνοδωμάτιο",), "expect_cm": [40, 35, 45], "parts": [
        *legs(2, 2, 38, 33, 40, 3, WHITE, round_=True), R((0, 0, 40), (40, 35, 45), 4, FABRIC_SAND, "ύφασμα")]}


# ------------------------------------------------------------------ children
def bunk_bed():
    # 90×200 mattresses, lower at 30, upper at 115, guard rail to 160
    w, L, h = 100, 210, 160
    parts = [*legs(0, 0, w, L, h, 6, PINE),
             B((0, 0, 15), (w, L, 30), PINE, "σκελετός"), B((0, 0, 100), (w, L, 115), PINE, "σκελετός"),
             R((5, 5, 30), (w - 5, L - 5, 45), 3, MATTRESS, "στρώμα"),
             R((5, 5, 115), (w - 5, L - 5, 130), 3, MATTRESS, "στρώμα"),
             B((0, 50, 130), (3, L - 6, 155), PINE, "προστατευτικό"), B((w - 3, 6, 130), (w, L - 6, 155), PINE, "προστατευτικό"),
             B((20, 0, 30), (23, 3, 130), PINE, "σκάλα"), B((45, 0, 30), (48, 3, 130), PINE, "σκάλα")]
    parts += [B((23, 0, 52 + k * 25), (45, 3, 55 + k * 25), PINE, "σκάλα") for k in range(3)]
    return {"name": "Κουκέτα 90×200", "category": ("Παιδικό",), "expect_cm": [w, L, h], "parts": parts}


def baby_cot():
    # 60×120 mattress, rail 95
    w, L, h = 66, 126, 95
    parts = [*legs(0, 0, w, L, h, 4, WHITE),
             B((2, 2, 22), (w - 2, L - 2, 25), WHITE, "σκελετός"),
             R((3, 3, 25), (w - 3, L - 3, 35), 3, MATTRESS, "στρώμα"),
             B((4, 0, 25), (w - 4, 2, 93), WHITE, "σκελετός"), B((4, L - 2, 25), (w - 4, L, 93), WHITE, "σκελετός")]
    for x0 in (0, w - 2):
        parts += [B((x0, 4, 22), (x0 + 2, L - 4, 25), WHITE, "σκελετός"), B((x0, 4, 90), (x0 + 2, L - 4, 93), WHITE, "σκελετός")]
        parts += [B((x0, 8 + k * 8, 25), (x0 + 2, 10 + k * 8, 90), WHITE, "κάγκελα") for k in range(14)]
    return {"name": "Κούνια μωρού 60×120", "category": ("Παιδικό",), "expect_cm": [w, L, h], "parts": parts}


def kids_desk():
    # child desk 70 high
    w, d, h = 100, 55, 70
    return {"name": "Παιδικό γραφείο 100", "category": ("Παιδικό",), "expect_cm": [w, d, h], "parts": [
        B((0, 0, h - 3), (w, d, h), WHITE, "επιφάνεια"),
        B((0, 2, 0), (3, d - 2, h - 3), PINE, "σκελετός"), B((w - 3, 2, 0), (w, d - 2, h - 3), PINE, "σκελετός"),
        B((3, d - 6, 30), (w - 3, d - 4, h - 3), PINE, "σκελετός")]}


# ------------------------------------------------------------------ bathroom
def wall_hung_wc():
    # seat 40, projection 54, concealed frame 110 high
    return {"name": "Λεκάνη κρεμαστή με εντοιχισμένο καζανάκι", "category": ("Μπάνιο",), "expect_cm": [60, 74, 110],
            "parts": [
                B((0, 54, 0), (60, 74, 110), WHITE, "επένδυση"),
                B((22, 53.5, 88), (38, 54, 100), CHROME, "πλήκτρο"),
                B((19, 30, 22), (41, 54, 38), CERAMIC, "πορσελάνη"),
                E((30, 27, 32), (18, 27, 8), CERAMIC, "πορσελάνη")]}


def bidet():
    # rim 40, projection 54
    return {"name": "Μπιντέ", "category": ("Μπάνιο",), "expect_cm": [36, 54, 40], "parts": [
        T((18, 27, 0), 11, 13, 34, CERAMIC, "πορσελάνη", 24),
        B((11, 34, 0), (25, 54, 34), CERAMIC, "πορσελάνη"),
        E((18, 27, 34), (18, 27, 6), CERAMIC, "πορσελάνη")]}


def pedestal_basin():
    # basin rim 85
    w, d, h = 60, 45, 85
    return {"name": "Νιπτήρας με κολόνα 60", "category": ("Μπάνιο",), "expect_cm": [w, d, h + 15], "parts": [
        T((30, 28, 0), 10, 8, 70, CERAMIC, "πορσελάνη", 24),
        R((0, 0, 70), (w, d, h), 6, CERAMIC, "πορσελάνη"),
        E((w / 2, 20, h + 0.01), (24, 15, 0.4), "#d9dde0", "πορσελάνη"),
        C((w / 2, 40, h), 1.6, 15, CHROME, "μπαταρία", segments=12)]}


def walk_in_shower():
    # tray 120×80, glass 200
    w, d = 120, 80
    return {"name": "Ντουζιέρα walk-in 120×80", "category": ("Μπάνιο",), "expect_cm": [w, d, 200], "parts": [
        B((0, 0, 0), (w, d, 3), CERAMIC, "βάση"),
        B((40, 0, 3), (w, 1, 200), GLASS, "γυαλί"),
        C((20, 65, 193), 12, 2, CHROME, "μπαταρία", segments=24),
        C((20, 77, 100), 1.2, 95, CHROME, "μπαταρία", segments=10)]}


def freestanding_tub():
    w, d, h = 170, 80, 60
    return {"name": "Μπανιέρα ελεύθερη 170×80", "category": ("Μπάνιο",), "expect_cm": [w, d, h], "parts": [
        R((0, 0, 0), (w, d, h), 30, CERAMIC, "πορσελάνη"),
        E((w / 2, d / 2, h + 0.01), (w / 2 - 12, d / 2 - 8, 0.4), "#dfe4e7", "πορσελάνη")]}


def towel_radiator():
    # 50×120 bathroom radiator, 7 deep
    parts = [C((2, 5, 0), 2, 120, WHITE, "σώμα", segments=12), C((48, 5, 0), 2, 120, WHITE, "σώμα", segments=12)]
    parts += [B((2, 3.5, 10 + k * 10), (48, 6.5, 12 + k * 10), WHITE, "σώμα") for k in range(11)]
    parts += [B((3, 7, 20), (5, 10, 23), WHITE, "στήριγμα"), B((45, 7, 100), (47, 10, 103), WHITE, "στήριγμα")]
    return {"name": "Καλοριφέρ-πετσετοκρεμάστρα 50×120", "category": ("Μπάνιο",), "expect_cm": [50, 7, 120], "parts": parts}


def mirror_cabinet():
    return {"name": "Καθρέφτης-ντουλάπι μπάνιου 80", "category": ("Μπάνιο",), "expect_cm": [80, 15, 70], "parts": [
        B((0, 1, 0), (80, 15, 70), WHITE, "σώμα"),
        B((1, 0, 1), (39.5, 1, 69), GLASS, "καθρέφτης"), B((40.5, 0, 1), (79, 1, 69), GLASS, "καθρέφτης")]}


def water_heater():
    # 80 l electric water heater, Ø45
    return {"name": "Θερμοσίφωνας 80 l", "category": ("Μπάνιο",), "expect_cm": [45, 45, 85], "parts": [
        C((22.5, 22.5, 4), 22.5, 77, WHITE, "σώμα", segments=28),
        T((22.5, 22.5, 0), 18, 22.5, 4, WHITE, "σώμα", 28),
        T((22.5, 22.5, 81), 22.5, 18, 4, WHITE, "σώμα", 28)]}


# ------------------------------------------------------------------ appliances
def dryer():
    return appliance("Στεγνωτήριο ρούχων 60", 60, 60, 85, [
        C((30, 1.5, 42), 18, 1.5, "#cfd4d8", "πόρτα", axis="y", segments=32),
        C((30, 0, 42), 14, 1.5, GLASS_DARK, "τζάμι", axis="y", segments=28),
        B((3, 2.5, 74), (57, 3, 84), "#d4d6d8", "πίνακας")])


def microwave():
    return appliance("Φούρνος μικροκυμάτων", 50, 40, 30, [
        B((3, 2.5, 3), (36, 3, 27), GLASS_DARK, "τζάμι"), B((38, 2.5, 3), (47, 3, 27), "#3a3a3a", "πίνακας"),
        B((33, 0, 8), (35, 2.5, 22), STEEL, "χερούλια")], front=LIGHT_GREY)


def side_by_side_fridge():
    # side-by-side 91 wide, 178 high
    return appliance("Ψυγείο ντουλάπα 91", 91, 72, 178, [
        B((1, 2.5, 2), (45, 3, 177), STEEL, "πόρτες"), B((46, 2.5, 2), (90, 3, 177), STEEL, "πόρτες"),
        B((41, 0, 70), (43, 2.5, 140), CHROME, "χερούλια"), B((48, 0, 70), (50, 2.5, 140), CHROME, "χερούλια"),
        B((12, 2, 110), (30, 2.5, 135), GLASS_DARK, "παροχή νερού")], front=STEEL)


def built_in_oven():
    # 60 cm built-in oven, 59.5 high
    return appliance("Φούρνος εντοιχιζόμενος 60", 60, 56, 60, [
        B((4, 2.5, 8), (56, 3, 44), GLASS_DARK, "τζάμι φούρνου"),
        B((8, 0, 46), (52, 2.5, 48), STEEL, "χερούλια"),
        B((2, 2.5, 50), (58, 3, 58), STEEL, "πίνακας")], front=BLACK)


def air_conditioner():
    # wall split unit 90×30, 25 deep
    return {"name": "Κλιματιστικό τοίχου", "category": ("Συσκευές",), "expect_cm": [90, 25, 30], "parts": [
        R((0, 1, 0), (90, 25, 30), 4, WHITE, "σώμα"),
        B((6, 0, 3), (84, 1, 7), LIGHT_GREY, "περσίδα")]}


def panel_radiator():
    # panel radiator 100×60 on 10 cm feet
    return {"name": "Καλοριφέρ πάνελ 100×60", "category": ("Συσκευές",), "expect_cm": [100, 10, 70], "parts": [
        B((5, 3, 0), (9, 7, 10), WHITE, "πόδια"), B((91, 3, 0), (95, 7, 10), WHITE, "πόδια"),
        B((0, 0, 10), (100, 10, 70), WHITE, "σώμα")]}


# ------------------------------------------------------------------ office
def corner_desk():
    # desk 75, L 160×140
    return {"name": "Γραφείο γωνιακό 160×140", "category": ("Γραφείο",), "expect_cm": [160, 140, 75], "parts": [
        B((0, 70, 72), (160, 140, 75), OAK, "επιφάνεια"), B((0, 0, 72), (70, 70, 75), OAK, "επιφάνεια"),
        B((0, 2, 0), (3, 138, 72), BLACK, "σκελετός"), B((157, 72, 0), (160, 138, 72), BLACK, "σκελετός"),
        B((64, 0, 0), (70, 6, 72), BLACK, "σκελετός"),
        B((70, 134, 30), (157, 136, 72), BLACK, "σκελετός")]}


def file_cabinet():
    # under-desk pedestal 65 high
    parts = [B((2, 3, 0), (38, 48, 4), BLACK, "βάση"), B((0, 2, 4), (40, 50, 65), LIGHT_GREY, "σώμα")]
    for k in range(3):
        z = 6 + k * 19.5
        parts += [B((1, 1, z), (39, 2, z + 18.5), LIGHT_GREY, "συρτάρια"),
                  B((15, 0, z + 14), (25, 1, z + 15.5), STEEL, "χερούλια")]
    return {"name": "Συρταριέρα γραφείου 3 συρτάρια", "category": ("Γραφείο",), "expect_cm": [40, 50, 65], "parts": parts}


def shelf_unit(w, d, h, shelves, name, category, color=OAK):
    parts = [B((0, 0, 0), (2, d, h), color, "ξύλο"), B((w - 2, 0, 0), (w, d, h), color, "ξύλο"),
             B((2, d - 1, 0), (w - 2, d, h), color, "ξύλο")]
    for k in range(shelves + 1):
        z = k * (h - 2) / shelves
        parts.append(B((2, 0, z), (w - 2, d - 1, z + 2), color, "ξύλο"))
    return {"name": name, "category": category, "expect_cm": [w, d, h], "parts": parts}


# ------------------------------------------------------------------ lighting
def pendant_lamp():
    # hangs 100 below the ceiling; place its base 100 under the ceiling
    return {"name": "Κρεμαστό φωτιστικό Ø40", "category": ("Φωτισμός",), "expect_cm": [40, 40, 100], "parts": [
        T((20, 20, 0), 20, 6, 30, COPPER, "καπέλο", 28),
        E((20, 20, 7), (5, 5, 5), LAMP, "λάμπα"),
        C((20, 20, 30), 0.4, 68, BLACK, "καλώδιο", segments=6),
        C((20, 20, 98), 6, 2, BLACK, "βάση", segments=16)]}


def ceiling_light():
    return {"name": "Πλαφονιέρα Ø40", "category": ("Φωτισμός",), "expect_cm": [40, 40, 10], "parts": [
        C((20, 20, 0), 20, 8, LAMP, "διαχυτής", segments=36), C((20, 20, 8), 15, 2, WHITE, "βάση", segments=28)]}


def wall_sconce():
    return {"name": "Απλίκα τοίχου", "category": ("Φωτισμός",), "expect_cm": [15, 20, 25], "parts": [
        B((3.5, 18, 0), (11.5, 20, 23), BLACK, "βάση"), B((6.5, 8, 11), (8.5, 18, 13), BLACK, "βάση"),
        T((7.5, 7.5, 6), 6, 7.5, 19, LAMP, "καπέλο", 24)]}


# ------------------------------------------------------------------ decoration
def painting():
    return {"name": "Πίνακας ζωγραφικής 90×60", "category": ("Διακόσμηση",), "expect_cm": [90, 3, 60], "parts": [
        B((0, 0.5, 0), (90, 3, 60), WALNUT, "κορνίζα"),
        B((4, 0, 4), (50, 0.5, 56), "#c98f4f", "καμβάς"), B((50, 0, 4), (86, 0.5, 56), "#4f6f8a", "καμβάς")]}


def curtain():
    # 150 wide, ceiling rod at 250
    parts = [B((k * 10, (k % 2) * 4, 0), (k * 10 + 10, (k % 2) * 4 + 6, 247), LINEN_CURTAIN, "ύφασμα") for k in range(15)]
    parts.append(C((0, 5, 248.5), 1.5, 150, BLACK, "κουρτινόξυλο", axis="x", segments=10))
    return {"name": "Κουρτίνα 150×250", "category": ("Διακόσμηση",), "expect_cm": [150, 10, 250], "parts": parts}


LINEN_CURTAIN = "#e7dfcf"


def small_plant():
    return {"name": "Φυτό μικρό σε κασπώ", "category": ("Διακόσμηση",), "expect_cm": [30, 30, 50], "parts": [
        T((15, 15, 0), 10, 13, 22, WHITE, "κασπώ", 24), E((15, 15, 36), (15, 15, 14), GREEN, "φύλλωμα")]}


# ------------------------------------------------------------------ entrance
def coat_stand():
    return {"name": "Καλόγερος (κρεμάστρα δαπέδου)", "category": ("Είσοδος",), "expect_cm": [45, 45, 180], "parts": [
        C((22.5, 22.5, 0), 22.5, 2, BLACK, "βάση", segments=24),
        C((22.5, 22.5, 2), 1.5, 172, BLACK, "στέλεχος", segments=10),
        B((10, 21.5, 165), (35, 23.5, 167), BLACK, "άγκιστρα"), B((21.5, 10, 170), (23.5, 35, 172), BLACK, "άγκιστρα"),
        E((22.5, 22.5, 177), (3, 3, 3), OAK, "στέλεχος")]}


def shoe_cabinet():
    parts = [B((0, 1, 0), (80, 35, 100), WHITE, "σώμα")]
    parts += [B((1, 0, 2 + k * 32.5), (79, 1, 2 + k * 32.5 + 31.5), OAK, "πόρτες") for k in range(3)]
    return {"name": "Παπουτσοθήκη 80", "category": ("Είσοδος",), "expect_cm": [80, 35, 100], "parts": parts}


def hall_console():
    return {"name": "Κονσόλα εισόδου 100", "category": ("Είσοδος",), "expect_cm": [100, 30, 80], "parts": [
        *legs(2, 2, 98, 28, 77, 3, BLACK), B((0, 0, 77), (100, 30, 80), OAK, "ξύλο"),
        B((3, 3, 20), (97, 27, 22), OAK, "ξύλο")]}


# ------------------------------------------------------------------ outdoors
def masonry_bbq():
    # worktop 95, chimney 190
    return {"name": "Ψησταριά κτιστή 150", "category": ("Εξωτερικοί χώροι",), "expect_cm": [150, 60, 190], "parts": [
        B((0, 0, 0), (150, 60, 90), BRICK, "τούβλο"), B((0, 0, 90), (150, 60, 95), STONE, "πάγκος"),
        B((25, 5, 95), (35, 60, 150), BRICK, "τούβλο"), B((115, 5, 95), (125, 60, 150), BRICK, "τούβλο"),
        B((35, 50, 95), (115, 60, 150), BRICK, "τούβλο"),
        B((35, 5, 110), (115, 50, 111), BLACK, "σχάρα"),
        B((20, 0, 150), (130, 60, 165), BRICK, "τούβλο"), B((60, 25, 165), (90, 55, 190), BRICK, "τούβλο")]}


def garden_armchair():
    # seat 43, armrest 58
    parts = []
    for x0 in (0, 65):
        parts += [B((x0, 2, 0), (x0 + 5, 7, 55), TEAK, "ξύλο"), B((x0, 62, 0), (x0 + 5, 67, 55), TEAK, "ξύλο"),
                  B((x0, 72, 0), (x0 + 5, 80, 43), TEAK, "ξύλο"), B((x0, 7, 37), (x0 + 5, 72, 40), TEAK, "ξύλο")]
    parts += [B((0, 0, 55), (12, 72, 58), TEAK, "ξύλο"), B((58, 0, 55), (70, 72, 58), TEAK, "ξύλο")]
    parts += [B((5, 5 + k * 13, 40), (65, 15 + k * 13, 43), TEAK, "ξύλο") for k in range(5)]
    parts += [B((8 + k * 10.5, 72, 43), (16 + k * 10.5, 78, 90), TEAK, "ξύλο") for k in range(6)]
    return {"name": "Πολυθρόνα κήπου", "category": ("Εξωτερικοί χώροι",), "expect_cm": [70, 80, 90], "parts": parts}


def fountain():
    return {"name": "Σιντριβάνι Ø100", "category": ("Εξωτερικοί χώροι",), "expect_cm": [100, 100, 120], "parts": [
        C((50, 50, 0), 50, 40, STONE, "πέτρα", segments=40), C((50, 50, 40), 45, 0.5, WATER, "νερό", segments=40),
        C((50, 50, 40), 8, 50, STONE, "πέτρα", segments=20), T((50, 50, 90), 10, 25, 10, STONE, "πέτρα", 28),
        C((50, 50, 100), 4, 20, STONE, "πέτρα", segments=16)]}


def hot_tub():
    # 200×200 spa, 90 high
    return {"name": "Τζακούζι εξωτερικό 200×200", "category": ("Εξωτερικοί χώροι",), "expect_cm": [200, 200, 90], "parts": [
        R((0, 0, 0), (200, 200, 90), 15, TEAK, "επένδυση"),
        R((12, 12, 85), (188, 188, 90.3), 10, WATER, "νερό")]}


def swing_set():
    w, d, h = 250, 150, 200
    parts = [*legs(0, 0, w, d, 192, 8, GREEN),
             B((0, 0, 188), (8, d, 192), GREEN, "σκελετός"), B((w - 8, 0, 188), (w, d, 192), GREEN, "σκελετός"),
             C((0, 75, 196), 4, w, GREEN, "σκελετός", axis="x", segments=12)]
    for x0 in (75, 145):
        parts += [C((x0 + 3, 75, 45), 0.6, 147, BLACK, "σχοινί", segments=6),
                  C((x0 + 27, 75, 45), 0.6, 147, BLACK, "σχοινί", segments=6),
                  B((x0, 68, 42), (x0 + 30, 82, 45), "#c8473d", "κάθισμα")]
    return {"name": "Κούνια κήπου διπλή", "category": ("Εξωτερικοί χώροι", "Παιδικό"), "expect_cm": [w, d, h], "parts": parts}


def outdoor_shower():
    return {"name": "Ντους εξωτερικό", "category": ("Εξωτερικοί χώροι",), "expect_cm": [40, 40, 220], "parts": [
        B((0, 0, 0), (40, 40, 4), PINE, "πατάρι"),
        C((33, 33, 4), 3, 216, STEEL, "στήλη", segments=12),
        B((14, 31, 214), (33, 35, 216), STEEL, "στήλη"),
        C((14, 33, 212), 7, 2, CHROME, "κεφαλή", segments=20)]}


def garden_bollard():
    return {"name": "Φωτιστικό κήπου κολονάκι", "category": ("Εξωτερικοί χώροι", "Φωτισμός"), "expect_cm": [20, 20, 80],
            "parts": [B((0, 0, 0), (20, 20, 70), "#3a3d40", "σώμα"), B((1, 1, 70), (19, 19, 76), LAMP, "διαχυτής"),
                      B((0, 0, 76), (20, 20, 80), "#3a3d40", "σώμα")]}


def specs():
    return [
        corner_sofa(), pouf(), side_table(), fireplace(), television(), upright_piano(),
        dining_table(220, 100, "Τραπέζι τραπεζαρίας 8θέσιο", 8), round_table_120(), sideboard(), vitrine(), dining_bench(),
        bed(180, "Υπέρδιπλο κρεβάτι 180×200"), bed(140, "Διπλό κρεβάτι 140×200"), bed(120, "Ημίδιπλο κρεβάτι 120×200"),
        bed_bench(), dressing_table(), vanity_stool(),
        bunk_bed(), baby_cot(), kids_desk(),
        wall_hung_wc(), bidet(), pedestal_basin(), walk_in_shower(), freestanding_tub(), towel_radiator(),
        mirror_cabinet(), water_heater(),
        dryer(), microwave(), side_by_side_fridge(), built_in_oven(), air_conditioner(), panel_radiator(),
        corner_desk(), file_cabinet(), shelf_unit(80, 35, 120, 3, "Ραφιέρα 80×120", ("Γραφείο", "Σαλόνι")),
        pendant_lamp(), ceiling_light(), wall_sconce(),
        painting(), curtain(), small_plant(),
        coat_stand(), shoe_cabinet(), hall_console(),
        masonry_bbq(), garden_armchair(), fountain(), hot_tub(), swing_set(), outdoor_shower(), garden_bollard(),
    ]
