"""ArchForge core library: project-owned objects that ship with the app.

Every item is an ArchForge original built from simple solids (see
``builder.py``) with standard real-world dimensions (seat 45 cm, table 75 cm,
bed 160x200, worktop 90 cm ...).  Online pictures and models are used only
as visual reference, never copied; no brands.  Each item states the size it
must have (``expect_cm``) and is checked against it and visually
(``asset_preview.py``) before it is added here.

Front faces -Y, backs +Y, Z up, centimetres.
"""
from archforge.library import builder

# Palette (realistic, neutral)
OAK, WALNUT, PINE, BLACK, STEEL, CHROME = "#b08a5a", "#6b4a31", "#d2b48c", "#2b2b2b", "#9a9ea3", "#c9ccd0"
FABRIC_GREY, FABRIC_BLUE, FABRIC_SAND, LEATHER = "#8d8f93", "#4b5d7a", "#c9b99a", "#7a4a2c"
WHITE, CERAMIC, GLASS, LINEN, MATTRESS = "#f2f0eb", "#f5f5f2", "#bcd3d8", "#e9e2d4", "#efeae0"
GREEN, TERRACOTTA, STONE, APPLIANCE = "#4f7a3a", "#b5653b", "#8c8780", "#e6e7e8"
GLASS_DARK, LAMP = "#2f3337", "#f3e9c9"

CATEGORIES = ("Σαλόνι", "Τραπεζαρία", "Υπνοδωμάτιο", "Παιδικό", "Μπάνιο", "Συσκευές", "Γραφείο", "Φωτισμός",
              "Διακόσμηση", "Είσοδος", "Εξωτερικοί χώροι")


def B(lo, hi, color, part):
    return {"shape": "box", "min": list(lo), "max": list(hi), "color": color, "part": part}


def R(lo, hi, radius, color, part):
    return {"shape": "rounded_box", "min": list(lo), "max": list(hi), "radius": radius, "color": color, "part": part}


def C(base, radius, height, color, part, axis="z", segments=20):
    return {"shape": "cylinder", "base": list(base), "radius": radius, "height": height, "axis": axis,
            "color": color, "part": part, "segments": segments}


def T(base, r0, r1, height, color, part, segments=20):
    return {"shape": "taper", "base": list(base), "r0": r0, "r1": r1, "height": height, "color": color,
            "part": part, "segments": segments}


def E(center, radii, color, part):
    return {"shape": "ellipsoid", "center": list(center), "radii": list(radii), "color": color, "part": part}


def legs(x0, y0, x1, y1, height, size, color, inset=0.0, round_=False):
    out = []
    for x in (x0 + inset, x1 - inset - size):
        for y in (y0 + inset, y1 - inset - size):
            if round_:
                out.append(T((x + size / 2, y + size / 2, 0), size / 2.6, size / 2, height, color, "πόδια", 12))
            else:
                out.append(B((x, y, 0), (x + size, y + size, height), color, "πόδια"))
    return out


# ------------------------------------------------------------------ items
def sofa(width, fabric, name):
    d, h, arm = 90, 85, 18
    return {"name": name, "category": ("Σαλόνι",), "expect_cm": [width, d, h], "parts": [
        *legs(4, 6, width - 4, d - 6, 12, 5, BLACK),
        R((0, 0, 12), (width, d, 42), 4, fabric, "ύφασμα"),                    # base
        R((arm, 4, 42), (width - arm, d - 20, 52), 6, fabric, "ύφασμα"),        # seat cushions
        R((arm, d - 22, 42), (width - arm, d, h), 8, fabric, "ύφασμα"),          # back
        R((0, 0, 42), (arm, d, 66), 6, fabric, "ύφασμα"),
        R((width - arm, 0, 42), (width, d, 66), 6, fabric, "ύφασμα"),
    ]}


def armchair():
    w = d = 85
    return {"name": "Πολυθρόνα", "category": ("Σαλόνι",), "expect_cm": [w, d, 85], "parts": [
        *legs(5, 6, w - 5, d - 6, 14, 4, WALNUT, round_=True),
        R((0, 0, 14), (w, d, 42), 4, FABRIC_SAND, "ύφασμα"),
        R((16, 4, 42), (w - 16, d - 22, 52), 6, FABRIC_SAND, "ύφασμα"),
        R((0, d - 22, 42), (w, d, 85), 8, FABRIC_SAND, "ύφασμα"),
        R((0, 0, 42), (16, d, 64), 6, FABRIC_SAND, "ύφασμα"),
        R((w - 16, 0, 42), (w, d, 64), 6, FABRIC_SAND, "ύφασμα"),
    ]}


