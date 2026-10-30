"""Owner 29/10: «τα φώτα ήταν έντονα και την ημέρα … μετά δεν έχει καθόλου, ούτε τη νύχτα».

- A luminaire without data-sheet lumen is drawn with the reference lamp of the shipped fixtures (806 lm / 370 lm,
  content/lights/SOURCES.txt), not 700 cd (~8 800 lm) that burnt rooms white.
- «Φώτα του έργου: αυτόματα» lights them at night *or* when the project's sun is below the horizon.
- At night with not one luminaire lit, the status bar says why.
"""
import math

import pytest

from archforge.core.model import Document, Entity
from archforge.scenarios import click3d


def _light(**kw):
    return Entity('electrical_point', {'x': 1.0, 'y': 1.0, 'z': 0.0, 'point_type': 'light', 'power_w': 60.0, **kw})


def test_a_luminaire_without_lumen_is_drawn_with_the_reference_lamp_not_700_cd():
    from archforge.ui.lighting_system import _entity_light_spec
    doc = Document()
    light = _light(); doc.add(light)
    spec = _entity_light_spec(light, doc)
    assert spec['intensity'] == pytest.approx(806.0 / (4 * math.pi))          # 64.1 cd
    spot = _light(point_type='spot', beam_deg=36.0); doc.add(spot)
    assert _entity_light_spec(spot, doc)['intensity'] == pytest.approx(370.0 / (2 * math.pi * (1 - math.cos(math.radians(18)))))
    dimmed = _light(dim_level=0.5); doc.add(dimmed)
    assert _entity_light_spec(dimmed, doc)['intensity'] == pytest.approx(806.0 / (4 * math.pi) * 0.5)
    measured = _light(lumen=400.0, kelvin=3000.0); doc.add(measured)
    assert _entity_light_spec(measured, doc)['intensity'] == pytest.approx(400.0 / (4 * math.pi))   # the data sheet wins


def test_auto_project_lights_follow_the_sun_below_the_horizon():
    if not click3d.available():
        pytest.skip('χωρίς Node / Playwright / Chromium')
    doc = Document()
    doc.add(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2}))
    result = click3d.run_in_page(doc, """
    window.setArchitecturalLightingMode('day');
    window.setArchitecturalLights({project_lights: 'auto', lights: [{id: 'l', kind: 'point', intensity: 64, position: [1, 1, 2.4]}]});
    window.setSun(40, 180);  const noon = window.__archforgeProjectLightsOn;
    window.setSun(-5, 280);  const afterSunset = window.__archforgeProjectLightsOn;
    window.setSun(3, 297);   const dusk = window.__archforgeProjectLightsOn;
    window.setArchitecturalLights({project_lights: 'off', lights: []});
    window.setSun(-5, 280);  const off = window.__archforgeProjectLightsOn;
    return {noon, afterSunset, dusk, off};
    """)
    assert result == {'noon': False, 'afterSunset': True, 'dusk': False, 'off': False}, result


def test_night_without_one_lit_luminaire_says_why():
    from PySide6.QtWidgets import QApplication
    from archforge.core.commands import CommandStack
    from archforge.ui.lighting_system import install_lighting_system
    QApplication.instance() or QApplication([])
    install_lighting_system()
    from archforge.ui.pbr_viewport import PBRViewport
    doc = Document()
    doc.add(_light(light_on=0))
    view = PBRViewport(doc, CommandStack(doc))
    messages = []
    view.statusChanged.connect(messages.append)
    view.set_lighting_mode('night')
    assert any('κανένα αναμμένο φωτιστικό' in m for m in messages), messages
    messages.clear()
    doc.add(_light())
    view.set_lighting_mode('night')
    assert not any('κανένα αναμμένο' in m for m in messages), messages
