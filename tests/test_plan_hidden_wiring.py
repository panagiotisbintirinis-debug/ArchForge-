"""Bots 06/11: the plan routed every cable on each change even with the electrical layers hidden (0,9 s per undo).
Skipping it must give the very same frame: what the layers hide is never drawn anyway."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core import layers as L
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame


def _house():
    doc = Document()
    for a, b in (((0, 0), (6, 0)), ((6, 0), (6, 5)), ((6, 5), (0, 5)), ((0, 5), (0, 0))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 2.7, 'thickness': 0.2}))
    doc.add(Entity('electrical_point', {'point_type': 'panel', 'x': 0.1, 'y': 1.0, 'z': 0.0}))
    doc.add(Entity('electrical_point', {'point_type': 'socket', 'x': 5.9, 'y': 1.0, 'z': 0.0}))
    return doc


def _shape(frame):
    return sorted((p.kind, p.role, tuple(map(tuple, p.points))) for p in frame.primitives)


def test_hidden_wiring_frame_is_the_same_and_shown_wiring_is_drawn():
    doc = _house()
    L.ensure_view_layers(doc)
    L.set_workspace(doc, 'arch')
    hidden = build_plan_frame(doc)
    assert not [p for p in hidden.primitives if p.role in ('cable', 'elec-box', 'electrical-label')]
    full = build_plan_frame(doc, layers=False)                    # everything computed (technical plan)
    assert [p for p in full.primitives if p.role == 'cable']
    L.set_workspace(doc, 'mep')
    shown = build_plan_frame(doc)
    assert [p for p in shown.primitives if p.role == 'cable']
    L.set_workspace(doc, 'arch')
    assert _shape(build_plan_frame(doc)) == _shape(hidden)