def coffee_table():
    w, d, h = 110, 60, 42
    return {"name": "Τραπεζάκι σαλονιού", "category": ("Σαλόνι",), "expect_cm": [w, d, h], "parts": [
        *legs(4, 4, w - 4, d - 4, h - 3, 4, OAK),
        R((0, 0, h - 3), (w, d, h), 2, OAK, "ξύλο"),
        B((6, 6, 12), (w - 6, d - 6, 14), OAK, "ξύλο"),
    ]}


def tv_unit():
    w, d, h = 180, 40, 50
    return {"name": "Έπιπλο TV", "category": ("Σαλόνι",), "expect_cm": [w, d, h], "parts": [
        *legs(3, 3, w - 3, d - 3, 10, 3, BLACK),
        B((0, 0, 10), (w, d, h), WALNUT, "ξύλο"),
        B((2, -0.5, 13), (w / 2 - 1, 0, h - 3), OAK, "πρόσοψη"),
        B((w / 2 + 1, -0.5, 13), (w - 2, 0, h - 3), OAK, "πρόσοψη"),
    ]}


def bookcase():
    w, d, h = 90, 30, 200
    parts = [B((0, 0, 0), (2, d, h), OAK, "ξύλο"), B((w - 2, 0, 0), (w, d, h), OAK, "ξύλο"),
             B((2, d - 1, 0), (w - 2, d, h), OAK, "ξύλο")]
    for k in range(6):
        z = k * (h - 2) / 5
        parts.append(B((2, 0, z), (w - 2, d - 1, z + 2), OAK, "ξύλο"))
    for k, col in enumerate(("#7d3b2f", "#2f4f6b", "#c4a35a", "#3d5c3a")):
        parts.append(B((6 + k * 7, 4, 42), (12 + k * 7, d - 4, 70), col, "βιβλία"))
    return {"name": "Βιβλιοθήκη με ράφια", "category": ("Σαλόνι",), "expect_cm": [w, d, h], "parts": parts}


def rug(w, d, color, name):
    return {"name": name, "category": ("Σαλόνι", "Διακόσμηση"), "expect_cm": [w, d, 1],
            "parts": [R((0, 0, 0), (w, d, 1), 2, color, "χαλί")]}


def dining_table(w, d, name, seats):
    h = 75
    return {"name": name, "category": ("Τραπεζαρία",), "expect_cm": [w, d, h], "parts": [
        *legs(5, 5, w - 5, d - 5, h - 4, 6, OAK),
        B((0, 0, h - 4), (w, d, h), OAK, "ξύλο"),
        B((8, 8, h - 12), (w - 8, 10, h - 4), OAK, "ξύλο"),
        B((8, d - 10, h - 12), (w - 8, d - 8, h - 4), OAK, "ξύλο"),
    ]}


def round_table():
    return {"name": "Τραπέζι στρογγυλό Ø100", "category": ("Τραπεζαρία",), "expect_cm": [100, 100, 75], "parts": [
        C((50, 50, 72), 50, 3, WALNUT, "ξύλο", segments=40),
        T((50, 50, 3), 4, 4, 69, BLACK, "βάση", 16),
        C((50, 50, 0), 25, 3, BLACK, "βάση", segments=32),
    ]}


def dining_chair():
    w, d = 45, 52
    return {"name": "Καρέκλα τραπεζαρίας", "category": ("Τραπεζαρία",), "expect_cm": [w, d, 90], "parts": [
        *legs(2, 2, w - 2, d - 2, 43, 3.5, WALNUT),
        R((0, 0, 43), (w, d, 47), 3, FABRIC_GREY, "κάθισμα"),
        B((2, d - 5, 47), (5.5, d - 1.5, 90), WALNUT, "σκελετός"),
        B((w - 5.5, d - 5, 47), (w - 2, d - 1.5, 90), WALNUT, "σκελετός"),
        R((2, d - 4, 62), (w - 2, d - 1, 88), 2, WALNUT, "σκελετός"),
    ]}


