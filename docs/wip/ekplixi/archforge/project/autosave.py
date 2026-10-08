"""Αυτόματη αποθήκευση και επαναφορά μετά από κατάρρευση (χωρίς Qt).

Κάθε συνεδρία της εφαρμογής έχει ένα ``session_id``. Στον φάκελο αυτόματης
αποθήκευσης (``~/.archforge/autosave`` ή ``$ARCHFORGE_AUTOSAVE_DIR``) γράφει:

* ``<session>.archforge.autosave``      το πιο πρόσφατο αντίγραφο του Document
* ``<session>.archforge.autosave.1 …``  παλαιότερα αντίγραφα (κυκλικά, ``keep`` συνολικά)
* ``<session>.meta.json``               μεταδεδομένα: pid, αρχικό αρχείο έργου,
  χρόνος, πλήθος στοιχείων, έκδοση εφαρμογής. Το mtime του είναι ο «παλμός»
  (heartbeat) της ζωντανής συνεδρίας.

Όλες οι εγγραφές είναι ατομικές (προσωρινό αρχείο + ``os.replace``), ώστε μια
κατάρρευση στη μέση της εγγραφής να μην αφήνει μισό αρχείο. Γράφουμε μόνο όταν
το περιεχόμενο του Document άλλαξε από την τελευταία αυτόματη αποθήκευση
(σύγκριση hash του σειριοποιημένου ``to_dict``: πιάνει και αλλαγές που δεν
περνούν από το CommandStack, π.χ. ``room_data``).

Σε κανονικό κλείσιμο η συνεδρία σβήνει τα αρχεία της (``finish``). Ό,τι μένει
στον φάκελο ανήκει σε συνεδρία που κατέρρευσε· το ``find_recoverable`` το
βρίσκει όταν η διεργασία-ιδιοκτήτης δεν ζει πια ή ο παλμός της είναι παλιός.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from archforge.core.model import Document

log = logging.getLogger(__name__)

ENV_DIR = 'ARCHFORGE_AUTOSAVE_DIR'
AUTOSAVE_SUFFIX = '.archforge.autosave'
META_SUFFIX = '.meta.json'
DEFAULT_KEEP = 3
# Συνεδρία χωρίς παλμό τόσα λεπτά θεωρείται νεκρή, ακόμη κι αν το pid
# φαίνεται ζωντανό (επαναχρησιμοποίηση pid) ή δεν μπορεί να ελεγχθεί.
DEFAULT_STALE_MINUTES = 15.0


def _app_version() -> Optional[str]:
    try:
        from archforge import __version__
        return str(__version__)
    except Exception:
        return None


def autosave_dir(directory=None) -> Path:
    """Ο φάκελος αυτόματης αποθήκευσης: όρισμα > ``$ARCHFORGE_AUTOSAVE_DIR`` > ``~/.archforge/autosave``."""
    if directory is None:
        directory = os.environ.get(ENV_DIR) or (Path.home() / '.archforge' / 'autosave')
    return Path(directory)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def pid_alive(pid) -> Optional[bool]:
    """True/False αν η διεργασία ζει· None αν δεν μπορεί να ελεγχθεί.

    Στα Windows **δεν** καλούμε ``os.kill(pid, 0)``: εκεί τερματίζει τη
    διεργασία. Χρησιμοποιούμε OpenProcess/GetExitCodeProcess μέσω ctypes.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        import psutil  # type: ignore
        return bool(psutil.pid_exists(pid))
    except ImportError:
        pass
    except Exception:
        return None
    if sys.platform.startswith('win'):
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            ERROR_ACCESS_DENIED = 5
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return ctypes.get_last_error() == ERROR_ACCESS_DENIED
            try:
                code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return None
                return code.value == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


