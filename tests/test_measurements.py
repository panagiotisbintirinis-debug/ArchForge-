import pytest

from archforge.core.model import Document, Entity
from archforge.architecture.measurements import measure_entity, MeasurementStatus


def _pod():
    return Entity(kind='pod', params={
        'cx': 2.0, 'cy': -1.0, 'floor_level': 0.5,
        'diameter_x': 6.0, 'diameter_y': 4.0, 'height': 3.5,
        'shell_thickness': 0.02, 'rotation': 37.0,
    })


def test_pod_measurements_are_model_derived_with_explicit_units_and_provenance():
    doc = Document(); pod = _pod(); doc.add(pod)
    result = measure_entity(doc, pod.id)

    assert result.entity_id == pod.id
    assert result.entity_kind == 'pod'
    assert result['diameter_x'].value == pytest.approx(6.0)
    assert result['diameter_x'].unit == 'm'
    assert result['diameter_x'].status is MeasurementStatus.EXACT
    assert result['diameter_x'].method == 'semantic_parameter'
    assert result['height'].value == pytest.approx(3.5)
    assert result['floor_footprint_area'].value == pytest.approx(3.141592653589793 * 3.0 * 2.0)
    assert result['floor_footprint_area'].unit == 'm^2'
    assert result['floor_footprint_area'].method == 'analytic_ellipse_from_semantic_parameters'


def test_opening_measurements_report_semantic_dimensions_not_fabrication_geometry():
    doc = Document(); pod = _pod(); doc.add(pod)
    opening = Entity(kind='window', parent_id=pod.id, params={
        'surface_u': 0.25, 'width': 1.2, 'height': 0.8, 'sill': 1.0,
    }); doc.add(opening)
    result = measure_entity(doc, opening.id)

    assert result['width'].value == pytest.approx(1.2)
    assert result['height'].value == pytest.approx(0.8)
    assert result['sill'].value == pytest.approx(1.0)
    assert all(m.status is MeasurementStatus.EXACT for m in result.values())
    assert all(m.method == 'semantic_parameter' for m in result.values())


def test_unsupported_quantity_is_explicit_and_never_invents_a_number():
    doc = Document(); pod = _pod(); doc.add(pod)
    result = measure_entity(doc, pod.id, quantities=('fabrication_shell_area',))
    measurement = result['fabrication_shell_area']
    assert measurement.status is MeasurementStatus.UNSUPPORTED
    assert measurement.value is None
    assert measurement.unit == 'm^2'
    assert 'fabrication' in measurement.reason.lower()


def test_unknown_entity_id_is_rejected():
    with pytest.raises(KeyError):
        measure_entity(Document(), 'missing')

def test_joined_pod_net_floor_footprint_area_computes_clipped_polygon_area():
    from archforge.organic.biospectre import junction_key_for_pods
    doc = Document()
    a = Entity(
        kind="pod",
        params={
            "cx": 0.0,
            "cy": 0.0,
            "floor_level": 0.0,
            "diameter_x": 6.0,
            "diameter_y": 6.0,
            "height": 3.5,
            "rotation": 0.0,
        },
        id="pod_a",
    )
    b = Entity(
        kind="pod",
        params={
            "cx": 4.0,
            "cy": 0.0,
            "floor_level": 0.0,
            "diameter_x": 6.0,
            "diameter_y": 6.0,
            "height": 3.5,
            "rotation": 0.0,
        },
        id="pod_b",
    )
    doc.add(a)
    doc.add(b)

    # Before junction: net area matches gross area exactly
    res_before = measure_entity(doc, a.id)
    assert res_before["gross_floor_footprint_area"].value == pytest.approx(3.141592653589793 * 9.0)
    assert res_before["net_floor_footprint_area"].value == pytest.approx(3.141592653589793 * 9.0)
    assert res_before["net_floor_footprint_area"].method == "analytic_ellipse_unclipped"

    # Add active junction
    j = Entity(
        "organic_junction",
        {
            "component_a": a.id,
            "component_b": b.id,
            "junction_key": junction_key_for_pods(a.id, b.id),
            "status": "active",
        },
        id="j_a_b",
    )
    doc.add(j)

    res_after = measure_entity(doc, a.id)
    gross = res_after["gross_floor_footprint_area"].value
    net = res_after["net_floor_footprint_area"].value
    assert gross == pytest.approx(3.141592653589793 * 9.0)
    # Clipped area must be strictly less than gross area due to junction cut
    assert 0 < net < gross
    assert res_after["net_floor_footprint_area"].status is MeasurementStatus.EXACT
    assert res_after["net_floor_footprint_area"].unit == "m^2"
    assert res_after["net_floor_footprint_area"].method == "planar_polygon_surveyor_formula_from_junction_clipped_plan"
