"""Parametric kitchen cabinets and wardrobes."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.kitchen.cabinets import (FRONT, GAP, WORKTOP, auto_doors, cabinet_boxes, cabinet_mesh,
                                        default_params, snap_to_neighbours, wall_aligned)


def _extent(verts):
    return [max(v[i] for v in verts) - min(v[i] for v in verts) for i in range(3)]


def _fronts(p):
    return [(lo, hi) for role, lo, hi in cabinet_boxes(p) if role == 'front']


@pytest.mark.parametrize('kind', ['base', 'drawers', 'sink', 'wall', 'tall', 'wardrobe'])
def test_every_type_builds_at_its_nominal_size(kind):
    p = default_params(kind)
    verts, tris, roles = cabinet_mesh(p)
    w, d, h = _extent(verts)
    assert w == pytest.approx(p['width'])
    assert h == pytest.approx(p['height'] + (WORKTOP if p['worktop'] else 0.0))
    assert d >= p['depth'] - 1e-9            # handles and worktop overhang stick out in front
    assert {'carcass', 'front'} <= set(roles)
    Document().add(Entity('cabinet', p))      # schema accepts the defaults


def test_resizing_keeps_panel_thickness_and_door_gaps():
    narrow, wide = default_params('base', width=0.6), default_params('base', width=0.9)
    assert (narrow['doors'], wide['doors']) == (1, 2)
    for p in (narrow, wide):
        for lo, hi in _fronts(p):
            assert hi[1] - lo[1] == pytest.approx(FRONT)
        carcass = [hi[0] - lo[0] for role, lo, hi in cabinet_boxes(p) if role == 'carcass' and hi[2] - lo[2] > 0.5]
        assert min(carcass) == pytest.approx(0.018)
    doors = sorted(_fronts(wide), key=lambda f: f[0][0])[-2:]
    assert doors[1][0][0] - doors[0][1][0] == pytest.approx(2 * GAP)
    assert auto_doors('wardrobe', 1.5) == 3


def test_cabinet_backs_onto_the_wall_and_butts_against_a_neighbour():
    doc = Document(); stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'z': 0.0, 'x2': 5.0, 'y2': 0.0, 'height': 2.7, 'thickness': 0.2})))
    x, y, rot = wall_aligned(doc, 1.0, 0.7, 0.6)
    assert (x, y) == pytest.approx((1.0, 0.1 + 0.3)) and rot == pytest.approx(180.0)
    p = default_params('base', x, y, rotation=rot)
    verts = cabinet_mesh(p)[0]
    assert min(v[1] for v in verts) == pytest.approx(0.1 - 1e-9, abs=1e-6) or min(v[1] for v in verts) >= 0.1 - 1e-6
    stack.execute(AddEntity(Entity('cabinet', p)))
    nx, ny = snap_to_neighbours(doc, 1.65, y, rot, 0.6, 0.6)
    assert (nx, ny) == pytest.approx((1.6, y))           # touches the first cabinet
    assert wall_aligned(doc, 1.0, 3.0, 0.6) is None       # too far from any wall


def test_cabinet_in_document_plan_and_scene_with_role_materials():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.materials import MATERIAL_PRESETS
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); stack = CommandStack(doc)
    base = Entity('cabinet', default_params('base', 1.0, 1.0)); stack.execute(AddEntity(base))
    wall = Entity('cabinet', default_params('wall', 2.0, 1.0)); stack.execute(AddEntity(wall))
    roles = {p.role for p in build_plan_frame(doc).primitives if p.entity_id in (base.id, wall.id)}
    assert {'cabinet', 'cabinet-front', 'cabinet-wall'} <= roles
    mid = next(iter(MATERIAL_PRESETS))
    stack.execute(UpdateEntity(base.id, {'surface_materials': {'front': mid}}))
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    mine = {o['render_part'].split(':')[1]: o['material']['color'] for o in objs if o['id'] == base.id}
    assert mine['front'] == MATERIAL_PRESETS[mid]['color'] and mine['carcass'] != mine['front']
    stack.execute(MoveEntities([base.id], 0.5, 0.0))
    assert doc.get(base.id).params['x'] == pytest.approx(1.5)
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(base.id, {'cabinet_type': 'spaceship'}))
    with pytest.raises(ValueError):
        cabinet_mesh(dict(default_params('base'), width=0.03))


def test_kitchen_panel_places_a_cabinet_against_a_wall_and_modifier_edits_it():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.stack.execute(AddEntity(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'z': 0.0, 'x2': 4.0, 'y2': 0.0, 'height': 2.7, 'thickness': 0.2})))
        ctl = window.plan_view.controller
        ctl.set_component_definition(dict(name='Ντουλάπι βάσης', entity='cabinet', cabinet_type='base', role='cabinet', width=.6, depth=.6, height=.86))
        window._set_active_tool('component')
        from archforge.core.viewport import PointerEvent
        ctl.pointer_down(PointerEvent(1.0, 0.5)); ctl.pointer_up(PointerEvent(1.0, 0.5))
        cab = [e for e in window.doc.entities.values() if e.kind == 'cabinet']
        assert len(cab) == 1 and cab[0].params['y'] == pytest.approx(0.4)
        dialog = window._open_object_modifier(cab[0].id)
        dialog.set_param('width', 0.9)
        p = window.doc.get(cab[0].id).params
        assert p['width'] == pytest.approx(0.9) and p['doors'] == 2
        dialog.set_param('cabinet_type', 'drawers')
        p = window.doc.get(cab[0].id).params
        assert (p['doors'], p['drawers']) == (0, 3)
        window.stack.undo()
        assert window.doc.get(cab[0].id).params['cabinet_type'] == 'base'
    finally:
        window._mark_clean(); window.close(); app.processEvents()
