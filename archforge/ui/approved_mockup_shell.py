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

MENUS=("Αρχείο","Επεξεργασία","Προβολή","Σχεδίαση","Κατασκευή","Έδαφος","Βιβλιοθήκη","Δομικά","Υλικά","Γλυπτική","Κουζίνα","Μηχανολογικά","Βοηθός AI","Απεικόνιση","Βοήθεια")

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
    # Right click: properties / delete; Delete key deletes what is selected in the tree.
    tree.setContextMenuPolicy(Qt.CustomContextMenu)
    tree.customContextMenuRequested.connect(lambda pos: window._project_tree_menu(pos))
    from PySide6.QtGui import QShortcut, QKeySequence
    tree_delete=QShortcut(QKeySequence(Qt.Key_Delete),tree); tree_delete.setContext(Qt.WidgetShortcut)
    tree_delete.activated.connect(lambda: window._delete_selection()); window._tree_delete_shortcut=tree_delete
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
        # Corner units and mechanisms (same parametric cabinet; style/mechanism editable in Ιδιότητες).
        "Γωνιακό Γ 90×90 με καρουζέλ": dict(name="Γωνιακό ντουλάπι βάσης (Γ)",entity="cabinet",cabinet_type="corner",role="cabinet",width=.90,depth=.90,height=.86,mechanism="carousel"),
        "Γωνιακό τυφλό με φασόλι": dict(name="Γωνιακό τυφλό ντουλάπι",entity="cabinet",cabinet_type="corner_blind",role="cabinet",width=1.10,depth=.60,height=.86,mechanism="half_moon"),
        "Συρόμενο καλάθι (cargo) 20": dict(name="Συρόμενο καλάθι",entity="cabinet",cabinet_type="base",role="cabinet",width=.20,depth=.60,height=.86,mechanism="cargo"),
        "Νεροχύτη με κάδους": dict(name="Ντουλάπι νεροχύτη με κάδους",entity="cabinet",cabinet_type="sink",role="cabinet",width=.80,depth=.60,height=.86,mechanism="bin"),
        "Με εσωτερικά συρτάρια": dict(name="Ντουλάπι με εσωτερικά συρτάρια",entity="cabinet",cabinet_type="base",role="cabinet",width=.60,depth=.60,height=.86,mechanism="inner_drawers"),
        "Κρεμαστό ανακλινόμενο": dict(name="Κρεμαστό ανακλινόμενο",entity="cabinet",cabinet_type="wall",role="cabinet",width=.90,depth=.35,height=.36,z=1.81,mechanism="lift_up",shelves=0),
        "Κρεμαστό βιτρίνα": dict(name="Κρεμαστό βιτρίνα",entity="cabinet",cabinet_type="wall",role="cabinet",width=.60,depth=.35,height=.72,front_style="glass"),
        "Ψηλή συρόμενη αποθήκη": dict(name="Ψηλή συρόμενη αποθήκη",entity="cabinet",cabinet_type="tall",role="cabinet",width=.40,depth=.60,height=2.10,mechanism="larder"),
    }
    # Appliances come from the core library (real 3D + plan symbol).
    appliances={"Κουζίνα με φούρνο":"Κουζίνα με φούρνο 60","Εστία":"Εστία κεραμική 60","Ψυγείο":"Ψυγειοκαταψύκτης 60",
                "Πλυντήριο πιάτων":"Πλυντήριο πιάτων 60","Απορροφητήρας":"Απορροφητήρας 60","Πλυντήριο ρούχων":"Πλυντήριο ρούχων 60",
                "Σκαμπό μπαρ":"Σκαμπό μπαρ"}
    for n in kitchen_defs: items.addItem(n)
    for n in appliances: items.addItem(n)
    window._kitchen_defs=kitchen_defs
    def place_kitchen_item(name):
        if name in appliances:
            window._place_library_by_name(appliances[name]);return
        definition=kitchen_defs.get(name)
        if not definition:return
        window.plan_view.controller.set_component_definition(definition)
        window._set_active_tool("component")
        window.statusBar().showMessage(f'{name}: μετακίνησε το ποντίκι και κάνε click για τοποθέτηση',5000)
    window._place_kitchen_item=place_kitchen_item
    window._kitchen_item_names=tuple(kitchen_defs)+tuple(appliances)
    items.itemDoubleClicked.connect(lambda item: place_kitchen_item(item.text()))
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
    window._structural_presets=presets
    for label,tool,preset in presets:
        it=QListWidgetItem(label); it.setData(Qt.UserRole,(tool,preset)); structural.addItem(it)
    structural.itemDoubleClicked.connect(lambda item: window._start_structural_preset(*item.data(Qt.UserRole)))
    structural.setToolTip("Διπλό κλικ: ξεκινά το εργαλείο με αυτή τη διατομή")
    mats=QListWidget(); window._library_materials_list=mats
    mats.itemDoubleClicked.connect(lambda item: window._apply_material_to_selection(item.data(Qt.UserRole)))
    mats.setToolTip("Διπλό κλικ: εφαρμόζει το υλικό στο επιλεγμένο αντικείμενο")
    lib.addTab(structural,"Δομικά"); lib.addTab(furniture,"Έπιπλα"); lib.addTab(page,"Κουζίνα"); lib.addTab(mats,"Υλικά"); lib.setCurrentIndex(2)
    box=QWidget(); lay=QVBoxLayout(box); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
    # The library as one tree of themes with one search (the tabbed lists stay as data sources).
    window._legacy_library_tabs=lib; lib.hide()
    browser=QWidget(); bl=QVBoxLayout(browser); bl.setContentsMargins(6,6,6,6); bl.setSpacing(4)
    lsearch=QLineEdit(); lsearch.setPlaceholderText("Αναζήτηση στη βιβλιοθήκη…"); bl.addWidget(lsearch)
    ltree=QTreeWidget(); ltree.setHeaderHidden(True); bl.addWidget(ltree)
    ltree.itemDoubleClicked.connect(lambda item,_c: window._library_tree_action(item))
    lsearch.textChanged.connect(window._filter_library_tree)
    window._library_tree=ltree; window._library_search=lsearch
    from archforge.ui.library_drag import install_tree_carry
    install_tree_carry(window,ltree)     # σύρσιμο φύλλου στην κάτοψη / στο 3D
    lay.addWidget(_card("Έργο",tabs),5); lay.addWidget(_card("Βιβλιοθήκη",browser),6)
    window._refresh_library_tree()
    window.project_tree=tree
    return box

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
    brief_action=QAction("Στοιχεία έργου (ερωτήσεις)…",window); brief_action.triggered.connect(lambda: window._edit_project_brief())
    file_menu.addAction(brief_action); window._brief_action=brief_action
    for a in (window.new_action,window.open_action,window.save_action):file_menu.addAction(a)
    file_menu.addSeparator()
    pdf_action=QAction("Εξαγωγή PDF (κατόψεις, επιμέτρηση, προσφορά)…",window); pdf_action.triggered.connect(lambda: window._export_pdf())
    file_menu.addAction(pdf_action); window._pdf_action=pdf_action
    prices_action=QAction("Τιμές & προσφορά…",window); prices_action.triggered.connect(lambda: window._edit_prices())
    file_menu.addAction(prices_action); window._prices_action=prices_action
    file_menu.addAction(window.export_stl_action)
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
    # Στέγη, by theme: with tiles (timber pitched roofs), without tiles (flat), attic ceiling, tools.
    roof_menu=QMenu("Στέγη",menus["Κατασκευή"]); menus["Κατασκευή"].addMenu(roof_menu)
    window._roof_menu=roof_menu
    renovation=QMenu("Ανακαίνιση (φάσεις)",menus["Κατασκευή"]); menus["Κατασκευή"].addMenu(renovation)
    window._renovation_menu=renovation
    for text,run in (("Όλα τα σχεδιασμένα = Υφιστάμενα (αποτύπωση)",lambda: window._set_phase(list(window.doc.entities),"existing")),
                     ("Επιλεγμένα → Καθαίρεση",lambda: window._set_phase(list(window.doc.selection),"demolish")),
                     ("Επιλεγμένα → Νέα",lambda: window._set_phase(list(window.doc.selection),"new"))):
        a=QAction(text,window); a.triggered.connect(lambda _=False,r=run: r()); renovation.addAction(a)
    takeoff=QAction("Επιμέτρηση εργασιών (ανά χώρο)…",window); takeoff.triggered.connect(lambda: window._show_takeoff())
    menus["Κατασκευή"].addAction(takeoff); window._takeoff_action=takeoff
    isotex=QAction("Τεμάχια Isotex (αναγωγή)…",window); isotex.triggered.connect(lambda: window._show_isotex())
    menus["Κατασκευή"].addAction(isotex); window._isotex_action=isotex
    priced=QAction("Λίστα υλικών με τιμές (Excel)…",window); priced.triggered.connect(lambda: window._export_priced_lists())
    menus["Κατασκευή"].addAction(priced); window._priced_lists_action=priced
    menus["Κατασκευή"].addAction(prices_action); menus["Κατασκευή"].addAction(pdf_action)
    tiled=QMenu("Με κεραμίδια (ξύλινη στέγη)",roof_menu); roof_menu.addMenu(tiled); window._roof_tiled_menu=tiled
    from archforge.structure.timber_roof import FORMS
    auto_tiled=QAction("Αυτόματα (μορφή από κάτοψη & φορτία)",window)
    auto_tiled.triggered.connect(lambda: window._auto_tiled_roofs()); tiled.addAction(auto_tiled); tiled.addSeparator()
    for form,label in FORMS.items():
        a=QAction(label,window); a.triggered.connect(lambda _=False,f=form: window._create_pitched_roof(f)); tiled.addAction(a)
        if form=="gable": window._pitched_roof_action=a
    flat=QMenu("Χωρίς κεραμίδια (επίπεδη / δώμα)",roof_menu); roof_menu.addMenu(flat); window._roof_flat_menu=flat
    auto_roof=QAction("Αυτόματη επίπεδη στέγη (μόνο όπου δεν υπάρχει όροφος από πάνω)",window)
    auto_roof.triggered.connect(lambda: window._auto_roofs()); flat.addAction(auto_roof)
    attic=QMenu("Οροφή σοφίτας κάτω από κεραμοσκεπή",roof_menu); roof_menu.addMenu(attic); window._roof_attic_menu=attic
    for text,kind in (("Πλάκα σκυροδέματος","slab"),("Ξύλινες δοκίδες","joists")):
        a=QAction(text,window); a.triggered.connect(lambda _=False,k=kind: window._attic_ceilings(k)); attic.addAction(a)
    roof_menu.addSeparator()
    for text,choice in (("Κεραμοσκεπή σε χώρο (κλικ στον χώρο)","tiled"),("Ταράτσα σε χώρο (κλικ στον χώρο)","terrace")):
        a=QAction(text,window)
        a.triggered.connect(lambda _=False,c=choice,t=text: window._start_site_tool(f"roofroom_{c}",f"{t.split(' (')[0]}: κλικ μέσα στον χώρο — οι άλλοι χώροι κρατούν τη δική τους στέγη, Esc για τέλος"))
        roof_menu.addAction(a)
    roof_menu.addSeparator()
    fix_roofs=QAction("Διόρθωση στεγών",window); fix_roofs.setToolTip("Αφαιρεί στέγες κάτω από όροφο και προσθέτει όσες λείπουν")
    fix_roofs.triggered.connect(lambda: window._fix_roofs()); roof_menu.addAction(fix_roofs)
    delete_roofs=QAction("Διαγραφή όλων των στεγών",window)
    delete_roofs.triggered.connect(lambda: window._delete_all_roofs()); roof_menu.addAction(delete_roofs)
    roof_layer=QAction("Σκελετός στέγης στο 3D",window); roof_layer.setCheckable(True); roof_layer.setChecked(True)
    roof_layer.toggled.connect(lambda on: window._set_layer_visible("roof_structure",on))
    tiles_layer=QAction("Κεραμίδια στο 3D",window); tiles_layer.setCheckable(True); tiles_layer.setChecked(True)
    tiles_layer.toggled.connect(lambda on: window._set_layer_visible("roof_tiles",on))
    for a in (roof_layer,tiles_layer):
        menus["Κατασκευή"].addAction(a); window.view_menu.addAction(a)
    window._roof_tiles_layer_action=tiles_layer
    structure_menu=menus["Δομικά"]
    structure_menu.addSeparator()
    for text,run in (("Υπολογισμός φέροντα: κολόνες, δοκάρια, βάσεις",lambda: window._design_structure()),
                     ("Πρόταση φέροντος οργανισμού από τους τοίχους",lambda: window._propose_frame()),
                     ("Στοιχεία κτιρίου για στατική…",lambda: window._edit_structural_settings()),
                     ("Στατική ανάλυση φέροντος οργανισμού…",lambda: window._show_structural_analysis()),
                     ("Οπλισμός πλακών…",lambda: window._show_slabs())):
        a=QAction(text,window); a.triggered.connect(lambda _=False,r=run: r()); structure_menu.addAction(a)
    foundation_layer=QAction("Θεμελίωση στο 3D",window); foundation_layer.setCheckable(True); foundation_layer.setChecked(True)
    foundation_layer.toggled.connect(lambda on: window._set_layer_visible("foundation",on))
    structure_menu.addAction(foundation_layer); window.view_menu.addAction(foundation_layer); window._foundation_layer_action=foundation_layer
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
    from archforge.mep.drainage import POINT_TYPES as DRAIN
    drainage=QMenu("Αποχετεύσεις",mep_menu); mep_menu.addMenu(drainage)
    for key,(label,_l) in DRAIN.items():
        a=QAction(label,window)
        a.triggered.connect(lambda _=False,k=key,l=label: window._start_site_tool(f"drain_{k}",f"{l}: κλικ στην κάτοψη — η αποχέτευση ξαναχαράζεται αυτόματα, Esc για τέλος"))
        drainage.addAction(a)
    window._mockup_drainage_menu=drainage
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
    drain_layer=QAction("Αποχετεύσεις στο 3D",window); drain_layer.setCheckable(True); drain_layer.setChecked(True)
    drain_layer.toggled.connect(lambda on: window._set_layer_visible("drain",on))
    mep_menu.addAction(drain_layer); window.view_menu.addAction(drain_layer); window._drain_layer_action=drain_layer
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
    menus["Απεικόνιση"].addAction(ao)
    window._mockup_ao_action=ao
    sun_menu=QMenu("Ήλιος & ουρανός",menus["Απεικόνιση"]); menus["Απεικόνιση"].addMenu(sun_menu)
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

    from archforge.ui.workspace_layout import make_icon, popup_button, build_menu, install_workspace_layout
    ribbon=QToolBar("Εργαλεία σχεδίασης",window); ribbon.setObjectName("ribbon")
    ribbon.setMovable(True); ribbon.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); ribbon.setIconSize(QSize(30,30))

    def tool_action(text,tool,parent):
        a=QAction(text,parent); a.triggered.connect(lambda _=False,t=tool: window._set_active_tool(t)); return a
    for label,tool,icon,tip in (("Επιλογή","select","select","Κλικ σε αντικείμενο: επιλογή · σύρε τις λαβές για αλλαγή"),
                                ("Τοίχος","wall","wall","Σύρε από γωνία σε γωνία · Shift = ελεύθερη γωνία · Esc = ακύρωση")):
        a=tool_action(label,tool,window); a.setIcon(make_icon(icon)); a.setToolTip(tip); ribbon.addAction(a)
    # One menu for what goes into / along the walls: doors, windows, openings, stairs, kitchen, structure.
    elements=QMenu("Στοιχεία",window); window._mockup_elements_menu=elements
    for text,tool in (("Πόρτα","door"),("Παράθυρο","window"),("Άνοιγμα","opening_rect")):
        elements.addAction(tool_action(text,tool,elements))
    elements.addSeparator()
    circulation=QMenu("Σκάλα / Ράμπα",elements); elements.addMenu(circulation)
    for text,t in (("Σκάλα","stair"),("Ράμπα","ramp")):
        circulation.addAction(tool_action(text,t,circulation))
    # Explicit stair type; the wheel/Tab still switch while placing.
    types=QMenu("Τύπος σκάλας",circulation); circulation.addMenu(types)
    window._mockup_circulation_menu=circulation; window._mockup_stair_type_menu=types
    for text,layout in (("Αυτόματη",None),("Ευθεία","straight"),("Γ (L)","l"),("Π (U)","u"),("Σπιράλ","spiral")):
        item=QAction(text,types)
        item.triggered.connect(lambda _=False,l=layout: window._choose_stair_layout(l))
        types.addAction(item)
    kitchen=QMenu("Κουζίνα",elements); elements.addMenu(kitchen); window._mockup_kitchen_menu=kitchen
    def fill_kitchen():
        # The kitchen catalogue is built with the library panel; fill on first open.
        if kitchen.actions():
            return
        for name in getattr(window,"_kitchen_item_names",()):
            a=QAction(name,kitchen); a.triggered.connect(lambda _=False,n=name: window._place_kitchen_item(n)); kitchen.addAction(a)
    kitchen.aboutToShow.connect(fill_kitchen); window._fill_kitchen_menu=fill_kitchen
    elements.addMenu(window._roof_menu)
    pergola=QMenu("Πέργκολα",elements); elements.addMenu(pergola); window._mockup_pergola_menu=pergola
    for text,mat in (("Ξύλινη",'timber'),("Αλουμινίου",'aluminium')):
        a=QAction(text,pergola)
        a.triggered.connect(lambda _=False,m=mat,t=text: window._start_site_tool(f"pergola_{m}",f"Πέργκολα {t.lower()}: σύρε το ορθογώνιο στην κάτοψη (πλευρά σε τοίχο = στερεώνεται εκεί), Esc για τέλος"))
        pergola.addAction(a)
    menus["Κατασκευή"].addMenu(pergola)
    # Railings: one entry per type (click the corners), and the railing of a stair (click the stair).
    from archforge.architecture.railings import TYPES as RAILINGS
    railing=QMenu("Κάγκελα",elements); elements.addMenu(railing); window._mockup_railing_menu=railing
    for key,spec in RAILINGS.items():
        a=QAction(spec["label"],railing); a.triggered.connect(lambda _=False,k=key: window._start_railing_tool(k)); railing.addAction(a)
    railing.addSeparator()
    a=QAction("Κάγκελο σκάλας (κλικ σε σκάλα)",railing)
    a.triggered.connect(lambda: window._start_site_tool("railingstair_balusters","Κάγκελο σκάλας: κλικ πάνω στη σκάλα — μπαίνει στις ελεύθερες πλευρές, Esc για τέλος"))
    railing.addAction(a)
    menus["Κατασκευή"].addMenu(railing)
    # Structure: columns, beams, footings as one submenu.
    structural=QMenu("Δομικά: κολόνες, δοκάρια, βάσεις",elements); elements.addMenu(structural)
    window._mockup_structural_submenu=structural
    structural.addAction(tool_action("Κολώνα","structural_column",structural))
    structural.addAction(tool_action("Δοκός","structural_beam",structural))
    footings=QAction("Βάσεις (πέδιλα, συνδετήριες) — υπολογισμός φέροντα",structural)
    footings.triggered.connect(lambda: window._design_structure()); structural.addAction(footings)
    button=QToolButton(ribbon); button.setText("Στοιχεία"); button.setToolTip("Πόρτες, παράθυρα, ανοίγματα, σκάλες, κουζίνα, δομικά")
    button.setIcon(make_icon("elements"))
    button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup); button.setMenu(elements)
    button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    ribbon.addWidget(button); window._mockup_elements_button=button; window._mockup_circulation_button=button
    for label,tool in (("Γλυπτική","sculpt"),("Υλικά","materials")):
        a=QAction(make_icon(tool),label,window)
        a.setToolTip("Γλυπτική: πλάσε την επιφάνεια με το ποντίκι (δεξί κλικ: εργασία, ροδέλα: πινέλο)" if tool=="sculpt" else "Υλικό στο επιλεγμένο αντικείμενο")
        if tool=="sculpt": a.triggered.connect(lambda _=False: window.sculpt_action.toggle())
        else: a.triggered.connect(window._open_selected_materials)
        ribbon.addAction(a)
    # Reuse the proven Sculpt controls from the original toolbar. Hiding the
    # legacy toolbar must not hide access to brush operation/radius.
    # Reuse the isolated semantic Kitchen command already owned by MainWindow.
    # Do not duplicate generation logic in the mockup shell.
    # Sculpt operation and brush size live in the mouse menu (right click while
    # sculpting; the wheel sets the brush) — not on the ribbon.
    # Automatic floors / flat roof / site: one menu, so the bar stays narrow on a laptop.
    auto=QMenu("Αυτόματα",window); window._mockup_auto_menu=auto
    auto.addMenu(window._roof_menu)                       # roofs: tiled (auto / forms), flat, attic ceiling
    auto.addSeparator()
    auto_floor=QAction("Δάπεδα (αυτόματα)",window); auto_floor.triggered.connect(window._create_auto_floors); auto.addAction(auto_floor)
    flat_roof=QAction("Δώμα (αυτόματα)",window); flat_roof.triggered.connect(window._create_flat_roofs); auto.addAction(flat_roof)
    window._mockup_auto_floor_action=auto_floor
    terrain=QAction("Έδαφος",window); terrain.triggered.connect(window._create_terrain); auto.addAction(terrain)
    window._mockup_terrain_action=terrain
    window._mockup_flat_roof_action=flat_roof
    auto_button=QToolButton(ribbon); auto_button.setText("Αυτόματα"); auto_button.setToolTip("Δάπεδα, δώμα, έδαφος")
    auto_button.setIcon(make_icon("auto"))
    auto_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup); auto_button.setMenu(auto)
    auto_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    ribbon.addSeparator(); ribbon.addWidget(auto_button)
    window.addToolBar(Qt.TopToolBarArea,ribbon)

    # Second row, three bars the human can drag apart (or float, or hide):
    # storey · view (Προβολή ▾ / Στυλ ▾ popups + camera presets) · grid and snapping.
    floor_bar=QToolBar("Όροφος",window); floor_bar.setObjectName("floor_bar"); floor_bar.setIconSize(QSize(22,22))
    floor_bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    add_floor=QAction(make_icon("floor_add"),"Όροφος",window); add_floor.setToolTip("Νέος όροφος πάνω από τον τελευταίο")
    add_floor.triggered.connect(window._add_floor_level); floor_bar.addAction(add_floor)
    window._mockup_add_floor_action=add_floor
    floor_bar.addWidget(QLabel(" Σχεδιάζω στο: ")); _adopt(floor_bar,window.floor_selector)
    camera=QToolBar("Προβολή",window); camera.setObjectName("camera"); camera.setMovable(True)
    camera.setIconSize(QSize(22,22)); camera.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    window._mockup_camera_actions={}
    for label,mode,icon,tip in (("Πάνω","top","top","3D από πάνω"),("Πρόσοψη","front","front","3D: πρόσοψη"),
                                ("Πλάγια","side","side","3D: πλάγια όψη"),("3D","orbit","orbit","3D προοπτική — σύρε για περιστροφή")):
        a=QAction(make_icon(icon),label,window); a.setToolTip(tip)
        a.triggered.connect(lambda _=False,m=mode: window._set_pbr_camera(m)); camera.addAction(a)
        window._mockup_camera_actions[label]=a
    snap_bar=QToolBar("Κάνναβος & έλξη",window); snap_bar.setObjectName("snap_bar")
    grid=QCheckBox("Κάνναβος"); grid.setChecked(True); grid.setToolTip("Γραμμές κανάβου στην κάτοψη")
    grid.toggled.connect(window.plan_view.set_grid_visible); snap_bar.addWidget(grid)
    snap=QCheckBox("Έλξη"); snap.setToolTip("Το ποντίκι «κουμπώνει» σε γωνίες, άκρα και στον κάνναβο (Shift = ελεύθερα)")
    snap.setChecked(window.snap_action.isChecked()); snap.toggled.connect(window.snap_action.setChecked); window.snap_action.toggled.connect(snap.setChecked); snap_bar.addWidget(snap)
    snap_size=QComboBox(); snap_size.addItems(("0.10 m","0.05 m","0.25 m","0.50 m")); snap_size.setToolTip("Βήμα κανάβου και έλξης")
    snap_size.currentTextChanged.connect(lambda t: window.plan_view.set_grid_step(float(t.split()[0])))
    snap_bar.addWidget(QLabel("  Βήμα: ")); snap_bar.addWidget(snap_size)
    window._mockup_grid_check=grid; window._mockup_snap_check=snap; window._mockup_snap_size=snap_size
    # Own row: sharing the ribbon row squeezed Grid/Snap into the overflow.
    window.addToolBarBreak(Qt.TopToolBarArea)
    for bar in (floor_bar,camera,snap_bar): window.addToolBar(Qt.TopToolBarArea,bar)
    # Columns / beams / footings also as the first submenu of the Δομικά menu.
    first=window._structure_menu.actions()[0] if window._structure_menu.actions() else None
    window._structure_menu.insertMenu(first,window._mockup_structural_submenu)
    # The bars can be dragged anywhere (or floated) and hidden; Προβολή → Γραμμές εργαλείων brings them back.
    bars=QMenu("Γραμμές εργαλείων",window.view_menu); window.view_menu.addMenu(bars); window._toolbars_menu=bars
    for bar in (ribbon,floor_bar,camera,snap_bar):
        toggle=bar.toggleViewAction(); toggle.setText(bar.windowTitle()); toggle.setVisible(True); bars.addAction(toggle)
    lock=QAction("Κλείδωμα θέσης",window); lock.setCheckable(True)
    lock.toggled.connect(lambda on: [b.setMovable(not on) for b in (ribbon,floor_bar,camera,snap_bar)])
    bars.addSeparator(); bars.addAction(lock); window._toolbars_lock_action=lock
    window._mockup_ribbon=ribbon; window._mockup_camera_bar=camera; window._mockup_floor_bar=floor_bar; window._mockup_snap_bar=snap_bar

    # The real editors are mounted simultaneously, exactly where the supplied
    # prototype had PlanView and PBRViewport placeholders.
    right_tabs=QTabWidget()
    right_tabs.addTab(window.pbr_view,"3D Σκηνή")
    right_tabs.addTab(window.structural_view,"Στατικά")
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
    central_tabs.addTab(right_tabs,"3D / Στατικά")
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

    # Every view is live: camera presets, Doll House / Ortho overviews, and the
    # Section / Interior views that are dragged as a line in the 2D plan.
    # They open from «Προβολή ▾» on the view bar (no bottom strip eating height).
    view_specs=(
        ("3D Προοπτική",lambda: window._set_pbr_camera("orbit"),"orbit"),
        ("Πάνω",lambda: window._set_pbr_camera("top"),"top"),
        ("Πρόσοψη",lambda: window._set_pbr_camera("front"),"front"),
        ("Πλάγια",lambda: window._set_pbr_camera("side"),"side"),
        ("Κουκλόσπιτο (χωρίς στέγη)",lambda: window._set_pbr_camera("dollhouse"),"views"),
        ("Ορθογραφική",lambda: window._set_pbr_camera("ortho"),"views"),
        ("Τομή",lambda: window._start_view_line_tool("section"),"elements"),
        ("Εσωτερική Όψη",lambda: window._start_view_line_tool("camera"),"views"),
        ("Ρεαλιστική απεικόνιση",lambda: (window._set_render_style_from_workspace("pbr"),window._set_pbr_camera("orbit")),"style"),
        ("Περιήγηση",lambda: window._set_pbr_camera("eye"),"select"),
    )
    view_actions={label:run for label,run,_icon in view_specs}
    window._mockup_view_actions=view_actions
    first_camera=camera.actions()[0]
    view_popup=build_menu(window,"Προβολή",view_specs)
    window._mockup_view_popup=view_popup
    window._mockup_view_button=popup_button(camera,"Προβολή","views",view_popup,
                                            "Όλες οι προβολές: 3D, όψεις, κουκλόσπιτο, τομή, εσωτερική όψη, περιήγηση")
    # Styles = what the 3D scene really offers: material look with the sun at an hour, studio light, technical, glass.
    def style(technique,hour=False):
        def run():
            window._set_render_style_from_workspace(technique)
            if hour is not False: window.pbr_view.set_sun(hour)
            window._show_3d_view()
        return run
    style_specs=(
        ("Ρεαλιστικό (μεσημέρι)",style("pbr",11.0),"style"),
        ("Φυσικό φως (απόγευμα)",style("pbr",17.0),"style"),
        ("Βραδινό (δειλινό)",style("pbr",19.0),"style"),
        ("Στούντιο (ουδέτερο φως)",style("pbr",None),"views"),
        ("Τεχνικό (χωρίς σκιές)",style("technical"),"grid"),
        ("Γυάλινο (φαίνονται τα Η/Μ)",style("glass"),"materials"),
    )
    window._mockup_style_actions={label:run for label,run,_icon in style_specs}
    style_popup=build_menu(window,"Στυλ",style_specs,checkable=True)
    style_popup.actions()[0].setChecked(True)
    window._mockup_style_popup=style_popup
    from archforge.ui.object_menu import add_open_joinery_action
    add_open_joinery_action(window,style_popup,getattr(window,"view_menu",None))
    window._mockup_style_button=popup_button(camera,"Στυλ","style",style_popup,"Στυλ απεικόνισης του 3D: φως, ώρα, τεχνικό, γυάλινο")
    # Popups first, then a separator and the quick camera buttons.
    for w in (window._mockup_view_button,window._mockup_style_button):
        for a in camera.actions():
            if camera.widgetForAction(a) is w: camera.removeAction(a); camera.insertAction(first_camera,a)
    camera.insertSeparator(first_camera)

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
            if central_tabs.indexOf(right_tabs)<0: central_tabs.insertTab(1,right_tabs,"3D / Στατικά")
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
    project_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
    window.addDockWidget(Qt.LeftDockWidgetArea,project_dock)

    window.dock.setWindowTitle("Ιδιότητες")
    window.dock.setObjectName("approved_properties")
    window.addDockWidget(Qt.RightDockWidgetArea,window.dock)

    # Βοηθός: live proposals over the whole Document, tabbed with the Properties.
    assistant_dock=QDockWidget("Βοηθός",window)
    assistant_dock.setObjectName("approved_assistant")
    assistant_dock.setWidget(window._build_assistant_panel())
    assistant_dock.setAllowedAreas(Qt.LeftDockWidgetArea|Qt.RightDockWidgetArea)
    window.addDockWidget(Qt.RightDockWidgetArea,assistant_dock)
    window.tabifyDockWidget(window.dock,assistant_dock)
    window.dock.raise_()
    window._assistant_dock=assistant_dock
    # One task-dependent mouse menu in the plan and in the 3D views.
    for view in (window.plan_view,window.pbr_view,window.structural_view):
        view.marking_menu_window=window
    window._schedule_assistant_refresh()

    # Restore buttons/menu: Προβολή -> Παράθυρα.
    panels=window.view_menu.addMenu("Παράθυρα")
    for d in (project_dock,window.dock,assistant_dock):
        panels.addAction(d.toggleViewAction())
    # Workspace docks built before the shell (Library, AI, ...) lost their
    # toggles with the old View menu; keep them recoverable here too.
    extra=[d for d in getattr(window,"workspace_docks",()) if d not in (project_dock,window.dock,assistant_dock)]
    if extra:
        panels.addSeparator()
        for d in extra: panels.addAction(d.toggleViewAction())

    window.resizeDocks([project_dock],[270],Qt.Horizontal)
    window.resizeDocks([window.dock],[280],Qt.Horizontal)
    window.view=window.plan_view
    window._mockup_right_tabs=right_tabs
    window._approved_docks=(project_dock,window.dock,assistant_dock)
    window._central_tabs=central_tabs
    window._update_plan_title()

    views_menu=QMenu("3D Προβολές",window.view_menu); window.view_menu.addMenu(views_menu)
    for label,run,_icon in view_specs:
        a=QAction(label,views_menu); a.triggered.connect(lambda _=False,r=run: r()); views_menu.addAction(a)
    window._mockup_views_menu=views_menu

    simultaneous=QAction("Ταυτόχρονα 2D + 3D",window)
    simultaneous.setCheckable(True)
    simultaneous.setChecked(False)
    simultaneous.toggled.connect(set_simultaneous)
    window.view_menu.addSeparator()
    window.view_menu.addAction(simultaneous)
    window._simultaneous_action=simultaneous
    # Every bar and panel movable / floatable / closable; the layout is remembered (Προβολή → Επαναφορά διάταξης).
    # Layers panel and the Αρχιτεκτονικό / Φέρων / Η/Μ environments (view state, layers_panel.py).
    from archforge.ui.layers_panel import install_layers, install_menu
    workspace_bar,layers_dock=install_layers(window)
    window.tabifyDockWidget(assistant_dock,layers_dock); window.dock.raise_()
    install_workspace_layout(window,(ribbon,floor_bar,camera,snap_bar,workspace_bar),(project_dock,window.dock,assistant_dock,layers_dock))
    install_menu(window)
