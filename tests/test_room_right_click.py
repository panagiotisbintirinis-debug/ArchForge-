"""Found driving the two-storey house as a user (owner 14/10 «πάρε τη θέση του χρήστη»): since floors are made
automatically, a right click inside a room caught the storey's floor slab — the room's own commands
(Σε αυτόν τον χώρο ▸ Μπάνιο εδώ…, Χρήση χώρου) were gone.  Inside a room the room's menu opens again."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def test_right_click_inside_a_room_gives_the_room_menu_not_the_floor_slab():
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QContextMenuEvent
    from PySide6.QtWidgets import QApplication
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1200, 800); w.show(); app.processEvents()
    try:
        for x1, y1, x2, y2 in ((0, 0, 6, 0), (6, 0, 6, 5), (6, 5, 0, 5), (0, 5, 0, 0)):
            w.stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0,
                                                      'height': 2.7, 'thickness': 0.25})))
        w.stack.execute(AddEntity(Entity('room_floor', {'scope': 'storey', 'level_z': 0.0, 'thickness': 0.2,
                                                        'polygon': [[-1, -1], [7, -1], [7, 6], [-1, 6]]})))
        view = w.plan_view
        view.redraw(); view.fitInView(-1, -1, 8, 7); app.processEvents()
        pos = view.mapFromScene(QPointF(3.0, 2.5))
        hit = view._entity_items.get(view.itemAt(pos))
        assert hit and w.doc.get(hit).kind == 'room_floor'               # the slab is what lies under the mouse
        view.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos, view.viewport().mapToGlobal(pos)))
        app.processEvents()
        menu = view._marking_menu
        ids = []
        def walk(es):
            for e in es:
                ids.append(e.get('id')); walk(e.get('children') or ())
        walk(menu.menu['entries'])
        assert 'mm:group:room' in ids and 'mm:layout:bath' in ids
        view.hide_marking_menu()
        # Outside every room the slab keeps its own menu.
        pos = view.mapFromScene(QPointF(6.6, -0.6))
        if view._entity_items.get(view.itemAt(pos)):
            view.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos, view.viewport().mapToGlobal(pos)))
            app.processEvents()
            assert w.doc.selection and w.doc.get(w.doc.selection[0]).kind == 'room_floor'
            view.hide_marking_menu()
    finally:
        w._mark_clean(); w.close(); app.processEvents()
