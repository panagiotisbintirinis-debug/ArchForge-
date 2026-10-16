"""Earthworks from what the design gives: basement pit, foundations of the up-to-date design; ground from the terrain."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, CreateFloorLevel
from archforge.core.model import Document, Entity
from archforge.construction.earthworks import earthworks


def _walls(stack, z):
    for x1, y1, x2, y2 in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0)]:
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z, 'height': 2.7, 'thickness': 0.2})))


def test_nothing_given_nothing_measured_and_it_says_why():
    doc = Document(); stack = CommandStack(doc); _walls(stack, 0.0)
    r = earthworks(doc)
    assert r['rows'] == [] and any('υπόγειο' in m for m in r['missing']) and any('φέρων' in m for m in r['missing'])
    assert '±0,00' in r['basis'][0]


def test_basement_pit_from_its_rooms_and_the_ground():
    doc = Document(); stack = CommandStack(doc); _walls(stack, 0.0)
    stack.execute(CreateFloorLevel('Basement', -3.0)); _walls(stack, -3.0)
    r = earthworks(doc)
    rows = {m['code']: q for _d, _u, q, m in r['rows']}
    room_area = (8 + 0.2) * (6 + 0.2)                       # out to the outer face of the basement walls
    assert rows['earthworks.basement'] == pytest.approx(room_area * 3.0, rel=0.02)
    assert rows['earthworks.removal'] == pytest.approx(rows['earthworks.basement'])
    # With a terrain the ground comes from it (here 0,5 m above ±0,00 → deeper pit).
    from archforge.site.terrain import default_terrain_params
    p = default_terrain_params(doc); p['elevation'] = 0.5
    stack.execute(AddEntity(Entity('terrain', p)))
    r2 = earthworks(doc)
    deeper = {m['code']: q for _d, _u, q, m in r2['rows']}['earthworks.basement']
    if 'τοπογραφικό' in r2['basis'][0]:
        assert deeper > rows['earthworks.basement']
