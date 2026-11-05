"""Σ7 (κριτική v5): the take-off wrote «Ground / Floor 2» while the IFC wrote «Ισόγειο / 1ος όροφος».

One source (``core/storey_names.level_name``) for the take-off, the slab list and new slab names; the stored storey
ids do not change.  Σ3 of the same review was checked on the same file: storey 2 has one closed room (7 walls,
30,5 m² on the axes) and its floor slab is 30,46 m² — the «170 m²» was the sum of every slab, not a lost storey.
"""
import os

from archforge.core.storey_names import level_name
from archforge.project.persistence import load_project
from archforge.quantities.takeoff import slab_quantities, take_off

OWNER = os.path.join(os.path.dirname(__file__), "data", "owner_111_two_storey.archforge")


def test_level_names():
    assert level_name("Ground") == "Ισόγειο" and level_name("XY") == "Ισόγειο"
    assert level_name("Floor 2") == "1ος όροφος" and level_name("Floor 3") == "2ος όροφος"
    assert level_name("Σοφίτα") == "Σοφίτα"


def test_take_off_and_slabs_print_the_human_storey_names_of_the_owner_project():
    doc = load_project(OWNER).doc
    assert set(doc.levels) >= {"Ground", "Floor 2"}                       # ids stay as stored
    result = take_off(doc)
    assert {r["storey"] for r in result["rooms"]} == {"Ισόγειο", "1ος όροφος"}
    names = [s["name"] for s in slab_quantities(doc)]
    assert "Πλάκα δαπέδου — 1ος όροφος" in names and not any("Floor" in n or "Ground" in n for n in names)
    # Σ3: storey 2 is one room, and its floor slab is the same size — nothing is dropped.
    upper = [r for r in result["rooms"] if r["storey"] == "1ος όροφος"]
    slab = next(s for s in slab_quantities(doc) if s["name"] == "Πλάκα δαπέδου — 1ος όροφος")
    assert len(upper) == 1 and abs(upper[0]["floor_m2"] - slab["area_m2"]) < 2.5


def test_new_storey_slab_is_named_like_the_plan():
    from archforge.architecture.storey_slabs import storey_slab_name
    assert storey_slab_name("room_floor", "Floor 2") == "Πλάκα δαπέδου — 1ος όροφος"
    assert storey_slab_name("room_roof", "Ground") == "Πλάκα δώματος — Ισόγειο"
