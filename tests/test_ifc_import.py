"""IFC import (HANDOFF 30/10): storeys, walls with their build-up, doors / windows in them — one undo step, through
the same commands as drawing by hand.  Checked by a round trip of the owner's two-storey house and a hand-made file."""
import json
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

ifcopenshell = pytest.importorskip('ifcopenshell')

from archforge.architecture import wall_assemblies as wa  # noqa: E402
from archforge.architecture.wall_types import layers  # noqa: E402
from archforge.core.commands import AddEntity, CommandStack  # noqa: E402
from archforge.core.model import Document, Entity  # noqa: E402
from archforge.exchange.ifc import export_ifc  # noqa: E402
from archforge.exchange.ifc_import import import_ifc, min_rectangle, read  # noqa: E402

PROJECT = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')


def _key(e):
    p = e.params
    a, b = sorted([(round(p['x1'], 3), round(p['y1'], 3)), (round(p['x2'], 3), round(p['y2'], 3))])
    return (a, b, round(p['z'], 2))


def test_the_owners_house_comes_back_wall_for_wall(tmp_path):
    src = Document.from_dict(json.load(open(PROJECT, encoding='utf-8')))
    path = tmp_path / 'house.ifc'
    export_ifc(src, path, 'Δοκιμή')
    doc = Document(); stack = CommandStack(doc)
    summary = import_ifc(doc, stack, path)
    walls = {_key(e): e for e in src.entities.values() if e.kind == 'wall'}
    back = {_key(e): e for e in doc.entities.values() if e.kind == 'wall'}
    assert set(back) == set(walls) and summary['walls'] == len(walls)
    for k, e in walls.items():
        assert back[k].params['thickness'] == pytest.approx(e.params['thickness'], abs=1e-3) or \
            e.params.get('wall_type', 'generic') != 'generic'
    def count(d, kind):
        return sum(1 for e in d.entities.values() if e.kind == kind)
    assert (count(doc, 'door'), count(doc, 'window')) == (count(src, 'door'), count(src, 'window'))
    assert {round(z, 2) for z in doc.levels.values()} >= {round(z, 2) for z in src.levels.values()}
    assert summary['not_imported']                                    # slabs, roofs … are said, not dropped silently
    stack.undo()
    assert not doc.entities


def test_layers_return_as_the_built_in_type_or_one_new_project_type(tmp_path):
    src = Document(); st = CommandStack(src)
    key, cmd = wa.new_type_command(src, 'Δική μου 10 cm πετροβάμβακα',
                                   [{'material': 'cement_plaster', 'thickness': 0.02}, {'material': 'hollow_brick', 'thickness': 0.09},
                                    {'material': 'mineral_wool', 'thickness': 0.10}, {'material': 'hollow_brick', 'thickness': 0.09},
                                    {'material': 'cement_plaster', 'thickness': 0.02}])
    st.execute(cmd)
    for y, wt, t in ((0.0, 'brick_double_insulated', 0.27), (3.0, key, 0.32), (6.0, key, 0.32)):
        w = Entity('wall', {'x1': 0.0, 'y1': y, 'x2': 5.0, 'y2': y, 'z': 0.0, 'height': 2.7, 'thickness': t,
                            'wall_type': wt})
        st.execute(AddEntity(w))
        if y == 0.0:
            st.execute(AddEntity(Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9},
                                        parent_id=w.id)))
    path = tmp_path / 'layers.ifc'
    export_ifc(src, path)
    doc = Document(); stack = CommandStack(doc)
    summary = import_ifc(doc, stack, path)
    types = sorted(str(e.params['wall_type']) for e in doc.entities.values() if e.kind == 'wall')
    assert types[0] == 'brick_double_insulated' and types[1] == types[2] and types[1].startswith('proj_')
    assert summary['new_types'] == 1
    assert [l.material_id for l in layers(types[1], doc)][2] == 'mineral_wool'
    [win] = [e for e in doc.entities.values() if e.kind == 'window']
    p = win.params
    assert (p['offset'], p['width'], p['height'], p['sill']) == pytest.approx((2.0, 1.2, 1.4, 0.9), abs=0.02)


def test_a_wall_without_an_axis_is_read_from_its_body():
    pts = [(0, 0), (4, 0), (4, 0.3), (0, 0.3), (2, 0.15)]
    centre, u, long_side, short_side = min_rectangle([(x * math.cos(0.5) - y * math.sin(0.5),
                                                       x * math.sin(0.5) + y * math.cos(0.5)) for x, y in pts])
    assert (long_side, short_side) == pytest.approx((4.0, 0.3), abs=1e-5)
    assert abs(u[0] * math.cos(0.5) + u[1] * math.sin(0.5)) == pytest.approx(1.0)


def test_the_file_menu_has_import_ifc(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        src = Document(); src.add(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 3.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7,
                                                  'thickness': 0.2}))
        path = tmp_path / 'one.ifc'
        export_ifc(src, path)
        texts = [a.text() for a in w._file_import_menu.actions()]
        assert any('IFC' in t for t in texts)
        from archforge.ui.exchange_export import import_ifc as run
        result = run(w, str(path))
        assert result['walls'] == 1 and sum(1 for e in w.doc.entities.values() if e.kind == 'wall') == 1
    finally:
        w._mark_clean(); w.close(); app.processEvents()
