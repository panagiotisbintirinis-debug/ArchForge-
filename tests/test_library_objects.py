"""Library objects: imported meshes placed and sized through the Document."""
import os
import sqlite3
import struct

import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import entity_primitive
from archforge.library import assets, hd_calib
from archforge.library.objects import library_object_mesh, resized


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHFORGE_DATA", str(tmp_path / "data"))
    assets._CACHE.clear()


def _sofa_triangles():
    # 80 x 32 x 34 inch box, off-centre like a catalog part.
    c = [(10 + x * 80, -5 + y * 32, 3 + z * 34) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    inch = 0.0254
    return [tuple(tuple(q * inch for q in c[i]) for i in t)
            for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]


def _placed(asset_id, size, **kw):
    p = {"x": 2.0, "y": 1.0, "z": 0.0, "rotation": 0.0, "width": size[0], "depth": size[1],
         "height": size[2], "uniform": 1.0, "asset": asset_id}
    p.update(kw)
    return Entity("library_object", p, name="Sofa")


def _extent(verts):
    return [max(v[i] for v in verts) - min(v[i] for v in verts) for i in range(3)]


def test_asset_is_normalised_to_true_size_with_base_on_floor():
    asset_id, size = assets.store_asset("Sofa", _sofa_triangles(), {"source": "test"})
    assert size == pytest.approx([2.032, 0.8128, 0.8636])
    record = assets.load_asset(asset_id)
    zs = [v[2] for v in record["vertices"]]
    xs = [v[0] for v in record["vertices"]]
    assert min(zs) == pytest.approx(0.0) and min(xs) == pytest.approx(-max(xs))
    # Same geometry imported twice is the same asset.
    assert assets.store_asset("Sofa again", _sofa_triangles(), {})[0] == asset_id


def test_placed_object_mesh_matches_inspector_size_and_rotation():
    asset_id, size = assets.store_asset("Sofa", _sofa_triangles(), {})
    sofa = _placed(asset_id, size)
    verts, tris, roles = library_object_mesh(sofa.params)
    assert _extent(verts) == pytest.approx(size)
    assert set(roles) == {"body"} and len(tris) == 12
    stretched = dict(sofa.params, width=3.0, uniform=0.0)
    assert _extent(library_object_mesh(stretched)[0]) == pytest.approx([3.0, size[1], size[2]])
    turned = dict(sofa.params, rotation=90.0)
    assert _extent(library_object_mesh(turned)[0]) == pytest.approx([size[1], size[0], size[2]])


def test_uniform_resize_keeps_proportions_and_free_resize_does_not():
    p = {"width": 2.0, "depth": 0.8, "height": 0.9, "uniform": 1.0}
    assert resized(p, "width", 3.0) == pytest.approx({"width": 3.0, "depth": 1.2, "height": 1.35})
    assert resized(dict(p, uniform=0.0), "width", 3.0) == {"width": 3.0}
    with pytest.raises(ValueError):
        resized(p, "height", 0.0)


def test_missing_asset_shows_a_box_of_the_stored_size():
    sofa = _placed("a-not-on-this-machine", (2.0, 0.8, 0.9))
    verts, tris, roles = library_object_mesh(sofa.params)
    assert set(roles) == {"placeholder"}
    assert _extent(verts) == pytest.approx([2.0, 0.8, 0.9])


def test_library_object_lives_in_the_document_undo_redo_and_save_load(tmp_path):
    asset_id, size = assets.store_asset("Sofa", _sofa_triangles(), {})
    doc = Document(); stack = CommandStack(doc)
    sofa = _placed(asset_id, size)
    stack.execute(AddEntity(sofa))
    stack.execute(UpdateEntity(sofa.id, resized(sofa.params, "width", 3.048)))
    assert doc.get(sofa.id).params["depth"] == pytest.approx(0.8128 * 1.5)
    stack.undo()
    assert doc.get(sofa.id).params["width"] == pytest.approx(2.032)
    stack.redo()
    path = tmp_path / "p.archforge"
    doc.save(path)
    again = Document.load(path)
    assert again.get(sofa.id).params == pytest.approx(doc.get(sofa.id).params) or \
        again.get(sofa.id).params == doc.get(sofa.id).params
    prim = entity_primitive(again, sofa.id)
    assert prim.role == "library-object" and len(prim.points) == 4
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(sofa.id, {"height": -1.0}))


