"""What a stair is made of and what it carries — options of the stair itself (owner 14/10).

«Η σκάλα μπορεί να είναι διαφορετική, λεπτή, δηλαδή ξύλινη, μεταλλική — δεν είναι απαραίτητο να είναι
πλάκα» · «βάλε και επιλογή για κάγκελο … να ακολουθεί τη σκάλα» · κενό από κάτω για ντουλάπια.

``structure`` (stored on the stair, old stairs = ``solid``):

* ``solid``     — γεμάτη (κάθε σκαλί ως το δάπεδο), όπως ως τώρα;
* ``slab``      — πλάκα σκυροδέματος: κεκλιμένη πλάκα ``SLAB`` κάτω από τα σκαλιά, κενό από κάτω;
* ``timber``    — ξύλινη: πατήματα ``TREAD_TIMBER`` πάνω σε δύο πλαϊνά λουκέτα, χωρίς ρίχτια;
* ``steel``     — μεταλλική: λεπτά πατήματα σε δύο μεταλλικά λουκέτα;
* ``cantilever``— πρόβολα σκαλοπάτια πακτωμένα στον τοίχο της μίας πλευράς («κοινή πρακτική τελευταία»,
                  ιδιοκτήτης 14/10): χοντρό πάτημα ``TREAD_CANTILEVER``, ``EMBED`` μέσα στον τοίχο, τίποτα αλλού.

Sizes are typical practice (προς στατικό έλεγχο), not a design.
"""
from __future__ import annotations

STRUCTURES = {'solid': 'Γεμάτη (ως το δάπεδο)', 'slab': 'Πλάκα σκυροδέματος (κενό από κάτω)',
              'timber': 'Ξύλινη με λουκέτα', 'steel': 'Μεταλλική με λουκέτα',
              'cantilever': 'Πρόβολα σκαλοπάτια από τον τοίχο'}
SLAB = 0.15                  # waist slab, perpendicular to the pitch
TREAD_TIMBER = 0.045
TREAD_STEEL = 0.03
TREAD_CANTILEVER = 0.08
EMBED = 0.10
STRINGERS = {'sides': 'Δύο πλαϊνά', 'center': 'Ένα κεντρικό', 'three': 'Τρία', 'none': 'Κανένα'}
STRINGER_WIDTH = {'timber': 0.06, 'steel': 0.012}
STRINGER_DEPTH = {'timber': 0.28, 'steel': 0.25}

ROLE_NAMES = {'tread': 'Πάτημα', 'riser': 'Ρίχτι', 'edge': 'Πλευρές', 'bottom': 'Κάτω πλευρά',
              'slab': 'Πλάκα / κάτω πλευρά', 'stringer': 'Λουκέτα', 'landing': 'Πλατύσκαλο'}
DEFAULT_MATERIALS = {
    'solid': {'tread': 'marble_thassos', 'riser': 'marble_thassos', 'edge': 'concrete_smooth', 'bottom': 'concrete_smooth',
              'landing': 'marble_thassos'},
    'slab': {'tread': 'marble_thassos', 'riser': 'marble_thassos', 'slab': 'concrete_smooth', 'landing': 'marble_thassos'},
    'timber': {'tread': 'wood_oak', 'stringer': 'wood_oak', 'landing': 'wood_oak'},
    'steel': {'tread': 'wood_oak', 'stringer': 'steel_black', 'landing': 'wood_oak'},
    'cantilever': {'tread': 'wood_oak', 'landing': 'wood_oak'},
}


def cantilever_has_wall(doc, params):
    """Is there a wall of the storey along the side the cantilever steps are built into?"""
    from archforge.architecture.railings import _along_wall, stair_railing_lines
    try:
        lines = stair_railing_lines(params, cantilever_side(doc, params))
    except ValueError:
        return False
    return bool(lines) and all(_along_wall(doc, line, float(params['lower_z'])) for line in lines)


