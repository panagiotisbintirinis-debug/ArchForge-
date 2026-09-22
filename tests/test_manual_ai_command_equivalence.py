import pytest
import copy
from archforge.core.model import Document, Entity
from archforge.core.commands import CommandStack
from archforge.core.interaction import (
    MoveTransaction,
    RotateTransaction,
    PodStretchTransaction,
)
from archforge.core.viewport import PointerController, PointerEvent
from archforge.architecture.ai_commands import ArchForgeAIClient


def create_baseline_document() -> Document:
    """Create a baseline document with walls, pods, and boxes for equivalence testing."""
    doc = Document()
    pod = Entity(
        kind="pod",
        params={
            "cx": 10.0,
            "cy": 10.0,
            "floor_level": 0.0,
            "diameter_x": 6.0,
            "diameter_y": 6.0,
            "height": 3.5,
            "rotation": 0.0,
        },
        id="pod_main",
        name="Main Pod",
    )
    wall = Entity(
        kind="wall",
        params={
            "x1": 0.0,
            "y1": 0.0,
            "z": 0.0,
            "x2": 8.0,
            "y2": 0.0,
            "height": 3.0,
            "thickness": 0.2,
        },
        id="wall_main",
        name="Main Wall",
    )
    box = Entity(
        kind="box",
        params={
            "x": 2.0,
            "y": 2.0,
            "z": 0.0,
            "width": 1.0,
            "depth": 1.0,
            "height": 2.0,
            "rotation": 0.0,
        },
        id="box_main",
        name="Main Box",
    )
    doc.add(pod)
    doc.add(wall)
    doc.add(box)
    return doc


def test_move_operation_manual_transaction_vs_ai_command_equivalence():
    """Manual MoveTransaction commit and AI move_entities execute on identical baselines produce identical serialized states."""
    doc_manual = create_baseline_document()
    stack_manual = CommandStack(doc_manual)
    tx = MoveTransaction(doc_manual, stack_manual, ["pod_main", "wall_main", "box_main"])
    tx.update_delta(dx=3.5, dy=-2.0, dz=1.0)
    tx.commit()

    doc_ai = create_baseline_document()
    stack_ai = CommandStack(doc_ai)
    ai_client = ArchForgeAIClient(doc_ai, stack_ai)
    res = ai_client.move_entities(["pod_main", "wall_main", "box_main"], dx=3.5, dy=-2.0, dz=1.0)
    assert res.success is True

    assert doc_manual.to_dict() == doc_ai.to_dict()
    stack_manual.undo()
    stack_ai.undo()
    assert doc_manual.to_dict() == doc_ai.to_dict()
    stack_manual.redo()
    stack_ai.redo()
    assert doc_manual.to_dict() == doc_ai.to_dict()


def test_pointer_controller_move_uses_transaction_and_matches_ai_state():
    """The real pointer move path must use MoveTransaction and converge with the public AI command."""
    doc_manual = create_baseline_document()
    stack_manual = CommandStack(doc_manual)
    doc_manual.selection = {"box_main"}
    controller = PointerController(doc_manual, stack_manual)
    controller.set_tool("move")

    controller.pointer_down(PointerEvent(2.0, 2.0))
    assert isinstance(controller.active, MoveTransaction)
    preview = controller.pointer_move(PointerEvent(3.5, 1.0, shift=True))
    assert preview.hud["dx"] == pytest.approx(1.5)
    assert preview.hud["dy"] == pytest.approx(-1.0)
    controller.pointer_up(PointerEvent(3.5, 1.0, shift=True))

    doc_ai = create_baseline_document()
    stack_ai = CommandStack(doc_ai)
    ai_client = ArchForgeAIClient(doc_ai, stack_ai)
    res = ai_client.move_entities(["box_main"], dx=1.5, dy=-1.0, dz=0.0)
    assert res.success is True
    assert doc_manual.to_dict() == doc_ai.to_dict()

    stack_manual.undo()
    stack_ai.undo()
    assert doc_manual.to_dict() == doc_ai.to_dict()
    stack_manual.redo()
    stack_ai.redo()
    assert doc_manual.to_dict() == doc_ai.to_dict()


def test_rotate_operation_manual_transaction_vs_ai_command_equivalence():
    """Manual RotateTransaction commit and AI rotate_entities execute produce identical states."""
    doc_manual = create_baseline_document()
    stack_manual = CommandStack(doc_manual)
    rot_tx = RotateTransaction(doc_manual, stack_manual, "pod_main", angle_increment=0.0)
    rot_tx.update_angle(45.0, snap=False)
    rot_tx.commit()

    doc_ai = create_baseline_document()
    stack_ai = CommandStack(doc_ai)
    ai_client = ArchForgeAIClient(doc_ai, stack_ai)
    res = ai_client.rotate_entities(["pod_main"], angle_deg=45.0)
    assert res.success is True

    assert doc_manual.to_dict() == doc_ai.to_dict()
    stack_manual.undo()
    stack_ai.undo()
    assert doc_manual.to_dict() == doc_ai.to_dict()
    stack_manual.redo()
    stack_ai.redo()
    assert doc_manual.to_dict() == doc_ai.to_dict()


def test_pod_vertical_stretch_manual_transaction_vs_ai_resize_equivalence():
    """Manual PodStretchTransaction height handle and AI resize_pod produce identical states."""
    doc_manual = create_baseline_document()
    stack_manual = CommandStack(doc_manual)
    tx = PodStretchTransaction(doc_manual, stack_manual, "pod_main", handle="height")
    tx.update(z=5.0)
    tx.commit()

    doc_ai = create_baseline_document()
    stack_ai = CommandStack(doc_ai)
    ai_client = ArchForgeAIClient(doc_ai, stack_ai)
    res = ai_client.resize_pod("pod_main", height=5.0)
    assert res.success is True

    assert doc_manual.get("pod_main").params == doc_ai.get("pod_main").params
    assert doc_manual.to_dict() == doc_ai.to_dict()
    stack_manual.undo()
    stack_ai.undo()
    assert doc_manual.to_dict() == doc_ai.to_dict()
    stack_manual.redo()
    stack_ai.redo()
    assert doc_manual.to_dict() == doc_ai.to_dict()


def test_box_rotation_manual_vs_ai_command_equivalence():
    """Manual RotateTransaction and AI rotate_entities on box produce identical states."""
    doc_manual = create_baseline_document()
    stack_manual = CommandStack(doc_manual)
    rot_tx = RotateTransaction(doc_manual, stack_manual, "box_main", angle_increment=0.0)
    rot_tx.update_angle(90.0, snap=False)
    rot_tx.commit()

    doc_ai = create_baseline_document()
    stack_ai = CommandStack(doc_ai)
    ai_client = ArchForgeAIClient(doc_ai, stack_ai)
    res = ai_client.rotate_entities(["box_main"], angle_deg=90.0)
    assert res.success is True

    assert doc_manual.to_dict() == doc_ai.to_dict()
    stack_manual.undo()
    stack_ai.undo()
    assert doc_manual.to_dict() == doc_ai.to_dict()
    stack_manual.redo()
    stack_ai.redo()
    assert doc_manual.to_dict() == doc_ai.to_dict()