def _mesh_record(polys):
    out = b"\xcd\xab\x74\x00\xaf\x08" + b"\xff" * 4 + struct.pack("<I", len(polys))
    for pl in polys:
        n = len(pl)
        out += struct.pack("<HHIH", n, 0x1000, 0, 0)
        out += b"".join(struct.pack("<3d", *v) for v in pl)
        out += struct.pack(f"<{n}i", *([-1] * n)) + struct.pack("<I", 0) + struct.pack("<2d", 20.0, 20.0)
    return out


def test_import_from_catalog_gives_true_size_parts(tmp_path):
    c = [(x * 80, y * 32, z * 34) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    quads = [[c[i] for i in q] for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))]
    rug = [[(x * 36, y * 36, 0.0) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]]
    blob = b"\x01\x00\x00\x00\x01\xcd\xab\x61\x00" + _mesh_record(quads) + _mesh_record(rug)
    path = tmp_path / "Sets.calib"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE LibraryObjects (LibraryObjectId INTEGER PRIMARY KEY, Name TEXT, Type INTEGER);
        CREATE TABLE SymbolData4LibraryObjects (LibraryObjectId INTEGER PRIMARY KEY, SymbolData BLOB);""")
    conn.execute("INSERT INTO LibraryObjects VALUES (7, 'Living Room 03', 19)")
    conn.execute("INSERT INTO SymbolData4LibraryObjects VALUES (7, ?)", (blob,))
    conn.commit(); conn.close()
    cat = hd_calib.open_catalog(str(path))
    assert hd_calib.catalog_objects(cat) == [(7, "Living Room 03", 19, len(blob))]
    parts = hd_calib.object_parts(cat, 7)
    assert len(parts) == 2
    sizes = [assets.store_asset(f"part {i}", tris, {"source": "home-designer-calib"})[1]
             for i, (_, tris) in enumerate(parts)]
    assert sizes[0] == pytest.approx([2.032, 0.8128, 0.8636])
    assert sizes[1][:2] == pytest.approx([0.9144, 0.9144])


def test_library_object_reaches_the_3d_scene_at_its_size():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload

    asset_id, size = assets.store_asset("Sofa", _sofa_triangles(), {})
    doc = Document(); sofa = _placed(asset_id, size); doc.add(sofa)
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)["objects"]
    mine = [o for o in objs if o.get("kind") == "library_object"]
    assert len(mine) == 1 and mine[0]["id"] == sofa.id
    pos = mine[0]["positions"] if "positions" in mine[0] else mine[0]["vertices"]
    pts = [pos[i:i + 3] for i in range(0, len(pos), 3)] if pos and not isinstance(pos[0], (list, tuple)) else pos
    assert _extent(pts) == pytest.approx(size)


def _box_tris(x0, y0, z0, x1, y1, z1):
    c = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return [tuple(c[i] for i in t) for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]


def test_plan_symbol_traces_outline_hole_and_height_steps():
    from archforge.library.plan_symbol import plan_symbol
    # A 2 x 1 m "sofa": seat 0.45 high in front, back 0.9 high behind (step line),
    # plus a separate ring-like frame with a hole to check inner loops.
    tris = _box_tris(0, 0, 0, 2, 0.7, 0.45) + _box_tris(0, 0.7, 0, 2, 1.0, 0.9)
    verts = sorted({v for t in tris for v in t})
    idx = {v: i for i, v in enumerate(verts)}
    sym = plan_symbol(verts, [tuple(idx[v] for v in t) for t in tris])
    (outline,) = sym["outline"]
    xs = [q[0] for q in outline]; ys = [q[1] for q in outline]
    assert min(xs) == pytest.approx(0, abs=0.02) and max(xs) == pytest.approx(2, abs=0.03)
    assert max(ys) == pytest.approx(1, abs=0.03)
    # One inner line where the seat meets the back (y = 0.7).
    assert any(all(abs(q[1] - 0.7) < 0.02 for q in line) and
               max(q[0] for q in line) - min(q[0] for q in line) > 1.8 for line in sym["lines"])
    ring = _box_tris(0, 0, 0, 1, 0.2, 0.1) + _box_tris(0, 0.8, 0, 1, 1, 0.1) + \
        _box_tris(0, 0, 0, 0.2, 1, 0.1) + _box_tris(0.8, 0, 0, 1, 1, 0.1)
    verts = sorted({v for t in ring for v in t}); idx = {v: i for i, v in enumerate(verts)}
    assert len(plan_symbol(verts, [tuple(idx[v] for v in t) for t in ring])["outline"]) == 2


def test_gltf_reader_converts_y_up_metres_and_drops_display_base(tmp_path):
    import base64
    import json
    from archforge.library.gltf import drop_ground_planes, read_gltf
    # Object: 0.5 wide (x), 1.2 tall (+Y in glTF), 0.3 deep; base plate 3 x 3 m at y=0.
    obj = [(-0.25, 0.0, -0.15), (0.25, 0.0, -0.15), (0.25, 1.2, 0.15)]
    plate = [(-1.5, 0.0, -1.5), (1.5, 0.0, -1.5), (1.5, 0.0, 1.5)]
    raw = b"".join(struct.pack("<3f", *v) for v in obj + plate)
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0, 1]}],
           "nodes": [{"mesh": 0, "translation": [0, 0, 0]}, {"mesh": 1}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "material": 0}]},
                      {"primitives": [{"attributes": {"POSITION": 1}}]}],
           "materials": [{"name": "fabric", "pbrMetallicRoughness": {"baseColorFactor": [1, 0, 0, 1]}}],
           "buffers": [{"byteLength": len(raw), "uri": "data:application/octet-stream;base64," + base64.b64encode(raw).decode()}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36}, {"buffer": 0, "byteOffset": 36, "byteLength": 36}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                         {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC3"}]}
    path = tmp_path / "chair.gltf"
    path.write_text(json.dumps(doc))
    parts = read_gltf(path)
    assert len(parts) == 2 and parts[0][1] == "#ff0000" and parts[0][2] == "fabric"
    zs = [v[2] for v in parts[0][0][0]]
    assert max(zs) == pytest.approx(1.2)          # +Y up became +Z up
    kept, dropped = drop_ground_planes(parts)
    assert len(kept) == 1 and dropped == ["part 1"]


def test_colours_and_symbol_reach_3d_and_plan():
    from archforge.core.plan_scene import build_plan_frame
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    tris = _box_tris(0, 0, 0, 1, 0.5, 0.4) + _box_tris(0, 0, 0.4, 1, 0.5, 0.45)
    colors = ["#884422"] * 12 + ["#ddccaa"] * 12
    asset_id, size = assets.store_asset("Table", tris, {"source": "test"}, colors=colors)
    doc = Document(); obj = _placed(asset_id, size, rotation=90.0); doc.add(obj)
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)["objects"]
    assert sorted(o["material"]["color"] for o in objs if o["kind"] == "library_object") == ["#884422", "#ddccaa"]
    frame = build_plan_frame(doc)
    symbol = [p for p in frame.primitives if p.role == "library-symbol"]
    assert symbol and all(p.entity_id == obj.id for p in symbol)
    xs = [q[0] for p in symbol for q in p.points]
    # Rotated 90 degrees: the 1 m width now runs along Y, 0.5 m depth along X.
    assert max(xs) - min(xs) == pytest.approx(0.5, abs=0.02)
