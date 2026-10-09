"""The user's own materials («Δικά μου υλικά») and supplier codes (no Qt).

ArchForge ships generic finishes only (``rendering/materials.py``): no
manufacturer catalogue, decor names or codes.  A contractor orders melamine
and worktops by HIS supplier's decor code, so:

* a material applied to an element can carry a «Κωδικός» and «Προμηθευτής»
  typed by the user.  They live on the entity params next to the material id,
  ``material_codes = {role: {"code": .., "supplier": ..}}``, where ``role`` is
  the surface key of ``surface_materials`` ("exterior", "front" …) or ``""``
  for the whole element (``material_id``);
* the user can make his own materials (name, code, supplier, colour, a preset
  whose look it inherits, category).  Ids start with ``user_``.  They are kept
  in ``settings.json`` of the user data folder (like the keyboard shortcuts),
  so every project sees them, and a material that is used is also copied into
  ``doc.materials`` so the project opens the same on another computer;
* codes can be imported from a CSV file (``κωδικός;όνομα;χρώμα;κατηγορία;
  προμηθευτής``), as exported by Excel on a Greek Windows (cp1253, ``;``).

Appearance only, like the presets: no physical property is claimed.
"""
from __future__ import annotations

import copy
import csv
import io
import re
import unicodedata
from typing import Mapping

USER_PREFIX = "user_"
SETTINGS_KEY = "user_materials"
DEFAULT_CATEGORY = "Δικά μου υλικά"
DEFAULT_BASE = "melamine_white"

_HEX = re.compile(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})")

# Materials of the user data folder (loaded lazily) and of opened projects.
_registry: dict[str, dict] = {}
_loaded = False


def is_user_material(material_id) -> bool:
    return isinstance(material_id, str) and material_id.startswith(USER_PREFIX)


# ----------------------------------------------------------------- spec ---

def normalise_color(text) -> str | None:
    """'#AbC', 'abcdef', ' #a1b2c3 ' -> '#aabbcc' / '#a1b2c3'; None if not a colour."""
    m = _HEX.fullmatch(str(text or "").strip())
    if not m:
        return None
    h = m.group(1).lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h


def build_spec(name, color=None, base_id=DEFAULT_BASE, category="", code="", supplier="") -> dict:
    """A user material spec: the look (roughness, pattern, use) of ``base_id``
    in the user's colour, with his name, category, code and supplier."""
    from archforge.rendering.materials import MATERIAL_PRESETS
    base_id = base_id if base_id in MATERIAL_PRESETS else DEFAULT_BASE
    base = MATERIAL_PRESETS[base_id]
    spec = {
        "name": str(name).strip() or str(code).strip() or "Υλικό χρήστη",
        "category": str(category).strip() or DEFAULT_CATEGORY,
        "color": normalise_color(color) or str(base["color"]),
        "roughness": float(base["roughness"]),
        "metalness": float(base["metalness"]),
        "use": list(base.get("use", ("έπιπλο",))),
        "base": base_id,
        "code": str(code).strip(),
        "supplier": str(supplier).strip(),
        "user": True,
    }
    if "opacity" in base:
        spec["opacity"] = float(base["opacity"])
    if base.get("pattern"):
        spec["pattern"] = copy.deepcopy(dict(base["pattern"]))
    return spec


def valid_spec(spec) -> bool:
    if not isinstance(spec, Mapping):
        return False
    try:
        return (bool(str(spec.get("name", "")).strip())
                and normalise_color(spec.get("color")) is not None
                and 0.0 <= float(spec.get("roughness", 0.5)) <= 1.0
                and 0.0 <= float(spec.get("metalness", 0.0)) <= 1.0)
    except (TypeError, ValueError):
        return False


def _clean(spec: Mapping) -> dict:
    out = copy.deepcopy(dict(spec))
    out["color"] = normalise_color(out.get("color")) or "#9a9a9a"
    out["use"] = tuple(out.get("use") or ("έπιπλο",))
    out.setdefault("category", DEFAULT_CATEGORY)
    out["user"] = True
    return out


def new_id(name, code="", taken=()) -> str:
    """``user_<slug>``, unique among ``taken`` (Greek letters kept as ASCII-safe slug)."""
    text = f"{code} {name}".strip() if code else str(name)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.translate(_GREEKLISH).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:40] or "material"
    base = USER_PREFIX + slug
    taken = set(taken) | set(_registry)
    out, n = base, 2
    while out in taken:
        out, n = f"{base}_{n}", n + 1
    return out


