from types import SimpleNamespace
from unittest.mock import patch

from archforge.ui import material_library as ml
from archforge.ui.material_object_integration import install_material_object_integration


def test_library_object_targets_include_asset_parts_before_any_override():
    install_material_object_integration()
    entity = SimpleNamespace(
        kind="library_object",
        params={"asset": "fake-chair", "surface_materials": {}},
        name="",
    )
    parts = [
        ("part0", "#222222", "Πόδια"),
        ("part1", "#777777", "Ύφασμα"),
    ]
    with patch("archforge.library.objects.asset_parts", return_value=parts):
        targets = {target.key: target.label for target in ml._targets(entity)}

    assert targets["part0"] == "Πόδια"
    assert targets["part1"] == "Ύφασμα"
    assert "" in targets
