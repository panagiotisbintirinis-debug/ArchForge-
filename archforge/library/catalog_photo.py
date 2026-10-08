"""ArchForge core library, photo set (2026-10-08): generic types modelled from online photos.

The owner asked for objects "from photos": openly visible photos found online
(Openverse: CC0, public domain, CC BY, CC BY-SA; mostly Flickr) were looked at
with ``find_reference_photos.py`` and each type was modelled from them with
the simple solids of ``builder.py``.  The photo is reference only: it is not
stored, shipped or used as a texture, the model is our own generic type (no
brands, no copies of protected designer pieces), and the photo's page is kept
in the spec's ``reference`` (asset provenance), with its creator and licence in
a comment.

Sizes come from the photo's proportions anchored to one known dimension, noted
next to each item (seat 45, table 75, worktop 90, door 210 ...).
Front faces -Y, backs +Y, Z up, centimetres.
"""
from archforge.library.catalog import (BLACK, CERAMIC, CHROME, GLASS, GREEN, LAMP, OAK, PINE, STEEL, STONE,
                                       TERRACOTTA, WALNUT, WHITE, B, C, E, R, T, legs)

BRASS, IRON, RATTAN, LINEN_WHITE, TEAK = "#b5953f", "#3a3a3a", "#c8b088", "#f1ede4", "#8a6440"


def BM(a, b, width, thickness, color, part):
    return {"shape": "beam", "a": list(a), "b": list(b), "width": width, "thickness": thickness,
            "color": color, "part": part}


def TO(center, radius, tube, color, part, axis="z", arc=360.0, start=0.0, segments=24, sides=8):
    return {"shape": "torus", "center": list(center), "radius": radius, "tube": tube, "axis": axis, "arc": arc,
            "start": start, "segments": segments, "sides": sides, "color": color, "part": part}


def L(base, profile, color, part, segments=24):
    return {"shape": "lathe", "base": list(base), "profile": [list(p) for p in profile], "color": color,
            "part": part, "segments": segments}


def item(name, category, size, reference, parts):
    return {"name": name, "category": category, "expect_cm": list(size), "reference": reference, "parts": parts}


# ------------------------------------------------------------------ living room
def chesterfield_sofa():
    # Paris on Ponce & Le Maison Rouge, CC BY 2.0. Anchor: seat 45; rolled arms level with the back (78).
    w, d, h, arm = 215, 95, 78, 20
    leather, button = "#6e1f24", "#4a1418"
    parts = [*[E((x, y, 4), (5, 5, 4), WALNUT, "πόδια") for x in (8, w - 8) for y in (8, d - 8)],
             R((0, 0, 4), (w, d, 38), 4, leather, "δέρμα"),
             R((arm, 3, 38), (w - arm, d - 18, 45), 4, leather, "δέρμα"),
             R((0, d - 18, 38), (w, d, h - 9), 3, leather, "δέρμα"), C((0, d - 9, h - 9), 9, w, leather, "δέρμα", "x"),
             R((0, 0, 38), (arm, d, h - 10), 3, leather, "δέρμα"), C((10, 0, h - 10), 10, d, leather, "δέρμα", "y"),
             R((w - arm, 0, 38), (w, d, h - 10), 3, leather, "δέρμα"), C((w - 10, 0, h - 10), 10, d, leather, "δέρμα", "y")]
    for z in (52, 61):                                    # tufting buttons on the back
        for k in range(9):
            x = arm + 10 + k * (w - 2 * arm - 20) / 8 + (8 if z == 61 and k < 8 else 0)
            parts.append(B((x - 0.8, d - 18.6, z - 0.8), (x + 0.8, d - 18, z + 0.8), button, "κουμπιά"))
    return item("Καναπές chesterfield δερμάτινος", ("Σαλόνι",), (w, d, h),
                "https://www.flickr.com/photos/93887713@N00/8741822066", parts)


def midcentury_armchair():
    # CastawayVintage, CC BY 2.0. Anchor: seat 44, arm rest 62; open teak frame, loose cushions.
    w, d = 68, 76
    wood, seat, back = "#6b4226", "#d9542b", "#5c5f66"
    parts = []
    for x in (3, w - 3):
        parts += [BM((x, 10, 0), (x, 6, 60), 4, 4, wood, "σκελετός"),             # front leg / arm post
                  BM((x, d - 24, 0), (x, d - 3, 80), 4, 4, wood, "σκελετός"),      # back leg / stile
                  BM((x, 2, 61), (x, d - 9, 63), 6, 2.5, wood, "σκελετός")]        # arm rest
    parts += [B((3, 8, 30), (w - 3, 11, 36), wood, "σκελετός"), B((3, d - 26, 30), (w - 3, d - 23, 36), wood, "σκελετός"),
              R((6, 6, 36), (w - 6, d - 22, 44), 3, seat, "κάθισμα"),
              BM((w / 2, d - 22, 46), (w / 2, d - 9, 76), w - 12, 8, back, "πλάτη")]
    return item("Πολυθρόνα ρετρό με ξύλινο σκελετό", ("Σαλόνι",), (w, d, 80),
                "https://www.flickr.com/photos/44483053@N05/5583977007", parts)


