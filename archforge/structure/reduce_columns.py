"""Fewer columns with the same structural adequacy.

A column standing in the middle of a straight beam line (two collinear beams
meet on it) can go: the two beams become one longer beam, the frame is solved
again (``structure.analysis``) and every member that no longer passes takes
its proposed section — a column inside a wall grows *along* the wall (a
wall-like column, still plastered over), a beam gets deeper.  The removal is
kept only if, after that, every member passes and the limits below hold;
otherwise the column stays.  Columns at the same plan position on several
storeys go together (a column line), so nothing ever stands on a beam.

Corners are never removed; at a T or cross the other beams end on the joined beam.  All Document changes are
one undo step.  Pre-design, for review by a licensed engineer.
"""
from __future__ import annotations

import copy
import math

TOL_XY, TOL_Z = 0.15, 0.10
MAX_SPAN = 8.0              # m: longest beam a removal may create
MAX_BEAM_DEPTH = 0.80       # m
MAX_ROUNDS = 5


def _beams_at(doc, x, y, top):
    out = []
    for e in doc.entities.values():
        if e.kind != "structural_beam" or e.params.get("role", "structural") != "structural":
            continue
        p = e.params
        if abs(float(p["z"]) + float(p["height"]) - top) > TOL_Z:
            continue
        for end in (1, 2):
            if math.hypot(float(p[f"x{end}"]) - x, float(p[f"y{end}"]) - y) <= TOL_XY:
                out.append((e, end))
    return out


def _mid_line(doc, col):
    """Two collinear beams a column carries in a straight line (others ending there are then
    carried by the joined beam, beam on beam), and the joined span; else None (a corner)."""
    p = col.params
    x, y = float(p["x"]), float(p["y"])
    beams = _beams_at(doc, x, y, float(p["z"]) + float(p["height"]))
    dirs = []
    for e, end in beams:
        q = e.params
        other = 2 if end == 1 else 1
        dx, dy = float(q[f"x{other}"]) - x, float(q[f"y{other}"]) - y
        L = math.hypot(dx, dy)
        if L > 1e-6:
            dirs.append((e, end, dx / L, dy / L, L))
    best = None
    for i in range(len(dirs)):
        for j in range(i + 1, len(dirs)):
            a, b = dirs[i], dirs[j]
            if a[0].id != b[0].id and a[2] * b[2] + a[3] * b[3] < -0.98:
                span = a[4] + b[4]
                if best is None or span < best[1]:
                    best = (((a[0], a[1]), (b[0], b[1])), span)
    return best


def column_lines(doc):
    """Columns grouped by plan position (one line through all storeys), bottom first."""
    lines = []
    cols = sorted((e for e in doc.entities.values()
                   if e.kind == "structural_column" and e.params.get("role", "structural") == "structural"
                   and e.params.get("construction", "reinforced_concrete") != "steel"),
                  key=lambda e: float(e.params.get("z", 0.0)))
    for c in cols:
        x, y = float(c.params["x"]), float(c.params["y"])
        for line in lines:
            if math.hypot(line[0] - x, line[1] - y) <= TOL_XY:
                line[2].append(c.id)
                break
        else:
            lines.append([x, y, [c.id]])
    return [(x, y, ids) for x, y, ids in lines]


def _remove_line(doc, ids):
    """Remove the columns and join each pair of beams on them; False if any is not mid-line."""
    plans = []
    for cid in ids:
        info = _mid_line(doc, doc.get(cid))
        if info is None:
            return False
        (a, ea), (b, eb) = info[0]
        if info[1] > MAX_SPAN + 1e-9:
            return False
        plans.append((cid, a.id, ea, b.id, eb))
    for cid, aid, ea, bid, eb in plans:
        a, b = doc.get(aid).params, doc.get(bid).params
        far = 2 if eb == 1 else 1
        changes = {f"x{ea}": float(b[f"x{far}"]), f"y{ea}": float(b[f"y{far}"]),
                   "width": max(float(a["width"]), float(b["width"])),
                   "height": max(float(a["height"]), float(b["height"]))}
        top = float(a["z"]) + float(a["height"])
        changes["z"] = top - changes["height"]
        doc.update(aid, changes)
        doc.remove(bid)
        doc.remove(cid)
    return True


