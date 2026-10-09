"""The live measurement line over the plan, in Greek (raw tool values → «Μήκος 4,25 m · Γωνία 90°»)."""
from __future__ import annotations

# key: (label, unit, decimals); None = not shown (internal state).
LABELS = {
    "length": ("Μήκος", "m", 2), "angle_deg": ("Γωνία", "°", 1), "corner_deg": ("Γωνία με προηγούμενο", "°", 1),
    "x": ("X", "m", 2), "y": ("Y", "m", 2), "z": ("Στάθμη", "m", 2),
    "dx": ("ΔX", "m", 2), "dy": ("ΔY", "m", 2), "dz": ("ΔZ", "m", 2),
    "width": ("Πλάτος", "m", 2), "depth": ("Βάθος", "m", 2), "height": ("Ύψος", "m", 2), "thickness": ("Πάχος", "m", 2),
    "sill": ("Ποδιά", "m", 2), "offset": ("Θέση", "m", 2), "distance": ("Απόσταση", "m", 2),
    "diameter": ("Διάμετρος", "m", 3), "diameter_x": ("Πλάτος", "m", 2), "diameter_y": ("Βάθος", "m", 2),
    "base_z": ("Βάση", "m", 2), "top_z": ("Κορυφή", "m", 2), "level_z": ("Στάθμη", "m", 2), "floor_level": ("Δάπεδο", "m", 2),
    "rotation": ("Περιστροφή", "°", 1), "slope_pct": ("Κλίση", "%", 1), "run_length": ("Ανάπτυξη", "m", 2),
    "risers": ("Ρίχτια", "", 0), "riser": ("Ρίχτι", "m", 3), "tread": ("Πάτημα", "m", 3), "rise": ("Ύψος", "m", 2),
    "elevation": ("Υψόμετρο", "m", 2), "pivot_x": ("Κέντρο X", "m", 2), "pivot_y": ("Κέντρο Y", "m", 2),
    "cx": ("Κέντρο X", "m", 2), "cy": ("Κέντρο Y", "m", 2),
    "angle_locked": None, "magnet": None, "previous_deg": None, "valid": None, "surface_u": None,
    "active_index": None, "candidates": None, "option": None, "chosen": None,
}


def _num(v, decimals):
    return f"{v:.{decimals}f}".replace(".", ",")


def hud_text(hud):
    """One line: known values in Greek with units; magnet/lock as a short note; internal values hidden."""
    parts = []
    for k, v in hud.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        spec = LABELS.get(k, (k, "", 3))
        if spec is None:
            continue
        label, unit, dec = spec
        parts.append(f"{label} {_num(float(v), dec)}{' ' + unit if unit and unit not in '°%' else unit}")
    magnet = float(hud.get("magnet", 0) or 0)
    if magnet:
        parts.append(f"μαγνήτης {magnet:g}°")
    elif hud.get("angle_locked"):
        parts.append("κλειδωμένη γωνία")
    return "  ·  ".join(parts)
