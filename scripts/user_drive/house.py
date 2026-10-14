import sys; sys.path.insert(0, __import__('os').path.abspath(__import__('os').path.join(__import__('os').path.dirname(__file__), '..', '..')))
sys.path.insert(0, __import__('os').path.dirname(__file__)); from user import *
u = U(); auto_dialogs(u)
STOP = sys.argv[1] if len(sys.argv) > 1 else None
def menus():
    """Open the mouse menu where a person would and photograph it (judge noise / usefulness)."""
    from PySide6.QtCore import QRect
    def snap(x, y, name, more=False):
        m = u.right(x, y)
        if m is None: print('  (κανένα μενού)', name); return
        r = m.geometry()
        if more and getattr(m, 'more_button', None) is not None:
            m.more_button.showMenu() if False else None
        img = u.plan.viewport().grab(r.adjusted(-20, -20, 20, 20)); img.save(os.path.join(OUT, f'menu_{name}.png'))
        if more and getattr(m, 'more_button', None) is not None:
            pop = m.more_button.menu(); pop.popup(m.more_button.mapToGlobal(m.more_button.rect().bottomLeft())); u.pump()
            pop.grab().save(os.path.join(OUT, f'menu_{name}_more.png')); pop.hide()
        c = u.mm_content(x, y); print(f'  μενού {name}: κέντρο «{c["center"]}» · κύκλος {len(c["radial"])} · κουμπιά {len(c["inline"])} · «Περισσότερα» {len(c["more"])}')
        u.plan.hide_marking_menu()
    snap(3, -3, 'empty', more=True)
    snap(5, 2, 'wall')
    from PySide6.QtCore import QPointF as _P
    v = u.plan; print('  στο (3,0):', [(type(i).__name__, i.path().elementCount() if hasattr(i,'path') else 0, [round(c,2) for c in i.boundingRect().getCoords()], u.w.doc.get(v._entity_items[i]).kind if v._entity_items.get(i) in u.w.doc.entities else None, i.zValue()) for i in v.items(v.mapFromScene(_P(3, 0)))][:5])
    snap(3, 0.0, 'room_edge')
    snap(2.5, 2, 'room')
    snap(5, -1.5, 'balcony_railing')
    snap(5, -0.8, 'balcony_slab', more=True)
    u.toolbar('Τοίχος'); snap(3, -3, 'wall_tool'); u.key(Qt.Key.Key_Escape); u.mm(3, -3, 'mm:tool:select')
def stage(name):
    if STOP and name == STOP:
        u.shot('stop'); menus(); report(); sys.exit(0)
def report():
    print('--- σύνολο βημάτων:', sum(s for _, s in u.log)); print('kinds', dict(u.kinds()))
u.see(5, 4)
u.begin('Ισόγειο: εξωτερικοί τοίχοι 10×8')
u.toolbar('Τοίχος')
for p in [(0,0),(10,0),(10,8),(0,8),(0,0)]: u.click(*p)
u.end()
u.begin('Ισόγειο: 3 εσωτερικοί τοίχοι')
u.click(6,0); u.dbl(6,8); u.click(6,3); u.dbl(10,3); u.click(6,5.5); u.dbl(10,5.5)
u.end()
stage('doors')
u.begin('Ισόγειο: τέλος τοίχων → Πόρτα (μενού ποντικιού)')
u.mm(3,-1,'mm:tool:select'); print('  menu now', u.mm_content(3,-1)); u.mm(3,-1,'mm:tool:door'); print('  tool', u.plan.controller.tool)
u.end()
u.begin('Ισόγειο: 4 πόρτες (είσοδος, μπάνιο, χολ, δωμάτιο)')
for p in [(3,0),(6,1.5),(6,4.2),(6,6.8)]:
    n=u.kinds()['door']; u.click(*p)
    if u.kinds()['door']==n: u.note(f'πόρτα στο {p} δεν μπήκε: {u.status()}')
u.end()
u.begin('Ισόγειο: 5 παράθυρα')
u.mm(3,-1,'mm:tool:window')
for p in [(0,2),(0,6),(3,8),(10,1.5),(10,6.8)]:
    n=u.kinds()['window']; u.click(*p)
    if u.kinds()['window']==n: u.note(f'παράθυρο στο {p} δεν μπήκε: {u.status()}')
