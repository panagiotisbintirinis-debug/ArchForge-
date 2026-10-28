"""Which remote branches can be deleted with no loss: proof per branch, never a guess.

Owner 28/10: «να είσαι σίγουρος 100% ότι τα branches που σβήνεις είναι ολόκληρα, με τις ίδιες ακριβώς λειτουργίες».
So a branch is offered for deletion only when git proves that every one of its commits is in ``develop``:

* ``MERGED``   — every commit of the branch IS a commit of develop (``git merge-base --is-ancestor``).  The only
  status in the delete list.
* ``SAME_PATCH`` — every commit has a commit in develop with the identical diff (``git cherry``: same patch-id, no
  merge commits of its own), e.g. after a rebase or cherry-pick.  The code is the same, but the original commits
  (date, author, message) are not in develop: listed apart, deleted only with the owner's explicit «ναι».
* ``NO_NET_CHANGE`` — its final files equal a commit of develop (e.g. a spike and its revert).  NOT proof: the
  intermediate work (a file added, then reverted) exists only on the branch (Astra review 28/10,
  ``gpt/issue-102-display-palette``: ``archforge/ui/display_settings.py``).  Never offered.
* ``KEEP``     — at least one commit (or merge) without an identical copy in develop.  Never offered.

``develop``, ``main``, ``HEAD`` and every name passed with ``--protect`` (open PRs, the current session's branch)
are never offered.  The script only reads; it deletes nothing (agents cannot delete branches, the owner does).

    git fetch origin --prune
    python scripts/toolbox/branch_audit.py --protect claude/roof-under-upper-storey codex/s01-foundation-comparison
    python scripts/toolbox/branch_audit.py --markdown docs/BRANCH_AUDIT.md      # the table for the owner
"""
from __future__ import annotations

import argparse
import subprocess
import sys

ALWAYS_PROTECTED = {'develop', 'main', 'HEAD'}


def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True, text=True, encoding='utf-8').stdout


def remote_branches(remote):
    out = git('for-each-ref', '--format=%(refname:short)', f'refs/remotes/{remote}')
    names = []
    for ref in out.split():
        name = ref[len(remote) + 1:]
        if name and name != remote:
            names.append(name)
    return sorted(names)


def classify(remote, base, name):
    ref = f'{remote}/{name}'
    ahead = int(git('rev-list', '--count', f'{base}..{ref}').strip())
    date = git('log', '-1', '--format=%cs', ref).strip()
    tip = git('rev-parse', '--short', ref).strip()
    if subprocess.run(['git', 'merge-base', '--is-ancestor', ref, base]).returncode == 0:
        return dict(name=name, status='MERGED', ahead=0, unique=0, date=date, tip=tip, unique_subjects=[])
    cherry = [line for line in git('cherry', '-v', base, ref).splitlines() if line.strip()]
    unique = [line[43:].strip() for line in cherry if line.startswith('+')]
    # ``git cherry`` skips merge commits; a merge can carry a conflict resolution found nowhere else.
    merges = git('rev-list', '--merges', f'{base}..{ref}').split()
    unique += [f'merge {m[:7]} (δεν ελέγχεται με patch-id)' for m in merges]
    status = 'SAME_PATCH' if not unique else 'KEEP'
    if unique:
        # Its final files are exactly those of a commit already in develop (e.g. a change and its revert).
        merge_base = git('merge-base', base, ref).strip()
        if subprocess.run(['git', 'diff', '--quiet', merge_base, ref]).returncode == 0:
            status = 'NO_NET_CHANGE'
    return dict(name=name, status=status, ahead=ahead, unique=len(unique), date=date, tip=tip, unique_subjects=unique)


def audit(remote='origin', base_branch='develop', protect=()):
    base = f'{remote}/{base_branch}'
    protected = ALWAYS_PROTECTED | {base_branch} | set(protect)
    rows = []
    for name in remote_branches(remote):
        row = classify(remote, base, name)
        if name in protected:
            row['status'] = 'PROTECTED'
        rows.append(row)
    return rows


def markdown(rows, remote):
    order = {'KEEP': 0, 'PROTECTED': 1, 'NO_NET_CHANGE': 2, 'SAME_PATCH': 3, 'MERGED': 4}
    rows = sorted(rows, key=lambda r: (order[r['status']], r['date'], r['name']))
    count = {s: sum(r['status'] == s for r in rows) for s in order}
    deletable = [r['name'] for r in rows if r['status'] == 'MERGED']
    same_patch = [r['name'] for r in rows if r['status'] == 'SAME_PATCH']
    out = [f'Σύνολο {len(rows)} · MERGED {count["MERGED"]} · SAME_PATCH {count["SAME_PATCH"]} · '
           f'NO_NET_CHANGE {count["NO_NET_CHANGE"]} · KEEP {count["KEEP"]} · PROTECTED {count["PROTECTED"]}', '',
           '| Κατάσταση | Branch | Τελευταίο commit | Δικά του commits (χωρίς ίδιο αντίγραφο στο develop) |', '|---|---|---|---|']
    for r in rows:
        subj = '; '.join(r['unique_subjects'][:3]) + (' …' if len(r['unique_subjects']) > 3 else '')
        out.append(f"| {r['status']} | `{r['name']}` | {r['date']} `{r['tip']}` | {r['unique']} {subj} |")
    out += ['', f'Εντολή διαγραφής ({len(deletable)} branches, μόνο MERGED: κάθε commit τους είναι commit του develop):',
            '', '```']
    out += [f'git push {remote} --delete {n}' for n in deletable]
    out += ['```']
    if same_patch:
        out += ['', f'Μόνο με ρητή έγκριση του ιδιοκτήτη ({len(same_patch)} SAME_PATCH: ίδιος κώδικας, '
                'αλλά τα αρχικά commits δεν είναι στο develop):', '', '```']
        out += [f'git push {remote} --delete {n}' for n in same_patch]
        out += ['```']
    return '\n'.join(out) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--remote', default='origin')
    ap.add_argument('--base', default='develop')
    ap.add_argument('--protect', nargs='*', default=[], help='branches never offered (open PRs, active work)')
    ap.add_argument('--markdown', help='write the owner table to this file')
    args = ap.parse_args(argv)
    rows = audit(args.remote, args.base, args.protect)
    text = markdown(rows, args.remote)
    if args.markdown:
        with open(args.markdown, 'w', encoding='utf-8') as fh:
            fh.write(text)
    sys.stdout.write(text)


if __name__ == '__main__':
    main()
