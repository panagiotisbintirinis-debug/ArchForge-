from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PBRDisplayPalette:
    """View-only PBR display colors; never authoritative Document state."""

    background: str = "#d9dee5"
    technical_background: str = "#f4f5f7"
    ground: str = "#cbd1d7"
    default_surface: str = "#bdc5ce"

    def as_scene_colors(self) -> dict[str, str]:
        """Return the renderer-facing color contract without design/model state."""
        return {
            "background": self.background,
            "technical_background": self.technical_background,
            "ground": self.ground,
            "default_surface": self.default_surface,
        }