u.end()
u.shot('ground')
stage('kitchen')
u.begin('Κουζίνα στο σαλόνι (Κουζίνα εδώ…)')
u.mm(1.5,6.5,'mm:layout:kitchen')
a=u.w._layout_assist
print('  status:', u.status(), '| proposal', a.proposal is not None, '| room', a.room is not None)
u.mm(1.5,6.5,'mm:layout:shape_L'); print('  L:', u.status())
u.mm(1.5,6.5,'mm:layout:apply'); print('  apply:', u.status(), dict(u.kinds()))
u.end()
u.begin('Μπάνιο ισογείου (Μπάνιο εδώ…)')
u.mm(8,1.5,'mm:layout:bath'); print('  ', u.status())
print('  menu:', u.mm_content(8,1.5))
u.mm(8,1.5,'mm:layout:apply'); print('  apply:', u.status(), dict(u.kinds()))
u.end()
u.shot('ground2')
stage('floors')
u.begin('Νέος όροφος (+ Όροφος, προεπιλογή ύψους)')
u.toolbar('Όροφος')
print('  levels', u.w.doc.levels, 'wp z', u.w.doc.work_plane.origin[2], '|', u.status())
u.end()
u.shot('floor1_empty')
stage('floor1')
u.begin('1ος: εξωτερικοί τοίχοι πάνω στο αχνό ισόγειο')
u.toolbar('Τοίχος')
for p in [(0,0),(10,0),(10,8),(0,8),(0,0)]: u.click(*p)
z=u.w.doc.work_plane.origin[2]
up=[e.params for e in u.w.doc.entities.values() if e.kind=='wall' and abs(e.params['z']-z)<1e-6]
print('  walls on floor', len(up), 'corners', sorted({(round(w['x1'],3),round(w['y1'],3)) for w in up}))
u.end()
u.begin('1ος: 3 εσωτερικοί (3 υπνοδωμάτια + μπάνιο)')
u.click(5,0); u.dbl(5,8); u.click(5,4); u.dbl(10,4); u.click(0,4); u.dbl(5,4)
u.mm(3,-3,'mm:tool:select')
print('  rooms', len(u.w.doc.active_room_faces(z=z)))
u.end()
stage('balcony')
u.begin('1ος: μπαλκόνι στη νότια πλευρά (μενού ποντικιού → Μπαλκόνι, σύρσιμο)')
u.mm(3,-3,'mm:slab:balcony'); u.drag(1,0,9,-1.5)
print('  ', u.status(), dict(u.kinds()))
u.end()
u.shot('floor1')
stage('stair')
u.begin('Ισόγειο: σκάλα στο χολ (όροφος ← επιλογέας, δεξί κλικ → Σκάλα ▸ → Σκάλα, σύρσιμο)')
u.floor('Ground'); u.see(5, 4)
u.mm(3, -3, 'mm:menu:stair'); print('  υπομενού:', u.mm_content(3, -3) if u.plan._marking_menu is None else None)
m = u.plan._marking_menu; print('  ανοιχτό:', m.menu['center'] if m else None, [e['id'] for e in m.menu['entries']] if m else None)
u.steps += 1; m.buttons['mm:tool:stair'].click(); u.pump()
print('  tool', u.plan.controller.tool, '|', u.status())
vp = u.plan.viewport(); a = u._pos(6.6, 4.25)
QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a); u.pump()
for i, (x, y) in enumerate([(7.5, 4.25), (8.5, 4.25), (9.6, 4.25)]):
    QTest.mouseMove(vp, u._pos(x, y)); u.pump()
    pv = u.plan.controller.preview
    ch = (pv.geometry or {}).get('chosen', {}) if pv else {}
    print(f'  σύρσιμο ως ({x},{y}): {ch.get("layout")} {ch.get("riser_count")} ρίχτια, footprint', [tuple(round(c,2) for c in q) for q in (pv.geometry or {}).get('footprint', [])][:6], '|', u.status()[:110])
    u.shot(f'stair_drag{i}')
u.key(Qt.Key.Key_Escape)                         # red: does not fit in the hall -> cancel
QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, u._pos(9.6, 4.25)); u.pump()
print('  μετά το Esc: σκάλες', sum(e.kind == 'stair' for e in u.w.doc.entities.values()), 'tool', u.plan.controller.tool)
u.end()
u.begin('Ισόγειο: σκάλα στο σαλόνι, ξεκινώντας πάνω στον τοίχο x=6 (σύρσιμο δυτικά)')
a = u._pos(5.9, 7.0); QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a); u.pump()
for x in (4.5, 3.0, 1.5):
    QTest.mouseMove(vp, u._pos(x, 7.0)); u.pump()
pv = u.plan.controller.preview; ch = pv.geometry.get('chosen', {})
print('  προεπισκόπηση:', ch.get('layout'), 'fits', pv.geometry.get('fits'), 'αρχή', round(ch.get('x', 0), 2), round(ch.get('y', 0), 2))
u.shot('stair_living_drag')
QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, u._pos(1.5, 7.0)); u.pump(); u.steps += 1
st = [e for e in u.w.doc.entities.values() if e.kind == 'stair']
print('  σκάλες', len(st), st[-1].params.get('layout') if st else None, '|', u.status())
u.end()
u.shot('stair_placed')
stage('basement')
report()
