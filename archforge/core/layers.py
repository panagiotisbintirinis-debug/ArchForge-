"""Layers and working environments (Αρχιτεκτονικό / Φέρων / Η/Μ) — view state only.

Every entity kind and every derived plan role belongs to one layer
(``entity_layer`` / ``primitive_layer``).  A layer is *visible* or not,
*locked* (drawn, never picked, never changed) and/or *dim* (faint).

An environment (workspace) is a preset of those states plus the tools that
come first; switching environment never touches the entities.

Where it lives: ``Document.view_layers`` — saved with the project (so a
project reopens the way the human left it), but deliberately outside the
undo history: it is how we *look* at the building, not the building.  The
undo snapshots (``_restore_document_state``) leave it alone, so Ctrl+Z never
flips a layer and a layer click never fills the undo stack.  An empty value
(old project, bare ``Document()``) means «no layer filtering»; the main
window fills in the defaults (Αρχιτεκτονικό) when it opens a project.
"""
from __future__ import annotations

import copy
from dataclasses import replace

# key -> label the human reads (order = order of the Layers panel)
LAYERS = {
    'walls': 'Τοίχοι',
    'openings': 'Ανοίγματα / κουφώματα',
    'rooms': 'Χώροι & ετικέτες',
    'slabs': 'Πλάκες / στέγες',
    'stairs': 'Σκάλες & κάγκελα',
    'furniture': 'Έπιπλα & βιβλιοθήκη',
    'kitchen': 'Κουζίνα',
    'sanitary': 'Είδη υγιεινής',
    'other': 'Λοιπά αντικείμενα',
    'structure': 'Φέρων οργανισμός (κολόνες / δοκοί)',
    'foundation': 'Θεμελίωση',
    'structural_labels': 'Ετικέτες στατικών',
    'plumbing': 'Υδραυλικά',
    'drainage': 'Αποχέτευση',
    'electrical': 'Ηλεκτρολογικά',
    'ventilation': 'Εξαερισμοί',
    'dimensions': 'Διαστάσεις',
    'site': 'Οικόπεδο / έδαφος',
    'underlay': 'Υπόβαθρο κάτω ορόφου',
    'cameras': 'Κάμερες',
}

KIND_LAYERS = {
    'wall': 'walls', 'pod': 'walls', 'organic_junction': 'walls', 'organic_opening_patch': 'walls',
    'arboreal_branch': 'walls',
    'door': 'openings', 'window': 'openings', 'opening': 'openings',
    'room': 'rooms', 'floor': 'slabs',
    'room_floor': 'slabs', 'room_ceiling': 'slabs', 'room_roof': 'slabs', 'pitched_roof': 'slabs',
    'slab_opening': 'slabs', 'ceiling_joists': 'slabs', 'drywall_ceiling': 'slabs',
    'room_foundation': 'foundation',
    'stair': 'stairs', 'ramp': 'stairs', 'railing': 'stairs',
    'library_object': 'furniture',
    'cabinet': 'kitchen', 'kitchen_part': 'kitchen',
    'box': 'other', 'mesh': 'other', 'mechanical_part': 'other', 'mechanical_joint': 'other',
    'mechanical_mount': 'other', 'price_list': 'other', 'section_line': 'other',
    'structural_column': 'structure', 'structural_beam': 'structure', 'structural_support': 'structure',
    'structural_load': 'structure',
    'plumbing_point': 'plumbing', 'mep_terminal': 'plumbing',
    'drainage_point': 'drainage',
    'electrical_point': 'electrical',
    'ventilation_point': 'ventilation',
    'terrain': 'site', 'plant': 'site', 'site_path': 'site',
    'camera': 'cameras',
}

# Derived plan primitives: the role decides (a label of a column is a «label», a footing is «foundation»).
ROLE_LAYERS = {
    'derived-room': 'rooms', 'derived-room-label': 'rooms',
    'structural-label': 'structural_labels', 'footing-label': 'structural_labels', 'joists-label': 'structural_labels',
    'structural-load': 'structural_labels', 'structural-load-label': 'structural_labels',
    'footing': 'foundation', 'tie-beam': 'foundation',
    'pipe-cold': 'plumbing', 'pipe-hot': 'plumbing', 'manifold': 'plumbing', 'plumbing-label': 'plumbing',
    'mep-conduit': 'plumbing',
    'drain': 'drainage', 'drain-label': 'drainage', 'drain-node': 'drainage', 'drain-stack': 'drainage',
    'cable': 'electrical', 'elec-box': 'electrical', 'electrical-label': 'electrical',
    'duct': 'ventilation', 'vent-terminal': 'ventilation', 'ventilation-label': 'ventilation',
    'terrain': 'site', 'terrain-label': 'site',
    'floor-underlay': 'underlay',
    'camera': 'cameras', 'camera-cone': 'cameras', 'camera-label': 'cameras',
}
# Live feedback of the tool in hand is never filtered.
UNLAYERED_ROLES = ('preview', 'wall-move-arrow', 'wall-move-label', 'wall-move-opening', 'angle-arc', 'angle-label')

