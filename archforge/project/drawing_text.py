"""What a CAD drawing *writes* (owner 22/10: «το PDF είναι συνολικό σχέδιο … να δώσει πλήρη απεικόνιση σε 3D»).

An exported plan carries, as text, what its lines alone do not say:

* the scale — «SCALE 1:50» / «ΚΛΙΜΑΚΑ 1:50»;
* levels with their place — «+114.00m [F.L.]», «±00.00m [F.L.]», «-1.65m [C.L.]» (finished floor / ceiling);
* rooms — a name with its area under it — «BEDROOM» / «9.60 sq.m.»;
* openings — «w: 0.90 | h: 2.30», often written along a wall (vertical text).

Texts are rebuilt from the characters, by writing direction: pdfplumber's lines join neighbouring columns
(«w.c. BATHROOM BATHROOM») and break vertical text into one line per character.  Positions are in the
underlay's drawing units (PDF points of the page as shown, y up — ``underlay.pdf_vector_segments``).
The owner's comments (PDF annotations) are not part of the drawing and are not read.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Text:
    text: str
    x: float                 # centre, drawing units (pt, y up)
    y: float
    size: float              # character height (pt)
    angle: float             # writing direction, degrees (0 = left to right)


def _direction(matrix):
    """Writing direction in the page as shown (y up).  pdfplumber reports a turned page (/Rotate) already
    turned — the characters' matrices as well as their boxes (MASTERPLAN, /Rotate 270, reads at 0°)."""
    a, b = float(matrix[0]), float(matrix[1])
    n = math.hypot(a, b) or 1.0
    return a / n, b / n


def pdf_texts(path, page=0) -> List[Text]:
    """Every text run of the page: characters grouped by direction, baseline and spacing."""
    import pdfplumber
    with pdfplumber.open(str(path)) as pdf:
        p = pdf.pages[int(page)]
        cx0, ct, cx1, cb = (float(v) for v in p.cropbox)
        chars = []
        for ch in p.chars:
            x, y = (float(ch["x0"]) + float(ch["x1"])) / 2 - cx0, cb - (float(ch["top"]) + float(ch["bottom"])) / 2
            if not (0 <= x <= cx1 - cx0 and 0 <= y <= cb - ct):
                continue
            ux, uy = _direction(ch.get("matrix") or (1, 0, 0, 1, 0, 0))
            # Extent along the writing direction: the glyph box seen along (ux, uy).
            extent = abs(float(ch["x1"]) - float(ch["x0"])) * abs(ux) + abs(float(ch["bottom"]) - float(ch["top"])) * abs(uy)
            chars.append((ch["text"], x, y, float(ch.get("size") or 1.0), ux, uy, extent))
    groups = {}
    for c in chars:
        key = (round(c[4], 1), round(c[5], 1))
        groups.setdefault(key, []).append(c)
    out = []
    for (ux, uy), cs in groups.items():
        n = math.hypot(ux, uy) or 1.0
        ux, uy = ux / n, uy / n
        nx, ny = -uy, ux
        rows = {}
        for c in cs:                                   # baseline = offset across the writing direction
            across = c[1] * nx + c[2] * ny
            row = next((k for k in rows if abs(k - across) <= 0.35 * c[3]), None)
            rows.setdefault(across if row is None else row, []).append(c)
        for row in rows.values():
            row.sort(key=lambda c: c[1] * ux + c[2] * uy)
            run = [row[0]]
            for prev, c in zip(row, row[1:]):
                if _gap(prev, c, ux, uy) > 1.6 * max(prev[3], c[3]):
                    out.append(_text(run, ux, uy)); run = []
                run.append(c)
            out.append(_text(run, ux, uy))
    return [t for t in out if t.text.strip()]


def _gap(a, b, ux, uy):
    """Empty space between two characters along the writing direction (edge to edge)."""
    return (b[1] - a[1]) * ux + (b[2] - a[2]) * uy - (a[6] + b[6]) / 2


