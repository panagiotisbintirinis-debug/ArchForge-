"""Open a Home Designer catalog (.calib or .calibz) read-only, on any OS.

* ``.calib`` is a plain SQLite file.
* ``.calibz`` is a bundle (catalog + textures).  Its wrapper is not known yet,
  so we accept: a zip holding a .calib, a gzip stream, or any file that
  contains an embedded SQLite image (located by its header and carved out
  using the page size/count stored in that header).
"""
import gzip
import pathlib
import sqlite3
import struct
import tempfile
import zipfile

SQLITE_MAGIC = b"SQLite format 3\x00"


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
    """Return a filesystem path to a plain SQLite catalog for ``path``."""
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
            raise SystemExit(f"{path}: zip without a .calib inside: {z.namelist()[:10]}")
    data = pathlib.Path(path).read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    at = data.find(SQLITE_MAGIC)
    if at < 0:
        raise SystemExit(
            f"{path}: no SQLite catalog found inside. First bytes: {data[:32].hex(' ')} "
            "(send this line so the wrapper can be decoded)")
    out = tmp / (pathlib.Path(path).stem + ".calib")
    out.write_bytes(_carve_sqlite(data, at))
    return str(out)


def open_catalog(path):
    return connect_ro(resolve(path))