# 3D payload ``layer`` tags (rendering/scene.py) -> layer.
SCENE_LAYERS = {'roof_structure': 'slabs', 'roof_tiles': 'slabs', 'foundation': 'foundation', 'mep': 'plumbing',
                'drain': 'drainage', 'elec': 'electrical', 'vent': 'ventilation'}

BATH_CATEGORIES = ('Μπάνιο',)


def entity_layer(kind, params=None):
    """Layer of an entity kind (library objects: bathroom ones go to «Είδη υγιεινής»)."""
    params = params or {}
    if kind == 'library_object' and params.get('asset'):
        try:
            from archforge.library.assets import load_asset
            record = load_asset(str(params['asset'])) or {}
        except Exception:
            record = {}
        if any(c in BATH_CATEGORIES for c in record.get('category', ())):
            return 'sanitary'
    if kind in ('structural_column', 'structural_beam') and str(params.get('role', 'structural')) != 'structural':
        return 'other'          # pergola posts / non-bearing members belong to the architecture
    if kind == 'mesh' and (params.get('metadata') or {}).get('semantic_type') == 'conduit':
        return 'plumbing'
    return KIND_LAYERS.get(kind, 'other')


def primitive_layer(doc, primitive):
    """Layer of one plan primitive, or None for tool feedback (never filtered)."""
    role = primitive.role
    if role in UNLAYERED_ROLES:
        return None
    if role in ROLE_LAYERS:
        return ROLE_LAYERS[role]
    eid = primitive.entity_id
    if eid and eid in doc.entities:
        e = doc.get(eid)
        return entity_layer(e.kind, e.params)
    return 'other'


# ------------------------------------------------------------------ environments
WORKSPACES = {'arch': 'Αρχιτεκτονικό', 'structure': 'Φέρων', 'mep': 'Η/Μ'}
ARCH_LAYERS = ('walls', 'openings', 'rooms', 'slabs', 'stairs', 'furniture', 'kitchen', 'sanitary', 'other', 'site')
MEP_LAYERS = ('plumbing', 'drainage', 'electrical', 'ventilation')
ON = {'visible': True, 'locked': False, 'dim': False}
OFF = {'visible': False, 'locked': False, 'dim': False}
UNDER = {'visible': True, 'locked': True, 'dim': True}     # faint, unpickable reference


def _preset(workspace):
    states = {key: dict(ON) for key in LAYERS}
    if workspace == 'arch':
        # Columns stay as a faint, unpickable reference (they matter for the plan); their
        # labels, the footings and the networks are out of the way.
        states['structure'] = dict(UNDER)
        for key in ('foundation', 'structural_labels') + MEP_LAYERS:
            states[key] = dict(OFF)
        states['cameras'] = dict(ON)
    elif workspace == 'structure':
        states['cameras'] = dict(OFF)
        for key in ARCH_LAYERS:
            states[key] = dict(UNDER)
        for key in ('furniture', 'kitchen', 'sanitary') + MEP_LAYERS:
            states[key] = dict(OFF)
    elif workspace == 'mep':
        states['cameras'] = dict(OFF)
        for key in ARCH_LAYERS + ('structure',):
            states[key] = dict(UNDER)
        for key in ('furniture', 'foundation', 'structural_labels'):
            states[key] = dict(OFF)
    return states


def default_view_layers():
    return {'workspace': 'arch', 'overrides': {}}


def ensure_view_layers(doc):
    """Defaults for a project saved before layers existed (or a fresh one)."""
    if not getattr(doc, 'view_layers', None) or doc.view_layers.get('workspace') not in WORKSPACES:
        doc.view_layers = default_view_layers()
    doc.view_layers.setdefault('overrides', {})
    return doc.view_layers


def layers_active(doc):
    return bool(getattr(doc, 'view_layers', None))


def workspace(doc):
    return (getattr(doc, 'view_layers', None) or {}).get('workspace', 'arch')


def layer_states(doc):
    """Effective state of every layer: the environment's preset + the human's own changes."""
    ws = workspace(doc)
    states = _preset(ws)
    for key, change in ((getattr(doc, 'view_layers', None) or {}).get('overrides', {}).get(ws, {}) or {}).items():
        if key in states:
            states[key].update({k: bool(v) for k, v in change.items() if k in ON})
    return states


def layer_state(doc, key):
    return layer_states(doc).get(key, dict(ON))


def set_workspace(doc, name):
    """Switch environment (view only; the human's changes per environment are kept)."""
    if name not in WORKSPACES:
        raise ValueError(f'unknown workspace: {name}')
    ensure_view_layers(doc)['workspace'] = name


def set_layer_state(doc, key, **state):
    """Change visible / locked / dim of one layer in the current environment."""
    if key not in LAYERS:
        raise ValueError(f'unknown layer: {key}')
    data = ensure_view_layers(doc)
    current = data['overrides'].setdefault(data['workspace'], {}).setdefault(key, {})
    current.update({k: bool(v) for k, v in state.items() if k in ON})


