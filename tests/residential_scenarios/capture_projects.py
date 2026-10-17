"""Capture human-review screenshots for the residential scenario suite.

This is deliberately a presentation/regression aid, not an engineering validator.
The screenshots let the owner inspect what the software actually shows after the
programmatic stages have passed.
"""
from __future__ import annotations

import json
import os
import time
import base64
import hashlib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

from PySide6.QtCore import QEventLoop, QTimer, Qt, QRectF
from PySide6.QtWidgets import QApplication

from archforge.core.commands import CommandStack
from archforge.project.persistence import load_project
from archforge.structure.analysis import analyze_cached
from archforge.ui.app import MainWindow

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
MANIFEST = ROOT / "manifest.json"


def _wait(ms=900):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _js(view, source, timeout=30000):
    result = []
    loop = QEventLoop()
    def done(value):
        result.append(value)
        loop.quit()
    view.web_view.page().runJavaScript(source, done)
    QTimer.singleShot(timeout, loop.quit)
    loop.exec()
    if not result:
        raise RuntimeError('WebEngine JavaScript callback timed out')
    return result[0]


def _wait_renderer(view, timeout=45):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        ready = _js(view, "typeof window.archforgeCaptureFrame === 'function' && typeof window.archforgeSetScene === 'function' && !!document.querySelector('canvas')")
        if ready:
            _wait(500)
            return
        _wait(250)
    raise RuntimeError('PBR page did not initialise a real renderer; no screenshot accepted')


def _bind(window, doc):
    window._replace_project(doc)
    return window.stack


def _show_view(window, view):
    """Activate both nested tabs: selecting a hidden inner tab is insufficient."""
    if view is window.plan_view:
        window._central_tabs.setCurrentIndex(0)
    else:
        window._central_tabs.setCurrentWidget(window.tabs)
        window.tabs.setCurrentWidget(view)
        view.activate()


def _fit_plan(window):
    # itemsBoundingRect includes the infinite/grid presentation and zooms a
    # ten-metre house out to hundreds of metres. Fit actual active walls.
    z = float(window.doc.work_plane.origin[2])
    walls = [e.params for e in window.doc.entities.values() if e.kind == 'wall'
             and abs(float(e.params.get('z', 0.)) - z) < 1e-4]
    if not walls:
        raise RuntimeError('no active-storey walls for plan capture')
    xs = [float(p[k]) for p in walls for k in ('x1', 'x2')]
    ys = [float(p[k]) for p in walls for k in ('y1', 'y2')]
    from archforge.core.layers import workspace
    if workspace(window.doc) == 'mep':
        from archforge.mep.drainage import route_drainage_cached
        for node in route_drainage_cached(window.doc)['nodes']:
            if abs(float(node['z'])-z) < .05:
                xs.append(float(node['x']));ys.append(float(node['y']))
    rect = QRectF(min(xs)-1.5, min(ys)-2., max(xs)-min(xs)+3., max(ys)-min(ys)+3.5)
    window.plan_view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
    window.plan_view.redraw()


