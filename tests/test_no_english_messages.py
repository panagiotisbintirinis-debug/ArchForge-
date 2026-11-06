"""Bots 06/11: the person reads Greek — no status-bar message may be English only («wall openings must not
overlap», «Select one object…», «New project», 53 more in the 3D view).  A guard over the source: every literal
given to ``statusChanged.emit`` / ``showMessage`` that has words must have Greek in it."""
import glob
import re

PAT = re.compile(r'''(?:statusChanged\.emit|showMessage)\(\s*f?(["'])(.*?)\1''')
GREEK = re.compile('[Ͱ-Ͽἀ-῿]')
WORDS = re.compile(r'[A-Za-z]{3,} [A-Za-z]{2,}')


def test_status_messages_are_greek():
    bad = []
    for f in sorted(glob.glob('archforge/**/*.py', recursive=True)):
        for i, line in enumerate(open(f, encoding='utf-8'), 1):
            for m in PAT.finditer(line):
                text = re.sub(r'\{[^{}]*\}', '', m.group(2))                 # f-string fields are values, not words
                if WORDS.search(text) and not GREEK.search(text):
                    bad.append(f'{f}:{i}: {m.group(2)[:80]}')
    assert not bad, '\n'.join(bad)
