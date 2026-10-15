from types import SimpleNamespace
from unittest.mock import patch

import pytest

from archforge.ui import material_library as ml
from archforge.ui.material_object_integration import install_material_object_integration

_MISSING = object()


@pytest.fixture(autouse=True)
def _restore_patched_ui():
    """The integration patches modules for the whole process (as the real start-up does); put them back so
    later tests of the plain object dialog/preview see the code they test, whatever the test order."""
    from archforge.ui import object_modifier as om
    from archforge.ui import object_preview as op
    saved = [(ml, "_targets"), (ml, "_object_material_integration_installed"), (om, "visual_column"),
             (op.ObjectPreview, "_rebuild"), (op.ObjectPreview, "paintEvent"),
             (op.ObjectPreview, "_archforge_textured_material_preview")]
    for name in ("ObjectModifierDialog", "CabinetModifierDialog"):
        cls = getattr(om, name, None)
        if cls is not None:
            saved += [(cls, "refresh"), (cls, "pick_part")]
    before = [(obj, attr, obj.__dict__.get(attr, _MISSING)) for obj, attr in saved]
    yield
    for obj, attr, value in before:
        if value is _MISSING:
            if attr in obj.__dict__:
                delattr(obj, attr)
        else:
            setattr(obj, attr, value)


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
