"""Length units the human sees (owner 30/10: «όλοι δουλεύουν σε εκατοστά»).

The model stays in metres; only what is shown and written for others changes:

* ``display_unit()`` — dimensions in the plan and the selected wall's distances: ``mm`` / ``cm`` (default) / ``m``;
* ``ifc_unit()`` — the length unit of an exported IFC: ``m`` (default) or ``mm`` (what many ArchiCAD / Revit
  templates use); the importer reads either.

Program settings (``settings.json`` of the user data folder, like the keyboard shortcuts), not project data.
"""
from __future__ import annotations

LENGTH_UNITS = {"mm": ("χιλιοστά (mm)", 1000.0, 0), "cm": ("εκατοστά (cm)", 100.0, 1), "m": ("μέτρα (m)", 1.0, 2)}
IFC_UNITS = {"m": "μέτρα", "mm": "χιλιοστά"}
DEFAULT_DISPLAY, DEFAULT_IFC = "cm", "m"
_cache = {}


def _settings():
    from archforge.ui.autosave import load_settings
    return load_settings()


def display_unit():
    if "display" not in _cache:
        u = str(_settings().get("length_unit", DEFAULT_DISPLAY))
        _cache["display"] = u if u in LENGTH_UNITS else DEFAULT_DISPLAY
    return _cache["display"]


def ifc_unit():
    if "ifc" not in _cache:
        u = str(_settings().get("ifc_length_unit", DEFAULT_IFC))
        _cache["ifc"] = u if u in IFC_UNITS else DEFAULT_IFC
    return _cache["ifc"]


def save(display=None, ifc=None):
    """Store the choices (``UserDataError``: the settings file could not be read, nothing written)."""
    from archforge.ui.autosave import save_settings
    changes = {}
    if display is not None:
        if display not in LENGTH_UNITS:
            raise ValueError(f"άγνωστη μονάδα {display}")
        changes["length_unit"] = display
    if ifc is not None:
        if ifc not in IFC_UNITS:
            raise ValueError(f"άγνωστη μονάδα {ifc}")
        changes["ifc_length_unit"] = ifc
    if changes:
        save_settings(changes)
    _cache.clear()


def reset_cache():
    _cache.clear()


def fmt_length(metres, unit=None):
    """A length as drawn: «345» (cm), «345,5» (cm, half), «3450» (mm), «3,45» (m) — Greek comma, no unit sign."""
    unit = unit or display_unit()
    _label, k, decimals = LENGTH_UNITS[unit]
    v = float(metres) * k
    if unit == "cm":
        r = round(v, 1)
        text = f"{r:.0f}" if abs(r - round(r)) < 1e-9 else f"{r:.1f}"
    else:
        text = f"{v:.{decimals}f}"
    return text.replace(".", ",")


def suffix(unit=None):
    return {"mm": "mm", "cm": "cm", "m": "m"}[unit or display_unit()]
