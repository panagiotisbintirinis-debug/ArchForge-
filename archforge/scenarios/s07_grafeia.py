"""S07 — γραφεία 15 × 10 m: ανοιχτός χώρος εργασίας, αίθουσα συσκέψεων, κουζινάκι, δύο WC (σχέδιο δοκιμής).

Εξωτερικοί τοίχοι μπετό με θερμοπρόσοψη 8 cm (37 cm), εσωτερικοί γυψοσανίδα 10 cm. Χρήση «γραφεία» για τα
φορτία της στατικής. Δώμα. Δοκιμάζει: άλλη χρήση κτιρίου, ξηρά δόμηση στην προσφορά, πολλές θέσεις εργασίας.
"""
from __future__ import annotations

from archforge.scenarios.builder import build_spec

KEY = "07"
NAME = "S07_grafeia"
TITLE = "Γραφεία 150 m²: open space, συσκέψεις, κουζινάκι, 2 WC, δώμα"
EXT, I = 0.37, 0.10
DESKS = [(x, y) for y in (2.4, 5.6) for x in (2.2, 4.8, 7.4)]
SPEC = {
    "levels": [("Ground", 0.0)],
    "storeys": {"Ground": {
        "outline": [(0, 0), (15, 0), (15, 10), (0, 10), (0, 0)], "ext": EXT,
        "walls": [((10, 0), (10, 10), I), ((10, 6), (15, 6), I), ((10, 3), (15, 3), I), ((12.5, 0), (12.5, 3), I)],
        "wall_types": {"ext": "concrete_etics", "int": "drywall_100"},
        "openings": [("door", 5.0, 0, 1.4), ("window", 1.5, 0, 1.6), ("window", 8.5, 0, 1.6), ("window", 0, 3.0, 1.6),
                     ("window", 0, 7.0, 1.6), ("window", 3.0, 10, 1.6), ("window", 7.0, 10, 1.6), ("window", 12.5, 10, 1.6),
                     ("window", 15, 8.0, 1.2), ("window", 15, 4.5, 1.0),
                     ("window", 11.25, 0, 0.6, {"height": 0.6, "sill": 1.6}), ("window", 13.75, 0, 0.6, {"height": 0.6, "sill": 1.6}),
                     ("door", 10, 8.0, 1.0), ("door", 10, 4.5, 0.9), ("door", 11.25, 3.0, 0.7), ("door", 13.75, 3.0, 0.7)],
        "rooms": {"Χώρος εργασίας": (5.0, 5.0), "Αίθουσα συσκέψεων": (12.5, 8.0), "Κουζίνα": (12.5, 4.5),
                  "WC 1": (11.25, 1.5), "WC 2": (13.75, 1.5)},
        "kitchen": (12.5, 5.6), "kitchen_shape": "I",
        "baths": [((11.25, 1.5), "shower"), ((13.75, 1.5), "shower")],
        "furniture": [f for x, y in DESKS for f in (("Γραφείο εργασίας 140", x, y, 180), ("Καρέκλα γραφείου", x, y + 0.8, 0))]
        + [("Τραπέζι τραπεζαρίας 8θέσιο", 12.5, 8.0, 0), ("Βιβλιοθήκη με ράφια", 0.5, 8.8, 0), ("Φυτό σε γλάστρα", 9.4, 9.4, 0),
           ("Καναπές διθέσιος", 7.0, 9.4, 0)]}},
    "roof": "flat",
    "mep": {"supply": (3.2, 0.3), "heater": ("Ground", 14.6, 3.4), "panel": ("Ground", 6.2, 0.3), "manhole": (12.5, -1.5),
            "points": [("Ground", "elec_air_conditioner", 0.25, 5.0), ("Ground", "elec_air_conditioner", 9.9, 2.0),
                       ("Ground", "elec_air_conditioner", 14.75, 7.0)]},
    "foundation": "strips", "occupancy": "office",
}
OWNER_PENDING = ("Θέρμανση/HVAC", "Προειδοποίηση: Κόμβος")
FINDINGS = [
    {"status": "FIXED", "found": "Πύλη: σωλήνας σε ταυ στη μέση άλλου σωλήνα μετρούσε ως ασύνδετος", "fix": "Το άκρο πάνω στον σωλήνα = σύνδεση",
     "files": ["scenarios/gate.py"], "commit": "(αυτό το commit)"},
    {"status": "FIXED", "found": "Πύλη: «καναπές στο σαλόνι» FAIL σε κτίριο χωρίς σαλόνι (γραφεία)", "fix": "N/A όταν δεν υπάρχει σαλόνι/υπνοδωμάτιο",
     "files": ["scenarios/gate.py"], "commit": "(αυτό το commit)"},
]
NOTES = ""


def build(window):
    return build_spec(window, KEY, TITLE, SPEC)
