"""Build a scenario building from a short description, through the UI's own paths (common.Scenario steps).

``spec`` (dict):
  levels:     [(name, z)] in build order (the first one exists already when z == 0, «Ground»).
  storeys:    {name: {"outline": [...corners, closed], "ext": t, "walls": [((a), (b), t)], "openings": [(kind, x, y, w, kw)],
              "walls" items may carry a 4th value, their own height (garden wall, pool), "rooms": {name: (x, y)},
              "kitchen": (x, y) | None, "kitchen_shape": "I"/"L"/"U"/"auto", "baths": [((x, y), "shower"/"bathtub")],
              "furniture": [(name, x, y, turn)], "wall_types": {"ext": key, "int": key} | None, "floor": True}}
  stairs:     [(level_name, origin, pointer)]
  roof:       "gable" | "hip" | "flat" | None;  attic: True → «Οροφή σοφίτας» slab
  mep:        {"supply": (x, y), "heater": (level, x, y), "panel": (level, x, y), "manhole": (x, y),
               "washing_machine": (level, x, y) | None, "points": [(level, tool, x, y)]}
  pergolas:   [(material, (x1, y1), (x2, y2))] on the main storey
  foundation: "strips" | "auto" | "pads";  occupancy: settings key (e.g. "office")
Every room gets a ceiling light, a switch beside its door and sockets on its two longest walls; appliances from
the kitchen layout get their supply on the wall behind them.
"""
from __future__ import annotations

import math

from archforge.scenarios.common import Scenario


def build_spec(window, key, title, spec):
    s = Scenario(key, title, window)
    for name, z in spec["levels"]:
        if name in window.doc.levels:
            s.level(name)
        else:
            s.level(name, z)
        st = spec["storeys"][name]
        if st.get("outline"):
            for a, b in zip(st["outline"], st["outline"][1:]):
                s.wall(a, b, st.get("ext", 0.25), height=st.get("height", 2.7))
        for a, b, t, *h in st.get("walls", ()):
            s.wall(a, b, t, height=h[0] if h else st.get("height", 2.7))
        if st.get("wall_types"):
            _wall_types(s, window, st["wall_types"], z, st.get("ext", 0.25))
        for kind, x, y, w, *kw in st.get("openings", ()):
            s.opening(kind, x, y, w, **(kw[0] if kw else {}))
        for room, xy in st.get("rooms", {}).items():
            s.name_room(*xy, room)
        if st.get("floor", True):
            s.step(f"Δάπεδα (αυτόματα) — {name}", lambda: _floors(window))
    for level, origin, pointer in spec.get("stairs", ()):
        s.level(level)
        s.stair(origin, pointer)
    top = spec.get("top", spec["levels"][-1][0])
    s.level(top)
    roof = spec.get("roof")
    if roof in ("gable", "hip"):
        s.step(f"Κεραμοσκεπή ({roof})", lambda: _ok(window._create_pitched_roof(roof), "στέγη"))
        if spec.get("attic"):
            s.step("Οροφή σοφίτας — πλάκα", lambda: _ok(window._attic_ceilings("slab"), "οροφή σοφίτας"))
    elif roof == "flat":
        s.step("Επίπεδη στέγη / δώμα (αυτόματα)", lambda: _ok(window._auto_roofs(), "δώμα") if window._auto_roofs is not None else None)
    for name, _z in spec["levels"]:
        st = spec["storeys"][name]
        s.level(name)
        if st.get("kitchen"):
            s.layout("kitchen", *st["kitchen"], shape=st.get("kitchen_shape", "auto"))
        for xy, wet in st.get("baths", ()):
            s.layout("bath", *xy, wet=wet)
        for fname, x, y, turn in st.get("furniture", ()):
            s.furniture(fname, x, y, turn)
    _mep(s, window, spec)
    for material, a, b in spec.get("pergolas", ()):
        s.level(spec.get("main", spec["levels"][0][0]))
        s.step(f"Πέργκολα ({material})", lambda m=material, a=a, b=b: (window._place_pergola(m, a[0], a[1], b[0], b[1]), "πέργκολα")[1])
    if spec.get("occupancy") or spec.get("foundation"):
        def settings():
            from archforge.structure.analysis.settings import get_settings
            p = get_settings(window.doc)
            if spec.get("foundation"):
                p["foundation_type"] = spec["foundation"]
            if spec.get("occupancy"):
                p["occupancy"] = spec["occupancy"]
            window._apply_structural_settings(p)
            return f"θεμελίωση {p['foundation_type']} · χρήση {p['occupancy']}"
        s.step("Στοιχεία κτιρίου για στατική", settings)
    s.level(spec.get("main", spec["levels"][0][0]))

    def structure():
        out = window._design_structure()
        res = out.get("result") or {}
        if res.get("error"):
            raise ValueError(res["error"])
        from archforge.structure.design_all import summary
        return summary(out)
    s.step("Φέρων οργανισμός: κολόνες, δοκοί, θεμελίωση", structure)
    return s


def _ok(value, what):
    if not value:
        raise ValueError(f"δεν δημιουργήθηκε {what}")
    return what


def _floors(window):
    slab = window._create_auto_floors()
    if slab is None:
        raise ValueError("δεν δημιουργήθηκε δάπεδο")
    return "πλάκα δαπέδου"