def wingback_chair():
    # Kai Hendry, CC BY 2.0 (slip-covered wing chair). Anchor: seat 46, back 105.
    w, d, h = 80, 85, 105
    cloth = "#d8d0bd"
    return item("Πολυθρόνα με «αυτιά» ντυμένη", ("Σαλόνι",), (w, d, h),
                "https://www.flickr.com/photos/16105436@N00/207948040", [
                    R((0, 0, 0), (w, d, 39), 3, cloth, "ύφασμα"),
                    R((14, 3, 39), (w - 14, d - 20, 46), 4, cloth, "ύφασμα"),
                    R((8, d - 20, 39), (w - 8, d, h), 6, cloth, "ύφασμα"),
                    R((0, d - 42, 50), (10, d, 96), 4, cloth, "ύφασμα"), R((w - 10, d - 42, 50), (w, d, 96), 4, cloth, "ύφασμα"),
                    R((0, 0, 39), (14, d - 20, 56), 3, cloth, "ύφασμα"), C((7, 0, 56), 7, d - 20, cloth, "ύφασμα", "y"),
                    R((w - 14, 0, 39), (w, d - 20, 56), 3, cloth, "ύφασμα"), C((w - 7, 0, 56), 7, d - 20, cloth, "ύφασμα", "y"),
                    E((w / 2, d - 26, 62), (17, 5, 15), "#a03a2c", "μαξιλάρι")])


def carved_settee():
    # JeepersMedia, CC BY 2.0 (carved settee in red velvet). Anchor: seat 46, crest 100.
    w, d = 130, 66
    wood, velvet = "#4a1a12", "#b0141e"
    parts = [BM((6, 6, 0), (8, 9, 34), 5, 5, wood, "σκελετός"), BM((w - 6, 6, 0), (w - 8, 9, 34), 5, 5, wood, "σκελετός"),
             BM((6, d - 4, 0), (7, d - 8, 34), 5, 5, wood, "σκελετός"), BM((w - 6, d - 4, 0), (w - 7, d - 8, 34), 5, 5, wood, "σκελετός"),
             B((3, 4, 30), (w - 3, d - 4, 38), wood, "σκελετός"),
             R((6, 4, 38), (w - 6, d - 10, 46), 3, velvet, "βελούδο"),
             R((10, d - 11, 46), (w - 10, d - 4, 86), 4, velvet, "βελούδο"),
             B((4, d - 12, 84), (w - 4, d - 3, 89), wood, "σκελετός"),
             E((w / 2, d - 7.5, 89), (24, 4.5, 11), wood, "σκελετός"),
             E((w / 2, d - 12, 66), (15, 1.5, 12), "#8c0f18", "βελούδο")]
    for x in (5, w - 5):
        parts += [BM((x, 7, 38), (x, 6, 64), 5, 4, wood, "σκελετός"), BM((x, 2, 65), (x, d - 6, 70), 7, 3, wood, "σκελετός"),
                  B((x - 4, d - 12, 46), (x + 4, d - 3, 84), wood, "σκελετός")]
    return item("Καναπές κλασικός σκαλιστός βελούδινος", ("Σαλόνι",), (w, d, 100),
                "https://www.flickr.com/photos/39160147@N03/9695393817", parts)


def rocking_chair():
    # Sarabbit, CC BY-SA 2.0 (painted spindle-back rocker). Anchor: seat 42, rocker 80 long.
    w, blue = 58, "#7fa6c9"
    parts = []
    for x in (3, w - 3):
        parts += [TO((x, 40, 151.5), 150, 1.8, blue, "ξύλο", axis="x", arc=32, start=254, segments=12),
                  BM((x, 19, 3.5), (x, 20, 62), 4, 4, blue, "ξύλο"),
                  BM((x, 58, 2), (x, 67, 105), 4, 4, blue, "ξύλο"),
                  BM((x, 15, 62), (x, 63, 64), 6, 2.5, blue, "ξύλο")]
    parts += [R((0, 14, 38), (w, 61, 42), 4, blue, "ξύλο"), E((w / 2, 36, 42), (14, 12, 0.6), "#e8d9a8", "μαξιλάρι"),
              B((1, 64.5, 95), (w - 1, 69, 104), blue, "ξύλο")]
    for x in (14, 21.5, 29, 36.5, 44):
        parts.append(BM((x, 60, 42), (x, 66, 95), 2.5, 2.5, blue, "ξύλο"))
    return item("Κουνιστή πολυθρόνα ξύλινη", ("Σαλόνι",), (w, 80, 105),
                "https://www.flickr.com/photos/92455770@N00/13339068414", parts)


