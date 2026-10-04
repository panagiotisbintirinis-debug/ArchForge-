import math

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.core.viewport import PointerController, PointerEvent
from archforge.rendering.fixtures import opening_fixture_parts


def _wall_with(tool, x):
    doc = Document(); stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': 0.25})))
    c = PointerController(doc, stack); c.set_tool(tool)
    c.pointer_down(PointerEvent(x, 0)); r = c.pointer_up(PointerEvent(x, 0))
    return doc, doc.get(r.entity_id)


def test_window_gets_frame_and_glass_inside_its_hole():
    doc, window = _wall_with('window', 3.0)
    parts = dict((k, (v, t)) for k, v, t in opening_fixture_parts(doc, window))
    assert set(parts) == {'window_frame', 'window_glass'}
    p = window.params
    u0 = p['offset'] - p['width'] / 2; u1 = p['offset'] + p['width'] / 2
    for verts, _ in parts.values():
        xs = [v[0] for v in verts]; zs = [v[2] for v in verts]; ys = [v[1] for v in verts]
        assert min(xs) >= u0 - 1e-9 and max(xs) <= u1 + 1e-9
        assert min(zs) >= p['sill'] - 1e-9 and max(zs) <= p['sill'] + p['height'] + 1e-9
        assert max(abs(y) for y in ys) <= 0.125 + 1e-9      # within the wall thickness


def test_door_gets_frame_and_leaf_and_renders_with_the_door_id():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload

    doc, door = _wall_with('door', 2.0)
    assert {k for k, _, _ in opening_fixture_parts(doc, door)} == {'door_frame', 'door_leaf'}
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [door.id], doc=doc)['objects']
    door_parts = [o for o in objs if o['id'] == door.id]
    assert {o['render_part'].split(':')[1] for o in door_parts} == {'door_frame', 'door_leaf'}
    assert all(o['material'].get('emissiveIntensity', 0) > 0 for o in door_parts)   # selected


def test_glass_is_transparent_and_wide_windows_get_a_mullion():
    from archforge.rendering.scene import _material
    assert _material('window_glass', False)['opacity'] < 0.5
    doc, window = _wall_with('window', 3.0)
    window.params['width'] = 2.0
    glass = [v for k, v, _ in opening_fixture_parts(doc, window) if k == 'window_glass']
    assert len(glass) == 1 and len(glass[0]) == 16    # two panes = two boxes
