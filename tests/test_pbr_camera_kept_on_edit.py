"""An edit in the 3D (move, rotate, library drop, open joinery) keeps the camera.

Owner (2026-10-14): «η κάμερα με πέταγε έξω κάθε φορά που άλλαζα ένα
υψόμετρο ... πρέπει να σταματήσει».  ``redraw(force_full=True)`` fits the
camera to the whole model, so only the first load and a new project use it;
the Fit command calls ``fit_camera()`` explicitly.
"""
import ast
from pathlib import Path


def _fitting_redraws(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    found = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "redraw"
                    and any(k.arg == "force_full" and isinstance(k.value, ast.Constant) and k.value.value is True
                            for k in node.keywords)):
                found.append(fn.name)
    return found


def test_only_first_load_and_new_project_fit_the_pbr_camera():
    assert sorted(set(_fitting_redraws("archforge/ui/pbr_viewport.py"))) == ["_on_load_finished", "rebind"]


def test_open_joinery_toggle_keeps_the_camera():
    assert _fitting_redraws("archforge/ui/object_menu.py") == []