_GREEKLISH = str.maketrans({
    **dict(zip("αβγδεζηθικλμνξοπρστυφχψωςΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ",
               ["a", "v", "g", "d", "e", "z", "i", "th", "i", "k", "l", "m", "n", "x", "o", "p", "r", "s",
                "t", "y", "f", "ch", "ps", "o", "s",
                "a", "v", "g", "d", "e", "z", "i", "th", "i", "k", "l", "m", "n", "x", "o", "p", "r", "s",
                "t", "y", "f", "ch", "ps", "o"])),
})


# -------------------------------------------------------------- storage ---

def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    for material_id, spec in load_saved().items():
        _registry.setdefault(material_id, spec)


def load_saved() -> dict:
    """User materials kept in settings.json (user data folder)."""
    try:
        from archforge.ui.autosave import load_settings
        raw = load_settings().get(SETTINGS_KEY, {})
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): _clean(v) for k, v in raw.items() if is_user_material(k) and valid_spec(v)}


def _save_all() -> None:
    from archforge.ui.autosave import save_settings
    saved = {k: _json(v) for k, v in _registry.items() if v.get("saved", True)}
    save_settings({SETTINGS_KEY: saved})


def _json(spec: Mapping) -> dict:
    out = copy.deepcopy(dict(spec))
    out["use"] = list(out.get("use", ()))
    out.pop("saved", None)
    return out


def reload() -> None:
    """Forget the in-memory list and read settings.json again (tests, new data folder)."""
    global _loaded
    _registry.clear()
    _loaded = False
    _ensure_loaded()


def user_materials(doc=None) -> dict:
    """All user materials: settings.json, then those carried by ``doc``."""
    _ensure_loaded()
    out = {k: copy.deepcopy(v) for k, v in _registry.items()}
    for k, v in project_materials(doc).items():
        out.setdefault(k, v)
    return out


def save_material(material_id, spec) -> str:
    """Add or replace a user material in settings.json; returns its id."""
    _ensure_loaded()
    if not valid_spec(spec):
        raise ValueError("μη έγκυρο υλικό (όνομα και χρώμα χρειάζονται)")
    material_id = str(material_id) if is_user_material(material_id) else new_id(spec.get("name", ""), spec.get("code", ""))
    _registry[material_id] = _clean(spec)
    _save_all()
    return material_id


def save_many(items: Mapping[str, Mapping]) -> None:
    _ensure_loaded()
    for material_id, spec in items.items():
        if is_user_material(material_id) and valid_spec(spec):
            _registry[str(material_id)] = _clean(spec)
    _save_all()


def delete_material(material_id) -> bool:
    """Remove from settings.json; projects that use it keep their copy."""
    _ensure_loaded()
    if _registry.pop(str(material_id), None) is None:
        return False
    _save_all()
    return True


def lookup(material_id, doc=None) -> dict | None:
    """Spec of a user material: the project's copy first, so a project opens the same everywhere."""
    if not is_user_material(material_id):
        return None
    carried = project_materials(doc).get(material_id)
    if carried is not None:
        return carried
    _ensure_loaded()
    spec = _registry.get(material_id)
    return copy.deepcopy(spec) if spec is not None else None


def project_materials(doc) -> dict:
    """User materials carried in ``doc.materials`` (other entries there are not ours)."""
    raw = getattr(doc, "materials", None) or {}
    return {k: _clean(v) for k, v in raw.items() if is_user_material(k) and valid_spec(v)}


def adopt_project(doc) -> None:
    """Make a project's user materials pickable in this session (not saved to settings)."""
    _ensure_loaded()
    for material_id, spec in project_materials(doc).items():
        if material_id not in _registry:
            entry = dict(spec)
            entry["saved"] = False
            _registry[material_id] = entry


def carry_command(doc, material_id):
    """``SetMaterial`` that copies a used user material into the project, or None."""
    if not is_user_material(material_id):
        return None
    _ensure_loaded()
    spec = _registry.get(material_id)
    if spec is None:
        return None
    data = _json(spec)
    if (getattr(doc, "materials", {}) or {}).get(material_id) == data:
        return None
    from archforge.core.commands import SetMaterial
    return SetMaterial(material_id, data)


# ----------------------------------------------------- codes on entities ---

def codes_of(entity) -> dict:
    raw = (entity.params.get("material_codes") if entity is not None else None) or {}
    return {str(k): dict(v) for k, v in raw.items() if isinstance(v, Mapping)} if isinstance(raw, Mapping) else {}