def bar_stool():
    return {"name": "Σκαμπό μπαρ", "category": ("Τραπεζαρία", "Συσκευές"), "expect_cm": [40, 40, 75], "parts": [
        C((20, 20, 72), 20, 3, LEATHER, "κάθισμα", segments=28),
        T((20, 20, 3), 2.5, 2.5, 69, CHROME, "μέταλλο", 12),
        C((20, 20, 0), 18, 3, CHROME, "μέταλλο", segments=28),
        C((20, 20, 26), 13, 1.5, CHROME, "μέταλλο", segments=24),
    ]}


def bed(width, name):
    L = 210
    hb = 110
    return {"name": name, "category": ("Υπνοδωμάτιο",), "expect_cm": [width + 10, L, hb], "parts": [
        *legs(2, 2, width + 8, L - 2, 12, 6, WALNUT),
        B((0, 0, 12), (width + 10, L, 35), WALNUT, "σκελετός"),
        R((5, 2, 35), (width + 5, L - 8, 57), 4, MATTRESS, "στρώμα"),
        B((0, L - 8, 12), (width + 10, L, hb), WALNUT, "κεφαλάρι"),
        R((10, 12, 57), (width, L - 70, 61), 3, LINEN, "κουβέρτα"),
        *([R((12, L - 58, 57), (width / 2 + 1, L - 14, 70), 5, WHITE, "μαξιλάρια"),
           R((width / 2 + 9, L - 58, 57), (width - 2, L - 14, 70), 5, WHITE, "μαξιλάρια")] if width >= 140 else
          [R((15, L - 58, 57), (width - 5, L - 14, 70), 5, WHITE, "μαξιλάρια")]),
    ]}


def nightstand():
    w, d, h = 45, 40, 50
    return {"name": "Κομοδίνο", "category": ("Υπνοδωμάτιο",), "expect_cm": [w, d, h], "parts": [
        *legs(2, 2, w - 2, d - 2, 10, 3, WALNUT),
        B((0, 0, 10), (w, d, h), WALNUT, "ξύλο"),
        B((2, -0.5, 30), (w - 2, 0, h - 2), OAK, "συρτάρι"),
        B((2, -0.5, 12), (w - 2, 0, 29), OAK, "συρτάρι"),
    ]}


def dresser():
    w, d, h = 100, 45, 80
    parts = [*legs(3, 5, w - 3, d - 3, 10, 4, WALNUT), B((0, 2.5, 10), (w, d, h), WALNUT, "ξύλο")]
    for k in range(3):
        z0 = 12 + k * (h - 14) / 3
        parts.append(B((2, 2, z0), (w - 2, 2.5, z0 + (h - 14) / 3 - 1), OAK, "συρτάρι"))
        parts.append(B((w / 2 - 8, 0, z0 + 9), (w / 2 + 8, 2, z0 + 10.5), STEEL, "χερούλια"))
    return {"name": "Συρταριέρα 3 συρτάρια", "category": ("Υπνοδωμάτιο",), "expect_cm": [w, d, h], "parts": parts}


def wc():
    # Close-coupled: pedestal and bowl at the front, cistern resting on the bowl's back.
    return {"name": "Λεκάνη WC με καζανάκι", "category": ("Μπάνιο",), "expect_cm": [36, 66, 80], "parts": [
        T((19, 28, 0), 11, 14, 38, CERAMIC, "πορσελάνη", 24),
        B((12, 36, 0), (26, 58, 40), CERAMIC, "πορσελάνη"),
        E((19, 28, 40), (17, 26, 5), CERAMIC, "πορσελάνη"),
        R((1, 50, 38), (37, 68, 80), 3, CERAMIC, "πορσελάνη"),
    ]}


def vanity():
    w, d, h = 80, 46, 85
    return {"name": "Νιπτήρας με έπιπλο 80", "category": ("Μπάνιο",), "expect_cm": [w, d, h + 18], "parts": [
        B((2, 6, 0), (w - 2, d - 2, 10), BLACK, "βάση"),
        B((1, 1, 10), (w - 1, d, 82), WHITE, "έπιπλο"),
        B((2, 0.5, 12), (w / 2 - 1, 1, 80), WHITE, "πόρτες"),
        B((w / 2 + 1, 0.5, 12), (w - 2, 1, 80), WHITE, "πόρτες"),
        R((0, 0, 82), (w, d, h), 3, CERAMIC, "πορσελάνη"),
        E((w / 2, d / 2 - 2, h + 0.01), (w / 2 - 10, d / 2 - 9, 0.4), "#d9dde0", "πορσελάνη"),
        C((w / 2, d - 6, h), 1.6, 18, CHROME, "μπαταρία", segments=12),
        C((w / 2, d - 17, h + 16), 1.2, 11, CHROME, "μπαταρία", axis="y", segments=12),
    ]}


