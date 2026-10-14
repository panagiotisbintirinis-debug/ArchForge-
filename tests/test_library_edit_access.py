"""Visual library identity and direct, reversible object editing."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import copy
import pytest
from PySide6.QtWidgets import QApplication
from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.ui.main_window import MainWindow
from archforge.library import assets

@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    assets._CACHE.clear()
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def test_library_has_mesh_previews_and_category_icons(window):
    window._seed_core_library()
    tree = window._library_tree
    leaves = []
    def walk(item):
        assert not item.icon(0).isNull(), item.text(0)
        if item.data(0, 0x0100): leaves.append(item)
        for i in range(item.childCount()): walk(item.child(i))
    for i in range(tree.topLevelItemCount()): walk(tree.topLevelItem(i))
    assert any(i.data(0, 0x0100)[0] == 'asset' for i in leaves)
    window._library_search.setText('Ψυγειο')
    previews = window._library_previews
    assert previews.count() == 1
    window._library_preview_action(previews.item(0))
    assert window.plan_view.controller.tool == 'library_place'
    from archforge.ui.library_icons import asset_icon
    records = assets.list_assets()
    a = asset_icon(records[0]['id']).pixmap(48, 48).toImage()
    b = asset_icon(records[-1]['id']).pixmap(48, 48).toImage()
    assert a != b


def test_object_menus_offer_finish_and_transform(window):
    for kind in ('library_object', 'cabinet', 'box', 'door', 'window'):
        obj = Entity(kind, {}, name=kind)
        window.doc.entities[obj.id] = obj
        for view in ('plan', 'pbr'):
            # Registry contract (build_menu needs valid geometry to describe an entity).
            from archforge.ui.object_context_menu import object_context_actions
            ids = {a['id'] for a in object_context_actions(kind, view) if a}
            assert {'materials', 'transform'} <= ids


def test_transform_is_one_undo_and_cancel_is_inert(window):
    from archforge.ui.object_transform import TransformDialog
    obj = Entity('box', dict(x=1., y=2., z=0., width=1., depth=2., height=3., rotation=0.))
    window.stack.execute(AddEntity(obj))
    before = copy.deepcopy(window.doc.get(obj.id).params)
    dialog = TransformDialog(window, obj.id)
    dialog.fields['x'].setValue(4.)
    dialog.fields['rotation'].setValue(45.)
    dialog.fields['scale'].setValue(2.)
    dialog.reject()
    assert window.doc.get(obj.id).params == before
    dialog = TransformDialog(window, obj.id)
    dialog.fields['x'].setValue(4.)
    dialog.fields['rotation'].setValue(45.)
    dialog.fields['scale'].setValue(2.)
    dialog.accept()
    p = window.doc.get(obj.id).params
    assert (p['x'], p['y'], p['rotation'], p['width'], p['height']) == pytest.approx((4, 2, 45, 2, 6))
    window.stack.undo()
    assert window.doc.get(obj.id).params == before
    window.stack.redo()
    assert window.doc.get(obj.id).params['width'] == 2


def test_color_changes_only_chosen_part_and_undo_removes_project_material(window):
    from archforge.ui.object_finish import apply_color
    from archforge.rendering.materials import MATERIAL_PRESETS, material_spec
    mid = next(k for k, v in MATERIAL_PRESETS.items() if v.get('pattern'))
    obj = Entity('cabinet', dict(x=0., y=0., z=0., width=.6, depth=.6, height=.9,
                               rotation=0., cabinet_type='base', material_id=mid, surface_materials={'front': mid}))
    window.stack.execute(AddEntity(obj))
    before = copy.deepcopy(window.doc.get(obj.id).params)
    result = apply_color(window, obj.id, '#123456', 'front')
    p = window.doc.get(obj.id).params
    assert p['material_id'] == mid
    assert p['surface_materials']['front'] == result
    spec = material_spec(result, window.doc)
    assert spec['color'] == '#123456'
    assert spec['pattern'] == MATERIAL_PRESETS[mid]['pattern']
    window.stack.undo()
    assert window.doc.get(obj.id).params == before
    assert result not in window.doc.materials


def test_color_variant_survives_save_load(window, tmp_path):
    from archforge.ui.object_finish import apply_color
    from archforge.core.model import Document
    from archforge.rendering.materials import material_spec
    obj = Entity('box', dict(x=1., y=2., z=0., width=1., depth=2., height=3., rotation=0.))
    window.stack.execute(AddEntity(obj))
    mid = apply_color(window, obj.id, '#abcdef')
    path = tmp_path / 'color.archforge'
    window.doc.save(path)
    loaded = Document.load(path)
    assert loaded.get(obj.id).params['material_id'] == mid
    assert material_spec(mid, loaded)['color'] == '#abcdef'


def test_menu_transform_opens_real_editor(window):
    obj = Entity('box', dict(x=1., y=2., z=0., width=1., depth=2., height=3., rotation=0.))
    window.stack.execute(AddEntity(obj))
    window._handle_object_context_action(obj.id, 'transform')
    assert window._transform_dialog.isVisible()
    assert set(window._transform_dialog.fields) == {'x', 'y', 'z', 'rotation', 'scale'}
    window._transform_dialog.reject()


def test_color_button_uses_texture_preview(window, monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog
    from archforge.rendering.materials import MATERIAL_PRESETS, material_spec
    obj = Entity('box', dict(x=0., y=0., z=0., width=1., depth=1., height=1., rotation=0.))
    window.stack.execute(AddEntity(obj))
    mid = next(k for k,v in MATERIAL_PRESETS.items() if v.get('pattern'))
    monkeypatch.setattr(QColorDialog, 'getColor', lambda *_args: QColor('#abcdef'))
    def choose():
        listing = window._materials_list
        category = next(c for c in listing.parent().findChildren(__import__('PySide6.QtWidgets',fromlist=['QComboBox']).QComboBox)
                        if c.findText(MATERIAL_PRESETS[mid]['category']) >= 0)
        category.setCurrentText(MATERIAL_PRESETS[mid]['category'])
        item = next(listing.item(i) for i in range(listing.count()) if listing.item(i).data(0x0100) == mid)
        listing.setCurrentItem(item)
        window._materials_color_button.click()
    QTimer.singleShot(0, choose)
    window._open_materials(obj.id)
    spec = material_spec(window.doc.get(obj.id).params['material_id'], window.doc)
    assert spec['color'] == '#abcdef'
    assert spec['pattern'] == MATERIAL_PRESETS[mid]['pattern']


def test_transform_uses_current_document_position(window):
    from archforge.ui.object_transform import TransformDialog
    from archforge.core.commands import MoveEntities
    obj = Entity('box', dict(x=1., y=2., z=0., width=1., depth=1., height=1., rotation=0.))
    window.stack.execute(AddEntity(obj))
    dialog = TransformDialog(window, obj.id)
    window.stack.execute(MoveEntities([obj.id], 10., 0.))
    dialog.fields['x'].setValue(4.)
    dialog.accept()
    assert window.doc.get(obj.id).params['x'] == pytest.approx(4.)
    window.stack.undo()
    assert window.doc.get(obj.id).params['x'] == pytest.approx(11.)


def test_eyedropper_samples_without_edit_and_paints_one_face(window):
    from archforge.ui.material_brush import MaterialBrush
    from archforge.rendering.materials import MATERIAL_PRESETS
    mid=next(k for k,v in MATERIAL_PRESETS.items() if v.get('pattern'))
    source=Entity('box',dict(x=0.,y=0.,z=0.,width=1.,depth=1.,height=1.,rotation=0.,material_id=mid))
    target=Entity('box',dict(x=3.,y=0.,z=0.,width=1.,depth=1.,height=1.,rotation=0.))
    window.stack.execute(AddEntity(source)); window.stack.execute(AddEntity(target))
    brush=MaterialBrush(window); before=len(window.stack.done)
    brush.sample(source.id)
    assert len(window.stack.done)==before
    brush.apply(target.id,'top')
    assert window.doc.get(target.id).params['surface_materials']=={'top':mid}
    assert 'material_id' not in window.doc.get(target.id).params
    window.stack.undo()
    assert 'surface_materials' not in window.doc.get(target.id).params
    brush.whole_object=True; brush.apply(target.id,'top')
    assert window.doc.get(target.id).params['material_id']==mid


def test_eyedropper_copies_original_library_part_and_cancels(window):
    from archforge.library import assets
    from archforge.ui.material_brush import MaterialBrush
    from archforge.rendering.materials import material_spec
    triangles=[((0,0,0),(1,0,0),(0,1,1))]
    aid,size=assets.store_asset('Sample',triangles,{'source':'test'},colors=['#123456'])
    obj=Entity('library_object',dict(x=0.,y=0.,z=0.,rotation=0.,width=size[0],depth=size[1],height=size[2],asset=aid))
    target=Entity('box',dict(x=3.,y=0.,z=0.,width=1.,depth=1.,height=1.,rotation=0.))
    window.stack.execute(AddEntity(obj)); window.stack.execute(AddEntity(target))
    brush=window._start_material_brush(); brush.sample(obj.id,'part0')
    mid=brush.apply(target.id)
    assert material_spec(mid,window.doc)['color']=='#123456'
    window._cancel_interactions()
    assert window._material_brush is None
    window.stack.undo()
    assert mid not in window.doc.materials


def test_material_preview_has_a_textured_cube(window):
    from archforge.ui.material_preview import MaterialPreview
    from archforge.rendering.materials import MATERIAL_PRESETS
    preview=MaterialPreview(doc=window.doc); preview.resize(240,200)
    mid=next(k for k,v in MATERIAL_PRESETS.items() if v.get('pattern'))
    preview.set_material(mid)
    assert preview.texture is not None
    assert not preview.grab().isNull()


def test_brush_material_reaches_only_the_clicked_3d_face(window):
    from archforge.ui.material_brush import MaterialBrush
    from archforge.rendering.scene import build_pbr_scene_payload
    from archforge.rendering.materials import MATERIAL_PRESETS
    mid=next(k for k,v in MATERIAL_PRESETS.items() if v.get('pattern'))
    source=Entity('box',dict(x=0.,y=0.,z=0.,width=1.,depth=1.,height=1.,rotation=0.,material_id=mid))
    target=Entity('box',dict(x=3.,y=0.,z=0.,width=1.,depth=1.,height=1.,rotation=0.))
    window.stack.execute(AddEntity(source)); window.stack.execute(AddEntity(target))
    brush=MaterialBrush(window); brush.sample(source.id); brush.apply(target.id,'top')
    payload=build_pbr_scene_payload(window.pbr_view._evaluation_cache.sync(window.doc),(),doc=window.doc)
    parts=[o for o in payload['objects'] if o['id']==target.id]
    assert len(parts)==6
    assert [o['surfaces'][0] for o in parts if o['material'].get('material_id')==mid]==['top']
    window.stack.undo()
    payload=build_pbr_scene_payload(window.pbr_view._evaluation_cache.sync(window.doc),(),doc=window.doc)
    assert not any(o['material'].get('material_id')==mid for o in payload['objects'] if o['id']==target.id)


def test_real_plan_clicks_sample_and_apply_then_escape(window):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    from archforge.rendering.materials import MATERIAL_PRESETS
    mid=next(iter(MATERIAL_PRESETS))
    source=Entity('box',dict(x=0.,y=0.,z=0.,width=.6,depth=.6,height=.6,rotation=0.,material_id=mid))
    target=Entity('box',dict(x=1.5,y=0.,z=0.,width=.6,depth=.6,height=.6,rotation=0.))
    window.stack.execute(AddEntity(source));window.stack.execute(AddEntity(target))
    window.resize(1280,960); window.show(); window.plan_view.redraw(); QApplication.processEvents()
    brush=window._start_material_brush(); before=len(window.stack.done)
    QTest.mouseClick(window.plan_view.viewport(),Qt.MouseButton.LeftButton,pos=window.plan_view.mapFromScene(QPointF(0,0)))
    assert brush.sampled is not None and len(window.stack.done)==before
    QTest.mouseClick(window.plan_view.viewport(),Qt.MouseButton.LeftButton,pos=window.plan_view.mapFromScene(QPointF(1.5,0)))
    assert window.doc.get(target.id).params['material_id']==mid
    QTest.keyClick(window.plan_view.viewport(),Qt.Key.Key_Escape)
    assert window._material_brush is None


def test_webengine_bridge_routes_surface_painting_to_commands(window):
    from archforge.ui.pbr_viewport import PBRInteractionBridge
    from archforge.rendering.materials import MATERIAL_PRESETS
    mid=next(iter(MATERIAL_PRESETS))
    source=Entity('box',dict(x=0.,y=0.,z=0.,width=1.,depth=1.,height=1.,rotation=0.,material_id=mid))
    target=Entity('box',dict(x=2.,y=0.,z=0.,width=1.,depth=1.,height=1.,rotation=0.))
    window.stack.execute(AddEntity(source));window.stack.execute(AddEntity(target))
    window._start_material_brush()
    bridge=PBRInteractionBridge(window.pbr_view)
    before=len(window.stack.done)
    bridge.materialBrushClick(source.id,'top',0.,0.)
    assert len(window.stack.done)==before
    bridge.materialBrushClick(target.id,'top',2.,0.)
    assert window.doc.get(target.id).params['surface_materials']=={'top':mid}
    assert len(window.stack.done)==before+1
    window.stack.undo()
    assert 'surface_materials' not in window.doc.get(target.id).params
