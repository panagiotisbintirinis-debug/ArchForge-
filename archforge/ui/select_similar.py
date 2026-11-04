"""Επεξεργασία › «Επιλογή όμοιων» και «Επιλογή εξωτερικών τοίχων» (κριτική v5, k3).

Οι κριτές μέτρησαν 48–69 βήματα για να πάρουν τύπο 16–23 εξωτερικοί τοίχοι, γιατί κάθε τοίχος επιλεγόταν χωριστά.

* **Επιλογή όμοιων:** από το επιλεγμένο, όλα του ίδιου είδους και τύπου σε όλο το έργο — τοίχοι: ίδιος τύπος και
  πάχος· πόρτες / παράθυρα: ίδιο πλάτος × ύψος· τα άλλα: ίδιο είδος.
* **Επιλογή εξωτερικών τοίχων:** όλων των ορόφων, με τον ίδιο κανόνα που χρησιμοποιεί η θέρμανση
  (``mep/ventilation.exterior_walls``).

Η επιλογή δεν αλλάζει το έργο (καμία αναίρεση)· μετά οι Ιδιότητες αλλάζουν όλα τα επιλεγμένα μαζί.
"""
from __future__ import annotations


def _key(e):
    p = e.params
    if e.kind == "wall":
        return ("wall", str(p.get("wall_type") or "generic"), round(float(p.get("thickness", 0.0)), 4))
    if e.kind in ("door", "window", "opening"):
        return (e.kind, round(float(p.get("width", 0.0)), 3), round(float(p.get("height", 0.0)), 3))
    return (e.kind,)


def similar_ids(doc, ids):
    """Everything like the given objects (see the module doc), visible ones only, in the order of the project."""
    keys = {_key(doc.get(i)) for i in ids if i in doc.entities}
    return [e.id for e in doc.entities.values() if e.visible and _key(e) in keys]


def exterior_wall_ids(doc):
    from archforge.mep.ventilation import exterior_walls
    zs = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall" and e.visible})
    out = []
    for z in zs:
        try:
            out += [w.id for w, _n in exterior_walls(doc, z)]
        except Exception as exc:                # noqa: BLE001 — say it, keep the storeys that worked
            from archforge.core.notices import not_computed
            not_computed("select.exterior", f"Επιλογή εξωτερικών: δεν βρέθηκαν οι εξωτερικοί τοίχοι του ορόφου {z:+.2f}", exc=exc)
    return list(dict.fromkeys(out))


def _apply(window, ids, said):
    window.doc.select(ids)
    window._redraw_views(all_views=True)
    window.refresh_inspector()
    window.statusBar().showMessage(said, 8000)


def select_similar(window):
    chosen = list(getattr(window.doc, "selection", []) or [])
    if not chosen:
        window.statusBar().showMessage("Επιλογή όμοιων: επίλεξε πρώτα ένα στοιχείο — παίρνει το είδος και τον τύπο του.", 8000)
        return []
    ids = similar_ids(window.doc, chosen)
    from archforge.ui.indication import describe
    _apply(window, ids, f"Επιλέχθηκαν {len(ids)} όμοια με «{describe(window.doc, chosen[0]).split(' · ')[0]}» · "
                        "οι Ιδιότητες αλλάζουν όλα μαζί")
    return ids


def select_exterior(window):
    ids = exterior_wall_ids(window.doc)
    if not ids:
        window.statusBar().showMessage("Επιλογή εξωτερικών τοίχων: δεν βρέθηκε κλειστό περίγραμμα τοίχων.", 8000)
        return []
    _apply(window, ids, f"Επιλέχθηκαν {len(ids)} εξωτερικοί τοίχοι (όλοι οι όροφοι) · οι Ιδιότητες αλλάζουν όλους μαζί")
    return ids


def install(window):
    from PySide6.QtGui import QAction
    similar = QAction("Επιλογή όμοιων (ίδιο είδος και τύπος)", window)
    similar.setToolTip("Από το επιλεγμένο: όλα του ίδιου είδους και τύπου σε όλο το έργο")
    similar.triggered.connect(lambda _=False: select_similar(window))
    exterior = QAction("Επιλογή εξωτερικών τοίχων", window)
    exterior.setToolTip("Όλοι οι εξωτερικοί τοίχοι, όλων των ορόφων")
    exterior.triggered.connect(lambda _=False: select_exterior(window))
    window._select_actions = [similar, exterior]
    window._main_actions.extend(window._select_actions)
    return window._select_actions
