"""Capture human-review screenshots for the residential scenario suite.

This is deliberately a presentation/regression aid, not an engineering validator.
The screenshots let the owner inspect what the software actually shows after the
programmatic stages have passed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtWidgets import QApplication

from archforge.core.commands import CommandStack
from archforge.project.persistence import load_project
from archforge.structure.analysis import analyze_cached
from archforge.ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
MANIFEST = ROOT / "manifest.json"


def _wait(ms=900):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _bind(window, doc):
    stack = CommandStack(doc)
    window.doc = doc
    window.stack = stack
    stack.listeners.append(window._on_document_changed)
    for view in (window.plan_view, window.pbr_view, window.structural_view):
        if hasattr(view, "rebind"):
            view.rebind(doc, stack)
        else:
            view.doc = doc
            view.stack = stack
    window._refresh_project_tree()
    window.refresh_inspector()
    window._redraw_views(all_views=True)
    return stack


def _save(widget, path):
    pix = widget.grab()
    if pix.isNull() or pix.width() < 100 or pix.height() < 100:
        raise RuntimeError(f"invalid screenshot for {path.name}: {pix.width()}x{pix.height()}")
    if not pix.save(str(path), "PNG"):
        raise RuntimeError(f"could not save screenshot: {path}")


def capture_one(app, spec):
    project_path = ROOT / spec["file"]
    report = load_project(project_path)
    if not report.ok:
        raise RuntimeError(report.message())

    doc = report.doc
    window = MainWindow()
    window._no_modal_dialogs = True
    window.resize(1500, 940)
    _bind(window, doc)
    window.show()
    app.processEvents()
    _wait(250)

    # 2D plan: one screenshot of the actual ArchForge plan widget.
    try:
        scene_rect = window.plan_view.scene().itemsBoundingRect()
        if scene_rect.isValid() and scene_rect.width() > 0 and scene_rect.height() > 0:
            window.plan_view.fitInView(
                scene_rect.adjusted(-0.6, -0.6, 0.6, 0.6),
                Qt.AspectRatioMode.KeepAspectRatio,
            )
    except Exception:
        pass
    window.plan_view.redraw()
    app.processEvents()
    _save(window.plan_view, OUT / f"{spec['id']}_01_plan.png")

    # 3D: activate the real PBR viewport, fit and let WebEngine draw before grab.
    window.tabs.setCurrentWidget(window.pbr_view)
    window.pbr_view.activate()
    try:
        window.pbr_view.set_camera_preset("iso30")
    except Exception:
        pass
    app.processEvents()
    _wait(1400)
    app.processEvents()
    _save(window.pbr_view, OUT / f"{spec['id']}_02_3d.png")

    # Structural: same authoritative document, derived structural view.
    analyze_cached(doc)
    window.tabs.setCurrentWidget(window.structural_view)
    window.structural_view.activate()
    try:
        window.structural_view.set_render_technique("technical")
        window.structural_view.set_camera_preset("iso30")
    except Exception:
        pass
    app.processEvents()
    _wait(1200)
    app.processEvents()
    _save(window.structural_view, OUT / f"{spec['id']}_03_structural.png")

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
        "",
        "Software tests passing is not engineering approval. Rules carrying ENGINEER_REVIEW, DESIGN_DEFAULT, UNVERIFIED or similar provenance retain that status.",
    ]
    (OUT / f"{spec['id']}_REPORT.md").write_text("\n".join(text) + "\n", encoding="utf8")
    window.close()
    app.processEvents()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    specs = json.loads(MANIFEST.read_text(encoding="utf8"))
    for spec in specs:
        print(f"capture {spec['id']} {spec['name']}")
        capture_one(app, spec)

    index = ["# Residential scenario handoff", ""]
    for spec in specs:
        index.append(
            f"- **{spec['id']} {spec['name']}** — `{spec['file']}` + plan / 3D / structural screenshots + `{spec['id']}_REPORT.md`"
        )
    index += ["", "Generated after the sequential design -> structure -> MEP -> quote test passes."]
    (OUT / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf8")


if __name__ == "__main__":
    main()
