"""Owner 29/10: «στο έδαφος δεν κάνει τίποτα» — Γλυπτική on the ground: a stroke in the site terrain itself (one undo),
previewed while dragging with the document untouched; on a project without a terrain the first stroke adds it."""
import json

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.site.terrain import stroke_falloff, terrain_height


def test_a_stroke_raises_the_ground_smoothly_to_nothing_at_its_radius():
    params = {'x0': -5, 'y0': -5, 'x1': 5, 'y1': 5, 'elevation': 0.0, 'strokes': [{'x': 0, 'y': 0, 'radius': 2, 'dz': 0.8}]}
    assert terrain_height(params, 0, 0) == pytest.approx(0.8)
    assert 0 < terrain_height(params, 1, 0) < 0.8
    assert terrain_height(params, 2.0, 0) == pytest.approx(0.0) and terrain_height(params, 3, 0) == pytest.approx(0.0)
    params['strokes'].append({'x': 0, 'y': 0, 'radius': 1, 'dz': -0.3})        # strokes add up, in order
    assert terrain_height(params, 0, 0) == pytest.approx(0.5)
    assert stroke_falloff(0.5, 1.0, sharp=True) < stroke_falloff(0.5, 1.0)


def _view():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.pbr_viewport import PBRViewport
    QApplication.instance() or QApplication([])
    doc = Document(); stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 6.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})))
    view = PBRViewport(doc, stack)
    sent = []

    class Page:
        def runJavaScript(self, script, *args):
            sent.append(script)

    class Web:
        def page(self):
            return Page()
    view.web_view = Web()
    view.set_tool('sculpt')
    view.configure_sculpt(operation='pull', radius=1.5)
    return view, doc, stack, sent


def _stroke(view, x, y, amount, entity_id=''):
    view._begin_sculpt_from_web(json.dumps({'entity_id': entity_id, 'surface_role': 'ground', 'point': [x, y, -0.15], 'normal': [0, 0, 1]}))
    view._update_sculpt_from_web(amount)


def test_the_first_ground_stroke_adds_the_terrain_with_it_in_one_undo():
    view, doc, stack, sent = _view()
    done = len(stack.done)
    _stroke(view, 3.0, -4.0, 0.9)
    assert not any(e.kind == 'terrain' for e in doc.entities.values())       # dragging: the project is untouched
    last = sent[-1] if 'archforgeSetScene(' in sent[-1] else next(s for s in reversed(sent) if 'archforgeSetScene(' in s)
    assert '"terrain"' in last                                                  # …but the 3D shows the ground rising
    view._finish_sculpt_from_web()
    terrain = next(e for e in doc.entities.values() if e.kind == 'terrain')
    assert terrain.params['strokes'] == [{'x': 3.0, 'y': -4.0, 'radius': 1.5, 'dz': 0.9}]
    assert terrain_height(terrain.params, 3.0, -4.0) == pytest.approx(-0.15 + 0.9)
    assert len(stack.done) == done + 1
    stack.undo()
    assert not any(e.kind == 'terrain' for e in doc.entities.values())


def test_a_stroke_on_the_terrain_adds_to_it_and_push_lowers():
    view, doc, stack, _sent = _view()
    _stroke(view, 3.0, -4.0, 0.9); view._finish_sculpt_from_web()
    terrain = next(e for e in doc.entities.values() if e.kind == 'terrain')
    view.configure_sculpt(operation='push')
    _stroke(view, 3.0, -4.0, 0.4, terrain.id)
    assert len(doc.get(terrain.id).params['strokes']) == 1                    # still only the first while dragging
    view._finish_sculpt_from_web()
    strokes = doc.get(terrain.id).params['strokes']
    assert [s['dz'] for s in strokes] == [0.9, -0.4]
    stack.undo()
    assert [s['dz'] for s in doc.get(terrain.id).params['strokes']] == [0.9]


def test_smooth_on_the_ground_is_refused_with_a_message():
    view, doc, stack, _sent = _view()
    view.configure_sculpt(operation='smooth')
    messages = []
    view.statusChanged.connect(messages.append)
    _stroke(view, 3.0, -4.0, 0.5)
    view._finish_sculpt_from_web()
    assert not any(e.kind == 'terrain' for e in doc.entities.values())
    assert any('Λείανση' in m for m in messages), messages