def _text(run, ux, uy):
    text, prev = "", None
    for c in run:
        if prev is not None and _gap(prev, c, ux, uy) > 0.2 * max(prev[3], c[3]) and not text.endswith(" "):
            text += " "                                  # an empty space wider than a fifth of a character
        text += c[0]
        prev = c
    xs, ys = [c[1] for c in run], [c[2] for c in run]
    return Text(text.strip(), (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(c[3] for c in run),
                math.degrees(math.atan2(uy, ux)))


# ------------------------------------------------------------------------------------------------- what it says

_NUM = r"(\d+(?:[.,]\d+)?)"
SCALE = re.compile(r"(?:SCALE|ΚΛΙΜΑΚΑ|ΚΛΙΜΑΚΑ:)\s*:?\s*1\s*:\s*(\d+)", re.I)
# «+114.00m [F.L.]», «±00.00m», «-2.80m»: a signed value in metres; [C.L.] marks a ceiling.  «h:2.42m» is a height.
# An altitude may also be written without a sign («126.00m», ground spots on the masterplan): two digits or more.
LEVEL = re.compile(r"(?<![:\w.])([+\-−±]|(?=\d{2,}[.,]\d+\s*m\b))\s*(\d+[.,]\d+)\s*m\b(?:\s*\[\s*(F\.?\s*L|C\.?\s*L)\.?\s*\])?", re.I)
AREA = re.compile(rf"^{_NUM}\s*(?:sq\.?\s*m\.?|m²|m2|τ\.?\s*μ\.?)$", re.I)
# «w: 0.90 | h: 2.30» a door; «w: 0.60 | s: 1.20 | h: 1.00» a window (s = sill).
OPENING = re.compile(rf"w\s*:\s*{_NUM}\s*\|?\s*(?:s\s*:\s*{_NUM}\s*\|?\s*)?h\s*:\s*{_NUM}", re.I)


def _f(s):
    return float(s.replace(",", "."))


def scale(texts) -> Optional[int]:
    for t in texts:
        m = SCALE.search(t.text)
        if m:
            return int(m.group(1))
    return None


@dataclass
class Level:
    value: float             # metres, signed (±0 → 0)
    ceiling: bool            # [C.L.] ceiling level, else [F.L.] finished floor
    x: float
    y: float


def levels(texts) -> List[Level]:
    out = []
    for t in texts:
        for m in LEVEL.finditer(t.text):
            sign = -1.0 if m.group(1) in ("-", "−") else 1.0
            out.append(Level(sign * _f(m.group(2)), bool(m.group(3)) and m.group(3).upper().startswith("C"), t.x, t.y))
    return out


@dataclass
class Room:
    name: str
    area: float
    x: float
    y: float


def rooms(texts) -> List[Room]:
    """A «xx sq.m.» text and the name written just above it (same column, within two lines)."""
    out = []
    # Two letters at least, not necessarily together («w.c.»).
    names = [t for t in texts if len(re.findall(r"[A-Za-zΑ-Ωα-ωά-ώ]", t.text)) >= 2 and not AREA.match(t.text.strip())
             and not LEVEL.search(t.text) and not OPENING.search(t.text) and abs(t.angle) < 1]
    for t in texts:
        m = AREA.match(t.text.strip())
        if not m or abs(t.angle) >= 1:
            continue
        above = [n for n in names if 0 < n.y - t.y <= 2.6 * t.size and abs(n.x - t.x) <= max(len(n.text), 6) * 0.6 * n.size]
        if above:
            name = min(above, key=lambda n: (n.y - t.y) + 0.2 * abs(n.x - t.x))
            out.append(Room(name.text, _f(m.group(1)), (name.x + t.x) / 2, (name.y + t.y) / 2))
    return out


@dataclass
class OpeningLabel:
    width: float
    height: float
    x: float
    y: float
    angle: float
    sill: Optional[float] = None       # given → a window, else a door

    @property
    def kind(self):
        return "window" if self.sill is not None else "door"


def openings(texts) -> List[OpeningLabel]:
    out = []
    for t in texts:
        for m in OPENING.finditer(t.text):
            sill = _f(m.group(2)) if m.group(2) else None
            out.append(OpeningLabel(_f(m.group(1)), _f(m.group(3)), t.x, t.y, t.angle, sill))
    return out


def model_labels(params):
    """Scale, levels, rooms and opening labels of a PDF underlay, positions in model coordinates (metres)."""
    from archforge.project.underlay import to_model
    texts = pdf_texts(params["path"], params.get("page", 0)) if params.get("source") == "pdf" else []
    rot = float(params.get("rotation", 0.0))

    def at(item):
        item.x, item.y = to_model(params, item.x, item.y)
        if hasattr(item, "angle"):
            item.angle = item.angle + rot
        return item
    return {"scale": scale(texts), "levels": [at(v) for v in levels(texts)], "rooms": [at(v) for v in rooms(texts)],
            "openings": [at(v) for v in openings(texts)]}


# Room names of English-language drawings → (Greek name, use of ui/marking_menu.ROOM_USES).
ROOM_NAMES = (
    (r"MASTER\s+BED", "Κύριο υπνοδωμάτιο", "Υπνοδωμάτιο"), (r"BED\s*ROOM", "Υπνοδωμάτιο", "Υπνοδωμάτιο"),
    (r"BATH\s*ROOM|SHOWER", "Μπάνιο", "Μπάνιο"), (r"^W\.?\s*C\.?$|TOILET", "WC", "WC"),
    (r"LIVING.*KITCHEN|KITCHEN.*LIVING", "Σαλόνι – κουζίνα", "Σαλόνι – κουζίνα"),
    (r"LIVING|LOUNGE|SITTING", "Σαλόνι", "Σαλόνι"), (r"KITCHEN", "Κουζίνα", "Κουζίνα"),
    (r"DINING", "Τραπεζαρία", "Σαλόνι"), (r"CORRIDOR|HALL|PASSAGE", "Διάδρομος", "Διάδρομος"),
    (r"ENTRANCE|ENTRY|FOYER", "Είσοδος", "Διάδρομος"), (r"OFFICE|STUDY", "Γραφείο", "Γραφείο"),
    (r"STOR(E|AGE)|PANTRY", "Αποθήκη", "Αποθήκη"), (r"LAUNDRY", "Πλυσταριό", "Πλυσταριό"),
    (r"BOILER", "Λεβητοστάσιο", "Λεβητοστάσιο"), (r"ENGINE\s*ROOM|PLANT\s*ROOM|MACHINE", "Μηχανοστάσιο", "Λεβητοστάσιο"),
    (r"GARAGE|PARKING", "Γκαράζ", "Γκαράζ"), (r"POOL", "Πισίνα", "Πισίνα"),
    (r"COURS\s*ANGLAIS|LIGHT\s*WELL|ATRIUM|PATIO", "Αίθριο (cours anglais)", "Αυλή"), (r"YARD|GARDEN|TERRACE", "Αυλή", "Αυλή"),
    (r"WATER\s*TANK|TANK", "Δεξαμενή", "Αποθήκη"),
)


def greek_room(name) -> Tuple[str, str]:
    """(name, use) in Greek for a drawing's room label; an unknown label keeps its text, use = its text."""
    for pattern, gr, use in ROOM_NAMES:
        if re.search(pattern, name.strip(), re.I):
            return gr, use
    return name.strip(), name.strip()


# ------------------------------------------------------------------------------------------ scale from dimensions

STANDARD_SCALES = (1, 2, 5, 10, 20, 25, 50, 75, 100, 200, 250, 500, 1000, 2000, 2500, 5000)
DIMENSION = re.compile(r"^\d{1,3}[.,]\d{2}$")


def scale_from_dimensions(texts, segments):
    """(1:N, votes) read off the dimensions (owner 22/10: «η κλίμακα μπορεί να βγει από τις διαστάσεις»).

    A dimension's number («6.00», metres) is written along its dimension line, just beside it: the line's
    length on paper (PDF points, 1/72 inch) against the number gives 1:N.  Every dimension votes for the
    nearest standard scale (within 4 %); the most voted wins.  None when fewer than three agree."""
    dims = [t for t in texts if DIMENSION.match(t.text.strip()) and _f(t.text.strip()) > 0]
    if not dims:
        return None, 0
    # Grid of the segments by the cells they cross (cell = a few text heights): each number looks only nearby.
    cell = 4.0 * max(t.size for t in dims)
    grid = {}
    for seg in segments:
        x1, y1, x2, y2 = seg
        for gx in range(int(min(x1, x2) // cell), int(max(x1, x2) // cell) + 1):
            for gy in range(int(min(y1, y2) // cell), int(max(y1, y2) // cell) + 1):
                grid.setdefault((gx, gy), []).append(seg)
                if len(grid) > 4_000_000:
                    break
    votes = {}
    for t in dims:
        value = _f(t.text.strip())
        ux, uy = math.cos(math.radians(t.angle)), math.sin(math.radians(t.angle))
        best = None
        near = {s for dx in (-1, 0, 1) for dy in (-1, 0, 1) for s in grid.get((int(t.x // cell) + dx, int(t.y // cell) + dy), ())}
        for x1, y1, x2, y2 in near:
            L = math.hypot(x2 - x1, y2 - y1)
            if L < 3 * t.size:
                continue
            if abs(((x2 - x1) * uy - (y2 - y1) * ux) / L) > 0.02:
                continue                                         # not parallel to the text
            across = abs((t.x - x1) * -uy + (t.y - y1) * ux)
            along = (t.x - x1) * ux + (t.y - y1) * uy
            lo, hi = sorted((0.0, (x2 - x1) * ux + (y2 - y1) * uy))
            if across > 1.5 * t.size or not lo < along < hi:
                continue
            if best is None or across < best[0]:
                best = (across, L)
        if best is None:
            continue
        n = value * 1000.0 / (best[1] * 25.4 / 72.0)          # metres on paper (mm) → 1:N
        std = min(STANDARD_SCALES, key=lambda s: abs(s - n) / s)
        if abs(std - n) / std <= 0.04:
            votes[std] = votes.get(std, 0) + 1
    if not votes:
        return None, 0
    std, count = max(votes.items(), key=lambda kv: kv[1])
    return (std, count) if count >= 3 else (None, count)
