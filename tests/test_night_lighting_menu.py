"""Owner 25/10: «το πρόγραμμα για δοκιμές φωτισμού σε νυχτερινό δεν το είδα ποτέ στην πράξη — πού είναι;»

The night mode of ui/lighting_system.py had no command: «Ήλιος & ουρανός ▸ Νύχτα» turns it on, an hour turns it off.
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')

from PySide6.QtWidgets import QApplication


def test_night_is_in_the_sun_menu_and_an_hour_brings_the_day_back():
    app = QApplication.instance() or QApplication([])
    # Only the lighting layer, as tests/test_lighting_system.py does: importing archforge.ui.app would install every
    # startup layer on MainWindow for the rest of the run and break later tests.
    from archforge.ui.rendering_quality_upgrade import install_rendering_quality_upgrade
    from archforge.ui.lighting_system import install_lighting_system
    install_rendering_quality_upgrade()          # app.py's order: the quality look first, then the lighting
    install_lighting_system()
    from archforge.ui.main_window import MainWindow
    w = MainWindow()
    app.processEvents()
    night = w._mockup_night_action
    assert night.text().startswith('Νύχτα') and night in w._mockup_sun_menu.actions()
    night.trigger()
    assert w.pbr_view._architectural_lighting_mode == 'night'
    noon = next(a for a in w._mockup_sun_menu.actions() if a.text().startswith('Μεσημέρι'))
    noon.trigger()
    assert w.pbr_view._architectural_lighting_mode == 'day'


def test_a_ceiling_light_sits_at_the_ceiling_and_walls_stop_it():
    """Owner 25/10 (night, his file 123): «το φως έπρεπε να φαίνεται μόνο από τα παράθυρα» — the light sat on the
    floor (its point's z) and cast no shadow, so it lit the eaves, the ground and the slab through walls and roof."""
    import json
    from archforge.core.model import Document
    from archforge.ui.lighting_system import _entity_light_spec
    path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'user_drive', 'files', 'owner_123.archforge')
    with open(path, encoding='utf-8') as f:
        doc = Document.from_dict(json.load(f))
    light = next(e for e in doc.entities.values() if e.kind == 'electrical_point' and e.params['point_type'] == 'light')
    spec = _entity_light_spec(light, doc)
    assert 2.0 < spec['position'][2] < 2.7            # under the top of the 2,70 m walls, not on the floor
    assert spec['shadows'] is True


def test_project_lights_are_off_by_day_and_have_a_switch_in_the_sun_menu():
    """Owner 25/10: «μεσημέρι και τα φώτα αναμμένα — πού τα κλείνω;»"""
    app = QApplication.instance() or QApplication([])
    from archforge.ui import pbr_viewport
    from archforge.ui.rendering_quality_upgrade import install_rendering_quality_upgrade
    from archforge.ui.lighting_system import install_lighting_system
    install_rendering_quality_upgrade()
    install_lighting_system()
    html = pbr_viewport._PBR_HTML
    # By default (auto) the lights' group is shown at night, or after sunset (owner 29/10); the mode and the lights
    # both re-check it.
    assert 'architecturalLightsSwitch === "auto" && (architecturalLightingMode === "night" || sunDown)' in html
    assert html.count('afUpdateLightVisibility();') >= 2
    from archforge.ui.main_window import MainWindow
    w = MainWindow()
    app.processEvents()
    try:
        actions = w._mockup_project_lights_actions
        assert set(actions) == {'auto', 'on', 'off'} and actions['auto'].isChecked()
        assert all(a in w._mockup_sun_menu.actions() for a in actions.values())
        assert w.pbr_view._lighting_payload is not None
        actions['off'].trigger()
        assert w.pbr_view._project_lights == 'off'
        actions['on'].trigger()
        assert w.pbr_view._project_lights == 'on' and not actions['auto'].isChecked()
    finally:
        w._mark_clean(); w.close(); app.processEvents()
