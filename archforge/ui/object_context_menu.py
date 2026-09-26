from __future__ import annotations


def object_context_actions(kind: str):
    """Return only currently supported object actions for the human context menu."""
    kind = str(kind)
    actions = [('properties', 'Open / Properties')]

    if kind in ('wall', 'box', 'pod', 'floor', 'room', 'door', 'window'):
        actions.append(('move', 'Move'))
    if kind in ('wall', 'box', 'pod', 'door', 'window'):
        actions.append(('stretch', 'Stretch'))
    if kind in ('wall', 'box', 'pod'):
        actions.append(('rotate', 'Rotate'))

    actions.append(('separator', ''))
    actions.append(('delete', 'Delete'))
    return tuple(actions)
