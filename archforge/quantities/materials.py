"""Priced material lists: every quantity the program measures, with a price column the user fills in.

Each list is ``[(description, unit, quantity)]`` (quantity None = from another
study, e.g. reinforcement from the structural design).  Isotex has its own
list.  ``write_workbook`` writes them as sheets of one .xlsx whose totals are
Excel formulas (quantity × unit price, SUM).
"""
from __future__ import annotations

from archforge.quantities.xlsx import write_priced_workbook


def isotex_list(doc):
    from archforge.construction.isotex import BLOCKS, take_off_isotex
    r = take_off_isotex(doc)
    if not r["walls"]:
        return []
    rows = [(f"Τεμάχιο {BLOCKS[c][0]} — 50×25×{BLOCKS[c][1] * 100:.0f} cm", "τεμ.", v["blocks"]) for c, v in r["by_code"].items()]
    t = r["totals"]
    rows += [("Σκυρόδεμα πλήρωσης τεμαχίων" + (" (μέρος κατ' εκτίμηση)" if r["estimated"] else ""), "m³", t["concrete_m3"]),
             ("Οπλισμός τοιχωμάτων (κατακόρυφος/οριζόντιος) — από τη στατική μελέτη", "kg", None),
             ("Πρέκια / σενάζ — από τη στατική μελέτη", "m", None),
             ("Εργασία τοποθέτησης τεμαχίων Isotex", "m²", t["net_m2"]),
             ("Εργασία σκυροδέτησης πλήρωσης", "m³", t["concrete_m3"])]
    return rows


def takeoff_list(doc):
    from archforge.quantities.takeoff import take_off
    r = take_off(doc)
    t, d = r["totals"], r["demolition"]
    rows = [("Βαφή τοίχων", "m²", t["paint_walls_m2"]), ("Βαφή οροφών", "m²", t["paint_ceiling_m2"]),
            ("Πλακάκια δαπέδου", "m²", t["floor_tiles_m2"]), ("Πλακάκια τοίχου (υγρά)", "m²", t["wall_tiles_m2"]),
            ("Ξύλινο δάπεδο", "m²", t["wood_floor_m2"]), ("Σοβατεπί", "m", t["skirting_m"]),
            ("Καθαίρεση τοίχων", "m³", d["walls_m3"]), ("Διάνοιξη ανοιγμάτων σε υφιστάμενους τοίχους", "τεμ.", d["openings_to_cut"])]
    return [row for row in rows if row[2]]


def drainage_list(doc):
    if not any(e.kind == "plumbing_point" for e in doc.entities.values()):
        return []
    from archforge.mep.drainage import route_drainage_cached
    route = route_drainage_cached(doc)
    rows = [(f"Σωλήνας αποχέτευσης PVC Φ{dn}", "m", round(m, 2)) for dn, m in sorted(route["report"]["length_by_dn"].items()) if m > 0]
    for kind, label in (("floor_drain", "Σιφώνι δαπέδου"), ("stack", "Στήλη αποχέτευσης — αερισμός/καπέλο"), ("manhole", "Φρεάτιο")):
        n = sum(1 for x in route["nodes"] if x["kind"] == kind)
        if n:
            rows.append((label, "τεμ.", n))
    return rows


def all_lists(doc):
    """``[(sheet name, title, rows, notes)]`` for the lists that have quantities."""
    from archforge.construction.isotex import PROVENANCE as ISOTEX
    out = []
    for name, title, rows, notes in (
            ("Isotex", "Λίστα Isotex — τεμάχια, σκυρόδεμα, εργασίες", isotex_list(doc), (ISOTEX,)),
            ("Επιμέτρηση", "Επιμέτρηση εργασιών (σύνολα έργου)", takeoff_list(doc), ("Ανά χώρο: Κατασκευή → Επιμέτρηση εργασιών.",)),
            ("Αποχέτευση", "Αποχέτευση — σωλήνες και εξαρτήματα", drainage_list(doc), ("Προμελέτη — προς έλεγχο μηχανολόγου.",))):
        if rows:
            out.append((name, title, rows, ("Συμπλήρωσε τις κίτρινες στήλες (τιμή μονάδας και ό,τι ποσότητα λείπει)· "
                                            "τα σύνολα βγαίνουν αυτόματα.",) + tuple(notes)))
    return out


def write_workbook(doc, path, only=None):
    sheets = [s for s in all_lists(doc) if only is None or s[0] in only]
    if not sheets:
        return None
    return write_priced_workbook(path, sheets)
