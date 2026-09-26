from __future__ import annotations

# Editable, data-driven object-context registry.
#
# Add/remove future commands here instead of rewriting the mouse handlers in
# PlanView or PBRViewport. "placement" controls the PBR marking-menu layout:
#   radial -> around the mouse pointer
#   panel  -> compact command strip above the radial menu
ACTIONS = {
    'properties': {
        'label': 'Properties',
        'views': {'plan', 'pbr'},
        'placement': 'radial',
    },
    'move': {
        'label': 'Move',
        'views': {'plan'},
        'placement': 'radial',
    },
    'stretch': {
        'label': 'Stretch',
        'views': {'plan'},
        'placement': 'radial',
    },
    'rotate': {
        'label': 'Rotate',
        'views': {'plan'},
        'placement': 'radial',
    },
    'delete': {
        'label': 'Delete',
        'views': {'plan', 'pbr'},
        'placement': 'radial',
    },
    'fit_view': {
        'label': 'Fit',
        'views': {'pbr'},
        'placement': 'radial',
    },
    'orbit_view': {
        'label': 'Orbit',
        'views': {'pbr'},
        'placement': 'radial',
    },
    'top_view': {
        'label': 'Top',
        'views': {'pbr'},
        'placement': 'panel',
    },
    'front_view': {
        'label': 'Front',
        'views': {'pbr'},
        'placement': 'panel',
    },
    'side_view': {
        'label': 'Side',
        'views': {'pbr'},
        'placement': 'panel',
    },
    'iso_view': {
        'label': 'ISO 30°',
        'views': {'pbr'},
        'placement': 'panel',
    },
}

# Ordered object actions. None inserts a separator in list-style menus.
ENTITY_MENUS = {
    '*': ('properties', None, 'delete'),
    'wall': ('properties', 'move', 'stretch', 'rotate', None, 'delete'),
    'box': ('properties', 'move', 'stretch', 'rotate', None, 'delete'),
    'pod': ('properties', 'move', 'stretch', 'rotate', None, 'delete'),
    'door': ('properties', 'move', 'stretch', None, 'delete'),
    'window': ('properties', 'move', 'stretch', None, 'delete'),
    'floor': ('properties', 'move', None, 'delete'),
    'room': ('properties', 'move', None, 'delete'),
    'room_floor': ('properties', None, 'delete'),
    'room_roof': ('properties', None, 'delete'),
    'mesh': ('properties', None, 'delete'),
}

# View/navigation commands are real PBR operations, independent of entity kind.
PBR_NAVIGATION = (
    'fit_view',
    'orbit_view',
    'top_view',
    'front_view',
    'side_view',
    'iso_view',
)


def object_context_actions(kind: str, view: str):
    """Return menu entries allowed for one entity kind in one view.

    Each entry is either None (separator) or a mapping with id/label/placement.
    Unsupported actions are omitted rather than shown as fake controls.
    """
    kind = str(kind)
    view = str(view)
    action_ids = list(ENTITY_MENUS.get(kind, ENTITY_MENUS['*']))
    if view == 'pbr':
        action_ids.extend(PBR_NAVIGATION)

    out = []
    pending_separator = False
    for action_id in action_ids:
        if action_id is None:
            pending_separator = bool(out)
            continue
        spec = ACTIONS.get(action_id)
        if not spec or view not in spec.get('views', set()):
            continue
        if pending_separator and out and out[-1] is not None:
            out.append(None)
        pending_separator = False
        out.append({
            'id': action_id,
            'label': str(spec['label']),
            'placement': str(spec.get('placement', 'radial')),
        })
    while out and out[-1] is None:
        out.pop()
    return tuple(out)