def club_chair():
    # lacasavictoria, CC BY 2.0 (grey leather club chair). Anchor: seat 45, back 78.
    w, d, h = 90, 90, 78
    leather = "#b9bdb8"
    return item("Πολυθρόνα club δερμάτινη", ("Σαλόνι",), (w, d, h),
                "https://www.flickr.com/photos/19568916@N07/5982555269", [
                    R((0, 0, 0), (w, d, 38), 10, leather, "δέρμα"),
                    R((18, 4, 38), (w - 18, d - 22, 45), 6, leather, "δέρμα"),
                    R((0, d - 22, 38), (w, d, h - 4), 10, leather, "δέρμα"), E((w / 2, d - 11, h - 4), (w / 2 - 6, 10, 4), leather, "δέρμα"),
                    R((0, 0, 38), (18, d - 6, 64), 8, leather, "δέρμα"), E((9, (d - 6) / 2, 64), (9, (d - 6) / 2, 5), leather, "δέρμα"),
                    R((w - 18, 0, 38), (w, d - 6, 64), 8, leather, "δέρμα"), E((w - 9, (d - 6) / 2, 64), (9, (d - 6) / 2, 5), leather, "δέρμα")])


def nesting_tables():
    # bitmask, CC BY-SA 2.0 (teak nest of three). Anchor: largest table 50 high.
    teak = "#a0623a"
    parts = []
    for w, d, h in ((55, 40, 50), (48, 37, 45), (41, 34, 40)):
        x0 = (55 - w) / 2
        for x in (x0, x0 + w - 2.5):
            parts += [B((x, 1, 0), (x + 2.5, 3.5, h - 2), teak, "ξύλο"), B((x, d - 3.5, 0), (x + 2.5, d - 1, h - 2), teak, "ξύλο"),
                      B((x, 3.5, 6), (x + 2.5, d - 3.5, 8), teak, "ξύλο")]
        parts.append(B((x0, 0, h - 2), (x0 + w, d, h), teak, "ξύλο"))
    return item("Τραπεζάκια ζιγκόνι (σετ 3)", ("Σαλόνι",), (55, 40, 50),
                "https://www.flickr.com/photos/35034348161@N01/7370061562", parts)


def bean_bag():
    # PersonalCreations.com, CC BY 2.0. Anchor: Ø90, 70 high (adult bean bag).
    blue = "#5d6fa8"
    return item("Πουφ-σακί (bean bag)", ("Σαλόνι", "Παιδικό"), (90, 90, 70),
                "https://www.flickr.com/photos/127294011@N07/20681977834", [
                    E((45, 45, 22), (45, 45, 22), blue, "ύφασμα"), E((45, 60, 40), (38, 28, 30), blue, "ύφασμα")])


def peacock_chair():
    # soapylovedeb, CC BY-SA 2.0 (fan-back wicker chair). Anchor: seat 46, fan back 150.
    w, rattan = 106, "#c9b98f"
    cx = w / 2
    return item("Πολυθρόνα ψάθινη «παγώνι»", ("Σαλόνι", "Εξωτερικοί χώροι"), (w, 75, 150),
                "https://www.flickr.com/photos/60608121@N00/5157926511", [
                    L((cx, 34, 0), ((30, 0), (24, 8), (16, 22), (24, 36), (31, 40)), rattan, "ψάθα"),
                    C((cx, 34, 40), 31, 6, "#b8c4cc", "μαξιλάρι", segments=28),
                    TO((cx, 34, 52), 34, 4, rattan, "ψάθα", arc=180, segments=16),
                    E((cx, 66, 96), (53, 6, 54), rattan, "ψάθα")])


def glass_coffee_table():
    # lacasavictoria, CC BY 2.0 (glass top, square steel tube frame). Anchor: height 40.
    w, d, h = 120, 60, 40
    parts = [*legs(0, 0, w, d, h - 2, 3, STEEL),
             B((3, 0, h - 5), (w - 3, 3, h - 2), STEEL, "μέταλλο"), B((3, d - 3, h - 5), (w - 3, d, h - 2), STEEL, "μέταλλο"),
             B((0, 3, h - 5), (3, d - 3, h - 2), STEEL, "μέταλλο"), B((w - 3, 3, h - 5), (w, d - 3, h - 2), STEEL, "μέταλλο"),
             B((0, 0, h - 2), (w, d, h), GLASS, "γυαλί")]
    return item("Τραπεζάκι σαλονιού γυάλινο με ατσάλινο σκελετό", ("Σαλόνι",), (w, d, h),
                "https://www.flickr.com/photos/19568916@N07/4999300224", parts)