def _wall_types(s, window, types, z, ext):
    """Wall assembly (Inspector ▸ Τύπος τοίχου) on every wall of the storey: ``{"ext": key, "int": key}`` by thickness."""
    def run():
        n = {}
        for e in list(window.doc.entities.values()):
            if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < 1e-3:
                side = "ext" if abs(float(e.params.get("thickness", 0.0)) - ext) < 1e-3 else "int"
                if types.get(side):
                    window._set_wall_type(e.id, types[side])
                    n[side] = n.get(side, 0) + 1
        return " · ".join(f"{v} {('εξωτερικοί' if k == 'ext' else 'εσωτερικοί')} → {types[k]}" for k, v in n.items())
    s.step("Τύπος τοίχων: " + " / ".join(types.values()), run)


def _mep(s, window, spec):
    mep = spec.get("mep", {})
    first = spec.get("main", spec["levels"][0][0])
    if mep.get("supply"):
        s.level(first)
        s.point("plumb_water_supply", *mep["supply"])
    for key, tool in (("heater", "plumb_water_heater"), ("washing_machine", "plumb_washing_machine")):
        if mep.get(key):
            lvl, x, y = mep[key]
            s.level(lvl)
            s.point(tool, x, y)
            s.point({"heater": "elec_water_heater", "washing_machine": "elec_washing_machine"}[key], x + 0.1, y)
    for lvl, tool, x, y in mep.get("points", ()):
        s.level(lvl)
        s.point(tool, x, y)
    if mep.get("manhole"):
        s.level(first)
        s.point("drain_manhole", *mep["manhole"])
    if mep.get("panel"):
        lvl, x, y = mep["panel"]
        s.level(lvl)
        s.point("elec_panel", x, y)
        s.point("elec_network_rack", x, y + 0.4)
    # Every room of every storey: light, switch by the door, two sockets.
    for name, z in spec["levels"]:
        if not spec["storeys"][name].get("room_points", True):
            continue                                       # a pool: no lights or sockets in the water
        s.level(name)
        from archforge.architecture.roof_need import OPEN_AIR_USES
        for face in list(window.doc.active_room_faces()):
            if window.doc.room_metadata(face.signature).get("use") in OPEN_AIR_USES:
                continue                                   # pool / courtyard: their lights are placed by hand
            for tool, xy in _room_points(window.doc, face, z):
                s.point(tool, *xy)
        st = spec["storeys"][name]
        if st.get("kitchen"):
            for appliance, tool in (("Εστία", "elec_cooker"), ("Πλυντήριο πιάτων", "elec_dishwasher"),
                                    ("Ψυγειοκαταψύκτης", "elec_socket"), ("Απορροφητήρας", "elec_socket")):
                xy = _behind_on_level(s, appliance, z)
                if xy is not None:
                    s.point(tool, *xy)


def _behind_on_level(s, name_part, z):
    for e in s.doc.entities.values():
        if e.kind in ("library_object", "cabinet") and name_part in (e.name or "") and -0.1 < float(e.params.get("z", 0.0)) - z < 2.6:
            p = e.params
            a = math.radians(float(p.get("rotation", 0.0)))
            d = float(p.get("depth", 0.6)) / 2 - 0.02
            return (round(float(p["x"]) - math.sin(a) * d, 3), round(float(p["y"]) + math.cos(a) * d, 3))
    return None


def _room_points(doc, face, z):
    from archforge.assistant.understanding import _opening_sides
    from archforge.geometry.regions import point_in_polygon
    from archforge.quantities.takeoff import net_polygon
    net = net_polygon(doc, face.polygon, z)
    cx = sum(p[0] for p in net) / len(net)
    cy = sum(p[1] for p in net) / len(net)
    if not point_in_polygon(cx, cy, net):
        cx, cy = net[0][0] * 0.5 + net[2 % len(net)][0] * 0.5, net[0][1] * 0.5 + net[2 % len(net)][1] * 0.5
    out = [("elec_light", (round(cx, 3), round(cy, 3)))]
    # Switch: beside the first door into this room, inside it.
    for d in doc.entities.values():
        if d.kind != "door" or d.parent_id not in doc.entities:
            continue
        sides = [q for q in _opening_sides(doc, d) if point_in_polygon(q[0], q[1], face.polygon)]
        if not sides:
            continue
        w = doc.get(d.parent_id).params
        L = math.hypot(float(w["x2"]) - float(w["x1"]), float(w["y2"]) - float(w["y1"])) or 1.0
        ux, uy = (float(w["x2"]) - float(w["x1"])) / L, (float(w["y2"]) - float(w["y1"])) / L
        # Beside the door leaf (narrow rooms: closer to the frame); last resort the jamb inside the room.
        q = next(((sides[0][0] + ux * off * sgn, sides[0][1] + uy * off * sgn)
                  for off in (float(d.params["width"]) / 2 + g for g in (0.2, 0.1, 0.06)) for sgn in (1, -1)
                  if point_in_polygon(sides[0][0] + ux * off * sgn, sides[0][1] + uy * off * sgn, net)), sides[0])
        out.append(("elec_switch", (round(q[0], 3), round(q[1], 3))))
        break
    # Sockets: middle of the two longest net edges, 12 cm inside.
    edges = sorted(((math.dist(net[i], net[(i + 1) % len(net)]), i) for i in range(len(net))), reverse=True)[:2]
    for _l, i in edges:
        a, b = net[i], net[(i + 1) % len(net)]
        L = math.dist(a, b) or 1.0
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        for sgn in (1, -1):
            q = (m[0] + nx * 0.12 * sgn, m[1] + ny * 0.12 * sgn)
            if point_in_polygon(q[0], q[1], net):
                out.append(("elec_socket", (round(q[0], 3), round(q[1], 3))))
                break
    return out
