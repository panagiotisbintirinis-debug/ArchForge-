"""The real 3D page without Qt or a GPU: run a script in it, or click it with a tool.

``run_in_page(doc, js)`` loads ``pbr_page_html()`` with ``scene_payload(doc)`` in headless Chromium (Playwright,
software WebGL), runs ``js`` (the body of an async function; ``payload`` is the scene) and returns its result.
``clicks(doc, tool)`` activates ``tool``, clicks a grid over the canvas and returns the bridge calls the page made,
e.g. ``[['paintMaterial', '{"entity_id": …, "surface_role": "exterior"}'], …]`` — the page's own raycast decides what
each click hits.  Script: ``scripts/toolbox/page_3d.mjs``.  ``available()`` is False where Node/Playwright/Chromium
are missing (tests skip there).  Timings in software WebGL are slow and only comparable with each other.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(_ROOT, 'scripts', 'toolbox', 'page_3d.mjs')
_PLAYWRIGHT = '/opt/node22/lib/node_modules/playwright/index.mjs'
_BROWSERS = '/opt/pw-browsers'


def available():
    return bool(shutil.which('node')) and os.path.exists(_PLAYWRIGHT) and os.path.isdir(_BROWSERS)


def run_in_page(doc, js, size=(800, 520), timeout=300, before=""):
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    # As ui/app.py: the page the user sees has the quality upgrade and the project's lights.
    from archforge.ui.rendering_quality_upgrade import install_rendering_quality_upgrade
    from archforge.ui.lighting_system import install_lighting_system
    install_rendering_quality_upgrade()
    install_lighting_system()
    from archforge.ui.pbr_viewport import pbr_page_html, scene_payload
    payload = scene_payload(doc, IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), False)
    with tempfile.TemporaryDirectory() as tmp:
        files = {name: os.path.join(tmp, name) for name in ('page.html', 'scene.json', 'script.js')}
        with open(files['page.html'], 'w', encoding='utf-8') as fh:
            fh.write(pbr_page_html())
        with open(files['scene.json'], 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        with open(files['script.js'], 'w', encoding='utf-8') as fh:
            fh.write(js)
        run = subprocess.run(['node', SCRIPT, files['page.html'], files['scene.json'], files['script.js'],
                              str(size[0]), str(size[1])], capture_output=True, text=True, timeout=timeout)
    if run.returncode != 0:
        raise RuntimeError(run.stderr[-1500:])
    if 'pageerror' in run.stderr:
        raise RuntimeError('σφάλμα της σελίδας 3D: ' + run.stderr[-800:])
    return json.loads(run.stdout.strip().splitlines()[-1])['result']


def clicks(doc, tool, cols=24, rows=14, preset='orbit'):
    # The pointer events go to the canvas inside the page (the same listeners and raycast as a real mouse):
    # Playwright's own mouse waits for a rendered frame per event — minutes with software WebGL.
    js = f"""
    window.setCameraPreset({json.dumps(preset)});
    window.setActiveTool({json.dumps(tool)});
    await new Promise((r) => setTimeout(r, 1500));
    window.__calls = [];
    const canvas = document.querySelector('canvas');
    const box = canvas.getBoundingClientRect();
    for (let r = 1; r <= {int(rows)}; r++) {{
      for (let c = 1; c <= {int(cols)}; c++) {{
        const at = {{clientX: box.left + box.width * c / {int(cols) + 1}, clientY: box.top + box.height * r / {int(rows) + 1},
                    button: 0, buttons: 1, pointerId: 1, isPrimary: true, bubbles: true, cancelable: true}};
        canvas.dispatchEvent(new PointerEvent('pointerdown', at));
        canvas.dispatchEvent(new PointerEvent('pointerup', {{...at, buttons: 0}}));
      }}
    }}
    return window.__calls;
    """
    return run_in_page(doc, js)