def cantilever_side(doc, params):
    """Side ('left' / 'right', going up) whose wall carries cantilever steps: the stored choice, else the
    side that runs along a wall of the storey, else left."""
    side = params.get('cantilever_side')
    if side in ('left', 'right'):
        return side
    if doc is not None:
        from archforge.architecture.railings import _along_wall, stair_railing_lines
        for s in ('left', 'right'):
            try:
                lines = stair_railing_lines(params, s)
            except ValueError:
                break
            if lines and _along_wall(doc, lines[0], float(params['lower_z'])):
                return s
    return 'left'


def structure(params):
    s = str(params.get('structure') or 'solid')
    return s if s in STRUCTURES else 'solid'


def has_space_under(params):
    """Free height under the stair (for cupboards): every structure but «γεμάτη»."""
    return structure(params) != 'solid'


def role_material_id(params, role):
    """The stair's material for a surface role: the human's choice, else the structure's default."""
    chosen = (params.get('surface_materials') or {}).get(role)
    if chosen:
        return chosen
    return DEFAULT_MATERIALS[structure(params)].get(role) or params.get('material_id')


def railing_command(doc, stair_id, choice, railing_type=None, changes=None):
    """One undo: the stair's railing choice (and other ``changes`` of the stair) with its child railings."""
    from archforge.architecture.railings import STAIR_RAILING_CHOICES, stair_railing_entities
    from archforge.core.commands import AddEntities, CompositeCommand, DeleteEntities, UpdateEntity
    if choice not in STAIR_RAILING_CHOICES:
        raise ValueError(f'unknown stair railing choice: {choice}')
    stair = doc.get(stair_id)
    old = [cid for cid in doc.children.get(stair_id, ()) if cid in doc.entities
           and doc.get(cid).kind == 'railing' and 'stair_side' in doc.get(cid).params]
    if railing_type is None:
        railing_type = doc.get(old[0]).params.get('railing_type', 'balusters') if old else 'balusters'
    changes = dict(changes or {}, railing=choice)
    commands = [UpdateEntity(stair_id, changes)]
    if old:
        commands.append(DeleteEntities(old))
    future = stair.clone(); future.params = dict(stair.params, **changes)     # the railings of the stair as it will be
    new = stair_railing_entities(doc, future, choice, railing_type)
    if new:
        commands.append(AddEntities(new))
    return CompositeCommand(commands, 'Κάγκελο σκάλας')


def railing_choice(doc, stair_id):
    p = doc.get(stair_id).params
    has = any(doc.get(cid).kind == 'railing' and 'stair_side' in doc.get(cid).params
              for cid in doc.children.get(stair_id, ()) if cid in doc.entities)
    return str(p.get('railing', 'none')) if has else 'none'


# --- cupboards under the stair (owner 14/10: «εφόσον η σκάλα έχει κενό από κάτω μπορούν να μπουν ντουλάπια») --

UNDER_MIN = 0.35              # low end of the first cupboard (its top slopes up from there)
UNDER_MAX = 2.10              # a tall cupboard
UNDER_GAP = 0.02
UNDER_MODULE = 0.60


def underside_offset(params):
    """Height of the stair's underside above its walking-line slope (z = base + s·pitch + offset)."""
    import math
    r, t = float(params['riser_height']), float(params['tread_depth'])
    kind = structure(params)
    if kind == 'slab':
        return -SLAB * math.sqrt(1 + (r / t) ** 2)
    if kind in ('timber', 'steel'):
        return r + 0.02 - STRINGER_DEPTH[kind]
    if kind == 'cantilever':
        return r - TREAD_CANTILEVER
    return None