def bathtub():
    w, d, h = 170, 75, 58
    return {"name": "Μπανιέρα 170×75", "category": ("Μπάνιο",), "expect_cm": [w, d, h], "parts": [
        R((0, 0, 0), (w, d, h), 8, CERAMIC, "πορσελάνη"),
        E((w / 2, d / 2, h + 0.01), (w / 2 - 10, d / 2 - 9, 0.4), "#dfe4e7", "πορσελάνη"),
    ]}


def shower():
    s = 90
    return {"name": "Ντουζιέρα 90×90", "category": ("Μπάνιο",), "expect_cm": [s, s, 200], "parts": [
        B((0, 0, 0), (s, s, 4), CERAMIC, "βάση"),
        B((0, s - 1, 4), (s, s, 200), GLASS, "γυαλί"),     # back wall side
        B((0, 0, 4), (1, s, 200), GLASS, "γυαλί"),         # side; the front stays open
        C((s - 15, s - 12, 180), 10, 2, CHROME, "μπαταρία", segments=20),
        C((s - 15, s - 3, 110), 1.2, 72, CHROME, "μπαταρία", segments=10),
    ]}


def appliance(name, w, d, h, parts_extra, front=APPLIANCE, categories=("Συσκευές",), body_h=None):
    """Body starts 3 cm back so handles stay inside the nominal depth."""
    return {"name": name, "category": categories, "expect_cm": [w, d, h], "parts": [
        R((0, 3, 0), (w, d, body_h or h), 1.5, front, "σώμα"), *parts_extra]}


def fridge():
    return appliance("Ψυγειοκαταψύκτης 60", 60, 65, 185, [
        B((1, 2.5, 66), (59, 3, 184), APPLIANCE, "πόρτες"), B((1, 2.5, 2), (59, 3, 64), APPLIANCE, "πόρτες"),
        B((53, 0, 100), (55, 2.5, 140), STEEL, "χερούλια"), B((53, 0, 40), (55, 2.5, 60), STEEL, "χερούλια")])


def cooker():
    return appliance("Κουζίνα με φούρνο 60", 60, 60, 85, [
        B((4, 2.5, 10), (56, 3, 60), GLASS_DARK, "τζάμι φούρνου"),
        B((10, 0, 62), (50, 2.5, 64), STEEL, "χερούλια"),
        B((1, 4, 84), (59, 59, 84.6), BLACK, "εστία"),
        *[C((x, y, 84.6), r, 0.4, "#555555", "μάτια", segments=20) for x, y, r in ((17, 19, 8), (43, 19, 6), (17, 44, 6), (43, 44, 8))]],
        body_h=84)


def hob():
    return {"name": "Εστία κεραμική 60", "category": ("Συσκευές",), "expect_cm": [60, 52, 5], "parts": [
        B((0, 0, 0), (60, 52, 5), BLACK, "γυαλί"),
        *[C((x, y, 5), r, 0.2, "#4a4a4a", "μάτια", segments=20) for x, y, r in ((16, 15, 9), (44, 15, 7), (16, 37, 7), (44, 37, 9))]]}


def dishwasher():
    return appliance("Πλυντήριο πιάτων 60", 60, 57, 82, [
        B((1, 2.5, 8), (59, 3, 81), WHITE, "πόρτα"), B((10, 0, 74), (50, 2.5, 76), STEEL, "χερούλια")])


def washing_machine():
    return appliance("Πλυντήριο ρούχων 60", 60, 60, 85, [
        C((30, 1.5, 42), 17, 1.5, "#cfd4d8", "πόρτα", axis="y", segments=32),
        C((30, 0.5, 42), 13, 1, GLASS_DARK, "τζάμι", axis="y", segments=28),
        B((3, 2.5, 74), (57, 3, 84), "#d4d6d8", "πίνακας")])


def hood():
    return {"name": "Απορροφητήρας 60", "category": ("Συσκευές",), "expect_cm": [60, 50, 70], "parts": [
        B((0, 0, 0), (60, 50, 6), STEEL, "ανοξείδωτο"),
        B((8, 10, 6), (52, 50, 14), STEEL, "ανοξείδωτο"),
        B((19, 25, 14), (41, 50, 70), STEEL, "ανοξείδωτο")]}


