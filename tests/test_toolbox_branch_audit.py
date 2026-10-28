"""branch_audit offers a branch for deletion only with git proof that nothing of it is lost (owner 28/10)."""
import importlib.util
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    spec = importlib.util.spec_from_file_location('branch_audit', os.path.join(ROOT, 'scripts', 'toolbox', 'branch_audit.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    return subprocess.run(['git', '-c', 'commit.gpgsign=false', *args], cwd=repo, check=True, capture_output=True, text=True, env=env).stdout.strip()


def _commit(repo, name, text, msg):
    with open(os.path.join(repo, name), 'w') as fh:
        fh.write(text)
    _git(repo, 'add', name)
    _git(repo, 'commit', '-q', '-m', msg)
    return _git(repo, 'rev-parse', 'HEAD')


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = str(tmp_path)
    _git(r, 'init', '-q', '-b', 'develop')
    _commit(r, 'a.txt', 'base\n', 'base')
    # merged: its commit is in develop
    _git(r, 'checkout', '-q', '-b', 'merged')
    _commit(r, 'm.txt', 'm\n', 'merged work')
    _git(r, 'checkout', '-q', 'develop')
    _git(r, 'merge', '-q', '--ff-only', 'merged')
    # picked: same diff re-applied on develop under another commit
    _git(r, 'checkout', '-q', '-b', 'picked')
    picked = _commit(r, 'p.txt', 'p\n', 'picked work')
    _git(r, 'checkout', '-q', 'develop')
    _commit(r, 'other.txt', 'o\n', 'develop moves on')
    _git(r, 'cherry-pick', picked)
    # unique: a change develop never got
    _git(r, 'checkout', '-q', '-b', 'unique')
    _commit(r, 'u.txt', 'u\n', 'only here')
    _git(r, 'checkout', '-q', 'develop')
    # merge_fix: two branches already in develop, joined by a merge that adds a change found nowhere else
    _git(r, 'checkout', '-q', '-b', 'side1')
    side1 = _commit(r, 's1.txt', '1\n', 'side1')
    _git(r, 'checkout', '-q', 'develop')
    _git(r, 'checkout', '-q', '-b', 'side2')
    side2 = _commit(r, 's2.txt', '2\n', 'side2')
    _git(r, 'checkout', '-q', 'side1')
    _git(r, 'merge', '-q', '--no-ff', '--no-commit', 'side2')
    with open(os.path.join(r, 'a.txt'), 'w') as fh:
        fh.write('only in the merge\n')
    _git(r, 'add', 'a.txt')
    _git(r, 'commit', '-q', '-m', 'merge side2')
    _git(r, 'branch', 'merge_fix')
    _git(r, 'checkout', '-q', 'develop')
    _git(r, 'cherry-pick', side1)
    _git(r, 'cherry-pick', side2)
    # spike: a change and its revert — final files equal develop's past
    _git(r, 'checkout', '-q', '-b', 'spike')
    _commit(r, 'x.txt', 'x\n', 'try')
    _git(r, 'revert', '--no-edit', 'HEAD')
    _git(r, 'checkout', '-q', 'develop')
    # open_pr: merged, but the owner's open PR points at it
    _git(r, 'branch', 'open_pr', 'merged')
    for b in ('develop', 'merged', 'picked', 'unique', 'merge_fix', 'spike', 'open_pr'):
        _git(r, 'update-ref', f'refs/remotes/origin/{b}', b)
    monkeypatch.chdir(r)
    return r


def test_only_proven_branches_are_offered(repo):
    mod = _load()
    rows = {row['name']: row for row in mod.audit('origin', 'develop', protect=['open_pr'])}
    assert rows['merged']['status'] == 'MERGED'
    assert rows['picked']['status'] == 'SAME_PATCH'
    assert rows['unique']['status'] == 'KEEP'
    assert rows['unique']['unique_subjects'] == ['only here']
    # git cherry ignores merges: the hand-made resolution must keep the branch
    assert rows['merge_fix']['status'] == 'KEEP'
    assert rows['spike']['status'] == 'NO_NET_CHANGE'
    assert rows['open_pr']['status'] == 'PROTECTED'
    assert rows['develop']['status'] == 'PROTECTED'


def test_delete_commands_only_for_proven(repo):
    mod = _load()
    text = mod.markdown(mod.audit('origin', 'develop', protect=['open_pr']), 'origin')
    commands = [line for line in text.splitlines() if line.startswith('git push')]
    assert sorted(commands) == ['git push origin --delete merged', 'git push origin --delete picked',
                                'git push origin --delete spike']
