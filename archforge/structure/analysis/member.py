"""One member at a time: its internal actions, a re-check with the section and bars the
user types, the proposed solution, and applying the choice to the Document (one undo).

The re-check keeps the internal actions of the last analysis of the whole frame: a new
section changes stiffness and self-weight, so «Εφαρμογή» stores the choice and the next
analysis re-solves the frame with it (the analysis then checks the stored bars,
``params['rebar']``, instead of choosing them).
"""
from __future__ import annotations

from archforge.structure.analysis import _resize_rc, analyze_cached, describe_member, wall_axis
from archforge.structure.analysis.rc import design_beam, design_column

STIRRUP_BARS = (8, 10, 12)


def member_entry(doc, entity_id):
    """The analysis entry of this column / beam (analysis cached), or None (with the reason)."""
    result = analyze_cached(doc)
    if result.get("error"):
        return None, result["error"]
    entry = result["members"].get(entity_id)
    if entry is None:
        return None, "Το μέλος δεν αναλύεται (όχι φέρον ή άλλη κατασκευή)"
    return entry, None


def recheck(entry, settings, b, h, rebar=None):
    """Design of the member with section b × h and (optional) the given bars, same actions."""
    i = entry["inputs"]
    if entry["kind"] == "beam":
        out = design_beam(b, h, i["M_sag"], i["M_hog"], i["V"], i["span"], settings, i["cantilever"], rebar=rebar)
    else:
        out = design_column(b, h, i["L"], i["actions"], i["V"], settings, i["seismic"], rebar=rebar)
    out.update({k: entry[k] for k in ("id", "name", "kind", "material") if k in entry})
    out["section"] = f"{b * 100:.0f}/{h * 100:.0f}"
    out["text"] = describe_member(out)
    return out


def proposal(doc, entry, settings):
    """Preferred solution: (b, h, design) — the current section with the cheapest bars,
    else the smallest larger section that passes (a column in a wall grows along it)."""
    b, h = entry["b"], entry["h"]
    d = recheck(entry, settings, b, h)
    if d["ok"]:
        return b, h, d
    from types import SimpleNamespace
    m = SimpleNamespace(b=b, h=h)
    axis = None
    if entry["kind"] == "column" and entry["id"] in doc.entities:
        from archforge.structure.analysis.building import read_members
        members, _x = read_members(doc)
        if entry["id"] in members:
            axis = wall_axis(doc, members[entry["id"]])
    size = _resize_rc(m, settings, lambda nb, nh: recheck(entry, settings, nb, nh), entry["kind"], axis)
    if size is None:
        return b, h, d
    return size[0], size[1], recheck(entry, settings, *size)


def rebar_of(design):
    """The bars of a design result, in the form stored in ``params['rebar']``."""
    out = {}
    if design.get("kind") == "beam":
        for side in ("bottom", "top"):
            if side in design:
                out[side] = {"n": design[side]["n"], "d": design[side]["d"]}
    elif "bars" in design:
        out.update({"d": design["bars"]["d"], "nb": design["bars"]["nb"], "nh": design["bars"]["nh"]})
    if "stirrups" in design:
        st = design["stirrups"]
        out["stirrups"] = {"d": st["d"], "s": round(st["s"], 3), "s_crit": round(st["s_crit"], 3)}
    return out


def apply_command(doc, entity_id, b, h, rebar):
    """UpdateEntity with the section and the bars (a beam keeps its top: the slab level)."""
    from archforge.core.commands import UpdateEntity
    e = doc.get(entity_id)
    p = e.params
    if e.kind == "structural_beam":
        top = float(p["z"]) + float(p["height"])
        changes = {"width": round(b, 3), "height": round(h, 3), "z": round(top - h, 4)}
    else:
        changes = {"width": round(b, 3), "depth": round(h, 3)}
    changes["rebar"] = rebar or None
    return UpdateEntity(entity_id, changes)
