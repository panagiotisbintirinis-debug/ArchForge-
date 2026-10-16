import json
import os
import subprocess
import sys
import time

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.project import autosave
from archforge.project.autosave import AutoSaver, discard, find_recoverable, pid_alive, recover


def _wall(x=0.0):
    return Entity('wall', {'x1': x, 'y1': 0, 'x2': x + 4, 'y2': 0, 'thickness': .25, 'height': 3, 'z': 0, 'level': 'Ground'})


def _doc(n=2):
    doc = Document()
    for i in range(n):
        doc.add(_wall(i * 5.0))
    return doc


def _dead_pid():
    proc = subprocess.Popen([sys.executable, '-c', 'pass'])
    proc.wait()
    return proc.pid


def _set_pid(saver, pid):
    meta = json.loads(saver.meta_path.read_text(encoding='utf8'))
    meta['pid'] = pid
    saver.meta_path.write_text(json.dumps(meta), encoding='utf8')


def test_directory_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv('ARCHFORGE_AUTOSAVE_DIR', str(tmp_path / 'env'))
    assert autosave.autosave_dir() == tmp_path / 'env'
    assert autosave.autosave_dir(tmp_path / 'arg') == tmp_path / 'arg'
    monkeypatch.delenv('ARCHFORGE_AUTOSAVE_DIR')
    assert autosave.autosave_dir().parts[-2:] == ('.archforge', 'autosave')


def test_writes_only_when_document_changed(tmp_path):
    doc = Document()
    stack = CommandStack(doc)
    saver = AutoSaver(tmp_path, session_id='s1')
    assert saver.autosave(doc) is True
    assert saver.autosave(doc) is False
    stack.execute(AddEntity(_wall()))
    assert saver.autosave(doc, original_path='/x/house.archforge') is True
    assert saver.autosave(doc) is False
    meta = json.loads(saver.meta_path.read_text(encoding='utf8'))
    assert meta['pid'] == os.getpid() and meta['entity_count'] == 1
    assert meta['original_path'] == '/x/house.archforge'
    assert meta['app_version'] and meta['timestamp'] <= time.time()
    stack.undo()
    assert saver.autosave(doc) is True
    assert saver.save_count == 3


def test_rotation_keeps_last_copies(tmp_path):
    doc = Document()
    saver = AutoSaver(tmp_path, session_id='rot', keep=3)
    for i in range(5):
        doc.add(_wall(i * 5.0))
        assert saver.autosave(doc)
    counts = [len(json.loads(saver.rotation_path(i).read_text(encoding='utf8'))['entities']) for i in range(3)]
    assert counts == [5, 4, 3]
    assert not saver.rotation_path(3).exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        'rot.archforge.autosave', 'rot.archforge.autosave.1', 'rot.archforge.autosave.2', 'rot.meta.json']


def test_atomic_write_keeps_previous_copy_on_failure(tmp_path, monkeypatch):
    doc = _doc(1)
    saver = AutoSaver(tmp_path, session_id='atom', keep=1)
    saver.autosave(doc)
    before = saver.path.read_bytes()
    doc.add(_wall(10))

    def boom(src, dst):
        raise OSError('disk full')
    monkeypatch.setattr(autosave.os, 'replace', boom)
    with pytest.raises(OSError):
        saver.autosave(doc)
    monkeypatch.undo()
    assert saver.path.read_bytes() == before                  # the old copy is intact
    assert not [p for p in tmp_path.iterdir() if p.name.endswith('.tmp')]   # no temp left behind
    assert saver.autosave(doc)                                 # and the next attempt writes


def test_live_session_is_not_recoverable_but_crashed_one_is(tmp_path):
    ours = AutoSaver(tmp_path, session_id='ours')
    ours.autosave(_doc(1))
    other = AutoSaver(tmp_path, session_id='crashed')
    other.autosave(_doc(3), original_path='/p/spiti.archforge')
    _set_pid(other, _dead_pid())
    assert pid_alive(os.getpid()) is True
    found = find_recoverable(tmp_path, exclude_session='ours')
    assert [r.session_id for r in found] == ['crashed']
    assert found[0].entity_count == 3 and found[0].original_path == '/p/spiti.archforge'
    # A second live session of our own process is not offered while its heartbeat is fresh…
    assert [r.session_id for r in find_recoverable(tmp_path, exclude_session='crashed')] == []
    # …but is once the heartbeat is stale.
    stale = find_recoverable(tmp_path, exclude_session='crashed', now=time.time() + 3600)
    assert [r.session_id for r in stale] == ['ours']


