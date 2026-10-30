"""The 8 main menus of the approved mockup (owner 14/10, `docs/mockups/menou_2026-10-14.png`):

Αρχείο · Επεξεργασία · CAD · Κατασκευή · Βιβλιοθήκη · Προβολή · Εργαλεία · Βοήθεια

The commands are created by many installers into the older 15 menus (Έδαφος, Δομικά, Μηχανολογικά, Κουζίνα,
Απεικόνιση …).  This runs once, last, and only *moves* what exists: the old menus become submenus (same
QMenu objects, so every ``window._…_menu`` reference keeps working), and anything not recognised stays, at
the end of its menu — no command is ever lost.  Owner decisions: Έδαφος / Δομικά / Η/Μ as submenus of
«Κατασκευή»; the 2D drawing menu is called «CAD»; Τομή and Εσωτερική όψη belong to «Προβολή».
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

MAIN_MENUS = ("Αρχείο", "Επεξεργασία", "CAD", "Κατασκευή", "Βιβλιοθήκη", "Προβολή", "Εργαλεία", "Βοήθεια")

# The «… στο 3D» switches: one place, Προβολή ▸ Εμφάνιση στο 3D (they were repeated in 4 menus).
LAYER_TEXTS = ("Ξυλεία στέγης στο 3D", "Στρώσεις στέγης στο 3D (ταμπλάς, μόνωση, μεμβράνες)", "Κεραμίδια στο 3D",
               "Θεμελίωση στο 3D", "Ηλεκτρολογικά στο 3D",
               "Αποχετεύσεις στο 3D", "Εξαερισμοί στο 3D", "Μηχανολογικά στο 3D", "Ανοιχτά κουφώματα στο 3D")


def _plain(text):
    return text.replace("&&", "&")


def _find(menu, text, startswith=False):
    """The action of ``menu`` with this text (submenus by their title), or None."""
    if menu is None:
        return None
    for a in menu.actions():
        t = _plain(a.text())
        if t == text or (startswith and t.startswith(text)):
            return a
    return None


def _remove(menu, *texts):
    for text in texts:
        a = _find(menu, text)
        while a is not None:
            menu.removeAction(a)
            a = _find(menu, text)


def _tidy(menu):
    """No separator first, last or twice in a row (left behind by the moves)."""
    previous_sep = True
    for a in list(menu.actions()):
        if a.isSeparator():
            if previous_sep:
                menu.removeAction(a)
            previous_sep = True
        else:
            previous_sep = False
    while menu.actions() and menu.actions()[-1].isSeparator():
        menu.removeAction(menu.actions()[-1])


def _fill(menu, items):
    """Rebuild ``menu`` from ``items`` (actions, menus, None = separator); what was there and is not listed
    stays at the end."""
    listed = set()
    for i in items:
        if isinstance(i, QMenu):
            listed.add(i.menuAction())
        elif i is not None:
            listed.add(i)
    leftovers = [a for a in menu.actions() if not a.isSeparator() and a not in listed]
    for a in list(menu.actions()):
        menu.removeAction(a)
    for i in items:
        if i is None:
            menu.addSeparator()
        elif isinstance(i, QMenu):
            if i.actions():
                menu.addMenu(i)
        else:
            menu.addAction(i)
    if leftovers:
        menu.addSeparator()
        for a in leftovers:
            menu.addAction(a)
    _tidy(menu)


def _submenu(window, title, items):
    sub = QMenu(title, window)
    _fill(sub, items)
    window._main_submenus.append(sub)
    return sub


def _action(window, text, run, tip=""):
    a = QAction(text, window)
    a.triggered.connect(lambda _=False: run())
    if tip:
        a.setToolTip(tip)
    window._main_actions.append(a)
    return a


def organize_main_menus(window):
    """Regroup the menu bar into the 8 menus of the mockup (moves, never drops)."""
    bar = window.menuBar()
    window._main_submenus, window._main_actions = [], []
    old = {_plain(a.text()): a.menu() for a in bar.actions() if a.menu() is not None}
    get = old.get
    file_menu, edit_menu, view_menu = get("Αρχείο"), get("Επεξεργασία"), get("Προβολή")
    build, library = get("Κατασκευή"), get("Βιβλιοθήκη")
    terrain, structure, mep = get("Έδαφος"), get("Δομικά"), get("Μηχανολογικά")
    kitchen, materials, render = get("Κουζίνα"), get("Υλικά"), get("Απεικόνιση")
    sculpt_menu, ai_menu, help_menu = get("Γλυπτική"), get("Βοηθός AI"), get("Βοήθεια")
    cad = get("Σχεδίαση") or QMenu("CAD", window)
    cad.setTitle("CAD")

    # The «στο 3D» switches out of the thematic menus (they stay in Προβολή).
    for menu in (build, structure, mep, getattr(window, "_roof_menu", None)):
        if menu is not None:
            _remove(menu, *LAYER_TEXTS)
            _tidy(menu)

    # --- Αρχείο: Εισαγωγή ▸ / Εξαγωγή ▸ ---
    if file_menu is not None:
        imports = [_find(terrain, "Εισαγωγή τοπογραφικού", True), _find(library, "Εισαγωγή μοντέλου glTF", True),
                   _find(library, "Εισαγωγή αντικειμένων", True)]
        imports = [a for a in imports if a is not None]
        for a in imports[1:]:
            library.removeAction(a)              # the topographic import also stays in Έδαφος (its own workflow)
        if hasattr(window, "_import_underlay"):
            from PySide6.QtGui import QAction
            underlay = QAction("Σχέδιο μηχανικού (PDF / DXF) ως υπόβαθρο…", window)
            underlay.triggered.connect(lambda _=False: window._import_underlay())
            imports.insert(0, underlay)
            window._import_underlay_action = underlay
            drawing_set = QAction("Σύνολο σχεδίων (πολλά PDF: κατόψεις, τομή, γενική διάταξη)…", window)
            drawing_set.setToolTip("Τα σχέδια συσχετίζονται μόνα τους (υψόμετρα, σημάδια τομής, τοίχοι) και γίνονται "
                                   "όροφοι, τοίχοι, κουφώματα, χώροι και έδαφος — μία αναίρεση")
            drawing_set.triggered.connect(lambda _=False: __import__("archforge.ui.drawing_set_import",
                                                                     fromlist=["import_set"]).import_set(window))
            imports.insert(1, drawing_set)
            window._import_drawing_set_action = drawing_set
        camera_menu = _find(view_menu, "Κάμερες")
        image = _find(camera_menu.menu(), "Εξαγωγή εικόνας", True) if camera_menu is not None else None
        from archforge.ui.exchange_export import actions as exchange_actions, import_action as ifc_import_action
        imports.append(ifc_import_action(window))
        exports = [getattr(window, "_pdf_action", None), *exchange_actions(window),
                   getattr(window, "export_stl_action", None), image]
        exports = [a for a in exports if a is not None]
        if getattr(window, "export_stl_action", None) is not None:
            window.export_stl_action.setText("STL (για εκτύπωση)…")
        if image is not None:
            image.setText("Εικόνα 3D…")
        window._file_import_menu = _submenu(window, "Εισαγωγή", imports)
        window._file_export_menu = _submenu(window, "Εξαγωγή", exports)
        prices = getattr(window, "_prices_action", None)
        for a in [prices, getattr(window, "_trades_action", None), getattr(window, "_insulation_action", None),
                  *exports, *imports]:     # prices live in Κατασκευή ▸ Επιμετρήσεις & τιμές
            if a is not None and a in file_menu.actions():
                file_menu.removeAction(a)
        _fill(file_menu, [window.new_action, window.open_action, getattr(window, "open_sample_action", None),
                          window.save_action,
                          getattr(window, "save_as_action", None) or None, None,
                          getattr(window, "_brief_action", None), None,
                          window._file_import_menu, window._file_export_menu, None,
                          getattr(window, "recover_action", None), getattr(window, "autosave_action", None), None,
                          getattr(window, "check_updates_action", None)])

    # --- Επεξεργασία: the editing commands that had only a key or a mouse-menu entry ---
    if edit_menu is not None:
        acts = getattr(getattr(window, "shortcuts", None), "actions", {}) or {}
        tail = [a for a in edit_menu.actions() if not a.isSeparator() and a not in
                (window.undo_action, window.redo_action, window.delete_action)]
        _fill(edit_menu, [window.undo_action, window.redo_action, None,
                          acts.get("edit.move"), acts.get("edit.rotate"), acts.get("edit.stretch"),
                          acts.get("edit.corner"),
                          acts.get("edit.duplicate"), None, window.delete_action, None, *tail])

    # --- CAD: drawing aids and dimensions (tape + automatic, ui/dimension_tool.py); lines and markup come next ---
    grid = getattr(window, "_mockup_grid_check", None)
    snap = getattr(window, "snap_action", None)
    aids = []
    if grid is not None:
        grid_action = QAction("Κάνναβος", window); grid_action.setCheckable(True); grid_action.setChecked(grid.isChecked())
        grid_action.toggled.connect(grid.setChecked); grid.toggled.connect(grid_action.setChecked)
        window._main_actions.append(grid_action); aids.append(grid_action)
    if snap is not None:
        snap.setText("Έλξη (γωνίες, άκρα, κάνναβος)")
        aids.append(snap)
    from archforge.ui.dimension_tool import menu as dimension_menu
    # Audit F08: no visible «— έρχονται» entry; lines and markup appear here when they work (RELEASE_PLAN rule 2.7).
    dims = dimension_menu(window); window._main_submenus.append(dims)
    _fill(cad, [_submenu(window, "Βοηθήματα σχεδίασης", aids), None, dims])
    window._cad_menu = cad

    if mep is not None:                                  # mechanisms: parts, hinges, slides (kinematics/)
        from archforge.ui.mechanical_tool import menu as mechanism_menu
        mep.addSeparator(); mep.addMenu(mechanism_menu(window))

    # --- Κατασκευή: Δομικά ▸, Η/Μ ▸, Έδαφος ▸ as submenus ---
    if build is not None:
        frame = getattr(window, "_mockup_structural_submenu", None)
        if frame is not None and frame.menuAction() in build.actions():
            build.removeAction(frame.menuAction())       # it is the first entry of Δομικά ▸
        _remove(build, "Έδαφος (οικόπεδο)")              # = Έδαφος & περιβάλλον ▸ Δημιουργία εδάφους
        before = _find(build, "Ανακαίνιση (φάσεις)")
        sep = build.insertSeparator(before) if before is not None else build.addSeparator()
        for menu, title in ((structure, "Δομικά"), (mep, "Η/Μ εγκαταστάσεις"), (terrain, "Έδαφος && περιβάλλον")):
            if menu is None:
                continue
            menu.setTitle(title)
            if before is not None:
                build.insertMenu(sep, menu)
            else:
                build.addMenu(menu)
        from archforge.ui.build_menu import _icon
        for menu, kind in ((structure, "frame"), (mep, "joinery"), (terrain, "site")):
            if menu is not None and menu.icon().isNull():
                menu.setIcon(_icon(kind))
        _tidy(build)

    # --- Βιβλιοθήκη: + Κουζίνα & μπάνιο ▸, Υλικά ▸ ---
    if library is not None:
        if kitchen is not None:
            kitchen.setTitle("Κουζίνα && μπάνιο")
            # Owner 15/10: the kitchen is drawn freely (no Γ / Π proposals of the Βοηθός).
            for a in list(kitchen.actions()):
                t = a.text().replace("&&", "&")
                if t.startswith("Κουζίνα εδώ"):
                    kitchen.removeAction(a)
                elif t.startswith("Γραμμή ντουλαπιών σε τοίχο"):
                    a.setText("Σχεδίασε κουζίνα (ελεύθερα)…")
                    kitchen.removeAction(a); kitchen.insertAction(kitchen.actions()[0] if kitchen.actions() else None, a)
            _tidy(kitchen)
            library.addSeparator(); library.addMenu(kitchen)
        mats = materials if materials is not None else QMenu("Υλικά", window)
        if not mats.actions() and hasattr(window, "_open_selected_materials"):
            mats.addAction(_action(window, "Υλικό στο επιλεγμένο…", window._open_selected_materials))
        mats.setTitle("Υλικά")
        library.addMenu(mats)
        window._library_materials_menu = mats
        _tidy(library)

    # --- Προβολή: όψεις, τομή, κάμερες, απεικόνιση, εμφάνιση στο 3D, πάνελ ---
    if view_menu is not None:
        views = _find(view_menu, "3D Προβολές")
        section = interior = None
        if views is not None:
            vm = views.menu(); vm.setTitle("Όψεις")
            section, interior = _find(vm, "Τομή"), _find(vm, "Εσωτερική Όψη")
            for a in (section, interior):
                if a is not None:
                    vm.removeAction(a)
            if section is not None:
                section.setText("Τομή (σύρε γραμμή στην κάτοψη)")
            if interior is not None:
                interior.setText("Εσωτερική όψη (σύρε γραμμή στην κάτοψη)")
        layers = [a for a in (_find(view_menu, t) for t in LAYER_TEXTS) if a is not None]
        show3d = _submenu(window, "Εμφάνιση στο 3D", layers)
        window._view_show3d_menu = show3d
        if render is not None:
            render.setTitle("Απεικόνιση")
        panels = _find(view_menu, "Παράθυρα")
        if panels is not None:
            panels.menu().setTitle("Πάνελ")
        bars = getattr(window, "_toolbars_menu", None)
        reset = getattr(window, "_reset_layout_action", None)

        def m(a):
            return a.menu() if a is not None and a.menu() is not None else a
        _fill(view_menu, [m(views), section, interior, getattr(window, "_simultaneous_action", None), None,
                          m(_find(view_menu, "Κάμερες")), render, show3d, None,
                          m(_find(view_menu, "Περιβάλλον")), _find(view_menu, "Layers"), None,
                          m(panels), bars, getattr(window, "status_bar_action", None), reset])
        _remove(view_menu, *LAYER_TEXTS)          # only inside «Εμφάνιση στο 3D» now
        _tidy(view_menu)

    # --- Εργαλεία: Γλυπτική, υλικό, Βοηθός ---
    tools = QMenu("Εργαλεία", window)
    tool_items = []
    if getattr(window, "sculpt_action", None) is not None:
        window.sculpt_action.setText("Γλυπτική (ενεργή / ανενεργή)")
        tool_items.append(window.sculpt_action)
    if hasattr(window, "_open_selected_materials"):
        tool_items.append(_action(window, "Υλικό στο επιλεγμένο…", window._open_selected_materials))
    tool_items.append(None)
    assistant = getattr(window, "_assistant_dock", None)
    if assistant is not None:
        def show_assistant():
            assistant.show(); assistant.raise_()
        tool_items.append(_action(window, "Βοηθός (πάνελ)", show_assistant))
    for menu in (sculpt_menu, ai_menu):           # whatever was added there over time
        if menu is not None:
            tool_items.extend([None, *[a for a in menu.actions() if not a.isSeparator()]])
    _fill(tools, tool_items)
    window._main_submenus.append(tools)
    window._tools_menu = tools

    # --- Βοήθεια ---
    if help_menu is not None:
        def about():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.about(window, "Σχετικά με το ArchForge",
                              "ArchForge — αρχιτεκτονικός σχεδιασμός, 2D και 3D από το ίδιο μοντέλο.\n"
                              "Έκδοση ανάπτυξης.")
        help_menu.addSeparator()
        help_menu.addAction(_action(window, "Σχετικά με το ArchForge", about))
        _tidy(help_menu)

    # --- The bar: exactly the 8, in order ---
    final = {"Αρχείο": file_menu, "Επεξεργασία": edit_menu, "CAD": cad, "Κατασκευή": build,
             "Βιβλιοθήκη": library, "Προβολή": view_menu, "Εργαλεία": tools, "Βοήθεια": help_menu}
    for a in list(bar.actions()):
        bar.removeAction(a)                       # not clear(): that deletes the menus we keep
    for name in MAIN_MENUS:
        menu = final.get(name)
        if menu is None:
            menu = QMenu(name, window)
        menu.setTitle(name)
        bar.addMenu(menu)
    window._main_menus = {name: final[name] for name in MAIN_MENUS if final.get(name) is not None}
    # Installers look menus up by their old names; keep those names pointing at the same QMenu objects.
    legacy = dict(getattr(window, "_mockup_menus", {}) or {})
    legacy.update(window._main_menus)
    legacy["Σχεδίαση"] = cad
    window._mockup_menus = legacy
    return window._main_menus


# ------------------------------------------------------------------ the work menus (owner 30/10: «ναι στο 4»)
WORK_MENUS = ("Έργο", "Επεξεργασία", "Κατασκευή", "Εγκαταστάσεις", "Διαμόρφωση", "Σχέδια", "Προβολή", "⚙ Ρυθμίσεις")
BAR = ("__first_row__", "")      # home of the commands always at hand (Κάνναβος · Έλξη · Βοηθός)
# Old menus without a namesake: where a reference to them (a group's title button …) points now — (menu, section).
SUCCESSORS = {"Αρχείο": ("Έργο", ""), "CAD": ("Σχέδια", ""), "Βιβλιοθήκη": ("Διαμόρφωση", "Βιβλιοθήκη"),
              "Εργαλεία": ("Διαμόρφωση", ""), "Βοήθεια": ("⚙ Ρυθμίσεις", "")}
SEP_TEXT = " / "


OLD_PATH = "archforge_old_menu_path"


def old_menu_path(action):
    """The path a command had before the work menus (``" / "``-joined, as ``menu_map.RULES``), or None."""
    value = action.property(OLD_PATH)
    return str(value) if value else None


def _key(text):
    """A menu text as the map writes it (``menu_smoke._leaves``: no mnemonic «&»)."""
    return text.replace("&&", "&").replace("&", "")


def _target(home):
    """``(menu, section)`` of a home of ``menu_map.RULES`` in the bar (section "" = directly in the menu).

    Only the first section level becomes a submenu (as in mockup v4); the object menu and the always-visible bar
    do not exist yet in this look, so their commands stay in Επεξεργασία until the new look (step 3)."""
    if home.startswith(("Αντικείμενο", "Γραμμή εργασίας")):
        return "Επεξεργασία", ""
    if home.startswith("Προβολή ▾"):
        rest = home[len("Προβολή ▾"):].lstrip(" /")
        return "Προβολή", "" if rest.startswith("(") else rest.split(SEP_TEXT)[0]
    top, _, section = home.partition(SEP_TEXT)
    return top, section.split(SEP_TEXT)[0]


def _dynamic(menu):
    """A menu filled when it opens (Κάμερες, κουζίνα …) moves whole: its actions are made again each time."""
    from PySide6.QtCore import SIGNAL
    try:
        return menu.receivers(SIGNAL("aboutToShow()")) > 0
    except (TypeError, RuntimeError):
        return False


def _leaf_paths(menu, path):
    out = []
    for a in menu.actions():
        if a.isSeparator() or not a.text():
            continue
        p = path + (_key(a.text()),)
        if a.menu() is not None:
            out += _leaf_paths(a.menu(), p)
        else:
            out.append((p, a))
    return out


def organize_work_menus(window):
    """Give every command of the bar its home in the work menus (``menu_map.RULES``), last of all installers.

    The work menus and their sections are new QMenus holding the *same* QAction objects (shortcuts, check state,
    triggers unchanged); no old menu is renamed, emptied or given foreign commands, because the tool-group buttons
    and the hidden ribbon share them.  Inside a section:

    * a submenu whose commands all go there and make at least half of it is the section's own category («Υδραυλικά
      σημεία» → Ύδρευση): its commands are listed directly in the section, and a command added to it later appears
      there too (``_Mirror``);
    * a smaller one stays whole behind ▸ with its own name («Περιβάλλων χώρος ▸ Πέργκολα», «Στέγη ▸ Με
      κεραμίδια»), as do menus filled when they open (the same object keeps refilling itself; one already named as
      its section is the section).

    A command found twice gets one home (the first).  The old menus left the bar; references to them in
    ``window._…`` attributes and in tool-group title buttons now mean the work menu that replaced them
    (``SUCCESSORS`` for those without a namesake).  ``window._menu_aliases`` maps each old path
    (``toolbar_custom.SEP``-joined) to the new one, so buttons and mouse menus saved with old paths still find their
    command."""
    from archforge.ui.menu_map import UNPLACED, home
    from archforge.ui.toolbar_custom import SEP
    bar = window.menuBar()
    tops = [(a.text(), a.menu()) for a in bar.actions() if a.menu() is not None]
    # Keyed by id(): ``keep`` holds every wrapper for the whole run, so an id cannot be freed and reused meanwhile.
    menus, sections, placed, old_paths, old_cpaths, old_menus, keep, dynamic = {}, {}, set(), {}, {}, {}, [], []
    old_tops = {_key(t): m for t, m in tops}
    window._work_mirrors = []
    quick_row = getattr(window, "_top_row", None) is not None
    window._quick_actions, window._quick_paths = [], {}

    def top_menu(name):
        if name not in menus:
            menus[name] = QMenu(name, window)
            old = old_tops.get(name)
            if old is not None:                                # same name: same tear-off (📌), icon
                menus[name].setTearOffEnabled(old.isTearOffEnabled())
                menus[name].setIcon(old.icon())
        return menus[name]

    def section_menu(top, section, use=None):
        if not section:
            return top_menu(top)
        key = (top, section)
        if key not in sections:
            if use is not None:
                sections[key] = use
                top_menu(top).addMenu(use)
            else:
                parent = top_menu(top)
                sections[key] = QMenu(section.replace("&", "&&"), parent)   # explicit parent: the wrapper stays valid
                parent.addMenu(sections[key])
        return sections[key]

    def where(path):
        h = home(SEP_TEXT.join(path))
        if h.startswith("Γραμμή εργασίας (") and "πάντα ορατό" not in h and quick_row:
            return BAR                                         # always at hand in the first row
        return None if h == UNPLACED else _target(h)

    size, counted = {}, []                                     # commands per section, each command once
    for text, menu in tops:
        for lp, la in _leaf_paths(menu, (_key(text),)):
            if not any(la is c for c in counted):
                counted.append(la)
                size[where(lp)] = size.get(where(lp), 0) + 1

    def mirror(source, target, fallback_path):
        window._work_mirrors.append(_Mirror(source, target, fallback_path))

    def move(menu, path, cpath):
        for a in list(menu.actions()):
            if a.isSeparator() or not a.text():
                continue
            p = path + (_key(a.text()),)
            cp = cpath + (a.text().replace("&&", "&"),)
            sub = a.menu()
            keep.append(a)
            if sub is None:
                if id(a) in placed:
                    continue                                   # one home per command
                t = where(p) or (_key(path[0]), "")
                if t == BAR:
                    from archforge.ui.layout2 import add_quick_action
                    add_quick_action(window, a)
                    window._quick_actions.append(a)
                    window._quick_paths[SEP.join(cp)] = a          # saved buttons / mouse menus still find it
                else:
                    section_menu(*t).addAction(a)
                placed.add(id(a)); old_paths[id(a)] = p; old_cpaths[id(a)] = cp
                continue
            leaves = _leaf_paths(sub, p)
            keep.append(sub); keep.extend(la for _lp, la in leaves)
            homes = {where(lp) for lp, _ in leaves}
            old_menus[id(sub)] = cp
            if _dynamic(sub) or not leaves:
                dynamic.append(sub)
                t = where(p + ("",)) or where(p) or (_key(path[0]), "")
                same = t[1] and _key(sub.title()).split(" (")[0] == t[1].split(" (")[0]
                if same and t not in sections:
                    section_menu(*t, use=sub)                  # it already is the section
                else:
                    section_menu(*t).addMenu(sub)
                for x in sub.actions():
                    placed.add(id(x)); keep.append(x)
                continue
            if len(homes) != 1 or None in homes or BAR in homes:
                move(sub, p, cp)                               # split between homes (or to the first row)
                counts = {h: sum(1 for lp, _la in leaves if where(lp) == h) for h in homes if h and h[1]}
                if counts and not sub.icon().isNull():
                    most = section_menu(*max(counts, key=counts.get))
                    if most.icon().isNull():
                        most.setIcon(sub.icon())               # the section that took most of it shows its icon
                continue
            t = homes.pop()
            if any(id(la) in placed for _lp, la in leaves) or not t[1] or 2 * len(leaves) < size.get(t, 0):
                if any(id(la) in placed for _lp, la in leaves):
                    move(sub, p, cp)                           # holds a command that already has its home
                    continue
                section_menu(*t).addMenu(sub)                  # whole, behind ▸, with its own name
                if section_menu(*t).icon().isNull() and t[1]:
                    section_menu(*t).setIcon(sub.icon())
            else:
                target = section_menu(*t)                      # the section's own category: listed directly
                if target.actions():
                    target.addSeparator()
                for x in sub.actions():
                    target.addAction(x)
                if target.icon().isNull():
                    target.setIcon(sub.icon())
                mirror(sub, target, p)
            for lp, la in leaves:
                placed.add(id(la)); old_paths.setdefault(id(la), lp)
            for cp2, la in _leaf_paths_sep(sub, cp):
                old_cpaths.setdefault(id(la), cp2)

    for text, menu in tops:
        move(menu, (_key(text),), (text.replace("&&", "&"),))
    for a in list(bar.actions()):
        bar.removeAction(a)                                    # not clear(): that would delete the old menus
    order = list(WORK_MENUS) + [n for n in menus if n not in WORK_MENUS]
    for name in order:
        if name in menus and menus[name].actions():
            for sec in menus[name].actions():
                if sec.menu() is not None and sec.menu() in sections.values():
                    _tidy(sec.menu())
            _tidy(menus[name])
            bar.addMenu(menus[name])
    window._work_menus = {n: menus[n] for n in order if n in menus}
    window._work_sections = sections
    for sub in dynamic:
        if _dynamic(sub):
            sub.aboutToShow.emit()                             # refill once, now that the work menus exist
    # References to an old menu (window.view_menu, a group's title button …) mean the work menu that replaced it;
    # a command added to an old menu later appears at the end of that work menu.
    replaced = {}
    for text, menu in tops:
        name = _key(text)
        target = menus.get(name)
        if target is None and name in SUCCESSORS:
            top, section = SUCCESSORS[name]
            target = sections.get((top, section)) or menus.get(top)
        if target is not None:
            replaced[id(menu)] = target
            mirror(menu, target, (name,))
    _repoint(window, replaced)
    # Old path → new path (only where it changed), for saved buttons / mouse menus.
    aliases = {}
    for new_path, a in _leaf_paths_sep(bar):
        old = old_cpaths.get(id(a))
        if old is not None and old != new_path:
            aliases.setdefault(SEP.join(old), SEP.join(new_path))
    # … and for submenus that moved whole (mouse menus can hold a whole submenu).
    for new_path, sub in _menu_paths(bar):
        old = old_menus.get(id(sub))
        if old is not None and old != new_path:
            aliases.setdefault(SEP.join(old), SEP.join(new_path))
    window._menu_aliases = aliases
    for _n, a in _leaf_paths_sep(bar):                     # the old path on the command itself (tool_map.py)
        if id(a) in old_paths:
            a.setProperty(OLD_PATH, SEP_TEXT.join(old_paths[id(a)]))
    return window._work_menus


class _Mirror(QObject):
    """A command added to an old menu after the regrouping (e.g. «Υδραυλικά — λεπτομέρειες», added by a later
    installer) also appears in the work menu or section that replaced it."""

    def __init__(self, source, target, path):
        super().__init__(source)
        self.target, self.path = target, path
        source.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ActionAdded:
            a = event.action()
            if a not in self.target.actions():
                self.target.addAction(a)
                a.setProperty(OLD_PATH, SEP_TEXT.join(self.path + (_key(a.text()),)))
        return False


def _repoint(window, poured):
    from PySide6.QtWidgets import QToolButton
    for button in window.findChildren(QToolButton):
        if button.menu() is not None and id(button.menu()) in poured:
            button.setMenu(poured[id(button.menu())])
    for name, value in list(vars(window).items()):
        if isinstance(value, QMenu) and id(value) in poured:
            setattr(window, name, poured[id(value)])
        elif isinstance(value, dict) and name.endswith("menus"):
            for k, v in list(value.items()):
                if isinstance(v, QMenu) and id(v) in poured:
                    value[k] = poured[id(v)]


def _menu_paths(bar):
    """``[(path tuple, QMenu)]`` of every submenu of the bar (catalog spelling)."""
    out = []

    def walk(menu, path):
        for a in menu.actions():
            if a.menu() is not None and a.text():
                p = path + (a.text().replace("&&", "&"),)
                out.append((p, a.menu()))
                walk(a.menu(), p)
    for top in bar.actions():
        if top.menu() is not None:
            walk(top.menu(), (top.text().replace("&&", "&"),))
    return out


def resolve_path(window, path):
    """A menu path saved before the work menus (buttons, mouse menus) → where that command is now."""
    return (getattr(window, "_menu_aliases", None) or {}).get(path, path)


def _leaf_paths_sep(bar, path=None):
    """``[(path tuple as the catalog writes it — «&&» → «&», a)]`` of every leaf of a bar (or of a menu under
    ``path``)."""
    out = []

    def walk(menu, path):
        for a in menu.actions():
            if a.isSeparator() or not a.text():
                continue
            p = path + (a.text().replace("&&", "&"),)
            if a.menu() is not None:
                walk(a.menu(), p)
            else:
                out.append((p, a))
    if path is not None:
        walk(bar, tuple(path))
        return out
    for top in bar.actions():
        if top.menu() is not None:
            walk(top.menu(), (top.text().replace("&&", "&"),))
    return out
