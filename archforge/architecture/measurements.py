"""Deterministic, provenance-carrying measurements for supported semantic entities.

This module reports only quantities that current ArchForge semantics can derive
without pretending preview geometry is fabrication geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import pi
from typing import Iterable, Iterator, Mapping

from archforge.core.model import Document


class MeasurementStatus(str, Enum):
    """Truth status attached to every reported quantity."""

    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Measurement:
    value: float | None
    unit: str
    status: MeasurementStatus
    method: str
    reason: str = ""


@dataclass(frozen=True)
class EntityMeasurements(Mapping[str, Measurement]):
    entity_id: str
    entity_kind: str
    measurements: Mapping[str, Measurement]

    def __getitem__(self, key: str) -> Measurement:
        return self.measurements[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.measurements)

    def __len__(self) -> int:
        return len(self.measurements)


_POD_DEFAULTS = (
    "diameter_x",
    "diameter_y",
    "height",
    "floor_footprint_area",
)
_OPENING_DEFAULTS = ("width", "height", "sill")
_UNSUPPORTED_UNITS = {
    "fabrication_shell_area": "m^2",
    "fabrication_shell_volume": "m^3",
}


def _exact(value: object, unit: str, method: str = "semantic_parameter") -> Measurement:
    return Measurement(float(value), unit, MeasurementStatus.EXACT, method)


def _unsupported(quantity: str) -> Measurement:
    unit = _UNSUPPORTED_UNITS.get(quantity, "")
    return Measurement(
        None,
        unit,
        MeasurementStatus.UNSUPPORTED,
        "unsupported",
        "No faithful fabrication measurement is defined by the current semantic model."
        if quantity.startswith("fabrication_")
        else "This quantity is not supported for the current entity semantics.",
    )


def _measure_pod(params: Mapping[str, object], quantity: str) -> Measurement:
    if quantity in {"diameter_x", "diameter_y", "height"}:
        if quantity not in params:
            return _unsupported(quantity)
        return _exact(params[quantity], "m")
    if quantity == "floor_footprint_area":
        if "diameter_x" not in params or "diameter_y" not in params:
            return _unsupported(quantity)
        dx = float(params["diameter_x"])
        dy = float(params["diameter_y"])
        return Measurement(
            pi * (dx / 2.0) * (dy / 2.0),
            "m^2",
            MeasurementStatus.EXACT,
            "analytic_ellipse_from_semantic_parameters",
        )
    return _unsupported(quantity)


def _measure_opening(params: Mapping[str, object], quantity: str) -> Measurement:
    if quantity in {"width", "height", "sill"} and quantity in params:
        return _exact(params[quantity], "m")
    return _unsupported(quantity)


def measure_entity(
    document: Document,
    entity_id: str,
    *,
    quantities: Iterable[str] | None = None,
) -> EntityMeasurements:
    """Measure one entity from repository state with explicit provenance.

    Values marked EXACT are exact with respect to the semantic model contract,
    not a claim of fabrication or engineering verification.
    """

    entity = document.get(entity_id)
    if entity is None:
        raise KeyError(entity_id)

    if quantities is None:
        if entity.kind == "pod":
            requested = _POD_DEFAULTS
        elif entity.kind in {"door", "window", "opening"}:
            requested = _OPENING_DEFAULTS
        else:
            requested = ()
    else:
        requested = tuple(quantities)

    if entity.kind == "pod":
        values = {name: _measure_pod(entity.params, name) for name in requested}
    elif entity.kind in {"door", "window", "opening"}:
        values = {name: _measure_opening(entity.params, name) for name in requested}
    else:
        values = {name: _unsupported(name) for name in requested}

    return EntityMeasurements(entity.id, entity.kind, values)
