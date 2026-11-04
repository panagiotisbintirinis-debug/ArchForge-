"""Explicit text bindings: stable keys change labels without replacing commands.

Existing controls are migrated through bind(), not by walking all widget text:
a project name or input value must never be guessed to be an interface label.
"""
from __future__ import annotations

import weakref

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QMessageBox
from shiboken6 import isValid

from archforge.localization import translator as default_translator, validate_inventory

KEY_PROPERTY = 'archforge_translation_key'
SOURCE_TEXT_PROPERTY = 'archforge_source_action_text'


def source_text(action):
    """Existing saved paths use the source label, never the selected display language.

    This compatibility alias is not the new command id. The inventory still owns
    that id; callers migrate to ids separately without invalidating saved paths.
    """
    value = action.property(SOURCE_TEXT_PROPERTY)
    return str(value) if value is not None else action.text()


def bind(obj, setter, key, *, prefix=(), values=None, translator=None):
    """Bind one label/title/tooltip/tab, without changing its id, data or callback.

    ``prefix`` holds setter arguments before the text (e.g. the tab index).
    ``values`` is a callback returning formatting values, evaluated on refresh.
    Returns the refresh callable for dynamic messages and document refreshes.
    """
    t = translator if translator is not None else default_translator()
    if key not in t.keys():
        raise KeyError(key)
    source_action = obj if isinstance(obj, QAction) and setter == 'setText' else (
        obj.menuAction() if isinstance(obj, QMenu) and setter == 'setTitle' else None)
    if source_action is not None and source_action.property(SOURCE_TEXT_PROPERTY) is None:
        source_action.setProperty(SOURCE_TEXT_PROPERTY, source_action.text() or t.source(key))
    target = weakref.ref(obj)
    obj.setProperty(KEY_PROPERTY + '_' + setter, key)

    def refresh():
        live = target()
        if live is not None and isValid(live):
            args = values() if values is not None else {}
            getattr(live, setter)(*prefix, t.text(key, **args))

    disconnect = t.subscribe(refresh)
    obj.destroyed.connect(lambda *_: disconnect())
    refresh()
    return refresh


def bind_inventory(actions_by_id, items, *, translator=None):
    """Connect the approved inventory to *existing* actions/menus, independent of location.

    Resolve all ids and validate all keys before changing any label. This is the
    adapter for the mockup inventory; it does not discover commands by visible text.
    The caller must first migrate any remaining text-based consumers of those actions.
    """
    t = translator if translator is not None else default_translator()
    errors = validate_inventory(items, t)
    if errors:
        raise ValueError('\n'.join(errors))
    seen = set()
    for item in items:
        for role in ('label_key', 'tooltip_key'):
            if item.get(role):
                try:
                    t.text(item[role])
                except (KeyError, ValueError) as exc:
                    errors.append(f'{item["id"]}: {role} needs formatting values: {exc}')
        target = actions_by_id.get(item['id'])
        if not isinstance(target, (QAction, QMenu)) or not isValid(target):
            errors.append(f'{item["id"]}: missing live QAction or QMenu')
            continue
        action = target.menuAction() if isinstance(target, QMenu) else target
        identity = action.property('archforge_command_id')
        if identity is not None and identity != item['id']:
            errors.append(f'{item["id"]}: existing command id {identity!r} differs')
        if id(action) in seen:
            errors.append(f'{item["id"]}: same action has more than one inventory id')
        seen.add(id(action))
    if errors:
        raise ValueError('\n'.join(errors))
    for item in items:
        target = actions_by_id[item['id']]
        action = target.menuAction() if isinstance(target, QMenu) else target
        action.setProperty('archforge_command_id', item['id'])
        bind(target, 'setTitle' if isinstance(target, QMenu) else 'setText', item['label_key'], translator=t)
        if item.get('tooltip_key'):
            bind(action, 'setToolTip', item['tooltip_key'], translator=t)


def install_language_menu(window, *, translator=None):
    """Append the language selector to the existing Settings menu, once.

    The source menu registry stays untouched. The mockup/menu inventory can move
    this same QMenu later; no command paths, shortcut data or Document state change.
    """
    if hasattr(window, '_language_menu'):
        return window._language_menu
    t = translator if translator is not None else default_translator()
    menus = getattr(window, '_work_menus', None) or getattr(window, '_main_menus', {})
    settings = menus.get('⚙ Ρυθμίσεις')
    if settings is None:
        raise RuntimeError('Install language selection after the Settings menu exists')
    menu = QMenu(settings)
    menu.setObjectName('language_menu')
    menu.menuAction().setProperty('archforge_command_id', 'settings.language')
    bind(menu, 'setTitle', 'language.title', translator=t)
    group = QActionGroup(menu)
    group.setExclusive(True)
    actions = {}

    def choose(code):
        try:
            t.set_language(code)
        except OSError as exc:
            update()
            QMessageBox.warning(window, t.text('language.save_error'), str(exc))

    for code, native in t.languages():
        action = menu.addAction(native)              # autonyms: discoverable in every selected language
        action.setData(code)
        action.setObjectName('language_' + code)
        action.setProperty('archforge_command_id', 'settings.language.' + code)
        action.setCheckable(True)
        group.addAction(action)
        action.triggered.connect(lambda _checked=False, code=code: choose(code))
        actions[code] = action

    def update():
        for code, action in actions.items():
            if isValid(action):
                blocker = QSignalBlocker(action)
                action.setChecked(t.language == code)
                del blocker

    disconnect = t.subscribe(update)
    menu.destroyed.connect(lambda *_: disconnect())
    update()
    settings.addMenu(menu)
    window._language_menu, window._language_actions = menu, actions
    window._language_group = group
    return menu
