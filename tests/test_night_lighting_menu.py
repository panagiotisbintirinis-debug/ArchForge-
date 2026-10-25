"""Owner 25/10: «το πρόγραμμα για δοκιμές φωτισμού σε νυχτερινό δεν το είδα ποτέ στην πράξη — πού είναι;»

The night mode of ui/lighting_system.py had no command: «Ήλιος & ουρανός ▸ Νύχτα» turns it on, an hour turns it off.
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')

from PySide6.QtWidgets import QApplication


def test_night_is_in_the_sun_menu_and_an_hour_brings_the_day_back():
    app = QApplication.instance() or QApplication([])
    import archforge.ui.app  # noqa: F401  (installs the lighting system, as the program does)
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
    assert 2.0 < spec['position'][2] <= 2.7           # under the 2,70 m ceiling, not on the floor
    assert spec['shadows'] is True
