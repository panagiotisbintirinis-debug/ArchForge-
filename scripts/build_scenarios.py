"""Build the test scenarios into docs/scenarios: <key>_*.archforge, a plan image and a report each.

Usage (any OS):  py scripts/build_scenarios.py [01 02 …]
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
OUT = ROOT / "docs" / "scenarios"


def modules():
    import archforge.scenarios as pkg
    for m in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        if m.name[:1] == "s" and m.name[1:3].isdigit():
            yield importlib.import_module(f"archforge.scenarios.{m.name}")


def run(only=()):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from archforge.ui.main_window import MainWindow
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for mod in modules():
        if only and mod.KEY not in only:
            continue
        window = MainWindow()
        window._no_modal_dialogs = True
        try:
            s = mod.build(window)
            mod.checks(s)
            stem = OUT / f"{mod.KEY}_{mod.__name__.split('_', 1)[1]}"
            s.check_save_load(str(stem.with_suffix(".archforge")))
            s.plan_image(str(stem) + "_katopsi.png")
            extra = f"Αρχείο: `{stem.name}.archforge` · κάτοψη: `{stem.name}_katopsi.png`\n\n" + getattr(mod, "NOTES", "")
            failed = s.report(str(stem) + ".md", extra=extra)
            results[mod.KEY] = failed
            print(f"{mod.KEY}: {len(s.steps)} βήματα, {len(s.checks)} έλεγχοι, {len(failed)} προβλήματα")
        finally:
            window._mark_clean(); window.close()
    return results


if __name__ == "__main__":
    run(tuple(sys.argv[1:]))
