"""Owner 18/10: on a laptop with a dark Windows theme the menus were very dark — ArchForge always opens light."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from archforge.ui.theme import use_light_theme


def test_light_theme_even_when_the_system_is_dark():
    app = QApplication.instance() or QApplication([])
    hints = app.styleHints()
    if hasattr(hints, 'setColorScheme'):
        hints.setColorScheme(Qt.ColorScheme.Dark)
    use_light_theme(app)
    assert hints.colorScheme() != Qt.ColorScheme.Dark
    assert app.palette().window().color().lightness() > 180
    if hasattr(hints, 'unsetColorScheme'):
        hints.unsetColorScheme()
