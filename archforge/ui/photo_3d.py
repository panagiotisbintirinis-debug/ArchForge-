"""«Φωτογραφία» (owner 29/10: «κουμπί φωτογραφία σαν στιγμιότυπο του 3Δ αντί να κάνω save screen με όλη την οθόνη»).

One click: the 3D view as it is now (camera, sun, lights, style) saved as a PNG, at twice the view's resolution —
the page's own ``archforgeCaptureFrame`` (always full quality: contact shadows, full resolution).  Nothing in the
project changes; nothing goes in the undo history.
"""
from __future__ import annotations

import base64
import datetime
import os

MAX_SIDE = 4096


def default_path(window):
    """~/Pictures (or home) / ArchForge_<project>_<date-time>.png."""
    folder = os.path.join(os.path.expanduser("~"), "Pictures")
    if not os.path.isdir(folder):
        folder = os.path.expanduser("~")
    name = os.path.splitext(os.path.basename(getattr(window, "current_path", "") or ""))[0] or "ArchForge"
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return os.path.join(folder, f"{name}_{stamp}.png" if name.startswith("ArchForge") else f"ArchForge_{name}_{stamp}.png")


def photo_size(width, height, scale=2.0):
    """The picture's size: ``scale`` × the view, the longer side at most MAX_SIDE."""
    w, h = max(1, int(width * scale)), max(1, int(height * scale))
    k = min(1.0, MAX_SIDE / max(w, h))
    return max(1, int(w * k)), max(1, int(h * k))


def take_photo(window, path=None, done=None):
    """Save the 3D view as a PNG. ``path`` None → ask where (suggesting ``default_path``). ``done(path or None)``."""
    pbr = getattr(window, "pbr_view", None)
    if pbr is None or getattr(pbr, "web_view", None) is None:
        window.statusBar().showMessage("Φωτογραφία: άνοιξε πρώτα το 3D", 5000)
        if done:
            done(None)
        return
    if path is None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(window, "Φωτογραφία του 3D", default_path(window), "Εικόνα PNG (*.png)")
        if not path:
            if done:
                done(None)
            return
    if not path.lower().endswith(".png"):
        path += ".png"
    width, height = photo_size(pbr.web_view.width(), pbr.web_view.height())

    def save(data_url):
        saved = None
        if isinstance(data_url, str) and data_url.startswith("data:image/png;base64,"):
            from archforge.project.persistence import atomic_write_bytes
            atomic_write_bytes(path, base64.b64decode(data_url.split(",", 1)[1]))
            saved = path
            window.statusBar().showMessage(f"Φωτογραφία {width}×{height}: {path}", 8000)
        else:
            window.statusBar().showMessage("Φωτογραφία: το 3D δεν έδωσε εικόνα — δοκίμασε ξανά", 6000)
        if done:
            done(saved)

    pbr.web_view.page().runJavaScript(
        f"window.archforgeCaptureFrame ? window.archforgeCaptureFrame({width}, {height}) : ''", 0, save)
