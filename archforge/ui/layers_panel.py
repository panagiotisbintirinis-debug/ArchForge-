"""Layers panel and the working environments bar (Αρχιτεκτονικό / Φέρων / Η/Μ).

View state only (core/layers.py): nothing here goes through the CommandStack,
so switching environment or ticking a layer never adds an undo step.  The
state is kept in ``Document.view_layers`` and saved with the project.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (QCheckBox, QDockWidget, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton,
                               QScrollArea, QToolBar, QToolButton, QVBoxLayout, QWidget)

from archforge.core import layers as L

TIPS = {
    'arch': 'Τοίχοι, ανοίγματα, χώροι, έπιπλα· οι κολόνες αχνές και δεν πιάνουν κλικ, χωρίς ετικέτες στατικών και δίκτυα',
    'structure': 'Κολόνες, δοκοί, πέδιλα και ετικέτες πάνω σε αχνή, κλειδωμένη κάτοψη',
    'mep': 'Υδραυλικά, αποχέτευση, ηλεκτρολογικά, εξαερισμοί πάνω σε αχνή, κλειδωμένη κάτοψη',
}
# Tools that belong to an environment: picking one brings its environment forward.
STRUCTURE_TOOLS = ('structural_column', 'structural_beam')
ARCH_TOOLS = ('wall', 'door', 'window', 'opening_rect', 'opening_arch', 'stair', 'ramp', 'component')
MEP_PREFIXES = ('plumb_', 'elec_', 'drain_', 'vent_', 'mep_')


# --------------------------------------------------------------------------- switching
def set_workspace(window, name, announce=True):
    if L.workspace(window.doc) == name and L.layers_active(window.doc):
        return
    L.set_workspace(window.doc, name)
    _after_change(window)
    if announce:
        window.statusBar().showMessage(f'Περιβάλλον: {L.WORKSPACES[name]} — {TIPS[name]}', 6000)


def _after_change(window):
    # A selection that just became hidden or locked is let go (selection is view state too).
    keep = [eid for eid in window.doc.selection if L.editable(window.doc, eid)]
    if keep != list(window.doc.selection):
        window.doc.select(keep)
    refresh(window)
    window._redraw_views(all_views=True)
    window.refresh_inspector()


def refresh(window):
    """Bring the environment buttons, the tools row and the panel's ticks in step with the Document."""
    ws = L.workspace(window.doc)
    for name, action in getattr(window, '_workspace_actions', {}).items():
        action.blockSignals(True); action.setChecked(name == ws); action.blockSignals(False)
    for name, actions in getattr(window, '_workspace_tools', {}).items():
        for action in actions:
            action.setVisible(name == ws)
    rows = getattr(window, '_layer_rows', {})
    states = L.layer_states(window.doc)
    for key, boxes in rows.items():
        for field, box in boxes.items():
            box.blockSignals(True); box.setChecked(states[key][field]); box.blockSignals(False)
    title = getattr(window, '_layers_title', None)
    if title is not None:
        title.setText(f'Περιβάλλον: <b>{L.WORKSPACES[ws]}</b>')


def _set(window, key, field, value):
    L.set_layer_state(window.doc, key, **{field: value})
    _after_change(window)


def _solo(window, key):
    L.solo_layer(window.doc, key)
    _after_change(window)
    window.statusBar().showMessage(f'Μόνο: {L.LAYERS[key]}', 4000)


def _reset(window):
    L.reset_workspace(window.doc)
    _after_change(window)


# --------------------------------------------------------------------------- inspector / refusals
def inspector_lock(window):
    """A selected object on a locked layer shows its properties but cannot be changed."""
    dock = getattr(window, 'dock', None)
    panel = dock.widget() if dock is not None else None
    if panel is None:
        return
    sel = list(window.doc.selection)
    locked = [eid for eid in sel if L.layers_active(window.doc) and eid in window.doc.entities
              and L.entity_state(window.doc, eid)['locked']]
    panel.setEnabled(not locked)
    if locked:
        e = window.doc.get(locked[0])
        label = L.LAYERS[L.entity_layer(e.kind, e.params)]
        window.statusBar().showMessage(f'Το layer «{label}» είναι κλειδωμένο — ξεκλείδωσέ το στο πάνελ Layers ή άλλαξε περιβάλλον', 6000)