def code_for(entity, role="", material_id=None, doc=None) -> dict:
    """``{"code", "supplier"}`` shown for a surface ``role`` ("" = whole element).

    The code typed on the element wins; otherwise a user material brings its own.
    """
    codes = codes_of(entity)
    entry = codes.get(str(role))
    if entry is None and role and not ((entity.params.get("surface_materials") or {}).get(role)):
        entry = codes.get("")       # surface without its own finish shows the element's
    entry = dict(entry or {})
    if not entry.get("code") and material_id:
        spec = lookup(material_id, doc)
        if spec:
            entry["code"] = spec.get("code", "")
            if not entry.get("supplier"):
                entry["supplier"] = spec.get("supplier", "")
    return {"code": str(entry.get("code", "") or "").strip(),
            "supplier": str(entry.get("supplier", "") or "").strip()}


def with_code(codes: Mapping, roles, code, supplier) -> dict:
    """New ``material_codes`` with ``roles`` set (empty code and supplier = removed)."""
    out = {str(k): dict(v) for k, v in (codes or {}).items()}
    code, supplier = str(code or "").strip(), str(supplier or "").strip()
    for role in roles:
        if code or supplier:
            out[str(role)] = {"code": code, "supplier": supplier}
        else:
            out.pop(str(role), None)
    return out


def label(name, code="", supplier="") -> str:
    """«Μελαμίνη δρυς — κωδ. 1234 (Προμηθευτής)» for lists and the Properties panel."""
    text = str(name)
    if code:
        text += f" — κωδ. {code}"
    if supplier:
        text += f" ({supplier})"
    return text


def assignments(doc, entity):
    """``[(role, material_id)]`` that an element actually shows (role "" = whole)."""
    out = []
    surface = entity.params.get("surface_materials") or {}
    if isinstance(surface, Mapping):
        out += [(str(r), str(m)) for r, m in surface.items() if m]
    if entity.params.get("material_id"):
        out.insert(0, ("", str(entity.params["material_id"])))
    return out


# ------------------------------------------------------------------ CSV ---

CSV_COLUMNS = ("κωδικός", "όνομα", "χρώμα", "κατηγορία", "προμηθευτής")
_HEADER_WORDS = {"κωδικος", "κωδικός", "code", "κωδ", "κωδ."}


def decode_bytes(data: bytes) -> str:
    """UTF-8 (with or without BOM), else Greek Windows cp1253."""
    for encoding in ("utf-8-sig", "cp1253", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_csv(data, base_id=DEFAULT_BASE, default_category="", default_supplier=""):
    """Read a supplier code list.

    Returns ``{"rows": [(id, spec)], "skipped": [(line, reason)], "separator": ";"}``.
    Columns: κωδικός; όνομα; χρώμα (hex, optional); κατηγορία (optional);
    προμηθευτής (optional).  A first line with column titles is skipped.
    """
    text = decode_bytes(data) if isinstance(data, (bytes, bytearray)) else str(data)
    lines = text.splitlines()
    sample = "\n".join(lines[:20])
    separator = ";" if sample.count(";") >= sample.count(",") else ","
    if separator == "," and sample.count("\t") > sample.count(","):
        separator = "\t"
    rows, skipped, taken = [], [], set()
    reader = csv.reader(io.StringIO(text), delimiter=separator)
    for number, cells in enumerate(reader, 1):
        cells = [c.strip() for c in cells]
        if not any(cells):
            continue
        if number == 1 and cells[0].lower().rstrip(":") in _HEADER_WORDS:
            continue
        cells += [""] * (5 - len(cells))
        code, name, color, category, supplier = cells[:5]
        if not code:
            skipped.append((number, "λείπει ο κωδικός"))
            continue
        if not name:
            skipped.append((number, f"«{code}»: λείπει το όνομα"))
            continue
        hex_color = normalise_color(color) if color else None
        if color and hex_color is None:
            skipped.append((number, f"«{code}»: το χρώμα «{color}» δεν είναι #rrggbb"))
            continue
        spec = build_spec(name, hex_color, base_id, category or default_category, code, supplier or default_supplier)
        material_id = existing_id_for(code, spec["supplier"]) or new_id(name, code, taken)
        taken.add(material_id)
        rows.append((material_id, spec))
    return {"rows": rows, "skipped": skipped, "separator": separator}


def existing_id_for(code, supplier="") -> str | None:
    """A user material with the same code (and supplier): re-import updates it."""
    _ensure_loaded()
    for material_id, spec in _registry.items():
        if spec.get("code") == str(code).strip() and str(spec.get("supplier", "")) == str(supplier).strip():
            return material_id
    return None
