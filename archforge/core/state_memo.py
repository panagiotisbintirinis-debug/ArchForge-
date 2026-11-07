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


# Kinds that never change a wall, a room or an opening: points of the installations, furniture, plants, notes.
# (bots 07/11: each luminaire in a 120-wall block of flats re-cut the layers of every wall — 0,1 s per click.)
NOT_ARCHITECTURE = frozenset(("electrical_point", "plumbing_point", "heating_point", "ventilation_point",
                              "drainage_point", "library_object", "cabinet", "plant", "dimension", "auto_dimensions",
                              "drafting", "camera", "light_probe", "section_line", "elevation_line", "sheet"))


def architecture_key(doc):
    """Like ``state_key`` for readers of the building only (walls, openings, rooms, slabs, materials): what an
    installation point, a piece of furniture or a note changes does not change it.  The parameters themselves are
    in the key (not revisions or the change serial, which undo / redo can bring back to a value already seen)."""
    import json
    quick = state_key(doc)
    held = _STORE.get("_architecture_key")
    if held is not None and held[0] == quick:
        return held[1]                                  # same state: the key is not rebuilt per wall asked
    parts = []
    for e in doc.entities.values():
        if e.kind in NOT_ARCHITECTURE:
            continue
        parts.append((e.id, e.kind, e.parent_id, e.visible, json.dumps(e.params, sort_keys=True, default=str)))
    key = (doc_token(doc), hash(tuple(sorted(parts))), repr(getattr(doc, "constructions", None)),
           repr(getattr(doc, "materials", None)), repr(getattr(doc, "room_data", None)),
           tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())))
    _STORE["_architecture_key"] = (quick, key)
    return key


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
