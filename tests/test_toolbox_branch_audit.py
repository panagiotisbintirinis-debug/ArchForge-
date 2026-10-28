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
    first, _, rest = text.partition('Μόνο με ρητή έγκριση')
    # Only branches whose every commit is a develop commit; a spike+revert keeps work found nowhere else (Astra 28/10).
    assert [l for l in first.splitlines() if l.startswith('git push')] == ['git push origin --delete merged']
    assert [l for l in rest.splitlines() if l.startswith('git push')] == ['git push origin --delete picked']
    assert 'spike' not in [l.split()[-1] for l in text.splitlines() if l.startswith('git push')]


def test_delete_tool_re_proves_each_branch_before_deleting(tmp_path, monkeypatch):
    """delete_merged_branches: only branches whose every commit is in develop, re-checked at deletion time."""
    spec = importlib.util.spec_from_file_location(
        'delete_merged', os.path.join(ROOT, 'scripts', 'toolbox', 'delete_merged_branches.py'))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    remote = str(tmp_path / 'remote.git')
    _git(str(tmp_path), 'init', '-q', '--bare', remote)
    work = str(tmp_path / 'work')
    os.makedirs(work)
    _git(work, 'init', '-q', '-b', 'develop')
    _commit(work, 'a.txt', 'a\n', 'base')
    _git(work, 'branch', 'done')                               # merged
    _git(work, 'checkout', '-q', '-b', 'late')                 # was merged when audited, got a new commit since
    _commit(work, 'l.txt', 'l\n', 'new work after the audit')
    _git(work, 'checkout', '-q', 'develop')
    _git(work, 'remote', 'add', 'origin', remote)
    _git(work, 'push', '-q', 'origin', 'develop', 'done', 'late')
    _git(work, 'fetch', '-q', 'origin')
    audit = tmp_path / 'BRANCH_AUDIT.md'
    audit.write_text('Εντολή διαγραφής (3):\n\n```\ngit push origin --delete done\ngit push origin --delete late\n'
                     'git push origin --delete develop\n```\n\nΜόνο με ρητή έγκριση (1):\n```\n'
                     'git push origin --delete picked\n```\n', encoding='utf-8')
    monkeypatch.chdir(work)
    assert tool.merged_list(str(audit)) == ['done', 'late', 'develop']
    lines = []
    deleted, skipped = tool.run(tool.merged_list(str(audit)), yes=True, record=str(tmp_path / 'rec.txt'),
                                out=lines.append)
    assert deleted == ['done']
    assert {n for n, _w in skipped} == {'late', 'develop'}
    heads = _git(work, 'ls-remote', '--heads', 'origin')
    assert 'refs/heads/done' not in heads and 'refs/heads/late' in heads
    assert (tmp_path / 'rec.txt').read_text().split()[0] == 'done'
