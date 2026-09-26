from __future__ import annotations

from math import hypot
from typing import Dict, Tuple

# Editable property registry for the human object-properties dialog.
# Future entity types/properties can be added here without rewriting the dialog.
PROPERTY_FIELDS = {
    'wall': (
        {'id': 'length', 'label': 'Length', 'unit': 'm', 'minimum': 0.01, 'step': 0.10},
        {'id': 'height', 'label': 'Height', 'unit': 'm', 'minimum': 0.01, 'step': 0.10},
        {'id': 'thickness', 'label': 'Thickness', 'unit': 'm', 'minimum': 0.01, 'step': 0.01},
    ),
    'door': (
        {'id': 'width', 'label': 'Width', 'unit': 'm', 'minimum': 0.01, 'step': 0.05},
        {'id': 'height', 'label': 'Height', 'unit': 'm', 'minimum': 0.01, 'step': 0.05},
    ),
    'window': (
        {'id': 'width', 'label': 'Width', 'unit': 'm', 'minimum': 0.01, 'step': 0.05},
        {'id': 'height', 'label': 'Height', 'unit': 'm', 'minimum': 0.01, 'step': 0.05},
        {'id': 'sill', 'label': 'Sill Height', 'unit': 'm', 'minimum': 0.0, 'step': 0.05},
    ),
    'box': (
        {'id': 'width', 'label': 'Width', 'unit': 'm', 'minimum': 0.01, 'step': 0.05},
        {'id': 'depth', 'label': 'Depth', 'unit': 'm', 'minimum': 0.01, 'step': 0.05},
        {'id': 'height', 'label': 'Height', 'unit': 'm', 'minimum': 0.01, 'step': 0.05},
    ),
    'pod': (
        {'id': 'diameter_x', 'label': 'Width', 'unit': 'm', 'minimum': 0.01, 'step': 0.05},
        {'id': 'diameter_y', 'label': 'Depth', 'unit': 'm', 'minimum': 0.01, 'step': 0.05},
        {'id': 'height', 'label': 'Height', 'unit': 'm', 'minimum': 0.01, 'step': 0.05},
        {'id': 'shell_thickness', 'label': 'Shell Thickness', 'unit': 'm', 'minimum': 0.001, 'step': 0.01},
    ),
}


def property_fields(kind: str):
    return tuple(PROPERTY_FIELDS.get(str(kind), ()))


def property_values(entity) -> Dict[str, float]:
    p = entity.params
    values = {}
    for spec in property_fields(entity.kind):
        key = spec['id']
        if entity.kind == 'wall' and key == 'length':
            values[key] = hypot(float(p['x2']) - float(p['x1']), float(p['y2']) - float(p['y1']))
        else:
            values[key] = float(p[key])
    return values


def property_changes(entity, values: Dict[str, float]) -> Dict[str, float]:
    """Translate human dimensions back into authoritative entity parameters."""
    requested = {str(k): float(v) for k, v in values.items()}
    changes = {}
    allowed = {spec['id'] for spec in property_fields(entity.kind)}
    unknown = set(requested) - allowed
    if unknown:
        raise ValueError('unsupported property: ' + ', '.join(sorted(unknown)))

    p = entity.params
    if entity.kind == 'wall' and 'length' in requested:
        length = requested['length']
        if length <= 0:
            raise ValueError('wall length must be positive')
        dx = float(p['x2']) - float(p['x1'])
        dy = float(p['y2']) - float(p['y1'])
        old_length = hypot(dx, dy)
        if old_length <= 1e-12:
            raise ValueError('cannot resize a zero-length wall')
        ux, uy = dx / old_length, dy / old_length
        changes['x2'] = float(p['x1']) + ux * length
        changes['y2'] = float(p['y1']) + uy * length

    for key, value in requested.items():
        if key == 'length':
            continue
        changes[key] = value

    return changes
