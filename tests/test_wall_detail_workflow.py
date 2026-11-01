"""Owner 01/11: wall kinds expose editable layers both from Τοίχος ▾ and existing wall Ιδιότητες.

The construction library and CommandStack, not a dialog-local copy, remain authoritative.
"""
import json

import pytest

from archforge.core.commands import AddEntity
from archforge.core.model import Document, Entity


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow

    QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w.hide()


@pytest.fixture(autouse=True)
def no_unexpected_modal_warning(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _title, message: pytest.fail(str(message)))


def _wall(window, y, wall_type="generic", thickness=0.15):
    e = Entity("wall", {"x1": 0.0, "y1": y, "x2": 3.5, "y2": y, "height": 2.7,
                        "z": 0.0, "thickness": thickness, "wall_type": wall_type})
    window.stack.execute(AddEntity(e))
    return e.id


def test_each_type_in_wall_button_has_a_details_action(window, monkeypatch):
    from archforge.architecture.wall_types import WALL_TYPES

    chosen = []
    monkeypatch.setattr(window, "_open_wall_type_details", lambda key, wall_id=None: chosen.append((key, wall_id)))
    actions = window._mockup_wall_detail_actions
    assert set(WALL_TYPES) - {"generic"} <= set(actions)
    actions["isotex_hdiii_30_7"].trigger()
    assert chosen == [("isotex_hdiii_30_7", None)]


def test_existing_wall_properties_open_the_same_details(window, monkeypatch):
    from PySide6.QtWidgets import QDialog, QPushButton

    wid = _wall(window, 0)
    called = []
    monkeypatch.setattr(window, "_open_wall_type_details", lambda key, wall_id=None: called.append((key, wall_id)))

    def inspect(dialog):
        button = next(b for b in dialog.findChildren(QPushButton) if b.objectName() == "wallDetailsButton")
        button.click()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect)
    window._open_object_properties(wid)
    assert called == [("generic", wid)]


def test_a_layered_wall_derives_thickness_from_its_layers_in_properties(window, monkeypatch):
    from PySide6.QtWidgets import QDialog, QDoubleSpinBox

    wid = _wall(window, 0, "brick_partition", 0.13)

    def inspect(dialog):
        spins = dialog.findChildren(QDoubleSpinBox)
        derived = [s for s in spins if not s.isEnabled() and "στρώσεις" in s.toolTip()]
        assert len(derived) == 1 and derived[0].value() == pytest.approx(0.13)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect)
    window._open_object_properties(wid)


def test_isotex_finishes_are_chosen_from_the_library_and_keep_block_identity(window):
    from archforge.ui.wall_details_dialog import WallDetailsDialog
    from archforge.architecture.wall_types import layers, total_thickness
    from archforge.construction.isotex import take_off_isotex

    d = WallDetailsDialog(window, "isotex_hdiii_30_7")
    assert [r["material"] for r in d.layer_specs()][0] == "isotex_wood_cement"
    assert "cement_plaster" in d.available_material_ids()
    assert "gypsum_board" in d.available_material_ids()
    categories = {a.text() for a in d.add_outside.menu().actions()}
    assert {"Κονιάματα", "Ξηρά δόμηση", "Μονώσεις"} <= categories
    outside = d.add_layer("cement_plaster", "outside")
    outside["thickness"].setValue(2.0)   # explicit user choice in cm, not a hidden default
    inside = d.add_layer("gypsum_board", "inside")
    inside["thickness"].setValue(1.25)
    d.accept()
    assert d.result() == d.DialogCode.Accepted
    key = window.plan_view.controller.wall_choice
    assert key.startswith("proj_")
    assert [l.material_id for l in layers(key, window.doc)][0] == "cement_plaster"
    assert [l.material_id for l in layers(key, window.doc)][-1] == "gypsum_board"
    assert total_thickness(key, window.doc) == pytest.approx(0.3325)
    assert window.doc.constructions["walltype:" + key]["base_type"] == "isotex_hdiii_30_7"
    wid = _wall(window, 0, key, total_thickness(key, window.doc))
    report = take_off_isotex(window.doc)
    assert report["walls"][0]["wall"] == wid and report["walls"][0]["code"] == "HDIII 30/7"
    restored = Document.from_dict(json.loads(json.dumps(window.doc.to_dict())))
    assert take_off_isotex(restored)["walls"][0]["code"] == "HDIII 30/7"


