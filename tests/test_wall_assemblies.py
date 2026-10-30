"""The project's own wall assemblies (spec §3 step 2): new / copy / edit → all its walls, own type for one wall."""
import json

import pytest

from archforge.architecture import curved_wall as cw
from archforge.architecture import wall_assemblies as wa
from archforge.architecture.wall_types import indicative_u, label, layer_lines, layers, total_thickness, wall_types
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity

ROWS = [{"material": "cement_plaster", "thickness": 0.02}, {"material": "hollow_brick", "thickness": 0.09},
        {"material": "mineral_wool", "thickness": 0.10}, {"material": "hollow_brick", "thickness": 0.09},
        {"material": "cement_plaster", "thickness": 0.02}]


def _doc():
    doc = Document()
    return doc, CommandStack(doc)


def _wall(stack, y, wall_type="generic", thickness=0.2):
    w = Entity("wall", {"x1": 0.0, "y1": y, "x2": 4.0, "y2": y, "z": 0.0, "height": 2.7, "thickness": thickness,
                        "wall_type": wall_type})
    stack.execute(AddEntity(w))
    return w.id


def test_a_new_project_type_is_a_wall_type_like_the_built_in_ones_and_is_saved():
    doc, stack = _doc()
    key, cmd = wa.new_type_command(doc, "Διπλή με πετροβάμβακα 10", ROWS)
    stack.execute(cmd)
    assert key.startswith("proj_") and label(key, doc) == "Διπλή με πετροβάμβακα 10" and key in wall_types(doc)
    assert total_thickness(key, doc) == pytest.approx(0.32)
    assert [l.role for l in layers(key, doc)] == ["finish", "structure", "insulation", "structure", "finish"]
    wid = _wall(stack, 0.0, key, 0.32)
    assert len(layer_lines(doc.get(wid).params, key, 1, doc)) == 4
    assert indicative_u(key, doc) < indicative_u("brick_double_insulated")     # 10 cm wool against 5 cm XPS
    assert layers(key) == []                                                      # without its project: no layers
    reopened = Document.from_dict(json.loads(json.dumps(doc.to_dict())))
    assert [l.spec() for l in layers(key, reopened)] == [l.spec() for l in layers(key, doc)]
    stack.undo(); stack.undo()
    assert key not in wall_types(doc)


def test_built_in_types_are_copied_never_edited():
    doc, stack = _doc()
    with pytest.raises(ValueError):
        wa.edit_type_command(doc, "brick_double_insulated", name="x")
    key, cmd = wa.copy_type_command(doc, "brick_double_insulated")
    stack.execute(cmd)
    assert wa.layer_specs(doc, key) == wa.layer_specs(doc, "brick_double_insulated")
    assert "αντίγραφο" in label(key, doc)
    with pytest.raises(ValueError):
        wa.copy_type_command(doc, "generic")


def test_editing_a_project_type_moves_every_wall_of_it_in_one_undo():
    doc, stack = _doc()
    key, cmd = wa.new_type_command(doc, "Δική μου", ROWS)
    stack.execute(cmd)
    a, b = _wall(stack, 0.0, key, 0.32), _wall(stack, 3.0, key, 0.32)
    other = _wall(stack, 6.0, "brick_partition", 0.13)
    thicker = [dict(r) for r in ROWS]
    thicker[2]["thickness"] = 0.15
    stack.execute(wa.edit_type_command(doc, key, rows=thicker))
    assert [doc.get(i).params["thickness"] for i in (a, b, other)] == pytest.approx([0.37, 0.37, 0.13])
    stack.undo()
    assert [doc.get(i).params["thickness"] for i in (a, b)] == pytest.approx([0.32, 0.32])
    assert total_thickness(key, doc) == pytest.approx(0.32)


def test_one_wall_gets_its_own_type_and_the_others_keep_theirs():
    doc, stack = _doc()
    a, b = _wall(stack, 0.0, "brick_partition", 0.13), _wall(stack, 3.0, "brick_partition", 0.13)
    key, cmd = wa.own_type_command(doc, a, ROWS)
    stack.execute(cmd)
    assert doc.get(a).params["wall_type"] == key and doc.get(a).params["thickness"] == pytest.approx(0.32)
    assert doc.get(b).params["wall_type"] == "brick_partition"
    stack.undo()
    assert doc.get(a).params["wall_type"] == "brick_partition" and key not in wall_types(doc)


def test_a_curved_wall_takes_its_own_type_along_the_whole_arc():
    doc, stack = _doc()
    command, walls = cw.create_command(doc, (0, 0), (4, 0), (2, 1), n=4)
    stack.execute(command)
    key, cmd = wa.own_type_command(doc, walls[1].id, ROWS)
    stack.execute(cmd)
    assert {doc.get(w.id).params["wall_type"] for w in walls} == {key}


def test_bad_layers_and_keys_are_refused():
    doc, stack = _doc()
    for rows in ([], [{"material": "cardboard", "thickness": 0.1}], [{"material": "xps", "thickness": 0}],
                 [{"material": "xps", "thickness": 0.1, "role": "decor"}]):
        with pytest.raises(ValueError):
            wa.new_type_command(doc, "x", rows)
    wid = _wall(stack, 0.0)
    stack.execute(UpdateEntity(wid, {"wall_type": "proj_7"}))          # a project key: resolved with the project
    assert layers("proj_7", doc) == []
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(wid, {"wall_type": "cardboard"}))


def test_the_wall_menu_lists_the_projects_types_when_it_opens():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        key, cmd = wa.new_type_command(w.doc, "Δική μου", ROWS)
        w.stack.execute(cmd)
        w._mockup_wall_types_menu.aboutToShow.emit()
        assert key in w._mockup_wall_choices
        w._mockup_wall_choices[key].trigger()
        assert w.plan_view.controller.wall_choice == key
        w.stack.undo()
        w._mockup_wall_types_menu.aboutToShow.emit()
        assert key not in w._mockup_wall_choices
    finally:
        w.hide()