def futon_sofa_bed():
    # Wonderlane, CC BY 2.0 (click-clack sofa bed with bolsters). Anchor: seat 42, opens to 190x110.
    w, d, red = 190, 92, "#b3222e"
    parts = [*[C((x, y, 0), 2.5, 14, CHROME, "πόδια", segments=12) for x in (10, w - 10) for y in (10, d - 10)],
             B((6, 6, 14), (w - 6, d - 6, 18), BLACK, "σκελετός"),
             R((0, 0, 18), (w, d - 8, 42), 4, red, "ύφασμα"),
             BM((w / 2, d - 18, 42), (w / 2, d - 7, 84), w, 12, red, "ύφασμα"),
             C((12, 4, 52), 10, d - 30, red, "ύφασμα", "y"), C((w - 12, 4, 52), 10, d - 30, red, "ύφασμα", "y")]
    for k in range(1, 6):
        parts.append(B((k * w / 6 - 0.5, -0.3, 30), (k * w / 6 + 0.5, d - 20, 42.3), "#8a1822", "ραφές"))
    return item("Καναπές-κρεβάτι με μπολστερ", ("Σαλόνι",), (w, d, 86),
                "https://www.flickr.com/photos/71401718@N00/3134708752", parts)


def leather_loveseat():
    # Birdies100, CC BY-SA 2.0 (padded leather two-seater). Anchor: seat 45, back 88.
    w, d, h, arm = 150, 90, 88, 22
    tan = "#8a4a24"
    parts = [*legs(6, 6, w - 6, d - 6, 6, 5, BLACK),
             R((0, 0, 6), (w, d, 36), 6, tan, "δέρμα"),
             R((arm, 2, 36), (w / 2, d - 24, 46), 7, tan, "δέρμα"), R((w / 2, 2, 36), (w - arm, d - 24, 46), 7, tan, "δέρμα"),
             R((arm - 2, d - 26, 40), (w / 2, d - 6, h), 9, tan, "δέρμα"), R((w / 2, d - 26, 40), (w - arm + 2, d - 6, h), 9, tan, "δέρμα"),
             R((0, d - 12, 36), (w, d, 80), 6, tan, "δέρμα"),
             R((0, 0, 36), (arm, d, 62), 8, tan, "δέρμα"), E((arm / 2, d / 2, 62), (arm / 2, d / 2, 4), tan, "δέρμα"),
             R((w - arm, 0, 36), (w, d, 62), 8, tan, "δέρμα"), E((w - arm / 2, d / 2, 62), (arm / 2, d / 2, 4), tan, "δέρμα")]
    return item("Καναπές διθέσιος δερμάτινος αφράτος", ("Σαλόνι",), (w, d, h),
                "https://www.flickr.com/photos/50113019@N00/4936041292", parts)


def wicker_daybed():
    # YourCastlesDecor, CC BY 2.0 (white wicker daybed). Anchor: mattress 90x190, seat 46.
    w, d = 206, 98
    wicker = "#efece4"
    parts = [B((8, 0, 6), (w - 8, d - 6, 34), wicker, "ψάθα"),
             B((0, d - 8, 0), (w, d, 90), wicker, "ψάθα"),
             B((0, 0, 0), (8, d, 76), wicker, "ψάθα"), B((w - 8, 0, 0), (w, d, 76), wicker, "ψάθα"),
             C((4, 0, 76), 4, d, wicker, "ψάθα", "y"), C((w - 4, 0, 76), 4, d, wicker, "ψάθα", "y"),
             C((0, d - 4, 90), 4, w, wicker, "ψάθα", "x"),
             R((8, 2, 34), (w - 8, d - 8, 46), 4, "#e9dfe6", "στρώμα")]
    for k, col in enumerate(("#e7c3cf", "#f4efe6", "#d7a6b5", "#f4efe6")):
        x = 34 + k * 46
        parts.append(E((x, d - 18, 60), (22, 7, 15), col, "μαξιλάρια"))
    return item("Ντιβάνι ψάθινο (daybed)", ("Σαλόνι", "Εξωτερικοί χώροι"), (w, d, 94),
                "https://www.flickr.com/photos/101592688@N07/14009269620", parts)


def specs():
    return [
        chesterfield_sofa(), midcentury_armchair(), wingback_chair(), carved_settee(), rocking_chair(), club_chair(),
        nesting_tables(), bean_bag(), peacock_chair(), glass_coffee_table(), futon_sofa_bed(), leather_loveseat(),
        wicker_daybed(),
    ]
