from archforge.core.model import Document, Entity
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.organic.biospectre import junction_plane
from archforge.organic.junctions import infer_organic_junctions


def _pod(cx, floor, height=4.0):
    return Entity('pod', {
        'cx': float(cx), 'cy': 0.0,
        'floor_level': float(floor),
        'diameter_x': 8.0, 'diameter_y': 6.0,
        'height': float(height), 'shell_thickness': 0.18,
        'rotation': 0.0,
    })


def _key(v):
    return tuple(round(float(x), 8) for x in v)


def test_junction_clipping_is_limited_to_vertical_overlap_band():
    doc = Document()
    lower = _pod(0.0, 0.0, 4.0)
    upper = _pod(4.0, 2.0, 4.0)
    doc.add(lower); doc.add(upper)

    full = TessellatedPreviewBackend().evaluate(doc)
    full_lower = full.body(lower.id).payload
    full_upper = full.body(upper.id).payload

    result = infer_organic_junctions(doc)
    assert result.active_ids
    plane = junction_plane(lower.params, upper.params)
    assert plane is not None
    assert plane['z0'] == 2.0 and plane['z1'] == 4.0

    clipped = TessellatedPreviewBackend().evaluate(doc)
    clipped_lower = clipped.body(lower.id).payload
    clipped_upper = clipped.body(upper.id).payload

    # Geometry outside the actual shared vertical band must remain untouched.
    lower_original = {_key(v) for v in full_lower.vertices if v[2] < plane['z0'] - 1e-8}
    lower_after = {_key(v) for v in clipped_lower.vertices if v[2] < plane['z0'] - 1e-8}
    assert lower_original <= lower_after

    upper_original = {_key(v) for v in full_upper.vertices if v[2] > plane['z1'] + 1e-8}
    upper_after = {_key(v) for v in clipped_upper.vertices if v[2] > plane['z1'] + 1e-8}
    assert upper_original <= upper_after
