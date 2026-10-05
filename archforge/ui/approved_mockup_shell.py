from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QListWidget, QListWidgetItem, QTreeWidget,
    QTreeWidgetItem, QTabWidget, QVBoxLayout, QHBoxLayout, QSplitter, QToolBar,
    QToolButton, QCheckBox, QComboBox, QFrame, QSizePolicy, QDockWidget, QMenu
)

STYLE = """
QMainWindow { background:#F1F4F8; }
QWidget { font-family:'Segoe UI'; font-size:12px; color:#1E2A3B; }
QMenuBar,QToolBar { background:#FFFFFF; border:0; border-bottom:1px solid #D8DEE8; }
QMenuBar::item { padding:9px 12px; }
QMenuBar::item:selected,QToolButton:hover { background:#E8EEF7; }
QToolButton { border:1px solid transparent; border-radius:6px; padding:4px 7px; }
QToolButton:checked { background:#CFE0FA; border-color:#2F6BD6; }
QTabWidget::pane { border:1px solid #D8DEE8; background:#FFFFFF; }
QTabBar::tab { padding:7px 13px; background:#F7F9FC; color:#5B6778; }
QTabBar::tab:selected { background:#FFFFFF; color:#2F6BD6; font-weight:600; border-bottom:2px solid #2F6BD6; }
QTreeWidget,QListWidget { background:#FFFFFF; border:0; outline:0; }
QTreeWidget::item:selected,QListWidget::item:selected { background:#CFE0FA; }
QLineEdit,QComboBox { background:#fff; border:1px solid #D8DEE8; border-radius:5px; padding:4px 6px; }
QFrame#card { background:#FFFFFF; border:1px solid #D8DEE8; border-radius:6px; }
QLabel#cardTitle { font-weight:600; padding:6px 10px 2px 10px; }
QStatusBar { background:#FFFFFF; border-top:1px solid #D8DEE8; }
QSplitter::handle { background:#F1F4F8; }
"""

MENUS=("Αρχείο","Επεξεργασία","Προβολή","Σχεδίαση","Κατασκευή","Έδαφος","Βιβλιοθήκη","Δομικά","Υλικά","Sculpt","Κουζίνα","Μηχανολογικά","AI","Rendering","Βοήθεια")

def _card(title, widget):
    f=QFrame(); f.setObjectName("card")
    v=QVBoxLayout(f); v.setContentsMargins(0,0,0,5); v.setSpacing(0)
    t=QLabel(title); t.setObjectName("cardTitle"); v.addWidget(t); v.addWidget(widget)
    return f

