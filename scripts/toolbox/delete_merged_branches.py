"""Delete the MERGED branches listed in docs/BRANCH_AUDIT.md — each one re-proved right before it is deleted.

For the owner (agents cannot delete branches).  Owner 28/10: «τα 117, εφόσον είμαστε σίγουροι, σβήσε τα».

    git fetch origin --prune
    python scripts/toolbox/delete_merged_branches.py            # shows what it would delete, deletes nothing
    python scripts/toolbox/delete_merged_branches.py --yes      # deletes

A branch is deleted only if, at that moment, every commit of it is a commit of origin/develop
(``git merge-base --is-ancestor``) and it is not develop / main.  Anything else is skipped and named.  Before
deleting, each branch's last commit is written to ``deleted_branches.txt``; a branch can be made again with
``git push origin <sha>:refs/heads/<name>``.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

NEVER = {'develop', 'main', 'HEAD'}
HEADER = 'Εντολή διαγραφής'
STOP = 'Μόνο με ρητή έγκριση'


def merged_list(audit_path):
    """The branch names of the MERGED delete block of BRANCH_AUDIT.md (not the SAME_PATCH one)."""
    names, inside = [], False
    with open(audit_path, encoding='utf-8') as fh:
        for line in fh:
            if line.startswith(HEADER):
                inside = True
            elif line.startswith(STOP):
                inside = False
            elif inside and line.startswith('git push') and '--delete' in line:
                names.append(line.split()[-1])
    return names


def _git(*args, check=True):
    return subprocess.run(['git', *args], capture_output=True, text=True, encoding='utf-8', check=check)


def run(names, remote='origin', base='develop', yes=False, record='deleted_branches.txt', out=print):
    deleted, skipped = [], []
    for name in names:
        ref = f'{remote}/{name}'
        if name in NEVER:
            skipped.append((name, 'προστατευμένο'))
            continue
        tip = _git('rev-parse', '--verify', '--quiet', ref, check=False).stdout.strip()
        if not tip:
            skipped.append((name, 'δεν υπάρχει πια'))
            continue
        if _git('merge-base', '--is-ancestor', ref, f'{remote}/{base}', check=False).returncode != 0:
            skipped.append((name, f'έχει commits που δεν είναι στο {base} — ΔΕΝ σβήνεται'))
            continue
        if not yes:
            out(f'θα σβηστεί: {name} ({tip[:7]})')
            deleted.append(name)
            continue
        with open(record, 'a', encoding='utf-8') as fh:
            fh.write(f'{name} {tip}\n')
        done = _git('push', remote, '--delete', name, check=False)
        if done.returncode == 0:
            out(f'σβήστηκε: {name} ({tip[:7]})')
            deleted.append(name)
        else:
            skipped.append((name, f'το GitHub αρνήθηκε: {done.stderr.strip()[-120:]}'))
    for name, why in skipped:
        out(f'παραλείφθηκε: {name} — {why}')
    verb = 'σβήστηκαν' if yes else 'θα σβηστούν (τρέξε με --yes)'
    out(f'\n{len(deleted)} {verb} · {len(skipped)} παραλείφθηκαν'
        + (f' · αντίγραφο ασφαλείας: {os.path.abspath(record)}' if yes and deleted else ''))
    return deleted, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--audit', default=os.path.join('docs', 'BRANCH_AUDIT.md'))
    ap.add_argument('--remote', default='origin')
    ap.add_argument('--yes', action='store_true', help='delete for real (without it: only show)')
    args = ap.parse_args(argv)
    names = merged_list(args.audit)
    if not names:
        print(f'Δεν βρέθηκε λίστα «{HEADER}» στο {args.audit}')
        return 1
    run(names, args.remote, yes=args.yes)
    return 0


if __name__ == '__main__':
    sys.exit(main())
