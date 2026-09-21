from archforge.core.model import Document, Entity
from archforge.core.view_frame import build_view_frame
from archforge.organic.biospectre import junction_key_for_pods


def _pod(pod_id, cx, cy, diameter_x, diameter_y, rotation):
    return Entity(
        "pod",
        {
            "cx": cx,
            "cy": cy,
            "floor_level": 0.0,
            "diameter_x": diameter_x,
            "diameter_y": diameter_y,
            "height": 4.0,
            "shell_thickness": 0.2,
            "rotation": rotation,
        },
        id=pod_id,
    )


def test_rotated_elliptical_pod_junction_projection_is_exactly_supported():
    """A rotated ellipse uses its exact world-axis support radius before junction clipping."""
    doc = Document()
    a = _pod("pod-a", 0.0, 0.0, 8.0, 6.0, 45.0)
    b = _pod("pod-b", 6.0, 0.0, 8.0, 8.0, 0.0)
    doc.add(a)
    doc.add(b)
    doc.add(
        Entity(
            "organic_junction",
            {
                "component_a": a.id,
                "component_b": b.id,
                "junction_key": junction_key_for_pods(a.id, b.id),
                "status": "active",
            },
            id="junction-a-b",
        )
    )

    frame = build_view_frame(doc, "XZ")
    projected = next(p for p in frame.primitives if p.entity_id == "pod-a")

    assert projected.role == "pod-junction-clipped"
    assert dict(projected.meta).get("junction_projection") == "supported-rotated-ellipse"
    # Rotation changes the X support radius from 4.0 to sqrt((4 cos45)^2 + (3 sin45)^2).
    expected_radius = (12.5) ** 0.5
    xs = [point[0] for point in projected.points]
    assert abs(min(xs) + expected_radius) < 1e-9


def test_quarter_turn_elliptical_pod_remains_explicitly_unsupported():
    """A 90-degree ellipse is axis-aligned and outside the oblique-rotation contract."""
    doc = Document()
    a = _pod("pod-a", 0.0, 0.0, 8.0, 6.0, 90.0)
    b = _pod("pod-b", 6.0, 0.0, 8.0, 8.0, 0.0)
    doc.add(a)
    doc.add(b)
    doc.add(
        Entity(
            "organic_junction",
            {
                "component_a": a.id,
                "component_b": b.id,
                "junction_key": junction_key_for_pods(a.id, b.id),
                "status": "active",
            },
            id="junction-a-b",
        )
    )

    frame = build_view_frame(doc, "XZ")
    projected = next(p for p in frame.primitives if p.entity_id == "pod-a")

    assert projected.role == "pod-junction-unclipped-unsupported"
    assert dict(projected.meta).get("junction_projection") == "unsupported"
