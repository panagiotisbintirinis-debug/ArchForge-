from types import SimpleNamespace


def _entity(eid, kind, params):
    return SimpleNamespace(id=eid, kind=kind, params=dict(params), visible=True)


def test_manifold_object_reaches_pbr_payload(monkeypatch):
    """Regression: a derived manifold must reach the final PBR scene payload."""
    from archforge.ui import pbr_viewport
    from archforge.ui.plumbing_manifold_3d import install
    import archforge.mep.plumbing_visuals as visuals

    install()

    monkeypatch.setattr(
        visuals,
        "manifold_scene_objects",
        lambda doc: [{
            "id": "",
            "render_part": "mep:manifold:cold:0",
            "kind": "mep_manifold",
            "layer": "mep",
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "triangles": [[0, 1, 2]],
            "surfaces": ["cabinet"],
            "material": {"color": "#2d6fb3"},
        }],
    )

    base = pbr_viewport.build_pbr_scene_payload
    # If already wrapped by app import, this call still exercises the active chain.
    evaluation = SimpleNamespace(bodies=[])
    doc = SimpleNamespace(entities={}, selection=[])
    payload = base(evaluation, (), doc=doc)
    assert any(o.get("kind") == "mep_manifold" for o in payload.get("objects", []))
