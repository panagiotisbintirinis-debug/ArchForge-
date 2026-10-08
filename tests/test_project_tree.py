"""The project tree shows only what exists in the Document."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.kitchen.cabinets import default_params
from archforge.ui.project_outline import project_outline


def _labels(node):
    out = [node['label']]
    for c in node['children']:
        out += _labels(c)
    return out


def _walls(stack, z=0.0):
    pts = [(0, 0), (4, 0), (4, 3), (0, 3)]
    ids = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        w = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z, 'height': 2.7, 'thickness': 0.2})
        stack.execute(AddEntity(w)); ids.append(w.id)
    return ids


def test_empty_project_lists_no_invented_rooms_or_storeys():
    from archforge.core.model import Document
    labels = _labels(project_outline(Document(), 'Νέο'))
    assert labels[0] == 'Νέο'
    for fake in ('Σαλόνι', 'Κουζίνα', 'Τραπεζαρία', 'Υπνοδωμάτιο 1', 'Μπάνιο 1', 'Όροφος 1', 'Στέγη', 'House Project 1'):
        assert fake not in ' '.join(labels)
    assert not any(l.startswith(('Τοίχοι', 'Δωμάτια', 'Έπιπλα', 'Οικόπεδο')) for l in labels)


def test_tree_follows_the_document_and_selects_entities():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        tree = window.project_tree
        walls = _walls(window.stack)
        cab = Entity('cabinet', default_params('base', 1.0, 0.4), name='Ντουλάπι βάσης')
        window.stack.execute(AddEntity(cab))
        window._refresh_project_tree()
        labels = _labels(project_outline(window.doc))
        assert 'Τοίχοι (4)' in labels and 'Ντουλάπια & κουζίνα (1)' in labels   # the cabinet is listed in its room
        assert any(l.startswith('Δωμάτια (1)') for l in labels)       # the four walls enclose one room
        assert any('12.00 m²' in l or '11.' in l for l in labels if 'm²' in l)

        def find(item, text):
            if item.text(0) == text:
                return item
            for i in range(item.childCount()):
                hit = find(item.child(i), text)
                if hit:
                    return hit
        root = tree.topLevelItem(0)
        item = find(root, 'Ντουλάπι βάσης')
        assert item is not None
        window._project_tree_clicked(item)
        assert window.doc.selection == [cab.id]
        window.stack.undo()                                  # cabinet removed -> gone from the tree
        window._on_document_changed()
        assert find(tree.topLevelItem(0), 'Ντουλάπι βάσης') is None
        assert window._project_levels_list.count() >= 1
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_construction_tree_lists_every_entity_once_in_its_place():
    from archforge.core.commands import CommandStack
    from archforge.core.model import Document
    doc = Document(); stack = CommandStack(doc)
    walls = _walls(stack)
    win = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=walls[0], name='Παράθυρο')
    stack.execute(AddEntity(win))
    wc = Entity('plumbing_point', {'x': 1.0, 'y': 1.0, 'z': 0.0, 'point_type': 'wc'}, name='Λεκάνη WC')
    stack.execute(AddEntity(wc))
    out = project_outline(doc)

    def find(node, eid, path=()):
        if node['entity_id'] == eid:
            return path + (node['label'],)
        for c in node['children']:
            hit = find(c, eid, path + (node['label'],))
            if hit:
                return hit
    room_path = find(out, wc.id)
    assert any(p.startswith('Χώρος 1 · WC') and '12.00 m²' in p for p in room_path)      # inside its room, use inferred
    wall_path = find(out, win.id)
    assert any(p.startswith('Εξωτερικοί (4)') for p in wall_path) and wall_path[-2].startswith('Τοίχος Ν · Χώρος 1 · 4.00 m')    # facing south, room named
    ids = []

    def collect(n):
        if n['entity_id']:
            ids.append(n['entity_id'])
        for c in n['children']:
            collect(c)
    collect(out)
    assert sorted(ids) == sorted(doc.entities) and len(ids) == len(set(ids))


def test_selection_in_the_drawing_is_highlighted_in_the_tree():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        walls = _walls(window.stack)
        window._refresh_project_tree()
        window.doc.select([walls[2]])
        window.refresh_inspector()
        current = window.project_tree.currentItem()
        assert current is not None and current.data(0, 0x0100) == walls[2]
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_tree_groups_and_rooms_select_in_the_drawing_and_can_be_deleted():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow(); window._no_modal_dialogs = True
    try:
        ids = _walls(window.stack)
        window.doc.levels['Floor 2'] = 2.7
        _walls(window.stack, 2.7)
        from archforge.structure.timber_roof import default_params
        roof = Entity('pitched_roof', default_params(window.doc, z=2.7), name='Κεραμοσκεπή δίρριχτη')
        window.stack.execute(AddEntity(roof))
        window._refresh_project_tree()
        tree = window.project_tree

        def find(prefix, item=None):
            item = item or tree.invisibleRootItem()
            for i in range(item.childCount()):
                c = item.child(i)
                if c.text(0).startswith(prefix):
                    return c
                hit = find(prefix, c)
                if hit is not None:
                    return hit
        walls_group = find('Τοίχοι')
        window._project_tree_clicked(walls_group)
        assert set(ids) <= set(window.doc.selection) or set(window.doc.selection) == set(window._tree_item_ids(walls_group))
        room = find('Χώρος 1')
        window._project_tree_clicked(room)
        assert len(window.doc.selection) == 4                      # the room's walls light up
        # The tiled roof is listed under the storey it covers, not the ground floor.
        roof_item = next(it for it in [find('Κεραμοσκεπή')] if it is not None)
        level = roof_item.data(0, 0x0100 + 1)
        assert level == 'Floor 2'
        window._project_tree_clicked(roof_item)
        assert window.doc.selection == [roof.id] or list(window.doc.selection) == [roof.id]
        menu = window._project_tree_menu(tree.visualItemRect(roof_item).center())
        texts = [a.text() for a in menu.actions()]
        assert texts == ['Ιδιότητες', 'Διαγραφή']
        menu.actions()[1].trigger()
        assert roof.id not in window.doc.entities
        window.stack.undo()
        assert roof.id in window.doc.entities
    finally:
        window._mark_clean(); window.close(); app.processEvents()
