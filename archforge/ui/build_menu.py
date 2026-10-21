"""«Κατασκευή» as short submenus by kind of element (owner 14/10: «συμπύκνωσε σε υπομενού πρώτα τις
κατασκευές», showing Home Designer's Build menu: Wall ▸ Railing and Deck ▸ Door ▸ … — a reference for the
grouping, not a copy).

The entries are added by several installers (shell, slab, drywall, kitchen …).  This runs once at the end
and only *moves* what is there into themed submenus — anything it does not recognise stays, at the end —
so no command is ever lost.  Icons are drawn here (no image files).
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QMenu

INK = QColor(40, 62, 92)
ACCENT = QColor(47, 107, 214)
WOOD = QColor(176, 122, 70)


def _icon(kind):
    pix = QPixmap(32, 32); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(INK, 2.0); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
    if kind == 'wall':
        p.setBrush(QColor(200, 210, 224)); p.drawRect(QRectF(4, 11, 24, 10))
        for x in (10, 16, 22):
            p.drawLine(QPointF(x, 11), QPointF(x, 21))
    elif kind == 'joinery':
        p.drawRect(QRectF(5, 5, 10, 22)); p.drawEllipse(QPointF(12.5, 16), 1, 1)
        p.setPen(QPen(ACCENT, 2)); p.drawRect(QRectF(18, 7, 10, 10)); p.drawLine(QPointF(23, 7), QPointF(23, 17))
    elif kind == 'railing':
        p.drawLine(QPointF(4, 9), QPointF(28, 9)); p.drawLine(QPointF(4, 26), QPointF(28, 26))
        for x in (6, 11, 16, 21, 26):
            p.drawLine(QPointF(x, 9), QPointF(x, 26))
    elif kind == 'pergola':
        p.setPen(QPen(WOOD, 2.4))
        p.drawLine(QPointF(7, 10), QPointF(7, 28)); p.drawLine(QPointF(25, 10), QPointF(25, 28))
        p.drawLine(QPointF(3, 10), QPointF(29, 10))
        for x in (9, 14, 19, 24):
            p.drawLine(QPointF(x, 6), QPointF(x - 2, 13))
    elif kind == 'slab':
        p.setBrush(QColor(210, 214, 220))
        p.drawPolygon(QPolygonF([QPointF(3, 18), QPointF(17, 11), QPointF(29, 16), QPointF(15, 23)]))
        p.drawLine(QPointF(3, 18), QPointF(3, 21)); p.drawLine(QPointF(15, 23), QPointF(15, 26)); p.drawLine(QPointF(29, 16), QPointF(29, 19))
        p.drawLine(QPointF(3, 21), QPointF(15, 26)); p.drawLine(QPointF(15, 26), QPointF(29, 19))
    elif kind == 'roof':
        p.setBrush(QColor(196, 90, 70)); p.drawPolygon(QPolygonF([QPointF(3, 17), QPointF(16, 5), QPointF(29, 17)]))
        p.setBrush(Qt.BrushStyle.NoBrush); p.drawRect(QRectF(7, 17, 18, 11))
    elif kind == 'ceiling':
        p.drawLine(QPointF(3, 6), QPointF(29, 6))
        for x in (8, 16, 24):
            p.drawLine(QPointF(x, 6), QPointF(x, 12))
        p.setPen(QPen(ACCENT, 2.4)); p.drawLine(QPointF(4, 13), QPointF(28, 13))
        p.setPen(QPen(INK, 1.5)); p.drawLine(QPointF(4, 27), QPointF(28, 27))
    elif kind == 'frame':
        p.setBrush(QColor(210, 214, 220)); p.drawRect(QRectF(6, 8, 5, 20)); p.drawRect(QRectF(21, 8, 5, 20))
        p.drawRect(QRectF(4, 5, 24, 5))
    elif kind == 'stair':
        p.drawPolyline(QPolygonF([QPointF(3, 28), QPointF(3, 23), QPointF(9, 23), QPointF(9, 18), QPointF(15, 18),
                                  QPointF(15, 13), QPointF(21, 13), QPointF(21, 8), QPointF(28, 8)]))
    elif kind == 'cabinet':
        p.drawRect(QRectF(5, 7, 22, 20)); p.drawLine(QPointF(16, 7), QPointF(16, 27))
        p.drawLine(QPointF(13, 15), QPointF(13, 19)); p.drawLine(QPointF(19, 15), QPointF(19, 19))
    elif kind == 'storey':
        for y in (8, 16, 24):
            p.drawLine(QPointF(5, y), QPointF(27, y))
        p.setPen(QPen(ACCENT, 2.4)); p.drawLine(QPointF(24, 2), QPointF(24, 10)); p.drawLine(QPointF(20, 6), QPointF(28, 6))
    elif kind == 'site':
        p.setBrush(QColor(140, 175, 110))
        p.drawPolygon(QPolygonF([QPointF(3, 26), QPointF(11, 16), QPointF(17, 21), QPointF(23, 12), QPointF(29, 26)]))
    elif kind == 'renovation':
        p.drawRect(QRectF(4, 12, 16, 14)); p.setPen(QPen(QColor(200, 60, 50), 2.4))
        p.drawLine(QPointF(4, 12), QPointF(20, 26)); p.drawLine(QPointF(20, 12), QPointF(4, 26))
        p.setPen(QPen(ACCENT, 2.4)); p.drawLine(QPointF(25, 9), QPointF(25, 19)); p.drawLine(QPointF(20, 14), QPointF(30, 14))
    elif kind == 'report':
        p.drawRect(QRectF(7, 4, 18, 24))
        for y in (10, 15, 20):
            p.drawLine(QPointF(10, y), QPointF(22, y))
        p.setPen(QPen(ACCENT, 2.2)); p.drawText(QRectF(14, 18, 14, 12), Qt.AlignmentFlag.AlignCenter, '€')
    p.end()
    return QIcon(pix)


def _submenu(window, title, kind, entries):
    """A themed submenu holding ``entries`` (actions or menus; None = separator), kept alive on the window."""
    sub = QMenu(title, window)
    sub.setIcon(_icon(kind))
    for e in entries:
        if e is None:
            sub.addSeparator()
        elif isinstance(e, QMenu):
            sub.addMenu(e)
        else:
            sub.addAction(e)
    window._build_submenus.append(sub)
    return sub


def _tool(window, text, tool):
    from PySide6.QtGui import QAction
    a = QAction(text, window)
    a.triggered.connect(lambda _=False, t=tool: window._set_active_tool(t))
    window._build_actions.append(a)
    return a


def organize_build_menu(window):
    """Regroup the menu bar's «Κατασκευή» into submenus by kind of element (moves, never drops)."""
    from PySide6.QtGui import QAction
    bar = [a for a in window.menuBar().actions() if a.text().replace('&', '') == 'Κατασκευή' and a.menu()]
    if not bar:
        return None
    menu = bar[0].menu()
    window._build_submenus, window._build_actions = [], []
    present = [a for a in menu.actions() if not a.isSeparator()]
    by_text = {a.text().replace('&&', '&'): a for a in present}
    used = set()

    def take(obj):
        """The action already in the menu for ``obj`` (an action, or a menu by its menuAction)."""
        if obj is None:
            return None
        action = obj.menuAction() if isinstance(obj, QMenu) else obj
        if action in present:
            used.add(action)
            return obj
        return None

    def take_text(prefix):
        for text, a in by_text.items():
            if text.startswith(prefix) and a not in used:
                used.add(a)
                return a.menu() if a.menu() is not None else a
        return None

    def keep(*items):
        return [i for i in items if i is not None or False]

    # Things with no entry of their own in «Κατασκευή» yet: the drawing tools behind them.
    wall = _tool(window, 'Τοίχος (κλικ στις γωνίες)', 'wall'); wall.setIcon(_icon('wall'))
    from PySide6.QtGui import QAction
    from archforge.ui import room_box_tool
    room_box = QAction('Δωμάτιο (ορθογώνιο)', window); room_box.setIcon(_icon('wall'))
    room_box.triggered.connect(lambda _=False: room_box_tool.start(window))
    room_sized = QAction('Δωμάτιο με διαστάσεις…', window)
    room_sized.triggered.connect(lambda _=False: room_box_tool.start(window, sized=True))
    window._room_box_action, window._room_sized_action = room_box, room_sized
    room_resize = QAction('Διαστάσεις δωματίου… (κλικ μέσα του)', window)
    room_resize.triggered.connect(lambda _=False: room_box_tool.start_resize(window))
    wall_angle = QAction('Γωνία επιλεγμένου τοίχου…', window)
    wall_angle.triggered.connect(lambda _=False: room_box_tool.wall_angle(window))
    from PySide6.QtGui import QActionGroup
    from archforge.architecture.wall_face import LABELS
    face_menu = QMenu('Σχεδίαση τοίχου από', window)
    face_group = QActionGroup(face_menu)
    current = getattr(window.plan_view.controller, 'wall_face', 'auto')
    for key in ('auto', 'axis', 'left', 'right'):
        act = QAction(LABELS[key] + (' (F στη σχεδίαση)' if key == 'left' else ''), face_menu)
        act.setCheckable(True); act.setChecked(key == current); face_group.addAction(act); face_menu.addAction(act)
        act.triggered.connect(lambda _=False, k=key: (setattr(window.plan_view.controller, 'wall_face', k),
                                                      window.statusBar().showMessage(f'Τοίχος από: {LABELS[k]}', 5000)))
    window._wall_face_menu = face_menu
    from_underlay = QAction('Τοίχοι από το υπόβαθρο (PDF / DXF)…', window)
    from_underlay.triggered.connect(lambda _=False: __import__('archforge.ui.walls_from_underlay',
                                                               fromlist=['run']).run(window))
    walls = _submenu(window, 'Τοίχοι && δωμάτια', 'wall', [wall, face_menu, None, room_box, room_sized, None,
                                                            room_resize, wall_angle, None, from_underlay])
    complete = QAction('Ολοκλήρωση κτιρίου…', window); complete.setIcon(_icon('storey'))
    complete.setToolTip('Δάπεδα, στέγη, κουζίνα/μπάνια, φως-πρίζες, πίνακας, θέρμανση, φέρων — ό,τι λείπει, μία αναίρεση')
    complete.triggered.connect(lambda _=False: __import__('archforge.ui.complete_building', fromlist=['open_dialog']).open_dialog(window))
    window._complete_building_action = complete
    joinery = _submenu(window, 'Κουφώματα', 'joinery', [
        _tool(window, 'Πόρτα', 'door'), _tool(window, 'Παράθυρο', 'window'), None,
        _tool(window, 'Άνοιγμα (χωρίς κούφωμα)', 'opening_rect'), _tool(window, 'Τοξωτό άνοιγμα', 'opening_arch')])
    railing = take(getattr(window, '_mockup_railing_menu', None))
    pergola = take(getattr(window, '_mockup_pergola_menu', None))
    slab_items = [take(a) for a in getattr(window, '_slab_opening_actions', ())]
    slabs = _submenu(window, 'Δάπεδα && πλάκες', 'slab', keep(
        getattr(window, '_mockup_auto_floor_action', None), getattr(window, '_mockup_flat_roof_action', None), None,
        *[a for a in slab_items if a is not None]))
    roof = take(getattr(window, '_roof_menu', None))
    roof_views = [take_text('Ξυλεία στέγης στο 3D'), take_text('Στρώσεις στέγης στο 3D (ταμπλάς, μόνωση, μεμβράνες)'),
                  take_text('Κεραμίδια στο 3D')]
    if roof is not None and any(roof_views):
        roof.addSeparator()
        for a in roof_views:
            if a is not None:
                roof.addAction(a)
    ceiling = take_text('Ψευδοροφή γυψοσανίδας')
    frame = getattr(window, '_mockup_structural_submenu', None)
    stairs = getattr(window, '_mockup_circulation_menu', None)
    cabinets = getattr(window, '_mockup_kitchen_menu', None)
    if cabinets is not None:
        getattr(window, '_fill_kitchen_menu', lambda: None)()   # filled on first open otherwise -> looked empty
        cabinets.setTitle('Ντουλάπια / κουζίνα')
    storeys = _submenu(window, 'Όροφοι', 'storey', keep(
        getattr(window, '_mockup_add_floor_action', None), take(getattr(window, '_mockup_basement_action', None))))
    site = take_text('Έδαφος (οικόπεδο)')
    renovation = take(getattr(window, '_renovation_menu', None))
    reports = _submenu(window, 'Επιμετρήσεις && τιμές', 'report', [a for a in (
        take(getattr(window, '_takeoff_action', None)), take(getattr(window, '_isotex_action', None)),
        take_text('Τεμάχια ICF'), take_text('Γυψοσανίδες — υλικά'), None,
        take(getattr(window, '_priced_lists_action', None)), take(getattr(window, '_trades_action', None)),
        take(getattr(window, '_insulation_action', None)),
        take(getattr(window, '_prices_action', None)),
        take(getattr(window, '_pdf_action', None))) if a is not None or False])
    # Icons on the menus that already existed.
    for obj, kind in ((railing, 'railing'), (pergola, 'pergola'), (roof, 'roof'), (ceiling, 'ceiling'), (frame, 'frame'),
                      (stairs, 'stair'), (cabinets, 'cabinet'), (renovation, 'renovation')):
        if isinstance(obj, QMenu):
            obj.setIcon(_icon(kind))
    if site is not None:
        site.setIcon(_icon('site'))
    if railing is not None:
        railing.setTitle('Κάγκελα && μπαλκόνια')
        balcony = next((a for a in slab_items if a is not None and a.text().startswith('Μπαλκόνι')), None)
        if balcony is not None:
            # After the railing types, before «Κάγκελο σκάλας».
            last = railing.actions()[-1] if railing.actions() else None
            railing.insertAction(last, balcony)
    leftovers = [a for a in present if a not in used]
    for a in present:
        menu.removeAction(a)
    for a in [x for x in menu.actions()]:
        menu.removeAction(a)                          # old separators
    order = [walls, complete, None, joinery, railing, pergola, slabs, roof, ceiling, frame, stairs, cabinets, storeys, site,
             None, renovation, reports]
    for item in order:
        if item is None:
            menu.addSeparator()
        elif isinstance(item, QMenu):
            if item.actions():
                menu.addMenu(item)
        else:
            menu.addAction(item)
    if leftovers:                                     # never lose a command someone added
        menu.addSeparator()
        for a in leftovers:
            menu.addAction(a)
    window._build_menu = menu
    return menu