def _project_panel(window):
    tabs=QTabWidget()
    # Filled from the Document by window._refresh_project_tree(): only real things.
    tree=QTreeWidget(); tree.setHeaderHidden(True)
    tree.itemClicked.connect(lambda item,_c: window._project_tree_clicked(item))
    levels_list=QListWidget(); materials_list=QListWidget()
    levels_list.itemClicked.connect(lambda item: window._activate_level_by_name(item.data(Qt.UserRole)))
    tabs.addTab(tree,"Έργο"); tabs.addTab(levels_list,"Επίπεδα"); tabs.addTab(materials_list,"Υλικά")
    window._project_levels_list=levels_list; window._project_materials_list=materials_list

    lib=QTabWidget(); page=QWidget(); v=QVBoxLayout(page); v.setContentsMargins(8,8,8,8)
    search=QLineEdit(); search.setPlaceholderText("Αναζήτηση κουζίνας..."); v.addWidget(search)
    items=QListWidget()
    kitchen_defs={
        # Parametric cabinets (doors, drawers, shelves follow the size).
        "Κάτω ντουλάπι": dict(name="Ντουλάπι βάσης",entity="cabinet",cabinet_type="base",role="cabinet",width=.60,depth=.60,height=.86),
        "Συρτάρια": dict(name="Συρταριέρα",entity="cabinet",cabinet_type="drawers",role="cabinet",width=.60,depth=.60,height=.86),
        "Ντουλάπι νεροχύτη": dict(name="Ντουλάπι νεροχύτη",entity="cabinet",cabinet_type="sink",role="cabinet",width=.80,depth=.60,height=.86),
        "Κρεμαστό ντουλάπι": dict(name="Κρεμαστό ντουλάπι",entity="cabinet",cabinet_type="wall",role="cabinet",width=.60,depth=.35,height=.72),
        "Ψηλό ντουλάπι": dict(name="Ψηλό ντουλάπι",entity="cabinet",cabinet_type="tall",role="cabinet",width=.60,depth=.60,height=2.10),
        "Ντουλάπα": dict(name="Ντουλάπα",entity="cabinet",cabinet_type="wardrobe",role="cabinet",width=1.00,depth=.60,height=2.40),
        "Νησίδα": dict(name="Νησίδα",entity="cabinet",cabinet_type="base",role="cabinet",width=1.20,depth=.90,height=.86),
    }
    # Appliances come from the core library (real 3D + plan symbol).
    appliances={"Κουζίνα με φούρνο":"Κουζίνα με φούρνο 60","Εστία":"Εστία κεραμική 60","Ψυγείο":"Ψυγειοκαταψύκτης 60",
                "Πλυντήριο πιάτων":"Πλυντήριο πιάτων 60","Απορροφητήρας":"Απορροφητήρας 60","Πλυντήριο ρούχων":"Πλυντήριο ρούχων 60",
                "Σκαμπό μπαρ":"Σκαμπό μπαρ"}
    for n in kitchen_defs: items.addItem(n)
    for n in appliances: items.addItem(n)
    def place_kitchen_component(item):
        if item.text() in appliances:
            window._place_library_by_name(appliances[item.text()]);return
        definition=kitchen_defs.get(item.text())
        if not definition:return
        window.plan_view.controller.set_component_definition(definition)
        window._set_active_tool("component")
        window.statusBar().showMessage(f'{item.text()}: μετακίνησε το ποντίκι και κάνε click για τοποθέτηση',5000)
    items.itemDoubleClicked.connect(place_kitchen_component)
    search.textChanged.connect(lambda t:[items.item(i).setHidden(t.lower() not in items.item(i).text().lower()) for i in range(items.count())])
    v.addWidget(items)
    furniture=QWidget(); fv=QVBoxLayout(furniture); fv.setContentsMargins(0,0,0,0)
    fsearch=QLineEdit(); fsearch.setPlaceholderText("Αναζήτηση επίπλων…"); fv.addWidget(fsearch)
    flist=QListWidget(); fv.addWidget(flist)
    fsearch.textChanged.connect(lambda t:[flist.item(i).setHidden(t.lower() not in flist.item(i).text().lower()) for i in range(flist.count())])
    flist.itemDoubleClicked.connect(lambda item: window._choose_library_asset(item.data(Qt.UserRole)))
    window._library_assets_list=flist
    structural=QListWidget()
    presets=[("Κολόνα 25×25 (οπλ. σκυρόδεμα)","structural_column",dict(width=.25,depth=.25)),
             ("Κολόνα 30×30 (οπλ. σκυρόδεμα)","structural_column",dict(width=.30,depth=.30)),
             ("Κολόνα 40×40 (οπλ. σκυρόδεμα)","structural_column",dict(width=.40,depth=.40)),
             ("Κολόνα 25×50 (τοιχίο)","structural_column",dict(width=.50,depth=.25)),
             ("Δοκός 20×30","structural_beam",dict(width=.20,height=.30)),
             ("Δοκός 25×50","structural_beam",dict(width=.25,height=.50)),
             ("Δοκός 30×60","structural_beam",dict(width=.30,height=.60))]
    for label,tool,preset in presets:
        it=QListWidgetItem(label); it.setData(Qt.UserRole,(tool,preset)); structural.addItem(it)
    structural.itemDoubleClicked.connect(lambda item: window._start_structural_preset(*item.data(Qt.UserRole)))
    structural.setToolTip("Διπλό κλικ: ξεκινά το εργαλείο με αυτή τη διατομή")
    mats=QListWidget(); window._library_materials_list=mats
    mats.itemDoubleClicked.connect(lambda item: window._apply_material_to_selection(item.data(Qt.UserRole)))
    mats.setToolTip("Διπλό κλικ: εφαρμόζει το υλικό στο επιλεγμένο αντικείμενο")
    lib.addTab(structural,"Δομικά"); lib.addTab(furniture,"Έπιπλα"); lib.addTab(page,"Κουζίνα"); lib.addTab(mats,"Υλικά"); lib.setCurrentIndex(2)
    box=QWidget(); lay=QVBoxLayout(box); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
    lay.addWidget(_card("Έργο",tabs),5); lay.addWidget(_card("Βιβλιοθήκη",lib),6)
    window.project_tree=tree
    return box

