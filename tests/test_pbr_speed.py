"""3D speed (owner 29/10 «τρόπος να επιταχύνουμε το 3Δ»): the sun's shadow map is drawn again only when the model,
the lights or the cut change — never because the camera moved — and a captured picture is always full quality.
Measured on the owner's two-storey house: orbit frame 3144 → 935 ms (software WebGL; docs/WORKLOG.md 29/10)."""
import pytest

from archforge.core.model import Document, Entity
from archforge.scenarios import click3d


def _doc():
    doc = Document()
    doc.add(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2}))
    doc.add(Entity('box', {'x': 1.0, 'y': 2.0, 'z': 0.0, 'width': 1.0, 'depth': 1.0, 'height': 1.0}))
    return doc


def test_camera_moves_do_not_redraw_shadows_but_a_model_change_does():
    if not click3d.available():
        pytest.skip('χωρίς Node / Playwright / Chromium')
    result = click3d.run_in_page(_doc(), """
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    await wait(1500);
    const canvas = document.querySelector('canvas');
    const before = window.archforgeShadowRedraws;
    for (let i = 0; i < 6; i++) {                       // zoom with the wheel: a camera-only change
      canvas.dispatchEvent(new WheelEvent('wheel', {deltaY: 120, clientX: 400, clientY: 260, bubbles: true}));
      await wait(150);
    }
    await wait(800);
    const afterCamera = window.archforgeShadowRedraws;
    window.archforgeSetScene(payload, false);           // the model is pushed again (new geometry)
    await wait(1200);
    const afterModel = window.archforgeShadowRedraws;
    const still = window.archforgeCaptureFrame(400, 260).length;
    return {before, afterCamera, afterModel, still};
    """)
    assert result['afterCamera'] == result['before'], result
    assert result['afterModel'] > result['afterCamera'], result
    assert result['still'] > 1000
