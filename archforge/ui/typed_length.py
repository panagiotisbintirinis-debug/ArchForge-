"""Μήκος και γωνία με το πληκτρολόγιο την ώρα της σχεδίασης τοίχου.

Κριτική v5 (04/11, `docs/reviews/2026-11-04_v5/SYNOPSIS.md`): 7/7 ψήφοι, σφάλμα Σ1 — «κλικ, 4.20, Enter» δεν έβαζε τοίχο
και το Enter τον ακύρωνε. Ιδιοκτήτης 04/11: «μήκος και με πληκτρολόγιο».

Μετά το πρώτο κλικ του τοίχου:

* ψηφία / κόμμα / τελεία γράφουν το **μήκος** (``4`` = 4 m, ``4,20``, ``420 cm``, ``4200 mm`` — ίδιος κανόνας με τις
  διαστάσεις, ``core/units.parse_edit_length``);
* **Tab** περνά στη **γωνία** σε μοίρες (0° = δεξιά, 90° = πάνω· χωρίς γωνία ο τοίχος πάει προς το ποντίκι, με τους
  μαγνήτες 90°/45°/15° που ήδη έχει);
* **Enter** βάζει τον τοίχο με αυτό το μήκος και συνεχίζει από την άκρη του, όπως ένα κλικ· με κενό πεδίο το Enter
  τελειώνει τη σειρά τοίχων όπως πριν;
* **Backspace** σβήνει ένα χαρακτήρα, **Esc** σβήνει ό,τι γράφτηκε (δεύτερο Esc = ακύρωση, όπως πριν).

Ο τοίχος μπαίνει από την ίδια εντολή με το κλικ (``PointerController.pointer_up(..., exact={'length': L})``): ίδια
αναίρεση, ίδιες ενώσεις, ίδια πλευρά (F / Διάστημα).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import Qt

NUMBER_CHARS = set("0123456789.,")
UNIT_CHARS = set("mcMC ")


@dataclass
class TypedEntry:
    length: str = ""
    angle: str = ""
    field: str = "length"            # "length" | "angle"

    def has_text(self):
        return bool(self.length.strip() or self.angle.strip())

    def text(self):
        """What the status bar and the chip next to the mouse show."""
        mark = "▏"
        length = (self.length or "") + (mark if self.field == "length" else "")
        parts = [f"Μήκος {length or '…'}"]
        if self.angle or self.field == "angle":
            parts.append(f"Γωνία {(self.angle or '') + (mark if self.field == 'angle' else '')}°")
        return " · ".join(parts)


def _wall_live(view):
    from archforge.core.interaction import WallDrawTransaction
    ctl = view.controller
    return ctl.tool == "wall" and view._wall_chain_active() and isinstance(ctl.active, WallDrawTransaction)


def entry(view):
    return getattr(view, "_typed", None)


def clear(view):
    view._typed = None


def _say(view, e, extra=""):
    view.statusChanged.emit(
        f"Τοίχος: {e.text()} · Enter = τοίχος · Tab = {'μήκος' if e.field == 'angle' else 'γωνία'}"
        f" · Backspace = διόρθωση · Esc = σβήσιμο{extra}")
    view.viewport().update()


def wants_key(view, event):
    """ShortcutOverride: while a length is being typed, letters of a unit (m, cm, mm) are text, not the window's
    one-letter tools (M = Μετακίνηση)."""
    if not _wall_live(view):
        return False
    if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
        return False
    e = entry(view)
    if e is None or not e.has_text():
        return bool(event.text()) and event.text() in NUMBER_CHARS      # the first digit starts the length
    if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Backspace, Qt.Key.Key_Return, Qt.Key.Key_Enter,
                       Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
        return True                  # Esc clears the typed text first (the window's Esc would cancel the wall)
    t = event.text()
    return bool(t) and (t in NUMBER_CHARS or t in UNIT_CHARS)


def handle_key(view, event):
    """True when the key belonged to the typed length / angle."""
    if not _wall_live(view):
        clear(view)
        return False
    if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
        return False
    e = entry(view)
    key, t = event.key(), event.text()
    if t and t in NUMBER_CHARS:
        e = e or TypedEntry()
        view._typed = e
        setattr(e, e.field, getattr(e, e.field) + t)
        _say(view, e)
        return True
    if e is None:
        return False
    if t and t in UNIT_CHARS and e.field == "length" and e.length:
        e.length += t.lower()
        _say(view, e)
        return True
    if key == Qt.Key.Key_Backspace:
        setattr(e, e.field, getattr(e, e.field)[:-1])
        _say(view, e)
        return True
    if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
        e.field = "angle" if e.field == "length" else "length"
        _say(view, e)
        return True
    if key == Qt.Key.Key_Escape and e.has_text():
        clear(view)
        view.statusChanged.emit("Τοίχος: σβήστηκε ό,τι γράφτηκε · γράψε μήκος ή κλικ στην επόμενη γωνία · Esc = ακύρωση")
        view.viewport().update()
        return True
    if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and e.has_text():
        commit(view)
        return True
    return False


def target(view, e):
    """``(length, (x, y))`` of the wall's end from what was typed, or ValueError with what to do."""
    from archforge.core.units import parse_edit_length
    if not e.length.strip():
        raise ValueError("Τοίχος: γράψε και μήκος (π.χ. 4,20 ή 420 cm) πριν από το Enter")
    length = parse_edit_length(e.length, default="m")
    if length <= 0:
        raise ValueError("Τοίχος: το μήκος πρέπει να είναι πάνω από 0")
    tx = view.controller.active
    sx, sy = tx.start
    if e.angle.strip():
        try:
            a = math.radians(float(e.angle.replace(",", ".")))
        except ValueError:
            raise ValueError("Τοίχος: γράψε τη γωνία σε μοίρες, π.χ. 90") from None
        ux, uy = math.cos(a), math.sin(a)
    else:
        ex, ey = tx.end
        d = math.hypot(ex - sx, ey - sy)
        if d < 1e-9:
            raise ValueError("Τοίχος: κίνησε το ποντίκι προς τα πού πάει ο τοίχος (ή γράψε γωνία με Tab), μετά Enter")
        ux, uy = (ex - sx) / d, (ey - sy) / d
    return length, (sx + ux * length, sy + uy * length)


