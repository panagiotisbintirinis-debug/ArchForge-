"""Wall assemblies: type sets thickness, plan layers and face colours."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.wall_types import (WALL_TYPES, face_colors, indicative_u, layer_lines, layers,
                                               total_thickness)
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame


def _wall(**kw):
    p = {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2}
    p.update(kw)
    return Entity('wall', p)


def test_assemblies_sum_their_layers_and_give_plausible_indicative_u():
    assert total_thickness('drywall_100') == pytest.approx(0.10)
    assert total_thickness('brick_double_insulated') == pytest.approx(0.27)
    assert total_thickness('stone_uninsulated') == pytest.approx(0.54)
    assert indicative_u('generic') is None
    # Insulation lowers U; uninsulated stone is far worse than insulated stone.
    assert indicative_u('stone_insulated') < 0.6 < 1.5 < indicative_u('stone_uninsulated')
    assert indicative_u('brick_double_insulated') < indicative_u('brick_partition')
    for key in WALL_TYPES:
        assert all(d > 0 and lam > 0 for _n, d, lam, _c, _i in layers(key))


def test_wall_type_is_validated_and_drawn_in_plan_with_insulation_dashed():
    doc = Document(); stack = CommandStack(doc)
    wall = _wall(); stack.execute(AddEntity(wall))
    stack.execute(UpdateEntity(wall.id, {'wall_type': 'brick_double_insulated', 'thickness': 0.27}))
    prims = [p for p in build_plan_frame(doc).primitives if p.entity_id == wall.id]
    roles = [p.role for p in prims]
    assert roles.count('wall-insulation') == 2 and roles.count('wall-layer') == 2
    ys = sorted(round(p.points[0][1], 4) for p in prims if p.role in ('wall-layer', 'wall-insulation'))
    assert ys == pytest.approx([-0.115, -0.025, 0.025, 0.115])
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(wall.id, {'wall_type': 'cardboard'}))
    assert layer_lines(doc.get(wall.id).params, 'generic') == []


def test_wall_faces_render_with_their_finishing_layers():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); doc.add(_wall(wall_type='stone_insulated', thickness=total_thickness('stone_insulated')))
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    colours = {o['render_part'].split(':')[1]: o['material']['color'] for o in objs}
    ext, inner = face_colors('stone_insulated')
    assert colours['__type_exterior__'] == ext and colours['__type_interior__'] == inner


def test_inspector_wall_type_sets_type_and_thickness_with_undo():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        wall = _wall(); window.stack.execute(AddEntity(wall))
        window.doc.select([wall.id]); window.refresh_inspector()
        window._set_wall_type(wall.id, 'stone_uninsulated')
        p = window.doc.get(wall.id).params
        assert p['wall_type'] == 'stone_uninsulated' and p['thickness'] == pytest.approx(0.54)
        window.stack.undo()
        assert window.doc.get(wall.id).params['thickness'] == pytest.approx(0.2)
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_wall_layers_show_in_3d_where_the_wall_is_cut():
    """The top, the ends and the reveals of openings show each layer's colour (owner 30/10: layers in 3D)."""
    from archforge.architecture.wall_types import layer_bands
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    t = total_thickness('brick_double_insulated')
    doc = Document(); wall = _wall(wall_type='brick_double_insulated', thickness=t); doc.add(wall)
    bands = layer_bands(wall.params, 'brick_double_insulated')
    assert len(bands) == 5 and bands[0][0] == pytest.approx(t / 2) and bands[-1][1] == pytest.approx(-t / 2)
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    parts = {o['render_part'].split(':')[1]: o for o in objs if o['id'] == wall.id}
    for k, (hi, lo, colour) in enumerate(bands):
        part = parts[f'__layer_{k}__']
        assert part['material']['color'] == colour and set(part['surfaces']) >= {'top'}
        for tri in part['triangles']:                      # every piece lies inside its layer (wall along +x: d = y)
            ys = [part['vertices'][i][1] for i in tri]
            assert all(lo - 1e-6 <= y <= hi + 1e-6 for y in ys)
    assert '__type_exterior__' in parts and '__type_interior__' in parts     # the faces keep their finish
    assert layer_bands(wall.params, 'generic') == []
