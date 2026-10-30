"""Building materials registry: every wall layer points to one material; project data-sheet values with undo."""
import json

import pytest

from archforge.architecture.wall_types import WALL_TYPES, indicative_u, layer_materials, layers
from archforge.construction import building_materials as bm
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.core.provenance import MANUFACTURER_DATA, UNVERIFIED, VERIFIED, rules
from archforge.rendering.materials import MATERIAL_PRESETS


def test_every_layer_of_every_wall_type_is_a_registry_material():
    for key in WALL_TYPES:
        for layer, (mat, d) in zip(layers(key), layer_materials(key)):
            assert mat is bm.MATERIALS[layer.material_id]
            assert layer == (mat.name, d, mat.conductivity, mat.colour, mat.insulation)


def test_u_values_did_not_change_when_the_layers_moved_to_the_registry():
    # The λ the wall types used before (plaster 0.87, brick 0.47, XPS 0.034): same indicative U.
    r = 0.13 + 0.04 + 2 * 0.02 / 0.87 + 2 * 0.09 / 0.47 + 0.05 / 0.034
    assert indicative_u('brick_double_insulated') == pytest.approx(1 / r)


def test_built_in_values_are_honest_about_their_status():
    status = {r.id: r.status for r in rules('materials.')}
    assert set(status) == {f'materials.{m.id}.conductivity' for m in bm.MATERIALS.values()}
    assert VERIFIED not in status.values() and set(status.values()) == {UNVERIFIED}
    for m in bm.MATERIALS.values():
        assert m.density is None                      # only from a data sheet the user enters
        assert m.role in bm.ROLES and m.hatch in bm.HATCHES
        assert m.appearance is None or m.appearance in MATERIAL_PRESETS
        assert m.insulation == (m.role == 'insulation')
        assert m.price_code == f'bmat.{m.id}'


def _house():
    doc = Document(); stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7,
                                            'thickness': 0.27, 'wall_type': 'brick_double_insulated'})))
    return doc, stack


def test_project_data_sheet_value_changes_u_with_one_undo_and_survives_save():
    doc, stack = _house()
    before = indicative_u('brick_double_insulated', doc)
    stack.execute(bm.set_properties_command(doc, 'xps', conductivity=0.029, density=33, source='Φύλλο XPS 300'))
    m = bm.material('xps', doc)
    assert (m.conductivity, m.density, m.conductivity_status) == (0.029, 33.0, MANUFACTURER_DATA)
    assert m.conductivity_source == 'Φύλλο XPS 300'
    assert bm.MATERIALS['xps'].conductivity == 0.034            # the built-in value is untouched
    after = indicative_u('brick_double_insulated', doc)
    assert after < before and indicative_u('brick_double_insulated') == pytest.approx(before)
    reopened = Document.from_dict(json.loads(json.dumps(doc.to_dict())))
    assert indicative_u('brick_double_insulated', reopened) == pytest.approx(after)
    stack.undo()
    assert indicative_u('brick_double_insulated', doc) == pytest.approx(before)
    assert bm.material('xps', doc) is bm.MATERIALS['xps']


def test_clearing_returns_to_built_in_and_bad_values_are_refused():
    doc, stack = _house()
    stack.execute(bm.set_properties_command(doc, 'xps', conductivity=0.029))
    stack.execute(bm.set_properties_command(doc, 'xps'))
    assert bm.material('xps', doc) is bm.MATERIALS['xps']
    stack.undo()
    assert bm.material('xps', doc).conductivity == 0.029
    for bad in (0, -1):
        with pytest.raises(ValueError):
            bm.set_properties_command(doc, 'xps', conductivity=bad)
    with pytest.raises(ValueError):
        bm.set_properties_command(doc, 'cardboard', conductivity=0.1)


def test_overrides_live_beside_appearance_materials_without_mixing():
    from archforge.rendering.user_materials import project_materials
    doc, stack = _house()
    stack.execute(bm.set_properties_command(doc, 'xps', conductivity=0.029))
    assert project_materials(doc) == {}
    assert bm.overrides(doc) == {'xps': {'conductivity': 0.029, 'density': None, 'source': ''}}


def test_quantities_per_layer_material_with_no_built_in_price():
    from archforge.construction.shell import layer_material_list
    from archforge.quantities.materials import all_lists
    doc, stack = _house()                                   # 4 m × 2.7 m, double brick with 5 cm XPS
    rows = {(d, u): (q, m) for d, u, q, m in layer_material_list(doc)}
    q, meta = rows[('Εξηλασμένη πολυστερίνη (XPS) — όγκος στρώσης', 'm³')]
    assert q == pytest.approx(4 * 2.7 * 0.05, abs=1e-3) and meta['code'] == 'bmat.xps'
    assert rows[('Οπτόπλινθος διάτρητος — επιφάνεια στρώσης', 'm²')][0] == pytest.approx(2 * 4 * 2.7)
    sheet = next(s for s in all_lists(doc) if s[0] == 'Στρώσεις')
    from archforge.quantities.quote import quote
    priced = [r for _t, sec in quote(doc)['sections'] for r in sec if str(r['code']).startswith('bmat.')]
    assert priced and all(r['amount'] is None for r in priced) and sheet[2]
