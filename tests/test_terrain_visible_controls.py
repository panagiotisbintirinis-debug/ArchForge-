import os
import subprocess
import sys
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def test_slope_enter_keeps_editor_alive_until_key_event_returns():
    script = '''
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from shiboken6 import isValid
from archforge.ui.main_window import MainWindow
app = QApplication([]); w = MainWindow(); w.show(); w._create_terrain(); app.processEvents()
for key, label in [('slope_x', 'Κλίση X %'), ('slope_y', 'Κλίση Y %')]:
    for i in range(w.form.rowCount()):
        item = w.form.itemAt(i, w.form.ItemRole.LabelRole)
        if item and item.widget().text() == label:
            spin = w.form.itemAt(i, w.form.ItemRole.FieldRole).widget(); break
    spin.setFocus(); spin.setValue(-45.)
    QTest.keyClick(spin, Qt.Key.Key_Return)
    assert isValid(spin), 'editor deleted inside its own key event'
    app.processEvents()
    assert w._terrain_entity().params[key] == -45.
w._mark_clean(); w.close(); app.processEvents()
print('slope edits passed')
'''
    env = dict(os.environ, QTWEBENGINE_DISABLE_SANDBOX='1', PYTEST_CURRENT_TEST='slope-regression')
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'slope edits passed' in result.stdout


def test_terrain_corners_show_height_without_control_points(terrain_window):
    from PySide6.QtWidgets import QGraphicsTextItem
    from archforge.ui.terrain_tools import mark
    from archforge.site.terrain import terrain_height
    w, app = terrain_window
    w._create_terrain()
    e = w._terrain_entity()
    w._commit_property(e.id, 'slope_x', 50.)
    app.processEvents()
    values = {item.toPlainText() for item in w.plan_view.scene().items() if isinstance(item, QGraphicsTextItem)}
    p = e.params
    for x, y in ((p['x0'], p['y0']), (p['x1'], p['y0']), (p['x1'], p['y1']), (p['x0'], p['y1'])):
        assert mark(terrain_height(p, x, y)) in values


def test_basement_and_rectangle_tools_are_directly_visible(terrain_window):
    w, app = terrain_window
    # Διάταξη 2: «Υπόγειο» on the «Όροφος» group, the elevation frame in Κατασκευή ▸ Έδαφος & περιβάλλον.
    assert w._mockup_basement_action in w._tool_groups['storey'].items
    assert w._terrain_rectangle_action in w._mockup_terrain_menu.actions()
    w._terrain_rectangle_action.trigger()
    assert w.plan_view.controller.tool == 'terrain_region_rectangle'


@pytest.mark.parametrize('displaced', [False, True])
def test_floor_and_terrace_at_decimal_storey_level(terrain_window, displaced):
    from archforge.core.model import Entity, WorkPlane
    from archforge.core.commands import AddEntity
    from archforge.ui.slab_tools import auto_storey_slab
    from archforge.architecture.storey_slabs import storey_slab_geometry
    w, app = terrain_window
    w.doc.levels['Floor 2'] = 1.4
    w.doc.work_plane = WorkPlane(name='Floor 2', origin=(0., 0., 1.4))
    if displaced:
        for a,b in (((-20,0),(-14,0)),((-14,0),(-14,4)),((-14,4),(-20,4)),((-20,4),(-20,0))):
            w.stack.execute(AddEntity(Entity('wall',dict(x1=a[0],y1=a[1],x2=b[0],y2=b[1],
                                                        z=0.,height=1.4,thickness=.2))))
    for a,b in (((0,0),(6,0)),((6,0),(6,4)),((6,4),(0,4)),((0,4),(0,0))):
        w.stack.execute(AddEntity(Entity('wall',dict(x1=a[0],y1=a[1],x2=b[0],y2=b[1],
                                                    z=1.4,height=2.7,thickness=.2))))
    floor = auto_storey_slab(w, 'room_floor')
    roof = auto_storey_slab(w, 'room_roof')
    assert storey_slab_geometry(w.doc, floor)['z'] == 1.4
    assert abs(storey_slab_geometry(w.doc, roof)['z'] - 4.1) < 1e-8
    assert storey_slab_geometry(w.doc, floor)['area'] > 20.
    w._undo()
    assert roof.id not in w.doc.entities and floor.id in w.doc.entities


@pytest.mark.parametrize('finish', ['enter', 'double'])
def test_plot_perimeter_finishes_with_keyboard_or_double_click(terrain_window, finish):
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtTest import QTest
    w, app = terrain_window
    w._start_site_tool('plot_point', '')
    points = [(-3.,-2.),(3.,-2.),(3.,2.),(-3.,2.)]
    for x,y in points:
        w.plan_view.sitePointRequested.emit('plot_point', x, y)
    assert w._terrain_entity() is None
    if finish == 'enter':
        QTest.keyClick(w.plan_view.viewport(), Qt.Key.Key_Return)
    else:
        QTest.mouseDClick(w.plan_view.viewport(), Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier, w.plan_view.mapFromScene(QPointF(*points[-1])))
    app.processEvents()
    assert w._terrain_entity().params['boundary'] == [list(p) for p in points]
    assert w.plan_view.controller.tool == 'select'
    assert w.doc.selection == [w._terrain_entity().id]
    assert len(w.stack.done) == 1
    w._undo()
    assert w._terrain_entity() is None


from tests.test_terrain_regions_basement import terrain_window
