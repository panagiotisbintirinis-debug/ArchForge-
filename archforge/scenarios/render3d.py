"""3D pictures of a scenario without a GPU: the application's own 3D page and scene, in headless Chromium.

The page is ``pbr_page_html()`` and the scene ``scene_payload()`` — exactly what the 3D tab draws — rendered
with software WebGL (SwiftShader).  Used by the quality gate (docs/scenarios/QUALITY_GATE.md, section 6).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

CANDIDATES = ("/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell", "/opt/pw-browsers/chromium")


def browser():
    for path in CANDIDATES + tuple(filter(None, (shutil.which(n) for n in ("chromium", "chromium-browser", "google-chrome")))):
        if path and os.path.exists(path):
            return path
    return None


def render(doc, png_path, structural_only=False, drop_kinds=(), size=(1400, 900), timeout=240, camera=None):
    """Write ``png_path``; returns None or the reason it could not be drawn."""
    exe = browser()
    if exe is None:
        return "δεν βρέθηκε Chromium"
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.ui.pbr_viewport import pbr_page_html, scene_payload
    payload = scene_payload(doc, IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), structural_only)
    if drop_kinds:
        payload["objects"] = [o for o in payload["objects"] if o.get("kind") not in drop_kinds]
    after = ""
    if camera:
        # Same calls as PBRViewport.set_camera_preset (a module script runs after the page's own module).
        after = f"<script type=\"module\">window.setCameraPreset({json.dumps(camera)});"
        if camera == "dollhouse":
            from archforge.ui.pbr_viewport import dollhouse_cut_z
            after += f"window.setDollhouseCut({json.dumps(dollhouse_cut_z(doc))});"
        after += "</script>"
    page = pbr_page_html().replace(
        "</body>", "<script>window.__archforgePendingScene=" + json.dumps(payload, separators=(",", ":")) + ";</script>" + after + "</body>", 1)
    html = os.path.splitext(png_path)[0] + ".html"
    with open(html, "w", encoding="utf-8") as fh:
        fh.write(page)
    try:
        run = subprocess.run([exe, "--headless", "--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                              "--ignore-gpu-blocklist", f"--window-size={size[0]},{size[1]}", "--virtual-time-budget=15000",
                              f"--screenshot={png_path}", "file://" + os.path.abspath(html)],
                             capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"{type(exc).__name__}: {exc}"
    finally:
        try:
            os.remove(html)
        except OSError:
            pass
    errors = [ln for ln in run.stderr.splitlines() if "CONSOLE" in ln and ("Error" in ln or "Uncaught" in ln)]
    if errors:
        return "σφάλμα της σελίδας 3D: " + errors[0][-200:]
    if not os.path.exists(png_path) or os.path.getsize(png_path) < 20000:
        return "κενή εικόνα"
    return None
