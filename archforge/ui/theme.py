"""Application theme (kept apart from app.py, whose import installs the shell on MainWindow)."""


def use_light_theme(app):
    """ArchForge's colours are drawn for a light window: a dark Windows theme made menus and panels dark (owner 18/10).
    Qt 6.8 follows the system scheme unless told otherwise."""
    from PySide6.QtCore import Qt
    hints=app.styleHints()
    if hasattr(hints,'setColorScheme'):
        hints.setColorScheme(Qt.ColorScheme.Light)
    if hints.colorScheme()==Qt.ColorScheme.Dark:      # older Qt or a style that ignores the request
        from PySide6.QtWidgets import QStyleFactory
        app.setStyle(QStyleFactory.create('Fusion'))
        app.setPalette(app.style().standardPalette())
