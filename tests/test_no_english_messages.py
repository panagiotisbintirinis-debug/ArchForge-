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


# Raised by what the mouse does and shown as it is (str(exc) on the status line): Greek too. Internal guards a person
# cannot reach are listed — a new English one must be added here on purpose, or written in Greek.
USER_FACING = ('archforge/core/interaction.py', 'archforge/core/viewport.py', 'archforge/architecture/openings.py',
               'archforge/architecture/railings.py', 'archforge/architecture/joinery.py')
INTERNAL = {'transaction cancelled', 'stair has no candidates', 'stair has no valid preview', 'ramp has no candidates',
            'endpoint must be 1 or 2', 'beam endpoint stretch requires a structural_beam', 'invalid pod handle',
            'opening kind must be door, window, or opening', 'opening edit requires door/window/opening',
            'opening handle must be move, left or right', 'wall angle reference must be global or relative',
            'host wall has zero length', 'axis must be XZ or YZ'}
RAISE = re.compile(r'''raise (?:ValueError|RuntimeError)\(\s*f?(["'])(.*?)\1''')


def test_mouse_errors_are_greek():
    bad = []
    for f in USER_FACING:
        for i, line in enumerate(open(f, encoding='utf-8'), 1):
            for m in RAISE.finditer(line):
                text = re.sub(r'\{[^{}]*\}', '', m.group(2))
                if m.group(2) in INTERNAL or not WORDS.search(text) or GREEK.search(text):
                    continue
                bad.append(f'{f}:{i}: {m.group(2)[:80]}')
    assert not bad, '\n'.join(bad)
