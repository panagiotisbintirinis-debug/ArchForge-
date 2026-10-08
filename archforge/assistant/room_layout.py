"""«Κουζίνα εδώ» / «Μπάνιο εδώ»: the assistant lays out a room, the user keeps editing it.

A layout is never a special object: it is ordinary ``cabinet``,
``library_object``, ``plumbing_point`` (and hood ``ventilation_point``)
entities, so every piece moves, changes and is deleted like any other.
They carry three plain parameters so the assistant can recognise them:

* ``layout_id``   — the layout they belong to (delete / re-fit as a whole);
* ``layout_spec`` — what the user chose (kitchen shape and guide legs on
  which walls, dishwasher, bath with shower or tub, variant), kept so the
  layout can be recomputed when the room changes;
* ``layout_role`` — sink, hob, fridge, wc … (rules and drag snapping);
* ``layout_host`` — on points and appliances that sit on a piece (the hob
  on its cabinet, the water point of a WC): they follow it when it moves.

Applying a proposal is ONE ``AddEntities`` (one undo); deleting a layout
one ``DeleteEntities``; re-fitting it to a changed room one composite.
"""
from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass, field
from typing import List

KINDS = {"kitchen": "Κουζίνα", "bath": "Μπάνιο"}
MEMBER_KINDS = ("cabinet", "library_object", "plumbing_point", "ventilation_point")


@dataclass
class LayoutProposal:
    kind: str                                   # 'kitchen' | 'bath'
    entities: list
    label: str
    notes: List[str] = field(default_factory=list)      # rules applied and measured values
    problems: List[str] = field(default_factory=list)   # what could not be met
    source: str = ""
    spec: dict = field(default_factory=dict)
    legs: list = field(default_factory=list)            # [(run, lo, hi)] drawn as the guide
    variant: int = 0
    variants: int = 1
    layout_id: str = ""

    def summary(self):
        counts = {}
        for e in self.entities:
            if e.kind in ("cabinet", "library_object"):
                counts[e.kind] = counts.get(e.kind, 0) + 1
        return counts


# ------------------------------------------------------------------ library assets
def core_asset(name):
    """``{"id", "size"}`` of a shipped library item, built into the local store if missing."""
    from archforge.library.assets import list_assets, store_asset
    for r in list_assets():
        if r["name"] == name and r.get("provenance", {}).get("source") == "archforge-core":
            return {"id": r["id"], "size": tuple(float(v) for v in r["size"])}
    from archforge.library import builder
    from archforge.library.catalog import specs
    spec = next((s for s in specs() if s["name"] == name), None)
    if spec is None:
        return None
    tris, colors, names = builder.build(spec)
    asset_id, size = store_asset(spec["name"], tris, {
        "source": "archforge-core", "license": "project", "redistributable": True,
        "reference": spec.get("reference", "standard furniture dimensions; online pictures as visual reference only"),
    }, colors=colors, category=spec["category"], part_names=names)
    return {"id": asset_id, "size": tuple(float(v) for v in size)}


def library_entity(name, run, s_mid, depth, z, role, *, size=None, label=None):
    """A library object with its back on ``run``'s face, centred at ``s_mid`` along it."""
    from archforge.core.model import Entity
    asset = core_asset(name)
    if asset is None:
        return None
    w, d, h = size or asset["size"]
    x, y = run.point(s_mid, (depth if depth is not None else d) / 2)
    uniform = 1.0 if size is None else 0.0
    return Entity("library_object", {"x": x, "y": y, "z": float(z), "rotation": run.rotation,
                                     "width": float(w), "depth": float(d), "height": float(h),
                                     "uniform": uniform, "asset": asset["id"], "layout_role": role},
                  name=label or name)


def cabinet_entity(cabinet_type, run, s0, width, level, role, name=None, **extra):
    """A parametric cabinet with its back on ``run``'s face, from ``s0`` along it (``level`` = floor; a
    wall unit's own ``z`` is its height above the floor)."""
    from archforge.core.model import Entity
    from archforge.kitchen.cabinets import TYPES, auto_doors, default_params
    p = default_params(cabinet_type, width=width)
    p.update(extra)
    if "doors" not in extra and p["doors"]:
        p["doors"] = auto_doors(cabinet_type, width)
    x, y = run.point(s0 + width / 2, float(p["depth"]) / 2)
    p.update(x=x, y=y, rotation=run.rotation, z=float(level) + (float(p["z"]) if cabinet_type == "wall" else 0.0),
             layout_role=role)
    return Entity("cabinet", p, name=name or TYPES[cabinet_type][0])


def point_entity(point_type, run, s_mid, z, host):
    from archforge.core.model import Entity
    from archforge.mep.plumbing import POINT_TYPES
    x, y = run.point(s_mid, 0.10)
    return Entity("plumbing_point", {"x": x, "y": y, "z": float(z), "point_type": point_type, "layout_host": host.id},
                  name=POINT_TYPES[point_type][0])


