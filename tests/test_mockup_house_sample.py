"""The delivered sample is a real editable model, not a rendered background."""
from pathlib import Path
from collections import Counter
from archforge.core.model import Document
from archforge.core.commands import CommandStack, UpdateEntity
from archforge.core.layers import set_workspace

PATH = Path(__file__).resolve().parents[1] / 'docs/scenarios/S11_mockup_villa.archforge'


def test_mockup_house_contains_editable_building_and_site():
    doc = Document.load(str(PATH))
    counts = Counter(e.kind for e in doc.entities.values())
    for kind in ('wall','door','window','library_object','cabinet','floor','room_floor','room_roof','stair','pool','terrain','railing'):
        assert counts[kind] > 0, kind
    assert sorted(doc.levels.values()) == [0.,3.]
    assert doc.get(next(e.id for e in doc.entities.values() if e.kind=='stair')).params['layout'] == 'u'


def test_mockup_house_wall_edit_undo_and_reopen(tmp_path):
    doc = Document.load(str(PATH)); set_workspace(doc,'arch')
    wall = next(e for e in doc.entities.values() if e.kind=='wall')
    height = wall.params['height']; stack = CommandStack(doc)
    stack.execute(UpdateEntity(wall.id, {'height':height+.1}))
    assert doc.get(wall.id).params['height'] == height+.1
    stack.undo()
    assert doc.get(wall.id).params['height'] == height
    saved=tmp_path/'copy.archforge';doc.save(str(saved))
    reopened=Document.load(str(saved))
    assert {e.id:e.params for e in reopened.entities.values()} == {e.id:e.params for e in doc.entities.values()}
