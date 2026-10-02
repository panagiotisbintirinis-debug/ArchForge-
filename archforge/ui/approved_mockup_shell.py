from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QListWidget, QListWidgetItem, QTreeWidget,
    QTreeWidgetItem, QTabWidget, QVBoxLayout, QHBoxLayout, QSplitter, QToolBar,
    QToolButton, QCheckBox, QComboBox, QFrame, QSizePolicy, QDockWidget
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

MENUS=("Αρχείο","Επεξεργασία","Προβολή","Σχεδίαση","Κατασκευή","Δομικά","Υλικά","Sculpt","Κουζίνα","Μηχανολογικά","AI","Rendering","Βοήθεια")

def _card(title, widget):
    f=QFrame(); f.setObjectName("card")
    v=QVBoxLayout(f); v.setContentsMargins(0,0,0,5); v.setSpacing(0)
    t=QLabel(title); t.setObjectName("cardTitle"); v.addWidget(t); v.addWidget(widget)
    return f

def _project_panel(window):
    tabs=QTabWidget()
    tree=QTreeWidget(); tree.setHeaderHidden(True)
    root=QTreeWidgetItem(tree,["House Project 1"])
    ground=QTreeWidgetItem(root,["Ισόγειο"]); rooms=QTreeWidgetItem(ground,["Δωμάτια"])
    for n in ("Σαλόνι","Κουζίνα","Τραπεζαρία","Υπνοδωμάτιο 1","Μπάνιο 1"): QTreeWidgetItem(rooms,[n])
    for n in ("Τοίχοι","Ανοίγματα","Δομικά","Έπιπλα","Μηχανολογικά"): QTreeWidgetItem(ground,[n])
    for n in ("Όροφος 1","Στέγη","Έδαφος"): QTreeWidgetItem(root,[n])
    root.setExpanded(True); ground.setExpanded(True); rooms.setExpanded(True)
    tabs.addTab(tree,"Έργο"); tabs.addTab(QListWidget(),"Επίπεδα"); tabs.addTab(QListWidget(),"Υλικά")

    lib=QTabWidget(); page=QWidget(); v=QVBoxLayout(page); v.setContentsMargins(8,8,8,8)
    search=QLineEdit(); search.setPlaceholderText("Αναζήτηση κουζίνας..."); v.addWidget(search)
    items=QListWidget()
    for n in ("Κάτω ντουλάπι","Συρτάρια","Ντουλάπι νεροχύτη","Κρεμαστό ντουλάπι","Ψηλό ντουλάπι","Νησίδα","Εστία","Φούρνος","Ψυγείο","Πλυντήριο πιάτων"): items.addItem(n)
    search.textChanged.connect(lambda t:[items.item(i).setHidden(t.lower() not in items.item(i).text().lower()) for i in range(items.count())])
    v.addWidget(items)
    lib.addTab(QWidget(),"Δομικά"); lib.addTab(QWidget(),"Έπιπλα"); lib.addTab(page,"Κουζίνα"); lib.addTab(QWidget(),"Υλικά"); lib.setCurrentIndex(2)
    box=QWidget(); lay=QVBoxLayout(box); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
    lay.addWidget(_card("Έργο",tabs),5); lay.addWidget(_card("Βιβλιοθήκη",lib),6)
    window.project_tree=tree
    return box

def _thumb_strip(names):
    w=QListWidget(); w.setFlow(QListWidget.LeftToRight); w.setWrapping(False); w.setFixedHeight(92)
    for n in names: w.addItem(QListWidgetItem(n))
    return w

