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
    const frames = async (n) => { const f = window.archforgeFrames; while (window.archforgeFrames - f < n) await wait(50); };
    await frames(2);
    const canvas = document.querySelector('canvas');
    const before = window.archforgeShadowRedraws;
    for (let i = 0; i < 6; i++) {                       // zoom with the wheel: a camera-only change
      canvas.dispatchEvent(new WheelEvent('wheel', {deltaY: 120, clientX: 400, clientY: 260, bubbles: true}));
      await frames(1);
    }
    await frames(3);
    const afterCamera = window.archforgeShadowRedraws;
    window.archforgeSetScene(payload, false);           // the model is pushed again (new geometry)
    window.archforgeWakeRender(5);
    await frames(2);
    const afterModel = window.archforgeShadowRedraws;
    const still = window.archforgeCaptureFrame(400, 260).length;
    return {before, afterCamera, afterModel, still};
    """)
    assert result['afterCamera'] == result['before'], result
    assert result['afterModel'] > result['afterCamera'], result
    assert result['still'] > 1000


def test_moving_frames_are_lighter_except_in_a_lighting_study():
    """Owner 29/10: in one view the moving camera may draw a lighter frame; in the lighting study everything, always."""
    if not click3d.available():
        pytest.skip('χωρίς Node / Playwright / Chromium')
    result = click3d.run_in_page(_doc(), """
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    const canvas = document.querySelector('canvas');
    const zoom = async () => {
      // Software WebGL is slow (more so under load): keep the camera moving (in and out, never against the zoom
      // limit) until frames have been drawn; every drawn frame is logged by the page.
      window.archforgeFrameLog = [];
      const start = window.archforgeFrames;
      for (let i = 0; i < 200 && window.archforgeFrames - start < 4; i++) {
        canvas.dispatchEvent(new WheelEvent('wheel', {deltaY: i % 2 ? 60 : -60, clientX: 400, clientY: 260, bubbles: true}));
        await wait(60);
      }
      const lighter = window.archforgeFrameLog.some((m) => m === true);
      const f = window.archforgeFrames;
      while (window.archforgeFrames - f < 2) await wait(50);
      return {lighter, atRest: window.archforgeMovingFrame};
    };
    await wait(1200);
    const normal = await zoom();
    window.setArchitecturalLights({project_lights: 'on', lights: []});
    const study = await zoom();
    return {normal, study};
    """)
    assert result['normal'] == {'lighter': True, 'atRest': False}, result
    assert result['study'] == {'lighter': False, 'atRest': False}, result


# --- Only what changed (owner 29/10: «να στέλνονται μόνο τα αλλαγμένα») ---------------------------------------------

def test_scene_changes_keeps_unchanged_objects_and_sends_the_changed_ones():
    from archforge.ui.pbr_viewport import scene_changes
    first = {'objects': [{'id': 'a', 'kind': 'wall', 'vertices': [[0, 0, 0]]},
                         {'id': 'b', 'kind': 'box', 'vertices': [[1, 1, 1]]}], 'selected': []}
    full, is_full = scene_changes(first, None)
    assert is_full and [o['key'] for o in full['objects']] == ['a#0', 'b#0'] and 'keep' not in full
    sent = full.pop('_sent')
    second = {'objects': [{'id': 'a', 'kind': 'wall', 'vertices': [[0, 0, 0]]},
                          {'id': 'b', 'kind': 'box', 'vertices': [[2, 1, 1]]},
                          {'id': 'c', 'kind': 'box', 'vertices': [[3, 1, 1]]}], 'selected': ['b']}
    diff, is_full = scene_changes(second, sent)
    assert not is_full
    assert diff['keep'] == ['a#0'] and [o['key'] for o in diff['objects']] == ['b#0', 'c#0']
    assert diff['selected'] == ['b']


def test_an_edit_sends_only_the_changed_objects_to_the_3d_page(monkeypatch):
    import json
    from PySide6.QtWidgets import QApplication
    from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
    from archforge.ui.pbr_viewport import PBRViewport
    QApplication.instance() or QApplication([])
    doc = _doc()
    other = Entity('wall', {'x1': 0.0, 'y1': 3.0, 'x2': 4.0, 'y2': 3.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
    stack = CommandStack(doc)
    stack.execute(AddEntity(other))
    view = PBRViewport(doc, stack)
    scripts = []

    class Page:
        def runJavaScript(self, script, *args):
            scripts.append(script)

    class Web:
        def page(self):
            return Page()
    view.web_view = Web()
    view.redraw(force_full=True)
    whole = next(s for s in scripts if 'archforgeSetScene' in s)
    assert '__archforgePendingScene' in whole and '"keep"' not in whole
    scripts.clear()
    stack.execute(UpdateEntity(other.id, {'height': 3.0}))
    view.redraw()
    edit = next(s for s in scripts if 'archforgeSetScene' in s)
    sent = json.loads(edit[edit.index('archforgeSetScene(') + len('archforgeSetScene('):edit.rindex(', ')])
    assert sent['keep'] and {o['id'] for o in sent['objects']} == {other.id}
    assert len(edit) < len(whole) / 2
    view.bridge = None
    from archforge.ui.pbr_viewport import PBRInteractionBridge
    scripts.clear()
    PBRInteractionBridge(view).requestFullScene()          # the page lost step: the whole scene again
    again = next(s for s in scripts if 'archforgeSetScene' in s)
    assert '__archforgePendingScene' in again and '"keep"' not in again


def test_the_real_page_builds_only_the_changed_meshes_and_asks_for_all_when_out_of_step():
    if not click3d.available():
        pytest.skip('χωρίς Node / Playwright / Chromium')
    result = click3d.run_in_page(_doc(), """
    // payload: the whole scene, already set by the tool (objects without keys) — set it again with keys.
    const keyed = payload.objects.map((o, i) => Object.assign({}, o, {key: 'k' + i}));
    window.archforgeSetScene(Object.assign({}, payload, {objects: keyed}), false);
    const meshes = () => window.__meshCount ? window.__meshCount() : null;
    const built0 = window.archforgeSceneBuilt;
    const changed = Object.assign({}, keyed[0], {vertices: keyed[0].vertices.map((v) => [v[0], v[1], v[2] + 0.5])});
    window.archforgeSetScene({objects: [changed], keep: keyed.slice(1).map((o) => o.key), selected: []}, false);
    const builtOne = window.archforgeSceneBuilt - built0;
    window.__calls = [];
    window.archforgeSetScene({objects: [], keep: ['missing#0'], selected: []}, false);
    await new Promise((r) => setTimeout(r, 50));
    return {total: keyed.length, builtOne, asked: window.__calls.map((c) => c[0])};
    """)
    assert result['total'] >= 2
    assert result['builtOne'] == 1, result
    assert result['asked'] == ['requestFullScene'], result


def test_the_picture_keeps_its_size_while_the_camera_moves():
    """Owner 29/10 (Windows): «η εικόνα μικραίνει ανά διαστήματα με το που πατήσω το ποντίκι» — the lighter moving
    frame drew a smaller canvas instead of the same picture at a lower resolution."""
    if not click3d.available():
        pytest.skip('χωρίς Node / Playwright / Chromium')
    result = click3d.run_in_page(_doc(), """
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    const canvas = document.querySelector('canvas');
    const full = canvas.getBoundingClientRect().width;
    window.archforgeFrameLog = [];
    let smallest = full;
    const start = window.archforgeFrames;
    for (let i = 0; i < 200 && window.archforgeFrames - start < 4; i++) {
      canvas.dispatchEvent(new WheelEvent('wheel', {deltaY: i % 2 ? 60 : -60, clientX: 400, clientY: 260, bubbles: true}));
      await wait(60);
      smallest = Math.min(smallest, canvas.getBoundingClientRect().width);
    }
    return {full, smallest, moved: window.archforgeFrameLog.some((m) => m === true), page: window.innerWidth};
    """)
    assert result['moved'], result
    assert result['smallest'] == result['full'] == result['page'], result
