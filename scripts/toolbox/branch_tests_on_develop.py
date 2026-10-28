"""Run an old branch's own tests on today's develop: is its behaviour already there?

``branch_audit.py`` proves when a branch's *code* is in develop.  A branch marked KEEP may still have been rebuilt
differently later.  This tool gives the evidence for that case: it checks out develop in a throw-away worktree,
copies in the test files the branch added or changed (not its application code) and runs them.

* all pass → develop already behaves as the branch asked (the branch can be closed, with this output as proof);
* failures → something of the branch is missing in develop, OR develop changed that contract on purpose since —
  read the failure before deciding.  Never delete a branch on a failure.

    python scripts/toolbox/branch_tests_on_develop.py gpt/issue-91-close-unsaved-guard [more branches …]

Qt runs offscreen; set QTWEBENGINE_DISABLE_SANDBOX=1 in the cloud.  Nothing in the main checkout is touched.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile


def git(*args, cwd=None):
    return subprocess.run(['git', *args], check=True, capture_output=True, text=True, encoding='utf-8', cwd=cwd).stdout


def branch_test_files(remote, base, branch):
    out = git('diff', '--name-only', '--diff-filter=AM', f'{remote}/{base}...{remote}/{branch}', '--', 'tests')
    return [f for f in out.split() if f.endswith('.py')]


def run(branches, remote='origin', base='develop', timeout=1800):
    repo = git('rev-parse', '--show-toplevel').strip()
    work = tempfile.mkdtemp(prefix='af_branch_tests_')
    tree = os.path.join(work, 'develop')
    git('worktree', 'add', '--detach', tree, f'{remote}/{base}', cwd=repo)
    results = {}
    try:
        for branch in branches:
            git('checkout', '-q', '-f', f'{remote}/{base}', cwd=tree)
            git('clean', '-qfd', 'tests', cwd=tree)
            files = branch_test_files(remote, base, branch)
            for f in files:
                dest = os.path.join(tree, f)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, 'w', encoding='utf-8', newline='') as fh:
                    fh.write(git('show', f'{remote}/{branch}:{f}', cwd=repo))
            tests = [f for f in files if os.path.basename(f).startswith('test_')]
            if not tests:
                results[branch] = 'NO TESTS'
                print(f'{branch}: NO TESTS', flush=True)
                continue
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
            try:
                proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *tests],
                                      cwd=tree, env=env, capture_output=True, text=True, encoding='utf-8',
                                      errors='replace', timeout=timeout)
                lines = [l for l in proc.stdout.splitlines() if l.strip()]
                summary = lines[-1] if lines else proc.stderr.strip()[-300:]
                failed = [l for l in lines if l.startswith(('FAILED', 'ERROR'))]
                # The reason, once each (e.g. "ModuleNotFoundError: No module named …" = the branch's code is absent).
                reasons = list(dict.fromkeys(l[1:].strip() for l in lines if l.startswith('E ')))
                results[branch] = summary
                print(f'{branch}: {summary}', flush=True)
                for l in failed[:20]:
                    print(f'    {l}', flush=True)
                for l in reasons[:8]:
                    print(f'      why: {l[:200]}', flush=True)
            except subprocess.TimeoutExpired:
                results[branch] = 'TIMEOUT'
                print(f'{branch}: TIMEOUT', flush=True)
    finally:
        git('worktree', 'remove', '--force', tree, cwd=repo)
        shutil.rmtree(work, ignore_errors=True)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('branches', nargs='+')
    ap.add_argument('--remote', default='origin')
    ap.add_argument('--base', default='develop')
    args = ap.parse_args(argv)
    run(args.branches, args.remote, args.base)


if __name__ == '__main__':
    main()