def install_approved_mockup_shell(window):
    """Use the supplied mockup structure, but mount the real ArchForge editors."""
    window.setWindowTitle("ArchForge"); window.resize(1536,1000); window.setStyleSheet(STYLE)

    # Replace the old menu presentation with the supplied mockup menu row.
    mb=window.menuBar(); mb.clear()
    for name in MENUS: mb.addMenu(name)

    # Existing development toolbars remain as command owners, but are hidden.
    for tb in window.findChildren(QToolBar): tb.hide()

    ribbon=QToolBar("Mockup Ribbon",window); ribbon.setMovable(False); ribbon.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    tool_specs=(
        ("Επιλογή","select"),("Τοίχος","wall"),("Πόρτα","door"),("Παράθυρο","window"),
        ("Άνοιγμα","opening_rect"),("Κλίμακα","stair"),("Δομικά","structural_column"),
        ("Sculpt","sculpt"),("Υλικά","materials")
    )
    for label,tool in tool_specs:
        a=QAction(label,window)
        if tool=="sculpt": a.triggered.connect(lambda _=False: window.sculpt_action.toggle())
        elif tool=="materials": a.triggered.connect(window._open_selected_materials)
        else: a.triggered.connect(lambda _=False,t=tool: window._set_active_tool(t))
        ribbon.addAction(a)
    ribbon.addSeparator()
    auto_floor=QAction("Auto Floor",window); auto_floor.triggered.connect(window._create_auto_floors); ribbon.addAction(auto_floor)
    flat_roof=QAction("Flat / Auto Roof",window); flat_roof.triggered.connect(window._create_flat_roofs); ribbon.addAction(flat_roof)
    window._mockup_auto_floor_action=auto_floor
    window._mockup_flat_roof_action=flat_roof
    spacer=QWidget(); spacer.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred); ribbon.addWidget(spacer)
    ribbon.addWidget(QLabel("Όροφος: ")); ribbon.addWidget(window.floor_selector)
    ribbon.addWidget(QLabel("  Απεικόνιση: ")); ribbon.addWidget(window.render_technique)
    window.addToolBar(Qt.TopToolBarArea,ribbon)

    camera=QToolBar("Mockup Camera",window); camera.setMovable(False); camera.addWidget(QLabel("Κάμερα: "))
    for label,mode in (("Top","top"),("Front","front"),("Side","side"),("3D","orbit")):
        a=QAction(label,window); a.triggered.connect(lambda _=False,m=mode: window._set_pbr_camera(m)); camera.addAction(a)
    camera.addSeparator()
    grid=QCheckBox("Grid"); grid.setChecked(True); camera.addWidget(grid)
    snap=QCheckBox("Snap"); snap.setChecked(window.snap_action.isChecked()); snap.toggled.connect(window.snap_action.setChecked); camera.addWidget(snap)
    snap_size=QComboBox(); snap_size.addItems(("0.10 m","0.05 m","0.25 m","0.50 m")); camera.addWidget(QLabel("  Snap: ")); camera.addWidget(snap_size)
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
    central_tabs=QTabWidget()
    central_tabs.addTab(plan_card,"2D Σχεδίαση")
    central_tabs.addTab(right_tabs,"3D / Structural")
    central_tabs.setCurrentIndex(0)

    def central_changed(index):
        if index==0:
            window.view=window.plan_view
            if hasattr(window.plan_view,"setFocus"): window.plan_view.setFocus()
        else:
            current=right_tabs.currentWidget()
            window.view=current if current in (window.pbr_view,window.structural_view) else window.pbr_view
            if window.view is window.pbr_view: window.pbr_view.activate()
            elif window.view is window.structural_view: window.structural_view.activate()
    central_tabs.currentChanged.connect(central_changed)

    strips=QHBoxLayout(); strips.setSpacing(6)
    views=_thumb_strip(("3D Προοπτική","Top","Front","Side","Εσωτερική Όψη","Render (PBR)","Walkthrough"))
    styles=_thumb_strip(("Ρεαλιστικό","Φυσικό φως","Βραδινό","Clay","Sketch"))

    center=QWidget(); cv=QVBoxLayout(center); cv.setContentsMargins(0,0,0,0); cv.setSpacing(6)
    cv.addWidget(central_tabs,1)
    window.setCentralWidget(center)

    # Optional simultaneous mode remains available. It is deliberately not
    # the default. The same real widgets are reparented; no duplicate model.
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

    for d in (project_dock,window.dock,views_dock):
        d.setFeatures(QDockWidget.DockWidgetClosable|QDockWidget.DockWidgetMovable|QDockWidget.DockWidgetFloatable)

    # Restore buttons/menu: Προβολή -> Παράθυρα.
    view_menu=None
    for action in mb.actions():
        if action.text()=="Προβολή":
            view_menu=action.menu(); break
    if view_menu is None: view_menu=mb.addMenu("Προβολή")
    panels=view_menu.addMenu("Παράθυρα")
    for d in (project_dock,window.dock,views_dock):
        panels.addAction(d.toggleViewAction())

    window.resizeDocks([project_dock],[270],Qt.Horizontal)
    window.resizeDocks([window.dock],[280],Qt.Horizontal)
    window.resizeDocks([views_dock],[120],Qt.Vertical)
    window.view=window.plan_view
    window._mockup_right_tabs=right_tabs
    window._approved_docks=(project_dock,window.dock,views_dock)
    window._central_tabs=central_tabs

    simultaneous=QAction("Ταυτόχρονα 2D + 3D",window)
    simultaneous.setCheckable(True)
    simultaneous.setChecked(False)
    simultaneous.toggled.connect(set_simultaneous)
    view_menu.addSeparator()
    view_menu.addAction(simultaneous)
    window._simultaneous_action=simultaneous
