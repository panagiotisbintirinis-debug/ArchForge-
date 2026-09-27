from types import SimpleNamespace

from archforge.geometry.mesh import MeshPayload
from archforge.core.model import Document, Entity
from archforge.rendering.scene import build_pbr_scene_payload


def test_pbr_scene_payload_uses_authoritative_mesh_and_identity():
    mesh = MeshPayload(
        vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 3.0)),
        triangles=((0, 1, 2),),
        triangle_surfaces=("front",),
    )
    body = SimpleNamespace(entity_id="wall-1", semantic_kind="wall", payload=mesh)
    evaluation = SimpleNamespace(bodies=(body,))

    payload = build_pbr_scene_payload(evaluation, selected_ids={"wall-1"})

    assert payload["objects"] == [
        {
            "id": "wall-1",
            "kind": "wall",
            "vertices": [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 0.0, 3.0]],
            "triangles": [[0, 1, 2]],
            "surfaces": ["front"],
            "material": {
                "color": "#d8d2c7",
                "roughness": 0.72,
                "metalness": 0.02,
                "emissive": "#1f5f93",
                "emissiveIntensity": 0.28,
            },
        }
    ]


def test_pbr_scene_payload_ignores_non_mesh_bodies():
    body = SimpleNamespace(entity_id="x", semantic_kind="unsupported", payload={"preview": True})
    evaluation = SimpleNamespace(bodies=(body,))

    assert build_pbr_scene_payload(evaluation) == {"objects": []}


def test_pbr_scene_payload_accepts_transient_mesh_override():
    base = MeshPayload(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        triangles=((0, 1, 2),),
        triangle_surfaces=("front",),
    )
    preview = MeshPayload(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.5)),
        triangles=((0, 1, 2),),
        triangle_surfaces=("front",),
    )
    body = SimpleNamespace(entity_id="wall-1", semantic_kind="wall", payload=base)
    evaluation = SimpleNamespace(bodies=(body,))

    payload = build_pbr_scene_payload(
        evaluation,
        mesh_overrides={"wall-1": preview},
    )

    assert payload["objects"][0]["vertices"][2] == [0.0, 0.0, 1.5]


def test_pbr_scene_payload_uses_authoritative_entity_material_assignment():
    mesh = MeshPayload(
        vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 3.0)),
        triangles=((0, 1, 2),),
        triangle_surfaces=("front",),
    )
    body = SimpleNamespace(entity_id="wall-material", semantic_kind="wall", payload=mesh)
    evaluation = SimpleNamespace(bodies=(body,))
    doc = Document()
    doc.add(Entity(
        'wall',
        {
            'x1': 0.0, 'y1': 0.0, 'x2': 2.0, 'y2': 0.0,
            'z': 0.0, 'height': 3.0, 'thickness': 0.15,
            'material_id': 'wood_oak',
        },
        id='wall-material',
    ))

    payload = build_pbr_scene_payload(evaluation, doc=doc)
    material = payload['objects'][0]['material']

    assert material['material_id'] == 'wood_oak'
    assert material['material_name'] == 'Natural Oak'
    assert material['color'] == '#b98755'
    assert material['roughness'] == 0.64
    assert material['metalness'] == 0.0


def test_selected_material_keeps_surface_color_and_adds_highlight():
    mesh = MeshPayload(
        vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 3.0)),
        triangles=((0, 1, 2),),
        triangle_surfaces=("front",),
    )
    body = SimpleNamespace(entity_id="selected-material", semantic_kind="wall", payload=mesh)
    evaluation = SimpleNamespace(bodies=(body,))
    doc = Document()
    doc.add(Entity(
        'wall',
        {
            'x1': 0.0, 'y1': 0.0, 'x2': 2.0, 'y2': 0.0,
            'z': 0.0, 'height': 3.0, 'thickness': 0.15,
            'material_id': 'stone_dark',
        },
        id='selected-material',
    ))

    payload = build_pbr_scene_payload(
        evaluation,
        selected_ids={'selected-material'},
        doc=doc,
    )
    material = payload['objects'][0]['material']

    assert material['color'] == '#5b5c58'
    assert material['emissive'] == '#1f5f93'
    assert material['emissiveIntensity'] == 0.28


def test_wall_side_materials_render_independently_for_one_authoritative_wall():
    mesh = MeshPayload(
        vertices=(
            (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 3.0),
            (0.0, 0.15, 0.0), (2.0, 0.15, 0.0), (0.0, 0.15, 3.0),
        ),
        triangles=((0, 1, 2), (3, 5, 4)),
        triangle_surfaces=("exterior", "interior"),
    )
    body = SimpleNamespace(entity_id="two-sided-wall", semantic_kind="wall", payload=mesh)
    evaluation = SimpleNamespace(bodies=(body,))
    doc = Document()
    doc.add(Entity(
        'wall',
        {
            'x1': 0.0, 'y1': 0.0, 'x2': 2.0, 'y2': 0.0,
            'z': 0.0, 'height': 3.0, 'thickness': 0.15,
            'surface_materials': {
                'exterior': 'wood_oak',
                'interior': 'stone_dark',
            },
        },
        id='two-sided-wall',
    ))

    payload = build_pbr_scene_payload(evaluation, doc=doc)
    objects = payload['objects']

    assert len(objects) == 2
    assert {obj['id'] for obj in objects} == {'two-sided-wall'}
    materials = {obj['material'].get('material_id') for obj in objects}
    assert materials == {'wood_oak', 'stone_dark'}

    by_material = {obj['material']['material_id']: obj for obj in objects}
    assert by_material['wood_oak']['surfaces'] == ['exterior']
    assert by_material['stone_dark']['surfaces'] == ['interior']