def finish(proposal, layout_id=None):
    """Stamp every entity with the layout id and the user's choices."""
    proposal.layout_id = layout_id or proposal.layout_id or uuid.uuid4().hex[:12]
    for e in proposal.entities:
        e.params["layout_id"] = proposal.layout_id
        e.params["layout_spec"] = copy.deepcopy(proposal.spec)
    return proposal


# ------------------------------------------------------------------ obstacles (shared)
def footprint_of(e):
    """Plan polygon of something that stands in the room, or None."""
    p = e.params
    if e.kind == "cabinet":
        from archforge.kitchen.cabinets import footprint
        return footprint(p)
    if e.kind in ("library_object", "box"):
        from archforge.library.objects import footprint
        return footprint(p)
    if e.kind == "structural_column":
        from archforge.kitchen.cabinets import plan_box
        return plan_box(float(p["x"]), float(p["y"]), float(p.get("rotation", 0.0)), float(p["width"]), float(p["depth"]))
    return None


def obstacles(doc, level, ignore=()):
    """Footprints of the things already standing on the storey (not ``ignore``)."""
    out = []
    for e in doc.entities.values():
        if e.id in ignore or e.kind not in ("cabinet", "library_object", "box", "structural_column"):
            continue
        z = float(e.params.get("z", 0.0))
        if not level - 0.05 <= z <= level + 2.5:
            continue
        poly = footprint_of(e)
        if poly:
            out.append((e, poly))
    return out


def run_interval(run, poly, depth):
    """Interval ``(s0, s1)`` a footprint takes along ``run`` within ``depth`` of its face, or None."""
    ss = [(x - run.a[0]) * run.u[0] + (y - run.a[1]) * run.u[1] for x, y in poly]
    dd = [(x - run.a[0]) * run.n[0] + (y - run.a[1]) * run.n[1] for x, y in poly]
    if min(dd) >= depth or max(dd) <= 0.0 or max(ss) <= 0.0 or min(ss) >= run.length:
        return None
    return min(ss), max(ss)


def subtract(intervals, cuts, min_len=0.0):
    out = []
    for lo, hi in intervals:
        parts = [(lo, hi)]
        for c0, c1 in cuts:
            nxt = []
            for a, b in parts:
                if c1 <= a or c0 >= b:
                    nxt.append((a, b))
                    continue
                if c0 > a:
                    nxt.append((a, c0))
                if c1 < b:
                    nxt.append((c1, b))
            parts = nxt
        out += [(a, b) for a, b in parts if b - a > min_len + 1e-9]
    return out


# ------------------------------------------------------------------ the layouts in the Document
def layout_of(doc, entity_id):
    e = doc.entities.get(entity_id)
    return e.params.get("layout_id") if e is not None else None


def members(doc, layout_id):
    return [e for e in doc.entities.values() if layout_id and e.params.get("layout_id") == layout_id]


def layouts(doc):
    """``{layout_id: [entities]}``."""
    out = {}
    for e in doc.entities.values():
        lid = e.params.get("layout_id")
        if lid and e.kind in MEMBER_KINDS:
            out.setdefault(lid, []).append(e)
    return out


def followers(doc, ids):
    """Things that sit on the moved pieces (hob, hood, water points) and move with them."""
    ids = set(ids)
    return [e.id for e in doc.entities.values() if e.params.get("layout_host") in ids and e.id not in ids]


def apply_command(proposal):
    from archforge.core.commands import AddEntities
    return AddEntities([e.clone() for e in proposal.entities])


def delete_command(doc, layout_id):
    from archforge.core.commands import DeleteEntities
    ids = [e.id for e in members(doc, layout_id)]
    return DeleteEntities(ids) if ids else None


def _wall_signature(doc, wall_ids):
    out = []
    for wid in wall_ids:
        e = doc.entities.get(wid)
        if e is None:
            out.append((wid, None))
            continue
        p = e.params
        out.append((wid, tuple(round(float(p[k]), 2) for k in ("x1", "y1", "x2", "y2", "thickness"))))
    return [[w, list(s) if s else None] for w, s in out]


def room_signature(doc, spec):
    return _wall_signature(doc, spec.get("walls", []))


def plan(doc, kind, room, *, legs=None, options=None, variant=0, z=None, ignore=(), keep_style=None):
    """Proposal of ``kind`` for ``room`` (legs = guide line intervals ``[(run, lo, hi)]`` or None)."""
    options = dict(options or {})
    if kind == "kitchen":
        from archforge.assistant.kitchen_layout import plan_kitchen
        proposal = plan_kitchen(doc, room, legs=legs, options=options, variant=variant, z=z, ignore=ignore)
    else:
        from archforge.assistant.bath_layout import plan_bath
        proposal = plan_bath(doc, room, legs=legs, options=options, variant=variant, z=z, ignore=ignore)
    if keep_style:
        for e in proposal.entities:
            if e.kind == "cabinet":
                e.params.update({k: v for k, v in keep_style.items() if k in ("front_style", "handle")})
    proposal.spec["signature"] = room_signature(doc, proposal.spec)
    return finish(proposal)


