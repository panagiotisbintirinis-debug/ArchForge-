from types import SimpleNamespace

from archforge.core.model import Document, Entity
from archforge.core.commands import CommandStack
from archforge.ui.material_library import _assigned_material, _apply_material, _targets


class _Status:
    def showMessage(self, *args, **kwargs):
        pass


class _Window:
    def __init__(self, doc):
        self.doc = doc
        self.stack = CommandStack(doc)
        self.redraw_count = 0
        self.inspector_count = 0
        self._status = _Status()

    def _redraw_views(self, **kwargs):
        self.redraw_count += 1

    def refresh_inspector(self):
        self.inspector_count += 1

    def statusBar(self):
        return self._status


def _wall():
    return Entity('wall', {
        'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0,
        'z': 0.0, 'height': 2.7, 'thickness': 0.15,
    }, id='wall-material-library')


def test_material_library_exposes_whole_object_and_wall_sides():
    entity = _wall()
    targets = {target.key: target.label for target in _targets(entity)}
    assert '' in targets
    assert 'exterior' in targets
    assert 'interior' in targets


def test_material_library_applies_whole_object_through_command_stack():
    doc = Document(); entity = _wall(); doc.add(entity)
    window = _Window(doc)

    _apply_material(window, entity.id, '', 'wood_oak')

    assert doc.get(entity.id).params['material_id'] == 'wood_oak'
    assert window.redraw_count == 1
    assert window.inspector_count == 1
    window.stack.undo()
    assert not doc.get(entity.id).params.get('material_id')


def test_material_library_applies_one_surface_without_overwriting_other_side():
    doc = Document(); entity = _wall(); doc.add(entity)
    window = _Window(doc)

    _apply_material(window, entity.id, 'exterior', 'stone_dark')
    _apply_material(window, entity.id, 'interior', 'plaster_white')

    surface = doc.get(entity.id).params['surface_materials']
    assert surface['exterior'] == 'stone_dark'
    assert surface['interior'] == 'plaster_white'
    assert _assigned_material(doc.get(entity.id), 'exterior') == 'stone_dark'
    assert _assigned_material(doc.get(entity.id), 'interior') == 'plaster_white'


def test_stair_targets_include_piece_roles():
    entity = SimpleNamespace(kind='stair', params={'surface_materials': {}}, name='')
    keys = {target.key for target in _targets(entity)}
    assert {'', 'tread', 'riser', 'landing', 'slab', 'stringer'} <= keys
