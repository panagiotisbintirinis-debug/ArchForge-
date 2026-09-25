from pathlib import Path

from archforge.core.model import Document, Entity
from archforge.core.modifiers import SurfaceModifier, SurfaceRef, ordered_modifiers
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.plan import _opening_intents_for_host
from archforge.geometry.incremental import IncrementalEvaluationCache


class _NoIterDict(dict):
    def __iter__(self):
        raise AssertionError('global entity iteration is forbidden for indexed lookup')


class _NoValuesDict(dict):
    def values(self):
        raise AssertionError('global modifier scan is forbidden for owner lookup')


class _CountingBackend(TessellatedPreviewBackend):
    def __init__(self):
        super().__init__()
        self.calls = []

    def evaluate_plan(self, doc, plan):
        self.calls.append(tuple(node.entity_id for node in plan.nodes))
        return super().evaluate_plan(doc, plan)


def _box(x=0.0):
    return Entity('box', {
        'x': x, 'y': 0.0, 'z': 0.0,
        'width': 1.0, 'depth': 1.0, 'height': 1.0, 'rotation': 0.0,
    })


def _wall():
    return Entity('wall', {
        'x1': 0.0, 'y1': 0.0, 'z': 0.0,
        'x2': 5.0, 'y2': 0.0, 'height': 3.0, 'thickness': 0.2,
    })


def test_opening_intents_use_host_index_without_scanning_document():
    doc = Document()
    wall = _wall(); doc.add(wall)
    door = Entity('door', {'offset': 1.0, 'width': 0.9, 'height': 2.1, 'sill': 0.0}, parent_id=wall.id)
    window = Entity('window', {'offset': 3.0, 'width': 1.0, 'height': 1.0, 'sill': 1.0}, parent_id=wall.id)
    doc.add(door); doc.add(window)
    for i in range(50):
        doc.add(_box(10.0 + i * 2.0))

    assert set(doc.opening_ids_for_host(wall.id)) == {door.id, window.id}
    doc.entities = _NoIterDict(doc.entities)
    intents = _opening_intents_for_host(doc, wall.id)
    assert [item['id'] for item in intents] == sorted((door.id, window.id))


def test_modifier_owner_index_tracks_add_retarget_and_remove_without_global_scan():
    doc = Document()
    a = _box(0.0); b = _box(3.0); doc.add(a); doc.add(b)
    modifier = SurfaceModifier(SurfaceRef(a.id, 'top'), 'pull', {'amount': 0.1})
    mid = doc.add_surface_modifier(modifier)
    assert doc.modifier_ids_for_owner(a.id) == (mid,)

    doc.update_surface_modifier(mid, target=SurfaceRef(b.id, 'top'))
    assert doc.modifier_ids_for_owner(a.id) == ()
    assert doc.modifier_ids_for_owner(b.id) == (mid,)

    doc.surface_modifiers = _NoValuesDict(doc.surface_modifiers)
    assert [m.id for m in ordered_modifiers(doc, b.id)] == [mid]

    # Restore the ordinary backing store directly; the wholesale-store setter is itself
    # an index rebuild boundary and is allowed to scan once. The assertion above isolates
    # the hot owner-query path that must remain O(1).
    doc._surface_modifiers = dict(dict.items(doc.surface_modifiers))
    doc.remove_surface_modifier(mid)
    assert doc.modifier_ids_for_owner(b.id) == ()


def test_incremental_evaluation_cache_reuses_clean_bodies_and_rebuilds_only_dirty_entity():
    doc = Document()
    a = _box(0.0); b = _box(5.0); doc.add(a); doc.add(b)
    backend = _CountingBackend()
    cache = IncrementalEvaluationCache(backend)

    first = cache.sync(doc)
    assert {body.entity_id for body in first.bodies} == {a.id, b.id}
    assert len(backend.calls) == 1

    second = cache.sync(doc)
    assert second.bodies == first.bodies
    assert len(backend.calls) == 1

    before_generation = doc.dirty_generation(a.id)
    doc.update(a.id, {'width': 2.0})
    assert doc.dirty_generation(a.id) > before_generation

    third = cache.sync(doc)
    assert len(backend.calls) == 2
    assert backend.calls[-1] == (a.id,)
    assert third.body(a.id).payload.vertices != first.body(a.id).payload.vertices
    assert third.body(b.id) == first.body(b.id)


def test_incremental_cache_purges_deleted_entity_without_rebuilding_clean_survivors():
    doc = Document()
    a = _box(0.0); b = _box(5.0); doc.add(a); doc.add(b)
    backend = _CountingBackend(); cache = IncrementalEvaluationCache(backend)
    cache.sync(doc)

    doc.remove(a.id)
    result = cache.sync(doc)
    assert {body.entity_id for body in result.bodies} == {b.id}
    assert len(backend.calls) == 1


def test_viewport_drag_path_has_no_scene_clear_or_tessellation_evaluation():
    source = Path('archforge/ui/viewport_3d.py').read_text(encoding='utf-8')
    assert 'self._scene.clear()' not in source

    move_start = source.index('    def mouseMoveEvent')
    release_start = source.index('    def mouseReleaseEvent', move_start)
    move_body = source[move_start:release_start]
    assert 'TessellatedPreviewBackend' not in move_body
    assert '.evaluate(' not in move_body
    assert '_update_interaction_proxies' not in move_body
    assert '_orbit_to(pos)' in move_body
    assert '_pan_to(pos)' in move_body
    assert 'redraw(force_full=True)' in move_body

    orbit_start = source.index('    def _orbit_to')
    pan_start = source.index('    def _pan_to', orbit_start)
    orbit_body = source[orbit_start:pan_start]
    event_filter_start = source.index('    def eventFilter', pan_start)
    pan_body = source[pan_start:event_filter_start]
    assert '_redraw_camera_only()' in orbit_body
    assert '_redraw_camera_only()' in pan_body

    release_end = source.index('    def resizeEvent', release_start)
    release_body = source[release_start:release_end]
    assert '_update_interaction_proxies' not in release_body


def test_main_window_redraw_defaults_to_current_view_not_all_four_views():
    source = Path('archforge/ui/main_window.py').read_text(encoding='utf-8')
    marker = '    def _redraw_views(self, *, all_views=False):'
    assert marker in source
    start = source.index(marker)
    end = source.index('    def _undo', start)
    body = source[start:end]
    assert 'targets=(self.plan_view,self.front_view,self.side_view,self.view_3d) if all_views else (self.view,)' in body