def under_stair_cabinets(doc, stair):
    """Cupboards filling the free space under the stair's first flight, fronts to the open side.

    Each top follows the slope (``height`` at one end, ``height_end`` at the other, owner 14/10: «να
    ακολουθούν την κλίση της σκάλας»), a gap under the underside, at most ``UNDER_MAX``.  Returns new ``cabinet`` entities (children of the stair).
    """
    import math
    from archforge.architecture.railings import _along_wall, _flights, stair_railing_lines
    from archforge.architecture.stairs import candidate_from_params
    from archforge.core.model import Entity
    from archforge.kitchen.cabinets import default_params
    p = stair.params
    offset = underside_offset(p)
    if offset is None:
        raise ValueError('Η σκάλα είναι γεμάτη ως το δάπεδο — άλλαξε την κατασκευή (πλάκα, ξύλινη, μεταλλική, πρόβολα)')
    c = candidate_from_params(p)
    if c.layout == 'spiral':
        raise ValueError('Ντουλάπια κάτω από σπιράλ σκάλα: δεν υποστηρίζονται ακόμη')
    (sx, sy), (dx, dy), m, _k0, _end = _flights(c)[0]
    a = math.radians(c.angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    wdx, wdy = ca * dx - sa * dy, sa * dx + ca * dy                     # flight direction in the world
    nx, ny = -wdy, wdx                                                  # its left
    base = float(p['lower_z']); pitch = c.riser_height / c.tread_depth
    run = m * c.tread_depth
    s_min = max(0.0, (UNDER_MIN + UNDER_GAP - offset) / pitch)
    if s_min >= run - 0.30:
        raise ValueError('Κάτω από τη σκάλα δεν μένει ύψος για ντουλάπια')
    # Fronts to the side without a wall (right going up, unless the wall is there).
    lines = {side: stair_railing_lines(p, side)[0] for side in ('left', 'right')}
    face = 'left' if _along_wall(doc, lines['right'], base) and not _along_wall(doc, lines['left'], base) else 'right'
    depth = min(0.60, c.width - 0.05)
    sign = -1.0 if face == 'right' else 1.0                             # front direction = sign · left
    across = -sign * (c.width / 2 - depth / 2)                          # back against the far side
    rotation = math.degrees(math.atan2(wdy, wdx)) + (0.0 if face == 'right' else 180.0)
    count = max(1, round((run - s_min) / UNDER_MODULE))
    width = (run - s_min) / count
    ox, oy = c.origin
    lx, ly = ca * sx - sa * sy, sa * sx + ca * sy
    out = []
    for k in range(count):
        s0 = s_min + k * width
        low = min(UNDER_MAX, s0 * pitch + offset - UNDER_GAP)
        high = min(UNDER_MAX, (s0 + width) * pitch + offset - UNDER_GAP)
        if low < UNDER_MIN - 1e-6:
            continue
        mid = s0 + width / 2
        x = ox + lx + wdx * mid + nx * across
        y = oy + ly + wdy * mid + ny * across
        q = default_params('tall', x, y, base, rotation, width - 0.004)
        # Local +X runs up the flight when the fronts face right, down it when they face left.
        first, second = (low, high) if face == 'right' else (high, low)
        q.update(depth=depth, height=round(first, 3), height_end=round(second, 3), under_stair=1)
        out.append(Entity('cabinet', q, name='Ντουλάπι κάτω από τη σκάλα', parent_id=stair.id))
    return out


def under_stair_command(doc, stair_id):
    """One undo: the cupboards under the stair (replacing earlier ones of the same stair)."""
    from archforge.core.commands import AddEntities, CompositeCommand, DeleteEntities
    new = under_stair_cabinets(doc, doc.get(stair_id))
    old = [cid for cid in doc.children.get(stair_id, ()) if cid in doc.entities
           and doc.get(cid).kind == 'cabinet' and doc.get(cid).params.get('under_stair')]
    return CompositeCommand(([DeleteEntities(old)] if old else []) + [AddEntities(new)], 'Ντουλάπια κάτω από τη σκάλα'), new


class UnderStairCabinets:
    """Command: (re)fill the space under the stair as it is when the command runs — so it can follow a
    change of the stair in the same undo step (the «Σκάλα» window)."""

    def __init__(self, stair_id):
        self.stair_id = stair_id
        self.inner = None

    def do(self, doc):
        if self.inner is None:
            self.inner, _new = under_stair_command(doc, self.stair_id)
        self.inner.do(doc)

    def undo(self, doc):
        if self.inner is not None:
            self.inner.undo(doc)


def has_under_stair_cabinets(doc, stair_id):
    return any(doc.get(cid).kind == 'cabinet' and doc.get(cid).params.get('under_stair')
               for cid in doc.children.get(stair_id, ()) if cid in doc.entities)
