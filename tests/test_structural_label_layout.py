"""Structural plan labels (columns, beams, footings, tie beams) do not overlap each other."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import (LABEL_MIN_SCALE, _axis_candidates, _corner_candidates, build_plan_frame,
                                       label_box, place_labels)

H = 3.0


def _frame_10x8():
    """10 × 8 m frame, columns on a 5 × 4 m grid, walls on every axis."""
    doc = Document(); st = CommandStack(doc); doc.levels['L1'] = H
    xs, ys = (0.0, 5.0, 10.0), (0.0, 4.0, 8.0)
    for x1, y1, x2, y2 in [(0, 0, 10, 0), (10, 0, 10, 8), (10, 8, 0, 8), (0, 8, 0, 0), (5, 0, 5, 8), (0, 4, 10, 4)]:
        st.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': H - .5, 'thickness': .2})))
    for x in xs:
        for y in ys:
            st.execute(AddEntity(Entity('structural_column', {
                'x': x, 'y': y, 'z': 0, 'width': .4, 'depth': .4, 'height': H, 'rotation': 0.0, 'role': 'structural',
                'construction': 'reinforced_concrete', 'section': 'rectangular', 'base_level': 'Ground', 'top_level': 'Unassigned'})))
    for a, b in [((0, y), (10, y)) for y in ys] + [((x, 0), (x, 8)) for x in xs]:
        st.execute(AddEntity(Entity('structural_beam', {
            'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': H - .5, 'width': .25, 'height': .5,
            'role': 'structural', 'construction': 'reinforced_concrete', 'section': 'rectangular', 'level': 'Ground'})))
    return doc, st


def _overlaps(labels):
    bad = []
    for i, (ta, aa, ala, sa) in enumerate(labels):
        for tb, ab, alb, sb in labels[i + 1:]:
            s = max(sa, sb)
            a = label_box(aa, ala, ta, s); b = label_box(ab, alb, tb, s)
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                bad.append((ta, tb))
    return bad


def test_ground_plan_labels_of_a_10x8_frame_do_not_overlap():
    from archforge.structure.design_all import design_structure
    doc, st = _frame_10x8()
    out = design_structure(doc, st)
    assert out['result'] is not None
    prims = [p for p in build_plan_frame(doc, layers=False).primitives if p.role in ('structural-label', 'footing-label')]
    texts = [dict(p.meta)['text'] for p in prims]
    assert any(t.startswith('Δ') for t in texts) and any(t.startswith('ΣΔ') for t in texts) and any(t.startswith('Π') for t in texts)
    labels = [(dict(p.meta)['text'], p.points[0], dict(p.meta)['align'], dict(p.meta)['min_scale']) for p in prims]
    assert not _overlaps(labels)
    # At the default plan zoom (55 px/m) nearly all of them show.
    shown = [q for q in labels if q[3] <= 55.0]
    assert len(shown) >= .9 * len(labels)


def test_dense_10x8_grid_labels_never_overlap_and_hide_when_zoomed_out():
    items = []
    for i in range(10):
        for j in range(8):
            items.append((f'Κ{i * 8 + j + 1} 40/40 8Ø16', _corner_candidates(i * 4.0, j * 4.0, .2, .2)))
    for i in range(10):
        for j in range(8):
            if i < 9:
                items.append((f'Δ{len(items)} 25/50', _axis_candidates((i * 4.0, j * 4.0), ((i + 1) * 4.0, j * 4.0), .175)))
                items.append((f'ΣΔ{len(items)} 25/50 4Ø14', _axis_candidates((i * 4.0, j * 4.0), ((i + 1) * 4.0, j * 4.0), .175, first_side=-1)))
            if j < 7:
                items.append((f'Δ{len(items)} 25/50', _axis_candidates((i * 4.0, j * 4.0), (i * 4.0, (j + 1) * 4.0), .175)))
    for i in range(10):
        for j in range(8):
            items.append((f'Π{i * 8 + j + 1} 1.00×1.00\nh0.50 Ø12/17.5', _corner_candidates(i * 4.0, j * 4.0, .5, .5, order=('sw', 'nw', 'se', 'ne'))))
    placed = place_labels(tuple(items))
    labels = [(t, a, al, s) for (t, _c), (a, al, s) in zip(items, placed)]
    assert not _overlaps(labels)
    assert all(s >= LABEL_MIN_SCALE for *_x, s in labels)
    # Columns first: every column label shows from the base zoom.
    assert all(s == LABEL_MIN_SCALE for t, _a, _al, s in labels if t.startswith('Κ'))
