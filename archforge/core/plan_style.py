"""How every primitive of the plan frame looks: one table for the screen and for every output (owner 28/10: «ο
σχεδιασμός είναι ένας· η εκτύπωση είναι μεταφραστής»).

``build_plan_frame`` (plan_scene.py) says *what* the plan shows; ``style`` says *how* each primitive is drawn —
colour, line width (metres, as the plan view draws it), dash, fill, stacking.  The plan view paints these with Qt
on screen; the PDF paints the same primitives with the same styles on paper.  No Qt here: colours are RGBA tuples,
dashes are names.

Screen-only states (selected, indicated) are arguments, so the printed drawing is simply the unselected one.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Tuple

RGBA = Tuple[int, int, int, int]

# Roles that exist only while working on screen: never printed or exported.
SCREEN_ONLY = frozenset({
    'preview', 'floor-underlay', 'align-guide', 'angle-arc', 'wall-move-opening', 'wall-move-arrow',
    'wall-move-label', 'stair', 'opening',
})
SCREEN_ONLY_PREFIXES = ('camera',)

CONTAINER_KINDS = ('room_floor', 'room_ceiling', 'room_foundation', 'room_roof', 'floor', 'room',
                   'pitched_roof', 'ceiling_joists', 'terrain')


def printable(p, entity_kind=None, has_symbol=False):
    """True when the primitive is part of the drawing (not a working aid of the screen).

    ``has_symbol``: the frame also draws a library symbol for this entity (then its footprint only picks)."""
    if p.role in SCREEN_ONLY or p.role.startswith(SCREEN_ONLY_PREFIXES):
        return False
    if p.kind == 'line' and p.role == 'model' and entity_kind == 'wall':
        return False                    # the wall's axis only picks; the cut region (wall-poche) is the wall
    if p.role == 'library-object' and has_symbol:
        return False                    # footprint for picking; the symbol (library-symbol) is the drawing
    return True


@dataclass(frozen=True)
class Style:
    color: RGBA = (0, 0, 0, 255)
    width: float = 0.0                  # metres of the plan (screen); paper mm = width × 1000 / 100 at 1:100
    dash: str = 'solid'                 # solid | dash | dashdot | dot
    cap: str = 'square'                 # square | flat
    join: str = 'bevel'                 # bevel | miter
    cosmetic: bool = False              # width in screen pixels (guides)
    fill: Optional[RGBA] = None         # None = not filled
    z: float = 0.0
    opacity: float = 1.0
    # Labels.
    text_color: RGBA = (55, 80, 65, 255)
    text_scale: float = 1.0             # × the default font size
    bold: bool = False


def _c(r, g, b, a=255):
    return (r, g, b, a)


def _pen(color, width=None):
    return Style(color=color, width=1.0 if width is None else width)


def label_style(p):
    """Colour, size and weight of a label primitive."""
    meta = dict(p.meta)
    s = Style(z=8.0)
    if p.role == 'section-label':
        s = replace(s, bold=True, text_scale=1.4, text_color=_c(200, 40, 40))
    if p.role == 'wall-move-label':
        text = str(meta.get('text', ''))
        s = replace(s, bold=True, text_scale=1.25, text_color=_c(210, 40, 40) if text.startswith('⚠') else _c(20, 110, 220))
    if p.role == 'dimension-label':
        s = replace(s, text_scale=.9, text_color=_c(30, 90, 170))
    if meta.get('layer_dim'):
        s = replace(s, opacity=.3)
    return s


def style(p, entity_kind=None, has_symbol=False, selected=False, indicated=False):
    """Style of a non-label primitive ``p`` (plan_scene.Primitive2D).

    ``entity_kind``: kind of ``p.entity_id`` in the Document (or None); ``has_symbol``: the frame also has a
    library symbol for that entity; ``selected`` / ``indicated``: screen states (False when printing)."""
    meta = dict(p.meta)
    role = p.role
    if role in ('section-line', 'section-arrow'):
        # Section mark: red dash-dot cut line, filled arrows towards where the section looks.
        s = _pen(_c(200, 40, 40), .06 if selected else .035)
        if p.kind == 'polygon':
            return replace(s, fill=_c(200, 40, 40), z=25.0)
        return replace(s, dash='dashdot' if role == 'section-line' else 'solid', z=25.0)
    preview = role == 'preview'; opening = role == 'opening'; room = role == 'derived-room'
    terrain = role in ('terrain', 'plant')
    # The storey below is drawn like structural context: faint grey.
    context = role in ('structural-context', 'floor-underlay')
    s = _pen(_c(150, 150, 150, 150) if context else
             (_c(180, 90, 20) if opening else (_c(40, 150, 70) if preview else (_c(95, 140, 60) if terrain else _c(45, 55, 65)))),
             .022 if context else (.06 if opening else (.04 if preview else .035)))
    if opening and meta.get('typed'):
        # Typed joinery draws its own symbol; keep the pick line light.
        s = _pen(_c(180, 90, 20, 110), .02)
    if preview and meta.get('fits') is False:
        s = _pen(_c(210, 40, 40), .05)
    if preview and str(meta.get('semantic', '')).startswith('stair-preview-'):
        # Steps of the stair being placed: thin, so the treads read (red when it does not fit).
        s = _pen(_c(210, 40, 40) if meta.get('fits') is False else _c(40, 150, 70), .015)
        if str(meta['semantic']).endswith(('hidden', 'walk-hidden')):
            s = replace(s, dash='dash')
    if role == 'library-symbol':
        s = _pen(_c(40, 45, 55), .012)
    if role in ('cabinet', 'cabinet-front'):
        s = _pen(_c(40, 45, 55), .012)
    if role in ('railing', 'railing-post'):
        s = _pen(_c(40, 45, 55), .01)
    if role in ('pipe-cold', 'pipe-hot'):
        s = _pen(_c(31, 111, 209) if role == 'pipe-cold' else _c(209, 48, 31), .035 if meta.get('diameter', 16) >= 20 else .02)
    if role == 'dimension':
        # Dimensions (architecture/dimensions.py): blue, the ticks and extension lines thinner.
        s = _pen(_c(20, 110, 220) if selected else _c(30, 90, 170), (.008 if meta.get('thin') else .012) * (2 if selected else 1))
    if role in ('roof-outline', 'roof-ridge'):
        s = _pen(_c(150, 70, 40), .02 if role == 'roof-outline' else .015)
        s = replace(s, dash='dash' if role == 'roof-outline' else 'dashdot')
    if role == 'cable':
        from archforge.mep.electrical import CABLE_COLORS
        s = _pen(_hex(CABLE_COLORS.get(meta.get('group'), '#e07a00')), .015)
        s = replace(s, dash={'wall': 'solid', 'floor': 'dot'}.get(meta.get('run'), 'dash'))
    if role in ('lv-cable', 'lv-box'):
        from archforge.mep.electrical import CABLE_COLORS
        s = _pen(_hex(CABLE_COLORS.get(meta.get('system'), '#0e9aa7')), .012 if role == 'lv-cable' else .008)
        if role == 'lv-cable':
            s = replace(s, dash='dashdot')
    if role == 'led-strip':
        s = replace(_pen(_c(232, 170, 20), .03), dash='dash', cap='flat')
    if role == 'manifold':
        s = _pen(_c(31, 111, 209) if meta.get('system') == 'cold' else _c(209, 48, 31), .012)
    if role == 'elec-box':
        s = _pen(_hex({'pull': '#c0262d', 'floor': '#0a8a5a'}.get(meta.get('box'), '#3a3f48')), .012)
    if role == 'electrical-point':
        s = _pen(_c(200, 120, 0), .02)
    if role == 'plumbing-point':
        s = _pen(_c(31, 90, 160), .02)
    if role in ('heat-supply', 'heat-return'):
        # Heating: supply red, return blue dashed, drawn at the owner's Ø.
        s = _pen(_c(200, 40, 30) if role == 'heat-supply' else _c(30, 80, 200), max(.012, float(meta.get('diameter', 16)) / 1500.))
        if role == 'heat-return':
            s = replace(s, dash='dash')
    if role in ('pool', 'pool-rim'):
        s = _pen(_c(20, 120, 170), .03 if role == 'pool-rim' else .015)
    if role == 'pool-zone':
        # Electrical safety zones around the basin (HD 60364-7-702): dash-dot, zone 2 fainter.
        s = replace(_pen(_c(200, 60, 140) if meta.get('zone') == 1 else _c(200, 60, 140, 110), .015), dash='dashdot')
    if role == 'pool-pipe':
        s = _pen(_c(70, 70, 70), max(.015, float(meta.get('diameter', 50)) / 2500.))
    if role == 'pool-plant':
        s = replace(_pen(_c(90, 90, 90), .02), dash='dash')
    if role == 'heat-loop':
        s = _pen(_c(225, 110, 40, 200), .012)
    if role in ('heat-manifold', 'heat-fitting', 'heating-point'):
        s = _pen(_c(170, 40, 40), .012)
    if role == 'duct':
        # Overhead element (under the ceiling): dashed, drawn at its true Ø.
        s = replace(_pen(_c(105, 115, 128, 200), float(meta.get('diameter', 125)) / 1000.), dash='dash', cap='flat')
    if role in ('drain', 'drain-node', 'drain-stack', 'drainage-point'):
        s = _pen(_c(150, 80, 30), max(.015, float(meta.get('diameter', 50)) / 2500.) if role == 'drain' else .015)
        if role == 'drain' and meta.get('kind') == 'branch':
            s = replace(s, dash='dash')
    if role == 'wall-move-opening':
        s = _pen(_c(180, 90, 20, 170), .07)
    if role == 'wall-move-arrow':
        s = replace(_pen(_c(20, 110, 220), .025), dash='dash')
    if role == 'align-guide':
        # Where to stop for right angles: a thin dashed line to the corner it lines up with.
        s = replace(_pen(_c(20, 110, 220), 1.2), cosmetic=True, dash='dash')
    if role == 'angle-arc':
        # Corner mark: blue on a magnet (90/45/15), grey for a free angle.
        s = _pen(_c(20, 110, 220) if meta.get('magnet') else _c(120, 120, 120), .02)
    if role == 'plot-boundary':
        # The plot's legal outline: dash-dot, like on the survey.
        s = replace(_pen(_c(170, 40, 40), .04), dash='dashdot')
    if role == 'contour':
        # Contour lines: thin brown, every 1 m (or the chosen step) a little stronger.
        z = float(meta.get('z', 0.)); major = abs(z - round(z)) < 1e-6
        s = _pen(_c(150, 110, 60, 200 if major else 120), .02 if major else .01)
    if role in ('footing', 'tie-beam'):
        # Below the floor: hidden lines.
        s = replace(_pen(_c(95, 95, 90), .015), dash='dash')
    if role == 'joist':
        s = replace(_pen(_c(150, 105, 45) if meta.get('ok', True) else _c(200, 40, 40), .02), dash='dash')
    if role == 'joists-area':
        s = _pen(_c(150, 105, 45, 120), .01)
    if role in ('vent-terminal', 'ventilation-point'):
        s = _pen(_c(70, 80, 95), .015)
    if role in ('wall-layer', 'wall-insulation'):
        s = _pen(_c(120, 110, 95) if role == 'wall-layer' else _c(200, 150, 40), .008)
        if role == 'wall-insulation':
            s = replace(s, dash='dash')
    if role in ('opening-symbol', 'opening-symbol-hidden'):
        s = _pen(_c(40, 45, 55), .018 if meta.get('style') == 'solid' else .01)
        if role == 'opening-symbol-hidden':
            s = replace(s, dash='dash')
    if role in ('worktop', 'worktop-cutout', 'sink-symbol', 'hob-symbol', 'hood'):
        # Derived parts of a cabinet run: worktop edge, cut-outs, sink bowl, hob zones; the hood is above (dashed).
        s = _pen(_c(40, 45, 55) if role == 'worktop' else _c(70, 80, 95), .016 if role == 'worktop' else .009)
        if role == 'hood':
            s = replace(s, dash='dash')
    if role == 'cabinet-wall':
        s = replace(_pen(_c(70, 80, 95), .01), dash='dash')
    if role == 'library-object' and has_symbol:
        # Footprint stays for picking; the symbol carries the drawing.
        s = _pen(_c(150, 160, 170, 90), .006)
    if role in ('drywall-ceiling', 'drywall-ceiling-step'):
        # Suspended ceiling: above the cut plane, dashed.
        s = replace(_pen(_c(70, 110, 150), .016 if role == 'drywall-ceiling' else .01), dash='dash')
    if role == 'stair':
        s = _pen(_c(0, 0, 0, 0), .01)       # pick area only: the symbol is drawn below
    if role.startswith('stair-'):
        s = _pen(_c(45, 55, 65), {'stair-opening': .03, 'stair-cut': .016, 'stair-walk': .012, 'stair-walk-hidden': .012}.get(role, .014))
        if role in ('stair-hidden', 'stair-walk-hidden'):
            s = replace(s, dash='dash')
    if role in ('slab-opening', 'slab-opening-cross'):
        # Void in the slab: thin cross; dashed when the void is in the slab above (roof only).
        s = _pen(_c(60, 65, 75), .018 if role == 'slab-opening' else .012)
        if meta.get('above'):
            s = replace(s, dash='dash')
    wall_line = p.kind == 'line' and role == 'model' and entity_kind == 'wall'
    if wall_line:
        # The wall itself is drawn by the cut region (wall-poche); its axis line only picks, as wide as the wall.
        s = replace(_pen(_c(20, 110, 220, 110) if selected else (_c(240, 140, 30, 90) if indicated else _c(0, 0, 0, 0)),
                         float(meta.get('thickness', .2))), cap='flat')
    if role == 'wall-poche':
        s = replace(_pen(_c(40, 45, 55), .02), join='miter')
    # Fill.
    fill = None
    if p.kind == 'polygon' and meta.get('islands'):
        fill = _c(205, 200, 190) if role == 'wall-poche' else _c(80, 160, 220, 40)
    elif p.kind == 'polygon':
        fill = (_c(160, 160, 160, 18) if context else
                (_c(90, 180, 120, 28) if room else (_c(150, 140, 125, 70) if role == 'site-path' else
                 (_c(255, 255, 255, 1) if role == 'library-object' else (_c(236, 230, 220, 120) if role == 'cabinet' else
                  (_c(0, 0, 0, 0) if role in ('cabinet-wall', 'joists-area') else (_c(70, 110, 150, 14) if role == 'drywall-ceiling' else
                   (_c(255, 255, 255, 90) if role == 'slab-opening' else (_c(255, 255, 255, 1) if role == 'stair' else _c(80, 160, 220, 40))))))))))
        if room:
            s = _pen(_c(110, 150, 120), .015)
    elif p.kind == 'ellipse':
        fill = _c(160, 160, 160, 14) if context else _c(170, 120, 210, 30)
    container = entity_kind in CONTAINER_KINDS
    z = (-30 if role == 'contour' else -20 if context else (-10 if room else (10 if opening else (20 if preview else
         (-5 if container else (-1 if role == 'wall-poche' else (1 if wall_line else 0)))))))
    s = replace(s, fill=fill, z=float(z))
    if indicated and not wall_line:
        s = replace(s, color=_c(240, 140, 30), width=.03, dash='solid', cap='square', join='bevel', cosmetic=False)
    if preview and p.kind == 'polygon' and meta.get('fits') is False:
        s = replace(s, fill=_c(210, 40, 40, 45))
    if preview and p.kind == 'polygon' and meta.get('semantic') == 'wall-body-preview':
        # The wall being drawn looks like a wall: its cut fill, a green edge (not yet placed).
        s = replace(s, fill=_c(205, 200, 190, 235), color=_c(40, 150, 70), width=.025, dash='solid', cap='square', join='miter')
    # Dim layer (Layers panel / environment): a faint reference under the work.
    if meta.get('layer_dim'):
        s = replace(s, opacity=.28, z=-30.0)
    return s


def _hex(code):
    code = code.lstrip('#')
    return (int(code[0:2], 16), int(code[2:4], 16), int(code[4:6], 16), 255)
