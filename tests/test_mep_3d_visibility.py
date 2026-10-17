from archforge.core.layers import ensure_view_layers, set_workspace
from archforge.core.model import Document
from archforge.ui.mep_3d_visibility import effective_hidden_layers


def test_new_layers_system_overrides_legacy_hidden_mep_flags():
    doc = Document()
    ensure_view_layers(doc)
    set_workspace(doc, "mep")

    hidden = {"mep", "drain", "elec", "vent", "other_legacy"}
    assert effective_hidden_layers(doc, hidden) == {"other_legacy"}


def test_legacy_hidden_mep_flags_are_preserved_when_layers_system_is_inactive():
    doc = Document()
    doc.view_layers = {}
    hidden = {"mep", "drain"}
    assert effective_hidden_layers(doc, hidden) == hidden
