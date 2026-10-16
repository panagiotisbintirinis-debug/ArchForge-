"""Project files that survive crashes, bad disks and old versions.

The Document stays the only design truth; this module only moves its
``to_dict()`` to and from disk, more carefully than ``Document.save``:

* **Atomic write** — the file is written next to its target under a temporary
  name, flushed to disk and then swapped in with ``os.replace``.  A crash or a
  full disk mid-save leaves the previous file intact, never half a file.
* **Backups** — before a save over an existing project the old file is kept as
  ``έργο.archforge.bak`` (newest), ``.bak2``, ``.bak3``; older ones drop off.
* **Recovery (autosave)** — a separate file in the user data folder
  (``<data>/recovery/``), never over the user's own project.  It carries the
  project path and the time, so after a crash the program can offer it back.
* **Check on open** — a damaged or truncated file, or entities that no longer
  pass their schema, do not crash the program: what can be loaded is loaded
  and the rest is listed in Greek (``LoadReport``), with the backups offered.
* **Version** — the ``format`` field is the file version.  Older projects
  (no ``format``, or a lower one) are brought up to the current one on load;
  only missing fields are filled with the defaults the program always used.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field, fields
from typing import List, Optional

from archforge.core.model import Document, Entity

# The version Document.to_dict() writes (kept in step with model.py).
FORMAT_VERSION = 7
BACKUP_COUNT = 3
RECOVERY_SUFFIX = '.recovery.json'
_ENTITY_FIELDS = {f.name for f in fields(Entity)}


class ProjectFileError(Exception):
    """A project file that cannot be read at all; ``str()`` is a Greek message."""


# --------------------------------------------------------------- atomic write

def atomic_write_text(path, text):
    """Write ``text`` to ``path`` so that the file is either the old or the new one, never half."""
    path = os.path.abspath(os.fspath(path))
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(handle, 'w', encoding='utf8') as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        if os.path.exists(path):
            try:
                shutil.copymode(path, tmp)      # keep the user's file permissions
            except OSError:
                pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path, data, indent=2):
    atomic_write_text(path, json.dumps(data, indent=indent))


# -------------------------------------------------------------------- backups

def backup_paths(path):
    """Backup files of a project, newest first: έργο.archforge.bak, .bak2, .bak3."""
    path = os.fspath(path)
    return [path + '.bak'] + [f'{path}.bak{n}' for n in range(2, BACKUP_COUNT + 1)]


def existing_backups(path):
    return [p for p in backup_paths(path) if os.path.isfile(p)]


def rotate_backups(path):
    """Keep the file about to be overwritten as the newest backup (last BACKUP_COUNT kept)."""
    if not os.path.isfile(path):
        return None
    names = backup_paths(path)
    for older, newer in zip(reversed(names[1:]), reversed(names[:-1])):
        if os.path.isfile(newer):
            os.replace(newer, older)
    shutil.copy2(path, names[0])
    return names[0]


def save_project(doc, path):
    """Save the Document: backup of the previous file, then an atomic write."""
    data = doc.to_dict()
    text = json.dumps(data, indent=2)       # serialise first: a failure here touches no file
    rotate_backups(path)
    atomic_write_text(path, text)
    return path


# ------------------------------------------------------------ version upgrade

def upgrade_project_data(data):
    """Bring a project dict of any older ``format`` to the current one.

    Returns ``(data, notes, rejected, version)``: Greek notes on what was converted and
    the raw entities that cannot even be read as entities.  Only fields that
    are missing get the defaults the program always used; nothing is guessed.
    """
    if not isinstance(data, dict):
        raise ProjectFileError('Το αρχείο δεν είναι έργο ArchForge (λείπει η δομή του έργου).')
    data = dict(data)
    notes, rejected = [], []
    try:
        version = int(data.get('format', 0))
    except (TypeError, ValueError):
        version = 0
    if version > FORMAT_VERSION:
        notes.append(f'Το αρχείο είναι από νεότερη έκδοση του ArchForge (μορφή {version}, '
                     f'αυτή διαβάζει έως {FORMAT_VERSION}). Ό,τι δεν αναγνωρίζεται παραλείπεται.')
    elif version < FORMAT_VERSION:
        notes.append(f'Παλιό έργο (μορφή {version}): μετατράπηκε στη μορφή {FORMAT_VERSION}. '
                     'Με την αποθήκευση γράφεται στη νέα μορφή.')
    for key, default in (('levels', {'Ground': 0.0}), ('materials', {}), ('constructions', {}),
                         ('room_data', {}), ('room_bindings', {}), ('dependencies', {})):
        if not isinstance(data.get(key), dict):
            data[key] = default
    for key in ('entities', 'surface_modifiers'):
        if not isinstance(data.get(key), list):
            data[key] = []
    if not isinstance(data.get('work_plane'), dict):
        data.pop('work_plane', None)
    entities = []
    for raw in data['entities']:
        if not isinstance(raw, dict) or 'kind' not in raw or not isinstance(raw.get('params', {}), dict):
            rejected.append({'kind': str(raw.get('kind', '')) if isinstance(raw, dict) else '',
                             'id': str(raw.get('id', '')) if isinstance(raw, dict) else '',
                             'name': '', 'reason': 'ελλιπής εγγραφή στοιχείου'})
            continue
        raw = {key: value for key, value in raw.items() if key in _ENTITY_FIELDS}
        raw.setdefault('params', {})
        entities.append(raw)
    data['entities'] = entities
    data['format'] = FORMAT_VERSION
    return data, notes, rejected, version


# --------------------------------------------------------------- load + check

@dataclass
class LoadReport:
    doc: Document
    path: str
    loaded: int = 0
    skipped: List[dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    upgraded_from: Optional[int] = None

    @property
    def ok(self):
        return not self.skipped

    def message(self):
        """Greek summary for the human: what was loaded, what was left out and why."""
        lines = [f'Φορτώθηκαν {self.loaded} στοιχεία.']
        if self.skipped:
            labels = _kind_labels()
            lines.append(f'Παραλείφθηκαν {len(self.skipped)} στοιχεία που δεν περνούν τον έλεγχο:')
            for item in self.skipped[:12]:
                label = labels.get(item['kind'], item['kind'] or 'άγνωστο')
                name = f' «{item["name"]}»' if item.get('name') else ''
                lines.append(f'  • {label}{name}: {item["reason"]}')
            if len(self.skipped) > 12:
                lines.append(f'  • … και άλλα {len(self.skipped) - 12}')
        lines.extend(self.notes)
        return '\n'.join(lines)


def _kind_labels():
    try:
        from archforge.ui.project_outline import KIND_LABELS
        return dict(KIND_LABELS, surface_modifier='Τροποποίηση επιφάνειας')
    except Exception:
        return {}


def read_project_json(path):
    try:
        with open(path, encoding='utf8') as handle:
            text = handle.read()
    except FileNotFoundError:
        raise ProjectFileError(f'Δεν βρέθηκε το αρχείο «{os.path.basename(path)}».') from None
    except UnicodeDecodeError:
        raise ProjectFileError(f'Το αρχείο «{os.path.basename(path)}» δεν είναι έργο ArchForge '
                               '(δεν είναι κείμενο).') from None
    except OSError as exc:
        raise ProjectFileError(f'Δεν διαβάζεται το αρχείο «{os.path.basename(path)}»: {exc.strerror or exc}.') from None
    if not text.strip():
        raise ProjectFileError(f'Το αρχείο «{os.path.basename(path)}» είναι άδειο.')
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProjectFileError(
            f'Το αρχείο «{os.path.basename(path)}» είναι κατεστραμμένο ή ελλιπές '
            f'(σφάλμα στη γραμμή {exc.lineno}, στήλη {exc.colno}) και δεν ανοίγει.') from None


def load_project_data(data, path=''):
    """Tolerant load of a project dict: never raises for bad entities, reports them."""
    data, notes, rejected, version = upgrade_project_data(data)
    skipped = list(rejected)
    try:
        doc = Document.from_dict(data, skipped=skipped)
    except Exception as exc:
        # Levels / work plane in a shape nothing can read: keep the entities.
        notes.append(f'Οι ρυθμίσεις ορόφων/επιπέδου εργασίας ήταν άκυρες και πήραν τις προεπιλογές ({exc}).')
        data = dict(data)
        data.pop('work_plane', None)
        data['levels'] = {'Ground': 0.0}
        skipped = list(rejected)
        doc = Document.from_dict(data, skipped=skipped)
    return LoadReport(doc=doc, path=os.fspath(path), loaded=len(doc.entities),
                      skipped=skipped, notes=notes,
                      upgraded_from=version if version < FORMAT_VERSION else None)


def load_project(path):
    """Open a project file with the check: raises ProjectFileError only if nothing can be read."""
    return load_project_data(read_project_json(path), path)


# ------------------------------------------------------------------- recovery

def recovery_dir():
    from archforge.library.assets import data_dir
    return os.path.join(os.fspath(data_dir()), 'recovery')


def new_recovery_path():
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    # Unique even for two windows of one process started in the same second.
    return os.path.join(recovery_dir(), f'session-{stamp}-{os.getpid()}-{uuid.uuid4().hex[:6]}{RECOVERY_SUFFIX}')


def write_recovery(path, doc_data, project_path=None, saved_at=None):
    """Write an autosave snapshot (a ``to_dict()``) as a recovery file, atomically.

    Plain ``json.dump`` without indent runs the pure-Python encoder in small
    pieces, so a background thread writing a large project leaves the UI
    thread (mouse, redraws) free between pieces.
    """
    payload = {
        'archforge_recovery': 1,
        'saved_at': float(saved_at if saved_at is not None else time.time()),
        'project_path': os.fspath(project_path) if project_path else None,
        'document': doc_data,
    }
    path = os.path.abspath(os.fspath(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix='.autosave.', suffix='.tmp', dir=os.path.dirname(path))
    try:
        with os.fdopen(handle, 'w', encoding='utf8') as out:
            json.dump(payload, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


@dataclass
class RecoveryInfo:
    path: str
    saved_at: float
    project_path: Optional[str]
    entity_count: Optional[int] = None

    @property
    def project_name(self):
        return os.path.basename(self.project_path) if self.project_path else 'Έργο χωρίς όνομα'

    @property
    def when(self):
        return datetime.datetime.fromtimestamp(self.saved_at).strftime('%d/%m/%Y %H:%M')

    def is_newer_than_project(self):
        """True when the recovery holds work the project file does not (a crash, not a later save)."""
        if not self.project_path or not os.path.isfile(self.project_path):
            return True
        return os.path.getmtime(self.project_path) < self.saved_at

    def read_document_data(self):
        payload = read_project_json(self.path)
        if not isinstance(payload, dict) or 'document' not in payload:
            raise ProjectFileError('Το αρχείο ανάκτησης είναι ελλιπές.')
        return payload['document']


def read_recovery_info(path):
    try:
        with open(path, encoding='utf8') as handle:
            payload = json.load(handle)
        entities = payload.get('document', {}).get('entities')
        return RecoveryInfo(path=os.fspath(path), saved_at=float(payload['saved_at']),
                            project_path=payload.get('project_path'),
                            entity_count=len(entities) if isinstance(entities, list) else None)
    except Exception:
        return None


def list_recoveries(exclude=()):
    """Recovery files in the data folder, newest first (``exclude``: this session's own)."""
    folder = recovery_dir()
    if not os.path.isdir(folder):
        return []
    skip = {os.path.abspath(p) for p in exclude if p}
    found = []
    for name in os.listdir(folder):
        path = os.path.abspath(os.path.join(folder, name))
        if not name.endswith(RECOVERY_SUFFIX) or path in skip:
            continue
        info = read_recovery_info(path)
        if info is not None:
            found.append(info)
        else:
            found.append(RecoveryInfo(path=path, saved_at=os.path.getmtime(path), project_path=None))
    return sorted(found, key=lambda info: info.saved_at, reverse=True)


def remove_recovery(path):
    for item in (path, os.fspath(path) + '.lock'):
        try:
            os.unlink(item)
        except OSError:
            pass
