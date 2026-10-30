"""The 8 main menus of the approved mockup (owner 14/10, `docs/mockups/menou_2026-10-14.png`):

Αρχείο · Επεξεργασία · CAD · Κατασκευή · Βιβλιοθήκη · Προβολή · Εργαλεία · Βοήθεια

The commands are created by many installers into the older 15 menus (Έδαφος, Δομικά, Μηχανολογικά, Κουζίνα,
Απεικόνιση …).  This runs once, last, and only *moves* what exists: the old menus become submenus (same
QMenu objects, so every ``window._…_menu`` reference keeps working), and anything not recognised stays, at
the end of its menu — no command is ever lost.  Owner decisions: Έδαφος / Δομικά / Η/Μ as submenus of
«Κατασκευή»; the 2D drawing menu is called «CAD»; Τομή and Εσωτερική όψη belong to «Προβολή».
"""
from __future__ import annotations

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
        from archforge.ui.exchange_export import actions as exchange_actions
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
