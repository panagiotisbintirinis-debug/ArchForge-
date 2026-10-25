"""Φωτισμός ανά χώρο (owner 25/10): the lights of the building by room, one luminaire at a time — on/off, dimmer,
replacement at the same point — in a small strip at the bottom with a pop-up per room; direction only for the
fittings that turn."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')

import pytest

from archforge.core.commands import CommandStack
from archforge.core.model import Document
from archforge.mep.lighting import OUTSIDE_ROOMS, lights_by_room, replace_luminaire, replacement_choices
from tests.test_electrical import _house, _pt


def _two_rooms():
    doc = Document(); stack = CommandStack(doc); _house(stack)       # rooms 0–4 and 4–8 (x)
    _pt(stack, 'panel', 0.3, 3.0)
    left = [_pt(stack, 'light', 2.0, 3.0), _pt(stack, 'wall_light', 0.3, 1.5), _pt(stack, 'wall_light', 0.3, 4.5),
            _pt(stack, 'led_strip', 1.0, 1.0, x2=3.0, y2=1.0)]
    right = [_pt(stack, 'spot', 6.0, 3.0)]
    garden = _pt(stack, 'light', 12.0, 3.0)
    _pt(stack, 'socket', 2.0, 0.3)                                    # not a light: never listed
    return doc, stack, left, right, garden


def test_lights_are_listed_by_room_and_by_kind():
    doc, _stack, left, right, garden = _two_rooms()
    rooms = lights_by_room(doc)
    assert len(rooms) == 3 and rooms[-1]['title'] == OUTSIDE_ROOMS
    by_ids = {frozenset(i for g in r['groups'] for i in g['ids']): r for r in rooms}
    room = by_ids[frozenset(e.id for e in left)]
    assert [g['label'] for g in room['groups']] == ['Κεντρικό', 'Απλίκες', 'Κρυφός φωτισμός']
    assert next(g for g in room['groups'] if g['label'] == 'Απλίκες')['ids'] == [left[1].id, left[2].id]
    assert frozenset(e.id for e in right) in by_ids
    assert rooms[-1]['groups'][0]['ids'] == [garden.id]


def test_replace_one_luminaire_at_the_same_point_with_one_undo():
    doc, stack, left, _right, _garden = _two_rooms()
    from archforge.core.commands import UpdateEntity
    lamp = left[0]
    stack.execute(UpdateEntity(lamp.id, {'dim_level': 0.4, 'automation_group': 'Σαλόνι', 'lumen': 800.0, 'kelvin': 2700.0}))
    choices = replacement_choices(doc.get(lamp.id))
    assert ('Χωνευτό φωτιστικό οροφής', 'downlight', None) in choices
    assert all(t != 'led_strip' for _l, t, _c in choices)             # a point is replaced by a point
    strip_choices = replacement_choices(doc.get(left[3].id))
    assert {t for _l, t, _c in strip_choices} == {'led_strip'} and any(c for _l, _t, c in strip_choices)
    n = len(doc.entities)
    command, new = replace_luminaire(doc, lamp.id, 'downlight', 'tpl_downlight_12w_36')
    stack.execute(command)
    assert lamp.id not in doc.entities and len(doc.entities) == n
    p = doc.get(new.id).params
    assert (p['x'], p['y'], p['point_type'], p['dim_level'], p['automation_group']) == (2.0, 3.0, 'downlight', 0.4, 'Σαλόνι')
    assert (p['power_w'], p['beam_deg'], p['catalog_id']) == (12.0, 36.0, 'tpl_downlight_12w_36')   # the new product's own
    for other in left[1:]:
        assert doc.get(other.id).params['point_type'] == other.params['point_type']                 # only that one
    stack.undo()
    assert new.id not in doc.entities and doc.get(lamp.id).params['lumen'] == 800.0
    with pytest.raises(ValueError):
        replace_luminaire(doc, lamp.id, 'led_strip')


def test_strip_at_the_bottom_changes_one_luminaire_at_a_time():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QCheckBox, QDockWidget, QSlider, QToolButton
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        doc, stack, left, right, _garden = _two_rooms()
        window._replace_project(doc)
        dock, strip = window._lighting_dock, window._lighting_strip
        assert window.dockWidgetArea(dock) == Qt.DockWidgetArea.BottomDockWidgetArea and dock.isHidden()
        assert dock.features() & QDockWidget.DockWidgetFeature.DockWidgetFloatable   # movable anywhere, resizable
        sun = window._mockup_sun_menu.actions()
        k = sun.index(window._lighting_strip_action)                  # right under «Φώτα του έργου: …»
        assert sun[k - 1].text().startswith('Φώτα του έργου:') and window._lighting_strip_action.isCheckable()
        window._lighting_strip_action.trigger(); app.processEvents()
        assert not dock.isHidden()                                     # shown to adjust …
        window._lighting_strip_action.trigger(); app.processEvents()
        assert dock.isHidden()                                         # … closed when done
        strip.refresh()
        assert len(strip.buttons) == 3
        title = next(t for t in strip.buttons if t != OUTSIDE_ROOMS and '4/4' in strip.buttons[t].text())
        menu = strip.buttons[title].menu()
        strip._fill(menu, title)
        rows = {r.objectName()[len('lightRow_'):]: r for r in (a.defaultWidget() for a in menu.actions()
                                                               if hasattr(a, 'defaultWidget') and a.defaultWidget())}
        assert set(rows) == {e.id for e in left}
        n = len(window.stack.done)
        rows[left[1].id].findChild(QCheckBox, 'lightRowOn').setChecked(False)          # one απλίκα off
        assert window.doc.get(left[1].id).params['light_on'] == 0 and len(window.stack.done) == n + 1
        assert 'light_on' not in window.doc.get(left[2].id).params                     # the other απλίκα untouched
        dim = rows[left[0].id].findChild(QSlider, 'lightRowDim')
        dim.setValue(30)                                                               # keyboard / click: commits
        assert window.doc.get(left[0].id).params['dim_level'] == 0.3
        assert all('dim_level' not in window.doc.get(e.id).params or e.id == left[0].id for e in left)
        strip.refresh(); app.processEvents()
        assert '3/4' in strip.buttons[title].text()
        change = rows[left[0].id].findChild(QToolButton, 'lightRowChange')
        spot = next(a for a in change.menu().actions() if a.text() == 'Σποτ (κατευθυνόμενο)')
        spot.trigger()
        new = window.doc.get(window.doc.selection[0])
        assert new.params['point_type'] == 'spot' and new.params['dim_level'] == 0.3 and left[0].id not in window.doc.entities
        window._undo()
        assert window.doc.get(left[0].id).params['point_type'] == 'light'
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_direction_only_for_fittings_that_turn_dimmer_for_all():
    from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QSlider
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        doc, _stack, left, right, _garden = _two_rooms()
        window._replace_project(doc)

        def rows(eid):
            window.doc.select([eid]); window.refresh_inspector(); app.processEvents()
            form = window.form
            out = {}
            for i in range(form.rowCount()):
                label = form.itemAt(i, form.ItemRole.LabelRole)
                field = form.itemAt(i, form.ItemRole.FieldRole)
                if label and field and label.widget() and field.widget():
                    out[label.widget().text()] = field.widget()
            return out
        fixed = rows(left[0].id)                                       # πλαφονιέρα
        assert isinstance(fixed['Κατεύθυνση'], QLabel) and isinstance(fixed['Ένταση (ροοστάτης)'], QSlider)
        for eid in (left[1].id, left[3].id):                           # απλίκα, ταινία
            r = rows(eid)
            assert isinstance(r['Κατεύθυνση'], QLabel) and isinstance(r['Ένταση (ροοστάτης)'], QSlider)
        aimed = rows(right[0].id)                                      # σποτ
        assert isinstance(aimed['Κατεύθυνση'], QComboBox) and 'Κλίση δέσμης' in aimed
        assert isinstance(aimed['Ένταση (ροοστάτης)'], QSlider)
    finally:
        window._mark_clean(); window.close(); app.processEvents()


# -- luminous library models (content pack, PR #157): same strip, their own fields, aim only when declared ----------
def _lit_asset(name, role, aimable=False, dimmable=True, kind='spot'):
    import math
    from archforge.library import assets
    source = dict(kind=kind, position=[0.0, 0.0, 0.3], direction=[0, 0, -1], intensity_cd=200.0, color=[1, 1, 1],
                  range_m=0.0, provenance={'light_role': role, 'aimable': aimable, 'render_dimmable': dimmable})
    if kind == 'spot':
        source.update(outer_cone_rad=math.pi / 6, inner_cone_rad=0.0)
    aid, _ = assets.store_asset(name, [((-.1, -.1, 0), (.1, -.1, 0), (0, .1, .3))], {'source': 'test'},
                                category=('Φωτισμός',), lighting={'sources': [source]})
    return aid


def _place(stack, aid, x, y):
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.library import assets
    from archforge.ui.library_instance_integration import library_instance_params
    record = assets.load_asset(aid)
    e = Entity('library_object', library_instance_params(record, x=x, y=y, z=0.0), name=record['name'])
    stack.execute(AddEntity(e))
    return e


def test_library_fixtures_join_their_room_with_their_own_controls(tmp_path, monkeypatch):
    import math
    from archforge.library.lighting import instance_light_specs
    from archforge.mep.lighting import (fixture_aimable, fixture_changes, fixture_on, replace_fixture,
                                        replacement_choices)
    from archforge.core.commands import UpdateEntity
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path))
    doc, stack, left, right, _garden = _two_rooms()
    pendant = _lit_asset('Κρεμαστό δοκιμής', 'pendant')
    projector = _lit_asset('Προβολέας με βραχίονα', 'garden_projector', aimable=True)
    plain = _lit_asset('Κολωνάκι δοκιμής', 'bollard', dimmable=False, kind='point')
    lamp = _place(stack, pendant, 1.5, 4.0)                       # left room, next to its electrical lights
    proj = _place(stack, projector, 12.0, 1.0)                    # garden
    room = next(r for r in lights_by_room(doc) if lamp.id in [i for g in r['groups'] for i in g['ids']])
    assert {e.id for e in left} < {i for g in room['groups'] for i in g['ids']}
    assert next(g for g in room['groups'] if lamp.id in g['ids'])['label'] == 'Κρεμαστά'
    outside = lights_by_room(doc)[-1]
    assert outside['title'] == OUTSIDE_ROOMS and next(g for g in outside['groups'] if proj.id in g['ids'])['label'] == 'Προβολείς'
    # One state per kind: the pack's light_enabled / light_level, never light_on / dim_level on a library object.
    assert fixture_changes(doc.get(lamp.id), on=False, level=0.5) == {'light_enabled': 0.0, 'light_level': 0.5}
    stack.execute(UpdateEntity(lamp.id, fixture_changes(doc.get(lamp.id), level=0.5)))
    assert instance_light_specs(doc.get(lamp.id))[0]['intensity'] == 100.0 and fixture_on(doc.get(lamp.id))
    # Aim only where the model says so: the projector turns, the pendant (a spot cone too) does not.
    assert fixture_aimable(doc.get(proj.id)) and not fixture_aimable(doc.get(lamp.id))
    stack.execute(UpdateEntity(proj.id, {'aim_tilt_deg': 60.0, 'aim_azimuth_deg': 0.0}))
    spec = instance_light_specs(doc.get(proj.id))[0]
    d = [t - q for t, q in zip(spec['target'], spec['position'])]
    assert d == pytest.approx([0.0, math.sin(math.radians(60)), -math.cos(math.radians(60))])   # north, 60° from down
    stack.execute(UpdateEntity(lamp.id, {'aim_tilt_deg': 60.0}))
    spec = instance_light_specs(doc.get(lamp.id))[0]
    assert [t - q for t, q in zip(spec['target'], spec['position'])] == pytest.approx([0, 0, -1])   # fixed beam
    # Replace with another luminous model at the same place; only lit models are offered.
    choices = replacement_choices(doc.get(lamp.id))
    assert {c for _l, k, c in choices if k == 'library'} == {pendant, projector, plain}
    command, new = replace_fixture(doc, lamp.id, 'library', plain)
    stack.execute(command)
    p = doc.get(new.id).params
    assert (p['x'], p['y'], p['asset'], p['light_level']) == (1.5, 4.0, plain, 0.5) and 'aim_tilt_deg' not in p
    stack.undo()
    assert lamp.id in doc.entities and new.id not in doc.entities


def test_strip_rows_for_library_fixtures(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QCheckBox, QDial, QLabel, QSlider
    from archforge.ui.main_window import MainWindow
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        doc, stack, left, _right, _garden = _two_rooms()
        window._replace_project(doc)
        plain = _lit_asset('Κολωνάκι δοκιμής', 'bollard', dimmable=False, kind='point')
        projector = _lit_asset('Προβολέας με βραχίονα', 'garden_projector', aimable=True)
        post = _place(window.stack, plain, 12.0, 1.0)
        proj = _place(window.stack, projector, 12.0, 4.0)
        strip = window._lighting_strip
        strip.refresh()
        menu = strip.buttons[OUTSIDE_ROOMS].menu()
        strip._fill(menu, OUTSIDE_ROOMS)
        rows = {a.defaultWidget().objectName()[len('lightRow_'):]: a.defaultWidget() for a in menu.actions()
                if hasattr(a, 'defaultWidget') and a.defaultWidget()}
        assert rows[post.id].findChild(QSlider, 'lightRowDim').isEnabled() is False     # model is on/off only
        rows[proj.id].findChild(QCheckBox, 'lightRowOn').setChecked(False)
        assert window.doc.get(proj.id).params['light_enabled'] == 0.0
        assert 'light_on' not in window.doc.get(proj.id).params
        assert window.doc.get(post.id).params['light_enabled'] == 1.0                  # the other one untouched
        # Ιδιότητες: aim rows for the projector, «Σταθερή δέσμη» for the post.
        window.doc.select([proj.id]); window.refresh_inspector(); app.processEvents()
        assert window.form.parentWidget().findChild(QDial, 'aimTilt') is not None
        window.doc.select([post.id]); window.refresh_inspector(); app.processEvents()
        assert window.form.parentWidget().findChild(QDial, 'aimTilt') is None
        assert any(isinstance(w, QLabel) and w.text().startswith('Σταθερή δέσμη')
                   for w in window.form.parentWidget().findChildren(QLabel))
    finally:
        window._mark_clean(); window.close(); app.processEvents()
