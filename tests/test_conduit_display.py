"""Owner regression: the conduit take-off, plan and 3D must show the same pipes."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from archforge.core.commands import AddEntity, CommandStack, MoveEntities
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.mep.conduits import conduit_map
from archforge.mep.electrical import route_cables_cached


def _project():
    doc = Document(); stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('wall', dict(x1=0, y1=0, x2=6, y2=0, z=0, height=2.7, thickness=.2))))
    devices = []
    for kind, x in [('panel', .2), ('cooker', 3), ('cooker', 5)]:
        e = Entity('electrical_point', dict(x=x, y=0, z=0, point_type=kind))
        stack.execute(AddEntity(e)); devices.append(e)
    return doc, stack, devices


def _scene(doc):
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    return build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']


def test_coincident_dedicated_conduits_are_distinct_in_plan_and_match_the_map():
    doc, _stack, _devices = _project()
    cmap = conduit_map(doc)
    assert cmap['conduits'] == 2
    prims = [p for p in build_plan_frame(doc).primitives if p.role == 'cable']
    assert {dict(p.meta).get('conduit') for p in prims} == {p['conduit'] for p in cmap['pieces']}
    by_source = {}
    for p in prims:
        meta = dict(p.meta)
        if not meta.get('connector'):
            by_source.setdefault(tuple(meta['source_segment']), []).append(p)
    shared = [pp for pp in by_source.values() if len({dict(p.meta)['conduit'] for p in pp}) > 1]
    assert shared
    assert all(len({p.points for p in pp}) == len(pp) for pp in shared)
    labels = [dict(p.meta)['text'] for p in build_plan_frame(doc).primitives if p.role == 'electrical-label']
    assert all(any(p['conduit'] in text and f"Φ{p['dn']}" in text for text in labels) for p in cmap['pieces'])


def test_3d_uses_each_map_piece_and_its_diameter_instead_of_constant_phi25():
    doc, _stack, _devices = _project()
    cmap = conduit_map(doc)
    objects = [o for o in _scene(doc) if o.get('kind') == 'elec_cable']
    assert {o.get('conduit_piece') for o in objects} == {p['id'] for p in cmap['pieces']}
    assert len(objects) == sum(p['count'] for p in cmap['pieces'])
    assert all(o['diameter_mm'] == 32 for o in objects)
    assert len({tuple(map(tuple, o['vertices'])) for o in objects}) == len(objects)


def test_view_separation_keeps_routes_quantities_and_document_unchanged():
    doc, _stack, _devices = _project()
    before = copy.deepcopy(route_cables_cached(doc)); cmap = copy.deepcopy(conduit_map(doc))
    snapshot = copy.deepcopy(doc.to_dict())
    build_plan_frame(doc); _scene(doc)
    assert route_cables_cached(doc) == before
    assert conduit_map(doc) == cmap
    assert doc.to_dict() == snapshot


def test_shared_conduit_is_not_duplicated_per_circuit_and_count_is_respected():
    from archforge.mep.conduit_display import display_pieces
    # Synthetic drawing contract, not an electrical sizing example.
    shared = dict(id='Σ1.1', conduit='Σ1', points=[(0,0,2),(2,0,2)], dn=25, count=1, lines=['Κ1','Κ2'])
    separate = dict(id='Σ2.1', conduit='Σ2', points=[(0,0,2),(2,0,2)], dn=32, count=2, lines=['Κ3'])
    cmap = {'pieces': [shared, separate]}
    original = copy.deepcopy(cmap)
    result = display_pieces(cmap)
    assert len(result) == 3
    assert len({p['points'] for p in result}) == 3
    assert next(p for p in result if p['conduit']=='Σ1')['lines'] == ['Κ1','Κ2']
    assert all(p['points'][0] == shared['points'][0] and p['points'][-1] == shared['points'][-1] for p in result)
    assert cmap == original


def test_move_undo_and_save_load_rederive_the_same_conduit_display(tmp_path):
    from archforge.mep.conduit_display import display_pieces
    doc, stack, devices = _project()
    def shown(d): return display_pieces(conduit_map(d))
    before = shown(doc)
    stack.execute(MoveEntities([devices[-1].id], -1, 0))
    assert shown(doc) != before
    stack.undo(); assert shown(doc) == before
    path = tmp_path/'conduits.archforge'; doc.save(path)
    assert shown(Document.load(path)) == before


def test_low_voltage_is_above_power_and_has_its_own_visible_plan_row():
    from archforge.mep.low_voltage import LV_RUN_RISE, route_low_voltage
    from archforge.mep.electrical import WALL_RUN_Z
    doc, stack, devices = _project()
    for kind, x in [('network_rack', .2), ('data_outlet', 5)]:
        stack.execute(AddEntity(Entity('electrical_point', dict(x=x,y=0,z=0,point_type=kind))))
    lv = route_low_voltage(doc)
    assert LV_RUN_RISE > 0
    horizontals = [(a,b) for a,b,_s,_t in lv['runs'] if abs(a[2]-b[2])<1e-8]
    assert horizontals and all(a[2] > WALL_RUN_Z for a,b in horizontals)
    frame = build_plan_frame(doc)
    lv_prims = [p for p in frame.primitives if p.role=='lv-cable' and not dict(p.meta)['connector']]
    power = [p for p in frame.primitives if p.role=='cable' and not dict(p.meta)['connector']]
    assert lv_prims and power
    # Wall runs on this synthetic wall are y=0 at source; the LV row is above power.
    lv_y = min(p.points[0][1] for p in lv_prims)
    power_y = max(p.points[0][1] for p in power)
    assert lv_y > power_y


def test_parallel_power_pipes_also_have_distinct_height_rows_in_3d():
    from archforge.mep.conduit_display import display_pieces,display_segments
    doc,_stack,_devices=_project()
    grouped={}
    for p in display_pieces(conduit_map(doc)):
        for a,b,source,connector in display_segments(p):
            if not connector and abs(source[0][2]-source[1][2])<1e-9:
                grouped.setdefault(tuple(sorted(source)),[]).append(a[2])
    shared=[heights for heights in grouped.values() if len(heights)>1]
    assert shared and all(len(set(heights))==len(heights) for heights in shared)