def legs_for_spec(runs, spec):
    """The guide legs of a stored layout on the runs of the (changed) room: same walls, same share of them."""
    if not spec.get("legs"):
        return None
    out = []
    for wid, f0, f1 in spec["legs"]:
        run = next((r for r in runs if wid in r.wall_ids), None)
        if run is None:
            return None
        out.append((run.index, f0 * run.length, f1 * run.length))
    from archforge.assistant.room_walls import order_legs
    return order_legs(runs, out)


def spec_legs(runs, legs):
    """Legs stored by wall id and share of the run, so they survive a moved wall."""
    out, walls = [], []
    for i, lo, hi in legs:
        r = runs[i]
        if not r.wall_ids or r.length <= 0:
            continue
        out.append([r.wall_ids[0], round(lo / r.length, 4), round(hi / r.length, 4)])
        walls.append(r.wall_ids[0])
    return out, walls


def refit(doc, layout_id):
    """Recompute a layout for its (changed) room with the same choices: ``(command, proposal)``."""
    from archforge.assistant.room_walls import room_runs
    from archforge.assistant.suggestions import room_at
    from archforge.core.commands import AddEntities, CompositeCommand, DeleteEntities
    old = members(doc, layout_id)
    if not old:
        return None, None
    spec = dict(old[0].params.get("layout_spec") or {})
    z = float(spec.get("z", doc.work_plane.origin[2]))
    pieces = [e for e in old if e.kind in ("cabinet", "library_object")] or old
    cx = sum(float(e.params["x"]) for e in pieces) / len(pieces)
    cy = sum(float(e.params["y"]) for e in pieces) / len(pieces)
    room = room_at(doc, cx, cy, z) or room_at(doc, *spec.get("point", (cx, cy)), z)
    if room is None:
        return None, None
    runs = room_runs(doc, room, z)
    legs = legs_for_spec(runs, spec)
    style = {}
    for key in ("front_style", "handle"):
        values = [e.params.get(key) for e in old if e.kind == "cabinet" and e.params.get(key)]
        if values:
            style[key] = max(set(values), key=values.count)
    proposal = plan(doc, spec.get("kind", "kitchen"), room, legs=legs, options=spec.get("options"),
                    variant=int(spec.get("variant", 0)), z=z, ignore={e.id for e in old}, keep_style=style)
    finish(proposal, layout_id)
    command = CompositeCommand([DeleteEntities([e.id for e in old]), AddEntities([e.clone() for e in proposal.entities])],
                               label="Αναπροσαρμογή διάταξης")
    return command, proposal


def refit_proposals(doc):
    """Βοηθός: layouts whose walls moved since they were laid out → «Αναπροσαρμογή διάταξης»."""
    from archforge.assistant.suggestions import Proposal
    out = []
    for lid, group in layouts(doc).items():
        spec = group[0].params.get("layout_spec") or {}
        if not spec.get("signature") or room_signature(doc, spec) == spec["signature"]:
            continue
        label = KINDS.get(spec.get("kind"), "Διάταξη")
        out.append(Proposal(
            f"LAY-1:{lid}", "hint", f"{label}: ο χώρος άλλαξε — αναπροσαρμογή διάταξης",
            "Οι τοίχοι όπου πατά η διάταξη μετακινήθηκαν. Η αναπροσαρμογή την ξαναϋπολογίζει για τον νέο χώρο, "
            "με τις ίδιες επιλογές σου (σχήμα, τοίχοι, συσκευές, πρόσοψη/χερούλι) — ένα undo.",
            "Ίδιοι κανόνες με την αρχική πρόταση (προτεινόμενες τιμές)",
            tuple(e.id for e in group), lambda d, i=lid: refit(d, i)[0]))
    return out


def ghost(proposal):
    """What the plan draws before «Εφαρμογή»: ``[(kind, points, closed)]`` (kind = base / wall / object / point)."""
    from archforge.kitchen.cabinets import footprint, front_line
    out = []
    for e in proposal.entities:
        p = e.params
        if e.kind == "cabinet":
            kind = "wall" if p.get("cabinet_type") == "wall" else "base"
            out.append((kind, footprint(p), True))
            out.append(("front", front_line(p), False))
        elif e.kind == "library_object":
            from archforge.library.objects import footprint as obj_footprint, plan_symbol_world
            role = p.get("layout_role")
            if role == "hood":
                continue
            out.append(("object", obj_footprint(p), True))
            out += [("symbol", pts, closed) for closed, pts in plan_symbol_world(p)]
        elif e.kind == "plumbing_point":
            x, y = float(p["x"]), float(p["y"])
            out.append(("point", [(x + 0.06 * math.cos(a * math.pi / 4), y + 0.06 * math.sin(a * math.pi / 4)) for a in range(8)], True))
    return out
