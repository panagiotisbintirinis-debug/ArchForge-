"""MAT3: melamine boards and kitchen worktops, supplier codes, the user's own materials."""
import os
import re

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.rendering import user_materials as um
from archforge.rendering.materials import (
    MATERIAL_PRESETS, MATERIAL_USES, USER_CATEGORY, material_spec, materials_for_use, materials_in_category,
    picker_categories, picker_materials,
)
from archforge.rendering.patterns import pattern_geometry, validate_pattern


def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """A fresh user data folder: settings.json of this test only."""
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    um.reload()
    yield tmp_path / 'data'
    monkeypatch.delenv('ARCHFORGE_DATA')
    um.reload()


def _wall(**params):
    base = {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.5, 'thickness': 0.2}
    base.update(params)
    return Entity('wall', base)


# ------------------------------------------------------------ presets ---

def test_melamine_and_worktop_presets_are_greek_and_valid():
    melamine = dict(materials_in_category('Μελαμίνες'))
    worktops = dict(materials_in_category('Πάγκοι κουζίνας'))
    assert 'melamine_white' in melamine            # moved here, same id
    assert len(melamine) >= 15 and len(worktops) >= 14
    names = ' '.join(s['name'] for s in list(melamine.values()) + list(worktops.values()))
    for word in ('λευκή', 'ανθρακί', 'δρυς', 'καρυδιά', 'τικ', 'σημύδα', 'βέγκε', 'τσιμέντου',
                 'λαμινέιτ', 'κόμπακτ', 'χαλαζία', 'γρανίτη', 'κεραμικός', 'μασίφ', 'ανοξείδωτος'):
        assert word in names, word
    for material_id, spec in {**melamine, **worktops}.items():
        assert not re.search(r'[A-Za-z]', spec['name']), material_id
    assert 'πάγκος' in MATERIAL_USES
    assert set(dict(materials_for_use('πάγκος'))) >= set(worktops)


def test_wood_decors_have_continuous_grain_and_granite_speckle():
    for material_id in ('melamine_oak_natural', 'melamine_walnut', 'melamine_wenge', 'worktop_laminate_oak'):
        pattern = MATERIAL_PRESETS[material_id]['pattern']
        assert pattern['type'] == 'grain' and validate_pattern(pattern) == []
        geo = pattern_geometry(pattern, MATERIAL_PRESETS[material_id]['color'], material_id)
        # Leaves run the full board length: no butt joints across the grain.
        assert all(abs(max(x for x, _ in c['pts']) - min(x for x, _ in c['pts']) - geo['width']) < 1e-6
                   for c in geo['cells'])
        assert len(geo['lines']) > 20 and geo['relief'] == 0.0
    for material_id in ('worktop_granite_black', 'worktop_granite_grey', 'worktop_granite_speckled'):
        pattern = MATERIAL_PRESETS[material_id]['pattern']
        assert pattern['type'] == 'speckle' and validate_pattern(pattern) == []
        geo = pattern_geometry(pattern, MATERIAL_PRESETS[material_id]['color'], material_id)
        assert 500 < len(geo['cells']) <= 2600
        assert len({c['color'] for c in geo['cells']}) > 20
    assert validate_pattern(dict(MATERIAL_PRESETS['worktop_granite_grey']['pattern'], unit_w=0.0005))


# -------------------------------------------------------------- codes ---