def _settle(doc):
    """Resize what fails, as ``design_structure`` does; True when every member passes within limits."""
    from archforge.structure.analysis import analyze_cached
    for _round in range(MAX_ROUNDS):
        r = analyze_cached(doc)
        if r.get("error"):
            return False, r
        fixes = [(mid, e["proposal"]) for mid, e in r.get("members", {}).items()
                 if not e.get("ok", True) and e.get("proposal") and mid in doc.entities]
        if not fixes:
            break
        for mid, prop in fixes:
            doc.update(mid, dict(prop))
    r = analyze_cached(doc)
    if r.get("error") or not all(e.get("ok", True) for e in r.get("members", {}).values()):
        return False, r
    for e in doc.entities.values():
        if e.kind == "structural_beam" and float(e.params.get("height", 0)) > MAX_BEAM_DEPTH + 1e-9:
            return False, r
    return True, r


def reduce_columns(doc, stack, column_ids=None):
    """Remove the columns that can go (``column_ids``: only the lines through these). One undo step.

    Returns {"removed": [names], "kept": [names with reason], "resized": [names], "result": analysis}."""
    from archforge.core.commands import CompositeCommand, DeleteEntities, UpdateEntity, _restore_document_state
    out = {"removed": [], "kept": [], "resized": [], "result": None}
    original = copy.deepcopy(doc.to_dict())
    selection = list(doc.selection)
    ok, result = _settle(doc)
    if not ok:
        _restore_document_state(doc, original, selection)
        out["result"] = result
        out["error"] = "Ο φέρων δεν επαρκεί ούτε με όλες τις κολόνες — πρώτα «Υπολογισμός φέροντα»"
        return out
    lines = column_lines(doc)
    if column_ids:
        wanted = set(column_ids)
        lines = [ln for ln in lines if wanted & set(ln[2])]
    # Shortest joined span first: the easiest removals free the most.
    def joined(line):
        info = _mid_line(doc, doc.get(line[2][-1]))
        return info[1] if info else math.inf
    for x, y, ids in sorted(lines, key=joined):
        if not all(i in doc.entities for i in ids):
            continue
        names = ", ".join(doc.get(i).name or i for i in ids)
        before = copy.deepcopy(doc.to_dict())
        if not _remove_line(doc, ids):
            if column_ids:
                out["kept"].append(f"{names}: γωνία/κόμβος ή άνοιγμα > {MAX_SPAN:g} m")
            continue
        ok, result = _settle(doc)
        if ok:
            out["removed"].append(names)
        else:
            _restore_document_state(doc, before, selection)
            if column_ids:
                out["kept"].append(f"{names}: χωρίς αυτήν δεν επαρκεί")
    final = copy.deepcopy(doc.to_dict())
    _restore_document_state(doc, original, selection)
    out["result"] = None
    if not out["removed"] and not _changed(original, final):
        return out
    commands = _diff_commands(doc, original, final)
    stack.execute(CompositeCommand(commands, "Λιγότερες κολόνες"))
    out["resized"] = [doc.get(c.eid).name or c.eid for c in commands
                      if isinstance(c, UpdateEntity) and doc.get(c.eid).kind == "structural_column"]
    from archforge.structure.analysis import analyze_cached
    out["result"] = analyze_cached(doc)
    return out


def _entities(state):
    return {e["id"]: e for e in state.get("entities", [])} if isinstance(state.get("entities"), list) \
        else dict(state.get("entities", {}))


def _changed(a, b):
    return _entities(a) != _entities(b)


def _diff_commands(doc, original, final):
    from archforge.core.commands import DeleteEntities, UpdateEntity
    before, after = _entities(original), _entities(final)
    commands = []
    for eid, e in after.items():
        old = before.get(eid)
        if old is not None and old.get("params") != e.get("params"):
            changes = {k: v for k, v in e["params"].items() if old["params"].get(k) != v}
            commands.append(UpdateEntity(eid, changes))
    gone = [eid for eid in before if eid not in after]
    if gone:
        commands.append(DeleteEntities(gone))
    return commands