def _wrap(window, name, before):
    original = getattr(window, name)

    def run(*args, **kwargs):
        before(*args, **kwargs)
        return original(*args, **kwargs)
    setattr(window, name, run)


def _tool_environment(window, tool, *_):
    tool = str(tool)
    ws = L.workspace(window.doc)
    if tool in STRUCTURE_TOOLS and ws != 'structure':
        set_workspace(window, 'structure')
    elif tool.startswith(MEP_PREFIXES) and ws != 'mep':
        set_workspace(window, 'mep')
    elif tool in ARCH_TOOLS and L.layer_state(window.doc, 'walls')['locked']:
        set_workspace(window, 'arch')


# --------------------------------------------------------------------------- building
def _panel(window):
    body = QWidget()
    outer = QVBoxLayout(body)
    title = QLabel(); window._layers_title = title
    outer.addWidget(title)
    switch = QHBoxLayout()
    for name, label in L.WORKSPACES.items():
        button = QPushButton(label); button.setToolTip(TIPS[name])
        button.clicked.connect(lambda _=False, n=name: set_workspace(window, n))
        switch.addWidget(button)
    outer.addLayout(switch)
    grid = QGridLayout(); grid.setHorizontalSpacing(6); grid.setVerticalSpacing(2)
    for col, text in enumerate(('Κατηγορία', 'Ορατό', 'Κλείδωμα', 'Αχνό', '')):
        head = QLabel(f'<b>{text}</b>'); grid.addWidget(head, 0, col)
    rows = {}
    tips = {'visible': 'Φαίνεται στην κάτοψη και στο 3D', 'locked': 'Φαίνεται αλλά δεν επιλέγεται και δεν αλλάζει',
            'dim': 'Αχνό, σαν υπόβαθρο'}
    for r, (key, label) in enumerate(L.LAYERS.items(), start=1):
        grid.addWidget(QLabel(label), r, 0)
        boxes = {}
        for c, field in enumerate(('visible', 'locked', 'dim'), start=1):
            box = QCheckBox(); box.setToolTip(tips[field])
            box.toggled.connect(lambda on, k=key, f=field: _set(window, k, f, on))
            grid.addWidget(box, r, c, alignment=Qt.AlignmentFlag.AlignHCenter)
            boxes[field] = box
        solo = QToolButton(); solo.setText('Μόνο αυτό'); solo.setToolTip('Μόνο αυτό το layer, τα άλλα κρυφά')
        solo.clicked.connect(lambda _=False, k=key: _solo(window, k))
        grid.addWidget(solo, r, 4)
        rows[key] = boxes
    outer.addLayout(grid)
    reset = QPushButton('Επαναφορά περιβάλλοντος'); reset.setToolTip('Τα layers όπως τα ορίζει το περιβάλλον')
    reset.clicked.connect(lambda: _reset(window)); outer.addWidget(reset)
    outer.addStretch(1)
    window._layer_rows = rows
    scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(body)
    return scroll


