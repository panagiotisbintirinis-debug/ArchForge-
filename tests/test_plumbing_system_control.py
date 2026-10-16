from types import SimpleNamespace

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep.plumbing import route_plumbing
from archforge.ui.plumbing_system_control import set_plumbing_system


def _point(stack, point_type, x, y, z=0.0):
    entity = Entity(
        "plumbing_point",
        {"x": x, "y": y, "z": z, "point_type": point_type},
        name=point_type,
    )
    stack.execute(AddEntity(entity))
    return entity


def _house(stack):
    for x1, y1, x2, y2 in (
        (0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0),
        (4, 0, 4, 6),
    ):
        stack.execute(AddEntity(Entity("wall", {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "z": 0.0, "height": 2.7, "thickness": 0.2,
        })))


def test_visible_system_choice_changes_authoritative_routing_and_is_undoable():
    doc = Document()
    stack = CommandStack(doc)
    _house(stack)
    supply = _point(stack, "water_supply", 0.3, 0.3)
    _point(stack, "solar_heater", 6.0, 2.0, 6.0)
    _point(stack, "basin", 5.0, 5.7)
    _point(stack, "wc", 6.5, 5.7)
    _point(stack, "shower", 7.7, 4.2)
    _point(stack, "kitchen_sink", 1.0, 5.7)
    _point(stack, "dishwasher", 1.7, 5.7)
    window = SimpleNamespace(doc=doc, stack=stack)

    before = route_plumbing(doc)
    assert before["report"]["system"] == "multilayer"
    assert before["manifolds"] == []

    assert set_plumbing_system(window, "manifold") is True
    assert supply.params["pipe_system"] == "manifold"
    after = route_plumbing(doc)
    assert after["report"]["system"] == "manifold"
    assert after["manifolds"]

    stack.undo()
    restored = route_plumbing(doc)
    assert restored["report"]["system"] == "multilayer"
    assert restored["manifolds"] == []


def test_system_choice_requires_supply_and_rejects_unknown_system():
    doc = Document()
    stack = CommandStack(doc)
    window = SimpleNamespace(doc=doc, stack=stack)
    assert set_plumbing_system(window, "manifold") is False
    with pytest.raises(ValueError, match="unsupported plumbing system"):
        set_plumbing_system(window, "unknown")
