from __future__ import annotations

# Editable, data-driven object context menu registry.
#
# To add/remove a future command, edit ACTIONS and ENTITY_MENUS rather than
# rewriting PlanView or PBRViewport mouse handlers.
ACTIONS = {
    'properties': {
        'label': 'Open / Properties',
        'views': {'plan', 'pbr'},
    },
    'move': {
        'label': 'Move',
        'views': {'plan'},
    },
    'stretch': {
        'label': 'Stretch',
        'views': {'plan'},
    },
    'rotate': {
        'label': 'Rotate',
        'views': {'plan'},
    },
    'delete': {
        'label': 'Delete',
        'views': {'plan', 'pbr'},
    },
}

# Each entity kind owns an ordered list of action IDs.
# Use None to insert a visual separator.
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


def object_context_actions(kind: str, view: str):
    """Return menu entries allowed for one entity kind in one view.

    Each entry is either None (separator) or a mapping with id/label.
    Unsupported actions are omitted rather than shown as fake controls.
    """
    kind = str(kind)
    view = str(view)
    action_ids = ENTITY_MENUS.get(kind, ENTITY_MENUS['*'])
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
        })
    while out and out[-1] is None:
        out.pop()
    return tuple(out)
