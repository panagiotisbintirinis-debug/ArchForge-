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
import math

from archforge.library.catalog import (BLACK, CERAMIC, CHROME, GLASS, GLASS_DARK, LAMP, PINE, STEEL, STONE, TERRACOTTA,
                                       WALNUT, WHITE, B, C, E, R, T, legs)

BRASS, IRON, RATTAN, APPLIANCE_WHITE, WATER_BLUE = "#b5953f", "#3a3a3a", "#c8b088", "#f4f4f2", "#6fa9bd"


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
    return item("Πολυθρόνα ρετρό με ξύλινο σκελετό", ("Σαλόνι",), (68, 73, 81),
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
    return item("Καναπές κλασικός σκαλιστός βελούδινος", ("Σαλόνι",), (128, 63.1, 100.3),
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
    return item("Κουνιστή πολυθρόνα ξύλινη", ("Σαλόνι",), (58, 83.7, 105.5),
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
    return item("Πολυθρόνα ψάθινη «παγώνι»", ("Σαλόνι", "Εξωτερικοί χώροι"), (106, 69, 150),
                "https://www.flickr.com/photos/60608121@N00/5157926511", [
                    L((cx, 34, 0), ((30, 0), (24, 8), (16, 22), (24, 36), (31, 40)), rattan, "ψάθα"),
                    C((cx, 34, 40), 31, 6, "#b8c4cc", "μαξιλάρι", segments=28),
                    E((cx, 64, 92), (53, 8, 58), rattan, "ψάθα"),
                    E((cx - 40, 54, 72), (9, 16, 34), rattan, "ψάθα"), E((cx + 40, 54, 72), (9, 16, 34), rattan, "ψάθα")])


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




# ------------------------------------------------------------------ dining
def bentwood_chair():
    # williamd, CC BY-SA 2.0 (café chair with cane seat). Anchor: seat 46.
    w, d, wood = 42, 48, "#3b2418"
    parts = [BM((8, 9, 0), (10, 11, 44), 3, 3, wood, "ξύλο"), BM((34, 9, 0), (32, 11, 44), 3, 3, wood, "ξύλο"),
             BM((8, d - 4, 0), (8, d - 6, 44), 3, 3, wood, "ξύλο"), BM((34, d - 4, 0), (34, d - 6, 44), 3, 3, wood, "ξύλο"),
             BM((6, d - 6, 44), (6, d - 3, 70), 3, 3, wood, "ξύλο"), BM((36, d - 6, 44), (36, d - 3, 70), 3, 3, wood, "ξύλο"),
             TO((21, d - 3, 70), 15, 1.5, wood, "ξύλο", axis="y", arc=180, segments=14),
             TO((21, 24, 18), 14, 1, wood, "ξύλο", segments=20),
             C((21, 24, 43), 20, 3, wood, "ξύλο", segments=28), C((21, 24, 45.5), 17, 0.6, "#d9c08a", "ψάθα", segments=28)]
    return item("Καρέκλα καφενείου λυγιστή με ψάθα", ("Τραπεζαρία",), (40, 42.5, 86.6),
                "https://www.flickr.com/photos/34501183@N00/3766631235", parts)


def windsor_chair():
    # karitsu, CC BY-SA 2.0 (bow-back spindle chair). Anchor: seat 45, bow 100.
    w, d, wood = 50, 50, "#3a2a20"
    parts = [R((0, 4, 41), (w, 46, 45), 6, wood, "ξύλο"),
             *[BM((x0, y0, 0), (x1, y1, 41), 3.5, 3.5, wood, "ξύλο")
               for x0, y0, x1, y1 in ((3, 3, 9, 9), (47, 3, 41, 9), (3, 47, 9, 41), (47, 47, 41, 41))],
             BM((6, 6, 16), (6, 44, 16), 2, 2, wood, "ξύλο"), BM((44, 6, 16), (44, 44, 16), 2, 2, wood, "ξύλο"),
             BM((6, 25, 16), (44, 25, 16), 2, 2, wood, "ξύλο"),
             TO((25, 44, 74), 23, 1.6, wood, "ξύλο", axis="y", arc=180, segments=16),
             BM((2, 44, 45), (2, 44, 74), 3, 3, wood, "ξύλο"), BM((48, 44, 45), (48, 44, 74), 3, 3, wood, "ξύλο")]
    for x in (11, 18, 25, 32, 39):
        top = 74 + math.sqrt(23 ** 2 - (x - 25) ** 2) - 1
        parts.append(BM((x, 42, 45), (x, 44, top), 1.6, 1.6, wood, "ξύλο"))
    return item("Καρέκλα windsor με τοξωτή πλάτη", ("Τραπεζαρία",), (50, 48.9, 99),
                "https://www.flickr.com/photos/15142906@N00/6494185503", parts)


def taverna_chair():
    # Mustang Joe, CC0 (white Greek taverna chairs). Anchor: seat 45, back 88.
    w, d, white, rush = 42, 44, "#f2f0ea", "#c9a86a"
    parts = [B((2, 2, 0), (5.5, 5.5, 45), white, "ξύλο"), B((w - 5.5, 2, 0), (w - 2, 5.5, 45), white, "ξύλο"),
             BM((3.75, d - 4, 0), (3.75, d - 2, 88), 3.5, 3.5, white, "ξύλο"),
             BM((w - 3.75, d - 4, 0), (w - 3.75, d - 2, 88), 3.5, 3.5, white, "ξύλο"),
             B((2, 2, 41), (w - 2, d - 3, 44), white, "ξύλο"), B((4, 4, 44), (w - 4, d - 4, 45.5), rush, "ψάθα"),
             B((5.5, 3, 12), (w - 5.5, 4.5, 15), white, "ξύλο"), B((5.5, 3, 20), (w - 5.5, 4.5, 23), white, "ξύλο"),
             B((2.5, 5.5, 14), (5, d - 4, 16), white, "ξύλο"), B((w - 5, 5.5, 14), (w - 2.5, d - 4, 16), white, "ξύλο"),
             B((5, d - 3.5, 66), (w - 5, d - 1.5, 71), white, "ξύλο"), B((5, d - 3, 79), (w - 5, d - 1, 85), white, "ξύλο")]
    return item("Καρέκλα ταβέρνας ψάθινη", ("Τραπεζαρία", "Εξωτερικοί χώροι"), (38, 41.8, 88.1),
                "https://www.flickr.com/photos/63234672@N04/29741939366", parts)


def farmhouse_table():
    # ju5ti, CC BY-SA 2.0 (rustic plank table). Anchor: table 76.
    w, d, h, wood = 200, 90, 76, "#6b4a2e"
    parts = [*legs(4, 4, w - 4, d - 4, h - 5, 10, wood),
             B((14, 5, h - 17), (w - 14, 8, h - 5), wood, "ξύλο"), B((14, d - 8, h - 17), (w - 14, d - 5, h - 5), wood, "ξύλο")]
    for k in range(4):
        parts.append(B((0, k * d / 4 + 0.15, h - 5), (w, (k + 1) * d / 4 - 0.15, h), wood, "ξύλο"))
    return item("Τραπέζι αγροτικό μασίφ 200", ("Τραπεζαρία",), (w, d - 0.3, h),
                "https://www.flickr.com/photos/87285907@N00/4315624637", parts)


def pedestal_table():
    # Paris on Ponce & Le Maison Rouge, CC BY 2.0 (round table on a flared base). Anchor: table 75.
    return item("Τραπέζι στρογγυλό με βάση-καμπάνα Ø110", ("Τραπεζαρία",), (110, 110, 75),
                "https://www.flickr.com/photos/93887713@N00/8416559369", [
                    L((55, 55, 0), ((30, 0), (30, 1.5), (20, 4), (8, 20), (6, 45), (7, 66), (14, 72)), WHITE, "βάση", 32),
                    C((55, 55, 72), 55, 3, WHITE, "επιφάνεια", segments=48)])


def industrial_stool():
    # Bernt Rostad, CC BY 2.0 (timber seat on black steel legs). Anchor: bar seat 75.
    parts = [C((22, 22, 72), 18, 3.5, "#8a5a34", "ξύλο", segments=28), TO((22, 22, 24), 16.5, 1, IRON, "μέταλλο", segments=20)]
    for cx, cy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        parts.append(BM((22 + cx * 19, 22 + cy * 19, 0), (22 + cx * 10, 22 + cy * 10, 72), 2.5, 2.5, IRON, "μέταλλο"))
    return item("Σκαμπό μπαρ βιομηχανικό", ("Τραπεζαρία",), (41.5, 41.5, 75.7),
                "https://www.flickr.com/photos/67975030@N00/9342996242", parts)


def bar_cart_industrial():
    # kurafire, CC BY 2.0 (steel and wood drinks trolley). Anchor: top shelf 85.
    w, d = 80, 40
    parts = [*[C((x, y, 0), 3, 2, BLACK, "ρόδες", "y", 12) for x in (5, w - 5) for y in (2, d - 4)],
             *[B((x, y, 6), (x + 2.5, y + 2.5, 92), IRON, "μέταλλο") for x in (0, w - 2.5) for y in (0, d - 2.5)],
             C((-3, d / 2, 88), 1.2, w + 6, IRON, "μέταλλο", "x", 10)]
    for z in (10, 45, 80):
        parts += [B((2.5, 2.5, z), (w - 2.5, d - 2.5, z + 3), "#8a5a34", "ξύλο"),
                  B((0, 0, z + 3), (w, 1, z + 6), IRON, "μέταλλο"), B((0, d - 1, z + 3), (w, d, z + 6), IRON, "μέταλλο")]
    return item("Τρόλεϊ μπαρ βιομηχανικό", ("Τραπεζαρία",), (86, 40, 95),
                "https://www.flickr.com/photos/62449696@N00/24029342729", parts)


def bar_cart_brass():
    # FTD Florists, CC BY 2.0 (oval brass serving trolley). Anchor: top tray 80.
    w, d = 76, 46
    parts = [*[C((x, y, 0), 3, 2, BLACK, "ρόδες", "y", 12) for x in (10, w - 10) for y in (3, d - 5)],
             *[C((x, y, 3), 1.2, 76, BRASS, "ορείχαλκος", segments=10) for x in (10, w - 10) for y in (4, d - 4)]]
    for z in (14, 76):
        parts += [R((0, 0, z), (w, d, z + 1), 22, GLASS, "γυαλί"), R((0, 0, z + 1), (w, d, z + 4), 22, BRASS, "ορείχαλκος")]
    return item("Τρόλεϊ σερβιρίσματος ορειχάλκινο οβάλ", ("Τραπεζαρία", "Σαλόνι"), (76, 46, 83),
                "https://www.flickr.com/photos/142320496@N06/31486747721", parts)


def kitchen_island():
    # ChalonHandmade, CC BY 2.0 (painted free-standing island with timber top). Anchor: worktop 90.
    w, d, blue = 120, 70, "#3f5b78"
    parts = [B((2, 2, 0), (w - 2, d - 2, 10), "#2f4458", "βάση"), B((0, 0, 10), (w, d, 86), blue, "σώμα"),
             B((-3, -3, 86), (w + 3, d + 3, 90), "#c99a62", "πάγκος")]
    for x0 in (4, w / 2 + 1):
        parts += [B((x0, -0.5, 14), (x0 + w / 2 - 5, 0, 60), "#4b6a8a", "πόρτες"),
                  B((x0, -0.5, 63), (x0 + w / 2 - 5, 0, 82), "#4b6a8a", "συρτάρια"),
                  B((x0 + 20, -2, 71), (x0 + 35, -0.5, 73), BRASS, "χερούλια")]
    return item("Νησίδα κουζίνας ελεύθερη με ξύλινο πάγκο", ("Τραπεζαρία",), (w + 6, d + 6, 90),
                "https://www.flickr.com/photos/68141625@N06/6206817133", parts)


# ------------------------------------------------------------------ bedroom
def canopy_bed():
    # MAZZALI bespoke italian furniture, CC BY-SA 2.0 (four-poster). Anchor: mattress 160x200 on 57, posts 210.
    w, L, h, cream = 172, 212, 210, "#e8dfc9"
    parts = [*[B((x, y, 0), (x + 6, y + 6, h), cream, "σκελετός") for x in (0, w - 6) for y in (0, L - 6)],
             B((0, 0, h - 6), (w, 6, h), cream, "σκελετός"), B((0, L - 6, h - 6), (w, L, h), cream, "σκελετός"),
             B((0, 6, h - 6), (6, L - 6, h), cream, "σκελετός"), B((w - 6, 6, h - 6), (w, L - 6, h), cream, "σκελετός"),
             B((6, 6, 15), (w - 6, L - 6, 35), cream, "σκελετός"),
             R((8, L - 12, 35), (w - 8, L - 6, 115), 3, "#d8cfae", "κεφαλάρι"),
             R((6, 8, 35), (w - 6, L - 12, 57), 4, WHITE, "στρώμα"),
             R((5, 10, 50), (w - 5, 90, 59), 3, "#8a6a5a", "κουβέρτα"),
             R((14, L - 60, 57), (w / 2 - 3, L - 16, 70), 5, WHITE, "μαξιλάρια"),
             R((w / 2 + 3, L - 60, 57), (w - 14, L - 16, 70), 5, WHITE, "μαξιλάρια")]
    return item("Κρεβάτι με ουρανό 160×200", ("Υπνοδωμάτιο",), (w, L, h),
                "https://www.flickr.com/photos/26098878@N06/3873602461", parts)


def armoire():
    # frenchfinds.co.uk, CC BY 2.0 (painted French armoire). Anchor: height 210 (door height).
    w, d, h, paint, panel = 110, 55, 210, "#e9e4d8", "#dcd5c4"
    parts = [*[BM((x, y, 0), (x + (3 if x < w / 2 else -3), y, 14), 5, 5, paint, "σκελετός") for x in (6, w - 6) for y in (6, d - 6)],
             B((0, 2, 12), (w, d, h - 12), paint, "σκελετός"), B((-2, 0, h - 12), (w + 2, d + 2, h - 6), paint, "σκελετός"),
             E((w / 2, 4, h - 6), (26, 3, 6), paint, "σκελετός"),
             B((4, 1.5, 88), (w / 2 - 1, 2, h - 18), panel, "πόρτες"), B((w / 2 + 1, 1.5, 88), (w - 4, 2, h - 18), panel, "πόρτες")]
    for k in range(3):
        z = 16 + k * 23
        parts += [B((4, 1.5, z), (w - 4, 2, z + 21), panel, "συρτάρια"), B((w / 2 - 7, 0, z + 9), (w / 2 + 7, 1.5, z + 11), BRASS, "χερούλια")]
    return item("Ντουλάπα-αρμάρι κλασική", ("Υπνοδωμάτιο",), (w + 4, d + 2, h),
                "https://www.flickr.com/photos/23717595@N05/6430631951", parts)


def steamer_trunk():
    # boingr, CC BY-SA 2.0 (striped travel trunk). Anchor: 90 long (classic steamer trunk).
    w, d, h, red = 90, 50, 50, "#7a2e22"
    parts = [R((0, 0, 0), (w, d, h), 2, red, "σώμα"), B((w / 2 - 4, -1, h - 12), (w / 2 + 4, 0, h - 4), BRASS, "κλειδαριά")]
    for x in (18, 42, 66):
        parts.append(B((x, -0.6, 0), (x + 6, d + 0.6, h + 0.6), "#2b211c", "λωρίδες"))
    for x in (-0.5, w - 5.5):
        parts += [B((x, -0.8, 0), (x + 6, 6, 6), BRASS, "γωνίες"), B((x, -0.8, h - 5.5), (x + 6, 6, h + 0.6), BRASS, "γωνίες")]
    return item("Μπαούλο ταξιδιού", ("Υπνοδωμάτιο", "Διακόσμηση"), (w + 1, d + 1.4, h + 0.6),
                "https://www.flickr.com/photos/10292464@N06/4152598914", parts)


def painted_chest():
    # apartment28, CC BY 2.0 (turquoise painted chest of drawers). Anchor: 100 high.
    w, d, h, paint, front = 80, 45, 100, "#5fb3b0", "#6fc2be"
    parts = [*[BM((x, y, 0), (x + (2 if x < w / 2 else -2), y, 10), 4, 4, paint, "σκελετός") for x in (4, w - 4) for y in (4, d - 4)],
             B((0, 1, 10), (w, d, h - 3), paint, "σκελετός"), B((-1, 0, h - 3), (w + 1, d + 1, h), paint, "σκελετός")]
    for z0, z1 in ((12, 30), (31, 49), (50, 68), (69, 82)):
        parts.append(B((3, 0.5, z0), (w - 3, 1, z1), front, "συρτάρια"))
        for x in (w / 4, 3 * w / 4):
            parts.append(E((x, -0.6, (z0 + z1) / 2), (1.6, 1.2, 1.6), "#c0392b", "πόμολα"))
    for x0, x1 in ((3, w / 2 - 0.5), (w / 2 + 0.5, w - 3)):
        parts += [B((x0, 0.5, 83), (x1, 1, h - 5), front, "συρτάρια"), E(((x0 + x1) / 2, -0.6, 90), (1.6, 1.2, 1.6), "#c0392b", "πόμολα")]
    return item("Συρταριέρα βαμμένη vintage", ("Υπνοδωμάτιο",), (w + 2, d + 2.8, h),
                "https://www.flickr.com/photos/52862371@N08/4868858377", parts)


def writing_desk_small():
    # CastawayVintage, CC BY 2.0 (small painted writing desk with a gallery). Anchor: desk 75.
    w, d, paint = 90, 50, "#8fa6b3"
    parts = [*[B((x, y, 0), (x + 3.5, y + 3.5, 72), paint, "σκελετός") for x in (1, w - 4.5) for y in (1, d - 4.5)],
             B((0, 0, 64), (w, d, 72), paint, "σκελετός"), B((-1, -1, 72), (w + 1, d + 1, 75), paint, "σκελετός"),
             B((30, -0.5, 65), (60, 0, 71), "#9fb6c3", "συρτάρι"),
             B((2, d - 16, 75), (w - 2, d - 1, 95), paint, "σκελετός")]
    for x0 in (6, 33, 60):
        parts.append(B((x0, d - 16.5, 79), (x0 + 24, d - 16, 91), "#9fb6c3", "συρτάρια"))
    return item("Γραφειάκι vintage με συρταράκια", ("Υπνοδωμάτιο", "Γραφείο"), (w + 2, d + 2, 95),
                "https://www.flickr.com/photos/44483053@N05/5573019037", parts)


# ------------------------------------------------------------------ children
def teepee():
    # donnierayjones, CC BY 2.0 (striped play tent). Anchor: 170 high (a child stands inside).
    c, white, green = 60, "#f1ede4", "#8cbf3f"
    parts = [T((c, c, 0), 58, 40, 45, white, "ύφασμα", 6), T((c, c, 45), 40, 27, 30, green, "ύφασμα", 6),
             T((c, c, 75), 27, 13, 35, white, "ύφασμα", 6), T((c, c, 110), 13, 6, 25, green, "ύφασμα", 6),
             ]
    for k in range(6):
        a = math.radians(60 * k + 30)
        parts.append(BM((c + 52 * math.cos(a), c + 52 * math.sin(a), 0), (c - 8 * math.cos(a), c - 8 * math.sin(a), 170),
                        2.5, 2.5, PINE, "κοντάρια"))
    return item("Σκηνή παιδική (teepee)", ("Παιδικό",), (116, 106, 171),
                "https://www.flickr.com/photos/11946169@N00/27749598336", parts)


def rocking_horse():
    # whatsthatpicture, public domain (antique bow rocking horse). Anchor: seat 55 for a 3-5 year old.
    y, coat, red = 17.5, "#e8e4dc", "#8a2b20"
    parts = [TO((50, 6, 131.5), 130, 1.5, red, "κουνιστές", axis="y", arc=44, start=158, segments=12),
             TO((50, 29, 131.5), 130, 1.5, red, "κουνιστές", axis="y", arc=44, start=158, segments=12),
             B((22, 4, 8), (26, 31, 10), red, "κουνιστές"), B((74, 4, 8), (78, 31, 10), red, "κουνιστές"),
             E((50, y, 52), (26, 10, 11), coat, "άλογο"),
             BM((70, y, 56), (80, y, 76), 9, 7, coat, "άλογο"), E((86, y, 76), (10, 5.5, 6), coat, "άλογο"),
             BM((76, y, 74), (60, y, 60), 2, 8, "#5a4a3a", "χαίτη"), BM((26, y, 54), (20, y, 34), 3, 3, "#5a4a3a", "χαίτη"),
             R((40, y - 10.5, 60), (58, y + 10.5, 64), 3, red, "σέλα")]
    for x0, x1 in ((34, 26), (66, 74)):
        for yy in (11, 24):
            parts.append(BM((x0, yy, 46), (x1, yy, 9), 4, 4, coat, "άλογο"))
    return item("Αλογάκι κουνιστό", ("Παιδικό",), (98.5, 26, 82),
                "https://www.flickr.com/photos/24469639@N00/2434120780", parts)


def kids_chair(x, y, facing, color, seat=30):
    """Small child chair centred on (x, y); facing +1 looks to +X, -1 to -X."""
    s = 15
    back = x - facing * (s - 2)
    return [*[B((x + dx - 1.5, y + dy - 1.5, 0), (x + dx + 1.5, y + dy + 1.5, seat - 2), color, "καρεκλάκια")
              for dx in (-s + 2, s - 2) for dy in (-s + 2, s - 2)],
            R((x - s, y - s, seat - 2), (x + s, y + s, seat), 2, color, "καρεκλάκια"),
            B((back - 1.5, y - s, seat), (back + 1.5, y + s, seat + 25), color, "καρεκλάκια")]


def kids_table_set():
    # PINTOY®, CC BY-SA 2.0 (wooden table with two little chairs). Anchor: child table 50, seat 30.
    top, chair = "#f4efe6", "#e9b7c4"
    parts = [*legs(35, 0, 95, 60, 47, 4, "#c9dce8"), B((35, 0, 47), (95, 60, 50), top, "τραπέζι"),
             *kids_chair(15, 30, 1, chair), *kids_chair(115, 30, -1, "#b9d7a8")]
    return item("Παιδικό τραπεζάκι με 2 καρεκλάκια", ("Παιδικό",), (130, 60, 55),
                "https://www.flickr.com/photos/67321821@N06/6155651060", parts)


def book_display():
    # BarelyFitz, CC BY 2.0 (front-facing children's book shelf). Anchor: 100 high, picture books 30 cm.
    w, d, wood = 90, 30, "#d8b58a"
    parts = [B((0, 0, 0), (2, d, 100), wood, "ξύλο"), B((w - 2, 0, 0), (w, d, 100), wood, "ξύλο"),
             BM((w / 2, d - 6, 6), (w / 2, d - 1, 98), w - 4, 1.8, wood, "ξύλο")]
    colors = ("#c0392b", "#2e86c1", "#f1c40f", "#27ae60", "#8e44ad", "#e67e22")
    for k, z in enumerate((4, 28, 52, 76)):
        y0 = 2 + (3 - k) * 1.5
        parts += [B((2, y0, z), (w - 2, y0 + 10, z + 2), wood, "ξύλο"), B((2, y0, z + 2), (w - 2, y0 + 1.5, z + 7), wood, "ξύλο")]
        for j in range(3):
            parts.append(BM((15 + j * 30, y0 + 4, z + 2), (15 + j * 30, y0 + 9, z + 22), 22, 1.2, colors[(k + j) % 6], "βιβλία"))
    return item("Βιβλιοθήκη παιδική με μετωπικά ράφια", ("Παιδικό",), (w, d, 100),
                "https://www.flickr.com/photos/43935390809@N01/3265559726", parts)


def play_tower():
    # BarelyFitz, CC BY 2.0 (wooden play tower with slide). Anchor: deck 150 (EN 1176 free height of fall).
    wood, roof, slide = "#a9895f", "#3e7c4a", "#2c8f8f"
    parts = [*[B((x, y, 0), (x + 9, y + 9, 250), wood, "ξύλο") for x in (0, 111) for y in (0, 111)],
             B((0, 0, 145), (120, 120, 150), wood, "ξύλο"),
             BM((60, -2, 247), (60, 60, 280), 128, 3, roof, "στέγη"), BM((60, 122, 247), (60, 60, 280), 128, 3, roof, "στέγη"),
             BM((120, 60, 150), (300, 60, 8), 50, 4, slide, "τσουλήθρα"),
             B((-35, 30, 0), (-31, 34, 150), wood, "ξύλο"), B((-35, 86, 0), (-31, 90, 150), wood, "ξύλο")]
    for z in range(20, 150, 25):
        parts.append(C((-33, 34, z), 1.5, 52, wood, "ξύλο", "y", 10))
    for y in (0, 111):
        parts.append(B((9, y, 175), (111, y + 9, 180), wood, "ξύλο"))
    return item("Παιδικός πύργος παιχνιδιού με τσουλήθρα", ("Παιδικό", "Εξωτερικοί χώροι"), (336.2, 125.4, 281.3),
                "https://www.flickr.com/photos/43935390809@N01/2429089345", parts)


# ------------------------------------------------------------------ bathroom
def basin(cx, cy, z, r, h, color, part):
    """Vessel basin: hollow turned bowl standing on a counter at height z."""
    return L((cx, cy, z), ((r * 0.55, 0), (r * 0.9, h * 0.35), (r, h), (r - 1, h), (r * 0.8, h * 0.45), (r * 0.45, 1.5)),
             color, part, 28)


def tap(x, y, z, reach=14, height=22):
    return [C((x, y, z), 1.6, height, CHROME, "μπαταρία", segments=12),
            BM((x, y, z + height), (x, y - reach, z + height - 3), 2.6, 2.6, CHROME, "μπαταρία")]


def floating_vanity_bowl():
    # PickComfort, CC BY 2.0 (wall-hung vanity with a vessel basin). Anchor: worktop 85 (z given on placing:
    # the unit hangs, so the height is stated without the gap, as for the other hung units).
    w, d = 80, 46
    parts = [B((0, 0, 0), (w, d, 30), WHITE, "σώμα"), B((1, -0.5, 1), (w - 1, 0, 29), "#ece9e2", "συρτάρι"),
             B((w / 2 - 12, -1.5, 22), (w / 2 + 12, -0.5, 23.5), CHROME, "χερούλι"),
             basin(w / 2 - 4, 22, 30, 21, 14, CERAMIC, "νιπτήρας"), *tap(w / 2 + 24, d - 8, 30)]
    return item("Έπιπλο μπάνιου κρεμαστό με επικαθήμενο", ("Μπάνιο",), (w, d + 1.5, 53.3),
                "https://www.flickr.com/photos/161816492@N07/40408017723", parts)


def stone_basin():
    # IndoGemstone, CC BY 2.0 (free-standing stone/petrified-wood basin). Anchor: rim 85.
    return item("Νιπτήρας μονόπετρος δαπέδου", ("Μπάνιο",), (48, 48, 85),
                "https://www.flickr.com/photos/47544036@N03/38922081724", [
                    L((24, 24, 0), ((22, 0), (23.5, 20), (22, 55), (24, 85), (19, 85), (14, 78), (6, 74)), "#8a7a62", "πέτρα", 20)])


def clawfoot_tub():
    # garann, CC BY-SA 2.0 (cast-iron roll-top tub on feet). Anchor: 170x78, rim 64.
    w, d = 170, 78
    parts = [*[E((x, y, 5), (5, 5, 6), CHROME, "πόδια") for x in (22, w - 22) for y in (14, d - 14)],
             R((0, 0, 10), (w, d, 62), 36, WHITE, "σώμα"), R((3, 3, 62), (w - 3, d - 3, 64), 34, "#f6f6f2", "χείλος"),
             R((10, 10, 63), (w - 10, d - 10, 64.2), 28, "#dfe7ea", "εσωτερικό")]
    return item("Μπανιέρα με πόδια κλασική", ("Μπάνιο",), (w, d, 64.2),
                "https://www.flickr.com/photos/60216816@N00/5165719832", parts)


def copper_tub():
    # Ta7za, CC BY 2.0 (hammered copper bath). Anchor: 170x80, raised ends 75.
    w, d, copper = 170, 80, "#b87333"
    parts = [R((10, 6, 0), (w - 10, d - 6, 8), 30, "#8a5426", "βάση"),
             R((0, 0, 8), (w, d, 58), 38, copper, "χαλκός"),
             BM((14, d / 2, 50), (4, d / 2, 72), d - 8, 6, copper, "χαλκός"), BM((w - 14, d / 2, 50), (w - 4, d / 2, 72), d - 8, 6, copper, "χαλκός"),
             R((14, 10, 58), (w - 14, d - 10, 60), 28, "#d9a273", "εσωτερικό")]
    return item("Μπανιέρα χάλκινη σκαφοειδής", ("Μπάνιο",), (170, 80, 73.2),
                "https://www.flickr.com/photos/87031353@N00/3342741102", parts)


def wood_vanity_glass_bowl():
    # shannondemma, CC BY 2.0 (dark wood vanity, stone top, glass vessel). Anchor: worktop 83.
    w, d, wood = 76, 52, "#5a2e1c"
    parts = [B((2, 2, 0), (w - 2, d, 8), "#3e1f13", "βάση"), B((0, 2, 8), (w, d, 80), wood, "ξύλο"),
             B((2, 1.5, 58), (w - 2, 2, 77), "#6a3a24", "συρτάρι"),
             B((2, 1.5, 10), (w / 2 - 1, 2, 56), "#6a3a24", "πόρτες"), B((w / 2 + 1, 1.5, 10), (w - 2, 2, 56), "#6a3a24", "πόρτες"),
             B((-1, 0, 80), (w + 1, d + 1, 83), "#cfc6b2", "πάγκος"),
             basin(w / 2, 24, 83, 20, 15, "#a9c8b8", "γυαλί"), *tap(w / 2, d - 6, 83, 12, 26)]
    return item("Έπιπλο μπάνιου ξύλινο με γυάλινο μπολ", ("Μπάνιο",), (w + 2, d + 1, 109.3),
                "https://www.flickr.com/photos/66915057@N08/6487511315", parts)


def towel_ladder():
    # Vegan Feast Catering, CC BY 2.0 (wooden towel ladder leaning on the wall). Anchor: 170 high.
    wood = "#c9b48e"
    parts = [BM((3, 2, 0), (3, 29, 170), 5, 3, wood, "ξύλο"), BM((47, 2, 0), (47, 29, 170), 5, 3, wood, "ξύλο")]
    for k in range(5):
        z = 30 + k * 32
        parts.append(C((3, 2 + 27 * z / 170, z), 1.6, 44, wood, "ξύλο", "x", 12))
    return item("Σκάλα-πετσετοκρεμάστρα ξύλινη", ("Μπάνιο", "Διακόσμηση"), (50, 30.4, 170.6),
                "https://www.flickr.com/photos/25128194@N02/4656786552", parts)


def shower_column():
    # CarlosPacheco, CC BY 2.0 (exposed shower column with rain head). Anchor: mixer at 95-100, head ~215
    # above the tray; the column is wall-mounted, so the size starts at the mixer and z is given on placing.
    return item("Στήλη ντους με κεφαλή βροχής", ("Μπάνιο",), (30, 45, 125.4), "https://www.flickr.com/photos/48678427@N06/8313110214", [
        B((10, 38, 95), (22, 42, 103), CHROME, "μπαταρία"), C((16, 34, 99), 2.5, 4, CHROME, "μπαταρία", "y"),
        C((16, 36, 99), 1.4, 110, CHROME, "στήλη", segments=12),
        TO((16, 26, 209), 10, 1.4, CHROME, "στήλη", axis="x", arc=90, start=0, segments=8),
        BM((16, 26, 219), (16, 12, 219), 2.8, 2.8, CHROME, "στήλη"), BM((16, 12, 219), (16, 12, 213), 2.8, 2.8, CHROME, "στήλη"),
        C((16, 12, 211.5), 15, 1.5, CHROME, "κεφαλή", segments=32),
        C((23, 37, 120), 1.6, 22, CHROME, "τηλέφωνο", segments=12)])


def frameless_shower():
    # Stradablog, CC BY 2.0 (frameless glass corner shower). Anchor: 90x90 tray, glass 200.
    s = 90
    return item("Ντουζιέρα γωνιακή χωρίς προφίλ 90×90", ("Μπάνιο",), (90.4, 91.5, 205), "https://www.flickr.com/photos/39075787@N02/14393578642", [
        R((0, 0, 0), (s, s, 4), 2, WHITE, "ντουζιέρα"),
        B((0, 0, 4), (s, 1, 204), GLASS, "γυαλί"), B((0, 1, 4), (1, s, 204), GLASS, "γυαλί"),
        B((s / 2 + 15, -1.5, 100), (s / 2 + 17, 0, 130), CHROME, "χερούλι"),
        *[B((-0.4, s - 12, z), (1.4, s - 6, z + 6), CHROME, "μεντεσέδες") for z in (30, 170)],
        C((s - 25, s - 25, 200), 12, 1.5, CHROME, "κεφαλή", segments=24), C((s - 25, s - 25, 201.5), 1.2, 3.5, CHROME, "κεφαλή", segments=8)])


def plank_washstand():
    # this_could_be_my_house, CC BY 2.0 (timber counter on steel pipes, two basins). Anchor: counter 85.
    w, d, wood = 140, 50, "#9c6a3e"
    parts = [*[C((x, y, 0), 2, 79, IRON, "μέταλλο", segments=12) for x in (6, w - 6) for y in (6, d - 6)],
             C((6, 6, 20), 1.5, d - 12, IRON, "μέταλλο", "y", 10), C((w - 6, 6, 20), 1.5, d - 12, IRON, "μέταλλο", "y", 10),
             B((0, 0, 79), (w, d, 85), wood, "ξύλο")]
    for cx in (w / 4, 3 * w / 4):
        parts += [basin(cx, 22, 85, 18, 13, CERAMIC, "νιπτήρες"), *tap(cx, d - 5, 85, 12, 20)]
    return item("Πάγκος νιπτήρων μασίφ σε μεταλλικό σκελετό", ("Μπάνιο",), (140, 50, 106.3),
                "https://www.flickr.com/photos/23932622@N08/2382181927", parts)


# ------------------------------------------------------------------ appliances
def retro_fridge():
    # JD Hancock, CC BY 2.0 (rounded retro refrigerator). Anchor: 150 high.
    w, d, h, cream = 66, 68, 150, "#efd9b0"
    return item("Ψυγείο ρετρό", ("Συσκευές",), (w, d + 3, h), "https://www.flickr.com/photos/83346641@N00/16937546469", [
        R((0, 3, 0), (w, d + 3, h - 8), 10, cream, "σώμα"), C((0, 13, h - 10), 8, w, cream, "σώμα", "x"),
        B((0, 13, h - 18), (w, d + 3, h), cream, "σώμα"),
        B((2, 2.5, 110), (w - 2, 3, h - 6), "#f3e3c2", "πόρτες"), B((2, 2.5, 8), (w - 2, 3, 108), "#f3e3c2", "πόρτες"),
        BM((w - 8, 1, 115), (w - 8, 1, 135), 2.5, 2, CHROME, "χερούλια"), BM((w - 8, 1, 80), (w - 8, 1, 102), 2.5, 2, CHROME, "χερούλια"),
        B((w - 9, 0, 125), (w - 7, 3, 127), CHROME, "χερούλια"), B((w - 9, 0, 90), (w - 7, 3, 92), CHROME, "χερούλια")])


def range_cooker():
    # anamoly23, CC BY 2.0 (100 cm dual-cavity range cooker). Anchor: hob 90 (worktop).
    w, d, body = 100, 60, "#2b2d30"
    parts = [B((0, 0, 0), (w, d, 90), body, "σώμα"), B((0, d - 4, 90), (w, d, 110), STEEL, "πλάτη"),
             B((2, 2, 90), (w - 2, d - 6, 91), "#1d1e20", "εστίες"),
             B((3, -0.5, 10), (59, 0, 62), "#3a3d41", "φούρνοι"), B((62, -0.5, 10), (w - 3, 0, 62), "#3a3d41", "φούρνοι"),
             B((10, -0.6, 25), (52, -0.4, 52), GLASS_DARK, "τζάμι"), B((68, -0.6, 25), (w - 9, -0.4, 52), GLASS_DARK, "τζάμι"),
             C((5, -4, 66), 1.2, 52, CHROME, "χερούλια", "x"), C((64, -4, 66), 1.2, 33, CHROME, "χερούλια", "x"),
             B((3, -0.5, 72), (w - 3, 0, 86), "#3a3d41", "πρόσοψη")]
    for k in range(7):
        parts.append(C((10 + k * 13.3, -2.5, 79), 2, 2.5, CHROME, "διακόπτες", "y", 12))
    for x, y in ((20, 15), (50, 15), (80, 15), (20, 40), (50, 40), (80, 40)):
        parts.append(C((x, y, 91), 5, 2, BLACK, "εστίες", segments=16))
    return item("Κουζίνα range 100 με δύο φούρνους", ("Συσκευές",), (100, 65.2, 110),
                "https://www.flickr.com/photos/13985356@N05/1808987915", parts)


def chest_freezer():
    # David Jackmanson, CC BY 2.0 (white chest freezer). Anchor: 85 high (counter-height chest).
    w, d = 95, 62
    return item("Καταψύκτης μπαούλο 200 l", ("Συσκευές",), (w, d + 2, 85), "https://www.flickr.com/photos/58301516@N00/16501162460", [
        R((0, 2, 2), (w, d + 2, 78), 3, APPLIANCE_WHITE, "σώμα"), R((0, 1, 78), (w, d + 2, 85), 3, APPLIANCE_WHITE, "καπάκι"),
        B((w / 2 - 12, 0, 74), (w / 2 + 12, 1, 80), "#cfd2d4", "χερούλι"),
        *[B((x, y, 0), (x + 5, y + 5, 2), "#888888", "πόδια") for x in (3, w - 8) for y in (5, d - 4)]])


def wood_stove():
    # Wonderlane, CC BY 2.0 (cast-iron wood stove on legs). Anchor: firebox door 45 above floor, flue to 120.
    w, d, iron = 55, 48, "#232323"
    return item("Ξυλόσομπα μαντεμένια με πόδια", ("Συσκευές", "Σαλόνι"), (w + 4, d + 2, 120),
                "https://www.flickr.com/photos/71401718@N00/5423958257", [
        *[BM((x, y, 0), (x + (3 if x < w / 2 else -3), y + (3 if y < d / 2 else -3), 22), 4, 4, iron, "μαντέμι")
          for x in (4, w - 4) for y in (4, d - 4)],
        B((0, 1, 22), (w, d + 1, 70), iron, "μαντέμι"), B((-2, 0, 70), (w + 2, d + 2, 74), iron, "μαντέμι"),
        B((8, 0.4, 30), (w - 8, 1, 62), "#2f2f2f", "πόρτα"), B((13, 0, 35), (w - 13, 0.4, 57), "#e07a2a", "τζάμι"),
        C((w / 2, d - 14, 74), 7.5, 46, iron, "καπνοδόχος", segments=20)])


def ceiling_fan():
    # .Larry Page, CC BY 2.0 (five-blade fan with light kit). Anchor: Ø120 blades, 45 drop (2.7 m ceiling).
    bronze, blade = "#4a3a2c", "#8a5a34"
    parts = [C((60, 60, 42), 7, 3, bronze, "μοτέρ", segments=20), C((60, 60, 28), 1.2, 14, bronze, "μοτέρ", segments=10),
             L((60, 60, 14), ((11, 0), (12, 8), (11, 14), (9, 14)), bronze, "μοτέρ", 24),
             C((60, 60, 6), 7, 8, bronze, "φωτιστικό", segments=16), E((60, 60, 4), (6, 6, 4), LAMP, "φωτιστικό")]
    for k in range(5):
        a = math.radians(72 * k + 18)
        parts.append(BM((60 + 13 * math.cos(a), 60 + 13 * math.sin(a), 18), (60 + 60 * math.cos(a), 60 + 60 * math.sin(a), 18),
                        13, 1.2, blade, "πτερύγια"))
    return item("Ανεμιστήρας οροφής με φωτιστικό", ("Συσκευές", "Φωτισμός"), (118.1, 112.4, 45),
                "https://www.flickr.com/photos/96029422@N00/3752656179", parts)


# ------------------------------------------------------------------ office
def rolltop_desk():
    # orionpozo, CC BY 2.0 (oak roll-top desk on two pedestals). Anchor: writing surface 76.
    w, d, oak = 140, 75, "#7a5232"
    parts = [B((0, 0, 0), (42, d, 74), oak, "ξύλο"), B((w - 42, 0, 0), (w, d, 74), oak, "ξύλο"),
             B((42, d - 3, 30), (w - 42, d, 74), oak, "ξύλο"), B((-1, -1, 74), (w + 1, d, 77), oak, "ξύλο"),
             B((0, d - 20, 77), (w, d, 120), oak, "ξύλο")]
    for x0 in (2, w - 40):
        for k in range(4):
            parts.append(B((x0, -0.5, 4 + k * 17.5), (x0 + 38, 0, 20 + k * 17.5), "#8a6240", "συρτάρια"))
    prev = None
    for k in range(7):                                   # tambour as six slats along a quarter circle
        a = math.radians(90 * k / 6)
        p = (w / 2, d - 20 - 40 * math.cos(a), 77 + 43 * math.sin(a))
        if prev:
            parts.append(BM(prev, p, w, 2, "#6a4428", "ρολό"))
        prev = p
    for x0 in (0, w - 2):
        for k in range(6):
            a = math.radians(90 * (k + 0.5) / 6)
            y0 = d - 20 - 40 * math.cos(a)
            parts.append(B((x0, y0, 77), (x0 + 2, d - 20, 77 + 43 * math.sin(a)), oak, "ξύλο"))
    return item("Γραφείο με ρολό κλασικό", ("Γραφείο",), (w + 2, d + 1, 120.6),
                "https://www.flickr.com/photos/65168863@N00/10099385244", parts)


def drafting_table():
    # TheLivingRoominKenmore, CC BY 2.0 (wooden drawing table, tilted top). Anchor: front edge 76, top tilted ~18°.
    w, d, wood = 120, 80, "#c58a45"
    parts = [*legs(2, 4, w - 2, d - 2, 74, 5, wood),
             B((7, 6, 64), (w - 7, 9, 72), wood, "ξύλο"), B((7, d - 7, 64), (w - 7, d - 4, 72), wood, "ξύλο"),
             B((7, 9, 10), (w - 7, 12, 14), wood, "ξύλο"),
             BM((w / 2, 2, 76), (w / 2, d - 2, 100), w, 2.5, wood, "επιφάνεια"),
             B((0, 0, 74), (w, 4, 79), wood, "επιφάνεια"),
             B((4, d - 10, 74), (8, d - 6, 99), wood, "ξύλο"), B((w - 8, d - 10, 74), (w - 4, d - 6, 99), wood, "ξύλο")]
    return item("Σχεδιαστήριο ξύλινο με κεκλιμένη επιφάνεια", ("Γραφείο",), (120, 78.4, 101.2),
                "https://www.flickr.com/photos/36910487@N07/5106142928", parts)


def filing_cabinet():
    # 401(K) 2013, CC BY-SA 2.0 (four-drawer steel file). Anchor: 132 high, A4/letter drawers 62 deep.
    w, d, grey = 46, 62, "#7e8389"
    parts = [B((0, 1.5, 0), (w, d, 132), grey, "μέταλλο")]
    for k in range(4):
        z = 3 + k * 32
        parts += [B((1.5, 1, z), (w - 1.5, 1.5, z + 30), "#8c9197", "συρτάρια"),
                  B((w / 2 - 7, 0, z + 17), (w / 2 + 7, 1, z + 20), CHROME, "χερούλια"),
                  B((w / 2 - 5, 0.5, z + 23), (w / 2 + 5, 1, z + 27), WHITE, "ετικέτες")]
    return item("Αρχειοθήκη μεταλλική 4 συρταριών", ("Γραφείο",), (w, d, 132),
                "https://www.flickr.com/photos/68751915@N05/7249752654", parts)


def cube_bookcase():
    # LaMenta3, CC BY-SA 2.0 (white 4x5 cube shelving). Anchor: 33 cm cubes, 182 high.
    cols, rows, t, c, d = 4, 5, 2.5, 33.6, 39
    w, h = cols * c + (cols + 1) * t, rows * c + (rows + 1) * t
    parts = [*[B((k * (c + t), 0, 0), (k * (c + t) + t, d, h), WHITE, "ράφια") for k in range(cols + 1)],
             *[B((t, 0, k * (c + t)), (w - t, d, k * (c + t) + t), WHITE, "ράφια") for k in range(rows + 1)],
             B((t, d - 1, t), (w - t, d, h - t), "#ece9e2", "πλάτη")]
    colors = ("#c0392b", "#2e86c1", "#d4ac0d", "#27ae60", "#7d3c98", "#d35400")
    for n, (i, j) in enumerate(((0, 1), (1, 3), (2, 0), (3, 2), (1, 4), (2, 2), (0, 3), (3, 4))):
        x0, z0 = t + i * (c + t), t + j * (c + t)
        parts.append(B((x0 + 3, 6, z0), (x0 + 3 + 12 + 3 * (n % 3), d - 4, z0 + 24), colors[n % 6], "βιβλία"))
    return item("Βιβλιοθήκη με κύβους 4×5", ("Γραφείο", "Σαλόνι"), (w, d, h),
                "https://www.flickr.com/photos/15304975@N03/4505616367", parts)


def bureau():
    # elsacapuntas, CC BY-SA 2.0 (slant-front writing bureau). Anchor: writing flap opens at 78.
    w, d, wood = 90, 48, "#6a2e1a"
    parts = [*[B((x, y, 0), (x + 8, y + 8, 8), wood, "πόδια") for x in (0, w - 8) for y in (0, d - 8)],
             B((0, 0, 8), (w, d, 78), wood, "ξύλο"), B((0, 26, 78), (w, d, 104), wood, "ξύλο"),
             BM((w / 2, 1, 78), (w / 2, 27, 103), w - 4, 2, "#7a3a22", "καπάκι")]
    for k, (z0, z1) in enumerate(((10, 26), (28, 44), (46, 60), (62, 76))):
        parts += [B((3, -0.5, z0), (w - 3, 0, z1), "#7a3a22", "συρτάρια"),
                  *[B((x - 4, -1.5, (z0 + z1) / 2 - 1), (x + 4, -0.5, (z0 + z1) / 2 + 1), BRASS, "χερούλια") for x in (w / 4, 3 * w / 4)]]
    for k in range(10):                                  # side cheeks under the slope
        y0 = 1 + 26 * k / 10
        parts += [B((0, y0, 78), (2, 27, 78 + 25 * (k + 0.5) / 10), wood, "ξύλο"),
                  B((w - 2, y0, 78), (w, 27, 78 + 25 * (k + 0.5) / 10), wood, "ξύλο")]
    return item("Γραμματέας με πτυσσόμενο καπάκι", ("Γραφείο", "Υπνοδωμάτιο"), (w, d + 1.5, 104),
                "https://www.flickr.com/photos/90746579@N00/12750736694", parts)


def scandi_desk():
    # pierrevedel.com, CC BY-SA 2.0 (pine top on red steel legs). Anchor: desk 75.
    w, d, red, pine = 140, 70, "#b22a2a", "#d9b98a"
    parts = [B((0, 0, 71), (w, d, 75), pine, "ξύλο"), B((4, 4, 61), (w - 4, d - 4, 71), pine, "ξύλο"),
             B((8, 8, 62), (w - 8, d - 8, 63), "#c9a879", "ξύλο")]
    for x0, x1 in ((6, 9), (w - 6, w - 9)):
        for y0, y1 in ((6, 9), (d - 6, d - 9)):
            parts.append(BM((x0 + (x0 - x1) * 0.6, y0 + (y0 - y1) * 0.6, 0), (x1, y1, 61), 4, 4, red, "πόδια"))
    return item("Γραφείο σκανδιναβικό με μεταλλικά πόδια", ("Γραφείο",), (w, d, 75),
                "https://www.flickr.com/photos/59716912@N05/5931284162", parts)


# ------------------------------------------------------------------ lighting
def shade(cx, cy, z, r0, r1, h, color, part):
    """Open lamp shade (thin turned wall): wide end r0 at z, r1 at z + h."""
    return L((cx, cy, z), ((r0, 0), (r1, h), (r1 - 0.6, h), (r0 - 0.6, 0.6)), color, part, 28)


def arc_lamp():
    # HALDANE MARTIN, CC BY 2.0 (arched floor lamp over a sofa). Anchor: shade 150 above the floor, reach 170.
    marble, steel = "#ecebe7", CHROME
    end = math.radians(60)
    tip = (100 + 90 * math.sin(end), 20, 120 + 90 * math.cos(end))
    return item("Φωτιστικό δαπέδου τόξο", ("Φωτισμός", "Σαλόνι"), (205.9, 40, 211.5), "https://www.flickr.com/photos/52634191@N08/4846890451", [
        C((10, 20, 0), 18, 6, marble, "βάση", segments=28),
        C((10, 20, 6), 1.6, 114, steel, "τόξο", segments=12),
        TO((100, 20, 120), 90, 1.6, steel, "τόξο", axis="y", arc=150, start=-90, segments=30),
        C((tip[0], 20, tip[2] - 8), 1.6, 8, steel, "τόξο", segments=12),
        L((tip[0], 20, tip[2] - 28), ((20, 0), (17, 10), (8, 19), (2, 20), (2, 19), (7.4, 18), (16.4, 9.6), (19.4, 0.6)),
          steel, "καπέλο", 28)])


def bulb_pendant():
    # JudyLighting.com, CC BY-SA 2.0 (bare bulb on a fabric cord). Anchor: 100 drop from the ceiling.
    return item("Κρεμαστό με γυμνή λάμπα", ("Φωτισμός",), (12, 12, 100), "https://www.flickr.com/photos/151453724@N07/34388246863", [
        C((6, 6, 96), 6, 4, BLACK, "βάση", segments=20), C((6, 6, 18), 0.4, 78, BLACK, "καλώδιο", segments=8),
        C((6, 6, 12), 1.8, 7, BRASS, "ντουί", segments=12), E((6, 6, 6), (4, 4, 6.5), "#f6d68a", "λάμπα")])


def crystal_chandelier():
    # Jenn Durfey, CC BY 2.0 (empire crystal chandelier). Anchor: Ø70, 100 drop.
    crystal, gold = "#e6ecf0", "#c9a94f"
    parts = [C((35, 35, 96), 8, 4, gold, "μέταλλο", segments=20), C((35, 35, 78), 0.8, 18, gold, "μέταλλο", segments=8),
             L((35, 35, 32), ((31, 0), (24, 18), (12, 38), (4, 46)), crystal, "κρύσταλλα", 24),
             TO((35, 35, 50), 24, 1.2, gold, "μέταλλο", segments=32), TO((35, 35, 30), 34, 1, gold, "μέταλλο", segments=32),
             L((35, 35, 0), ((2, 0), (30, 28), (33, 32), (31, 32), (4, 6)), crystal, "κρύσταλλα", 24)]
    for k in range(8):
        a = math.radians(45 * k)
        x, y = 35 + 30 * math.cos(a), 35 + 30 * math.sin(a)
        parts += [C((x, y, 32), 1.2, 7, WHITE, "κεριά", segments=8), E((x, y, 41), (0.8, 0.8, 1.6), "#f6d68a", "κεριά")]
    return item("Πολυέλαιος κρυστάλλινος", ("Φωτισμός",), (70, 70, 100), "https://www.flickr.com/photos/52498245@N03/7827548362", parts)


def globe_pendant():
    # Artdecodude, CC BY 2.0 (opal globe with a ring on a rod). Anchor: Ø30 globe, 80 drop.
    return item("Κρεμαστό γλόμπος με δακτύλιο", ("Φωτισμός",), (46, 46, 80), "https://www.flickr.com/photos/62920259@N03/5826672808", [
        C((23, 23, 76), 7, 4, "#9a8f7a", "μέταλλο", segments=20), C((23, 23, 30), 0.9, 46, "#9a8f7a", "μέταλλο", segments=8),
        C((23, 23, 27), 4, 4, "#9a8f7a", "μέταλλο", segments=16),
        E((23, 23, 15), (15, 15, 15), "#f3f1ea", "γυαλί"), TO((23, 23, 15), 20, 3, "#d9d5c8", "δακτύλιος", segments=32, sides=6)])


def paper_lantern():
    # sylvar, CC BY 2.0 (round paper lantern). Anchor: Ø45, 80 drop.
    orange = "#d9763a"
    parts = [C((22.5, 22.5, 76), 5, 4, WHITE, "βάση", segments=16), C((22.5, 22.5, 40), 0.4, 36, WHITE, "καλώδιο", segments=6),
             E((22.5, 22.5, 20), (22.5, 22.5, 20), orange, "χαρτί")]
    for z, r in ((10, 19.5), (20, 22.5), (30, 19.5)):
        parts.append(TO((22.5, 22.5, z), r, 0.4, "#b85f2c", "σκελετός", segments=28, sides=4))
    return item("Κρεμαστό χάρτινο φανάρι", ("Φωτισμός", "Παιδικό"), (45.4, 45.4, 80), "https://www.flickr.com/photos/44124401501@N01/2966974779", parts)


def woven_pendant():
    # Tilak Bahadur Karki, CC0 (woven rattan pendant). Anchor: Ø40, 90 drop.
    return item("Κρεμαστό ψάθινο", ("Φωτισμός",), (40, 40, 90), "https://wordpress.org/photos/photo/6216a17250/", [
        C((20, 20, 86), 5, 4, RATTAN, "βάση", segments=16), C((20, 20, 33), 0.4, 53, BLACK, "καλώδιο", segments=6),
        L((20, 20, 0), ((12, 0), (19, 8), (20, 18), (14, 30), (5, 34), (4, 33), (13.4, 29), (19.4, 18), (18.4, 8.4), (11.4, 0.6)),
          RATTAN, "ψάθα", 24)])


def mushroom_lamp():
    # clevelandart, CC0 (small table lamp with a dome shade on a slim stem). Anchor: 45 high.
    return item("Επιτραπέζιο φωτιστικό «μανιτάρι»", ("Φωτισμός",), (26, 26, 45), "https://www.rawpixel.com/image/9624051/mushroom-night-lamp-tiffany-glass-and-decorating-company-and-tiffany-studios", [
        L((13, 13, 0), ((11, 0), (11, 1.5), (7, 3), (3, 4.5)), BRASS, "βάση", 24),
        C((13, 13, 4.5), 1.8, 26, "#7e9a6e", "στέλεχος", segments=12),
        L((13, 13, 28), ((13, 0), (12, 7), (9, 13), (4, 16.5), (0.5, 17)), "#e2b44a", "καπέλο", 28)])


def stained_glass_lamp():
    # museado, CC0 (leaded glass cone shade on a bronze base). Anchor: Ø50 shade, 60 high.
    return item("Επιτραπέζιο φωτιστικό με βιτρό καπέλο", ("Φωτισμός", "Σαλόνι"), (50, 50, 60), "https://www.flickr.com/photos/200781279@N05/53862485444", [
        L((25, 25, 0), ((11, 0), (11, 2), (6, 4), (2.2, 8), (1.8, 40)), "#5a4a2c", "βάση", 24),
        shade(25, 25, 32, 25, 4, 26, "#a8a24a", "βιτρό"), C((25, 25, 58), 2, 2, "#5a4a2c", "βάση", segments=12)])


def bedside_lamp():
    # TheLivingRoominKenmore, CC BY 2.0 (classic brass lamp with a drum shade). Anchor: 75 high.
    return item("Πορτατίφ κλασικό με αμπαζούρ", ("Φωτισμός", "Υπνοδωμάτιο"), (40, 40, 75), "https://www.flickr.com/photos/36910487@N07/4643597111", [
        L((20, 20, 0), ((8, 0), (8, 3), (4, 5), (3, 10), (7, 18), (5, 26), (2.5, 30), (1.2, 46)), BRASS, "βάση", 24),
        E((20, 20, 21), (7.5, 7.5, 7), "#e8dfcf", "βάση"),
        shade(20, 20, 45, 20, 17, 30, "#f2ece0", "αμπαζούρ")])


def torchiere():
    # TheLivingRoominKenmore, CC BY 2.0 (uplighter with a bowl). Anchor: 180 high.
    return item("Φωτιστικό δαπέδου uplight", ("Φωτισμός",), (40, 40, 180), "https://www.flickr.com/photos/36910487@N07/4517123728", [
        L((20, 20, 0), ((15, 0), (15, 2), (8, 4), (2, 6)), BRASS, "βάση", 24),
        C((20, 20, 6), 1.2, 160, BRASS, "στέλεχος", segments=12),
        L((20, 20, 166), ((3, 0), (20, 12), (20, 14), (19.4, 14), (2.4, 1.4)), "#f1e6cc", "καπέλο", 28)])


def dome_desk_lamp():
    # FHKE, CC BY-SA 2.0 (dome desk lamp on a bent arm). Anchor: 45 high.
    steel = "#c2c6ca"
    return item("Φωτιστικό γραφείου με καμπάνα", ("Φωτισμός", "Γραφείο"), (18, 36, 40.8), "https://www.flickr.com/photos/16226024@N00/220593718", [
        C((9, 27, 0), 9, 2.5, steel, "βάση", segments=24),
        BM((9, 30, 2.5), (9, 26, 40), 1.6, 1.6, steel, "βραχίονας"), BM((9, 26, 40), (9, 12, 36), 1.6, 1.6, steel, "βραχίονας"),
        L((9, 9, 24), ((9, 0), (8, 6), (5, 10), (2, 12), (1.4, 11.4), (4.4, 9.4), (7.4, 5.8), (8.4, 0.6)), steel, "καπέλο", 24)])


def globe_sconce():
    # Cindy Funk, CC BY 2.0 (wall lantern: globe on a cast-iron arm). Anchor: Ø25 globe; fixed at ~200.
    iron = "#2f3a3a"
    return item("Απλίκα με γλόμπο σε μαντεμένιο βραχίονα", ("Φωτισμός", "Εξωτερικοί χώροι"), (25, 40.5, 56),
                "https://www.flickr.com/photos/84858864@N00/2106646274", [
        B((7, 38, 0), (18, 42, 26), iron, "βάση"),
        BM((12.5, 38, 22), (12.5, 16, 26), 2.5, 2.5, iron, "βραχίονας"),
        BM((12.5, 14, 14), (12.5, 14, 28), 3, 3, iron, "βραχίονας"),
        L((12.5, 14, 28), ((3, 0), (6, 4), (5, 6)), iron, "βάση", 16),
        E((12.5, 14, 43.5), (12.5, 12.5, 12.5), "#f4f1e8", "γυαλί")])


# ------------------------------------------------------------------ decoration
def olive_concrete_pot():
    # Amsterdam free photos, CC0 (old olive tree in a round concrete planter). Anchor: Ø60 pot, tree 180.
    trunk, leaf = "#6f6455", "#7d8b5a"
    return item("Ελιά αιωνόβια σε τσιμεντένια γλάστρα", ("Διακόσμηση", "Εξωτερικοί χώροι"), (100, 68, 180),
                "https://www.flickr.com/photos/104736837@N03/49002721558", [
        L((55, 48, 0), ((28, 0), (30, 50), (30, 55), (27, 55), (27, 50)), "#b9b6ae", "γλάστρα", 28),
        BM((55, 48, 45), (48, 44, 90), 12, 10, trunk, "κορμός"), BM((48, 44, 90), (60, 52, 125), 10, 8, trunk, "κορμός"),
        BM((60, 52, 120), (40, 40, 140), 6, 6, trunk, "κορμός"), BM((60, 52, 120), (78, 56, 145), 6, 6, trunk, "κορμός"),
        E((40, 42, 148), (30, 26, 22), leaf, "φύλλωμα"), E((78, 56, 152), (32, 28, 24), leaf, "φύλλωμα"),
        E((60, 46, 160), (28, 26, 20), leaf, "φύλλωμα")])


def monstera():
    # blumenbiene, CC BY 2.0 (monstera in a nursery pot). Anchor: Ø28 pot, 110 high.
    green, pot = "#2f6b2f", "#4a3a30"
    parts = [T((40, 40, 0), 11, 14, 26, pot, "γλάστρα")]
    leaves = ((20, 30, 70, 0), (62, 34, 85, 0), (34, 60, 98, 0), (52, 52, 60, 0), (40, 22, 92, 0))
    for x, y, z, _ in leaves:
        parts += [BM((40, 40, 24), (x, y, z - 2), 1.2, 1.2, "#4f8a3a", "μίσχοι"), E((x, y, z), (16, 13, 2.5), green, "φύλλα")]
    return item("Φυτό μονστέρα σε γλάστρα", ("Διακόσμηση",), (74, 64, 100.5),
                "https://www.flickr.com/photos/47439717@N05/6629764635", parts)


def amphora():
    # mharrsch, CC BY 2.0 (Attic neck amphora). Anchor: 65 high, as large table/floor amphorae.
    body, glaze = "#c47a3a", "#2a2420"
    return item("Αμφορέας κεραμικός", ("Διακόσμηση",), (37, 36.4, 65), "https://www.flickr.com/photos/44124324682@N01/2660508379", [
        L((22, 19, 0), ((8, 0), (8, 2), (5, 4), (8, 10), (16, 25), (18, 34), (15, 44), (8, 50)), glaze, "βερνίκι", 28),
        L((22, 19, 26), ((17, 0), (18.2, 8), (15.2, 18)), body, "πηλός", 28),
        L((22, 19, 50), ((8, 0), (7, 8), (11, 13), (11, 15), (6, 15)), glaze, "βερνίκι", 28),
        *[BM((22 + sx * 17.5, 19, 40), (22 + sx * 16, 19, 60), 2.5, 2, glaze, "βερνίκι") for sx in (-1, 1)],
        *[BM((22 + sx * 16, 19, 59), (22 + sx * 8, 19, 61), 2.5, 2, glaze, "βερνίκι") for sx in (-1, 1)]])


def basket():
    # Ivan Radic, CC BY 2.0 (woven basket with a hoop handle). Anchor: Ø30 basket, 45 to the handle.
    red = "#a8322a"
    return item("Καλάθι ψάθινο με χερούλι", ("Διακόσμηση",), (31, 30, 29.5), "https://www.flickr.com/photos/26344495@N05/49739526326", [
        L((16.5, 15, 0), ((11, 0), (14, 8), (15, 14), (14.2, 14), (13.2, 8.4), (10.4, 1.2)), red, "ψάθα", 24),
        TO((16.5, 15, 14), 14.5, 1, red, "χερούλι", axis="y", arc=180, start=-90, segments=16)])


def floor_vase():
    # quinet, CC BY 2.0 (tall painted porcelain floor vase). Anchor: 90 high.
    white, band = "#f2efe8", "#c4572e"
    return item("Βάζο δαπέδου πορσελάνινο", ("Διακόσμηση",), (36, 36, 90), "https://www.flickr.com/photos/91994044@N00/25496828173", [
        L((18, 18, 0), ((11, 0), (12, 4), (15, 20), (17, 36), (16, 50), (11, 64)), white, "πορσελάνη", 28),
        L((18, 18, 30), ((16.6, 0), (17.2, 6), (16.8, 14)), band, "διάκοσμος", 28),
        L((18, 18, 64), ((11, 0), (8, 12), (12, 22), (18, 26), (17, 26), (7, 16)), white, "πορσελάνη", 28)])


def sunburst_mirror():
    # emily @ go haus go, CC BY 2.0 (gilded sunburst mirror). Anchor: Ø90 overall, mirror Ø30.
    gold = "#c9a447"
    parts = [C((45, 3, 45), 15, 1, GLASS, "καθρέφτης", "y", 32), TO((45, 2, 45), 16, 1.6, gold, "κορνίζα", axis="y", segments=32, sides=6)]
    for k in range(20):
        a = math.radians(18 * k)
        parts.append(BM((45 + 17 * math.cos(a), 2, 45 + 17 * math.sin(a)), (45 + 44 * math.cos(a), 2, 45 + 44 * math.sin(a)),
                        1.2, 1.2, gold, "ακτίνες"))
    return item("Καθρέφτης «ήλιος»", ("Διακόσμηση",), (88, 3.4, 88), "https://www.flickr.com/photos/60849758@N05/8110888265", parts)


def hurricane_vase():
    # Bonsoni.com, CC BY 2.0 (footed glass hurricane). Anchor: 35 high.
    return item("Κηροπήγιο γυάλινο με πόδι", ("Διακόσμηση",), (20, 20, 35), "https://www.flickr.com/photos/56705951@N04/14197396202", [
        L((10, 10, 0), ((7, 0), (7, 1), (2, 3), (1.5, 8), (5, 10), (8, 18), (10, 35), (9.5, 35), (7.5, 18.4), (4.5, 10.6)), GLASS, "γυαλί", 28),
        C((10, 10, 10.6), 3, 10, WHITE, "κερί", segments=16)])


def cactus():
    # John Beans, CC BY 2.0 (cactus in a terracotta pot). Anchor: Ø20 pot, 40 high.
    green = "#4f7a3a"
    return item("Κάκτος σε πήλινο γλαστράκι", ("Διακόσμηση",), (20, 20, 40), "https://www.flickr.com/photos/147592390@N06/46934594804", [
        T((10, 10, 0), 8, 10, 16, TERRACOTTA, "γλάστρα"), C((10, 10, 13), 10, 3, TERRACOTTA, "γλάστρα"),
        L((10, 10, 15), ((5, 0), (6, 5), (6, 18), (4.5, 23), (1.5, 25)), green, "κάκτος", 12)])


def bonsai():
    # paalia, CC BY 2.0 (bonsai in a shallow tray). Anchor: 40 cm tray, 55 high.
    trunk, leaf = "#5a4636", "#3f6a33"
    return item("Μπονσάι σε ρηχή γλάστρα", ("Διακόσμηση",), (45, 28, 55), "https://www.flickr.com/photos/32628328@N00/2616207521", [
        B((5, 1, 0), (45, 29, 8), "#5e4b3c", "γλάστρα"),
        BM((24, 15, 6), (20, 15, 22), 5, 5, trunk, "κορμός"), BM((20, 15, 22), (30, 15, 34), 4, 4, trunk, "κορμός"),
        BM((30, 15, 34), (14, 15, 42), 3, 3, trunk, "κορμός"),
        E((12, 15, 44), (12, 10, 6), leaf, "φύλλωμα"), E((32, 15, 40), (12, 10, 5), leaf, "φύλλωμα"),
        E((25, 15, 50), (11, 9, 5), leaf, "φύλλωμα")])


def garden_urn():
    # Bonsoni.com, CC BY 2.0 (classical stone urn on a square plinth). Anchor: 80 high.
    stone = "#a9a59c"
    return item("Γλάστρα-κύπελλο κλασική", ("Διακόσμηση", "Εξωτερικοί χώροι"), (48, 48, 80), "https://www.flickr.com/photos/56705951@N04/14196624911", [
        B((6, 6, 0), (42, 42, 12), stone, "πέτρα"),
        L((24, 24, 12), ((12, 0), (8, 4), (6, 18), (10, 24), (16, 30), (22, 52), (24, 60), (24, 68), (21, 68), (19, 58)), stone, "πέτρα", 28)])


# ------------------------------------------------------------------ entrance
def shoe_bench():
    # Paintzen, CC BY 2.0 (entry bench with a shoe shelf). Anchor: seat 46.
    w, d, wood = 100, 35, "#b48a5a"
    return item("Παγκάκι εισόδου με ράφι παπουτσιών", ("Είσοδος",), (w, d, 50), "https://www.flickr.com/photos/147489968@N06/29300971813", [
        B((0, 0, 0), (3, d, 46), wood, "ξύλο"), B((w - 3, 0, 0), (w, d, 46), wood, "ξύλο"),
        B((3, 0, 8), (w - 3, d, 10), wood, "ξύλο"), B((3, 0, 26), (w - 3, d, 28), wood, "ξύλο"),
        B((0, 0, 46), (w, d, 48), wood, "ξύλο"), R((2, 2, 48), (w - 2, d - 2, 50), 3, "#c9c1b0", "μαξιλάρι"),
        R((8, 6, 10), (36, 16, 18), 3, "#3a3a3a", "παπούτσια"), R((60, 18, 28), (88, 28, 36), 3, "#7a4a2c", "παπούτσια")])


def hall_stand():
    # TheLivingRoominKenmore, CC BY 2.0 (cast-iron coat and umbrella stand). Anchor: 185 high.
    iron = "#2a2a2a"
    parts = [L((25, 25, 0), ((22, 0), (22, 3), (19, 5), (18, 5), (18, 3)), iron, "βάση", 24),
             C((25, 25, 3), 1.8, 172, iron, "κολόνα", segments=12), TO((25, 25, 62), 18, 1, iron, "δακτύλιος", segments=24),
             *[BM((25, 25, 40), (25 + 17 * math.cos(math.radians(a)), 25 + 17 * math.sin(math.radians(a)), 62), 1, 1, iron, "δακτύλιος")
               for a in (45, 165, 285)],
             E((25, 25, 180), (3, 3, 5), iron, "κολόνα")]
    for k in range(4):
        a = math.radians(90 * k)
        parts.append(BM((25, 25, 168), (25 + 14 * math.cos(a), 25 + 14 * math.sin(a), 176), 1.4, 1.4, iron, "γάντζοι"))
    return item("Καλόγερος-ομπρελοθήκη μαντεμένιος", ("Είσοδος",), (44, 44, 185), "https://www.flickr.com/photos/36910487@N07/4858064613", parts)


def plank_coat_rack():
    # sparr0, CC BY-SA 2.0 (reclaimed plank with hooks). Anchor: plank 100, hung at ~170 (z on placing).
    parts = [B((0, 7, 0), (100, 10, 15), "#8a6a48", "ξύλο")]
    for k in range(5):
        x = 10 + k * 20
        parts += [BM((x, 7, 9), (x, 1, 9), 1.4, 1.4, BRASS, "γάντζοι"), BM((x, 1.7, 8.3), (x, 0.7, 13), 1.4, 1.4, BRASS, "γάντζοι")]
    return item("Κρεμάστρα τοίχου σανίδα με γάντζους", ("Είσοδος",), (100, 10, 15), "https://www.flickr.com/photos/22611472@N02/12686560975", parts)


def shoe_cubby():
    # Mark.Pilgrim, CC BY-SA 2.0 (wooden cubby shoe rack). Anchor: 18 cubbies, 90 high.
    cols, rows, t, c, d, wood = 3, 6, 1.8, 24, 32, "#a0703c"
    w, h = cols * c + (cols + 1) * t, rows * 13 + (rows + 1) * t
    parts = [*[B((k * (c + t), 0, 0), (k * (c + t) + t, d, h), wood, "ξύλο") for k in range(cols + 1)],
             *[B((t, 0, k * (13 + t)), (w - t, d, k * (13 + t) + t), wood, "ξύλο") for k in range(rows + 1)],
             B((t, d - 0.6, t), (w - t, d, h - t), "#8a5e30", "πλάτη")]
    return item("Παπουτσοθήκη με θυρίδες", ("Είσοδος",), (w, d, h), "https://www.flickr.com/photos/41169327@N00/110696323", parts)


def iron_console():
    # TheLivingRoominKenmore, CC BY 2.0 (wrought-iron demilune console with glass top). Anchor: 80 high.
    iron, w, d = "#2b2b2b", 100, 40
    parts = [R((0, 0, 78), (w, d, 80), 18, GLASS, "γυαλί"), R((1, 1, 74), (w - 1, d - 1, 78), 17, iron, "σίδερο"),
             B((20, d - 4, 74), (w - 20, d - 1, 78), iron, "σίδερο")]
    for x0, x1 in ((8, 14), (w - 8, w - 14)):
        parts += [BM((x0, 8, 0), (x1, 12, 74), 2, 2, iron, "σίδερο"), BM((x0, d - 4, 0), (x1, d - 6, 74), 2, 2, iron, "σίδερο"),
                  TO(((x0 + x1) / 2, 10, 60), 6, 0.8, iron, "σίδερο", axis="x", arc=270, segments=12, sides=6)]
    parts.append(B((14, d - 6, 18), (w - 14, d - 4, 20), iron, "σίδερο"))
    return item("Κονσόλα σφυρήλατη με γυάλινο καπάκι", ("Είσοδος", "Σαλόνι"), (w, d, 80), "https://www.flickr.com/photos/36910487@N07/4542594220", parts)


def marble_console():
    # Kevin Payton, CC BY 2.0 (dark wood console with marble top). Anchor: 85 high.
    w, d, wood = 140, 40, "#3e2418"
    return item("Κονσόλα με μαρμάρινη επιφάνεια", ("Είσοδος", "Τραπεζαρία"), (w, d, 85), "https://www.flickr.com/photos/49948761@N08/4580694456", [
        *[L((x, y, 0), ((3.5, 0), (4.5, 4), (2.5, 12), (3.5, 30), (2.5, 50), (3.5, 64), (3, 78)), wood, "ξύλο", 12)
          for x in (5, w - 5) for y in (5, d - 5)],
        B((1, 1, 70), (w - 1, d - 1, 81), wood, "ξύλο"), B((4, 4, 14), (w - 4, d - 4, 17), wood, "ξύλο"),
        B((0, 0, 81), (w, d, 85), "#e8e4dc", "μάρμαρο")])


# ------------------------------------------------------------------ outdoor
def hanging_chair():
    # nan palmero, CC BY 2.0 (wicker hanging egg chair on a C-stand). Anchor: seat 45, stand 195.
    white, steel = "#f0eee8", "#e6e6e3"
    return item("Κρεμαστή πολυθρόνα-φωλιά με βάση", ("Εξωτερικοί χώροι", "Σαλόνι"), (100, 101.7, 190),
                "https://www.flickr.com/photos/97402086@N00/17280689125", [
        C((50, 50, 0), 50, 3, steel, "βάση", segments=40),
        TO((50, 50, 100), 95 / 2 + 2, 2.2, steel, "βάση", axis="x", arc=180, start=270, segments=16),
        C((50, 2.3, 3), 2.2, 97, steel, "βάση", segments=12),
        C((50, 50, 140), 0.8, 50, steel, "αλυσίδα", segments=6),
        L((50, 50, 30), ((10, 0), (30, 14), (34, 34), (31, 34), (27, 18), (9, 6)), white, "ψάθα", 28),
        E((50, 70, 98), (33, 10, 62), white, "ψάθα"), TO((50, 50, 64), 30, 3, white, "ψάθα", arc=180, segments=16, sides=6),
        E((50, 52, 46), (24, 22, 6), "#e8622c", "μαξιλάρι"), E((50, 66, 70), (20, 6, 18), "#e8622c", "μαξιλάρι")])


def hammock():
    # slgckgc, CC BY 2.0 (fabric hammock with spreader bars). Anchor: bed 200x100, hung 70-120; on a steel stand.
    steel, cloth = "#4a4f55", "#3e5f8a"
    return item("Αιώρα με βάση", ("Εξωτερικοί χώροι",), (335.7, 100, 121), "https://www.flickr.com/photos/14771153@N04/7433810112", [
        B((40, 45, 0), (290, 55, 6), steel, "βάση"),
        BM((40, 50, 3), (0, 50, 120), 6, 6, steel, "βάση"), BM((290, 50, 3), (330, 50, 120), 6, 6, steel, "βάση"),
        *[B((x, 0, 0), (x + 6, 100, 4), steel, "βάση") for x in (40, 284)],
        E((165, 50, 66), (100, 48, 6), cloth, "ύφασμα"),
        C((65, 0, 88), 1.5, 100, "#c9a879", "ξύλο", "y", 10), C((265, 0, 88), 1.5, 100, "#c9a879", "ξύλο", "y", 10),
        BM((65, 50, 88), (8, 50, 117), 1, 1, "#d9d2c0", "σχοινιά"), BM((265, 50, 88), (322, 50, 117), 1, 1, "#d9d2c0", "σχοινιά")])


def adirondack():
    # Kathleen Tyler Conklin, CC BY 2.0 (painted Adirondack chairs). Anchor: front seat 38, back 95.
    w, d, white = 74, 90, "#f2f0ea"
    parts = [BM((6, 4, 0), (6, 6, 58), 4, 6, white, "ξύλο"), BM((w - 6, 4, 0), (w - 6, 6, 58), 4, 6, white, "ξύλο"),
             BM((6, 2, 36), (6, 78, 18), 3, 10, white, "ξύλο"), BM((w - 6, 2, 36), (w - 6, 78, 18), 3, 10, white, "ξύλο"),
             BM((w / 2, 4, 38), (w / 2, 56, 26), 54, 2.5, white, "ξύλο"),
             BM((6, 0, 60), (6, 66, 60), 12, 2.5, white, "ξύλο"), BM((w - 6, 0, 60), (w - 6, 66, 60), 12, 2.5, white, "ξύλο")]
    for k in range(5):
        x = 17 + k * 10
        top = 88 - abs(k - 2) * 4
        parts.append(BM((x, 56, 26), (x, d - 2, top), 8, 2, white, "ξύλο"))
    return item("Πολυθρόνα κήπου αντιρόντακ", ("Εξωτερικοί χώροι",), (74, 88.9, 88.6),
                "https://www.flickr.com/photos/79865753@N00/2702254830", parts)


def pergola():
    # BethinAZ, CC BY 2.0 (timber pergola). Anchor: clear height 240 under the beams, 300x300 bay.
    wood, s = "#9c5a32", 300
    parts = [*[B((x, y, 0), (x + 15, y + 15, 250), wood, "κολόνες") for x in (10, s - 25) for y in (10, s - 25)]]
    for y in (10, s - 25):
        parts += [B((-15, y - 4, 230), (s + 15, y - 1, 255), wood, "δοκάρια"), B((-15, y + 16, 230), (s + 15, y + 19, 255), wood, "δοκάρια")]
    for k in range(9):
        x = 5 + k * 35
        parts.append(B((x, -15, 255), (x + 5, s + 15, 270), wood, "τεγίδες"))
    return item("Πέργκολα ξύλινη 300×300", ("Εξωτερικοί χώροι",), (330, 330, 270), "https://www.flickr.com/photos/20767049@N00/38961537", parts)


def picnic_table():
    # emily_sheldon, CC BY 2.0 (classic A-frame picnic table). Anchor: table 76, seats 45.
    w, grey = 180, "#9a9187"
    parts = []
    for k in range(5):
        parts.append(B((0, 40 + k * 14 + 0.5, 72), (w, 40 + (k + 1) * 14 - 0.5, 76), grey, "ξύλο"))
    for y0 in (0, 125):
        parts += [B((0, y0, 41), (w, y0 + 12, 45), grey, "ξύλο"), B((0, y0 + 13, 41), (w, y0 + 25, 45), grey, "ξύλο")]
    for x in (25, w - 30):
        parts += [BM((x + 2.5, 8, 2), (x + 2.5, 70, 68), 5, 8, grey, "σκελετός"), BM((x + 2.5, 142, 2), (x + 2.5, 80, 68), 5, 8, grey, "σκελετός"),
                  B((x, 0, 35), (x + 5, 150, 41), grey, "σκελετός"), B((x, 40, 64), (x + 5, 110, 72), grey, "σκελετός")]
    return item("Τραπέζι πικνίκ με πάγκους", ("Εξωτερικοί χώροι",), (w, 150, 76), "https://www.flickr.com/photos/26013167@N03/26172724401", parts)


def beach_deck_chair():
    # Yandle, CC BY 2.0 (striped folding deck chair). Anchor: seat front 35, 100 deep open.
    wood, stripes = "#b48a5a", ("#2e6fb5", "#f2f2ee")
    parts = [BM((3, 0, 0), (3, 80, 95), 4, 2.5, wood, "ξύλο"), BM((57, 0, 0), (57, 80, 95), 4, 2.5, wood, "ξύλο"),
             BM((6, 70, 0), (6, 10, 40), 4, 2.5, wood, "ξύλο"), BM((54, 70, 0), (54, 10, 40), 4, 2.5, wood, "ξύλο"),
             C((3, 10, 38), 1.5, 54, wood, "ξύλο", "x", 10)]
    for k in range(5):
        x = 6 + k * 9.6
        parts.append(BM((x + 4.8, 12, 36), (x + 4.8, 76, 88), 9.6, 0.6, stripes[k % 2], "ύφασμα"))
    return item("Σεζλόνγκ παραλίας πτυσσόμενη", ("Εξωτερικοί χώροι",), (58, 81.9, 96.8), "https://www.flickr.com/photos/13316988@N00/452905327", parts)


def steamer_lounger():
    # andrewmalone, CC BY 2.0 (teak ship's deck lounger). Anchor: seat 38, back 95, length 160.
    teak, cushion = "#8a6440", "#2f3e5c"
    parts = [*[B((x, y, 0), (x + 4, y + 4, 36), teak, "ξύλο") for x in (2, 54) for y in (60, 100)],
             BM((4, 0, 30), (4, 60, 34), 4, 4, teak, "ξύλο"), BM((56, 0, 30), (56, 60, 34), 4, 4, teak, "ξύλο"),
             B((2, 2, 0), (6, 6, 30), teak, "ξύλο"), B((54, 2, 0), (58, 6, 30), teak, "ξύλο"),
             B((0, 60, 34), (60, 104, 38), teak, "ξύλο"), BM((30, 104, 38), (30, 150, 92), 60, 3, teak, "ξύλο"),
             BM((30, 0, 32), (30, 60, 36), 56, 2.5, teak, "ξύλο"),
             B((-2, 60, 56), (5, 112, 59), teak, "ξύλο"), B((55, 60, 56), (62, 112, 59), teak, "ξύλο"),
             B((-1, 64, 38), (3, 68, 56), teak, "ξύλο"), B((57, 64, 38), (61, 68, 56), teak, "ξύλο"),
             BM((30, 8, 38), (30, 100, 41), 54, 4, cushion, "μαξιλάρι"), BM((30, 102, 41), (30, 145, 90), 54, 4, cushion, "μαξιλάρι")]
    return item("Ξαπλώστρα ξύλινη τύπου καταστρώματος", ("Εξωτερικοί χώροι",), (64, 151.3, 93),
                "https://www.flickr.com/photos/41894170049@N01/808723740", parts)


def garden_swing():
    # ell brown, CC BY 2.0 (A-frame garden swing seat). Anchor: seat 45, frame 200.
    w, wood = 230, "#d9d5cc"
    parts = [B((0, 63, 192), (w, 71, 202), wood, "σκελετός")]
    for x in (4, w - 10):
        parts += [BM((x + 3, 0, 0), (x + 3, 63, 192), 6, 7, wood, "σκελετός"), BM((x + 3, 134, 0), (x + 3, 71, 192), 6, 7, wood, "σκελετός"),
                  B((x, 30, 40), (x + 6, 104, 46), wood, "σκελετός")]
    sx0, sx1 = 45, w - 45
    parts += [B((sx0, 45, 41), (sx1, 95, 45), wood, "κάθισμα"), BM(((sx0 + sx1) / 2, 92, 45), ((sx0 + sx1) / 2, 100, 92), sx1 - sx0, 3, wood, "κάθισμα"),
              B((sx0 - 4, 45, 41), (sx0, 98, 65), wood, "κάθισμα"), B((sx1, 45, 41), (sx1 + 4, 98, 65), wood, "κάθισμα")]
    for x in (sx0 - 2, sx1 + 2):
        for y in (50, 92):
            parts.append(C((x, y, 65 if y == 50 else 92), 0.6, 127 if y == 50 else 100, "#777b80", "αλυσίδες", segments=6))
    return item("Κούνια-καναπές κήπου", ("Εξωτερικοί χώροι",), (230, 140.7, 203.1), "https://www.flickr.com/photos/39415781@N06/7182115872", parts)


def iron_chair(x, y, facing, color):
    """Wrought-iron bistro chair centred on (x, y); its back is away from the table (facing -1/+1 in X)."""
    s, parts = 21, []
    for dx in (-s + 2, s - 2):
        for dy in (-s + 2, s - 2):
            parts.append(BM((x + dx * 1.1, y + dy * 1.1, 0), (x + dx, y + dy, 44), 1.6, 1.6, color, "σίδερο"))
    back = x - facing * (s - 1)
    parts += [C((x, y, 43), s, 2.5, color, "σίδερο", segments=24), C((x, y, 45.5), s - 2, 2.5, "#e8e3d4", "μαξιλάρι", segments=24),
              BM((back, y, 45), (back - facing * 4, y, 92), 40, 1.5, color, "σίδερο")]
    return parts


def bistro_set():
    # ell brown, CC BY 2.0 (blue wrought-iron bistro table and two chairs). Anchor: table 72, seat 45.
    blue = "#3d6ea8"
    parts = [C((80, 30, 70), 30, 2.5, blue, "σίδερο", segments=32), C((80, 30, 2), 2, 68, blue, "σίδερο", segments=12),
             TO((80, 30, 2), 18, 1.5, blue, "σίδερο", segments=24, sides=6),
             *iron_chair(23, 30, 1, blue), *iron_chair(137, 30, -1, blue)]
    return item("Σετ μπιστρό σφυρήλατο (τραπέζι + 2 καρέκλες)", ("Εξωτερικοί χώροι",), (163.5, 60, 92.1),
                "https://www.flickr.com/photos/39415781@N06/4653978832", parts)


def teak_chair(x, y, facing_y, color):
    """Slatted garden chair centred on (x, y), facing +Y (1) or -Y (-1)."""
    s = 23
    back = y - facing_y * (s - 2)
    return [*[B((x + dx - 2, y + dy - 2, 0), (x + dx + 2, y + dy + 2, 44), color, "ξύλο") for dx in (-s + 2, s - 2) for dy in (-s + 2, s - 2)],
            B((x - s, y - s, 42), (x + s, y + s, 46), color, "ξύλο"),
            BM((x, back, 46), (x, back - facing_y * 6, 92), 2 * s, 2.5, color, "ξύλο"),
            R((x - s + 3, y - s + 3, 46), (x + s - 3, y + s - 3, 50), 3, "#2f6a6a", "μαξιλάρια")]


def teak_dining_set():
    # ell brown, CC BY 2.0 (garden table with six chairs). Anchor: table 75, seat 46.
    teak = "#a08a6a"
    parts = [*legs(40, 50, 240, 140, 71, 6, teak), B((40, 50, 71), (240, 140, 75), teak, "ξύλο")]
    for x in (80, 140, 200):
        parts += teak_chair(x, 23, 1, teak) + teak_chair(x, 167, -1, teak)
    return item("Τραπεζαρία κήπου ξύλινη 6 θέσεων", ("Εξωτερικοί χώροι",), (200, 200.5, 92.2),
                "https://www.flickr.com/photos/39415781@N06/4653943656", parts)


def cast_iron_bench():
    # Gawler History, CC BY-SA 2.0 (white cast-iron garden bench). Anchor: seat 45, back 80, 120 long.
    w, d, white = 120, 55, "#eeece6"
    parts = [B((6, 6, 41), (w - 6, 46, 45), white, "κάθισμα")]
    for k in range(4):
        parts.append(B((6, 8 + k * 10, 45), (w - 6, 15 + k * 10, 46), white, "κάθισμα"))
    for x in (2, w - 4):
        parts += [BM((x + 1, 0, 0), (x + 1, 10, 41), 3, 4, white, "μαντέμι"), BM((x + 1, d, 0), (x + 1, 44, 41), 3, 4, white, "μαντέμι"),
                  BM((x + 1, 2, 62), (x + 1, 46, 62), 3, 4, white, "μαντέμι"), BM((x + 1, 6, 45), (x + 1, 4, 62), 3, 3, white, "μαντέμι"),
                  TO((x + 1, 6, 58), 5, 1.2, white, "μαντέμι", axis="x", segments=12, sides=6)]
    parts.append(BM((w / 2, 46, 45), (w / 2, 52, 80), w - 6, 2, white, "πλάτη"))
    for k in range(5):
        parts.append(TO((14 + k * 23, 50.5, 64), 8, 1.2, white, "πλάτη", axis="y", segments=14, sides=6))
    return item("Παγκάκι μαντεμένιο λευκό", ("Εξωτερικοί χώροι",), (117, 58.9, 80.7), "https://www.flickr.com/photos/69522134@N06/7157403280", parts)


def bird_bath():
    # Anonymous Account, CC BY 2.0 (stone bird bath). Anchor: bowl rim 75, Ø60.
    stone = "#a8a296"
    return item("Ποτίστρα πουλιών πέτρινη", ("Εξωτερικοί χώροι", "Διακόσμηση"), (60, 60, 75), "https://www.flickr.com/photos/37053322@N00/246624893", [
        L((30, 30, 0), ((18, 0), (18, 5), (10, 9), (8, 40), (10, 60)), stone, "πέτρα", 24),
        L((30, 30, 60), ((10, 0), (28, 10), (30, 15), (27, 15), (20, 11), (2, 9)), stone, "πέτρα", 32),
        C((30, 30, 68), 22, 2, WATER_BLUE, "νερό", segments=28)])


def pizza_oven():
    # vwcampin, CC BY 2.0 (tiled dome wood-fired oven on a masonry base). Anchor: hearth 100 (working height).
    brick, tile = "#a0563b", "#d9692b"
    return item("Φούρνος ξύλων θολωτός", ("Εξωτερικοί χώροι", "Συσκευές"), (120, 120, 200), "https://www.flickr.com/photos/125112383@N06/33535490660", [
        B((0, 0, 0), (120, 120, 92), brick, "βάση"), B((-0, 0, 92), (120, 120, 100), STONE, "πλάκα"),
        L((60, 64, 100), ((52, 0), (50, 22), (40, 42), (22, 56), (6, 60)), tile, "θόλος", 28),
        B((40, 6, 100), (80, 30, 132), tile, "θόλος"), B((45, 5, 100), (75, 6, 126), "#1e1a18", "στόμιο"),
        C((60, 26, 128), 7, 72, "#4a4a4a", "καπνοδόχος", segments=16), C((60, 26, 196), 10, 4, "#4a4a4a", "καπνοδόχος", segments=16)])


def gas_grill():
    # Janice Temple Tour Organizer, CC BY-SA 2.0 (gas grill on a cart with side shelves). Anchor: grill 90.
    w, d, black = 140, 60, "#222426"
    parts = [B((30, 6, 12), (110, 54, 82), "#2e3134", "ντουλάπι"), B((30, 5.5, 16), (110, 6, 78), "#3a3d41", "πόρτες"),
             *[C((x, y, 0), 6, 4, BLACK, "ρόδες", "y", 14) for x in (36, 104) for y in (8, 48)],
             B((25, 0, 82), (115, d, 96), black, "σώμα"), C((25, 30, 96), 30, 90, black, "καπάκι", "x"),
             B((0, 5, 92), (25, 55, 95), STEEL, "ράφια"), B((115, 5, 92), (w, 55, 95), STEEL, "ράφια"),
             C((35, -4, 108), 1.4, 70, CHROME, "χερούλι", "x", 10)]
    for k in range(4):
        parts.append(C((40 + k * 20, -2, 89), 2, 2, CHROME, "διακόπτες", "y", 12))
    return item("Ψησταριά υγραερίου με καπάκι", ("Εξωτερικοί χώροι",), (140, 65.4, 132), "https://www.flickr.com/photos/52232167@N05/5963838259", parts)


def kamado():
    # Didriks, CC BY 2.0 (ceramic egg-shaped grill on a stand). Anchor: grill grate 85.
    green = "#2f6b3e"
    return item("Ψησταριά κεραμική «αυγό»", ("Εξωτερικοί χώροι",), (110, 62, 125.2), "https://www.flickr.com/photos/49889671@N03/14272326440", [
        *[BM((55 + 22 * math.cos(math.radians(a)), 30 + 22 * math.sin(math.radians(a)), 0), (55 + 18 * math.cos(math.radians(a)),
              30 + 18 * math.sin(math.radians(a)), 30), 3, 3, BLACK, "βάση") for a in (90, 210, 330)],
        L((55, 30, 28), ((14, 0), (26, 12), (30, 34), (28, 60), (20, 80), (8, 90), (5, 93)), green, "κεραμικό", 28),
        C((55, 30, 121), 4, 4, "#6a6a6a", "καπνοδόχος", segments=12),
        B((0, 18, 78), (25, 42, 80), "#a07a4a", "ράφια"), B((85, 18, 78), (110, 42, 80), "#a07a4a", "ράφια"),
        B((52, -2, 95), (58, 4, 98), "#a07a4a", "χερούλι")])


def patio_heater():
    # jasonwoodhead23, CC BY 2.0 (mushroom patio heater). Anchor: reflector Ø80 at 225.
    steel = "#b9bcc0"
    return item("Θερμάστρα αερίου εξωτερικού χώρου", ("Εξωτερικοί χώροι",), (80, 80, 228), "https://www.flickr.com/photos/80365963@N00/5215746651", [
        L((40, 40, 0), ((24, 0), (24, 4), (20, 8), (20, 78), (12, 82), (4, 84)), steel, "βάση", 28),
        C((40, 40, 84), 4, 106, steel, "κολόνα", segments=16),
        L((40, 40, 190), ((6, 0), (9, 6), (9, 24), (6, 26)), "#5a5e63", "καυστήρας", 20),
        L((40, 40, 216), ((4, 0), (40, 8), (40, 10), (39, 10), (3, 2)), steel, "ανακλαστήρας", 32),
        C((40, 40, 222), 3, 6, steel, "ανακλαστήρας", segments=12)])


def specs():
    return [
        # living room
        chesterfield_sofa(), midcentury_armchair(), wingback_chair(), carved_settee(), rocking_chair(), club_chair(),
        nesting_tables(), bean_bag(), peacock_chair(), glass_coffee_table(), futon_sofa_bed(), leather_loveseat(),
        wicker_daybed(),
        # dining
        bentwood_chair(), windsor_chair(), taverna_chair(), farmhouse_table(), pedestal_table(), industrial_stool(),
        bar_cart_industrial(), bar_cart_brass(), kitchen_island(),
        # bedroom
        canopy_bed(), armoire(), steamer_trunk(), painted_chest(), writing_desk_small(),
        # children
        teepee(), rocking_horse(), kids_table_set(), book_display(), play_tower(),
        # bathroom
        floating_vanity_bowl(), stone_basin(), clawfoot_tub(), copper_tub(), wood_vanity_glass_bowl(), towel_ladder(),
        shower_column(), frameless_shower(), plank_washstand(),
        # appliances
        retro_fridge(), range_cooker(), chest_freezer(), wood_stove(), ceiling_fan(),
        # office
        rolltop_desk(), drafting_table(), filing_cabinet(), cube_bookcase(), bureau(), scandi_desk(),
        # lighting
        arc_lamp(), bulb_pendant(), crystal_chandelier(), globe_pendant(), paper_lantern(), woven_pendant(),
        mushroom_lamp(), stained_glass_lamp(), bedside_lamp(), torchiere(), dome_desk_lamp(), globe_sconce(),
        # decoration
        olive_concrete_pot(), monstera(), amphora(), basket(), floor_vase(), sunburst_mirror(), hurricane_vase(),
        cactus(), bonsai(), garden_urn(),
        # entrance
        shoe_bench(), hall_stand(), plank_coat_rack(), shoe_cubby(), iron_console(), marble_console(),
        # outdoor
        hanging_chair(), hammock(), adirondack(), pergola(), picnic_table(), beach_deck_chair(), steamer_lounger(),
        garden_swing(), bistro_set(), teak_dining_set(), cast_iron_bench(), bird_bath(), pizza_oven(), gas_grill(),
        kamado(), patio_heater(),
    ]
