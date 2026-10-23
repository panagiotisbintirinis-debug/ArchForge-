"""What a room is, from what is drawn in it — for plans that write no room names (the owner's OLD VILLA upper
floor: not one label, only «fridge», «COOKTOP», «ENTRANCE»; HANDOFF 22/10 «OLD VILLA πάνω όροφος χωρίς
ετικέτες χώρων»).

The architect's blocks are told by their size, as a person reads them:

* **bed**: a light grey fill 1,35–2,20 × 1,85–2,25 (double: 2,00 × 1,60) or 0,55–1,05 × 1,60–2,15 (single, bunk);
* **table**: a light grey fill 0,75–1,25 × 1,00–1,59 (the dining tables 1,40 × 1,00);
* **toilet**: an outline curve of 6+ points, 0,18–0,45 × 0,45–0,75 (the bowl);
* **bath / shower tray**: an outline rectangle 0,65–0,95 × 1,40–1,95;
* **kitchen**: the words written in it — fridge, cooktop, oven, hob, sink (and Greek).

A room is named only by what it holds (a bed → bedroom, a toilet or a bath → bathroom / WC, kitchen words →
kitchen, a table → dining); of the rooms left the largest one the drawing gives a room height («H=3.07m») is
the living room.  Anything else stays unnamed — never guessed.  Plain data, no Qt.
"""
from __future__ import annotations

import re

KITCHEN_WORDS = re.compile(r"FRIDGE|COOK\s*TOP|OVEN|\bHOB\b|SINK|ΨΥΓΕΙΟ|ΚΟΥΖΙΝ|ΕΣΤΙΑ|ΦΟΥΡΝΟΣ", re.I)
ROOM_HEIGHT = re.compile(r"^\s*H\s*=\s*\d+[.,]\d+\s*m?\s*$", re.I)


def _grey(colour, lo=0.55, hi=0.95):
    if not isinstance(colour, (list, tuple)) or len(colour) != 3:
        return False
    r, g, b = (float(v) for v in colour)
    return abs(r - g) < 0.02 and abs(g - b) < 0.02 and lo <= r <= hi


def kind_of(w, h, filled, colour, curve, points):
    """The block a drawn shape is, or None."""
    a, b = sorted((w, h))
    if filled and _grey(colour):
        if 1.35 <= a <= 2.20 and 1.85 <= b <= 2.25:
            return "bed"
        if 0.55 <= a <= 1.05 and 1.60 <= b <= 2.15:
            return "bed"
        if 0.75 <= a <= 1.25 and 1.00 <= b <= 1.59:
            return "table"
        return None
    if not filled:
        if curve and points >= 6 and 0.18 <= a <= 0.45 and 0.45 <= b <= 0.75:
            return "toilet"
        if not curve and 0.65 <= a <= 0.95 and 1.40 <= b <= 1.95:
            return "bath"
    return None


def read_items(path, page=0, metres_per_pt=1.0):
    """``[(kind, x, y)]`` of the blocks on the page as shown (metres at the sheet's scale, y up)."""
    import pdfplumber
    out = []
    with pdfplumber.open(str(path)) as pdf:
        p = pdf.pages[int(page)]
        cx0, _ct, _cx1, cb = (float(v) for v in p.cropbox)
        for o in list(p.rects) + list(p.curves):
            filled = bool(o.get("fill"))
            colour = o.get("non_stroking_color") if filled else o.get("stroking_color")
            w = (float(o["x1"]) - float(o["x0"])) * metres_per_pt
            h = (float(o["bottom"]) - float(o["top"])) * metres_per_pt
            kind = kind_of(w, h, filled, colour, o.get("object_type") == "curve", len(o.get("pts") or ()))
            if kind:
                x = ((float(o["x0"]) + float(o["x1"])) / 2 - cx0) * metres_per_pt
                y = (cb - (float(o["top"]) + float(o["bottom"])) / 2) * metres_per_pt
                if not any(k == kind and abs(x - u) < 0.05 and abs(y - v) < 0.05 for k, u, v in out):
                    out.append((kind, x, y))              # the same block filled and outlined is one
    return out


def words(texts):
    """``[(kind, x, y)]`` from the texts: kitchen words and room heights (texts' own units)."""
    out = []
    for t in texts:
        if KITCHEN_WORDS.search(t.text):
            out.append(("kitchen", t.x, t.y))
        elif ROOM_HEIGHT.match(t.text):
            out.append(("height", t.x, t.y))
    return out


def _area(poly):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]))) / 2


def name_rooms(faces, items, min_area=1.0):
    """``{face index: label}`` (English labels, as a drawing would write them — drawing_text.greek_room turns them
    Greek) for ``faces`` (polygons) from ``items`` (kind, x, y) in the same frame."""
    from archforge.geometry.regions import point_in_polygon
    held = []
    for poly in faces:
        held.append({k for k, x, y in items if point_in_polygon(x, y, poly)})
    out = {}
    for i, poly in enumerate(faces):
        a, has = _area(poly), held[i]
        if a < min_area:
            continue
        if "bed" in has:
            out[i] = "BEDROOM"
        elif "kitchen" in has:
            out[i] = "KITCHEN"
        elif has & {"toilet", "bath"} and a <= 12.0:
            out[i] = "BATHROOM" if "bath" in has or a > 2.5 else "WC"
        elif "table" in has and "height" in has:
            out[i] = "DINING"
    rest = [i for i, poly in enumerate(faces) if i not in out and "height" in held[i] and _area(poly) >= 12.0]
    if rest:
        out[max(rest, key=lambda i: _area(faces[i]))] = "LIVING"
    beds = [i for i, n in out.items() if n == "BEDROOM"]
    if len(beds) > 1:
        out[max(beds, key=lambda i: _area(faces[i]))] = "MASTER BEDROOM"
    return out
