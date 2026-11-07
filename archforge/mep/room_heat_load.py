"""Θερμικό φορτίο ανά χώρο (07/11): ό,τι υπολογίζει το ``heat_load`` για όλο το κτίριο, μοιρασμένο στους χώρους —
η βάση για τα σώματα και τον υδραυλικό υπολογισμό (παροχή κάθε κυκλώματος = φορτίο του χώρου του / c·ΔT).

Ίδιοι τύποι, ίδιες υποθέσεις και ίδια όρια με το ``heat_load`` (ενδεικτικό, όχι μελέτη EN 12831-1 / ΚΕΝΑΚ):

* **τοίχοι**: κάθε εξωτερικός τοίχος μοιράζεται στους χώρους που έχουν πλευρά πάνω στον άξονά του, κατά το μήκος
  της πλευράς · τα κουφώματα του τοίχου πάνε στον χώρο όπου πέφτει το κέντρο τους;
* **οροφή / δάπεδο**: το κομμάτι του χώρου χωρίς χώρο από πάνω / από κάτω;
* **αερισμός**: εμβαδόν × μέσο ύψος ορόφου × αλλαγές αέρα (όπως το σύνολο);
* **προς μη θερμαινόμενους** (κλιμακοστάσιο, αποθήκη, λεβητοστάσιο…): τοίχοι / πόρτες / πλάκες × b·U·ΔT· οι ίδιοι οι
  μη θερμαινόμενοι χώροι δεν έχουν φορτίο;
* **θερμογέφυρες**: μένουν στο κτίριο (δεν μοιράζονται — λέγεται).
* **διαμέρισμα**: Ιδιότητες χώρου ▸ Διαμέρισμα, αλλιώς ένα ανά όροφο· τα μη θερμαινόμενα = «Κοινόχρηστα».

Κανόνας: Σ χώρων + «κτίριο» = το σύνολο του ``heat_load``, όρο προς όρο (τεστ και έλεγχος των bot).
"""
from __future__ import annotations

import math


def room_loads(doc, season="winter"):
    """``{"rooms": [{"z", "signature", "name", "apartment", "heated", "area_m2", "parts": {...}, "watts"}],
    "apartments": {name: W}, "building": {part: W not in a room}, "total": heat_load result}`` — the rooms are the
    ones ``heat_load`` sums (one computation), so they add up to it by construction."""
    from archforge.mep.heat_load import heat_load
    total = heat_load(doc, season)
    rooms = total["rooms"]
    building = {k: round(float(v) - sum(r["parts"].get(k, 0.0) for r in rooms), 1) for k, v in total["parts"]}
    return {"rooms": rooms, "apartments": total["apartments"], "building": building, "total": total}


def emitter_loads(doc):
    """``{emitter id: W}``: each room's load shared equally among the radiators / fan coils in it (the engineer
    sizes them — this is the flow each needs, for the hydraulics).  Emitters outside every room get nothing."""
    from archforge.mep.heating_layout import EMITTERS, heating_points
    from archforge.mep.ventilation import _floor_of
    from archforge.assistant.understanding import inside
    loads = room_loads(doc)
    ems = [e for e in heating_points(doc) if e.params.get("point_type") in EMITTERS]
    out = {e.id: 0.0 for e in ems}
    for r in loads["rooms"]:
        here = [e for e in ems if abs(_floor_of(doc, float(e.params["z"])) - r["z"]) < 1e-6
                and inside(r["polygon"], float(e.params["x"]), float(e.params["y"]))]
        for e in here:
            out[e.id] += r["watts"] / len(here)
    return out