@dataclass
class Recoverable:
    """Αυτόματη αποθήκευση που άφησε μια συνεδρία που δεν έκλεισε κανονικά."""
    session_id: str
    path: Path                      # το πιο πρόσφατο ``.archforge.autosave``
    meta: dict = field(default_factory=dict)

    @property
    def original_path(self) -> Optional[str]:
        return self.meta.get('original_path')

    @property
    def timestamp(self) -> float:
        try:
            return float(self.meta.get('timestamp'))
        except (TypeError, ValueError):
            try:
                return self.path.stat().st_mtime
            except OSError:
                return 0.0

    @property
    def entity_count(self) -> int:
        try:
            return int(self.meta.get('entity_count', 0))
        except (TypeError, ValueError):
            return 0


def _session_files(directory: Path, session_id: str) -> List[Path]:
    prefix = session_id + '.'
    try:
        return [p for p in directory.iterdir() if p.name.startswith(prefix)]
    except OSError:
        return []


class AutoSaver:
    """Γράφει περιοδικά αντίγραφα του Document για μία συνεδρία."""

    def __init__(self, directory=None, session_id: Optional[str] = None, keep: int = DEFAULT_KEEP,
                 app_version: Optional[str] = None):
        self.directory = autosave_dir(directory)
        self.session_id = session_id or uuid.uuid4().hex
        self.keep = max(1, int(keep))
        self.app_version = app_version if app_version is not None else _app_version()
        self._last_hash: Optional[str] = None
        self.save_count = 0

    @property
    def path(self) -> Path:
        return self.directory / (self.session_id + AUTOSAVE_SUFFIX)

    @property
    def meta_path(self) -> Path:
        return self.directory / (self.session_id + META_SUFFIX)

    def rotation_path(self, index: int) -> Path:
        return self.path if index == 0 else Path(f'{self.path}.{index}')

    def autosave(self, doc: Document, original_path=None, force: bool = False) -> bool:
        """Γράφει το ``doc`` αν άλλαξε από την προηγούμενη φορά. Επιστρέφει True αν έγραψε."""
        data = json.dumps(doc.to_dict(), ensure_ascii=False, sort_keys=True).encode('utf8')
        digest = hashlib.sha256(data).hexdigest()
        if not force and digest == self._last_hash:
            return False
        self._rotate()
        _atomic_write_bytes(self.path, data)
        meta = {
            'session_id': self.session_id,
            'pid': os.getpid(),
            'original_path': str(original_path) if original_path else None,
            'timestamp': time.time(),
            'entity_count': len(doc.entities),
            'app_version': self.app_version,
            'sha256': digest,
        }
        _atomic_write_bytes(self.meta_path, json.dumps(meta, ensure_ascii=False, indent=2).encode('utf8'))
        self._last_hash = digest
        self.save_count += 1
        return True

    def heartbeat(self) -> None:
        """Δείχνει ότι η συνεδρία ζει (ανανεώνει το mtime των μεταδεδομένων, αν υπάρχουν)."""
        try:
            if self.meta_path.exists():
                os.utime(self.meta_path, None)
        except OSError:
            pass

    def _rotate(self) -> None:
        if not self.path.exists():
            return
        oldest = self.rotation_path(self.keep - 1)
        if self.keep == 1:
            return  # το os.replace της νέας εγγραφής αντικαθιστά το μοναδικό αντίγραφο
        try:
            oldest.unlink()
        except FileNotFoundError:
            pass
        for index in range(self.keep - 2, -1, -1):
            src = self.rotation_path(index)
            if src.exists():
                os.replace(src, self.rotation_path(index + 1))

    def finish(self) -> None:
        """Κανονικό κλείσιμο: σβήνει όλα τα αρχεία αυτής της συνεδρίας."""
        _remove_session(self.directory, self.session_id)
        self._last_hash = None


def _remove_session(directory: Path, session_id: str) -> None:
    for path in _session_files(directory, session_id):
        try:
            path.unlink()
        except OSError as exc:
            log.warning('Δεν σβήστηκε %s: %s', path, exc)


def _read_meta(meta_path: Path) -> dict:
    try:
        with open(meta_path, encoding='utf8') as handle:
            meta = json.load(handle)
        return meta if isinstance(meta, dict) else {}
    except (OSError, ValueError):
        return {}


