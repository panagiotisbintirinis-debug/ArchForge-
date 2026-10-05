"""Contract for the read-only Home Designer catalog inspector (library skill).

Uses a synthetic SQLite catalog built here; no licensed .calib is committed.
"""
import importlib.util
import pathlib
import sqlite3
import struct

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/archforge-library/scripts/calib_inspect.py"


def _load():
    spec = importlib.util.spec_from_file_location("calib_inspect", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lp(s):
    b = s.encode("latin-1") + b"\0"
    return struct.pack("<I", len(b)) + b


def _material_blob(name, color_bytes, path, repeat):
    nb = name.encode("latin-1")
    return (b"\xcd\xab9\x00" + b"\x00" * 16 + struct.pack("<I", len(nb)) + nb
            + b"\x00" * 5 + color_bytes + b"\x00\x00\x05" + b"\x00" * 16
            + _lp(path) + struct.pack("<dd", repeat, repeat) + b"\x00" * 8)


def _catalog(path):
    c = sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE LibraryObjects (LibraryObjectId INTEGER PRIMARY KEY, Name TEXT, Type INTEGER,
      Lock INTEGER, CopyrightId INTEGER, Metric INTEGER, ElementVersion INTEGER, UniqueId TEXT);
    CREATE TABLE Data4LibraryObjects (LibraryObjectId INTEGER PRIMARY KEY, Data BLOB);
    CREATE TABLE Keywords (KeywordId INTEGER PRIMARY KEY, Keyword TEXT);
    CREATE TABLE Keywords4LibraryObjects (LibraryObjectId INTEGER, KeywordId INTEGER);
    CREATE TABLE Copyrights (CopyrightId INTEGER PRIMARY KEY, Copyright TEXT);
    CREATE TABLE LibraryViews (LibraryViewId INTEGER PRIMARY KEY, LibraryView TEXT, Name TEXT);
    """)
    c.execute("INSERT INTO Copyrights VALUES (1, 'Copyright Test Co')")
    c.execute("INSERT INTO Keywords VALUES (1, 'countertop')")
    rows = [
        (1, "New Style", b"\xd5\xd6\xd4\xff\x00\x00\x00\xff\x00\x00", r"C:\x\New Style 512.JPG", 35.0),
        (2, "Old Style", b"\xff\xff\xdc\xcf\xbf\x00\x00\x00\x00\x00", "C:/y/OldIS.jpg", 14.0),
    ]
    for oid, name, col, p, rep in rows:
        c.execute("INSERT INTO LibraryObjects VALUES (?,?,?,0,1,0,1,?)", (oid, name, 8, f"u{oid}"))
        c.execute("INSERT INTO Data4LibraryObjects VALUES (?,?)", (oid, _material_blob(name, col, p, rep)))
        c.execute("INSERT INTO Keywords4LibraryObjects VALUES (?,1)", (oid,))
    xml = ("'<?xml version=\"1.0\"?>\n<TreeView><Directory Name=\"Brand\">"
           "<Directory Name=\"Line A\"><Item Id=\"1\"/></Directory>"
           "<Directory Name=\"Line B\"><Item Id=\"2\"/></Directory></Directory></TreeView>\n'")
    c.execute("INSERT INTO LibraryViews VALUES (1, ?, 'User Catalog')", (xml,))
    c.commit()
    c.close()


def test_inspector_decodes_both_material_revisions_and_tree(tmp_path):
    cat = tmp_path / "Test.calib"
    _catalog(cat)
    before = cat.read_bytes()
    result = _load().inspect(str(cat))
    by_name = {o["name"]: o for o in result["objects"]}
    new, old = by_name["New Style"], by_name["Old Style"]
    assert new["color"] == "#d5d6d4" and old["color"] == "#dccfbf"
    assert new["texture_file"] == "New Style 512.JPG" and old["texture_file"] == "OldIS.jpg"
    assert new["texture_repeat"] == [35.0, 35.0] and old["texture_repeat"] == [14.0, 14.0]
    assert new["folder"] == ["Brand", "Line A"] and old["folder"] == ["Brand", "Line B"]
    assert new["keywords"] == ["countertop"] and new["copyright"] == "Copyright Test Co"
    assert all(o["provenance"] == {"source": "home-designer-calib", "redistributable": False}
               for o in result["objects"])
    assert cat.read_bytes() == before  # read-only


def test_sampler_copies_only_chosen_objects_and_keeps_source(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "calib_sample", SCRIPT.with_name("calib_sample.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src = tmp_path / "Big.calib"
    _catalog(src)
    before = src.read_bytes()
    out = tmp_path / "sample.calib"
    mod.sample(str(src), str(out), [2])
    assert src.read_bytes() == before
    result = _load().inspect(str(out))
    assert [o["name"] for o in result["objects"]] == ["Old Style"]
    assert result["objects"][0]["color"] == "#dccfbf"
    assert result["objects"][0]["folder"] == ["Brand", "Line B"]


def _mesh_module():
    spec = importlib.util.spec_from_file_location("calib_mesh", SCRIPT.with_name("calib_mesh.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mesh_scanner_finds_reported_triangle_layout():
    # Unit cube (inches) as 12 triangles in the reported layout:
    # CD AB <type> ... uint32 N, then N records of 162 bytes, 9 float64 first.
    c = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    tris = [t for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]
    body = b"".join(struct.pack("<9d", *c[i], *c[j], *c[k]) + b"\x00" * 90 for i, j, k in tris)
    blob = (b"\x01\x00\x00\x00\x01" + b"\xcd\xab\x61\x00" + b"junk" * 20
            + b"\xcd\xab\x74\x00\xb2\x0b" + struct.pack("<I", len(tris)) + b"\x00" * 4 + body + b"Hardware")
    mod = _mesh_module()
    meshes = mod.find_meshes(blob)
    assert len(meshes) == 1 and len(meshes[0][2]) == 12
    text, nv, nf = mod.to_obj(meshes[0][2], mod.UNITS["inch"])
    assert (nv, nf) == (8, 12)
    lo, hi = mod.bbox(meshes[0][2], 0.0254)
    assert [round(h - l, 6) for l, h in zip(lo, hi)] == [0.0254] * 3


def test_mesh_scanner_rejects_random_bytes():
    import random
    rnd = random.Random(1)
    blob = b"\xcd\xab" + bytes(rnd.randrange(256) for _ in range(20000))
    assert _mesh_module().find_meshes(blob) == []


def test_calibz_with_embedded_sqlite_is_carved_and_opened(tmp_path):
    cat = tmp_path / "Inner.calib"
    _catalog(cat)
    wrapped = tmp_path / "Bundle.calibz"
    wrapped.write_bytes(b"HDBUNDLE\x01\x02" + b"\x00" * 50 + cat.read_bytes() + b"\xff\xd8JPEGDATA" * 10)
    result = _load().inspect(str(wrapped))
    assert sorted(o["name"] for o in result["objects"]) == ["New Style", "Old Style"]


def test_mesh_scanner_prefers_full_count_over_coincidental_small_count():
    c = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    tris = [t for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]
    body = b"".join(struct.pack("<9d", *c[i], *c[j], *c[k]) + b"\x00" * 90 for i, j, k in tris)
    # Real count 12, then a second header field that also reads as a valid count (4).
    blob = b"\xcd\xab\x74\x00" + struct.pack("<II", 12, 4) + body
    meshes = _mesh_module().find_meshes(blob)
    assert [len(t) for _, _, t in meshes] == [12]


def test_sampler_can_truncate_large_blobs(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "calib_sample", SCRIPT.with_name("calib_sample.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src = tmp_path / "Big.calib"
    _catalog(src)
    out = tmp_path / "small.calib"
    mod.sample(str(src), str(out), [1], max_blob=64)
    conn = sqlite3.connect(out)
    assert conn.execute("SELECT LENGTH(Data) FROM Data4LibraryObjects").fetchall() == [(64,)]