def desk():
    w, d, h = 140, 70, 75
    return {"name": "Γραφείο εργασίας 140", "category": ("Γραφείο",), "expect_cm": [w, d, h], "parts": [
        B((0, 0, h - 3), (w, d, h), OAK, "επιφάνεια"),
        B((0, 2, 0), (3, d - 2, h - 3), BLACK, "σκελετός"), B((w - 3, 2, 0), (w, d - 2, h - 3), BLACK, "σκελετός"),
        B((3, d - 6, 40), (w - 3, d - 4, h - 3), BLACK, "σκελετός"),
        B((w - 45, 4, 20), (w - 3, d - 6, h - 3), WHITE, "συρταριέρα")]}


def office_chair():
    return {"name": "Καρέκλα γραφείου", "category": ("Γραφείο",), "expect_cm": [64, 64, 105], "parts": [
        B((2, 30, 2), (62, 34, 5), BLACK, "βάση"), B((30, 2, 2), (34, 62, 5), BLACK, "βάση"),
        *[C((x, y, 0), 2.5, 3, BLACK, "βάση", axis="z", segments=20) for x, y in ((2.5, 32), (61.5, 32), (32, 2.5), (32, 61.5))],
        C((32, 32, 5), 2.5, 40, CHROME, "μηχανισμός", segments=12),
        R((10, 10, 45), (54, 54, 52), 5, BLACK, "ύφασμα"),
        R((12, 50, 55), (52, 56, 105), 6, BLACK, "ύφασμα"),
        B((30, 51, 45), (34, 55, 56), BLACK, "ύφασμα")]}


def floor_lamp():
    return {"name": "Φωτιστικό δαπέδου", "category": ("Φωτισμός",), "expect_cm": [40, 40, 165], "parts": [
        C((20, 20, 0), 14, 2, BLACK, "βάση", segments=24),
        C((20, 20, 2), 1.2, 128, BLACK, "στέλεχος", segments=10),
        T((20, 20, 130), 20, 13, 35, LAMP, "καπέλο", 28)]}


def table_lamp():
    return {"name": "Επιτραπέζιο φωτιστικό", "category": ("Φωτισμός",), "expect_cm": [30, 30, 48], "parts": [
        E((15, 15, 12), (9, 9, 12), "#7d8b6a", "κεραμικό"),
        C((15, 15, 22), 1, 8, CHROME, "μέταλλο", segments=8),
        T((15, 15, 28), 15, 10, 20, LAMP, "καπέλο", 24)]}


def plant_pot():
    return {"name": "Φυτό σε γλάστρα", "category": ("Διακόσμηση",), "expect_cm": [60, 60, 130], "parts": [
        T((30, 30, 0), 14, 19, 38, TERRACOTTA, "γλάστρα", 24),
        C((30, 30, 38), 1.5, 40, "#5a4630", "κορμός", segments=8),
        E((30, 30, 100), (30, 30, 30), GREEN, "φύλλωμα")]}


def floor_mirror():
    return {"name": "Καθρέφτης δαπέδου", "category": ("Διακόσμηση", "Υπνοδωμάτιο"), "expect_cm": [60, 30, 170], "parts": [
        B((0, 0, 0), (60, 4, 170), OAK, "κορνίζα"),
        B((4, -0.5, 4), (56, 0, 166), GLASS, "καθρέφτης"),
        B((5, 4, 0), (8, 30, 3), OAK, "στήριγμα"), B((52, 4, 0), (55, 30, 3), OAK, "στήριγμα")]}


def vase():
    return {"name": "Βάζο δαπέδου", "category": ("Διακόσμηση",), "expect_cm": [30, 30, 60], "parts": [
        T((15, 15, 0), 10, 15, 30, "#3e5566", "κεραμικό", 24),
        T((15, 15, 30), 15, 6, 25, "#3e5566", "κεραμικό", 24),
        C((15, 15, 55), 6, 5, "#3e5566", "κεραμικό", segments=24)]}


