from archforge.ui.library_instance_integration import (
    library_instance_params,
    source_size_for_instance,
)


def _record():
    return {
        "id": "cabinet-100",
        "name": "Βιτρίνα 100",
        "size": [1.00, 0.40, 1.90],
    }


def test_each_library_placement_has_fresh_instance_state():
    record = _record()
    original = {
        "id": record["id"],
        "name": record["name"],
        "size": list(record["size"]),
    }

    first = library_instance_params(record, x=1.0, y=2.0, z=0.0)
    second = library_instance_params(record, x=4.0, y=5.0, z=0.0)

    first["width"] = 1.75
    first["surface_materials"]["part2"] = "paint_blue_aegean"

    assert record == original
    assert second["width"] == 1.00
    assert second["surface_materials"] == {}
    assert first["surface_materials"] is not second["surface_materials"]


def test_instance_keeps_immutable_source_provenance_and_defaults():
    params = library_instance_params(_record(), x=0.0, y=0.0, z=-3.0)

    assert params["asset"] == "cabinet-100"
    assert params["source_asset_id"] == "cabinet-100"
    assert params["source_size"] == [1.00, 0.40, 1.90]
    assert params["material_id"] == ""
    assert params["surface_materials"] == {}
    assert source_size_for_instance(params) == (1.00, 0.40, 1.90)


def test_reset_source_size_does_not_follow_instance_resize():
    params = library_instance_params(_record(), x=0.0, y=0.0, z=0.0)
    params.update({"width": 1.22, "depth": 0.48, "height": 2.318})

    assert source_size_for_instance(params) == (1.00, 0.40, 1.90)
