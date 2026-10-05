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
