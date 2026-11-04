"""Language changes are presentation changes; project text and command ids stay intact."""
import json

import pytest


def test_english_default_and_explicit_greek(tmp_path):
    from archforge.localization import Translator
    t = Translator(settings_path=tmp_path / 'language.json')
    assert t.language == 'en'
    assert t.text('language.title') == 'Language'
    t.set_language('el')
    assert t.text('language.title') == 'Γλώσσα'
    assert Translator(settings_path=t.settings_path).language == 'el'


def test_formatted_user_text_is_preserved(tmp_path):
    from archforge.localization import Translator
    t = Translator(settings_path=tmp_path / 'language.json')
    assert t.text('project.named', name='Τοίχος / Save {name}') == 'Project: Τοίχος / Save {name}'
    t.set_language('el', persist=False)
    assert t.text('project.named', name='Τοίχος / Save {name}') == 'Έργο: Τοίχος / Save {name}'
    with pytest.raises(KeyError):
        t.text('project.named')


def test_new_language_falls_back_to_english_and_validates_fields(tmp_path):
    from archforge.localization import Translator, builtin_catalog_dir, validate_catalogs
    target = tmp_path / 'catalogs'
    target.mkdir()
    for name in ('en', 'el'):
        (target / f'{name}.json').write_bytes((builtin_catalog_dir() / f'{name}.json').read_bytes())
    (target / 'fr.json').write_text(json.dumps({
        'code': 'fr', 'native_name': 'Français',
        'messages': {'language.title': 'Langue', 'project.named': 'Projet : {name}'},
    }), encoding='utf8')
    assert validate_catalogs(target) == []
    t = Translator(catalog_dir=target, settings_path=tmp_path / 'prefs.json', language='fr')
    assert t.text('language.title') == 'Langue'
    assert t.text('field.width') == 'Width'
    assert dict(t.languages())['fr'] == 'Français'
    bad = json.loads((target / 'fr.json').read_text())
    bad['messages']['project.named'] = 'Projet : {wrong}'
    (target / 'fr.json').write_text(json.dumps(bad), encoding='utf8')
    assert any('project.named' in error for error in validate_catalogs(target))
    with pytest.raises(ValueError, match='project.named'):
        Translator(catalog_dir=target, settings_path=tmp_path / 'prefs.json')


def test_invalid_settings_and_unknown_language_are_safe(tmp_path):
    from archforge.localization import Translator
    path = tmp_path / 'prefs.json'
    path.write_text('{broken', encoding='utf8')
    t = Translator(settings_path=path)
    assert t.language == 'en'
    with pytest.raises(ValueError):
        t.set_language('../other')
    with pytest.raises(KeyError):
        t.text('does.not.exist')


def test_bindings_and_language_menu_keep_values_and_action_identity(tmp_path):
    from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QMainWindow, QTabWidget
    from archforge.localization import Translator
    from archforge.ui.language import bind, install_language_menu
    app = QApplication.instance() or QApplication([])
    t = Translator(settings_path=tmp_path / 'prefs.json')
    w = QMainWindow()
    settings = w.menuBar().addMenu('⚙ Ρυθμίσεις')
    w._work_menus = {'⚙ Ρυθμίσεις': settings}
    original = settings.addAction('Προσωπική εντολή')
    original.setData('stable-command-id')
    selected = []
    original.triggered.connect(lambda: selected.append(original.data()))
    save = settings.addAction('Αποθήκευση')
    save.setData('project.save')
    save.triggered.connect(lambda: selected.append(save.data()))
    bind(save, 'setText', 'command.save', translator=t)
    label = QLabel(w)
    field = QLineEdit('Τοίχος / Width', w)
    bind(label, 'setText', 'field.width', translator=t)
    tabs = QTabWidget(w)
    tabs.addTab(QLabel(), 'legacy')
    bind(tabs, 'setTabText', 'view.plan', prefix=(0,), translator=t)
    install_language_menu(w, translator=t)
    assert label.text() == 'Width'
    assert save.text() == 'Save'
    assert tabs.tabText(0) == 'Floor plan'
    en = w._language_actions['en']
    greek = w._language_actions['el']
    greek.trigger()
    assert label.text() == 'Πλάτος'
    assert save.text() == 'Αποθήκευση'
    assert tabs.tabText(0) == 'Κάτοψη'
    assert greek.isChecked() and not en.isChecked()
    assert field.text() == 'Τοίχος / Width'
    assert settings.actions()[0] is original
    original.trigger()
    save.trigger()
    assert selected == ['stable-command-id', 'project.save']
    before = len(settings.actions())
    install_language_menu(w, translator=t)
    assert len(settings.actions()) == before
    label.deleteLater()
    app.processEvents()
    t.set_language('en', persist=False)
    w.deleteLater()


