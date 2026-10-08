"""Project files: atomic write, .bak rotation, check on open, old formats, recovery files."""
from __future__ import annotations

import json
import os

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.project import persistence
from archforge.project.persistence import (
    FORMAT_VERSION, ProjectFileError, atomic_write_text, backup_paths, list_recoveries,
    load_project, rotate_backups, save_project, write_recovery,
)


def _wall(x2=4.0, name='Τοίχος'):
    return Entity('wall', {'x1': 0, 'y1': 0, 'z': 0, 'x2': x2, 'y2': 0, 'height': 2.7, 'thickness': 0.25},
                  name=name)


def _doc(*lengths):
    doc = Document()
    stack = CommandStack(doc)
    for length in lengths or (4.0,):
        stack.execute(AddEntity(_wall(length)))
    return doc


def test_format_version_matches_document():
    assert Document().to_dict()['format'] == FORMAT_VERSION


def test_atomic_write_keeps_old_file_when_write_fails(tmp_path, monkeypatch):
    target = tmp_path / 'έργο.archforge'
    target.write_text('παλιό', encoding='utf8')

    def broken_replace(src, dst):
        raise OSError('δίσκος γεμάτος')
    monkeypatch.setattr(persistence.os, 'replace', broken_replace)
    with pytest.raises(OSError):
        atomic_write_text(target, 'νέο')
    assert target.read_text(encoding='utf8') == 'παλιό'
    assert [p.name for p in tmp_path.iterdir()] == ['έργο.archforge']   # no temp left behind


def test_atomic_write_replaces_whole_file(tmp_path):
    target = tmp_path / 'a.archforge'
    atomic_write_text(target, 'x' * 1000)
    atomic_write_text(target, 'y')
    assert target.read_text() == 'y'


def test_save_keeps_last_three_backups(tmp_path):
    path = str(tmp_path / 'σπίτι.archforge')
    for n in range(1, 6):
        save_project(_doc(*[float(k + 1) for k in range(n)]), path)
    # Current file has 5 walls, backups 4, 3, 2 (newest first); the 1-wall file dropped off.
    assert len(json.load(open(path))['entities']) == 5
    counts = [len(json.load(open(p))['entities']) for p in backup_paths(path)]
    assert counts == [4, 3, 2]
    assert not os.path.exists(path + '.bak4')


def test_rotate_without_existing_file_is_a_no_op(tmp_path):
    assert rotate_backups(str(tmp_path / 'none.archforge')) is None
    assert list(tmp_path.iterdir()) == []


def test_save_load_round_trip(tmp_path):
    doc = _doc(3.0, 5.0)
    path = str(tmp_path / 'r.archforge')
    save_project(doc, path)
    report = load_project(path)
    assert report.ok and report.loaded == 2 and not report.notes
    assert report.doc.to_dict() == doc.to_dict()


@pytest.mark.parametrize('text', ['', '{"format": 7, "entities": [', 'not json at all', '\x00\x01'])
def test_corrupt_or_truncated_file_gives_greek_error(tmp_path, text):
    path = tmp_path / 'χαλασμένο.archforge'
    path.write_text(text, encoding='utf8')
    with pytest.raises(ProjectFileError) as err:
        load_project(str(path))
    assert 'χαλασμένο.archforge' in str(err.value)


def test_truncated_save_reports_line(tmp_path):
    path = str(tmp_path / 'μισό.archforge')
    save_project(_doc(2.0, 3.0), path)
    text = open(path).read()
    open(path, 'w').write(text[: len(text) // 2])
    with pytest.raises(ProjectFileError, match='κατεστραμμένο ή ελλιπές'):
        load_project(path)


def test_invalid_entities_are_skipped_and_listed(tmp_path):
    data = _doc(2.0, 3.0).to_dict()
    data['entities'][0]['params']['thickness'] = -1          # fails the wall schema
    data['entities'].append({'kind': 'wall'})                # no params at all is still readable…
    data['entities'].append('σκουπίδια')                     # …but this is not an entity
    data['entities'].append({'kind': 'door', 'params': {'offset': 1, 'width': 0.9, 'height': 2.1},
                             'parent_id': 'missing-wall'})   # host does not exist
    path = tmp_path / 'μερικό.archforge'
    path.write_text(json.dumps(data), encoding='utf8')
    report = load_project(str(path))
    assert not report.ok
    assert report.loaded == len(report.doc.entities) == 2    # the good wall + the empty-params wall
    assert len(report.skipped) == 3
    message = report.message()
    assert message.startswith('Φορτώθηκαν 2 στοιχεία.')
    assert 'Παραλείφθηκαν 3' in message and 'Τοίχος' in message and 'Πόρτα' in message


def test_strict_from_dict_still_raises():
    data = _doc().to_dict()
    data['entities'][0]['params']['thickness'] = -1
    with pytest.raises(Exception):
        Document.from_dict(data)


def test_old_project_without_new_fields_is_upgraded(tmp_path):
    # An early project: no format, no room data / bindings / modifiers / constructions / work plane.
    old = {'entities': [{'kind': 'wall', 'id': 'w1',
                         'params': {'x1': 0, 'y1': 0, 'z': 0, 'x2': 5, 'y2': 0, 'height': 2.7, 'thickness': 0.2}}],
           'levels': {'Ground': 0.0}}
    path = tmp_path / 'παλιό.archforge'
    path.write_text(json.dumps(old), encoding='utf8')
    report = load_project(str(path))
    assert report.ok and report.loaded == 1 and report.upgraded_from == 0
    assert 'Παλιό έργο' in report.message()
    wall = report.doc.entities['w1']
    assert wall.name == '' and wall.visible and not wall.locked
    data = report.doc.to_dict()
    assert data['format'] == FORMAT_VERSION and data['room_data'] == {} and data['surface_modifiers'] == []


def test_newer_format_and_unknown_fields_do_not_crash(tmp_path):
    data = _doc().to_dict()
    data['format'] = FORMAT_VERSION + 3
    data['entities'][0]['future_field'] = 42
    data['levels'] = 'λάθος'
    path = tmp_path / 'νέο.archforge'
    path.write_text(json.dumps(data), encoding='utf8')
    report = load_project(str(path))
    assert report.ok and report.loaded == 1
    assert 'νεότερη έκδοση' in report.message()
    assert report.doc.levels == {'Ground': 0.0}


def test_recovery_file_round_trip_and_newer_than_project(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    project = tmp_path / 'σπίτι.archforge'
    save_project(_doc(2.0), str(project))
    os.utime(project, (1000, 1000))
    doc = _doc(2.0, 6.0)
    path = persistence.new_recovery_path()
    write_recovery(path, doc.to_dict(), str(project), saved_at=2000)
    assert os.path.dirname(path) == persistence.recovery_dir()       # never next to the project
    [info] = list_recoveries()
    assert info.project_name == 'σπίτι.archforge' and info.is_newer_than_project()
    assert Document.from_dict(info.read_document_data()).to_dict() == doc.to_dict()
    os.utime(project, (3000, 3000))                                   # saved after the snapshot
    assert not info.is_newer_than_project()
    assert list_recoveries(exclude=(path,)) == []
    persistence.remove_recovery(path)
    assert list_recoveries() == []
