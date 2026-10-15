"""Owner 15/10: «δυνατότητα να τοποθετώ κουφώματα άσχετα εάν το σχεδιαστικό είναι στον πρώτο ή στο ισόγειο·
στο 3Δ τα βλέπω όλα και επιλέγω»."""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.architecture.openings import nearest_opening_host
from archforge.core.commands import AddEntity, CommandStack, CreateFloorLevel
from archforge.core.model import Document, Entity


def _two_storeys(doc, st):
    low = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
    up = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 0, 'z': 3.0, 'height': 2.7, 'thickness': 0.2})
    st.execute(AddEntity(low)); st.execute(AddEntity(up))
    return low, up


def test_the_host_is_looked_for_on_the_storey_of_the_clicked_wall():
    doc = Document(); st = CommandStack(doc)
    low, up = _two_storeys(doc, st)
    assert float(doc.work_plane.origin[2]) == 0.0                      # drawing on the ground floor
    assert nearest_opening_host(doc, 2.0, 0.1)['host_id'] == low.id
    assert nearest_opening_host(doc, 2.0, 0.1, level_z=3.0)['host_id'] == up.id


def test_a_window_clicked_in_3d_on_the_first_floor_while_drawing_the_ground_floor():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        low, up = _two_storeys(window.doc, window.stack)
        assert float(window.doc.work_plane.origin[2]) == 0.0
        window.pbr_view.set_tool('window')
        window.pbr_view._place_opening_from_web('window', json.dumps({'entity_id': up.id, 'point': [2.0, 0.1, 4.4]}))
        windows = [e for e in window.doc.entities.values() if e.kind == 'window']
        assert len(windows) == 1 and windows[0].parent_id == up.id
        assert float(window.doc.work_plane.origin[2]) == 0.0           # still drawing where you were
        window.pbr_view._place_opening_from_web('door', json.dumps({'entity_id': low.id, 'point': [4.0, 0.1, 1.0]}))
        doors = [e for e in window.doc.entities.values() if e.kind == 'door']
        assert len(doors) == 1 and doors[0].parent_id == low.id
    finally:
        window._mark_clean(); window.close(); app.processEvents()
