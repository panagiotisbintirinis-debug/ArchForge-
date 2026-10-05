"""Timber tiled roof: derived members and rafter pre-sizing from loads."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.structure.timber_roof import SECTIONS, members, ridge_z, roof_mesh, size_rafter, snow_load

BASE = {'insulation': 'xps', 'insulation_thickness': 0.08, 'x0': 0.0, 'y0': 0.0, 'x1': 10.0, 'y1': 8.0, 'eave_z': 3.0, 'pitch': 25.0, 'overhang': 0.5,
        'rafter_spacing': 0.6, 'roof_form': 'gable', 'tile': 'roman', 'snow_zone': 2, 'altitude': 0.0}


def test_gable_geometry_ridge_height_and_rafter_spacing():
    p = dict(BASE)
    assert ridge_z(p) == pytest.approx(3.0 + 4.0 * math.tan(math.radians(25)))
    rafters = [m for m in members(p) if m[0] == 'rafter']
    # 11 m along the eave (with overhang) at <=0.60 m spacing, two slopes
    per_side = len(rafters) // 2
    assert per_side == math.ceil(11.0 / 0.6) + 1
    for _r, a, b, _s in rafters:
        assert max(a[2], b[2]) == pytest.approx(ridge_z(p), abs=1e-6)
        assert min(a[2], b[2]) == pytest.approx(3.0 - 0.5 * math.tan(math.radians(25)), abs=1e-6)
    roles = {m[0] for m in members(p)}
    assert roles == {'plate', 'rafter', 'ridge', 'batten'}


def test_hip_and_shed_forms():
    hip = members(dict(BASE, roof_form='hip'))
    assert sum(1 for m in hip if m[0] == 'hip') == 4
    ridge = [m for m in hip if m[0] == 'ridge'][0]
    assert math.dist(ridge[1][:2], ridge[2][:2]) == pytest.approx(10.0 - 8.0)
    shed = dict(BASE, roof_form='shed')
    assert ridge_z(shed) == pytest.approx(3.0 + 8.0 * math.tan(math.radians(25)))
    assert not any(m[0] == 'ridge' for m in members(shed))
    plates = [m for m in members(shed) if m[0] == 'plate']
    assert max(max(a[2], b[2]) for _r, a, b, _s in plates) == pytest.approx(ridge_z(shed))   # high wall carries the roof
    assert all(a[2] == pytest.approx(3.0) and b[2] == pytest.approx(3.0) for _r, a, b, _s in members(BASE) if _r == 'plate')


def test_rafter_section_grows_with_snow_and_span_and_passes_its_checks():
    light = size_rafter(dict(BASE, snow_zone=1))
    heavy = size_rafter(dict(BASE, snow_zone=3, altitude=1000.0))
    wide = size_rafter(dict(BASE, y1=12.0))
    def rank(r):
        return SECTIONS.index((r['section']['b'], r['section']['h']))
    assert rank(light) < rank(heavy) and rank(light) < rank(wide)
    for r in (light, heavy, wide):
        s = r['section']
        assert s['sigma_mpa'] <= s['f_md_mpa'] and s['deflection_mm'] <= s['deflection_limit_mm']
        assert 'στατικό' in r['provenance']
    # Snow shape coefficient vanishes on steep roofs.
    assert snow_load(dict(BASE, pitch=60.0))[0] == 0.0
    impossible = size_rafter(dict(BASE, y1=30.0, snow_zone=3, altitude=1500.0, rafter_spacing=1.2))
    assert impossible['section'] is None and not impossible['ok']


def test_roof_in_document_plan_3d_and_moves():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); stack = CommandStack(doc)
    roof = Entity('pitched_roof', dict(BASE, eave_z=2.7)); stack.execute(AddEntity(roof))
    roles = [p.role for p in build_plan_frame(doc).primitives if p.entity_id == roof.id]
    assert 'roof-outline' in roles and 'roof-ridge' in roles
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    parts = {o['render_part'].split(':')[1]: o for o in objs if o['id'] == roof.id}
    assert set(parts) == {'plate', 'rafter', 'ridge', 'batten', 'counter_batten', 'boarding', 'vapour_barrier',
                          'insulation', 'membrane', 'tiles'}
    assert parts['tiles']['layer'] == 'roof_tiles' and parts['rafter']['layer'] == 'roof_structure'
    stack.execute(MoveEntities([roof.id], 1.0, 2.0))
    assert doc.get(roof.id).params['x0'] == 1.0 and doc.get(roof.id).params['y1'] == 10.0
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(roof.id, {'pitch': 80.0}))
    v, t, r = roof_mesh(doc.get(roof.id).params)
    assert len(t) == len(r) and max(q[2] for q in v) > ridge_z(doc.get(roof.id).params)


def test_menu_creates_roof_over_the_walls():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        for x1, y1, x2, y2 in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0)]:
            window.stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': 2.7, 'thickness': 0.2})))
        window._pitched_roof_action.trigger()
        roofs = [e for e in window.doc.entities.values() if e.kind == 'pitched_roof']
        assert len(roofs) == 1
        p = roofs[0].params
        assert (p['x0'], p['y0'], p['x1'], p['y1'], p['eave_z']) == pytest.approx((-0.1, -0.1, 8.1, 6.1, 2.7))
        window._set_entity_choice(roofs[0].id, 'roof_form', 'hip')
        assert window.doc.get(roofs[0].id).params['roof_form'] == 'hip'
        window._roof_tiles_layer_action.setChecked(False)
        assert 'roof_tiles' in window.pbr_view.hidden_layers
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_insulation_build_up_feeds_loads_u_and_3d_order():
    from archforge.structure.timber_roof import build_up, dead_load, indicative_u
    bare = dict(BASE, insulation='none', insulation_thickness=0.0)
    insulated = dict(BASE, insulation='xps', insulation_thickness=0.10)
    assert [r for *_x, r in build_up(insulated)] == ['boarding', 'vapour_barrier', 'insulation', 'membrane']
    assert 'insulation' not in [r for *_x, r in build_up(bare)]
    assert dead_load(insulated) > dead_load(bare)
    assert indicative_u(insulated) < 0.35 < 2.0 < indicative_u(bare)
    # In 3D the layers stack upwards: boarding < insulation < membrane < tiles above the same point.
    v, t, r = roof_mesh(insulated)
    def top(role):
        return max(v[i][2] for tri, rr in zip(t, r) if rr == role for i in tri)
    assert top('boarding') < top('insulation') < top('membrane') < top('tiles')
    with pytest.raises(ValueError):
        Document().add(Entity('pitched_roof', dict(BASE, insulation='straw')))
