"""Autosave + crash recovery + file check in the main window."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.project import persistence
from archforge.ui.main_window import MainWindow


def _wall(x2):
    return Entity('wall', {'x1': 0, 'y1': 0, 'z': 0, 'x2': x2, 'y2': 0, 'height': 2.7, 'thickness': 0.25})


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    return tmp_path


def _window(every=20):
    QApplication.instance() or QApplication([])
    window = MainWindow()
    window._no_modal_dialogs = True
    window.autosave.every_commands = every
    window.autosave.set_enabled(True)
    return window


def _recoveries():
    return [p for p in os.listdir(persistence.recovery_dir()) if p.endswith(persistence.RECOVERY_SUFFIX)] \
        if os.path.isdir(persistence.recovery_dir()) else []


def test_autosave_does_not_touch_document_undo_or_clean_flag(data_dir):
    window = _window()
    window.stack.execute(AddEntity(_wall(3.0)))
    before = window.doc.to_dict()
    done = list(window.stack.done)
    dirty = window._is_dirty()
    clean = window._clean_state
    assert window.autosave.save_now(wait=True)
    assert window.doc.to_dict() == before
    assert window.stack.done == done and window.stack.undone == []
    assert window._is_dirty() == dirty is True
    assert window._clean_state is clean
    assert window.current_path is None
    with open(window.autosave.path, encoding='utf8') as handle:
        assert json.load(handle)['document'] == json.loads(json.dumps(before))
    # A recovery file in the data folder, nothing anywhere else.
    assert os.path.dirname(window.autosave.path) == persistence.recovery_dir()


def test_clean_project_writes_no_recovery(data_dir):
    window = _window()
    assert window.autosave.save_now(wait=True) is False
    assert _recoveries() == []


def test_autosave_after_every_x_commands(data_dir):
    window = _window(every=3)
    for k in range(3):
        window.stack.execute(AddEntity(_wall(1.0 + k)))
    QApplication.processEvents()                      # the save runs after the command, not inside it
    window.autosave.wait()
    assert len(_recoveries()) == 1
    with open(window.autosave.path, encoding='utf8') as handle:
        assert len(json.load(handle)['document']['entities']) == 3


def test_save_and_close_remove_recovery_and_keep_backups(data_dir):
    window = _window()
    path = str(data_dir / 'σπίτι.archforge')
    window.current_path = path
    window.stack.execute(AddEntity(_wall(3.0)))
    window.autosave.save_now(wait=True)
    assert len(_recoveries()) == 1
    assert window.save()
    assert _recoveries() == []                         # cleaned after a normal save
    window.stack.execute(AddEntity(_wall(4.0)))
    assert window.save()
    assert os.path.exists(path + '.bak')               # previous file kept
    window.stack.execute(AddEntity(_wall(5.0)))
    window.autosave.save_now(wait=True)
    assert len(_recoveries()) == 1
    window._confirm_destructive_action = lambda: True  # "Discard" in the close prompt
    window.close()
    assert _recoveries() == []                         # cleaned after a normal close
    assert not os.path.exists(window.autosave.path + '.lock')


def _crashed_session(data_dir, project_path):
    """A window that autosaved and then died without closing (lock released by the OS)."""
    window = _window()
    window.current_path = project_path
    window.stack.execute(AddEntity(_wall(3.0)))
    window.stack.execute(AddEntity(_wall(7.0)))
    window.autosave.save_now(wait=True)
    state = window.doc.to_dict()
    window.autosave._lock.unlock()                     # the process is gone; its file stays
    path = window.autosave.path
    window.autosave.path = None                        # "killed": nothing more of it runs
    window.autosave.enabled = False
    return state, path


def test_recovery_after_crash_restores_unsaved_with_file_name(data_dir, monkeypatch):
    project = str(data_dir / 'σπίτι.archforge')
    persistence.save_project(_window().doc, project)
    os.utime(project, (1000, 1000))                    # saved before the crash
    state, recovery = _crashed_session(data_dir, project)
    window = _window()
    asked = []
    monkeypatch.setattr(window, '_ask_recovery', lambda info: asked.append(info) or 'recover')
    assert window._offer_recovery() == 'recover'
    assert asked[0].project_name == 'σπίτι.archforge'
    assert window.doc.to_dict() == state
    assert window.current_path == project              # the right file name
    assert window._is_dirty()                          # «μη αποθηκευμένο»
    assert window.isWindowModified() and 'σπίτι.archforge' in window.windowTitle()
    assert window.stack.done == []                     # recovered as the starting state
    window.autosave.wait()
    assert not os.path.exists(recovery)                # adopted by this session…
    assert len(_recoveries()) == 1                     # …which keeps its own copy
    assert window.save()
    assert _recoveries() == []
    assert len(json.load(open(project))['entities']) == 2


def test_recovery_discard_and_later(data_dir, monkeypatch):
    _state, recovery = _crashed_session(data_dir, None)
    window = _window()
    monkeypatch.setattr(window, '_ask_recovery', lambda info: 'later')
    assert window._offer_recovery() == 'later'
    assert os.path.exists(recovery) and len(window.doc.entities) == 0
    monkeypatch.setattr(window, '_ask_recovery', lambda info: 'discard')
    assert window._offer_recovery(manual=True) == 'discard'
    assert not os.path.exists(recovery)
    assert window._offer_recovery() is None


def test_recovery_of_a_running_window_is_not_offered(data_dir, monkeypatch):
    other = _window()
    other.stack.execute(AddEntity(_wall(3.0)))
    other.autosave.save_now(wait=True)                 # still running: holds its lock
    window = _window()
    monkeypatch.setattr(window, '_ask_recovery', lambda info: pytest.fail('must not ask'))
    assert window._offer_recovery() is None
    assert os.path.exists(other.autosave.path)


def test_recovery_older_than_project_is_dropped(data_dir, monkeypatch):
    project = str(data_dir / 'σπίτι.archforge')
    persistence.save_project(_window().doc, project)
    _state, recovery = _crashed_session(data_dir, project)
    os.utime(project, (os.path.getmtime(recovery) + 60,) * 2)
    window = _window()
    monkeypatch.setattr(window, '_ask_recovery', lambda info: pytest.fail('must not ask'))
    assert window._offer_recovery() is None
    assert not os.path.exists(recovery)


def test_open_corrupt_file_does_not_crash_and_offers_backup(data_dir):
    window = _window()
    path = str(data_dir / 'σπίτι.archforge')
    window.current_path = path
    window.stack.execute(AddEntity(_wall(3.0)))
    assert window.save()
    window.stack.execute(AddEntity(_wall(4.0)))
    assert window.save()                               # .bak holds the 1-wall version
    with open(path, 'w', encoding='utf8') as handle:
        handle.write('{"format": 7, "entities": [')  # truncated by a crash/disk
    fresh = _window()
    assert fresh.open(path) is False
    box = fresh._file_check_box
    assert 'κατεστραμμένο ή ελλιπές' in box.text()
    assert [b.text() for b in box.buttons() if 'αντιγράφου' in b.text()]
    # Opening the backup: content of the backup, saved back to the project's own name.
    assert fresh._open_checked(path + '.bak', path)
    assert len(fresh.doc.entities) == 1 and fresh.current_path == path and fresh._is_dirty()


def test_open_with_invalid_entities_loads_the_rest(data_dir):
    window = _window()
    path = str(data_dir / 'μερικό.archforge')
    data = window.doc.to_dict()
    good, bad = _wall(3.0), _wall(4.0)
    data['entities'] = [vars(good), dict(vars(bad), params=dict(bad.params, thickness=-1))]
    with open(path, 'w', encoding='utf8') as handle:
        json.dump(data, handle)
    assert window.open(path)
    assert list(window.doc.entities) == [good.id]
    assert 'Παραλείφθηκαν 1' in window._file_check_box.text()
    assert window._is_dirty()                          # not what is in the file any more
