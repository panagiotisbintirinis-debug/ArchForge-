"""Walls by their face and a later wall type — the owner's way (29/10, from the ArchiCAD 29 tutorial):

«ορίζεις εξωτερικά ή εσωτερικά μέτρα, σχεδιάζεις με λεπτή γραμμή, όταν ολοκληρωθεί του δίνεις τον τύπο, το σχέδιο
προσαρμόζεται χωρίς να αλλάξουν οι διαστάσεις» · «από τον άξονα είναι τελείως λάθος, ειδικά αν ο τοίχος είναι 50 εκ.»

1. A new project without project details: a 10 × 8 outline clicked a few pixels off its corners, closed on the first.
   The outline the hand drew must be the outer faces (not the axes).
2. Every wall gets «Πετροκτιστός 54 cm» from the Properties, one by one, as a person does: the outer size stays
   10,00 × 8,00 and the corners stay closed.
3. Ctrl+Z brings the walls back.

    QT_QPA_PLATFORM=offscreen QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu" \\
        python scripts/user_drive/wall_face_check.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.insert(0, os.path.dirname(__file__))
from user import *                                    # noqa: E402,F403
from PySide6.QtTest import QTest                      # noqa: E402
from PySide6.QtWidgets import QComboBox               # noqa: E402

CORNERS = [(0.0, 0.0), (0.0, 8.0), (10.0, 8.0), (10.0, 0.0)]          # clockwise; run(reverse=True): the other way
TYPE = 'stone_uninsulated'                            # «Πετροκτιστός 54 cm»


def outer_box(doc):
    """Outer size of the walls' cut region (wall_poche): what a dimension of the outline measures."""
    from archforge.core.plan_scene import wall_poche
    pts = [q for outer, _holes in wall_poche(doc) for q in outer]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), round(max(ys), 3)


def run(reverse=False):
    """``reverse``: the outline the other way round — the same room must come out (owner 29/10)."""
    corners = CORNERS[::-1] if reverse else CORNERS
    u = U(); auto_dialogs(u)
    fails = []

    def check(ok, text):
        print(('  ✔ ' if ok else '  ✘ ') + text)
        if not ok:
            fails.append(text)
    vp = u.plan.viewport()

    def move(x, y):
        QTest.mouseMove(vp, u._pos(x, y)); u.pump()

    def hand_click(x, y):
        # A hand, not a coordinate: arrive from the side and click 3 px off the corner.
        p = u._pos(x, y)
        move(x - 0.4, y + 0.4)
        QTest.mouseMove(vp, p + QPoint(3, -2)); u.pump()
        u.steps += 1; QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p + QPoint(3, -2)); u.pump()

    u.see(5, 4)
    u.begin('1 · Περίγραμμα 10 × 8 με κλικ δίπλα στις γωνίες, κλείσιμο στο πρώτο')
    u.toolbar('Τοίχος')
    for p in corners + [corners[0]]:
        hand_click(*p)
    u.key(Qt.Key.Key_Escape); u.key(Qt.Key.Key_Escape)
    walls = [e for e in u.w.doc.entities.values() if e.kind == 'wall']
    for e in walls:
        print('   ', e.name, [round(float(e.params[k]), 3) for k in ('x1', 'y1', 'x2', 'y2')], 't', e.params['thickness'])
    print('    εργαλείο', u.plan.controller.tool, '· κατάσταση:', u.status())
    box = outer_box(u.w.doc)
    check(len(walls) == 4, f'4 τοίχοι ({len(walls)})')
    check(len(u.w.doc.active_room_faces()) == 1, 'ένας κλειστός χώρος')
    w0, h0 = box[2] - box[0], box[3] - box[1]
    # The hand clicked within ~6 cm of the corners, onto the 10 cm grid: the outer faces lie there, within one grid
    # step (on the axis the outline would grow by the wall's thickness on every side).
    check(max(abs(box[0]), abs(box[1]), abs(box[2] - 10.0), abs(box[3] - 8.0)) <= 0.105,
          f'το περίγραμμα που σχεδίασε το χέρι είναι οι εξωτερικές παρειές: {box}')
    u.end()

    u.begin('2 · Τύπος «Πετροκτιστός 54 cm» σε κάθε τοίχο από τις Ιδιότητες')
    for wall in walls:
        a = (float(wall.params['x1']), float(wall.params['y1'])); b = (float(wall.params['x2']), float(wall.params['y2']))
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        u.plan.controller.set_tool('select')
        u.steps += 1
        QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, u._pos(*mid) + QPoint(2, 2)); u.pump()
        if u.w.doc.selection != [wall.id]:
            check(False, f'κλικ στον τοίχο {wall.name}: επιλογή {u.w.doc.selection}')
            continue
        combo = next((c for c in u.w.inspector.findChildren(QComboBox) if c.findData(TYPE) >= 0), None)
        if combo is None:
            check(False, 'Ιδιότητες: «Τύπος τοίχου»'); continue
        u.steps += 2; combo.setCurrentIndex(combo.findData(TYPE)); u.pump()
    thick = {round(float(u.w.doc.get(w.id).params['thickness']), 3) for w in walls}
    check(thick == {0.54}, f'πάχος {thick}')
    box2 = outer_box(u.w.doc)
    w1, h1 = box2[2] - box2[0], box2[3] - box2[1]
    check(abs(w1 - w0) <= 0.01 and abs(h1 - h0) <= 0.01, f'οι εξωτερικές διαστάσεις δεν άλλαξαν: {w0:.2f} × {h0:.2f} → {w1:.2f} × {h1:.2f}')
    check(len(u.w.doc.active_room_faces()) == 1, 'οι γωνίες έμειναν κλειστές (ένας χώρος)')
    u.end()

    u.begin('3 · Ctrl+Z')
    for _ in walls:
        u.steps += 1; QTest.keyClick(vp, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier); u.pump()
    check(outer_box(u.w.doc) == box, 'Ctrl+Z: οι τοίχοι όπως σχεδιάστηκαν')
    u.end()
    u.w._mark_clean(); u.w.close()
    print('ΑΠΟΤΕΛΕΣΜΑ:', 'όλα σωστά' if not fails else f'{len(fails)} προβλήματα')
    return fails


if __name__ == '__main__':
    sys.exit(1 if run() or run(reverse=True) else 0)