def test_code_is_stored_per_surface_and_undo_restores_it():
    doc = Document()
    stack = CommandStack(doc)
    wall = _wall(material_id='plaster_white')
    stack.execute(AddEntity(wall))
    from archforge.core.commands import UpdateEntity
    codes = um.with_code({}, ['exterior'], ' 4521 ΜΤ ', 'Ξυλεία Παπαδόπουλος')
    stack.execute(UpdateEntity(wall.id, {'surface_materials': {'exterior': 'melamine_oak_natural'},
                                         'material_codes': codes}))
    entity = doc.get(wall.id)
    assert entity.params['material_codes'] == {'exterior': {'code': '4521 ΜΤ', 'supplier': 'Ξυλεία Παπαδόπουλος'}}
    assert um.code_for(entity, 'exterior', 'melamine_oak_natural') == {'code': '4521 ΜΤ', 'supplier': 'Ξυλεία Παπαδόπουλος'}
    assert um.code_for(entity, 'interior', 'plaster_white')['code'] == ''
    # Empty code and supplier remove the entry.
    assert um.with_code(codes, ['exterior'], '', '') == {}
    # Save / load keeps it.
    again = Document.from_dict(doc.to_dict())
    assert again.get(wall.id).params['material_codes'] == entity.params['material_codes']
    stack.undo()
    assert 'material_codes' not in doc.get(wall.id).params
    stack.redo()
    assert doc.get(wall.id).params['material_codes']['exterior']['code'] == '4521 ΜΤ'


def test_dialog_edits_the_code_through_one_undo_step(monkeypatch, data_dir):
    app = _app()
    from archforge.ui.main_window import MainWindow

    def fake_exec(dialog):
        w._materials_code.setText('8800 ΣΓ')
        w._materials_supplier.setText('Ο προμηθευτής μου')
        cat = [c for c in dialog.findChildren(__import__('PySide6.QtWidgets', fromlist=['QComboBox']).QComboBox)
               if c.findText('Μελαμίνες') >= 0][0]
        cat.setCurrentText('Μελαμίνες')
        lst = w._materials_list
        row = next(i for i in range(lst.count()) if lst.item(i).data(256) == 'melamine_walnut')
        lst.setCurrentRow(row)
        # Presets are not the user's: nothing to edit or delete.
        assert not w._materials_buttons['edit'].isEnabled()
        assert not w._materials_buttons['delete'].isEnabled()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, 'exec', fake_exec)
    w = MainWindow()
    try:
        box = Entity('box', {'x': 0.0, 'y': 0.0, 'z': 0.0, 'width': 1.0, 'depth': 0.6, 'height': 0.9})
        w.stack.execute(AddEntity(box))
        before = len(w.stack.done)
        w._open_materials(box.id)
        app.processEvents()
        params = w.doc.get(box.id).params
        assert params['material_id'] == 'melamine_walnut'
        assert params['material_codes'] == {'': {'code': '8800 ΣΓ', 'supplier': 'Ο προμηθευτής μου'}}
        assert len(w.stack.done) == before + 1
        # Properties panel shows the code next to the finish.
        w.doc.select([box.id])
        w.refresh_inspector()
        from archforge.ui.material_codes import material_rows
        assert material_rows(w.doc, w.doc.get(box.id)) == [('Υλικό', 'Μελαμίνη καρυδιά — κωδ. 8800 ΣΓ (Ο προμηθευτής μου)')]
        w.stack.undo()
        assert 'material_codes' not in w.doc.get(box.id).params
    finally:
        w.hide()


def test_quantities_show_the_code():
    from archforge.quantities.materials import all_lists, finishes_list
    doc = Document()
    stack = CommandStack(doc)
    stack.execute(AddEntity(_wall(material_id='plaster_white')))
    for x in (0.0, 0.6):
        stack.execute(AddEntity(Entity('box', {
            'x': x, 'y': 1.0, 'z': 0.0, 'width': 0.6, 'depth': 0.6, 'height': 0.9,
            'material_id': 'worktop_quartz_white',
            'material_codes': {'': {'code': 'Q-1020', 'supplier': ''}}})))
    rows = finishes_list(doc)
    assert ('Πάγκος χαλαζία λευκός — κωδ. Q-1020', 'τεμ.', 2) in rows
    assert ('Λευκός σοβάς — όψη τοίχου (μικτό)', 'm²', 20.0) in rows
    assert 'Υλικά' in [s[0] for s in all_lists(doc)]
    from archforge.ui.project_outline import used_materials
    assert ('worktop_quartz_white', 'Πάγκος χαλαζία λευκός — κωδ. Q-1020', 2) in used_materials(doc)