def commit(view):
    """The wall with the typed length: the same command as a click at its end (one undo, joints, face side)."""
    from archforge.core.viewport import PointerEvent
    e = entry(view)
    ctl = view.controller
    try:
        length, (x, y) = target(view, e)
    except ValueError as exc:
        view.statusChanged.emit(str(exc))
        return None
    z = float(getattr(ctl.active, "z", 0.0))
    a, b = view.doc.work_plane.project((x, y, z))
    # Shift + Ctrl: no snap, no angle magnet, no corner pull — the end is exactly where the numbers say.
    ev = PointerEvent(a, b, shift=True, ctrl=True)
    clear(view)
    try:
        result = ctl.pointer_up(ev, exact={"length": length})
    except ValueError as exc:
        view.statusChanged.emit(str(exc))
        view.redraw()
        return None
    from archforge.core.units import fmt_length, suffix
    said = f"Τοίχος {fmt_length(length)} {suffix()} μπήκε"
    if getattr(ctl, "last_warning", None):
        view.statusChanged.emit(ctl.last_warning)
    elif view._wall_chain_active():
        view.statusChanged.emit(said + " · γράψε το επόμενο μήκος ή κλικ στην επόμενη γωνία · Enter = τέλος · Ctrl+Z = αναίρεση")
    else:
        view.to_select(said + " · το περίγραμμα έκλεισε · Επιλογή · Ctrl+Z = αναίρεση του τελευταίου τοίχου")
    view.redraw()
    return getattr(result, "entity_id", None)
