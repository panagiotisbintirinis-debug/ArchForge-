"""MAT2: stone masonry and tile joints visible at real size (2D swatch + 3D texture)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.rendering.materials import MATERIAL_PRESETS, PATTERNED_CATEGORIES, materials_in_category
from archforge.rendering.patterns import PATTERN_TYPES, pattern_geometry, pattern_key, validate_pattern


def _app():
    return QApplication.instance() or QApplication([])


def _inside(pt, poly):
    x, y = pt
    hit = False
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i - 1], poly[i]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def test_every_stone_and_tile_preset_has_a_valid_pattern():
    for category in PATTERNED_CATEGORIES:
        rows = materials_in_category(category)
        assert rows, category
        for material_id, spec in rows:
            assert 'pattern' in spec, material_id
            assert validate_pattern(spec['pattern']) == [], (material_id, validate_pattern(spec['pattern']))
    for material_id, spec in MATERIAL_PRESETS.items():
        if 'pattern' in spec:
            assert validate_pattern(spec['pattern']) == [], material_id


def test_stones_use_different_masonry_and_tiles_have_real_sizes():
    stone_types = {spec['pattern']['type'] for _, spec in materials_in_category('Πέτρα')}
    assert {'rubble', 'ashlar', 'polygonal', 'slab'} <= stone_types
    sizes = {(spec['pattern']['unit_w'], spec['pattern']['unit_h'], spec['pattern']['type'])
             for spec in MATERIAL_PRESETS.values() if 'pattern' in spec}
    assert (0.60, 0.60, 'tiles') in sizes                     # 60x60 floor
    assert (0.15, 0.075, 'tiles') in sizes                    # metro 7.5x15
    assert (1.20, 0.20, 'planks') in sizes                    # wood-look 20x120
    assert (1.20, 0.60, 'tiles') in sizes                     # cement-look large format
    metro = MATERIAL_PRESETS['tile_bath_white']['pattern']
    assert metro['offset'] == pytest.approx(0.5)


def test_validate_pattern_rejects_nonsense():
    good = dict(MATERIAL_PRESETS['porcelain_matt_white']['pattern'])
    assert validate_pattern(good) == []
    assert validate_pattern({**good, 'type': 'zigzag'})
    assert validate_pattern({**good, 'unit_w': 60})            # centimetres by mistake
    assert validate_pattern({**good, 'joint': 0.4})
    assert validate_pattern({**good, 'offset': 1.5})


@pytest.mark.parametrize('material_id', ['stone_drywall', 'limestone_light', 'stone_karystos',
                                         'stone_pelion', 'tile_bath_white', 'tile_wood_look'])
def test_geometry_is_deterministic_and_in_metres(material_id):
    spec = MATERIAL_PRESETS[material_id]
    a = pattern_geometry(spec['pattern'], spec['color'], seed=material_id)
    b = pattern_geometry(spec['pattern'], spec['color'], seed=material_id)
    assert a == b
    other = pattern_geometry(spec['pattern'], spec['color'], seed=material_id + '_x')
    assert other['cells'] != a['cells']
    assert a['type'] in PATTERN_TYPES
    # One period is a wall-sized patch of metres, not pixels or centimetres.
    assert 0.3 <= a['width'] <= 3.0 and 0.3 <= a['height'] <= 3.0
    unit = max(spec['pattern']['unit_w'], spec['pattern']['unit_h'])
    for cell in a['cells']:
        for x, y in cell['pts']:
            assert -2 * unit <= x <= a['width'] + 2 * unit
            assert -2 * unit <= y <= a['height'] + 2 * unit
    # Joints are visible but most of the surface is stone / tile.
    n, hits = 30, 0
    for i in range(n):
        for j in range(n):
            p = ((i + 0.5) / n * a['width'], (j + 0.5) / n * a['height'])
            hits += any(_inside(p, c['pts']) for c in a['cells'])
    assert 0.55 * n * n <= hits <= n * n
    if a["joint"] >= 0.007:          # wide mortar joints are hit by the sampling grid
        assert hits < n * n
    # Stone to stone the tone changes.
    assert len({c['color'] for c in a['cells']}) > 3


def test_tile_joint_and_size_are_exact():
    spec = MATERIAL_PRESETS['porcelain_matt_white']
    g = pattern_geometry(spec['pattern'], spec['color'], seed='porcelain_matt_white')
    p = spec['pattern']
    for cell in g['cells']:
        xs = [x for x, _ in cell['pts']]
        ys = [y for _, y in cell['pts']]
        assert max(xs) - min(xs) == pytest.approx(p['unit_w'] - p['joint'], abs=1e-4)
        assert max(ys) - min(ys) == pytest.approx(p['unit_h'] - p['joint'], abs=1e-4)
    assert g['width'] == pytest.approx(round(g['width'] / p['unit_w']) * p['unit_w'])


def test_pattern_key_is_stable_and_changes_with_params():
    spec = MATERIAL_PRESETS['sandstone']
    k = pattern_key('sandstone', spec['pattern'], spec['color'])
    assert k == pattern_key('sandstone', dict(spec['pattern']), spec['color'])
    assert k != pattern_key('sandstone', {**spec['pattern'], 'joint': 0.02}, spec['color'])


def _distinct_colors(image, step=3):
    return {image.pixel(x, y) for x in range(0, image.width(), step) for y in range(0, image.height(), step)}


def test_swatch_shows_the_pattern_not_a_flat_colour():
    _app()
    from archforge.ui.pattern_swatch import material_swatch
    for material_id in ('stone_drywall', 'stone_cladding', 'tile_bath_white', 'porcelain_matt_white', 'tile_wood_look'):
        image = material_swatch(material_id, 120, 60)
        assert image.width() == 120 and image.height() == 60
        assert len(_distinct_colors(image)) > 8, material_id
    plain = material_swatch('plaster_white', 40, 20)
    assert len(_distinct_colors(plain, 1)) == 1


def test_pattern_reaches_the_3d_payload():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document()
    stack = CommandStack(doc)
    wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0, 'z': 0.0, 'height': 2.8, 'thickness': 0.3,
                           'surface_materials': {'exterior': 'stone_drywall', 'interior': 'tile_bath_white'}})
    plain = Entity('wall', {'x1': 0, 'y1': 2, 'x2': 4, 'y2': 2, 'z': 0.0, 'height': 2.8, 'thickness': 0.3,
                            'material_id': 'plaster_white'})
    stack.execute(AddEntity(wall))
    stack.execute(AddEntity(plain))
    payload = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)
    mats = [o['material'] for o in payload['objects'] if o['id'] == wall.id]
    by_id = {m.get('material_id'): m for m in mats}
    assert {'stone_drywall', 'tile_bath_white'} <= set(by_id)
    for material_id in ('stone_drywall', 'tile_bath_white'):
        m = by_id[material_id]
        assert m['pattern'] == MATERIAL_PRESETS[material_id]['pattern']
        geo = payload['patterns'][m['pattern_key']]
        assert geo['cells'] and geo['width'] > 0
    for o in payload['objects']:
        if o['id'] == plain.id:
            assert 'pattern_key' not in o['material']
    # The 3D page knows how to turn it into a real-size texture.
    from archforge.ui.pbr_viewport import _PBR_HTML
    for needle in ('payload.patterns', 'function withMetricUVs', 'function patternTexturesFor',
                   'RepeatWrapping', 'bumpMap'):
        assert needle in _PBR_HTML, needle


def test_materials_dialog_shows_swatches(monkeypatch):
    app = _app()
    from archforge.ui.main_window import MainWindow
    monkeypatch.setattr(QDialog, 'exec', lambda self: QDialog.DialogCode.Rejected)
    w = MainWindow()
    try:
        wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0, 'z': 0.0, 'height': 2.8, 'thickness': 0.3,
                               'material_id': 'stone_pelion'})
        w.stack.execute(AddEntity(wall))
        w._open_materials(wall.id)
        app.processEvents()
        lst = w._materials_list
        assert lst.count() == len(materials_in_category('Πέτρα'))
        assert all(not lst.item(i).icon().isNull() for i in range(lst.count()))
        image = w._materials_preview.pixmap().toImage()
        assert len(_distinct_colors(image)) > 8
    finally:
        w.hide()