def test_unknown_pid_falls_back_to_stale_heartbeat(tmp_path, monkeypatch):
    saver = AutoSaver(tmp_path, session_id='old')
    saver.autosave(_doc(1))
    _set_pid(saver, 999999)
    monkeypatch.setattr(autosave, 'pid_alive', lambda pid: None)
    assert find_recoverable(tmp_path) == []
    assert [r.session_id for r in find_recoverable(tmp_path, now=time.time() + 3600)] == ['old']


def test_recover_round_trip_and_discard(tmp_path):
    doc = _doc(3)
    doc.room_data = {'sig': {'name': 'Σαλόνι'}}
    saver = AutoSaver(tmp_path, session_id='rt')
    saver.autosave(doc)
    _set_pid(saver, _dead_pid())
    item = find_recoverable(tmp_path)[0]
    assert recover(item).to_dict() == doc.to_dict()
    assert recover(item.path).to_dict() == doc.to_dict()
    discard(item.path)
    assert list(tmp_path.iterdir()) == []
    assert find_recoverable(tmp_path) == []


def test_recover_falls_back_to_older_copy_when_latest_is_corrupt(tmp_path):
    doc = _doc(1)
    saver = AutoSaver(tmp_path, session_id='bad')
    saver.autosave(doc)
    first = doc.to_dict()
    doc.add(_wall(9))
    saver.autosave(doc)
    saver.path.write_text('{ broken', encoding='utf8')
    assert recover(saver.path).to_dict() == first


def test_finish_removes_session_files(tmp_path):
    other = AutoSaver(tmp_path, session_id='keepme')
    other.autosave(_doc(1))
    saver = AutoSaver(tmp_path, session_id='done')
    saver.autosave(_doc(1))
    saver.autosave(_doc(2))
    saver.finish()
    assert sorted(p.name for p in tmp_path.iterdir()) == ['keepme.archforge.autosave', 'keepme.meta.json']


def test_main_window_autosave_and_recovery(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.autosave_glue import autosave_now, finish_autosave, install_autosave, offer_recovery
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])

    # A "crashed" session left an autosave of a saved project.
    project = tmp_path / 'spiti.archforge'
    original = _doc(1)
    original.save(project)
    crashed_doc = _doc(2)
    crashed = AutoSaver(tmp_path, session_id='crashed')
    crashed.autosave(crashed_doc, original_path=str(project))
    _set_pid(crashed, _dead_pid())

    window = MainWindow()
    window._no_modal_dialogs = True
    saver = install_autosave(window, interval_ms=50, directory=tmp_path)
    assert install_autosave(window) is saver
    assert window._autosave_timer.interval() == 50 and window._autosave_timer.isActive()

    found = offer_recovery(window)
    assert [r.session_id for r in found] == ['crashed']

    from archforge.ui.autosave_glue import restore_into_window
    restore_into_window(window, found[0])
    assert window.doc.to_dict() == crashed_doc.to_dict()
    assert window.current_path == str(project)
    assert window._is_dirty()                                   # recovered work is not yet saved
    assert not (tmp_path / 'crashed.meta.json').exists()      # old session discarded…
    assert saver.path.exists()                                 # …after our own copy was written

    window.stack.execute(AddEntity(_wall(20)))
    assert autosave_now(window) is True
    assert autosave_now(window) is False
    data = json.loads(saver.path.read_text(encoding='utf8'))
    assert len(data['entities']) == 3

    # Errors never escape: they go to the status bar.
    window.doc, real = None, window.doc
    assert autosave_now(window) is False
    assert 'αυτόματη αποθήκευση απέτυχε' in window.statusBar().currentMessage()
    window.doc = real

    # The timer drives autosave too.
    window.stack.execute(AddEntity(_wall(30)))
    deadline = time.time() + 3
    while time.time() < deadline and len(json.loads(saver.path.read_text(encoding='utf8'))['entities']) != 4:
        app.processEvents()
        time.sleep(0.02)
    assert len(json.loads(saver.path.read_text(encoding='utf8'))['entities']) == 4

    finish_autosave(window)
    assert not window._autosave_timer.isActive()
    assert list(tmp_path.glob('*.autosave*')) == []
    assert autosave_now(window) is False
    window.deleteLater()


def test_clean_close_removes_session_autosave(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.autosave_glue import autosave_now, install_autosave
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window._no_modal_dialogs = True
    saver = install_autosave(window, interval_ms=60000, directory=tmp_path)
    window.show()
    assert autosave_now(window) is True and saver.path.exists()
    assert window.close()                                      # nothing unsaved: close is accepted
    for _ in range(5):
        app.processEvents()
    assert list(tmp_path.iterdir()) == []
    assert not window._autosave_timer.isActive()
    window.deleteLater()
