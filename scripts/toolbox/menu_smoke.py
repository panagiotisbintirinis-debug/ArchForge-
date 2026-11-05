"""Every command the human can reach, pressed once: which ones break, which do nothing, which cannot be seen.

Opens the application as ``ui/app.py`` does (every startup layer), loads a project (default: the owner's two-storey
house), then presses each leaf command of the main menus and of the visible tool groups, one after the other, with
every dialog answered «Άκυρο» and every file dialog empty — the project is never saved.  A command that raises is
BROKEN; one that changes the project or the status bar is OK (as is one that starts a plan tool); one that only
opened a dialog / message / file picker (answered «Άκυρο») is ASKS, with what it showed; a check item that flipped is
TOGGLE; one that did none of these is QUIET — the ones to look at by hand.
Also lists the plan tools (``_start_site_tool`` / ``_set_active_tool`` ids in the code) that no menu or button reaches.

Run (cloud):  QTWEBENGINE_DISABLE_SANDBOX=1 QT_QPA_PLATFORM=offscreen python scripts/toolbox/menu_smoke.py [--project F]
              [--markdown out.md]
Reads only: never writes the project or the user's settings (layout persistence off).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
SKIP = re.compile(r"Έξοδος|Κλείσιμο|^Νέο|Άνοιγμα|Αποθήκευση|Εκτύπωση|Ενημερώσ|ενημερώσ|Εξαγωγή|Αναφορά σφάλματος|"
                  r"Πλήρης οθόνη|Επανεκκίνηση|Quit|Exit", re.I)


SHOWN = []      # what the last command put in front of the user (dialogs, messages, file pickers), as titles


def _title(args, fallback):
    """The title a dialog call carries: ``(parent, title, …)`` for the static helpers."""
    for x in args[1:2]:
        if isinstance(x, str) and x:
            return x
    return fallback


def _patch_dialogs():
    from PySide6.QtWidgets import (QColorDialog, QDialog, QFileDialog, QInputDialog, QMenu, QMessageBox)

    def shown(kind, result):
        def call(*a, **k):
            SHOWN.append(f"{kind}: {_title(a, '')}".rstrip(": "))
            return result() if callable(result) else result
        return staticmethod(call)

    def dialog_exec(self, *a, **k):
        SHOWN.append(f"παράθυρο: {self.windowTitle() or type(self).__name__}")
        return 0
    QDialog.exec = dialog_exec
    QMenu.exec = lambda self, *a, **k: SHOWN.append(f"μενού: {self.title()}".rstrip(": ")) and None
    for name in ("getOpenFileName", "getSaveFileName", "getOpenFileNames"):
        setattr(QFileDialog, name, shown("αρχείο", ("", "")))
    QFileDialog.getExistingDirectory = shown("φάκελος", "")
    QInputDialog.getText = shown("ερώτηση", ("", False))
    QInputDialog.getItem = shown("ερώτηση", ("", False))
    QInputDialog.getDouble = shown("ερώτηση", (0.0, False))
    QInputDialog.getInt = shown("ερώτηση", (0, False))
    QColorDialog.getColor = shown("χρώμα", lambda: __import__("PySide6.QtGui", fromlist=["QColor"]).QColor())
    for name in ("information", "warning", "critical", "question"):
        setattr(QMessageBox, name, shown("μήνυμα", QMessageBox.StandardButton.Cancel))
    QMessageBox.about = shown("μήνυμα", None)                       # «Σχετικά με» waited for OK forever
    QMessageBox.aboutQt = shown("μήνυμα", None)

    def box_exec(self, *a, **k):
        SHOWN.append(f"μήνυμα: {self.windowTitle() or self.text()[:60]}")
        return int(QMessageBox.StandardButton.Cancel)
    QMessageBox.exec = box_exec


def _leaves(menu, path=()):
    for action in menu.actions():
        if action.isSeparator():
            continue
        text = action.text().replace("&&", "&").replace("&", "")
        if action.menu() is not None:
            yield from _leaves(action.menu(), path + (text,))
        elif text:
            yield path + (text,), action


LOG = os.environ.get("MENU_SMOKE_LOG")


def _log(label, error):
    """Each result as it comes (a later hang loses nothing): one JSON line per command."""
    if LOG:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"label": label, "error": error.strip().splitlines()[-1][:300] if error else ""},
                                ensure_ascii=False) + "\n")


def run(project=None):
    import shutil
    import tempfile
    scratch = tempfile.mkdtemp(prefix="menu_smoke_")
    os.environ["ARCHFORGE_DATA"] = os.path.join(scratch, "data")        # the user's settings / library untouched
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    _patch_dialogs()
    import archforge.ui.app  # noqa: F401  — every startup layer, as the real program
    from archforge.ui.main_window import MainWindow
    w = MainWindow(); w.resize(1500, 950); w.show(); app.processEvents()
    if project:
        copy = os.path.join(scratch, os.path.basename(project))       # a copy: the project itself is never touched
        shutil.copy(project, copy)
        w._open_checked(copy); app.processEvents()
    errors = []
    sys.excepthook = lambda t, e, tb: errors.append("".join(traceback.format_exception(t, e, tb))[-600:])
    rows, seen = [], set()
    sources = [(("Μενού", top.text().replace("&&", "&").replace("&", "")), top.menu())
               for top in w.menuBar().actions() if top.menu() is not None]
    for key, group in getattr(w, "_tool_groups", {}).items():
        for text, button in group.labelled_buttons():
            if button.menu() is not None:
                sources.append((("Ομάδα", group.windowTitle() or key, text), button.menu()))
    for prefix, menu in sources:
        for path, action in _leaves(menu, prefix):
            if id(action) in seen:
                continue
            seen.add(id(action))
            label = " ▸ ".join(path)
            if SKIP.search(path[-1]):
                rows.append((label, "SKIPPED", "")); continue
            if not action.isEnabled():
                rows.append((label, "DISABLED", action.toolTip() if action.toolTip() != path[-1] else "")); continue
            print("…", label, file=sys.stderr, flush=True)       # progress: the last one printed is the one that hangs
            before_err = len(errors)
            status_before = w.statusBar().currentMessage(); undo_before = len(w.stack.done)
            checked_before = action.isChecked(); tool_before = _tool(w); windows_before = _visible_windows(app, w)
            view_before = _view(w, app)
            del SHOWN[:]
            try:
                action.trigger(); app.processEvents(); app.processEvents()   # a panel shown later shows now
            except Exception:                                   # noqa: BLE001 — a command must never raise
                errors.append(traceback.format_exc()[-600:])
            _log(label, errors[-1] if len(errors) > before_err else "")
            new_windows = _visible_windows(app, w) - windows_before
            if len(errors) > before_err:
                rows.append((label, "BROKEN", errors[-1].strip().splitlines()[-1][:200]))
            elif len(w.stack.done) != undo_before or w.statusBar().currentMessage() != status_before:
                rows.append((label, "OK", w.statusBar().currentMessage()[:90]))
            elif SHOWN or new_windows:
                rows.append((label, "ASKS", " · ".join(SHOWN + sorted(new_windows))[:120]))
            elif action.isCheckable() and action.isChecked() != checked_before:
                rows.append((label, "TOGGLE", "ναι" if action.isChecked() else "όχι"))
            elif _tool(w) != tool_before:
                rows.append((label, "OK", f"εργαλείο: {_tool(w)}"))
            elif _view(w, app) != view_before:
                rows.append((label, "OK", "φέρνει μπροστά καρτέλα / πάνελ"))
            else:
                rows.append((label, "QUIET", ""))
            for win in app.topLevelWidgets():                   # close what it opened: the next command starts clean
                if win is not w and win.isVisible() and win.isWindow() and _name(win) in new_windows:
                    win.close()
            app.processEvents()
            # Leave every tool: the next command starts clean.
            try:
                w._set_active_tool("select"); w.plan_view.controller.cancel()
                if w.sculpt_action.isChecked():
                    w.sculpt_action.setChecked(False)
            except Exception:                                   # noqa: BLE001
                pass
    w._mark_clean(); w.close(); app.processEvents()
    return rows, _unreached_tools()


def _tool(w):
    try:
        return str(w.plan_view.controller.tool)
    except AttributeError:
        return ""


def _view(w, app):
    """What is in front: the central tab, the visible panels and their front tab, the widget with the focus."""
    from PySide6.QtWidgets import QDockWidget, QTabWidget
    tabs = getattr(w, "_central_tabs", None)
    front = tuple((t.count(), t.currentIndex()) for t in w.findChildren(QTabWidget) if t.isVisible())
    docks = frozenset(d.windowTitle() for d in w.findChildren(QDockWidget) if d.isVisible())
    focus = app.focusWidget()
    return (tabs.currentIndex() if tabs is not None else None, tabs.count() if tabs is not None else None,
            front, docks, type(w.centralWidget()).__name__, id(focus) if focus is not None else None)


def _name(x):
    return x.windowTitle() or type(x).__name__


def _visible_windows(app, main):
    """Titles of the top-level windows on screen besides the main one (a non-modal panel or dialog it opened)."""
    from PySide6.QtWidgets import QMenu
    return {_name(x) for x in app.topLevelWidgets()
            if x is not main and x.isVisible() and x.isWindow() and not isinstance(x, QMenu)}


def _unreached_tools():
    """Tool ids the code can start (``_start_site_tool('x'`` / ``_set_active_tool('x'``) that no menu / button
    names: read from the source, so a tool only reachable from inside another one is listed too (check by hand)."""
    ui = os.path.join(ROOT, "archforge", "ui")
    used, defined = set(), set()
    pat = re.compile(r"""(?:_start_site_tool|_set_active_tool|set_tool)\(\s*f?["']([a-z_0-9]+)""")
    for name in os.listdir(ui):
        if name.endswith(".py"):
            text = open(os.path.join(ui, name), encoding="utf-8").read()
            used.update(pat.findall(text))
    plan = open(os.path.join(ui, "plan_view.py"), encoding="utf-8").read()
    defined.update(re.findall(r"""['"]([a-z]+_[a-z_]+)['"]""", plan.split("SITE_POINT_TOOLS=", 1)[1].split(")", 1)[0]))
    return sorted(defined - used)


def markdown(rows, unreached):
    count = {}
    for _l, state, _d in rows:
        count[state] = count.get(state, 0) + 1
    out = ["# Έλεγχος εντολών (menu_smoke)", "", " · ".join(f"{k}: {v}" for k, v in sorted(count.items())), ""]
    for state in ("BROKEN", "DISABLED", "QUIET", "ASKS", "TOGGLE"):
        sel = [r for r in rows if r[1] == state]
        if sel:
            out += [f"## {state} ({len(sel)})", "", "| Εντολή | Λεπτομέρεια |", "|---|---|"]
            out += [f"| {l} | {d.replace('|', '/')} |" for l, _s, d in sel] + [""]
    if unreached:
        out += ["## Εργαλεία κάτοψης χωρίς μενού/κουμπί", ""] + [f"- `{t}`" for t in unreached] + [""]
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.path.join(ROOT, "tests", "data", "owner_111_two_storey.archforge"))
    ap.add_argument("--markdown")
    args = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(90, repeat=True)          # a command that hangs shows where, every 90 s
    rows, unreached = run(args.project)
    text = markdown(rows, unreached)
    if args.markdown:
        open(args.markdown, "w", encoding="utf-8").write(text)
    print(text)
