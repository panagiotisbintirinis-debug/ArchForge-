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

import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from calib_open import connect_ro, open_catalog, resolve  # noqa: E402

# Tables without a LibraryObjectId column are copied whole only if small.
SMALL_TABLE_BYTES = 2 * 1024 * 1024


def _ro(path):
    return connect_ro(path)


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


def sample(src, dst, ids, max_blob=None):
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
        elif name == "AssociatedData":
            # Assumed (unverified) to share ids with LibraryObjects; may hold textures.
            rows = s.execute(f'SELECT * FROM "{name}" WHERE AssociatedDataId IN ({q})', ids).fetchall()
        elif name == "PlantData":
            rows = s.execute(
                f'SELECT * FROM "{name}" WHERE PlantDataId IN (SELECT PlantDataId FROM '
                f'LibraryObjects WHERE LibraryObjectId IN ({q}))', ids).fetchall()
        elif _table_bytes(s, name)[1] <= SMALL_TABLE_BYTES:
            rows = s.execute(f'SELECT * FROM "{name}"').fetchall()
        else:
            report[name] = "skipped (large, no object link)"
            continue
        if max_blob:
            # Study samples may keep only the head of each big BLOB (header +
            # first records); enough to learn a layout, small enough to share.
            rows = [tuple(v[:max_blob] if isinstance(v, bytes) and len(v) > max_blob else v
                          for v in r) for r in rows]
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
    ap.add_argument("--list", action="store_true", help="list objects by SymbolData size")
    ap.add_argument("--smallest", action="store_true",
                    help="sample the object with the smallest non-empty SymbolData (whole, untruncated)")
    ap.add_argument("--out")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--ids", help="comma-separated LibraryObjectId values")
    ap.add_argument("--max-blob-kb", type=int, help="truncate each BLOB to this many KB")
    a = ap.parse_args(argv)
    a.source = resolve(a.source)
    conn = _ro(a.source)
    st = stats(conn)
    print("Object types:", st["types"])
    for name, (rows, size) in sorted(st["tables"].items(), key=lambda t: -t[1][1]):
        print(f"  {name:30s} rows={rows:<7d} MB={size / 1048576:.2f}")
    if a.list:
        rows = conn.execute(
            "SELECT l.LibraryObjectId, l.Type, IFNULL(LENGTH(s.SymbolData),0), l.Name FROM LibraryObjects l "
            "LEFT JOIN SymbolData4LibraryObjects s USING(LibraryObjectId) ORDER BY 3")
        for oid, typ, size, name in rows:
            print(f"  id={oid:<6d} type={typ:<4d} MB={size / 1048576:6.2f}  {name}")
    if a.out:
        if a.smallest:
            ids = [conn.execute(
                "SELECT LibraryObjectId FROM SymbolData4LibraryObjects WHERE LENGTH(SymbolData) > 1000 "
                "ORDER BY LENGTH(SymbolData) LIMIT 1").fetchone()[0]]
        elif a.ids:
            ids = [int(x) for x in a.ids.split(",")]
        else:
            ids = _pick(conn, a.count)
        names = dict(conn.execute(
            f'SELECT LibraryObjectId, Name FROM LibraryObjects WHERE LibraryObjectId IN '
            f'({",".join("?" * len(ids))})', ids)) if ids else {}
        conn.close()
        report = sample(a.source, a.out, ids,
                        a.max_blob_kb * 1024 if a.max_blob_kb else None)
        print("Sampled objects:", {i: names.get(i) for i in ids})
        print("Copied rows:", report)
        print(f"Wrote {a.out}: {os.path.getsize(a.out) / 1048576:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
