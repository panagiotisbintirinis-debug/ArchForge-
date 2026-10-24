"""Owner-requested library designs: real geometry, distinct thumbnails and editable state."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from archforge.architecture import joinery
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity

DESIGNS = ('four_panel', 'six_panel', 'horizontal', 'vertical', 'glazed', 'three_lites')


def test_library_contains_new_designs_and_preserves_existing_keys():
    assert len(joinery.PRESETS) >= 39
    keys = [p[0] for p in joinery.PRESETS]
    assert len(keys) == len(set(keys))
    for key in ('w_casement_1', 'w_shutters', 'd_panel_80', 'd_pocket', 'd_folding'):
        assert joinery.preset(key)['kind'] in ('door', 'window')
    for design in DESIGNS:
        assert any(p[-1].get('leaf_design') == design for p in joinery.PRESETS)


@pytest.mark.parametrize('design', DESIGNS)
def test_door_design_is_real_geometry_with_glazing_voids_and_moves_with_leaf(design):
    p = dict(width=0.9, height=2.1, opening_type='interior_flush', leaf_design=design)
    boxes = joinery.joinery_boxes('door', p, 0.25)
    plain = joinery.joinery_boxes('door', dict(p, leaf_design='plain'), 0.25)
    assert boxes != plain
    if design in ('glazed', 'three_lites'):
        glass = [(lo, hi) for role, lo, hi in boxes if role == 'glass']
        assert len(glass) == (1 if design == 'glazed' else 3)
        # No opaque leaf box behind the centre of any glass pane.
        for lo, hi in glass:
            x, z = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
            assert not any(a[0] < x < b[0] and a[2] < z < b[2]
                           for role, a, b in boxes if role == 'leaf')
    posed = joinery.joinery_boxes_posed('door', p, 0.25, angle=65)
    assert all(pose is not None for role, _a, _b, pose in posed if role != 'frame')


def test_design_edit_undo_redo_and_file_round_trip(tmp_path):
    doc = Document(); stack = CommandStack(doc)
    wall = Entity('wall', dict(x1=0, y1=0, x2=6, y2=0, z=0, height=2.7, thickness=0.25))
    stack.execute(AddEntity(wall))
    door = Entity('door', dict(offset=3, width=0.9, height=2.1, sill=0,
                              opening_type='interior_flush'), parent_id=wall.id)
    stack.execute(AddEntity(door))
    original = dict(doc.get(door.id).params)
    stack.execute(UpdateEntity(door.id, {'leaf_design': 'three_lites'}))
    stack.undo(); assert doc.get(door.id).params == original
    stack.redo(); assert doc.get(door.id).params['leaf_design'] == 'three_lites'
    path = tmp_path / 'design.archforge'; doc.save(path)
    restored = Document.load(path)
    assert restored.get(door.id).params == doc.get(door.id).params
    before = dict(doc.get(door.id).params)
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(door.id, {'leaf_design': 'invented'}))
    assert doc.get(door.id).params == before


def test_opening_icons_show_the_chosen_design_instead_of_one_generic_door():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.library_icons import library_icon
    app = QApplication.instance() or QApplication([])
    keys = ('d_flush_90', 'd_classic_4', 'd_classic_6', 'd_modern_horizontal', 'd_glazed', 'd_three_lites')
    images = [library_icon(('opening', key), size=100).pixmap(100, 100).toImage() for key in keys]
    assert len({bytes(im.constBits()) for im in images}) == len(keys)
    app.processEvents()


@pytest.mark.parametrize('key', [p[0] for p in joinery.PRESETS[19:]])
def test_new_presets_place_from_the_library_tool_and_undo_as_one_operation(key):
    from archforge.core.viewport import PointerController, PointerEvent
    doc = Document(); stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('wall', dict(x1=0, y1=0, x2=6, y2=0, z=0, height=2.7, thickness=0.25))))
    pr = joinery.preset(key)
    controller = PointerController(doc, stack); controller.set_tool(pr['kind'])
    controller.opening_preset = pr
    controller.pointer_down(PointerEvent(3, 0)); result = controller.pointer_up(PointerEvent(3, 0))
    opening = doc.get(result.entity_id)
    assert all(opening.params[k] == v for k, v in pr['params'].items())
    assert (opening.params['width'], opening.params['height']) == (pr['width'], pr['height'])
    stack.undo(); assert opening.id not in doc.entities
    stack.redo(); assert doc.get(opening.id).params == opening.params


def test_leaf_design_property_is_selectable_and_type_switch_clears_incompatible_design():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    def field(label):
        for i in range(window.form.rowCount()):
            item = window.form.itemAt(i, window.form.ItemRole.LabelRole)
            if item is not None and item.widget() is not None and item.widget().text() == label:
                return window.form.itemAt(i, window.form.ItemRole.FieldRole).widget()
        raise AssertionError(label)
    try:
        wall = Entity('wall', dict(x1=0, y1=0, x2=6, y2=0, z=0, height=2.7, thickness=0.25))
        window.stack.execute(AddEntity(wall))
        door = Entity('door', dict(offset=3, width=0.9, height=2.1, sill=0,
                                  opening_type='interior_flush'), parent_id=wall.id)
        window.stack.execute(AddEntity(door)); window.doc.select([door.id]); window.refresh_inspector()
        combo = field('Σχέδιο φύλλου'); combo.setCurrentIndex(combo.findData('glazed'))
        assert window.doc.get(door.id).params['leaf_design'] == 'glazed'
        window.stack.undo(); assert 'leaf_design' not in window.doc.get(door.id).params
        window.stack.redo(); window.refresh_inspector()
        combo = field('Τύπος κουφώματος'); combo.setCurrentIndex(combo.findData('balcony_casement'))
        assert window.doc.get(door.id).params['leaf_design'] == 'auto'
        window.stack.undo(); assert window.doc.get(door.id).params['leaf_design'] == 'glazed'
    finally:
        window._mark_clean(); window.close(); app.processEvents()
