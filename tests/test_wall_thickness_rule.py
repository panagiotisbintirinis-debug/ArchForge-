"""Κανόνας ιδιοκτήτη 07/11: «δεν μπορεί να υφίσταται διαφορετικό πάχος τοίχου εάν οι στρώσεις δεν το δικαιολογούν»."""
import json
import os

import pytest

from archforge.architecture.wall_types import thickness_fix_command, thickness_mismatches, total_thickness
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity


def _doc(t):
    d = Document(); st = CommandStack(d)
    for a, b in (((0, 0), (5, 0)), ((5, 0), (5, 4)), ((5, 4), (0, 4)), ((0, 4), (0, 0))):
        st.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 3.0,
                                             'thickness': t, 'wall_type': 'brick_double_insulated'})))
    st.execute(AddEntity(Entity('wall', {'x1': 2.0, 'y1': 0.0, 'x2': 2.0, 'y2': 4.0, 'z': 0.0, 'height': 3.0,
                                         'thickness': 0.12, 'wall_type': 'generic'})))     # no layers: its own
    return d, st


def test_the_gate_lists_walls_the_layers_do_not_justify_and_one_click_fixes_them_in_one_undo():
    from archforge.scenarios.gate import FAIL
    from archforge.scenarios.live_gate import run as _unused  # noqa: F401 — the panel's runner exists
    layers = total_thickness('brick_double_insulated')
    d, st = _doc(0.25)
    bad = thickness_mismatches(d)
    assert len(bad) == 4 and all(abs(total - layers) < 1e-9 for _w, _t, total in bad)
    st.execute(thickness_fix_command(d))
    assert thickness_mismatches(d) == [] and thickness_fix_command(d) is None
    assert {round(e.params['thickness'], 4) for e in d.entities.values() if e.params.get('wall_type') != 'generic'} == {round(layers, 4)}
    st.undo()
    assert len(thickness_mismatches(d)) == 4
    _d, _st = _doc(layers)
    assert thickness_mismatches(_d) == []


def test_ifc_import_takes_the_layers_thickness_and_says_so(tmp_path):
    from archforge.exchange.ifc import export_ifc
    from archforge.exchange.ifc_import import import_ifc
    pytest.importorskip('ifcopenshell')
    d, _st = _doc(0.25)                           # a file whose bodies say 25 cm, build-up 27
    export_ifc(d, str(tmp_path / 'a.ifc'))
    back = Document(); summary = import_ifc(back, CommandStack(back), str(tmp_path / 'a.ifc'))
    assert thickness_mismatches(back) == []
    assert len(summary['thickness_from_layers']) == 4


def test_no_project_of_the_tests_breaks_the_rule():
    here = os.path.join(os.path.dirname(__file__), 'data')
    for name in ('bot16_three_storey_frame.archforge', 'owner_111_two_storey.archforge'):
        path = os.path.join(here, name)
        d = Document.load(path) if 'bot16' in name else Document.from_dict(json.load(open(path, encoding='utf-8')))
        assert thickness_mismatches(d) == [], name