def _thumb_strip(names):
    w=QListWidget(); w.setFlow(QListWidget.LeftToRight); w.setWrapping(False); w.setFixedHeight(92)
    for n in names: w.addItem(QListWidgetItem(n))
    return w

def _adopt(toolbar, widget):
    """Move a widget from a hidden legacy toolbar into ``toolbar``.

    The widget is hidden at this point (its legacy toolbar is hidden), and
    QToolBar.addWidget then creates an invisible action for it, so the
    selector never appeared in the ribbon. Make the new action visible.
    """
    for old in widget.window().findChildren(QToolBar):
        if old is toolbar:continue
        for action in list(old.actions()):
            if old.widgetForAction(action) is widget:
                old.removeAction(action)
    toolbar.addWidget(widget).setVisible(True)


def install_approved_mockup_shell(window):
    """Use the supplied mockup structure, but mount the real ArchForge editors."""
    window.setWindowTitle("ArchForge"); window.resize(1536,1000); window.setStyleSheet(STYLE)

    # Replace the old menu presentation with the supplied mockup menu row.
    # The real File/Edit/View commands move into the Greek menus; the legacy
    # toolbars that also carried them are hidden below, so without this the
    # menus would be empty and Save/Open/Undo would only exist as shortcuts.
    mb=window.menuBar(); mb.clear()
    menus={name:mb.addMenu(name) for name in MENUS}
    file_menu=menus["Αρχείο"]
    for a in (window.new_action,window.open_action,window.save_action):file_menu.addAction(a)
    file_menu.addSeparator(); file_menu.addAction(window.export_stl_action)
    edit_menu=menus["Επεξεργασία"]
    edit_menu.addAction(window.undo_action); edit_menu.addAction(window.redo_action)
    edit_menu.addSeparator(); edit_menu.addAction(window.delete_action)
    window.view_menu=menus["Προβολή"]
    window.status_bar_action.setText("Γραμμή κατάστασης")
    window.view_menu.addAction(window.status_bar_action)
    window._mockup_menus=menus
    site_action=QAction("Έδαφος (οικόπεδο)",window); site_action.triggered.connect(window._create_terrain)
    menus["Κατασκευή"].addAction(site_action)
    # Έδαφος menu, modelled on Home Designer's Terrain menu.
    terrain_menu=menus["Έδαφος"]
    for text,run in (
        ("Δημιουργία εδάφους",window._create_terrain),
        ("Προδιαγραφές εδάφους…",window._show_terrain_specification),
        ("Διαγραφή εδάφους",window._delete_terrain),
        (None,None),
        ("Υψομετρικά σημεία",lambda: window._start_site_tool(
            "terrain_point","Κλικ στην κάτοψη και δώσε υψόμετρο — Esc για τέλος")),
        (None,None),
        ("Φυτό: Δέντρο",lambda: window._start_site_tool(
            "plant_tree","Κλικ στην κάτοψη για δέντρο — Esc για τέλος")),
        ("Φυτό: Θάμνος",lambda: window._start_site_tool(
            "plant_shrub","Κλικ στην κάτοψη για θάμνο — Esc για τέλος")),
        (None,None),
        ("Μονοπάτι",lambda: window._start_site_tool("path_path","Σύρε στην κάτοψη από την αρχή ως το τέλος — Esc για τέλος")),
        ("Πεζοδρόμιο",lambda: window._start_site_tool("path_sidewalk","Σύρε στην κάτοψη από την αρχή ως το τέλος — Esc για τέλος")),
        ("Δρόμος",lambda: window._start_site_tool("path_road","Σύρε στην κάτοψη από την αρχή ως το τέλος — Esc για τέλος")),
    ):
        if text is None:terrain_menu.addSeparator();continue
        a=QAction(text,window); a.triggered.connect(lambda _=False,r=run: r()); terrain_menu.addAction(a)
    window._mockup_terrain_menu=terrain_menu
    roof_action=QAction("Ξύλινη κεραμοσκεπή (δοκοί & κεραμίδια)",window)
    roof_action.triggered.connect(lambda: window._create_pitched_roof())
    menus["Κατασκευή"].addAction(roof_action); window._pitched_roof_action=roof_action
    roof_layer=QAction("Σκελετός στέγης στο 3D",window); roof_layer.setCheckable(True); roof_layer.setChecked(True)
    roof_layer.toggled.connect(lambda on: window._set_layer_visible("roof_structure",on))
    tiles_layer=QAction("Κεραμίδια στο 3D",window); tiles_layer.setCheckable(True); tiles_layer.setChecked(True)
    tiles_layer.toggled.connect(lambda on: window._set_layer_visible("roof_tiles",on))
    for a in (roof_layer,tiles_layer):
        menus["Κατασκευή"].addAction(a); window.view_menu.addAction(a)
    window._roof_tiles_layer_action=tiles_layer
    structure_menu=menus["Δομικά"]
    structure_menu.addSeparator()
    for text,run in (("Στοιχεία κτιρίου για στατική…",lambda: window._edit_structural_settings()),
                     ("Στατική ανάλυση φέροντος οργανισμού…",lambda: window._show_structural_analysis())):
        a=QAction(text,window); a.triggered.connect(lambda _=False,r=run: r()); structure_menu.addAction(a)
    window._structure_menu=structure_menu
    mep_menu=menus["Μηχανολογικά"]
    from archforge.mep.plumbing import POINT_TYPES
    plumbing=QMenu("Υδραυλικά σημεία",mep_menu); mep_menu.addMenu(plumbing)
    for key,(label,_c,_h,_z,_l) in POINT_TYPES.items():
        a=QAction(label,window)
        a.triggered.connect(lambda _=False,k=key,l=label: window._start_site_tool(f"plumb_{k}",f"{l}: κλικ στην κάτοψη — οι σωληνώσεις χαράζονται αυτόματα, Esc για τέλος"))
        plumbing.addAction(a)
    window._mockup_plumbing_menu=plumbing
    from archforge.mep.electrical import POINT_TYPES as ELEC
    electrical=QMenu("Ηλεκτρολογικά σημεία",mep_menu); mep_menu.addMenu(electrical)
    for key,(label,_g,_w,_h,_l) in ELEC.items():
        a=QAction(label,window)
        a.triggered.connect(lambda _=False,k=key,l=label: window._start_site_tool(f"elec_{k}",f"{l}: κλικ στην κάτοψη — τα κυκλώματα σχηματίζονται αυτόματα, Esc για τέλος"))
        electrical.addAction(a)
    window._mockup_electrical_menu=electrical
    from archforge.mep.ventilation import POINT_TYPES as VENT
    ventilation=QMenu("Εξαερισμοί",mep_menu); mep_menu.addMenu(ventilation)
    for key,(label,_q,_h,_m,_l) in VENT.items():
        a=QAction(label,window)
        a.triggered.connect(lambda _=False,k=key,l=label: window._start_site_tool(f"vent_{k}",f"{l}: κλικ στην κάτοψη — ο αεραγωγός βγαίνει αυτόματα έξω, Esc για τέλος"))
        ventilation.addAction(a)
    window._mockup_ventilation_menu=ventilation
    schedule=QAction("Πίνακας κυκλωμάτων…",window); schedule.triggered.connect(lambda: window._show_circuit_schedule())
    mep_menu.addAction(schedule)
    elec_layer=QAction("Ηλεκτρολογικά στο 3D",window); elec_layer.setCheckable(True); elec_layer.setChecked(True)
    elec_layer.toggled.connect(lambda on: window._set_layer_visible("elec",on))
    mep_menu.addAction(elec_layer); window.view_menu.addAction(elec_layer); window._elec_layer_action=elec_layer
    vent_layer=QAction("Εξαερισμοί στο 3D",window); vent_layer.setCheckable(True); vent_layer.setChecked(True)
    vent_layer.toggled.connect(lambda on: window._set_layer_visible("vent",on))
    mep_menu.addAction(vent_layer); window.view_menu.addAction(vent_layer); window._vent_layer_action=vent_layer
    layer=QAction("Μηχανολογικά στο 3D",window); layer.setCheckable(True); layer.setChecked(True)
    layer.toggled.connect(lambda on: window._set_layer_visible("mep",on))
    mep_menu.addAction(layer); window.view_menu.addAction(layer); window._mep_layer_action=layer
    library_menu=menus["Βιβλιοθήκη"]
    for text,run in (("Τοποθέτηση αντικειμένου…",lambda: window._choose_library_asset()),
                     ("Object Modifier (επιλεγμένο)…",lambda: window._open_object_modifier()),
                     ("Εισαγωγή μοντέλου glTF/GLB…",lambda: window._import_gltf_model()),
                     ("Εισαγωγή από Home Designer (.calib/.calibz)…",lambda: window._import_hd_catalog())):
        a=QAction(text,window); a.triggered.connect(lambda _=False,r=run: r()); library_menu.addAction(a)
    window._mockup_library_menu=library_menu
    ao=QAction("Σκιές επαφής (Ambient Occlusion)",window); ao.setCheckable(True); ao.setChecked(True)
    ao.toggled.connect(window.pbr_view.set_ambient_occlusion)
    menus["Rendering"].addAction(ao)
    window._mockup_ao_action=ao
    sun_menu=QMenu("Ήλιος & ουρανός",menus["Rendering"]); menus["Rendering"].addMenu(sun_menu)
    sun_group=QActionGroup(sun_menu); sun_group.setExclusive(True)
    for text,hour in (("Πρωί (09:00)",9.0),("Μεσημέρι (11:00)",11.0),("Απόγευμα (17:00)",17.0),
                      ("Δειλινό (19:00)",19.0),("Χωρίς ουρανό (στούντιο)",None)):
        a=QAction(text,sun_menu); a.setCheckable(True); a.setChecked(hour==11.0)
        a.triggered.connect(lambda _=False,h=hour: window.pbr_view.set_sun(h)); sun_group.addAction(a); sun_menu.addAction(a)
    sun_menu.addSeparator()
    custom=QAction("Ώρα και μήνας…",sun_menu); custom.triggered.connect(window._choose_sun_time); sun_menu.addAction(custom)
    window._mockup_sun_menu=sun_menu
    # Keep keyboard shortcuts live although their toolbars are hidden.
    for a in (window.new_action,window.open_action,window.save_action,
              window.undo_action,window.redo_action,window.delete_action):
        window.addAction(a)

    # Existing development toolbars remain command owners only. Keep them
    # hidden and also hide their View-menu toggle actions so controls do not
    # appear twice above/below the approved ribbon.
    for tb in window.findChildren(QToolBar):
        tb.hide()
        tb.toggleViewAction().setVisible(False)

    ribbon=QToolBar("Mockup Ribbon",window); ribbon.setMovable(False); ribbon.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    tool_specs=(
        ("Επιλογή","select"),("Τοίχος","wall"),("Πόρτα","door"),("Παράθυρο","window"),
        ("Άνοιγμα","opening_rect"),("Σκάλα / Ράμπα","circulation"),
        ("Κολώνα","structural_column"),("Δοκός","structural_beam"),
        ("Sculpt","sculpt"),("Υλικά","materials")
    )
    for label,tool in tool_specs:
        if tool=="circulation":
            # One grouped vertical-circulation tool, as in the legacy toolbar.
            menu=QMenu(window)
            for text,t in (("Σκάλα","stair"),("Ράμπα","ramp")):
                item=QAction(text,menu); item.triggered.connect(lambda _=False,t=t: window._set_active_tool(t)); menu.addAction(item)
            # Explicit stair type; the wheel/Tab still switch while placing.
            types=QMenu("Τύπος σκάλας",menu); menu.addMenu(types)
            window._mockup_circulation_menu=menu; window._mockup_stair_type_menu=types
            for text,layout in (("Αυτόματη",None),("Ευθεία","straight"),("Γ (L)","l"),("Π (U)","u"),("Σπιράλ","spiral")):
                item=QAction(text,types)
                item.triggered.connect(lambda _=False,l=layout: window._choose_stair_layout(l))
                types.addAction(item)
            button=QToolButton(ribbon); button.setText(label); button.setToolTip("Σκάλα ή Ράμπα")
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup); button.setMenu(menu)
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            ribbon.addWidget(button); window._mockup_circulation_button=button
            continue
        a=QAction(label,window)
        if tool=="sculpt": a.triggered.connect(lambda _=False: window.sculpt_action.toggle())
        elif tool=="materials": a.triggered.connect(window._open_selected_materials)
        else: a.triggered.connect(lambda _=False,t=tool: window._set_active_tool(t))
        ribbon.addAction(a)
    # Reuse the proven Sculpt controls from the original toolbar. Hiding the
    # legacy toolbar must not hide access to brush operation/radius.
    # Reuse the isolated semantic Kitchen command already owned by MainWindow.
    # Do not duplicate generation logic in the mockup shell.
    ribbon.addSeparator()
    ribbon.addWidget(QLabel("Sculpt Op:"))
    _adopt(ribbon,window.sculpt_operation)
    ribbon.addWidget(QLabel("Brush Size:"))
    _adopt(ribbon,window.sculpt_radius)
    ribbon.addSeparator()
    auto_floor=QAction("Auto Floor",window); auto_floor.triggered.connect(window._create_auto_floors); ribbon.addAction(auto_floor)
    flat_roof=QAction("Flat / Auto Roof",window); flat_roof.triggered.connect(window._create_flat_roofs); ribbon.addAction(flat_roof)
    window._mockup_auto_floor_action=auto_floor
    terrain=QAction("Έδαφος",window); terrain.triggered.connect(window._create_terrain); ribbon.addAction(terrain)
    window._mockup_terrain_action=terrain
    window._mockup_flat_roof_action=flat_roof
    window.addToolBar(Qt.TopToolBarArea,ribbon)

    # Second row: storey/display, camera and snapping. A single row needs
    # ~1700 px, so on a laptop these controls fell into the hidden overflow.
    camera=QToolBar("Mockup Camera",window); camera.setMovable(False)
    add_floor=QAction("+ Όροφος",window); add_floor.triggered.connect(window._add_floor_level); camera.addAction(add_floor)
    window._mockup_add_floor_action=add_floor
    camera.addWidget(QLabel("Όροφος: ")); _adopt(camera,window.floor_selector)
    camera.addWidget(QLabel("  Απεικόνιση: ")); _adopt(camera,window.render_technique)
    camera.addSeparator(); camera.addWidget(QLabel("Κάμερα: "))
    for label,mode in (("Top","top"),("Front","front"),("Side","side"),("3D","orbit")):
        a=QAction(label,window); a.triggered.connect(lambda _=False,m=mode: window._set_pbr_camera(m)); camera.addAction(a)
    camera.addSeparator()
    grid=QCheckBox("Grid"); grid.setChecked(True); camera.addWidget(grid)
    snap=QCheckBox("Snap"); snap.setChecked(window.snap_action.isChecked()); snap.toggled.connect(window.snap_action.setChecked); window.snap_action.toggled.connect(snap.setChecked); camera.addWidget(snap)
    snap_size=QComboBox(); snap_size.addItems(("0.10 m","0.05 m","0.25 m","0.50 m")); camera.addWidget(QLabel("  Snap: ")); camera.addWidget(snap_size)
    # Own row: sharing the ribbon row squeezed Grid/Snap into the overflow.
    window.addToolBarBreak(Qt.TopToolBarArea)
    window.addToolBar(Qt.TopToolBarArea,camera)

    # The real editors are mounted simultaneously, exactly where the supplied
    # prototype had PlanView and PBRViewport placeholders.
    right_tabs=QTabWidget()
    right_tabs.addTab(window.pbr_view,"3D Σκηνή")
    right_tabs.addTab(window.structural_view,"Structural")
    window.tabs=right_tabs
    right_tabs.currentChanged.connect(window._on_tab_changed)

    # Default workflow: one large central editor, as requested. 2D is the
    # default; 3D and Structural are one click away. No functionality is lost.
    plan_card=_card("Κάτοψη - Ισόγειο",window.plan_view)
    window._plan_title=plan_card.findChild(QLabel,"cardTitle")
    # PlanView came from the old QTabWidget. Qt can preserve the hidden state
    # of a page when it is reparented; explicitly restore the real interactive
    # QGraphicsView and its viewport after mounting it in the approved shell.
    window.plan_view.setEnabled(True)
    window.plan_view.setVisible(True)
    window.plan_view.show()
    window.plan_view.viewport().setVisible(True)
    window.plan_view.viewport().show()
    window.plan_view.redraw()
    window.plan_view.viewport().update()
    central_tabs=QTabWidget()
    central_tabs.addTab(plan_card,"2D Σχεδίαση")
    central_tabs.addTab(right_tabs,"3D / Structural")
    central_tabs.setCurrentIndex(0)

    def central_changed(index):
        if index==0:
            window.view=window.plan_view
            window.plan_view.setVisible(True)
            window.plan_view.viewport().setVisible(True)
            window.plan_view.redraw()
            window.plan_view.viewport().update()
            if hasattr(window.plan_view,"setFocus"): window.plan_view.setFocus()
        else:
            current=right_tabs.currentWidget()
            window.view=current if current in (window.pbr_view,window.structural_view) else window.pbr_view
            if window.view is window.pbr_view: window.pbr_view.activate()
            elif window.view is window.structural_view: window.structural_view.activate()
    central_tabs.currentChanged.connect(central_changed)

    strips=QHBoxLayout(); strips.setSpacing(6)
    # Every view is live: camera presets, Doll House / Ortho overviews, and the
    # Section / Interior views that are dragged as a line in the 2D plan.
    view_specs=(
        ("3D Προοπτική",lambda: window._set_pbr_camera("orbit")),
        ("Top",lambda: window._set_pbr_camera("top")),
        ("Front",lambda: window._set_pbr_camera("front")),
        ("Side",lambda: window._set_pbr_camera("side")),
        ("Doll House",lambda: window._set_pbr_camera("dollhouse")),
        ("Ορθογραφική",lambda: window._set_pbr_camera("ortho")),
        ("Τομή",lambda: window._start_view_line_tool("section")),
        ("Εσωτερική Όψη",lambda: window._start_view_line_tool("camera")),
        ("Render (PBR)",lambda: (window._set_render_style_from_workspace("pbr"),window._set_pbr_camera("orbit"))),
        ("Walkthrough",lambda: window._set_pbr_camera("eye")),
    )
    views=_thumb_strip(tuple(label for label,_ in view_specs))
    view_actions=dict(view_specs)
    views.itemClicked.connect(lambda item: view_actions[item.text()]())
    window._mockup_view_actions=view_actions
    styles=_thumb_strip(("Ρεαλιστικό","Φυσικό φως","Βραδινό","Clay","Sketch"))

    center=QWidget(); cv=QVBoxLayout(center); cv.setContentsMargins(0,0,0,0); cv.setSpacing(6)
    cv.addWidget(central_tabs,1)
    window.setCentralWidget(center)

    # Optional simultaneous mode remains available. It is deliberately not
    # the default. The same real widgets are reparented; no duplicate model.
    def _show_plan():
        window.plan_view.setVisible(True)
        window.plan_view.viewport().setVisible(True)
        window.plan_view.redraw()
        window.plan_view.viewport().update()

    def set_simultaneous(enabled):
        enabled=bool(enabled)
        if enabled:
            if central_tabs.indexOf(plan_card)>=0: central_tabs.removeTab(central_tabs.indexOf(plan_card))
            if central_tabs.indexOf(right_tabs)>=0: central_tabs.removeTab(central_tabs.indexOf(right_tabs))
            split=QSplitter(Qt.Horizontal)
            split.addWidget(plan_card); split.addWidget(right_tabs)
            split.setCollapsible(0,False); split.setCollapsible(1,False); split.setSizes([430,650])
            central_tabs.addTab(split,"2D + 3D")
            central_tabs.setCurrentWidget(split)
            window._mockup_center_split=split
            # removeTab() leaves the former pages hidden and Qt keeps that
            # state when they are reparented into the splitter.
            plan_card.show(); right_tabs.show()
            _show_plan()
            current=right_tabs.currentWidget()
            if current is window.pbr_view: window.pbr_view.activate()
            elif current is window.structural_view: window.structural_view.activate()
        else:
            split=getattr(window,"_mockup_center_split",None)
            if split is not None:
                plan_card.setParent(None); right_tabs.setParent(None)
                idx=central_tabs.indexOf(split)
                if idx>=0: central_tabs.removeTab(idx)
                split.deleteLater()
            if central_tabs.indexOf(plan_card)<0: central_tabs.insertTab(0,plan_card,"2D Σχεδίαση")
            if central_tabs.indexOf(right_tabs)<0: central_tabs.insertTab(1,right_tabs,"3D / Structural")
            central_tabs.setCurrentWidget(plan_card)
            window._mockup_center_split=None
            _show_plan()
        window.view=window.plan_view if not enabled else window.plan_view
    window._set_simultaneous_views=set_simultaneous

    # All surrounding mockup regions are genuine closable/restorable docks.
    # Their toggleViewAction entries live in Προβολή, so a closed panel is
    # always recoverable from the appropriate menu.
    left=_project_panel(window)
    project_dock=QDockWidget("Έργο / Βιβλιοθήκη",window)
    project_dock.setObjectName("approved_project_library")
    project_dock.setWidget(left)
    project_dock.setAllowedAreas(Qt.LeftDockWidgetArea|Qt.RightDockWidgetArea)
    window.addDockWidget(Qt.LeftDockWidgetArea,project_dock)

    window.dock.setWindowTitle("Ιδιότητες")
    window.dock.setObjectName("approved_properties")
    window.addDockWidget(Qt.RightDockWidgetArea,window.dock)

    bottom=QWidget(); bv=QHBoxLayout(bottom); bv.setContentsMargins(0,0,0,0); bv.setSpacing(6)
    bv.addWidget(_card("Προβολές",views),6); bv.addWidget(_card("Στυλ Rendering",styles),4)
    views_dock=QDockWidget("Προβολές / Στυλ Rendering",window)
    views_dock.setObjectName("approved_views_rendering")
    views_dock.setWidget(bottom)
    views_dock.setAllowedAreas(Qt.BottomDockWidgetArea|Qt.TopDockWidgetArea)
    window.addDockWidget(Qt.BottomDockWidgetArea,views_dock)

    # Βοηθός: live proposals over the whole Document, tabbed with the Properties.
    assistant_dock=QDockWidget("Βοηθός",window)
    assistant_dock.setObjectName("approved_assistant")
    assistant_dock.setWidget(window._build_assistant_panel())
    assistant_dock.setAllowedAreas(Qt.LeftDockWidgetArea|Qt.RightDockWidgetArea)
    window.addDockWidget(Qt.RightDockWidgetArea,assistant_dock)
    window.tabifyDockWidget(window.dock,assistant_dock)
    window.dock.raise_()
    window._assistant_dock=assistant_dock
    window._schedule_assistant_refresh()

    for d in (project_dock,window.dock,views_dock,assistant_dock):
        d.setFeatures(QDockWidget.DockWidgetClosable|QDockWidget.DockWidgetMovable|QDockWidget.DockWidgetFloatable)

    # Restore buttons/menu: Προβολή -> Παράθυρα.
    panels=window.view_menu.addMenu("Παράθυρα")
    for d in (project_dock,window.dock,assistant_dock,views_dock):
        panels.addAction(d.toggleViewAction())
    # Workspace docks built before the shell (Library, AI, ...) lost their
    # toggles with the old View menu; keep them recoverable here too.
    extra=[d for d in getattr(window,"workspace_docks",()) if d not in (project_dock,window.dock,views_dock,assistant_dock)]
    if extra:
        panels.addSeparator()
        for d in extra: panels.addAction(d.toggleViewAction())

    window.resizeDocks([project_dock],[270],Qt.Horizontal)
    window.resizeDocks([window.dock],[280],Qt.Horizontal)
    window.resizeDocks([views_dock],[120],Qt.Vertical)
    window.view=window.plan_view
    window._mockup_right_tabs=right_tabs
    window._approved_docks=(project_dock,window.dock,views_dock)
    window._central_tabs=central_tabs
    window._update_plan_title()

    views_menu=QMenu("3D Προβολές",window.view_menu); window.view_menu.addMenu(views_menu)
    for label,run in view_specs:
        a=QAction(label,views_menu); a.triggered.connect(lambda _=False,r=run: r()); views_menu.addAction(a)
    window._mockup_views_menu=views_menu

    simultaneous=QAction("Ταυτόχρονα 2D + 3D",window)
    simultaneous.setCheckable(True)
    simultaneous.setChecked(False)
    simultaneous.toggled.connect(set_simultaneous)
    window.view_menu.addSeparator()
    window.view_menu.addAction(simultaneous)
    window._simultaneous_action=simultaneous
