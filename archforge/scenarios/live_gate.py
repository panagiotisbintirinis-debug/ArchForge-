"""Ζωντανός έλεγχος ποιότητας (owner 18/10, «Βήμα 2»): the scenarios' quality gate on the project being drawn.

Sections 1–3 of ``gate.Gate`` (σχεδιαστικό, στατικό, Η/Μ) run on the open document.  Left out: the
checks that test the *program* rather than the project — they edit and undo (system change, quote
prices), write files (save → reopen) or audit the rule registry — so the live run never touches the
person's undo history or disk.  Section 4–6 stay with the scenario builder.

Each result carries the entities its note names (``ids``, for «Δείξε μου») and, when the program has
a tool that fixes it, a ``fix`` key (ui/quality_panel.py maps it to that tool).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from archforge.scenarios.gate import FAIL, NA, PASS, Gate

# Checks of the program, not of the project (see module doc).
PROGRAM_CHECKS = ("Αποθήκευση → κλείσιμο → άνοιγμα", "Αλλαγή συστήματος", "Αποτελέσματα σημειωμένα «ΜΗ ΕΠΑΛΗΘΕΥΜΕΝΟ»",
                  "Κανένας κανόνας δεν βαφτίζεται", "Ονόματα στοιχείων στα ελληνικά")

# Item prefix → the tool that adds what is missing.
FIXES = (("Δάπεδο σε κάθε όροφο", "complete"), ("Στέγη πάνω από", "complete"), ("Κουζίνα:", "complete"),
         ("Μπάνιο:", "complete"), ("Ηλεκτρολογικά", "complete"), ("Θέρμανση", "complete"),
         ("Κολόνες", "frame"), ("Δοκοί", "frame"), ("Θεμελίωση", "frame"), ("Συνέχεια κολονών", "frame"))


@dataclass
class Result:
    section: str
    item: str
    status: str
    note: str = ""
    ids: Tuple[str, ...] = ()
    fix: Optional[str] = None


class _Project:
    """What ``Gate`` reads of a scenario: the document and the window."""

    def __init__(self, window):
        self.window = window

    @property
    def doc(self):
        return self.window.doc


class _NoScenario:
    """A project has no scenario module: no expected room list, no reviewed warnings."""
    KEY, NAME, TITLE = "live", "live", "Έργο"


class LiveGate(Gate):
    def __init__(self, window):
        super().__init__(_Project(window), _NoScenario, None)

    # Program checks: never run live (they edit + undo, or write to disk).
    def _reopen(self):
        pass

    def _pipe_system_change(self):
        pass

    def _heating_system_change(self):
        pass

    def run_live(self):
        self.checks = []
        for section, fn in enumerate((self.design, self.statics, self.mep), 1):
            try:
                fn()
            except Exception as exc:                                   # noqa: BLE001 — shown, never hidden
                self.add(section, f"Ο έλεγχος σταμάτησε ({fn.__name__})", False, f"{type(exc).__name__}: {exc}")
        return [Result(c.section, c.item, c.status, c.note, named_ids(self.doc, f"{c.item} {c.note}"), fix_for(c.item))
                for c in self.checks if not c.item.startswith(PROGRAM_CHECKS)]


def fix_for(item):
    return next((key for prefix, key in FIXES if item.startswith(prefix)), None)


def named_ids(doc, text):
    """Entities named as a whole word in the text («Κόμβος Κ3 / X», «χωρίς στήριξη: Κ3, Κ5» → those columns)."""
    text = str(text or "")
    return tuple(e.id for e in doc.entities.values()
                 if e.name and len(e.name) >= 2 and re.search(rf"(?<!\w){re.escape(e.name)}(?!\w)", text))


def run(window) -> List[Result]:
    return LiveGate(window).run_live()


def summary(results):
    """(passed, failed, not applicable)."""
    return (sum(r.status == PASS for r in results), sum(r.status == FAIL for r in results), sum(r.status == NA for r in results))
