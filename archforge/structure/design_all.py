"""One command for the whole load-bearing structure: columns, beams, footings.

1. No frame yet → the frame proposed from the walls (columns at junctions
   and every ≤ 6 m, beams along the walls).
2. Analysis; every member that fails takes the proposed section that passes
   (RC: next size up; steel: lightest adequate profile), then the analysis
   runs again — at most four rounds.
3. Footings (with reinforcement) and tie beams come out of the final
   analysis and are drawn under the base storey (plan, 3D layer
   "foundation").

All Document changes are one undo step.  Load-bearing walls (stone, Isotex)
need no frame: the command says so and leaves the walls to carry the loads.
"""
from __future__ import annotations

MAX_ROUNDS = 4


def design_structure(doc, stack):
    from archforge.core.commands import AddEntities, CompositeCommand, UpdateEntity
    from archforge.project.brief import load_bearing_walls
    from archforge.structure.analysis import analyze_cached, has_structure
    from archforge.structure.layout import propose_frame
    out = {"added": {"columns": 0, "beams": 0}, "resized": [], "rounds": 0, "result": None, "bearing_walls": False}
    if load_bearing_walls(doc) and not has_structure(doc):
        out["bearing_walls"] = True
        return out
    changed = False
    if not has_structure(doc):
        entities, report = propose_frame(doc)
        if not entities:
            return out
        stack.execute(AddEntities(entities))
        changed = True
        out["added"] = {"columns": report["columns"], "beams": report["beams"]}
    for _round in range(MAX_ROUNDS):
        result = analyze_cached(doc)
        out["result"], out["rounds"] = result, _round + 1
        fixes = [(mid, e["proposal"]) for mid, e in result.get("members", {}).items()
                 if not e.get("ok", True) and e.get("proposal") and mid in doc.entities]
        if not fixes:
            break
        cmd = CompositeCommand([UpdateEntity(mid, dict(p)) for mid, p in fixes], "Διατομές από τη στατική")
        (stack.amend if changed else stack.execute)(cmd)
        changed = True
        out["resized"] += [doc.get(mid).name or mid for mid, _p in fixes]
    out["result"] = analyze_cached(doc)
    return out


def summary(out):
    if out["bearing_walls"]:
        return "Φέρουσα τοιχοποιία / Isotex: οι τοίχοι είναι ο φέρων οργανισμός — χωρίς κολόνες· οπλισμός πλακών στο Δομικά → Οπλισμός πλακών"
    r = out["result"]
    if r is None:
        return "Δεν υπάρχουν τοίχοι ή φέρων οργανισμός για υπολογισμό"
    if r.get("error"):
        return f"Στατική: {r['error']}"
    members = list(r["members"].values())
    cols = sum(m["kind"] == "column" for m in members)
    beams = sum(m["kind"] == "beam" for m in members)
    failing = sum(not m.get("ok", True) for m in members)
    fd = r.get("foundation") or {}
    text = (f"Κολόνες {cols}, δοκάρια {beams}, πέδιλα {len(fd.get('footings', []))}, συνδετήριες {len(fd.get('ties', []))}"
            + (f", πεδιλοδοκοί {len(fd['strips'])}" if fd.get('strips') else "")
            + (f" · αυξήθηκαν διατομές: {', '.join(out['resized'][:6])}" if out["resized"] else "")
            + (f" · ⚠ {failing} μέλη χωρίς επαρκή τυπική διατομή" if failing else " · όλα επαρκούν"))
    return text