def garden_bench():
    w, d, h = 150, 60, 80
    parts = [*[B((x, 0, 0), (x + 6, d, 44), BLACK, "σκελετός") for x in (8, w - 14)],
             *[B((x, d - 6, 44), (x + 6, d - 2, h), BLACK, "σκελετός") for x in (8, w - 14)]]
    for k in range(4):
        parts.append(B((0, 4 + k * 12, 42), (w, 4 + k * 12 + 10, 45), PINE, "ξύλο"))
    for k in range(3):
        parts.append(B((0, d - 2, 52 + k * 9), (w, d, 59 + k * 9), PINE, "ξύλο"))
    return {"name": "Παγκάκι κήπου", "category": ("Εξωτερικοί χώροι",), "expect_cm": [w, d, h], "parts": parts}


def planter():
    w, d, h = 100, 40, 45
    return {"name": "Ζαρντινιέρα με φυτά", "category": ("Εξωτερικοί χώροι",), "expect_cm": [w, d, h], "parts": [
        B((0, 0, 0), (w, d, 40), STONE, "ζαρντινιέρα"),
        R((4, 4, 36), (w - 4, d - 4, h), 6, GREEN, "φυτά")]}


def sun_lounger():
    return {"name": "Ξαπλώστρα", "category": ("Εξωτερικοί χώροι",), "expect_cm": [65, 190, 85], "parts": [
        *legs(2, 2, 63, 188, 25, 4, PINE),
        R((0, 0, 25), (65, 130, 32), 3, PINE, "ξύλο"),
        R((3, 3, 32), (62, 128, 36), 3, WHITE, "μαξιλάρι"),
        R((0, 128, 25), (65, 190, 32), 3, PINE, "ξύλο"),
        R((3, 178, 32), (62, 188, 85), 3, WHITE, "μαξιλάρι")]}


def parasol():
    return {"name": "Ομπρέλα κήπου Ø250", "category": ("Εξωτερικοί χώροι",), "expect_cm": [250, 250, 240], "parts": [
        C((125, 125, 0), 25, 8, STONE, "βάση", segments=24),
        C((125, 125, 8), 2, 222, WHITE, "ιστός", segments=10),
        T((125, 125, 200), 125, 4, 40, "#e8e0cf", "πανί", 8)]}


def garden_table():
    return {"name": "Τραπέζι κήπου 4θέσιο", "category": ("Εξωτερικοί χώροι",), "expect_cm": [120, 80, 74], "parts": [
        *legs(4, 4, 116, 76, 70, 5, PINE),
        *[B((0, k * 70 / 6, 70), (120, k * 70 / 6 + 10, 74), PINE, "ξύλο") for k in range(7)]]}


def specs():
    from archforge.library import catalog_more
    return [
        sofa(210, FABRIC_GREY, "Καναπές τριθέσιος"), sofa(160, FABRIC_BLUE, "Καναπές διθέσιος"),
        armchair(), coffee_table(), tv_unit(), bookcase(),
        rug(200, 300, "#b9a98f", "Χαλί 200×300"), rug(160, 230, "#8a9aa8", "Χαλί 160×230"),
        dining_table(140, 80, "Τραπέζι τραπεζαρίας 4θέσιο", 4), dining_table(180, 90, "Τραπέζι τραπεζαρίας 6θέσιο", 6),
        round_table(), dining_chair(), bar_stool(),
        bed(160, "Διπλό κρεβάτι 160×200"), bed(90, "Μονό κρεβάτι 90×200"), nightstand(), dresser(),
        wc(), vanity(), bathtub(), shower(),
        fridge(), cooker(), hob(), dishwasher(), washing_machine(), hood(),
        desk(), office_chair(),
        floor_lamp(), table_lamp(),
        plant_pot(), floor_mirror(), vase(),
        garden_bench(), planter(), sun_lounger(), parasol(), garden_table(),
        *catalog_more.specs(),
    ]


CORE_VERSION = 2


def seed_core_library(force=False):
    """Build the core items into the local asset store (once per version)."""
    from archforge.library.assets import asset_dir, store_asset
    marker = asset_dir() / f".core-v{CORE_VERSION}"
    if marker.exists() and not force:
        return []
    ids = []
    for spec in specs():
        tris, colors, names = builder.build(spec)
        asset_id, _size = store_asset(spec["name"], tris, {
            "source": "archforge-core", "license": "project", "redistributable": True,
            "reference": spec.get("reference", "standard furniture dimensions; online pictures as visual reference only"),
        }, colors=colors, category=spec["category"], part_names=names)
        ids.append(asset_id)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("\n".join(ids), encoding="utf-8")
    return ids
