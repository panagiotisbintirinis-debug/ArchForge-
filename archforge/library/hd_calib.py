"""Read Home Designer / Chief Architect catalogs (.calib, .calibz) read-only.

Format notes and verification status live in
``.claude/skills/archforge-library/references/calib-format.md``.

Catalog content is licensed to the user by Chief Architect and the named
manufacturers: ArchForge reads it in place for the owner's own use and never
bundles or redistributes it.
"""
import gzip
import math
import pathlib
import sqlite3
import struct
import tempfile
import zipfile

SQLITE_MAGIC = b"SQLite format 3\x00"
INCH = 0.0254

# --------------------------------------------------------------- containers


def connect_ro(path):
    # Path.as_uri() gives file:///C:/... on Windows; a bare "file:C:\\..." fails there.
    uri = pathlib.Path(path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _carve_sqlite(data, at):
    page = struct.unpack_from(">H", data, at + 16)[0]
    page = 65536 if page == 1 else page
    count = struct.unpack_from(">I", data, at + 28)[0]
    size = page * count if count else len(data) - at
    return data[at:at + size]


def resolve(path):
    """Return a filesystem path to a plain SQLite catalog for ``path``.

    ``.calib`` is plain SQLite.  ``.calibz`` is a bundle whose wrapper is not
    fully known: a zip holding a .calib, a gzip stream, or any file that
    embeds an SQLite image are accepted.
    """
    with open(path, "rb") as f:
        head = f.read(16)
    if head == SQLITE_MAGIC:
        return str(path)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="calibz-"))
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            inner = [n for n in z.namelist() if n.lower().endswith(".calib")]
            if inner:
                return z.extract(inner[0], tmp)
            raise ValueError(f"{path}: zip without a .calib inside")
    data = pathlib.Path(path).read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    at = data.find(SQLITE_MAGIC)
    if at < 0:
        raise ValueError(f"{path}: no catalog found inside (first bytes {data[:32].hex(' ')})")
    out = tmp / (pathlib.Path(path).stem + ".calib")
    out.write_bytes(_carve_sqlite(data, at))
    return str(out)


def open_catalog(path):
    return connect_ro(resolve(path))

# ------------------------------------------------------------------- meshes

MESH_RECORD = b"\xcd\xab\x74\x00"
MAX_ABS = 2000.0       # |coordinate| in inches; larger is not furniture geometry
MAX_VERTS = 256        # per polygon
MAX_INDEX = 4096       # polygon header surface index


def parse_mesh_record(blob, m):
    """Parse the mesh record (``CD AB 74 00``) at offset ``m``.

    Layout (verified on three catalogs)::

        +0 CD AB 74 00, +4 uint16 version, +6 FF*4, +10 uint32 P polygons,
        then P records: uint16 n, uint16 flags, uint32 index, uint16 ?,
        n*3 float64 vertices (inches), n int32 neighbours, uint32 k,
        k*2 float64 UVs, 2 float64.

    Returns ``(polygons, end, complete)``; ``complete`` is False for truncated
    or undecodable data (the polygons read so far are still returned).
    """
    if blob[m:m + 4] != MESH_RECORD or m + 14 > len(blob):
        return [], m, False
    count = struct.unpack_from("<I", blob, m + 10)[0]
    p = m + 14
    polys = []
    for _ in range(count):
        if p + 10 > len(blob):
            return polys, p, False
        n = struct.unpack_from("<H", blob, p)[0]
        index = struct.unpack_from("<I", blob, p + 4)[0]
        vend = p + 10 + 24 * n
        if not (3 <= n <= MAX_VERTS and index < MAX_INDEX) or vend + 4 * n + 4 > len(blob):
            return polys, p, False
        vals = struct.unpack_from(f"<{3 * n}d", blob, p + 10)
        if not all(math.isfinite(v) and abs(v) < MAX_ABS for v in vals):
            return polys, p, False
        polys.append([vals[3 * i:3 * i + 3] for i in range(n)])
        t = vend + 4 * n
        k = struct.unpack_from("<I", blob, t)[0]
        if k > MAX_VERTS:
            return polys, p, False
        p = t + 4 + 16 * k + 16
    return polys, p, p <= len(blob)


def find_meshes(blob):
    """Return ``[(offset, polygons, complete)]`` for every mesh record."""
    out = []
    m = blob.find(MESH_RECORD)
    while m >= 0:
        polys, end, complete = parse_mesh_record(blob, m)
        if polys:
            out.append((m, polys, complete))
        m = blob.find(MESH_RECORD, end if complete else m + 1)
    return out


def triangulate(polys):
    """Fan-triangulate polygons (lists of points) into point triples."""
    return [(pl[0], pl[i], pl[i + 1]) for pl in polys for i in range(1, len(pl) - 1)]

# ------------------------------------------------------------------ objects


def catalog_objects(conn):
    """Objects that carry 3D symbol data: ``[(id, name, type, bytes)]``."""
    return [tuple(r) for r in conn.execute(
        "SELECT l.LibraryObjectId, l.Name, l.Type, LENGTH(s.SymbolData) FROM LibraryObjects l "
        "JOIN SymbolData4LibraryObjects s USING(LibraryObjectId) "
        "WHERE LENGTH(s.SymbolData) > 1000 ORDER BY l.Name")]


def object_parts(conn, object_id):
    """Complete meshes of one catalog object, each as metre triangles.

    Returns ``[(offset, triangles_m)]``.  Parts of grouped objects are in
    their own local coordinates (placement inside the group is not decoded),
    so callers offer them as separate library items.
    """
    row = conn.execute(
        "SELECT SymbolData FROM SymbolData4LibraryObjects WHERE LibraryObjectId = ?",
        (int(object_id),)).fetchone()
    if not row or row[0] is None:
        return []
    parts = []
    for m, polys, complete in find_meshes(bytes(row[0])):
        if complete:
            tris = [tuple(tuple(c * INCH for c in v) for v in t) for t in triangulate(polys)]
            parts.append((m, tris))
    return parts
