"""Minimal glTF 2.0 reader (.gltf + .bin, or .glb) for library import.

Reads triangle geometry and base colours only; textures, skins, morphs and
compressed geometry (Draco/meshopt) are not supported and are reported as
errors rather than guessed.  glTF is metres with +Y up; ArchForge is +Z up,
so points are mapped (x, y, z) -> (x, -z, y).
"""
import base64
import json
import math
import pathlib
import struct

_COMPONENT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_UNSUPPORTED = {"KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_mesh_quantization"}


def _load(path):
    path = pathlib.Path(path)
    data = path.read_bytes()
    if data[:4] == b"glTF":
        length = struct.unpack_from("<I", data, 8)[0]
        p, doc, binary = 12, None, None
        while p < length:
            clen, ctype = struct.unpack_from("<II", data, p)
            chunk = data[p + 8:p + 8 + clen]
            if ctype == 0x4E4F534A:
                doc = json.loads(chunk)
            elif ctype == 0x004E4942:
                binary = chunk
            p += 8 + clen
        buffers = [binary]
    else:
        doc = json.loads(data)
        buffers = []
        for b in doc.get("buffers", []):
            uri = b.get("uri", "")
            if uri.startswith("data:"):
                buffers.append(base64.b64decode(uri.split(",", 1)[1]))
            else:
                buffers.append((path.parent / uri).read_bytes())
    used = set(doc.get("extensionsRequired", [])) & _UNSUPPORTED
    if used:
        raise ValueError(f"unsupported compressed glTF ({', '.join(sorted(used))}); use the plain glTF variant")
    return doc, buffers


def _accessor(doc, buffers, index):
    acc = doc["accessors"][index]
    fmt, size = _COMPONENT[acc["componentType"]]
    n = _COUNT[acc["type"]]
    view = doc["bufferViews"][acc["bufferView"]]
    buf = buffers[view.get("buffer", 0)]
    base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride") or size * n
    out = []
    for i in range(acc["count"]):
        vals = struct.unpack_from(f"<{n}{fmt}", buf, base + i * stride)
        out.append(vals if n > 1 else vals[0])
    return out


def _matrix(node):
    if "matrix" in node:
        m = node["matrix"]  # column-major
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = node.get("translation", (0, 0, 0))
    qx, qy, qz, qw = node.get("rotation", (0, 0, 0, 1))
    sx, sy, sz = node.get("scale", (1, 1, 1))
    r = [[1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
         [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
         [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)]]
    return [[r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx],
            [r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty],
            [r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz],
            [0, 0, 0, 1]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _apply(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] + m[i][3] for i in range(3))


def _texture_average(doc, buffers, base, texinfo):
    """Mean linear colour of a base-colour texture, or None when unavailable."""
    try:
        from PySide6.QtGui import QImage
    except ImportError:
        return None
    try:
        image = doc["images"][doc["textures"][texinfo["index"]]["source"]]
        if "bufferView" in image:
            view = doc["bufferViews"][image["bufferView"]]
            off = view.get("byteOffset", 0)
            data = buffers[view.get("buffer", 0)][off:off + view["byteLength"]]
            img = QImage.fromData(data)
        elif image.get("uri", "").startswith("data:"):
            img = QImage.fromData(base64.b64decode(image["uri"].split(",", 1)[1]))
        else:
            img = QImage(str(base / image["uri"]))
    except (KeyError, IndexError, OSError, TypeError):
        return None
    if img.isNull():
        return None
    img = img.scaled(32, 32)
    acc = [0.0, 0.0, 0.0]
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            for i, v in enumerate((c.redF(), c.greenF(), c.blueF())):
                acc[i] += v ** 2.2          # sRGB -> linear
    n = img.width() * img.height()
    return [a / n for a in acc]


def _color(doc, primitive, buffers=None, base=None):
    mat = doc.get("materials", [])[primitive["material"]] if "material" in primitive else {}
    pbr = mat.get("pbrMetallicRoughness", {})
    r, g, b, _a = pbr.get("baseColorFactor", (0.8, 0.8, 0.8, 1.0))
    if "baseColorTexture" in pbr and buffers is not None:
        tex = _texture_average(doc, buffers, base, pbr["baseColorTexture"])
        if tex:
            r, g, b = r * tex[0], g * tex[1], b * tex[2]
    return "#%02x%02x%02x" % tuple(int(round(max(0.0, min(1.0, c)) ** (1 / 2.2) * 255)) for c in (r, g, b))


def read_gltf(path):
    """Return ``[(triangles_zup_m, base_colour_hex, material_name)]`` per primitive."""
    doc, buffers = _load(path)
    scene = doc.get("scenes", [{}])[doc.get("scene", 0)] if doc.get("scenes") else {"nodes": list(range(len(doc.get("nodes", []))))}
    identity = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
    parts = []

    def visit(index, parent):
        node = doc["nodes"][index]
        m = _mul(parent, _matrix(node))
        if "mesh" in node:
            for prim in doc["meshes"][node["mesh"]]["primitives"]:
                if prim.get("mode", 4) != 4 or "POSITION" not in prim["attributes"]:
                    continue
                pos = [_apply(m, v) for v in _accessor(doc, buffers, prim["attributes"]["POSITION"])]
                idx = _accessor(doc, buffers, prim["indices"]) if "indices" in prim else list(range(len(pos)))
                flip = _det3(m) < 0
                tris = []
                for i in range(0, len(idx) - 2, 3):
                    a, b, c = (pos[idx[i]], pos[idx[i + 1]], pos[idx[i + 2]])
                    if flip:
                        b, c = c, b
                    tris.append(tuple((x, -z, y) for x, y, z in (a, b, c)))
                mat = doc.get("materials", [])[prim["material"]].get("name", "") if "material" in prim else ""
                parts.append((tris, _color(doc, prim, buffers, pathlib.Path(path).parent), mat))
        for child in node.get("children", []):
            visit(child, m)

    for root in scene.get("nodes", []):
        visit(root, identity)
    if not parts:
        raise ValueError("no triangle geometry in glTF")
    return parts


def _det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def finite(parts):
    return all(math.isfinite(c) for tris, _c, _m in parts for t in tris for v in t for c in v)


def drop_ground_planes(parts):
    """Remove flat display bases (a floor slab under the actual object).

    A part is a ground plane when it is nearly flat (under 2 cm and under 5 %
    of the total height), sits at the bottom, and its footprint is more than
    2.5 times the footprint of everything else together.  Returns (parts,
    dropped_names) so callers can report what was removed.
    """
    def box(tris):
        pts = [v for t in tris for v in t]
        return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]
    boxes = [box(t) for t, _c, _m in parts]
    zmin = min(b[0][2] for b in boxes)
    zmax = max(b[1][2] for b in boxes)
    keep, dropped = [], []
    for k, ((lo, hi), part) in enumerate(zip(boxes, parts)):
        others = [b for j, b in enumerate(boxes) if j != k]
        if not others:
            keep.append(part)
            continue
        ox = max(b[1][0] for b in others) - min(b[0][0] for b in others)
        oy = max(b[1][1] for b in others) - min(b[0][1] for b in others)
        flat = hi[2] - lo[2] < min(0.02, 0.05 * (zmax - zmin))
        at_bottom = lo[2] - zmin < 0.01
        if flat and at_bottom and (hi[0] - lo[0]) * (hi[1] - lo[1]) > 2.5 * max(ox * oy, 1e-9):
            dropped.append(part[2] or f"part {k}")
        else:
            keep.append(part)
    return keep, dropped
