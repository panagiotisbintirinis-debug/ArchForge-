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


def _mesh_record(polys, version=b"\xb2\x0b", uv=True, surface=0):
    """Mesh record in the verified layout (see references/calib-format.md)."""
    out = b"\xcd\xab\x74\x00" + version + b"\xff" * 4 + struct.pack("<I", len(polys))
    for i, pl in enumerate(polys):
        n = len(pl)
        out += struct.pack("<HHIH", n, 0x1000, surface, 0x1108)
        out += b"".join(struct.pack("<3d", *v) for v in pl)
        out += struct.pack(f"<{n}i", *([i + 1] * (n - 1) + [-1]))
        if uv:
            out += struct.pack("<I", n) + b"".join(struct.pack("<2d", 514.6 + j, 14.26) for j in range(n))
        else:
            out += struct.pack("<I", 0)
        out += struct.pack("<2d", 20.0, 20.0)
    return out


_CUBE = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
_QUADS = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def test_mesh_parser_reads_triangles_with_uvs_like_belwith_handles():
    tris = [[_CUBE[i] for i in t] for a, b, c, d in _QUADS for t in ((a, b, c), (a, c, d))]
    blob = b"\x01\x00\x00\x00\x01\xcd\xab\x61\x00" + b"x" * 30 + _mesh_record(tris) + b"\xcd\xab\x30\x00tail"
    mod = _mesh_module()
    (m, polys, complete), = mod.find_meshes(blob)
    assert complete and m == 39 and len(polys) == 12 and polys[0] == tris[0]
    text, nv, nf = mod.to_obj([("cube", mod.triangulate(polys))], mod.UNITS["inch"])
    assert (nv, nf) == (8, 12)


def test_mesh_parser_reads_quads_without_uvs_and_several_records_like_grouped_furniture():
    quads = [[_CUBE[i] for i in q] for q in _QUADS]
    big = [[(x * 80, y * 32, z * 34) for x, y, z in q] for q in quads]
    blob = (_mesh_record(quads, b"\xaf\x08", uv=False, surface=2) + b"\xcd\xab\x1f\x00gap"
            + _mesh_record(big, b"\xaf\x08", uv=False, surface=1))
    mod = _mesh_module()
    meshes = mod.find_meshes(blob)
    assert [(len(p), c) for _, p, c in meshes] == [(6, True), (6, True)]
    assert len(mod.triangulate(meshes[1][1])) == 12
    lo, hi = mod.bbox([v for pl in meshes[1][1] for v in pl], 0.0254)
    assert [round(h - l, 4) for l, h in zip(lo, hi)] == [2.032, 0.8128, 0.8636]


def test_mesh_parser_flags_truncated_record_and_rejects_noise():
    import random
    quads = [[_CUBE[i] for i in q] for q in _QUADS]
    rec = _mesh_record(quads, uv=False)
    mod = _mesh_module()
    (_, polys, complete), = mod.find_meshes(rec[:-60])
    assert not complete and 0 < len(polys) < 6
    rnd = random.Random(1)
    assert mod.find_meshes(b"\xcd\xab\x74\x00" + bytes(rnd.randrange(256) for _ in range(5000))) == []


def test_calibz_with_embedded_sqlite_is_carved_and_opened(tmp_path):
    cat = tmp_path / "Inner.calib"
    _catalog(cat)
    wrapped = tmp_path / "Bundle.calibz"
    wrapped.write_bytes(b"HDBUNDLE\x01\x02" + b"\x00" * 50 + cat.read_bytes() + b"\xff\xd8JPEGDATA" * 10)
    result = _load().inspect(str(wrapped))
    assert sorted(o["name"] for o in result["objects"]) == ["New Style", "Old Style"]


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
