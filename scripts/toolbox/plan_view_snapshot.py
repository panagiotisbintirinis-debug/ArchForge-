"""Snapshot of how the plan view draws a project: every scene item's pen, brush, z and text, per storey.

What it does: opens each ``.archforge`` file, draws every storey in an offscreen PlanView and writes one sorted line
per scene item (item type, z, opacity, pen colour/width/style, brush, text colour/size/text).  Two snapshots taken
before and after a change to the plan view's drawing code must be identical when the change is a pure refactor.
It only reads the files.

Run:  QT_QPA_PLATFORM=offscreen python scripts/toolbox/plan_view_snapshot.py OUT.json [FILE.archforge …]
      (no files → the owner's file and the residential scenarios)
Compare:  python scripts/toolbox/plan_view_snapshot.py --diff BEFORE.json AFTER.json
"""
from __future__ import annotations

import glob
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

DEFAULT = ["scripts/user_drive/files/owner_123.archforge", *sorted(glob.glob("tests/residential_scenarios/*.archforge"))]


def _rgba(c):
    return "%02x%02x%02x%02x" % (c.red(), c.green(), c.blue(), c.alpha())


def item_line(it):
    from PySide6.QtWidgets import QGraphicsTextItem
    parts = [type(it).__name__, f"z={it.zValue():g}", f"op={it.opacity():.2f}", f"vis={int(it.isVisible())}"]
    if hasattr(it, "pen"):
        p = it.pen()
        parts += [f"pen={_rgba(p.color())}", f"w={p.widthF():.4f}", f"ps={int(p.style().value)}",
                  f"cap={int(p.capStyle().value)}", f"join={int(p.joinStyle().value)}", f"cos={int(p.isCosmetic())}"]
    if hasattr(it, "brush"):
        b = it.brush()
        parts += [f"brush={_rgba(b.color())}", f"bs={int(b.style().value)}"]
    if isinstance(it, QGraphicsTextItem):
        f = it.font()
        parts += [f"tc={_rgba(it.defaultTextColor())}", f"pt={f.pointSizeF():.2f}", f"b={int(f.bold())}",
                  f"text={it.toPlainText()!r}"]
    return " ".join(parts)


def snapshot(paths):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from archforge.core.commands import CommandStack
    from archforge.core.model import WorkPlane
    from archforge.project.persistence import load_project
    from archforge.ui.plan_view import PlanView
    out = {}
    for path in paths:
        doc = load_project(path).doc
        zs = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall"}) or [0.0]
        view = PlanView(doc, CommandStack(doc))
        for z in zs:
            old = doc.work_plane
            doc.work_plane = WorkPlane(name=old.name, origin=(old.origin[0], old.origin[1], z), u=old.u, v=old.v)
            view._show_grid = False
            view.redraw()
            out[f"{os.path.basename(path)}@{z:g}"] = sorted(item_line(it) for it in view._scene.items())
    return out


def diff(a, b):
    from collections import Counter
    bad = 0
    for key in sorted(set(a) | set(b)):
        ca, cb = Counter(a.get(key, [])), Counter(b.get(key, []))
        if ca != cb:
            bad += 1
            print(f"== {key}: {sum((ca - cb).values())} only before, {sum((cb - ca).values())} only after")
            for line in list((ca - cb).elements())[:8]:
                print("  -", line)
            for line in list((cb - ca).elements())[:8]:
                print("  +", line)
    print("identical" if not bad else f"{bad} storeys differ")
    return bad


if __name__ == "__main__":
    if sys.argv[1] == "--diff":
        a, b = (json.load(open(p, encoding="utf-8")) for p in sys.argv[2:4])
        sys.exit(1 if diff(a, b) else 0)
    data = snapshot(sys.argv[2:] or DEFAULT)
    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=0)
    print(len(data), "storeys,", sum(len(v) for v in data.values()), "items")
