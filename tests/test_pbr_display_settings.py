from archforge.ui.pbr_display_settings import PBRDisplayPalette


def test_pbr_display_palette_preserves_current_renderer_defaults():
    palette = PBRDisplayPalette()

    assert palette.as_scene_colors() == {
        "background": "#d9dee5",
        "technical_background": "#f4f5f7",
        "ground": "#cbd1d7",
        "default_surface": "#bdc5ce",
    }


def test_pbr_display_palette_can_change_view_colors_without_document_state():
    palette = PBRDisplayPalette(background="#101820", ground="#202830")

    assert palette.background == "#101820"
    assert palette.ground == "#202830"
    assert not hasattr(palette, "document")
