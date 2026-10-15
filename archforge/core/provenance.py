"""Status of every technical rule and value the program uses (owner's rule, 2026-10-15, AGENTS.md).

A rule never passes as «verified» just because it is already in the code.
Each module registers its rules here with one status:

* ``VERIFIED``          — cross-checked against a source in force (``source`` names it: document,
                          clause/table, URL); may be presented as a requirement.
* ``DESIGN_DEFAULT``    — our own default / placement choice, not a regulation; editable.
* ``MANUFACTURER_DATA`` — comes from a data sheet the user enters (no hidden value).
* ``ENGINEER_REVIEW``   — needs a study / calculation by an engineer.
* ``UNVERIFIED``        — must not be presented as a technical requirement.

``rules()`` lists them for the UI (e.g. the electrical board tab) and for the
tests that keep the registry honest.
"""
from __future__ import annotations

from dataclasses import dataclass

VERIFIED = "VERIFIED"
DESIGN_DEFAULT = "DESIGN_DEFAULT"
MANUFACTURER_DATA = "MANUFACTURER_DATA"
ENGINEER_REVIEW = "ENGINEER_REVIEW"
UNVERIFIED = "UNVERIFIED"

STATUS_LABELS = {
    VERIFIED: "Επαληθευμένο (ισχύουσα πηγή)",
    DESIGN_DEFAULT: "Προεπιλογή του προγράμματος (όχι κανονισμός)",
    MANUFACTURER_DATA: "Στοιχείο κατασκευαστή (από το φύλλο, το εισάγει ο χρήστης)",
    ENGINEER_REVIEW: "Θέλει μελέτη μηχανικού",
    UNVERIFIED: "Μη επαληθευμένο — όχι τεχνική απαίτηση",
}
STATUSES = tuple(STATUS_LABELS)


@dataclass(frozen=True)
class Rule:
    id: str            # "electrical.lighting_circuit"
    statement: str     # what the program does with it, in Greek
    status: str
    source: str = ""   # document + clause/table (+ URL) — required for VERIFIED
    note: str = ""

    def __post_init__(self):
        if self.status not in STATUS_LABELS:
            raise ValueError(f"unknown status {self.status}")
        if self.status == VERIFIED and not self.source:
            raise ValueError(f"{self.id}: a VERIFIED rule needs its source")

    @property
    def is_requirement(self):
        """Only verified rules may be shown as technical requirements."""
        return self.status == VERIFIED


_REGISTRY: dict[str, Rule] = {}


def register(*rules):
    for r in rules:
        _REGISTRY[r.id] = r
    return rules


def rule(rule_id):
    return _REGISTRY[rule_id]


def rules(prefix=""):
    """Registered rules whose id starts with ``prefix`` (modules register on import)."""
    _load()
    return [r for k, r in sorted(_REGISTRY.items()) if k.startswith(prefix)]


def _load():
    # Importing the modules registers their rules.
    import archforge.mep.electrical  # noqa: F401
    import archforge.mep.electrical_board  # noqa: F401
    import archforge.mep.lighting  # noqa: F401
    import archforge.mep.luminaire_catalog  # noqa: F401
    import archforge.mep.practice  # noqa: F401


# Standards references themselves (status of the documents the code cites).
register(
    Rule("standards.elot_hd_384",
         "Το ΕΛΟΤ HD 384 δεν είναι ισχύον: αντικαταστάθηκε (μέρος προς μέρος) από τη σειρά ΕΛΟΤ HD 60364· "
         "ίσχυσε ως 31/12/2023, το ΕΛΟΤ HD 60364 εφαρμόζεται πλήρως από 01/01/2024. Ο κώδικας δεν το επικαλείται ως πηγή.",
         VERIFIED,
         source="ΣΕΒ, παρουσίαση ΕΛΟΤ HD 60364 (2024): https://www.sev.org.gr/wp-content/uploads/2024/02/kokkinos_parousiasi_final.pdf · "
                "ΕΛΟΤ eshop, ΕΛΟΤ HD 60364.07.708 «Αντικαθιστά ΕΛΟΤ HD 384.07.708 S2:2005»: https://eshop.elot.gr/product/84427",
         note="Διασταυρώθηκε με αναζήτηση 15/10· τα πλήρη κείμενα δεν ανοίχτηκαν από το cloud (μπλοκαρισμένο δίκτυο)."),
)
