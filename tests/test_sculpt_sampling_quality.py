from archforge.core.model import Document, Entity
from archforge.geometry.selection import SurfaceHit, BrushSpec, sculpt_modifier_from_hit
from archforge.geometry.sculpt import SculptedPreviewBackend


def test_default_point_brush_has_dense_support_without_densifying_plain_walls():
    doc = Document()
    wall = Entity('wall', {
        'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0,
        'z': 0, 'height': 3, 'thickness': .2,
    })
    doc.add(wall)

    plain = SculptedPreviewBackend().evaluate(doc).body(wall.id).payload

    hit = SurfaceHit(wall.id, 'exterior', (2, .1, 1.5), (0, 1, 0))
    modifier = sculpt_modifier_from_hit(
        doc, hit, BrushSpec(.35, 1.0, 'smooth'), 'pull', .2,
    )
    doc.add_surface_modifier(modifier)
    sculpted = SculptedPreviewBackend().evaluate(doc).body(wall.id).payload

    # Ordinary walls retain the normal viewport mesh. Only a wall that actually
    # needs sculpt detail is densified.
    assert len(sculpted.vertices) > len(plain.vertices)

    exterior_vertices = {
        vertex_index
        for triangle_index, triangle in enumerate(sculpted.triangles)
        if sculpted.triangle_surfaces[triangle_index] == 'exterior'
        for vertex_index in triangle
    }
    local_x = sorted({
        round(sculpted.vertices[index][0], 6)
        for index in exterior_vertices
        if abs(sculpted.vertices[index][0] - 2.0) < .35
    })

    # The default 0.35 m brush needs enough samples across its diameter for the
    # smooth falloff to render as a rounded local deformation rather than a
    # handful of coarse facets.
    assert len(local_x) >= 8
