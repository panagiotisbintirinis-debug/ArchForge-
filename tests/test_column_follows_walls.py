"""Owner (2026-10-14): columns went to 2.70 instead of following the walls they stand on."""
from archforge.core.commands import CommandStack
from archforge.core.interaction import StructuralColumnPlaceTransaction
from archforge.core.model import Document, Entity
from archforge.structure.column_height import column_span
from archforge.structure.layout import _top_of


def _doc(levels, walls):
    doc = Document()
    doc.levels = dict(levels)
    for z, h, (x1, y1, x2, y2), extra in walls:
        doc.add(Entity("wall", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "z": z, "height": h,
                                "thickness": 0.25, **extra}))
    return doc


def test_column_on_wall_takes_wall_height_not_split_level():
    doc = _doc({"Ισόγειο": 0.0, "1ος όροφος": 1.40},
               [(0.0, 3.10, (0, 0, 6, 0), {}), (0.0, 3.10, (0, 0, 0, 5), {})])
    stack = CommandStack(doc)
    tx = StructuralColumnPlaceTransaction(doc, stack, 3.0, 0.0, z=0.0, snap_enabled=False, grid=None)
    eid = tx.commit()
    assert abs(doc.get(eid).params["height"] - 3.10) < 1e-9


def test_column_reads_sloped_wall_top_and_level_name():
    doc = _doc({"Ισόγειο": 0.0, "Δώμα": 3.0},
               [(0.0, 3.0, (0, 0, 4, 0), {"start_height": 2.0, "end_height": 4.0})])
    h, top = column_span(doc, 2.0, 0.0, 0.0)
    assert abs(h - 3.0) < 1e-9 and top == "Δώμα"


def test_basement_column_follows_basement_walls():
    doc = _doc({"Υπόγειο": -2.70, "Λάθος": -2.50, "Ισόγειο": 0.0},
               [(-2.70, 2.70, (0, 0, 5, 0), {}), (0.0, 3.0, (0, 0, 5, 0), {})])
    h, top = column_span(doc, 5.0, 0.0, -2.70)
    assert abs(h - 2.70) < 1e-9 and top == "Ισόγειο"


def test_free_column_without_walls_uses_next_level():
    doc = _doc({"Ισόγειο": 0.0, "1ος": 3.2}, [])
    assert column_span(doc, 1, 1, 0.0) == (3.2, "1ος")


def test_frame_top_ignores_split_level_below_wall_top():
    doc = _doc({"Ισόγειο": 0.0, "1ος όροφος": 1.40}, [(0.0, 3.0, (0, 0, 6, 0), {})])
    walls = [e for e in doc.entities.values()]
    assert abs(_top_of(doc, 0.0, walls) - 3.0) < 1e-9
    doc.levels["2ος"] = 3.0
    assert abs(_top_of(doc, 0.0, walls) - 3.0) < 1e-9