# ------------------------------------------------- the user's materials ---

def test_user_material_is_saved_loaded_and_rendered(data_dir):
    spec = um.build_spec('Μελαμίνη δρυς του Νίκου', '#A07850', 'melamine_oak_natural', 'Μελαμίνες', '3311', 'Ξυλεμπορική')
    material_id = um.save_material(None, spec)
    assert material_id.startswith('user_')
    # Kept in settings.json of the user data folder, so every project sees it.
    import json
    saved = json.loads((data_dir / 'settings.json').read_text(encoding='utf8'))[um.SETTINGS_KEY]
    assert saved[material_id]['code'] == '3311' and saved[material_id]['color'] == '#a07850'
    um.reload()
    loaded = material_spec(material_id)
    assert loaded['name'] == 'Μελαμίνη δρυς του Νίκου'
    assert loaded['pattern'] == MATERIAL_PRESETS['melamine_oak_natural']['pattern']     # inherited look
    assert loaded['roughness'] == MATERIAL_PRESETS['melamine_oak_natural']['roughness']
    # Listed in the dialog: own category first, and in its chosen category.
    assert picker_categories()[0] == USER_CATEGORY
    assert material_id in dict(picker_materials(USER_CATEGORY))
    assert material_id in dict(picker_materials('Μελαμίνες'))
    # 3D: same path as the presets.
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document()
    stack = CommandStack(doc)
    wall = _wall(material_id=material_id)
    stack.execute(AddEntity(wall))
    payload = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)
    mats = [o['material'] for o in payload['objects'] if o['id'] == wall.id]
    assert mats and all(m['material_id'] == material_id and m['color'] == '#a07850' for m in mats)
    assert payload['patterns'][mats[0]['pattern_key']]['cells']
    # Edit and delete.
    um.save_material(material_id, dict(loaded, name='Μελαμίνη δρυς Ν.'))
    assert material_spec(material_id)['name'] == 'Μελαμίνη δρυς Ν.'
    assert um.delete_material(material_id)
    assert material_spec(material_id) is None


def test_project_carries_its_user_materials(data_dir):
    material_id = um.save_material(None, um.build_spec('Πάγκος του πελάτη', '#335577', 'worktop_quartz_white',
                                                       'Πάγκοι κουζίνας', 'ΠΚ-7'))
    doc = Document()
    stack = CommandStack(doc)
    wall = _wall()
    stack.execute(AddEntity(wall))
    from archforge.core.commands import CompositeCommand, UpdateEntity
    carry = um.carry_command(doc, material_id)
    stack.execute(CompositeCommand([carry, UpdateEntity(wall.id, {'material_id': material_id})]))
    assert doc.materials[material_id]['code'] == 'ΠΚ-7'
    assert um.carry_command(doc, material_id) is None          # already carried, unchanged
    data = doc.to_dict()
    # Another computer: no such material in its settings.
    um.delete_material(material_id)
    um.reload()
    other = Document.from_dict(data)
    assert material_spec(material_id) is None
    assert material_spec(material_id, other)['color'] == '#335577'
    from archforge.quantities.materials import finishes_list
    assert ('Πάγκος του πελάτη — κωδ. ΠΚ-7 — όψη τοίχου (μικτό)', 'm²', 20.0) in finishes_list(other)
    um.adopt_project(other)                                    # pickable while the project is open
    assert material_id in dict(picker_materials(USER_CATEGORY, other))
    # Undo takes the material back out of the project too.
    stack.undo()
    assert material_id not in doc.materials


# ---------------------------------------------------------------- CSV ---

