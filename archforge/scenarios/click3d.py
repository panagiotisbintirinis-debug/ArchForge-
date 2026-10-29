"""Clicks in the real 3D page without Qt or a GPU: what the page sends to Python for a tool.

``clicks(doc, tool)`` loads ``pbr_page_html()`` with ``scene_payload(doc)`` in headless Chromium (Playwright, software
WebGL), activates ``tool``, clicks a grid over the canvas and returns the bridge calls, e.g.
``[['paintMaterial', '{"entity_id": …, "surface_role": "exterior"}'], …]``.  The page's own raycast decides what each
click hits.  Script: ``scripts/toolbox/click_3d.mjs``.  ``available()`` is False where Node/Playwright/Chromium are
missing (tests skip there).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(_ROOT, 'scripts', 'toolbox', 'click_3d.mjs')
_PLAYWRIGHT = '/opt/node22/lib/node_modules/playwright/index.mjs'
_BROWSERS = '/opt/pw-browsers'


def available():
    return bool(shutil.which('node')) and os.path.exists(_PLAYWRIGHT) and os.path.isdir(_BROWSERS)


def clicks(doc, tool, cols=24, rows=14, preset='orbit', timeout=240):
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.ui.pbr_viewport import pbr_page_html, scene_payload
    payload = scene_payload(doc, IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), False)
    with tempfile.TemporaryDirectory() as tmp:
        page, scene = os.path.join(tmp, 'page.html'), os.path.join(tmp, 'scene.json')
        with open(page, 'w', encoding='utf-8') as fh:
            fh.write(pbr_page_html())
        with open(scene, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        run = subprocess.run(['node', SCRIPT, page, scene, tool, str(cols), str(rows), preset],
                             capture_output=True, text=True, timeout=timeout)
    if run.returncode != 0:
        raise RuntimeError(run.stderr[-1500:])
    if 'pageerror' in run.stderr:
        raise RuntimeError('σφάλμα της σελίδας 3D: ' + run.stderr[-800:])
    return json.loads(run.stdout.strip().splitlines()[-1])['calls']