def solo_layer(doc, key):
    """«Μόνο αυτό»: this layer on and unlocked, every other one hidden."""
    for other in LAYERS:
        set_layer_state(doc, other, visible=(other == key), locked=False if other == key else layer_state(doc, other)['locked'],
                        dim=False if other == key else layer_state(doc, other)['dim'])


def reset_workspace(doc):
    """Forget the human's changes of the current environment."""
    data = ensure_view_layers(doc)
    data['overrides'].pop(data['workspace'], None)


def view_layers_to_dict(doc):
    return copy.deepcopy(getattr(doc, 'view_layers', None) or {})


def view_layers_from_dict(raw):
    """Tolerant reader: anything unknown is dropped (a damaged value → defaults)."""
    if not isinstance(raw, dict) or raw.get('workspace') not in WORKSPACES:
        return {}
    out = {'workspace': raw['workspace'], 'overrides': {}}
    for ws, layers in (raw.get('overrides') or {}).items():
        if ws not in WORKSPACES or not isinstance(layers, dict):
            continue
        out['overrides'][ws] = {key: {k: bool(v) for k, v in state.items() if k in ON}
                                for key, state in layers.items() if key in LAYERS and isinstance(state, dict)}
    return out


# ------------------------------------------------------------------ applying
def apply_to_frame(doc, frame):
    """Plan frame through the layers: hidden → out, locked → no entity id/handles, dim → marked faint."""
    if not layers_active(doc):
        return frame
    states = layer_states(doc)
    out = []
    for p in frame.primitives:
        key = primitive_layer(doc, p)
        if key is None:
            out.append(p)
            continue
        s = states[key]
        if not s['visible']:
            continue
        if s['locked'] and p.entity_id:
            p = replace(p, entity_id='')
        if s['dim']:
            p = replace(p, meta=tuple(p.meta) + (('layer_dim', True),))
        out.append(p)
    frame.primitives = out
    frame.handles = [h for h in frame.handles if editable(doc, h.entity_id)]
    return frame


def entity_state(doc, eid):
    e = doc.entities.get(eid)
    if e is None:
        return dict(ON)
    return layer_state(doc, entity_layer(e.kind, e.params))


def editable(doc, eid):
    """Visible and unlocked (True when layers are off or the id is unknown)."""
    if not layers_active(doc) or not eid or eid not in doc.entities:
        return True
    s = entity_state(doc, eid)
    return s['visible'] and not s['locked']


def apply_to_scene_objects(doc, objects):
    """3D payload objects through the layers (same rules as the plan)."""
    if not layers_active(doc):
        return list(objects)
    states = layer_states(doc)
    out = []
    for o in objects:
        eid = o.get('id') or ''
        if o.get('layer') in SCENE_LAYERS:
            key = SCENE_LAYERS[o['layer']]
        elif eid and eid in doc.entities:
            e = doc.get(eid)
            key = entity_layer(e.kind, e.params)
        else:
            out.append(o)
            continue
        s = states[key]
        if not s['visible']:
            continue
        if s['locked'] or s['dim']:
            o = dict(o)
            if s['locked'] and eid:
                o['render_part'] = o.get('render_part') or f'{eid}:locked'
                o['id'] = ''
            if s['dim']:
                material = dict(o.get('material') or {})
                material['opacity'] = min(float(material.get('opacity', 1.0)), 0.25)
                o['material'] = material
        out.append(o)
    return out


def _touched_ids(command):
    ids = []
    for name in ('eid', 'wall_id', 'entity_id'):
        value = getattr(command, name, None)
        if isinstance(value, str):
            ids.append(value)
    for name in ('ids', 'entity_ids'):
        value = getattr(command, name, None)
        if isinstance(value, (list, tuple, set)):
            ids.extend(str(v) for v in value)
    changes = getattr(command, 'changes', None)
    if isinstance(changes, dict) and all(isinstance(k, str) for k in changes) and type(command).__name__ == 'UpdateEntities':
        ids.extend(changes)
    for sub in getattr(command, 'commands', None) or ():
        ids.extend(_touched_ids(sub))
    return ids


def locked_layer_of(doc, command):
    """Label of a locked layer the command would change, or None."""
    if not layers_active(doc):
        return None
    states = layer_states(doc)
    for eid in _touched_ids(command):
        e = doc.entities.get(eid)
        if e is None:
            continue
        key = entity_layer(e.kind, e.params)
        if states[key]['locked']:
            return LAYERS[key]
    return None


class LayerLockedError(ValueError):
    pass


def check_command(doc, command):
    label = locked_layer_of(doc, command)
    if label:
        raise LayerLockedError(f'Το layer «{label}» είναι κλειδωμένο — ξεκλείδωσέ το στο πάνελ Layers ή άλλαξε περιβάλλον')
