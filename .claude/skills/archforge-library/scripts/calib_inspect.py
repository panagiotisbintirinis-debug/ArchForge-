#!/usr/bin/env python3
"""Read-only inspector for Home Designer / Chief Architect ``.calib`` catalogs.

A ``.calib`` file is a plain SQLite database.  This script opens it read-only,
lists the catalog tree and every library object, and decodes the parts of the
material record we understand (base colour, texture file name, texture repeat).

It never writes to the catalog and never copies texture images.  Output goes to
stdout (or ``--out``) as JSON so it can be studied or diffed.  Anything derived
from a Home Designer catalog is licensed content of Chief Architect and its
manufacturers: keep it on the owner's machine, never commit or redistribute it.

Usage:
    python calib_inspect.py CATALOG.calib [--out result.json] [--hex]
"""
import argparse
import json
import re
import sqlite3
import struct
import sys
import xml.etree.ElementTree as ET

import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from calib_open import connect_ro, open_catalog, resolve  # noqa: E402

# Object Type values observed so far (LibraryObjects.Type).  Unknown types are
# reported as "type-<n>" rather than guessed.
KNOWN_TYPES = {8: "material", 10: "backdrop"}


def _open_readonly(path):
    return open_catalog(path)


def _tree(conn):
    """Return {object_id: [folder, subfolder, ...]} from the TreeView XML."""
    row = conn.execute("SELECT LibraryView FROM LibraryViews LIMIT 1").fetchone()
    if not row or not row[0]:
        return {}
    text = row[0]
    # Stored wrapped in single quotes: '<?xml ...>...</TreeView>\n'
    text = text[text.find("<"):text.rfind(">") + 1] if "<" in text else text
    folders = {}

    def walk(node, trail):
        for child in node:
            if child.tag == "Directory":
                walk(child, trail + [child.get("Name", "")])
            elif child.tag == "Item":
                folders[int(child.get("Id"))] = trail

    try:
        walk(ET.fromstring(text.encode("utf-8")), [])
    except ET.ParseError:
        return {}
    return folders


def _keywords(conn, object_id):
    rows = conn.execute(
        "SELECT k.Keyword FROM Keywords4LibraryObjects m JOIN Keywords k "
        "ON k.KeywordId = m.KeywordId WHERE m.LibraryObjectId = ?", (object_id,))
    return sorted({r[0] for r in rows})


def _lp_string(blob, at):
    """Length-prefixed (uint32, includes trailing NUL) string at ``at``."""
    if at + 4 > len(blob):
        return None, at
    n = struct.unpack_from("<I", blob, at)[0]
    if n <= 0 or at + 4 + n > len(blob):
        return None, at
    raw = blob[at + 4: at + 4 + n].rstrip(b"\0")
    return raw.decode("latin-1"), at + 4 + n


def decode_material(name, blob):
    """Decode colour and texture fields of a material record (Type 8).

    Layout observed in IceStone.calib (two record revisions):
      <uint32 len><name>  then 5 bytes, then either
        R G B FF 00 00 00 FF ...        (newer records)
        FF FF R G B 00 00 00 00 ...     (older records)
      later: <uint32 len><texture path incl. NUL> <float64 repeat_u> <float64 repeat_v>
    Repeat values are inches in the catalogs seen so far (unverified).
    """
    out = {}
    nb = name.encode("latin-1", "replace")
    i = blob.find(struct.pack("<I", len(nb)) + nb)
    if i >= 0:
        c = blob[i + 4 + len(nb) + 5: i + 4 + len(nb) + 15]
        if len(c) == 10:
            if c[0:2] == b"\xff\xff" and c[5:10] == b"\0" * 5:
                rgb = c[2:5]
            else:
                rgb = c[0:3]
            out["color"] = "#%02x%02x%02x" % tuple(rgb)
    m = re.search(rb"[A-Za-z]:[\\/][ -~]{1,400}?\.(?:jpe?g|png|bmp|tga|tiff?)", blob, re.I)
    if m:
        path = m.group(0).decode("latin-1")
        out["texture_source_path"] = path
        out["texture_file"] = re.split(r"[\\/]", path)[-1]
        end = m.end() + 1  # trailing NUL
        if end + 16 <= len(blob):
            u, v = struct.unpack_from("<dd", blob, end)
            if 0 < u < 10000 and 0 < v < 10000:
                out["texture_repeat"] = [u, v]
                out["texture_repeat_unit"] = "inch (assumed)"
    return out


def inspect(path, with_hex=False):
    conn = _open_readonly(path)
    folders = _tree(conn)
    copyrights = dict(conn.execute("SELECT CopyrightId, Copyright FROM Copyrights"))
    objects = []
    for oid, name, typ, cid, metric, uid in conn.execute(
            "SELECT LibraryObjectId, Name, Type, CopyrightId, Metric, UniqueId "
            "FROM LibraryObjects ORDER BY LibraryObjectId"):
        row = conn.execute(
            "SELECT Data FROM Data4LibraryObjects WHERE LibraryObjectId = ?", (oid,)).fetchone()
        blob = bytes(row[0]) if row and row[0] is not None else b""
        item = {
            "id": oid,
            "name": name,
            "type": KNOWN_TYPES.get(typ, f"type-{typ}"),
            "folder": folders.get(oid, []),
            "keywords": _keywords(conn, oid),
            "copyright": copyrights.get(cid),
            "metric": bool(metric),
            "unique_id": uid,
            "data_bytes": len(blob),
            "provenance": {"source": "home-designer-calib", "redistributable": False},
        }
        if typ == 8:
            item.update(decode_material(name, blob))
        elif typ == 10:
            m = re.search(rb"[A-Za-z]:[\\/][ -~]{1,400}?\.(?:jpe?g|png)", blob, re.I)
            if m:
                item["image_file"] = re.split(r"[\\/]", m.group(0).decode("latin-1"))[-1]
        if with_hex:
            item["data_hex"] = blob.hex()
        objects.append(item)
    return {"catalog": path, "object_count": len(objects), "objects": objects}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("catalog")
    ap.add_argument("--out")
    ap.add_argument("--hex", action="store_true", help="include raw record bytes")
    a = ap.parse_args(argv)
    text = json.dumps(inspect(a.catalog, a.hex), ensure_ascii=False, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    main()
