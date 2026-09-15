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