def test_catalog_audit_uses_ids_not_menu_position():
    from scripts.toolbox.localization_audit import check_inventory
    from archforge.localization import Translator
    t = Translator(language='en')
    items = [{'id': 'stable.save', 'label_key': 'command.save', 'path': 'new/menu/place'}]
    assert check_inventory(items, t) == []
    items[0]['path'] = 'completely/different/menu'
    assert check_inventory(items, t) == []
    items.append({'id': 'stable.save', 'label_key': 'missing.label'})
    errors = check_inventory(items, t)
    assert any('duplicate' in e for e in errors)
    assert any('missing.label' in e for e in errors)


def test_property_labels_follow_language_without_changing_the_registry(tmp_path, monkeypatch):
    import archforge.localization as locale
    from archforge.ui.object_properties import PROPERTY_FIELDS, param_label, property_fields
    t = locale.Translator(settings_path=tmp_path / 'prefs.json')
    monkeypatch.setattr(locale, '_translator', t)
    assert property_fields('wall')[0]['label'] == 'Length'
    assert property_fields('door')[0]['label'] == 'Frame width'
    assert param_label('width') == 'Width'
    assert property_fields('wall')[0]['id'] == 'length'
    assert PROPERTY_FIELDS['wall'][0]['label'] == 'Μήκος'
    t.set_language('el', persist=False)
    assert property_fields('wall')[0]['label'] == 'Μήκος'
    assert param_label('width') == 'Πλάτος'


def test_saved_menu_paths_still_resolve_after_translating_labels(tmp_path):
    from PySide6.QtWidgets import QApplication, QMainWindow
    from archforge.localization import Translator
    from archforge.ui.language import bind
    from archforge.ui.toolbar_custom import catalog
    from archforge.ui.mouse_menus import _find_action, custom_entries, item_of_path, set_task
    app = QApplication.instance() or QApplication([])
    t = Translator(settings_path=tmp_path / 'prefs.json')
    w = QMainWindow()
    menu = w.menuBar().addMenu('Έργο')
    action = menu.addAction('Αποθήκευση')
    path = 'Έργο / Αποθήκευση'
    entry = item_of_path(path, action)
    set_task(w, 'empty', [entry])
    bind(menu, 'setTitle', 'menu.project', translator=t)
    bind(action, 'setText', 'command.save', translator=t)
    assert menu.title() == 'Project' and action.text() == 'Save'
    assert catalog(w)[path] is action
    assert _find_action(w, path) is action
    assert custom_entries(w, 'empty', [])[0]['label'] == 'Save'
    t.set_language('el', persist=False)
    assert catalog(w)[path] is action and _find_action(w, path) is action
    assert custom_entries(w, 'empty', [])[0]['label'] == 'Αποθήκευση'
    w.deleteLater()
    app.processEvents()


def test_real_window_language_switch_preserves_document_and_all_catalog_paths(tmp_path, monkeypatch):
    import copy
    import archforge.localization as locale
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.toolbar_custom import catalog
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    t = locale.Translator(settings_path=tmp_path / 'prefs.json')
    monkeypatch.setattr(locale, '_translator', t)
    w = MainWindow()
    before = copy.deepcopy(w.doc.to_dict())
    commands = catalog(w)
    undo_size = len(w.stack.done)
    w._language_actions['el'].trigger()
    after = catalog(w)
    assert set(after) == set(commands)
    assert all(after[key] is action for key, action in commands.items())
    assert w.doc.to_dict() == before
    assert len(w.stack.done) == undo_size
    w._mark_clean()
    w.close()
    w.deleteLater()
    app.processEvents()


def test_inventory_binding_is_independent_of_order_and_validates_before_mutation(tmp_path):
    from PySide6.QtWidgets import QApplication, QMainWindow
    from archforge.localization import Translator
    from archforge.ui.language import bind_inventory
    app = QApplication.instance() or QApplication([])
    t = Translator(settings_path=tmp_path / 'prefs.json')
    w = QMainWindow()
    menu = w.menuBar().addMenu('Έργο')
    save = menu.addAction('Αποθήκευση')
    new = menu.addAction('Νέο')
    objects = {'project.save': save, 'project.new': new}
    inventory = [{'id': 'project.save', 'label_key': 'command.save'},
                 {'id': 'project.missing', 'label_key': 'command.new'}]
    with pytest.raises(ValueError, match='project.missing'):
        bind_inventory(objects, inventory, translator=t)
    assert save.text() == 'Αποθήκευση'                    # no partially translated tree on a bad inventory
    inventory[1]['id'] = 'project.new'
    inventory[1]['label_key'] = 'project.named'
    with pytest.raises(ValueError, match='formatting values'):
        bind_inventory(objects, inventory, translator=t)
    assert save.text() == 'Αποθήκευση'
    inventory[1]['label_key'] = 'command.new'
    bind_inventory(objects, list(reversed(inventory)), translator=t)
    assert menu.actions() == [save, new]
    assert [a.text() for a in menu.actions()] == ['Save', 'New project']
    assert save.property('archforge_command_id') == 'project.save'
    t.set_language('el', persist=False)
    assert [a.text() for a in menu.actions()] == ['Αποθήκευση', 'Νέο έργο']
    w.deleteLater()
    app.processEvents()
