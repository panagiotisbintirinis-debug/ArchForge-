"""LIB5: icons in the library tree and «Ιδιότητες υλικού» from the material icon.

Owner: «δεν ξέρεις τι διαλέγεις» (a thumbnail on every library object) and
«ιδιότητες με πρόσβαση σε εικονίδιο και μοτίβα/υφές» (tile size, joint,
colour, direction).
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

from archforge.library import assets
from archforge.library.thumbnail import thumbnail_faces
from archforge.rendering import user_materials as um
from archforge.rendering.materials import MATERIAL_PRESETS, material_spec


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    assets._CACHE.clear()
    um.reload()
    yield
    monkeypatch.delenv('ARCHFORGE_DATA')
    um.reload()


def _box(w, d, h, x0=0.0):
    c = [(x0 + x * w, y * d, z * h) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    quads = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
    return [[c[q[0]], c[q[i]], c[q[i + 1]]] for q in quads for i in (1, 2)]


def _leaves(tree):
    out = []

    def walk(item):
        if item.childCount() == 0 and item.data(0, 0x0100):
            out.append(item)
        for i in range(item.childCount()):
            walk(item.child(i))
    walk(tree.invisibleRootItem())
    return out


# ------------------------------------------------------------ thumbnail ---

def test_thumbnail_fits_the_icon_draws_back_to_front_and_keeps_part_colours():
    tris = _box(2.0, 0.9, 0.8) + _box(0.3, 0.3, 1.6, x0=2.2)
    colors = ['#aa2222'] * 12 + ['#2222aa'] * 12
    asset_id, _size = assets.store_asset('Δοκιμή', tris, {'source': 'test'}, colors=colors)
    faces = thumbnail_faces(assets.load_asset(asset_id), size=48, margin=3)
    assert faces
    xs = [x for pts, _c in faces for x, _y in pts]
    ys = [y for pts, _c in faces for _x, y in pts]
    assert min(xs) >= 2.99 and max(xs) <= 45.01 and min(ys) >= 2.99 and max(ys) <= 45.01
    # the longest side spans the icon (the picture is not tiny in a corner)
    assert max(max(xs) - min(xs), max(ys) - min(ys)) == pytest.approx(42, abs=0.01)
    reds = [c for _p, c in faces if int(c[1:3], 16) > int(c[5:7], 16)]
    blues = [c for _p, c in faces if int(c[5:7], 16) > int(c[1:3], 16)]
    assert reds and blues                    # each part keeps its colour, shaded
    assert len({c for _p, c in faces}) > 2   # faces lit differently: reads as 3D
    # the top face of the tall post is drawn after (over) the box behind it
    assert thumbnail_faces({'vertices': [], 'triangles': []}) == []


def test_thumbnail_is_cached_on_disk_once():
    app = QApplication.instance() or QApplication([])
    from archforge.ui.library_icons import asset_thumbnail
    asset_id, _ = assets.store_asset('Κουτί', _box(1, 1, 1), {'source': 'test'})
    image = asset_thumbnail(asset_id, 40)
    assert image is not None and image.width() == 40
    cached = assets.asset_dir() / 'thumbs' / f'{asset_id}_40.png'
    assert cached.is_file()
    # opaque pixels in the middle: something is drawn
    assert image.pixelColor(20, 20).alpha() > 0
    assert asset_thumbnail('a_missing', 40) is None
    app.processEvents()


# -------------------------------------------------- material properties ---

def test_properties_of_a_builtin_material_become_the_users_copy():
    original = dict(MATERIAL_PRESETS['ceramic_light']['pattern'])
    spec = um.editable_spec('ceramic_light')
    edited = um.with_properties(spec, color='#ddeeff', unit_w=0.30, unit_h=0.60, joint=0.004,
                                joint_color='#202020', rotated=True, offset=0.5)
    assert edited['pattern']['unit_w'] == pytest.approx(0.60)     # laid the other way
    assert edited['pattern']['unit_h'] == pytest.approx(0.30)
    assert edited['pattern']['joint'] == pytest.approx(0.004)
    assert edited['pattern']['joint_color'] == '#202020'
    assert edited['pattern']['offset'] == pytest.approx(0.5)
    new_id = um.save_properties('ceramic_light', edited)
    assert um.is_user_material(new_id)
    saved = material_spec(new_id)
    assert saved['name'].endswith('(δικό μου)') and saved['base'] == 'ceramic_light'
    assert saved['color'] == '#ddeeff' and saved['pattern']['unit_w'] == pytest.approx(0.60)
    assert MATERIAL_PRESETS['ceramic_light']['pattern'] == original   # built-in unchanged
    # editing the user's own material saves in place
    again = um.with_properties(um.editable_spec(new_id), joint=0.002)
    assert um.save_properties(new_id, again) == new_id
    assert material_spec(new_id)['pattern']['joint'] == pytest.approx(0.002)


def test_invalid_pattern_is_refused_and_plain_materials_can_get_a_pattern():
    spec = um.editable_spec('ceramic_light')
    with pytest.raises(ValueError):
        um.with_properties(spec, joint=0.2)                      # wider than allowed
    with pytest.raises(ValueError):
        um.with_properties(spec, unit_w=0.02, unit_h=0.02, joint=0.015)   # joint > half a tile
    plain = next(k for k, v in MATERIAL_PRESETS.items() if not v.get('pattern'))
    tiled = um.with_properties(um.editable_spec(plain), pattern_type='tiles', unit_w=0.2, unit_h=0.2)
    assert tiled['pattern']['type'] == 'tiles'
    assert 'pattern' not in um.with_properties(tiled, pattern_type='')


# ----------------------------------------------------------------- UI ---

def test_every_library_leaf_has_an_icon_and_materials_open_their_properties():
    app = QApplication.instance() or QApplication([])
    from archforge.ui.main_window import MainWindow
    from archforge.ui.material_properties import MaterialPropertiesDialog
    window = MainWindow()
    try:
        window._seed_core_library()
        tree = window._library_tree
        assert tree.iconSize().width() >= 32
        leaves = _leaves(tree)
        kinds = {leaf.data(0, 0x0100)[0] for leaf in leaves}
        assert {'asset', 'material', 'opening', 'tool', 'structural'} <= kinds
        assert all(not leaf.icon(0).isNull() for leaf in leaves)
        material_leaf = next(l for l in leaves if l.data(0, 0x0100) == ('material', 'ceramic_light'))
        menu = window._library_tree_menu(material_leaf)
        assert any('Ιδιότητες υλικού' in a.text() for a in menu.actions())
        asset_leaf = next(l for l in leaves if l.data(0, 0x0100)[0] == 'asset')
        assert not any('Ιδιότητες υλικού' in a.text() for a in window._library_tree_menu(asset_leaf).actions())

        dialog = MaterialPropertiesDialog(window, 'ceramic_light', window.doc)
        dialog.unit_w.setValue(30); dialog.unit_h.setValue(60); dialog.joint.setValue(3)
        dialog.direction.setCurrentIndex(1)
        dialog.set_colors(color='#f0f0f0', joint_color='#303030')
        dialog.unit_w.setValue(2); dialog.unit_h.setValue(2); dialog.joint.setValue(15)
        assert not dialog.ok_button.isEnabled() and dialog.problem.text()   # joint > half a tile
        dialog.unit_w.setValue(30); dialog.unit_h.setValue(60); dialog.joint.setValue(3)
        assert dialog.ok_button.isEnabled()
        dialog._accept()
        saved = window._edit_material_properties('ceramic_light', dialog)
        spec = material_spec(saved)
        assert spec['pattern']['unit_w'] == pytest.approx(0.60) and spec['color'] == '#f0f0f0'
        mine = [l for l in _leaves(window._library_tree) if l.data(0, 0x0100) == ('material', saved)]
        assert mine and not mine[0].icon(0).isNull()             # the copy is in the library at once
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_editing_a_material_the_project_uses_updates_it_with_one_undo():
    app = QApplication.instance() or QApplication([])
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.ui.main_window import MainWindow
    from archforge.ui.material_properties import MaterialPropertiesDialog
    window = MainWindow()
    try:
        mine = um.save_properties('ceramic_light', um.with_properties(um.editable_spec('ceramic_light'), joint=0.003))
        wall = Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.5, 'thickness': 0.2})
        window.stack.execute(AddEntity(wall))
        window.doc.select([wall.id])
        window._apply_material_to_selection(mine)
        assert mine in window.doc.materials
        dialog = MaterialPropertiesDialog(window, mine, window.doc)
        dialog.joint.setValue(6)
        dialog._accept()
        window._edit_material_properties(mine, dialog)
        assert window.doc.materials[mine]['pattern']['joint'] == pytest.approx(0.006)
        window.stack.undo()
        assert window.doc.materials[mine]['pattern']['joint'] == pytest.approx(0.003)
    finally:
        window._mark_clean(); window.close(); app.processEvents()
