"""Presentation text by stable ids, independent of menu position and the Document.

English is the source catalog. Other JSON catalogs may be partial; missing keys
fall back to English. Values are formatted *after* translation, so names written
by the human are never interpreted as translation keys. No network or AI needed.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
from string import Formatter
import tempfile
from typing import Callable

log = logging.getLogger(__name__)
_CODE = re.compile(r'^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$')


def builtin_catalog_dir() -> Path:
    return Path(__file__).with_name('catalogs')


def _fields(text: str):
    """Require the same named fields, conversions and format specs in each language."""
    fields = []
    for _literal, field, spec, conversion in Formatter().parse(text):
        if field is not None:
            if not field.isidentifier():
                raise ValueError(f'Only named placeholders are supported: {field!r}')
            fields.append((field, spec, conversion))
    return sorted(fields)


def _load_catalogs(folder: Path):
    catalogs, errors = {}, []
    for path in sorted(folder.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf8'))
            code = data['code']
            if not isinstance(code, str) or not _CODE.fullmatch(code) or path.stem != code:
                raise ValueError('filename and valid language code must match')
            if not isinstance(data.get('native_name'), str) or not data['native_name'].strip():
                raise ValueError('native_name is required')
            messages = data['messages']
            if not isinstance(messages, dict):
                raise ValueError('messages must be an object')
            for key, value in messages.items():
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f'{key}: translation must be nonempty text')
                _fields(value)
            catalogs[code] = data
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f'{path.name}: {exc}')
    english = catalogs.get('en', {}).get('messages')
    if english is None:
        errors.append('en.json: English source catalog is required')
    else:
        for code, data in catalogs.items():
            for key, value in data['messages'].items():
                if key not in english:
                    errors.append(f'{code}: unknown source key {key}')
                elif _fields(value) != _fields(english[key]):
                    errors.append(f'{code}: {key}: placeholders differ from English')
    return catalogs, errors


def validate_catalogs(folder=None) -> list[str]:
    """Read-only validation for CI and the shared localization audit tool."""
    return _load_catalogs(Path(folder) if folder is not None else builtin_catalog_dir())[1]


def _settings_path() -> Path:
    from archforge.library.assets import data_dir
    return data_dir() / 'language.json'


class Translator:
    def __init__(self, *, catalog_dir=None, settings_path=None, language=None):
        self.catalog_dir = Path(catalog_dir) if catalog_dir is not None else builtin_catalog_dir()
        self.settings_path = Path(settings_path) if settings_path is not None else _settings_path()
        self._catalogs, errors = _load_catalogs(self.catalog_dir)
        if errors:
            raise ValueError('\n'.join(errors))
        self._listeners: list[Callable[[], None]] = []
        requested = language or os.environ.get('ARCHFORGE_LANGUAGE') or self._saved_language()
        if requested not in self._catalogs:
            log.warning('Unsupported saved language %r; using English', requested)
            requested = 'en'
        self.language = requested

    def _saved_language(self) -> str:
        try:
            data = json.loads(self.settings_path.read_text(encoding='utf8'))
            return str(data.get('language', 'en')) if isinstance(data, dict) else 'en'
        except FileNotFoundError:
            return 'en'
        except (OSError, ValueError) as exc:
            log.warning('Could not read language preference: %s', exc)
            return 'en'

    def languages(self):
        codes = sorted(self._catalogs, key=lambda code: (code != 'en', code))
        return tuple((code, self._catalogs[code]['native_name']) for code in codes)

    def keys(self):
        return frozenset(self._catalogs['en']['messages'])

    def source(self, key: str) -> str:
        """Canonical English template, for source validation and stable new label aliases."""
        return self._catalogs['en']['messages'][key]

    def text(self, key: str, **values) -> str:
        source = self._catalogs['en']['messages'][key]
        template = self._catalogs[self.language]['messages'].get(key, source)
        return template.format(**values)

    def subscribe(self, callback):
        """Return a disconnect function; Qt bindings release it when their object dies."""
        self._listeners.append(callback)

        def disconnect():
            if callback in self._listeners:
                self._listeners.remove(callback)
        return disconnect

    def set_language(self, code: str, *, persist=True):
        if code not in self._catalogs:
            raise ValueError(f'Unsupported language: {code!r}')
        if persist:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix='language-', suffix='.tmp', dir=self.settings_path.parent)
            try:
                with os.fdopen(fd, 'w', encoding='utf8') as stream:
                    json.dump({'language': code}, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, self.settings_path)
            finally:
                Path(name).unlink(missing_ok=True)
        if self.language != code:
            self.language = code
            for callback in tuple(self._listeners):
                callback()


_translator = None


def translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


def text(key: str, **values) -> str:
    return translator().text(key, **values)


def validate_inventory(items, service=None) -> list[str]:
    """Validate display keys against stable ids; menu paths are descriptive only."""
    t = service if service is not None else translator()
    errors, seen = [], set()
    if not isinstance(items, list):
        return ['inventory must contain an array of items']
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f'item {index}: expected an object')
            continue
        identity = item.get('id')
        if not isinstance(identity, str) or not identity.strip():
            errors.append(f'item {index}: stable id is required')
        elif identity in seen:
            errors.append(f'duplicate id: {identity}')
        else:
            seen.add(identity)
        label = item.get('label_key')
        if not isinstance(label, str) or label not in t.keys():
            errors.append(f'{identity}: unknown label_key {label!r}')
        tip = item.get('tooltip_key')
        if tip is not None and (not isinstance(tip, str) or tip not in t.keys()):
            errors.append(f'{identity}: unknown tooltip_key {tip!r}')
    return errors
