"""Γλυπτική στο έδαφος (owner 29/10: «στο έδαφος δεν κάνει τίποτα»).

A stroke raises or lowers the site terrain smoothly around the point pressed; it is stored in the terrain itself
(``params['strokes']``, ``site/terrain.py``), so 3D, plan contours and sections read one ground.  While dragging, the
document is untouched (a preview mesh); releasing is one undoable command.  On a project without a terrain the
stroke adds the terrain too — still one undo.
"""
from __future__ import annotations

# Sculpt operations on the ground: up / down; «Πτυχή» = up with a sharp crest.  «Λείανση» has no meaning yet on
# strokes (nothing to average) — refused with a message rather than doing something else.
DIRECTION = {"pull": 1.0, "inflate": 1.0, "crease": 1.0, "push": -1.0, "recess": -1.0}
LABELS = {"pull": "ανύψωση", "inflate": "ανύψωση", "crease": "ανύψωση (πτυχή)", "push": "βύθιση", "recess": "βύθιση"}


def terrain_at(doc, x, y):
    from archforge.site.terrain import terrain_contains
    return next((e for e in doc.entities.values()
                 if e.kind == "terrain" and e.visible and terrain_contains(e.params, x, y)), None)


class TerrainStroke:
    """One stroke from press to release: ``update(amount)`` previews, ``commit()`` writes it, ``cancel()`` forgets."""

    def __init__(self, doc, stack, x, y, radius, operation):
        if operation not in DIRECTION:
            raise ValueError("Γλυπτική εδάφους: η «Λείανση» δεν εφαρμόζεται στο έδαφος — διάλεξε Τράβηγμα ή Σπρώξιμο")
        self.doc, self.stack = doc, stack
        self.x, self.y, self.radius, self.operation = float(x), float(y), float(radius), str(operation)
        self.amount = 0.0
        terrain = terrain_at(doc, x, y)
        if terrain is None:
            from archforge.site.terrain import default_terrain_params
            params = default_terrain_params(doc)
            # The site must hold the stroke: grow it around the point pressed if needed.
            params["x0"] = min(params["x0"], self.x - self.radius - 1.0)
            params["y0"] = min(params["y0"], self.y - self.radius - 1.0)
            params["x1"] = max(params["x1"], self.x + self.radius + 1.0)
            params["y1"] = max(params["y1"], self.y + self.radius + 1.0)
            from archforge.core.model import Entity
            self.new_terrain = Entity("terrain", params, name="Έδαφος")
            self.terrain_id = self.new_terrain.id
            self.base_params = params
        else:
            self.new_terrain = None
            self.terrain_id = terrain.id
            self.base_params = dict(terrain.params)

    def stroke(self):
        s = {"x": round(self.x, 4), "y": round(self.y, 4), "radius": round(self.radius, 4),
             "dz": round(DIRECTION[self.operation] * self.amount, 4)}
        if self.operation == "crease":
            s["sharp"] = 1
        return s

    def params(self):
        out = dict(self.base_params)
        out["strokes"] = list(out.get("strokes") or ()) + [self.stroke()]
        return out

    def update(self, amount):
        self.amount = max(0.0, float(amount))

    def preview_mesh(self):
        from archforge.geometry.mesh import MeshPayload
        from archforge.site.terrain import terrain_mesh, building_exclusions, barriers, green_roofs
        v, t, r = terrain_mesh(self.params(), exclusions=building_exclusions(self.doc), walls=barriers(self.doc),
                               floors=green_roofs(self.doc))
        return MeshPayload(v, t, r)

    def commit(self):
        """One undo: the stroke (and the terrain, when the project had none)."""
        from archforge.core.commands import AddEntity, UpdateEntity
        if self.new_terrain is not None:
            terrain = self.new_terrain.clone() if hasattr(self.new_terrain, "clone") else self.new_terrain
            terrain.params = self.params()
            self.stack.execute(AddEntity(terrain))
        else:
            self.stack.execute(UpdateEntity(self.terrain_id, {"strokes": self.params()["strokes"]}))
        return self.stroke()
