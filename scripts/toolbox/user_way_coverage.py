"""Which of the program's commands are checked the user's way (owner rule 29/10: «όλα τα τεστ πρέπει να περνάνε με την
κίνηση και τον τρόπο του χρήστη, και όλα να βλέπουν με τον τρόπο του χρήστη»).

What it does: opens the main window offscreen, lists every command a person can reach — the menu bar (with its
submenus) and the toolbars / ribbon — and looks in the tests and in ``scripts/user_drive`` for a check that reaches
that command the way a person does: by its menu path or its button text (``_menu_action(w, '…')``, ``u.menu(…)``,
``u.toolbar('…')``).  A command that is only called as a function (``window._export_pdf(...)``) does not count.

It is a heuristic (it matches the visible text), and it only reads.  Output: a Markdown table — command, where it is,
checked the user's way yes / no — for the backlog in ``docs/specs/kateythynsi_epilysis.md`` (Π12).

Run:  QT_QPA_PLATFORM=offscreen QTWEBENGINE_DISABLE_SANDBOX=1 QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu" \\
          python scripts/toolbox/user_way_coverage.py [out.md]
"""
from __future__ import annotations

import glob
import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


def _plain(text):
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&").replace("\n", " ").strip()


def commands():
    """``[(path, text)]`` of every visible command: menu paths ('Αρχείο ▸ Εξαγωγή PDF…') and toolbar buttons."""
    from PySide6.QtCore import QCoreApplication, Qt
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    from PySide6.QtWidgets import QApplication, QToolBar, QToolButton
    app = QApplication.instance() or QApplication([])
    from archforge.ui.main_window import MainWindow
    MainWindow._ask_recovery = lambda self, info: "discard"
    w = MainWindow(); w._no_modal_dialogs = True
    out = []

    def walk(menu, path):
        menu.aboutToShow.emit()
        for a in menu.actions():
            if a.isSeparator() or not _plain(a.text()):
                continue
            if a.menu() is not None:
                walk(a.menu(), path + [_plain(a.text())])
            else:
                out.append((" ▸ ".join(path + [_plain(a.text())]), _plain(a.text())))
    for top in w.menuBar().actions():
        if top.menu() is not None:
            walk(top.menu(), [_plain(top.text())])
    for tb in w.findChildren(QToolBar):
        acts = list(tb.actions()) + [b.defaultAction() for b in tb.findChildren(QToolButton) if b.defaultAction()]
        for a in acts:
            if a is not None and _plain(a.text()) and not a.isSeparator():
                out.append((f"Κορδέλα ▸ {_plain(a.text())}", _plain(a.text())))
    w._mark_clean(); w.close(); app.processEvents()
    seen, unique = set(), []
    for path, text in out:
        if path not in seen:
            seen.add(path); unique.append((path, text))
    return unique


def user_way_texts():
    """Texts the user-way checks reach: arguments of _menu_action / u.menu / u.toolbar / u.mm in tests and user_drive."""
    texts = set()
    pat = re.compile(r"(?:_menu_action\(\s*\w+\s*,|\.menu\(|\.toolbar\(|\.mm\([^)]*?,)\s*((?:'[^']*'|\"[^\"]*\")(?:\s*,\s*(?:'[^']*'|\"[^\"]*\"))*)")
    for path in glob.glob(os.path.join(ROOT, "tests", "*.py")) + glob.glob(os.path.join(ROOT, "scripts", "user_drive", "*.py")):
        src = open(path, encoding="utf-8").read()
        for m in pat.finditer(src):
            for s in re.findall(r"'([^']*)'|\"([^\"]*)\"", m.group(1)):
                t = (s[0] or s[1]).strip()
                if t:
                    texts.add(t)
    return texts


def report(out_path=None):
    cmds = commands()
    reached = user_way_texts()
    rows, yes = [], 0
    for path, text in cmds:
        ok = any(text == t or text.startswith(t) for t in reached)
        yes += ok
        rows.append(f"| {path} | {'✔' if ok else '—'} |")
    md = (f"# Έλεγχος με τον τρόπο του χρήστη: κάλυψη εντολών\n\n"
          f"{yes} από {len(cmds)} εντολές (μενού και κορδέλα) έχουν έλεγχο που τις πατά όπως ο χρήστης "
          f"(`scripts/toolbox/user_way_coverage.py`, ευρετικό: ταιριάζει το ορατό κείμενο).\n\n"
          "| Εντολή | Με τον τρόπο του χρήστη |\n|---|---|\n" + "\n".join(rows) + "\n")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(md)
    print(f"{yes} / {len(cmds)} εντολές ελέγχονται με τον τρόπο του χρήστη")
    return yes, len(cmds)


if __name__ == "__main__":
    report(sys.argv[1] if len(sys.argv) > 1 else None)