def test_csv_import_with_semicolon_and_greek_windows_encoding(data_dir):
    text = ('Κωδικός;Όνομα;Χρώμα;Κατηγορία;Προμηθευτής\r\n'
            '1001;Λευκή ματ;#f0f0ec;Μελαμίνες;Ξυλεμπορική Α\r\n'
            '1002;Δρυς ανοιχτή;d4b994;;\r\n'
            ';Χωρίς κωδικό;#000000;;\r\n'
            '1003;;#ffffff;;\r\n'
            '1004;Γκρι;κόκκινο;;\r\n'
            '\r\n'
            'Π-20;Πάγκος γρανίτη Ζ;#333333;Πάγκοι κουζίνας;Μάρμαρα Β\r\n')
    data = text.encode('cp1253')
    with pytest.raises(UnicodeDecodeError):
        data.decode('utf-8')
    result = um.parse_csv(data, 'melamine_oak_natural', 'Μελαμίνες', 'Προμηθευτής Χ')
    assert result['separator'] == ';'
    rows = dict(result['rows'])
    assert len(rows) == 3 and len(result['skipped']) == 3
    by_code = {s['code']: s for s in rows.values()}
    assert by_code['1001']['name'] == 'Λευκή ματ' and by_code['1001']['supplier'] == 'Ξυλεμπορική Α'
    assert by_code['1002']['color'] == '#d4b994' and by_code['1002']['supplier'] == 'Προμηθευτής Χ'
    assert by_code['1002']['category'] == 'Μελαμίνες' and by_code['1002']['base'] == 'melamine_oak_natural'
    assert by_code['Π-20']['category'] == 'Πάγκοι κουζίνας'
    assert [line for line, _ in result['skipped']] == [4, 5, 6]
    assert all(k.startswith('user_') for k in rows)
    um.save_many(rows)
    assert material_spec(next(k for k, s in rows.items() if s['code'] == 'Π-20'))['name'] == 'Πάγκος γρανίτη Ζ'
    # Importing the same list again updates, does not duplicate.
    again = um.parse_csv(data, 'melamine_oak_natural', 'Μελαμίνες', 'Προμηθευτής Χ')
    assert set(dict(again['rows'])) == set(rows)


def test_csv_import_with_comma_and_utf8(data_dir):
    data = '﻿2001,Μελαμίνη μόκα,#8c7462\n2002,"Καρυδιά, σκούρα",#5a3a28,Μελαμίνες,Α & Β\n'.encode('utf-8')
    result = um.parse_csv(data)
    assert result['separator'] == ','
    names = sorted(s['name'] for _, s in result['rows'])
    assert names == ['Καρυδιά, σκούρα', 'Μελαμίνη μόκα']
    assert result['skipped'] == []


def test_import_preview_dialog_counts_rows_and_skips(data_dir, tmp_path):
    _app()
    from archforge.ui.material_codes import CodeImportDialog, import_codes
    path = tmp_path / 'codes.csv'
    path.write_bytes('3001;Λευκή;#ffffff\n;χωρίς;#000000\n3002;Ανθρακί;#444444\n'.encode('cp1253'))
    dialog = CodeImportDialog(None, path.read_bytes())
    assert dialog.rows.count() == 2 and dialog.skipped.count() == 1
    assert '2 κωδικοί' in dialog.summary.text()
    assert dialog.ok.text() == 'Εισαγωγή 2'
    assert import_codes(None, str(path), exec_dialog=False) == 2
    assert len(um.user_materials()) == 2


def test_new_material_form(data_dir):
    _app()
    from archforge.ui.material_codes import UserMaterialDialog
    form = UserMaterialDialog(None, category='Μελαμίνες')
    form.name.setText('Μελαμίνη πράσινη')
    form.code.setText('5005')
    form.supplier.setText('Ξυλεμπορική')
    form.base.setCurrentIndex(form.base.findData('melamine_white_matt'))
    form.set_color('#4a6b50')
    form._accept()
    assert form.result() == QDialog.DialogCode.Accepted
    spec = material_spec(form.material_id)
    assert spec['color'] == '#4a6b50' and spec['code'] == '5005' and spec['category'] == 'Μελαμίνες'
    assert spec['roughness'] == MATERIAL_PRESETS['melamine_white_matt']['roughness']