def test_the_real_3d_page_sends_a_stroke_from_the_open_ground():
    from archforge.scenarios import click3d
    if not click3d.available():
        pytest.skip('χωρίς Node / Playwright / Chromium')
    doc = Document()
    doc.add(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2}))
    calls = click3d.run_in_page(doc, """
    window.setCameraPreset('orbit'); window.setActiveTool('sculpt');
    await new Promise((r) => setTimeout(r, 1200));
    window.__calls = [];
    const canvas = document.querySelector('canvas');
    const box = canvas.getBoundingClientRect();
    const at = (y) => ({clientX: box.left + 30, clientY: box.top + box.height - y, button: 0, buttons: 1, pointerId: 1, bubbles: true, cancelable: true});
    canvas.dispatchEvent(new PointerEvent('pointerdown', at(40)));
    canvas.dispatchEvent(new PointerEvent('pointermove', at(140)));
    canvas.dispatchEvent(new PointerEvent('pointerup', {...at(140), buttons: 0}));
    return window.__calls;
    """)
    names = [c[0] for c in calls]
    assert names[:1] == ['beginSculpt'] and 'updateSculpt' in names and names[-1] == 'endSculpt', names
    begin = json.loads(calls[0][1])
    assert begin['entity_id'] == '' and begin['surface_role'] == 'ground'


# --- The plan shows it (owner 29/10: «στο 2Δ … την παραμόρφωση με νούμερα και σχεδιαστικά αχνές γραμμές») ----------

def test_the_plan_shows_faint_contours_and_the_height_of_each_ground_stroke():
    from archforge.core.plan_scene import build_plan_frame
    view, doc, stack, _sent = _view()
    _stroke(view, 3.0, -4.0, 0.8); view._finish_sculpt_from_web()
    view.configure_sculpt(operation='push')
    terrain = next(e for e in doc.entities.values() if e.kind == 'terrain')
    _stroke(view, 6.0, -6.0, 0.4, terrain.id); view._finish_sculpt_from_web()
    frame = build_plan_frame(doc)
    labels = [dict(p.meta)['text'] for p in frame.primitives if p.role == 'sculpt-label']
    assert labels == ['+0.80 m', '-0.40 m']
    contours = [p for p in frame.primitives if p.role == 'sculpt-contour']
    assert len(contours) > 10
    levels = {dict(p.meta)['z'] for p in contours}
    assert max(levels) > 0.3 and min(levels) < -0.3           # rings up on the mound, down in the hollow
    assert sum(1 for p in frame.primitives if p.role == 'sculpt-outline') == 2


def test_the_plan_shows_how_far_a_wall_was_sculpted():
    from archforge.core.plan_scene import build_plan_frame
    view, doc, stack, _sent = _view()
    wall = next(e for e in doc.entities.values() if e.kind == 'wall')
    view._begin_sculpt_from_web(json.dumps({'entity_id': wall.id, 'surface_role': 'exterior', 'point': [3, 0.1, 1.3], 'normal': [0, 1, 0]}))
    view._update_sculpt_from_web(1.24); view._finish_sculpt_from_web()
    frame = build_plan_frame(doc)
    assert [dict(p.meta)['text'] for p in frame.primitives if p.role == 'sculpt-label'] == ['+1.24 m']
    assert any(p.role == 'sculpt-outline' and p.entity_id == wall.id for p in frame.primitives)
    stack.undo()
    assert not any(p.role == 'sculpt-label' for p in build_plan_frame(doc).primitives)


def test_contours_stop_at_the_edge_of_the_ground():
    from archforge.site.sculpt_plan import stroke_contours
    params = {'x0': 0, 'y0': 0, 'x1': 10, 'y1': 10, 'elevation': 0.0, 'strokes': [{'x': 9.5, 'y': 5, 'radius': 2, 'dz': 0.8}]}
    segments = stroke_contours(params)
    assert segments and all(0 <= x <= 10 and 0 <= y <= 10 for _z, seg in segments for x, y in seg)


def test_a_surface_that_cannot_be_sculpted_says_so_in_words():
    view, doc, stack, _sent = _view()
    roof = Entity('site_path', {'x1': 0.0, 'y1': -3.0, 'x2': 6.0, 'y2': -3.0, 'z': 0.0, 'style': 'path', 'width': 1.0,
                                'thickness': 0.1})
    stack.execute(AddEntity(roof))
    messages = []
    view.statusChanged.connect(messages.append)
    view._begin_sculpt_from_web(json.dumps({'entity_id': roof.id, 'surface_role': 'top', 'point': [3, 2, 2.9], 'normal': [0, 0, 1]}))
    assert messages and 'δεν πλάθεται' in messages[-1] and 'έδαφος' in messages[-1], messages
