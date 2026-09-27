from __future__ import annotations

# Editable, data-driven object-context registry.
#
# Add/remove future commands here instead of rewriting PlanView or PBRViewport.
ACTIONS = {
    'properties': {
        'label': 'Properties',
        'views': {'plan', 'pbr'},
        'placement': 'radial',
    },
    'move': {
        'label': 'Move',
        'views': {'plan', 'pbr'},
        'placement': 'radial',
    },
    'stretch': {
        'label': 'Stretch',
        'views': {'plan'},
        'placement': 'radial',
    },
    'rotate': {
        'label': 'Rotate',
        'views': {'plan', 'pbr'},
        'placement': 'radial',
    },
    'materials': {
        'label': 'Materials',
        'views': {'plan', 'pbr'},
        'placement': 'radial',
    },
    'delete': {
        'label': 'Delete',
        'views': {'plan', 'pbr'},
        'placement': 'radial',
    },
}

ENTITY_MENUS = {
    '*': ('properties', None, 'delete'),
    'wall': ('properties', 'materials', 'move', 'stretch', 'rotate', None, 'delete'),
    'box': ('properties', 'materials', 'move', 'stretch', 'rotate', None, 'delete'),
    'pod': ('properties', 'materials', 'move', 'stretch', 'rotate', None, 'delete'),
    'door': ('properties', 'move', 'stretch', None, 'delete'),
    'window': ('properties', 'move', 'stretch', None, 'delete'),
    'opening': ('properties', 'move', 'stretch', None, 'delete'),
    'mep_terminal': ('properties', 'move', None, 'delete'),
    'floor': ('properties', 'materials', 'move', None, 'delete'),
    'room': ('properties', 'move', None, 'delete'),
    'room_floor': ('properties', 'materials', None, 'delete'),
    'room_roof': ('properties', 'materials', None, 'delete'),
    'room_ceiling': ('properties', 'materials', None, 'delete'),
    'room_foundation': ('properties', 'materials', None, 'delete'),
    'stair': ('properties', 'materials', 'move', 'rotate', None, 'delete'),
    'ramp': ('properties', 'materials', 'move', 'rotate', None, 'delete'),
    'mesh': ('properties', 'materials', None, 'delete'),
}


def object_context_actions(kind: str, view: str):
    """Return only currently supported object actions for one view."""
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
            'placement': str(spec.get('placement', 'radial')),
        })
    while out and out[-1] is None:
        out.pop()
    return tuple(out)
