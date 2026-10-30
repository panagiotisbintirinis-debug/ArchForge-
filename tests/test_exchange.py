"""The translator (owner 30/10: «μεταφραστής στοιχείων του σχεδίου … IFC, DXF, PDF και άλλα»): every file is read back
and checked against the Document it came from."""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

ifcopenshell = pytest.importorskip('ifcopenshell')
ezdxf = pytest.importorskip('ezdxf')

from archforge.core.model import Document  # noqa: E402

PROJECT = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')


@pytest.fixture(scope='module')
def doc():
    return Document.from_dict(json.load(open(PROJECT, encoding='utf-8')))


@pytest.fixture(scope='module')
def ifc_file(doc, tmp_path_factory):
    from archforge.exchange.ifc import export_ifc
    path = tmp_path_factory.mktemp('ifc') / 'house.ifc'
    summary = export_ifc(doc, path, 'Δοκιμή')
    return ifcopenshell.open(str(path)), summary


def test_ifc_is_valid_ifc4_with_the_storeys_of_the_project(ifc_file, doc):
    import ifcopenshell.validate
    f, summary = ifc_file
    assert f.schema == 'IFC4'
    log = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(f, log)
    assert log.statements == []                                            # schema-valid, no warnings
    levels = sorted(doc.levels.values())
    assert sorted(s.Elevation for s in f.by_type('IfcBuildingStorey')) == pytest.approx(levels)
    assert [s.Name for s in sorted(f.by_type('IfcBuildingStorey'), key=lambda s: s.Elevation)] == ['Ισόγειο', '1ος όροφος']
    assert summary['left_out'] == {}


def test_every_element_is_there_with_its_id_and_storey(ifc_file, doc):
    import ifcopenshell.util.element as U
    f, _summary = ifc_file
    kinds = {}
    for e in doc.entities.values():
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    assert len(f.by_type('IfcWall')) == kinds['wall']
    assert len(f.by_type('IfcDoor')) == kinds['door'] and len(f.by_type('IfcWindow')) == kinds['window']
    assert len(f.by_type('IfcColumn')) == kinds['structural_column'] and len(f.by_type('IfcBeam')) == kinds['structural_beam']
    assert len(f.by_type('IfcStair')) == kinds['stair'] and len(f.by_type('IfcRoof')) == kinds['pitched_roof']
    ids = {U.get_psets(x)['ArchForge']['Id'] for x in f.by_type('IfcElement') if 'ArchForge' in U.get_psets(x)}
    built = {e.id for e in doc.entities.values() if e.kind not in ('camera', 'auto_dimensions')}
    assert built <= ids                                                     # nothing built is lost
    for wall in f.by_type('IfcWall'):
        e = doc.get(U.get_psets(wall)['ArchForge']['Id'])
        expected = 'Ισόγειο' if float(e.params['z']) < 1.0 else '1ος όροφος'
        assert U.get_container(wall).Name == expected


def test_openings_void_their_wall_and_hold_the_door_or_window(ifc_file, doc):
    import ifcopenshell.util.element as U
    f, _summary = ifc_file
    for leaf in f.by_type('IfcDoor') + f.by_type('IfcWindow'):
        fills = leaf.FillsVoids
        assert len(fills) == 1
        hole = fills[0].RelatingOpeningElement
        wall = hole.VoidsElements[0].RelatingBuildingElement
        host = doc.get(U.get_psets(leaf)['ArchForge']['Id']).parent_id
        assert U.get_psets(wall)['ArchForge']['Id'] == host
        o = doc.get(U.get_psets(leaf)['ArchForge']['Id']).params
        assert (leaf.OverallWidth, leaf.OverallHeight) == pytest.approx((o['width'], o['height']))


def test_walls_carry_layers_and_common_properties_and_spaces_their_area(ifc_file, doc):
    import ifcopenshell.util.element as U
    from archforge.quantities.takeoff import _area, net_polygon
    f, summary = ifc_file
    wall = f.by_type('IfcWall')[0]
    e = doc.get(U.get_psets(wall)['ArchForge']['Id'])
    mat = U.get_material(wall)
    assert sum(l.LayerThickness for l in mat.MaterialLayers) == pytest.approx(float(e.params['thickness']))
    common = U.get_psets(wall)['Pset_WallCommon']
    assert 'LoadBearing' in common and 'IsExternal' in common
    assert sum(1 for w in f.by_type('IfcWall') if U.get_psets(w)['Pset_WallCommon']['IsExternal']) > 0
    spaces = f.by_type('IfcSpace')
    faces = [(z, face) for z in doc.levels.values() for face in doc.active_room_faces(z=z)]
    assert len(spaces) == len(faces) == len(summary['spaces'])
    z, face = faces[0]
    net = abs(_area(net_polygon(doc, face.polygon, z)))
    first = next(s for s in spaces if U.get_psets(s)['ArchForge']['Signature'] == face.signature)
    assert U.get_psets(first)['Qto_SpaceBaseQuantities']['NetFloorArea'] == pytest.approx(net, abs=0.01)