def _save(widget, path):
    pix = widget.grab()
    if pix.isNull() or pix.width() < 100 or pix.height() < 100:
        raise RuntimeError(f"invalid screenshot for {path.name}: {pix.width()}x{pix.height()}")
    if getattr(widget, 'web_view', None) is not None:
        # A queued native grab can contain the previous camera/viewport size.
        # Execute capture after the queued camera commands in the actual page.
        data = _js(widget, f"window.archforgeCaptureFrame({pix.width()}, {pix.height()})")
        if not isinstance(data,str) or not data.startswith('data:image/png;base64,'):
            raise RuntimeError(f'no real WebGL frame for {path.name}')
        from PySide6.QtGui import QImage
        raw=base64.b64decode(data.split(',',1)[1]); frame=QImage.fromData(raw)
        if frame.isNull() or frame.width()<100 or frame.height()<100:
            raise RuntimeError(f'invalid WebGL frame size for {path.name}')
        path.write_bytes(raw)
        print(f'{path.name}: actual WebGL viewport frame {frame.width()}x{frame.height()}',flush=True)
        return 'Actual WebGL viewport frame'
    qimage = pix.toImage()
    colors = {qimage.pixel(x, y) for x in range(0,qimage.width(),max(1,qimage.width()//40))
              for y in range(0,qimage.height(),max(1,qimage.height()//30))}
    if len(colors) < 8:
        raise RuntimeError(f'blank screenshot rejected: {path.name}')
    if not pix.save(str(path), "PNG"):
        raise RuntimeError(f"could not save screenshot: {path}")
    return 'Native Qt widget'


def capture_one(app, spec):
    project_path = ROOT / spec["file"]
    report = load_project(project_path)
    if not report.ok:
        raise RuntimeError(report.message())

    doc = report.doc
    ui = {'_project_sha256': hashlib.sha256(project_path.read_bytes()).hexdigest()}
    OUT.mkdir(parents=True, exist_ok=True)
    ui_path = OUT / f"{spec['id']}_UI_CHECKS.json"
    def result(name, status, detail):
        ui[name] = {'status': status, 'detail': detail}
        ui_path.write_text(json.dumps(ui,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for old in OUT.glob(f"{spec['id']}_*.png"):
        old.unlink()
    window = MainWindow()
    window._no_modal_dialogs = True
    window.resize(1500, 940)
    _bind(window, doc)
    window.show()
    app.processEvents()
    _wait(250)

    # 2D plan: one screenshot of the actual ArchForge plan widget.
    _show_view(window, window.plan_view)
    _fit_plan(window)
    app.processEvents()
    _save(window.plan_view, OUT / f"{spec['id']}_01_plan.png")
    result('Plan: Ground','PASS',f"{spec['id']}_01_plan.png — real Qt plan widget")
    before = set(window.doc.entities)
    window._activate_level_by_name('Level 1')
    _fit_plan(window); _wait(150)
    _save(window.plan_view, OUT/f"{spec['id']}_01b_upper_plan.png")
    result('Plan: Level 1','PASS',f"{spec['id']}_01b_upper_plan.png")
    result('UI level switch','PASS' if float(window.doc.work_plane.origin[2]) == 3. and set(window.doc.entities)==before else 'FAIL',
           'Floor selector changed work plane; no entity was removed')
    window._activate_level_by_name('Ground'); _fit_plan(window)
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QPointF
    window.plan_view.set_tool('select')
    sofa=next(e for e in window.doc.entities.values() if e.kind=='library_object' and e.params['z']==0.)
    point=window.plan_view.mapFromScene(QPointF(sofa.params['x'],sofa.params['y']))
    QTest.mouseDClick(window.plan_view.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
    app.processEvents()
    result('UI select','PASS' if sofa.id in window.doc.selection else 'FAIL','Actual double click in the plan on the sofa')
    window.doc.select([]);window.plan_view.redraw()

    from archforge.core.layers import set_workspace, set_layer_state
    set_workspace(window.doc,'mep')
    for layer, name, suffix in [('plumbing','Plumbing plan','04_plumbing'),('drainage','Drainage plan','05_drainage'),('electrical','Electrical plan','06_electrical')]:
        for other in ('plumbing','drainage','electrical','ventilation'):
            set_layer_state(window.doc,other,visible=other==layer)
        _fit_plan(window);_wait(150)
        _save(window.plan_view,OUT/f"{spec['id']}_{suffix}.png")
        result(name,'PASS',f"{spec['id']}_{suffix}.png — actual layer visibility controls")
    set_workspace(window.doc,'arch')

    # 3D: activate the real PBR viewport, fit and let WebEngine draw before grab.
    _show_view(window, window.pbr_view)
    _wait_renderer(window.pbr_view)
    try:
        window.pbr_view.set_camera_preset("iso30")
    except Exception:
        pass
    app.processEvents()
    _wait(1400)
    app.processEvents()
    method=_save(window.pbr_view, OUT / f"{spec['id']}_02_3d.png")
    result('PBR 3D','PASS',f"{spec['id']}_02_3d.png — {method}")
    window.pbr_view.set_camera_preset('dollhouse');_wait(500)
    _save(window.pbr_view,OUT/f"{spec['id']}_02b_dollhouse.png")

    # Structural: same authoritative document, derived structural view.
    analyze_cached(doc)
    _show_view(window, window.structural_view)
    _wait_renderer(window.structural_view)
    try:
        window.structural_view.set_render_technique("technical")
        window.structural_view.set_camera_preset("iso30")
    except Exception:
        pass
    app.processEvents()
    _wait(1200)
    app.processEvents()
    method=_save(window.structural_view, OUT / f"{spec['id']}_03_structural.png")
    result('Structural','PASS',f"{spec['id']}_03_structural.png — {method}")

    text = [
        f"# {spec['id']} — {spec['name']}",
        "",
        f"Project: `{spec['file']}`",
        f"Storeys: {spec['storeys']}",
        f"Roof: {spec['roof_form']} / {spec['tile']}",
        f"Plumbing system: {spec['pipe_system']}",
        f"Split-level: {spec['split_level']}",
        f"Balconies: {spec['balconies']}",
        "",
        "## Human review images",
        f"- `{spec['id']}_01_plan.png`",
        f"- `{spec['id']}_02_3d.png`",
        f"- `{spec['id']}_03_structural.png`",
        f"- `{spec['id']}_01b_upper_plan.png`",
        f"- `{spec['id']}_02b_dollhouse.png`",
        f"- `{spec['id']}_04_plumbing.png`",
        f"- `{spec['id']}_05_drainage.png`",
        f"- `{spec['id']}_06_electrical.png`",
        "",
        "Software tests passing is not engineering approval. Rules carrying ENGINEER_REVIEW, DESIGN_DEFAULT, UNVERIFIED or similar provenance retain that status.",
    ]
    # The full audit owns REPORT.md. A successful capture alone never writes
    # a pass report or replaces the list of unresolved checks.
    (OUT / f"{spec['id']}_CAPTURES.md").write_text("\n".join(text) + "\n", encoding="utf8")
    import tempfile
    from archforge.project.persistence import save_project
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory() as folder:
        saved=Path(folder)/'ui-reopen.archforge'
        expected=window.doc.to_dict(); save_project(window.doc,saved)
        window._mark_clean(); window.close();app.processEvents()
        reopened=MainWindow();reopened._no_modal_dialogs=True
        ok=reopened.open(str(saved))
        result('UI close/reopen','PASS' if ok and reopened.doc.to_dict()==expected else 'FAIL',
               'Saved project; closed real window; fresh MainWindow opened file via checked-open path')
        reopened._mark_clean();reopened.close();app.processEvents()
    window.close()
    app.processEvents()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', default='S01')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if QApplication.instance() is None:
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication([])
    specs = [s for s in json.loads(MANIFEST.read_text(encoding="utf8")) if s['id'] == args.scenario]
    for spec in specs:
        print(f"capture {spec['id']} {spec['name']}")
        capture_one(app, spec)

    index = ["# Residential scenario handoff", ""]
    for spec in specs:
        index.append(
            f"- **{spec['id']} {spec['name']}** — `{spec['file']}` + plan / 3D / structural screenshots + `{spec['id']}_REPORT.md`"
        )
    index += ["", "Diagnostic captures only. Read each full gate report; screenshot existence does not approve a scenario."]
    (OUT / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf8")


if __name__ == "__main__":
    main()
