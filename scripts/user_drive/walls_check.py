"""Walls checked with the mouse, the way the owner drew them on 24/10 (screenshots in the chat):

* a wall drawn by its face stays where its preview showed it («ο τοίχος μετατοπίζεται» on the click);
* three walls by eye, the fourth down at 90° onto the first: the outline closes square, no slanted wall;
* a wall drawn far from a finished room, in line with it: the guide shows, nothing else moves
  («συμπεριφέρεται εντελώς παράλογα μετακινώντας τοίχους για να κλείσουν»);
* the free end of a short wall dragged to make it longer: it grows along its own line.

    QT_QPA_PLATFORM=offscreen python scripts/user_drive/walls_check.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.insert(0, os.path.dirname(__file__)); from user import *
from PySide6.QtTest import QTest
from archforge.core.model import Entity
from archforge.core.commands import AddEntity

u = U(); auto_dialogs(u)
# The owner's project: details answered, outside measures (the wall tool draws by the outer face).
u.w.stack.execute(AddEntity(Entity('project_brief', {'project_type': 'new', 'wall_system': 'brick_double_insulated',
                                                      'interior_walls': 'brick_plaster', 'measure': 'exterior'})))
u.see(3, 5)
vp = u.plan.viewport()
fails = []

def move(x, y):
    QTest.mouseMove(vp, u._pos(x, y)); u.pump()

def hand_click(x, y):
    move(x - 0.3, y + 0.3); move(x, y); u.click(x, y)

def walls():
    return {e.id: tuple(round(float(e.params[k]), 3) for k in ('x1', 'y1', 'x2', 'y2')) for e in u.w.doc.entities.values() if e.kind == 'wall'}

def check(ok, text):
    print(('  ✔ ' if ok else '  ✘ ') + text)
    if not ok: fails.append(text)

# 1. A room drawn by eye by its outer faces; the fourth wall down at 90° onto the first.
u.begin('1 · Δωμάτιο με το μάτι, ο 4ος τοίχος κάτω στις 90° και κλικ στον πρώτο')
u.toolbar('Τοίχος')
for p in [(7.2, 5.0), (0.0, 5.0), (0.0, 8.6), (7.8, 8.6)]:
    hand_click(*p)
move(7.8, 6.0); move(7.25, 4.95)
pv = u.plan.controller.preview
check(bool(pv.geometry.get('guide')), 'οδηγός (διακεκομμένη) προς τον πρώτο τοίχο')
u.shot('walls_1_guide')
u.click(7.25, 4.95)
W = walls()
xs = sorted({round(v, 3) for w in W.values() for v in (w[0], w[2])})
ys = sorted({round(v, 3) for w in W.values() for v in (w[1], w[3])})
check(len(W) == 4 and len(xs) == 2 and len(ys) == 2, f'4 τοίχοι, ορθογώνιο (x {xs}, y {ys})')
check(u.plan.controller.tool == 'select', f'μετά το κλείσιμο: Επιλογή (εργαλείο {u.plan.controller.tool})')
check(len(u.w.doc.active_room_faces()) == 1, 'ένας κλειστός χώρος')
u.end(); u.shot('walls_1_room')
room = dict(W)

# 2. A lone wall drawn by its face: the click keeps it where its preview was.
u.begin('2 · Μεμονωμένος τοίχος: εκεί που τον έδειξε η προεπισκόπηση')
u.toolbar('Τοίχος')
hand_click(8.1, 10.2); move(9.5, 10.25); move(10.3, 10.2)
from archforge.core.plan_scene import preview_primitives
pv = u.plan.controller.preview
body = next(p for p in preview_primitives(pv) if p.kind == 'polygon')
ys_preview = sorted({round(q[1], 3) for q in body.points})
u.shot('walls_2_preview')
u.click(10.3, 10.2); u.key(Qt.Key.Key_Escape); u.key(Qt.Key.Key_Escape)
lone = next(e for e in u.w.doc.entities.values() if e.kind == 'wall' and e.id not in room)
t = float(lone.params['thickness']); y = float(lone.params['y1'])
check([round(y - t / 2, 3), round(y + t / 2, 3)] == ys_preview, f'προεπισκόπηση {ys_preview} = τοίχος {[round(y - t / 2, 3), round(y + t / 2, 3)]}')
check(all(walls()[k] == v for k, v in room.items()), 'το δωμάτιο δεν άλλαξε')
u.end()

# 3. Far from the room, in line with its top: the guide, and nothing else moves.
u.begin('3 · Τοίχος μακριά, στην ευθεία του δωματίου: δεν μετακινείται τίποτα')
before = walls()
u.toolbar('Τοίχος')
hand_click(9.6, 7.0); move(9.6, 8.0); move(9.6, 8.5)
pv = u.plan.controller.preview
print('  οδηγός:', pv.geometry.get('guide'))
u.shot('walls_3_guide')
u.click(9.6, 8.5); u.key(Qt.Key.Key_Escape); u.key(Qt.Key.Key_Escape)
after = walls()
check(all(after.get(k) == v for k, v in before.items()), 'κανένας άλλος τοίχος δεν άλλαξε')
check(len(after) == len(before) + 1, f'ένας νέος τοίχος ({len(after) - len(before)})')
u.end(); u.shot('walls_3_after')

# 4. A short wall at the room's corner, its free end dragged to make it longer.
u.begin('4 · Μικρός τοίχος στη γωνία: σύρσιμο της ελεύθερης άκρης για να μακρύνει')
u.toolbar('Τοίχος')
corner = next(((w[2], w[3]) for w in room.values() if w[2] == max(xs) and w[3] == min(ys)), (max(xs), min(ys)))
hand_click(*corner)
check(u.plan.controller.wall_chain is not None, 'το 1ο κλικ στη γωνία ξεκινά τοίχο (δεν φτιάχνει μικρό τοίχο)')
move(corner[0] - 0.28, corner[1] - 0.4); move(corner[0] + 0.02, corner[1] - 0.7)
_c = u.plan.controller
print('  πριν το κλικ: αρχή', _c.active.start if _c.active else None, 'άκρη', [round(v, 3) for v in _c.active.end] if _c.active else None,
      'έλξη', _c.preview.snap and _c.preview.snap['kind'])
u.click(corner[0] + 0.02, corner[1] - 0.7)
u.key(Qt.Key.Key_Escape); u.key(Qt.Key.Key_Escape)
stub_id = next(k for k in walls() if k not in after)
s = walls()[stub_id]
free = (s[2], s[3])
u.dbl((s[0] + s[2]) / 2, (s[1] + s[3]) / 2)
u.drag(free[0], free[1], free[0] + 0.2, free[1] - 1.5)
s2 = walls()[stub_id]
import math
a1 = math.degrees(math.atan2(s[3] - s[1], s[2] - s[0])); a2 = math.degrees(math.atan2(s2[3] - s2[1], s2[2] - s2[0]))
L1 = math.dist(s[:2], s[2:]); L2 = math.dist(s2[:2], s2[2:])
check(abs(a1 - a2) < 0.5 and L2 > L1 + 1.0, f'μάκρυνε στην ευθεία του: {L1:.2f} → {L2:.2f} m, γωνία {a1:.1f}° → {a2:.1f}°')
check(u.plan.controller.tool == 'select', f'μετά το σύρσιμο: Επιλογή ({u.plan.controller.tool})')
print('  γραμμή κατάστασης:', u.status())
u.end(); u.shot('walls_4_stretch')

# 5. (α) The room's exterior dimensions came by themselves when it closed.
u.begin('5 · Αυτόματες εξωτερικές διαστάσεις στο κλείσιμο (α)')
from archforge.architecture import dimensions as D
z = float(u.w.doc.work_plane.origin[2])
s_dims = D.settings(u.w.doc, z)
check(s_dims is not None and int(s_dims.params.get('exterior', 0)) == 1, 'εξωτερικές διαστάσεις ανοιχτές χωρίς μενού')
chains = D.exterior(u.w.doc, z)
check(len(chains) > 0, f'αλυσίδες εξωτερικών διαστάσεων: {len(chains)}')
u.end(); u.shot('walls_5_auto_dims')

# 6. (γ) One click selects a wall; pressing and dragging another one moves it at once. (β) One click on its
# distance types it.
u.begin('6 · Κλικ = επιλογή, σύρσιμο = μεταφορά (γ) · κλικ στη διάσταση = πληκτρολόγηση (β)')
u.key(Qt.Key.Key_Escape)
u.toolbar('Επιλογή')
far = next(e for e in u.w.doc.entities.values() if e.kind == 'wall' and e.id not in room and abs(float(e.params['x1']) - 9.6) < 0.3 and abs(float(e.params['x1']) - float(e.params['x2'])) < 1e-6)
fx = float(far.params['x1']); fy = (float(far.params['y1']) + float(far.params['y2'])) / 2
u.w.doc.select([]); u.plan.redraw(); u.pump()
u.click(fx, fy)
check(u.w.doc.selection == [far.id], 'ένα κλικ επέλεξε τον τοίχο')
u.w.doc.select([]); u.plan.redraw(); u.pump()
u.drag(fx, fy, fx + 0.6, fy)
x_after = float(u.w.doc.get(far.id).params['x1'])
check(abs(x_after - (fx + 0.6)) < 0.06, f'σύρθηκε χωρίς να επιλεγεί πρώτα: x {fx:.2f} → {x_after:.2f}')
u.w.doc.select([far.id]); u.plan.redraw(); u.pump()
labels = [(i, side) for i, side in u.w._wall_dims._labels if side is not None]
if labels:
    item, side = labels[0]
    u.answers.append(1.50)
    pos = u.plan.mapFromScene(item.pos()); pos.setX(pos.x() + 12); pos.setY(pos.y() + 8)
    before = float(u.w.doc.get(far.id).params['x1'])
    QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos); u.pump()
    from archforge.architecture.wall_dims import wall_dims
    clears = [round(x['clear'], 2) for x in wall_dims(u.w.doc, far.id)['sides']]
    check(1.5 in clears, f'ένα κλικ στη διάσταση → 1,50 m (καθαρές: {clears})')
else:
    check(False, 'ο επιλεγμένος τοίχος δεν δείχνει αποστάσεις')
u.end(); u.shot('walls_6_click_drag')

# 7. (δ) The side never changes by itself: drawn anticlockwise the walls lie outside the lines; Space turns them.
u.begin('7 · Πλευρά σώματος σταθερή, Διάστημα = άλλη πλευρά (δ)')
u.see(3, -6)
u.toolbar('Τοίχος')
hand_click(0, -8)
move(3, -8)
side0 = u.plan.controller.active.face_side
QTest.keyClick(vp, Qt.Key.Key_Space); u.pump()
side1 = u.plan.controller.active.face_side
check(side0 == -1 and side1 == 1, f'δεξιά (μέσα όταν σχεδιάζεις δεξιόστροφα) → Διάστημα → αριστερά ({side0} → {side1})')
u.key(Qt.Key.Key_Escape); u.key(Qt.Key.Key_Escape)
u.end()

# 8. Steps of 10–20 cm (owner 24/10: «δεν είναι όλα σε μία ευθεία»): zoomed in, the magnets pull only a few cm; Ctrl
# turns them off at any zoom.
u.begin('8 · Τοίχος 15 cm δίπλα στην ευθεία του δωματίου: με ζουμ μένει εκεί, με Ctrl σε κάθε ζουμ')
from PySide6.QtCore import QRectF
right_x = max(xs) + 0.135                                  # the room's right outer face (drawn line)
top_y = max(ys) + 0.135
u.plan.fitInView(QRectF(right_x - 1.0, top_y - 2.5, 3.0, 3.0)); u.pump(); u.plan._sync_snap_tolerance()
print('  ανοχή έλξης με ζουμ:', round(u.plan.controller.snap_tolerance, 3), 'm')
u.toolbar('Τοίχος')
hand_click(right_x + 0.15, top_y + 0.4)
move(right_x + 0.15, top_y - 0.6); move(right_x + 0.15, top_y - 1.2)
_c = u.plan.controller
ex = _c.active.end[0] if _c.active else None
check(ex is not None and abs(ex - (right_x + 0.15)) < 0.005, f'με ζουμ: η γραμμή μένει 15 cm έξω ({ex and round(ex, 3)} vs {round(right_x + 0.15, 3)})')
u.key(Qt.Key.Key_Escape); u.key(Qt.Key.Key_Escape)
u.see(3, 5); u.plan.resetTransform(); u.plan.scale(55.0, -55.0); u.see(3, 5); u.pump(); u.plan._sync_snap_tolerance()
print('  ανοχή έλξης από μακριά:', round(u.plan.controller.snap_tolerance, 3), 'm')
u.toolbar('Τοίχος')
hand_click(right_x + 0.15, top_y + 0.4)
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QEvent
for yy in (top_y - 0.6, top_y - 1.2):
    _p = QPointF(u._pos(right_x + 0.15, yy))
    QApplication.sendEvent(vp, QMouseEvent(QEvent.Type.MouseMove, _p, vp.mapToGlobal(_p), Qt.MouseButton.NoButton,
                                           Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier)); u.pump()
ex = _c.active.end[0] if _c.active else None
check(ex is not None and abs(ex - (right_x + 0.15)) < 0.02, f'από μακριά με Ctrl: μένει 15 cm έξω ({ex and round(ex, 3)})')
u.key(Qt.Key.Key_Escape); u.key(Qt.Key.Key_Escape)
u.end()

print('--- ΑΠΟΤΕΛΕΣΜΑ:', 'όλα σωστά' if not fails else f'{len(fails)} λάθη')
for f in fails: print('  ✘', f)