def test_ifc_geometry_builds_walls_with_their_holes(ifc_file):
    import ifcopenshell.geom
    f, _summary = ifc_file
    settings = ifcopenshell.geom.settings()
    walls = [w for w in f.by_type('IfcWall') if w.HasOpenings][:3]
    assert walls
    for w in walls + list(f.by_type('IfcSpace')[:2]) + list(f.by_type('IfcDoor')[:2]):
        shape = ifcopenshell.geom.create_shape(settings, w)
        assert len(shape.geometry.verts) > 0


def test_a_curved_wall_leaves_as_walls_of_one_arc(tmp_path):
    import ifcopenshell.util.element as U
    from archforge.architecture import curved_wall as cw
    from archforge.core.commands import CommandStack
    from archforge.exchange.ifc import export_ifc
    d = Document(); stack = CommandStack(d)
    command, walls = cw.create_command(d, (0, 0), (6, 0), (3, 2), n=6)
    stack.execute(command)
    export_ifc(d, tmp_path / 'arc.ifc')
    f = ifcopenshell.open(str(tmp_path / 'arc.ifc'))
    curves = {U.get_psets(w)['ArchForge'].get('CurveId') for w in f.by_type('IfcWall')}
    assert len(f.by_type('IfcWall')) == 6 and curves == {walls[0].params['curve']['id']}


def test_dxf_one_file_per_storey_in_metres_with_cad_layers(doc, tmp_path):
    from ezdxf import recover
    from archforge.exchange.dxf import export_dxf
    result = export_dxf(doc, tmp_path / 'house.dxf')
    assert [os.path.basename(p) for p in result['files']] == ['house - Ισόγειο.dxf', 'house - 1ος όροφος.dxf']
    dxf, auditor = recover.readfile(result['files'][0])
    assert not auditor.errors
    assert dxf.header['$INSUNITS'] == 6
    layers = {l.dxf.name for l in dxf.layers}
    assert {'A-WALL', 'A-DOOR', 'A-ANNO-DIMS', 'A-AREA-IDEN', 'S-COLS', 'S-BEAM'} <= layers
    msp = dxf.modelspace()
    assert msp.query('HATCH[layer=="A-WALL"]')                              # walls filled as in the plan
    texts = [t.text for t in msp.query('MTEXT[layer=="A-AREA-IDEN"]')]
    assert any('m²' in t for t in texts)
    # at the project coordinates: every ground wall's axis inside the drawn extents
    xs = [v[0] for e in msp.query('LWPOLYLINE') for v in e.get_points('xy')]
    ys = [v[1] for e in msp.query('LWPOLYLINE') for v in e.get_points('xy')]
    for w in (e for e in doc.entities.values() if e.kind == 'wall' and float(e.params['z']) < 1.0):
        for x, y in ((w.params['x1'], w.params['y1']), (w.params['x2'], w.params['y2'])):
            assert min(xs) - 1e-6 <= x <= max(xs) + 1e-6 and min(ys) - 1e-6 <= y <= max(ys) + 1e-6
    upper, _a = recover.readfile(result['files'][1])
    assert 'A-MISC' not in {l.dxf.name for l in upper.layers}               # the faint storey below is not exported


def test_export_commands_in_the_file_menu(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.mouse_menus import _find_action
    from archforge.ui.exchange_export import export_dxf, export_ifc
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); app.processEvents()
    try:
        w._no_modal_dialogs = True
        assert _find_action(w, 'Αρχείο / Εξαγωγή / IFC για μηχανικούς (BIM)…') is not None
        assert _find_action(w, 'Αρχείο / Εξαγωγή / DXF κατόψεις ανά όροφο…') is not None
        w._open_checked(PROJECT); app.processEvents()
        r = export_ifc(w, str(tmp_path / 'a'))
        assert r and os.path.exists(tmp_path / 'a.ifc') and 'IFC:' in w.statusBar().currentMessage()
        d = export_dxf(w, str(tmp_path / 'b.dxf'))
        assert d and all(os.path.exists(p) for p in d['files'])
        assert export_ifc(w) is None                                         # no dialog in tests: nothing written
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_ifc_is_written_in_metres_and_reads_at_true_size(ifc_file, doc):
    # Before 30/10 the file said millimetres while the values were metres: 1000× too small in ArchiCAD / Revit.
    import ifcopenshell.geom
    import ifcopenshell.util.unit
    f, _s = ifc_file
    assert ifcopenshell.util.unit.calculate_unit_scale(f) == 1.0
    wall = next(w for w in f.by_type('IfcWall'))
    s = ifcopenshell.geom.settings(); s.set(s.USE_WORLD_COORDS, True)
    v = ifcopenshell.geom.create_shape(s, wall).geometry.verts
    src = doc.get(wall.Tag)
    assert max(v[2::3]) - min(v[2::3]) == pytest.approx(float(src.params['height']), abs=0.05) or src.params.get('curve')
