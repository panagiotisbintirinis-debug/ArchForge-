"""The core, checked with the mouse the way the owner draws (23/10: «τα εργαλεία συνεχίζουν να δουλεύουν… οι τοίχοι δεν
δένουν… σχεδιάζονται με μια μεσοκάθετο μέσα στο πάχος… αφαιρώντας μικρό τοίχο ο διπλανός άλλαξε γωνία»).

    QT_QPA_PLATFORM=offscreen python scripts/user_drive/core_check.py
Clicks land a few centimetres off the corners, as a hand does; the mouse moves before every click.
"""
import sys, os, math
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.insert(0, os.path.dirname(__file__)); from user import *
from PySide6.QtTest import QTest
u = U(); auto_dialogs(u); u.see(4, 3)
vp = u.plan.viewport()

def move(x, y):
    QTest.mouseMove(vp, u._pos(x, y)); u.pump()

def hand_click(x, y):
    move(x - 0.3, y - 0.2); move(x, y); u.click(x, y)

def walls():
    return {e.id: e.params for e in u.w.doc.entities.values() if e.kind == 'wall'}

def ends(p):
    return (round(p['x1'], 3), round(p['y1'], 3)), (round(p['x2'], 3), round(p['y2'], 3))

# 1. A room drawn by hand: corners a few cm off, closing near the first corner.
u.begin('1 · Δωμάτιο 6×5 με το χέρι (κλικ λίγο δίπλα στις γωνίες), κλείσιμο κοντά στην αρχή')
u.toolbar('Τοίχος')
for p in [(0, 0), (6.03, 0.02), (5.98, 5.03), (0.02, 4.97), (0.04, 0.03)]:
    hand_click(*p)
W = walls()
print('  τοίχοι', len(W), [ends(p) for p in W.values()])
print('  εργαλείο μετά το κλείσιμο:', u.plan.controller.tool, '| χώροι', len(u.w.doc.active_room_faces()))
if u.plan.controller.tool != 'select': u.note(f'μετά το κλείσιμο του περιγράμματος το εργαλείο μένει «{u.plan.controller.tool}»')
corners = {}
for p in W.values():
    for q in ends(p): corners.setdefault(q, 0); corners[q] += 1
loose = [q for q, n in corners.items() if n < 2]
if loose: u.note(f'άκρα που δεν δένουν με άλλο τοίχο: {loose}')
from archforge.core.plan_scene import wall_poche
isl = wall_poche(u.w.doc)
print('  poche: νησιά', len(isl), 'τρύπες', [len(h) for _, h in isl], 'κορυφές εξωτ.', [len(o) for o, _ in isl])
u.end()
u.shot('core_room')

# 2. The wall as drawn in the plan: is the axis line visible inside the wall body?
from archforge.core.plan_scene import build_plan_frame
fr = build_plan_frame(u.w.doc)
axis = [p for p in fr.primitives if p.kind == 'line' and p.entity_id in W]
print('  2 · γραμμές άξονα τοίχων στην κάτοψη:', len(axis))
if axis: u.note('κάθε τοίχος έχει και τη γραμμή του άξονα ορατή μέσα στο πάχος του')
# while drawing: what does the preview show?
u.begin('2β · Προεπισκόπηση τοίχου όσο σχεδιάζεις')
u.toolbar('Τοίχος')
hand_click(8, 0); move(10, 0.5); move(11, 0)
pv = u.plan.controller.preview
print('  προεπισκόπηση:', pv.kind if pv else None, sorted((pv.geometry or {}).keys())[:12] if pv else None)
from archforge.core.plan_scene import preview_primitives
pp = preview_primitives(pv) if pv else []
print('  σχήματα προεπισκόπησης:', [(p.kind, len(p.points)) for p in pp][:6])
u.shot('core_wall_preview')
u.key(Qt.Key.Key_Escape); u.key(Qt.Key.Key_Escape)
print('  εργαλείο μετά από 2 Esc:', u.plan.controller.tool)
u.end()

# 3. A door: does the tool stop after it?
u.begin('3 · Πόρτα (δεξί κλικ ▸ Κουφώματα ▸ Πόρτα) και μετά;')
u.mm(3, -2, 'mm:tool:door')
hand_click(3, 0)
print('  πόρτες', u.kinds().get('door', 0), '| εργαλείο μετά:', u.plan.controller.tool)
if u.plan.controller.tool != 'select': u.note(f'μετά την πόρτα το εργαλείο μένει «{u.plan.controller.tool}»')
u.key(Qt.Key.Key_Escape)
u.end()

# 4. A short wall in a chain, deleted with the mouse menu: do its neighbours keep their angle?
u.begin('4 · Αλυσίδα με μικρό τοίχο (σκαλοπάτι 60 cm), διαγραφή του με δεξί κλικ ▸ Διαγραφή')
u.toolbar('Τοίχος')
for p in [(0, 8), (4, 8), (4.02, 8.6), (8, 8.6)]:
    hand_click(*p)
u.key(Qt.Key.Key_Escape); u.key(Qt.Key.Key_Escape)
W = walls()
short = min(W, key=lambda k: math.dist((W[k]['x1'], W[k]['y1']), (W[k]['x2'], W[k]['y2'])))
others = {k: ends(p) for k, p in W.items() if k != short and p['y1'] > 7}
print('  μικρός τοίχος', ends(W[short]), '| γείτονες πριν', list(others.values()))
sx, sy = (W[short]['x1'] + W[short]['x2']) / 2, (W[short]['y1'] + W[short]['y2']) / 2
try:
    u.mm(sx, sy, 'delete')
except LookupError as exc:
    print('  ', exc)
W2 = walls()
after = {k: ends(W2[k]) for k in others if k in W2}
print('  διαγράφηκε:', short not in W2, '| γείτονες μετά', list(after.values()))
for k in others:
    if k in W2 and after[k] != others[k]:
        u.note(f'ο γειτονικός τοίχος άλλαξε: {others[k]} → {after[k]}')
u.end()
u.shot('core_delete')
print('--- ΤΡΙΒΕΣ:'); [print('  •', t, '—', n) for t, n in u.notes]
