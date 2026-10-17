"""Owner 17 Oct: complete S01 evidence before S02, including actual stairs.

All dimensions/prices in these projects are synthetic software-fixture inputs.
This does not verify a building design, a regulatory rule, or market pricing.
"""
import importlib.util
import json
from pathlib import Path

from archforge.project.persistence import load_project_data

ROOT = Path(__file__).parent / 'residential_scenarios'


def generated_s01():
    spec = importlib.util.spec_from_file_location('residential_generator', ROOT / 'generate_projects.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    loaded = load_project_data(module.build_project(manifest[0]))
    assert loaded.ok, loaded.message()
    return loaded.doc


def test_s01_has_valid_canonical_railings():
    from archforge.architecture.railings import default_params
    doc = generated_s01()
    rails = [e for e in doc.entities.values() if e.kind == 'railing']
    assert rails
    for rail in rails:
        expected = default_params(rail.params['railing_type'], rail.params['points'],
                                  z=rail.params['z'], height=rail.params['height'])
        assert all(rail.params[k] == v for k, v in expected.items())


def test_s01_has_connected_cold_and_hot_sources():
    from archforge.mep.plumbing import route_plumbing
    result = route_plumbing(generated_s01())
    assert result['cold'] and result['hot']
    assert result['report']['unserved'] == []


def test_attic_candidates_exclude_rooms_covered_by_an_upper_storey():
    from archforge.architecture.roof_need import attic_rooms
    doc = generated_s01()
    for e in list(doc.entities.values()):
        if e.kind == 'room_ceiling':
            doc.remove(e.id)
    rooms = attic_rooms(doc)
    # Before ceilings are created, there are four top-storey candidates only.
    assert len(rooms) == 4
    assert {z for _face, z, _room_id in rooms} == {3.0}


def test_s01_has_stairs_and_accessible_room_openings():
    doc = generated_s01()
    assert sum(e.kind == 'stair' for e in doc.entities.values()) == 1
    assert sum(e.kind == 'door' for e in doc.entities.values()) >= 8
    assert sum(e.kind == 'window' for e in doc.entities.values()) >= 4


def test_s01_has_an_interstorey_slab_despite_the_roof_above_two_storeys():
    from archforge.architecture.storey_slabs import storey_slab_geometry
    doc = generated_s01()
    slabs = [e for e in doc.entities.values() if e.kind == 'room_roof']
    assert len(slabs) == 1
    assert slabs[0].params['level_z'] == 0.
    assert storey_slab_geometry(doc, slabs[0]) is not None


def test_s01_plumbing_plan_uses_pipe_only_display_without_overlapping_point_names():
    from archforge.core.layers import set_workspace
    from archforge.core.plan_scene import build_plan_frame
    from archforge.ui.plumbing_display import apply_display_state
    doc = generated_s01(); set_workspace(doc, 'mep')
    frame = apply_display_state(doc, build_plan_frame(doc))
    roles = [p.role for p in frame.primitives]
    assert 'pipe-cold' in roles and 'pipe-hot' in roles
    assert 'plumbing-label' not in roles


def test_s01_drainage_annotations_use_collision_managed_positions():
    from archforge.core.plan_scene import build_plan_frame, label_box
    frame = build_plan_frame(generated_s01(), layers=False)
    labels = [p for p in frame.primitives if p.role == 'drain-label']
    assert labels
    boxes = []
    for label in labels:
        meta = dict(label.meta)
        assert 'min_scale' in meta and 'align' in meta
        if meta['min_scale'] <= 60:
            boxes.append(label_box(label.points[0], meta['align'], meta['text'], 60))
    for i, a in enumerate(boxes):
        for b in boxes[i+1:]:
            assert not (a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3])
