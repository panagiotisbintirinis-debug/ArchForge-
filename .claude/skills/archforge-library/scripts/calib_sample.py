#!/usr/bin/env python3
"""Cut a small study sample out of a large Home Designer ``.calib`` catalog.

Big catalogs (furniture, appliances) are tens of MB to GB.  To learn their
format we only need a few objects.  This script opens the source read-only,
prints where the bytes live (rows/bytes per table, object types), and writes a
new small SQLite file with the same schema containing only the chosen objects
and the rows they reference.

The sample is still licensed Home Designer content: use it for local format
study only and never commit it.

Usage:
    python calib_sample.py SOURCE.calib --stats
    python calib_sample.py SOURCE.calib --out sample.calib [--count 3] [--ids 12,40]
"""
import argparse
import os
import sqlite3
import sys
import tempfile
import zipfile

# Tables without a LibraryObjectId column are copied whole only if small.
SMALL_TABLE_BYTES = 2 * 1024 * 1024


def _unpack(path):
    """A .calibz is a zip holding the .calib (plus textures): use the inner .calib."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            inner = [n for n in z.namelist() if n.lower().endswith(".calib")]
            if not inner:
                raise SystemExit(f"{path}: zip without a .calib inside")
            return z.extract(inner[0], tempfile.mkdtemp(prefix="calibz-"))
    return path


def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _tables(conn):
    return [(n, sql) for n, sql in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]


def _columns(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _table_bytes(conn, table):
    cols = _columns(conn, table)
    expr = " + ".join(f'IFNULL(LENGTH("{c}"),0)' for c in cols) or "0"
    rows, total = conn.execute(f'SELECT COUNT(*), IFNULL(SUM({expr}),0) FROM "{table}"').fetchone()
    return rows, total


def stats(conn):
    out = {"tables": {}, "types": {}}
    for name, _ in _tables(conn):
        out["tables"][name] = _table_bytes(conn, name)
    if "LibraryObjects" in out["tables"]:
        for typ, n in conn.execute("SELECT Type, COUNT(*) FROM LibraryObjects GROUP BY Type"):
            out["types"][typ] = n
    return out


def _pick(conn, count):
    """Median-sized objects of the most common type (smallest ones are often stubs)."""
    typ = conn.execute(
        "SELECT Type FROM LibraryObjects GROUP BY Type ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
    if not typ:
        return []
    rows = conn.execute(
        "SELECT l.LibraryObjectId FROM LibraryObjects l LEFT JOIN Data4LibraryObjects d "
        "USING(LibraryObjectId) WHERE l.Type=? ORDER BY IFNULL(LENGTH(d.Data),0)",
        (typ[0],)).fetchall()
    mid = len(rows) // 2
    lo = max(0, mid - count // 2)
    return [r[0] for r in rows[lo:lo + count]]


def sample(src, dst, ids):
    s = _ro(src)
    if os.path.exists(dst):
        os.remove(dst)
    d = sqlite3.connect(dst)
    report = {}
    ids = list(ids)
    q = ",".join("?" * len(ids))
    for name, sql in _tables(s):
        if sql:
            d.execute(sql)
    names = [n for n, _ in _tables(s)]
    for name in names:
        cols = _columns(s, name)
        if "LibraryObjectId" in cols:
            rows = s.execute(f'SELECT * FROM "{name}" WHERE LibraryObjectId IN ({q})', ids).fetchall()
        elif name == "LibrarySymbolData":
            rows = s.execute(
                f'SELECT * FROM "{name}" WHERE LibSymDataId IN (SELECT LibSymDataId FROM '
                f'LibraryObjects WHERE LibraryObjectId IN ({q}))', ids).fetchall()
        elif name == "PlantData":
            rows = s.execute(
                f'SELECT * FROM "{name}" WHERE PlantDataId IN (SELECT PlantDataId FROM '
                f'LibraryObjects WHERE LibraryObjectId IN ({q}))', ids).fetchall()
        elif _table_bytes(s, name)[1] <= SMALL_TABLE_BYTES:
            rows = s.execute(f'SELECT * FROM "{name}"').fetchall()
        else:
            report[name] = "skipped (large, no object link)"
            continue
        if rows:
            d.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" * len(cols))})', rows)
        report[name] = len(rows)
    # Recreate views (e.g. PlantDataView) so the sample opens like the original.
    for (sql,) in s.execute("SELECT sql FROM sqlite_master WHERE type='view' AND sql IS NOT NULL"):
        d.execute(sql)
    d.commit()
    d.close()
    s.close()
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--ids", help="comma-separated LibraryObjectId values")
    a = ap.parse_args(argv)
    a.source = _unpack(a.source)
    conn = _ro(a.source)
    st = stats(conn)
    print("Object types:", st["types"])
    for name, (rows, size) in sorted(st["tables"].items(), key=lambda t: -t[1][1]):
        print(f"  {name:30s} rows={rows:<7d} MB={size / 1048576:.2f}")
    if a.out:
        ids = [int(x) for x in a.ids.split(",")] if a.ids else _pick(conn, a.count)
        names = dict(conn.execute(
            f'SELECT LibraryObjectId, Name FROM LibraryObjects WHERE LibraryObjectId IN '
            f'({",".join("?" * len(ids))})', ids)) if ids else {}
        conn.close()
        report = sample(a.source, a.out, ids)
        print("Sampled objects:", {i: names.get(i) for i in ids})
        print("Copied rows:", report)
        print(f"Wrote {a.out}: {os.path.getsize(a.out) / 1048576:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
