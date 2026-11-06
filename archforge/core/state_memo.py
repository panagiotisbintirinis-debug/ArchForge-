"""Results remembered while the project does not change (bots 06/11: the same reading was rebuilt several times
for one change — the project tree, the assistant and the plan each asked for it).

The key is the whole state a reader can see, cheaply: the document, its change serial, element count and revisions,
and the project's wall types / materials.  Any change anywhere gives another key and everything is recomputed."""
from __future__ import annotations

import copy

_STORE = {}


def doc_token(doc):
    """A token unique to this document object — not ``id(doc)``, which a new document may reuse once the old one is
    gone (a new project would then be handed the old project's answers)."""
    held = doc.__dict__.get("_memo_token")
    if held is None or held[1] != id(doc):          # new, or a copy of another document: its own token
        import uuid
        held = doc.__dict__["_memo_token"] = (uuid.uuid4().hex, id(doc))
    return held[0]


def state_key(doc):
    ents = doc.entities
    return (doc_token(doc), getattr(doc, "_change_serial", None), len(ents), sum(e.revision for e in ents.values()),
            repr(getattr(doc, "constructions", None)), repr(getattr(doc, "materials", None)),
            repr(getattr(doc, "room_data", None)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())),
            tuple(getattr(doc.work_plane, "origin", ()) or ()))


def remembered(name, doc, args, compute, copy_out=True):
    """``compute()`` once per project state and ``args``; a deep copy is handed out (callers may change theirs)."""
    key = state_key(doc)
    slot = _STORE.get(name)
    if slot is None or slot[0] != key:
        slot = _STORE[name] = (key, {})
    if args not in slot[1]:
        slot[1][args] = compute()
    value = slot[1][args]
    return copy.deepcopy(value) if copy_out else value