def _environment_bar(window):
    bar = QToolBar('Περιβάλλον', window); bar.setObjectName('workspace_bar')
    bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    bar.addWidget(QLabel(' Περιβάλλον: '))
    group = QActionGroup(bar); group.setExclusive(True)
    actions = {}
    for name, label in L.WORKSPACES.items():
        a = QAction(label, bar); a.setCheckable(True); a.setToolTip(TIPS[name]); group.addAction(a)
        a.triggered.connect(lambda _=False, n=name: set_workspace(window, n))
        bar.addAction(a); actions[name] = a
    bar.addSeparator()
    tools = {'arch': [], 'structure': [], 'mep': []}

    def add(ws, label, run, tip):
        a = QAction(label, bar); a.setToolTip(tip); a.triggered.connect(lambda _=False: run()); bar.addAction(a)
        tools[ws].append(a)
    add('structure', 'Κολόνα', lambda: window._set_active_tool('structural_column'), 'Κλικ στην κάτοψη για κολόνα')
    add('structure', 'Δοκός', lambda: window._set_active_tool('structural_beam'), 'Σύρε από κολόνα σε κολόνα')
    add('structure', 'Πρόταση φέροντος', lambda: window._propose_frame(), 'Κολόνες και δοκοί από τους τοίχους (ένα undo)')
    add('structure', 'Πέδιλα && υπολογισμός', lambda: window._design_structure(), 'Κολόνες, δοκοί, πέδιλα, συνδετήριες (ένα undo)')
    add('structure', 'Στατική', lambda: window._show_structural_analysis(), 'Στατική ανάλυση φέροντος οργανισμού')
    for attr, label in (('_mockup_plumbing_menu', 'Υδραυλικά'), ('_mockup_electrical_menu', 'Ηλεκτρολογικά'),
                        ('_mockup_drainage_menu', 'Αποχετεύσεις'), ('_mockup_ventilation_menu', 'Εξαερισμοί')):
        menu = getattr(window, attr, None)
        if menu is None:
            continue
        button = QToolButton(bar); button.setText(label + ' ▾'); button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        tools['mep'].append(bar.addWidget(button))
    window._workspace_actions = actions
    window._workspace_tools = tools
    return bar


def install_layers(window):
    """Environment bar + Layers panel; returns them so the shell lays them out with the others."""
    L.ensure_view_layers(window.doc)
    bar = _environment_bar(window)
    second_row = getattr(window, '_mockup_floor_bar', None)
    if second_row is not None:
        # First row, next to the drawing tools: the second row is full on a laptop screen.
        window.removeToolBarBreak(second_row)
        window.insertToolBar(second_row, bar)
        window.insertToolBarBreak(second_row)
    else:
        window.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
    dock = QDockWidget('Layers', window); dock.setObjectName('layers_panel')
    dock.setWidget(_panel(window))
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    bars_menu = getattr(window, '_toolbars_menu', None)
    if bars_menu is not None:
        toggle = bar.toggleViewAction(); toggle.setText(bar.windowTitle())
        first = bars_menu.actions()[4] if len(bars_menu.actions()) > 4 else None
        bars_menu.insertAction(first, toggle) if first is not None else bars_menu.addAction(toggle)
    lock = getattr(window, '_toolbars_lock_action', None)
    if lock is not None:
        lock.toggled.connect(lambda on: bar.setMovable(not on))
    window._layers_dock = dock
    window._workspace_bar = bar
    window._set_workspace = lambda name: set_workspace(window, name)
    _wrap(window, '_set_active_tool', lambda tool, *a, **k: _tool_environment(window, tool))
    _wrap(window, '_start_site_tool', lambda tool, *a, **k: _tool_environment(window, tool))
    for name in ('_propose_frame', '_design_structure'):
        _wrap(window, name, lambda *a, **k: _tool_environment(window, 'structural_column'))
    refresh(window)
    if hasattr(window, '_mark_clean'):
        window._mark_clean()
    return bar, dock


def install_menu(window):
    """Προβολή: the environments and the Layers panel, at the place kept for them."""
    menu = window.view_menu
    anchor = getattr(window, '_view_menu_workspaces_anchor', None)
    sub = QMenu('Περιβάλλον', menu)
    group = QActionGroup(sub); group.setExclusive(True)
    window._workspace_menu_actions = {}
    for name, label in L.WORKSPACES.items():
        a = QAction(label, sub); a.setCheckable(True); a.setToolTip(TIPS[name]); group.addAction(a)
        a.triggered.connect(lambda _=False, n=name: set_workspace(window, n))
        sub.addAction(a); window._workspace_menu_actions[name] = a
    sub.aboutToShow.connect(lambda: [a.setChecked(n == L.workspace(window.doc)) for n, a in window._workspace_menu_actions.items()])
    toggle = window._layers_dock.toggleViewAction(); toggle.setText('Layers')
    if anchor is not None:
        menu.insertMenu(anchor, sub)
        menu.insertAction(anchor, toggle)
    else:
        menu.addMenu(sub); menu.addAction(toggle)
    window._workspace_menu = sub


def on_project_replaced(window):
    """New / opened project: defaults for an old project, then everything in step."""
    L.ensure_view_layers(window.doc)
    refresh(window)
