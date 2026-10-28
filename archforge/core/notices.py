"""«Δεν υπολογίστηκε» — a calculation that fails is said, never swallowed into 0 / [] / None (λίστα εργασιών Α3 Β).

Before: ``except Exception: inner = 0.0`` — the interior plaster vanished from the quote and the total looked
complete.  Now such a place calls ``not_computed(code, message, entity_id, exc)`` and keeps its fallback; whatever
the user is running (a quote, a sheet, a check) gathers the notices with ``collecting()`` and shows them next to
the result («ελλιπές: …»).  Outside a ``collecting()`` they are logged and kept in ``recent()``.

``Issue`` is the one record for this and for geometry (``geometry.backend.GeometryIssue`` is the same class).
"""
from __future__ import annotations

import collections
import contextlib
import logging
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger('archforge')


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    entity_id: Optional[str] = None


_collectors: List[List[Issue]] = []
_recent = collections.deque(maxlen=200)    # (serial, Issue)
_serial = 0
_logged = set()                            # each distinct notice is logged once (a redraw may repeat it)


def not_computed(code, message, entity_id=None, exc=None):
    """Record that ``message`` (Greek, for the user) could not be computed; returns the Issue."""
    text = f'{message} ({type(exc).__name__}: {exc})' if exc is not None else str(message)
    issue = Issue('warning', str(code), text, None if entity_id is None else str(entity_id))
    global _serial
    if issue not in _logged and len(_logged) < 10000:
        _logged.add(issue)
        log.warning('not computed: %s — %s', issue.code, issue.message)
    _serial += 1
    _recent.append((_serial, issue))
    for bucket in _collectors:
        bucket.append(issue)
    return issue


@contextlib.contextmanager
def collecting():
    """``with collecting() as found:`` — the notices raised inside, once each, in order."""
    bucket: List[Issue] = []
    _collectors.append(bucket)
    try:
        yield bucket
    finally:
        # By identity: two nested buckets with equal contents (e.g. both empty) are different collectors.
        del _collectors[next(i for i, b in enumerate(_collectors) if b is bucket)]
        unique = list(dict.fromkeys(bucket))
        bucket[:] = unique


def skipped_lines(code, what, lines):
    """One notice for a file read with unreadable lines: ``lines`` = [(line number, text)] (none: nothing said)."""
    if lines:
        n, text = lines[0]
        where = f'γραμμή {n}: ' if n is not None else ''
        return not_computed(code, f'{what}: {len(lines)} γραμμές δεν διαβάστηκαν και παραλείφθηκαν '
                                  f'(π.χ. {where}«{str(text)[:40]}») — ελέγξτε το αρχείο')
    return None


def recent():
    return [issue for _n, issue in _recent]


def serial():
    """Increases with every notice; ``since(serial())`` later = the notices raised in between."""
    return _serial


def since(mark):
    return list(dict.fromkeys(issue for n, issue in _recent if n > mark))