def test_existing_isotex_wall_can_gain_a_finish_without_losing_its_takeoff(window):
    from archforge.ui.wall_details_dialog import WallDetailsDialog
    from archforge.construction.isotex import take_off_isotex

    wall = _wall(window, 0, "isotex_hdiii_30_7", 0.30)
    d = WallDetailsDialog(window, "isotex_hdiii_30_7", wall_id=wall)
    finish = d.add_layer("gypsum_board", "inside")
    finish["thickness"].setValue(1.25)
    before = len(window.stack.done)
    d.accept()
    assert len(window.stack.done) == before + 1
    assert window.doc.get(wall).params["thickness"] == pytest.approx(0.3125)
    assert take_off_isotex(window.doc)["walls"][0]["code"] == "HDIII 30/7"
    window.stack.undo()
    assert window.doc.get(wall).params["wall_type"] == "isotex_hdiii_30_7"


def test_existing_wall_gets_its_own_layers_and_undo_preserves_neighbour(window):
    from archforge.ui.wall_details_dialog import WallDetailsDialog
    from archforge.architecture.wall_types import layers

    a = _wall(window, 0, "brick_partition", 0.13)
    b = _wall(window, 4, "brick_partition", 0.13)
    dialog = WallDetailsDialog(window, "brick_partition", wall_id=a)
    outside = dialog.add_layer("xps", "outside")
    outside["thickness"].setValue(3.0)
    before = len(window.stack.done)
    dialog.accept()
    key = window.doc.get(a).params["wall_type"]
    assert key.startswith("proj_") and key != window.doc.get(b).params["wall_type"]
    assert len(layers(key, window.doc)) == 4
    assert window.doc.get(a).params["thickness"] == pytest.approx(0.16)
    assert len(window.stack.done) == before + 1
    window.stack.undo()
    assert window.doc.get(a).params["wall_type"] == "brick_partition"
    assert window.doc.get(a).params["thickness"] == pytest.approx(0.13)


def test_existing_generic_wall_can_select_built_in_type_without_copy(window):
    from archforge.ui.wall_details_dialog import WallDetailsDialog

    wid = _wall(window, 0)
    d = WallDetailsDialog(window, "generic", wall_id=wid)
    d.type_combo.setCurrentIndex(d.type_combo.findData("brick_partition"))
    d.accept()
    assert window.doc.get(wid).params["wall_type"] == "brick_partition"
    assert window.doc.get(wid).params["thickness"] == pytest.approx(0.13)
    window.stack.undo()
    assert window.doc.get(wid).params["wall_type"] == "generic"


def test_project_type_details_from_menu_update_all_its_walls_in_one_undo(window):
    from archforge.architecture import wall_assemblies as wa
    from archforge.ui.wall_details_dialog import WallDetailsDialog

    rows = wa.layer_specs(window.doc, "brick_partition")
    key, command = wa.new_type_command(window.doc, "Δική μου τοιχοποιία", rows)
    window.stack.execute(command)
    a = _wall(window, 0, key, 0.13)
    b = _wall(window, 4, key, 0.13)
    window._mockup_wall_types_menu.aboutToShow.emit()
    assert key in window._mockup_wall_detail_actions
    dialog = WallDetailsDialog(window, key)
    outer = dialog.add_layer("cement_plaster", "outside")
    outer["thickness"].setValue(1.0)
    before = len(window.stack.done)
    dialog.accept()
    assert len(window.stack.done) == before + 1
    assert [window.doc.get(w).params["thickness"] for w in (a, b)] == pytest.approx([0.14, 0.14])
    window.stack.undo()
    assert [window.doc.get(w).params["thickness"] for w in (a, b)] == pytest.approx([0.13, 0.13])


def test_incomplete_layer_cannot_be_saved_as_a_hidden_default(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from archforge.ui.wall_details_dialog import WallDetailsDialog

    notices = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _title, message: notices.append(str(message)))
    d = WallDetailsDialog(window, "brick_partition")
    d.add_layer("gypsum_board", "inside")
    before = len(window.stack.done)
    d.accept()
    assert d.result() != d.DialogCode.Accepted
    assert len(window.stack.done) == before
    assert "πάχος" in notices[0]


def test_isotex_product_identity_disappears_if_its_actual_core_is_replaced(window):
    from archforge.architecture import wall_assemblies as wa
    from archforge.construction.isotex import take_off_isotex

    rows = wa.layer_specs(window.doc, "isotex_hdiii_30_10")
    key, command = wa.new_type_command(window.doc, "Isotex με τελείωμα", rows,
                                        base_type="isotex_hdiii_30_10")
    window.stack.execute(command)
    _wall(window, 0, key, 0.30)
    assert take_off_isotex(window.doc)["totals"]["walls"] == 1
    altered = [dict(r) for r in rows]
    altered[1]["material"] = "xps"  # no longer the manufacturer's graphite EPS core
    window.stack.execute(wa.edit_type_command(window.doc, key, rows=altered))
    assert "base_type" not in window.doc.constructions["walltype:" + key]
    assert take_off_isotex(window.doc)["totals"]["walls"] == 0