def find_recoverable(directory=None, exclude_session: Optional[str] = None,
                     stale_minutes: float = DEFAULT_STALE_MINUTES, now: Optional[float] = None) -> List[Recoverable]:
    """Αυτόματες αποθηκεύσεις συνεδριών που κατέρρευσαν, νεότερη πρώτη.

    Μια συνεδρία θεωρείται νεκρή όταν η διεργασία της δεν ζει, ή όταν ο
    παλμός της (mtime των μεταδεδομένων) είναι παλαιότερος από
    ``stale_minutes`` και δεν είναι η δική μας διεργασία.
    """
    directory = autosave_dir(directory)
    now = time.time() if now is None else now
    found: List[Recoverable] = []
    try:
        candidates = sorted(directory.glob('*' + AUTOSAVE_SUFFIX))
    except OSError:
        return found
    for path in candidates:
        session_id = path.name[:-len(AUTOSAVE_SUFFIX)]
        if not session_id or session_id == exclude_session:
            continue
        meta_path = directory / (session_id + META_SUFFIX)
        meta = _read_meta(meta_path)
        pid = meta.get('pid')
        try:
            heartbeat = meta_path.stat().st_mtime
        except OSError:
            heartbeat = path.stat().st_mtime if path.exists() else 0.0
        stale = (now - heartbeat) > stale_minutes * 60.0
        alive = pid_alive(pid) if pid is not None else None
        try:
            ours = int(pid) == os.getpid()
        except (TypeError, ValueError):
            ours = False
        if alive is False:
            dead = True
        elif ours:
            # Ίδιο pid με εμάς αλλά άλλη συνεδρία (π.χ. δεύτερο παράθυρο ή
            # επαναχρησιμοποιημένο pid): μόνο ο παλιός παλμός τη χαρακτηρίζει νεκρή.
            dead = stale
        else:
            # Ζωντανή ή άγνωστη διεργασία: νεκρή μόνο αν σταμάτησε ο παλμός.
            dead = stale
        if dead:
            found.append(Recoverable(session_id=session_id, path=path, meta=meta))
    found.sort(key=lambda item: item.timestamp, reverse=True)
    return found


def _coerce(item) -> tuple:
    if isinstance(item, Recoverable):
        return item.path.parent, item.session_id, item.path
    path = Path(item)
    name = path.name
    for suffix in (META_SUFFIX, AUTOSAVE_SUFFIX):
        if name.endswith(suffix):
            session_id = name[:-len(suffix)]
            return path.parent, session_id, path.parent / (session_id + AUTOSAVE_SUFFIX)
    if AUTOSAVE_SUFFIX + '.' in name:
        session_id = name.split(AUTOSAVE_SUFFIX + '.', 1)[0]
        return path.parent, session_id, path
    raise ValueError(f'Δεν είναι αρχείο αυτόματης αποθήκευσης: {path}')


def recover(item) -> Document:
    """Φορτώνει το Document μιας αυτόματης αποθήκευσης.

    Αν το πιο πρόσφατο αντίγραφο είναι κατεστραμμένο, δοκιμάζει τα παλαιότερα.
    """
    directory, session_id, path = _coerce(item)
    candidates = [path] + sorted(
        (p for p in _session_files(directory, session_id)
         if p.name.startswith(session_id + AUTOSAVE_SUFFIX + '.') and p.name.rsplit('.', 1)[-1].isdigit()),
        key=lambda p: int(p.name.rsplit('.', 1)[-1]),
    )
    error: Optional[Exception] = None
    for candidate in candidates:
        try:
            with open(candidate, encoding='utf8') as handle:
                return Document.from_dict(json.load(handle))
        except Exception as exc:  # κατεστραμμένο ή ελλιπές· δοκίμασε το επόμενο
            error = exc
            log.warning('Αποτυχία ανάγνωσης %s: %s', candidate, exc)
    raise ValueError(f'Δεν διαβάστηκε καμία αυτόματη αποθήκευση για {session_id}: {error}')


def discard(item) -> None:
    """Σβήνει όλα τα αρχεία (αντίγραφα και μεταδεδομένα) μιας αυτόματης αποθήκευσης."""
    directory, session_id, _ = _coerce(item)
    _remove_session(directory, session_id)
