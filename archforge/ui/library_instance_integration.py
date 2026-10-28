"""Placed-library-object instance semantics.

Library catalogue assets are immutable definitions.  Every placement creates a
new Document entity that references the source asset but owns all mutable state:
transform, size, materials and later sculpt/modifier overrides.
"""
from __future__ import annotations


def library_instance_params(record, *, x: float, y: float, z: float) -> dict:
    """Return fresh mutable params for one placement of an immutable asset."""
    w, d, h = (float(v) for v in record["size"])
    asset_id = str(record["id"])
    params = {
        "x": float(x),
        "y": float(y),
        "z": float(z),
        "rotation": 0.0,
        "width": w,
        "depth": d,
        "height": h,
        "uniform": 1.0,
        # ``asset`` remains the geometry-definition reference used by the
        # existing renderer.  The source fields below are immutable provenance
        # for Reset/default behaviour of this particular placed instance.
        "asset": asset_id,
        "source_asset_id": asset_id,
        "source_size": [w, d, h],
        "material_id": "",
        "surface_materials": {},
    }
    if record.get("lights"):
        import copy
        params.update(light_sources=copy.deepcopy(record["lights"]), light_level=1.0,
                      light_enabled=1.0, light_shadows=1.0)
    return params


def source_size_for_instance(params) -> tuple[float, float, float] | None:
    """Original size captured when the instance was placed.

    Older project files do not have ``source_size``; for those, fall back to
    the referenced asset's native size without ever modifying that asset.
    """
    raw = params.get("source_size")
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        try:
            values = tuple(float(v) for v in raw)
            if all(v > 0 for v in values):
                return values
        except (TypeError, ValueError):
            pass

    from archforge.library.assets import load_asset

    asset_id = str(params.get("source_asset_id") or params.get("asset") or "")
    asset = load_asset(asset_id) if asset_id else None
    if asset is None:
        return None
    try:
        values = tuple(float(v) for v in asset["size"])
    except (KeyError, TypeError, ValueError) as exc:
        from archforge.core.notices import not_computed
        not_computed("library.size", f"«{asset_id}»: δεν είναι γνωστό το αρχικό μέγεθος, η επαναφορά μεγέθους δεν "
                     "γίνεται", exc=exc)
        return None
    return values if len(values) == 3 and all(v > 0 for v in values) else None


def install_library_instance_model(MainWindow):
    """Install immutable-definition / mutable-instance behaviour once."""
    if getattr(MainWindow, "_archforge_library_instance_model", False):
        return

    from archforge.core.commands import AddEntity, UpdateEntity
    from archforge.core.model import Entity
    from archforge.library.objects import SIZE_KEYS
    from archforge.ui import object_modifier as om

    def place_library_object(self, x, y):
        record = getattr(self, "_pending_library_asset", None)
        if record is None:
            return None
        params = library_instance_params(
            record,
            x=float(x),
            y=float(y),
            z=float(self.doc.work_plane.origin[2]),
        )
        obj = Entity("library_object", params, name=str(record["name"]))
        self.stack.execute(AddEntity(obj))
        self._redraw_views(all_views=True)
        self.statusBar().showMessage(
            f"{record['name']}: μέγεθος/περιστροφή στις Ιδιότητες "
            "(uniform=1 κρατά αναλογίες) — κλικ για επόμενο, Esc για τέλος",
            6000,
        )
        return obj

    MainWindow._place_library_object = place_library_object

    # Reset must restore the immutable placement defaults captured in the
    # instance, not write into or depend on mutating the library definition.
    def reset_size(self):
        size = source_size_for_instance(self.entity.params)
        if size is None:
            return
        self._execute(UpdateEntity(
            self.entity_id,
            dict(zip(SIZE_KEYS, size)),
        ))

    om.ObjectModifierDialog.reset_size = reset_size
    MainWindow._archforge_library_instance_model = True
