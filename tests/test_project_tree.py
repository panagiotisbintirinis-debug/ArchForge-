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
        assert 'Τοίχοι (4)' in labels and 'Ντουλάπια & κουζίνα (1)' in labels
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
