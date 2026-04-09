"""Constraint checking and conflict detection for feasibility queries.

Pure functions that evaluate sensor parameters against task constraints.
No Neo4j dependency -- operates entirely on frozen Pydantic models.
Uses Pint for all unit conversions (per research Pitfall 6: never hand-roll).
"""

from __future__ import annotations

import pint
import structlog

from agentsim.knowledge_graph.models import (
    ConstraintSatisfaction,
    SensorNode,
)

from pydantic import BaseModel

logger = structlog.get_logger()

# Single Pint registry reused across all constraint evaluations.
_ureg = pint.UnitRegistry()


# ---------------------------------------------------------------------------
# ConstraintConflict model
# ---------------------------------------------------------------------------


class ConstraintConflict(BaseModel, frozen=True):
    """Report when no sensor satisfies all constraints simultaneously."""

    conflicting_constraints: tuple[str, ...]
    reason: str
    closest_sensor: str
    closest_satisfaction: tuple[ConstraintSatisfaction, ...]


# ---------------------------------------------------------------------------
# Individual constraint checkers (pure, no side effects)
# ---------------------------------------------------------------------------


def _check_range(sensor: SensorNode, required_range_m: float) -> ConstraintSatisfaction:
    """Check if the sensor's working distance range covers the required range."""
    wd_min = sensor.geometric.working_distance_min
    wd_max = sensor.geometric.working_distance_max

    if wd_min is None or wd_max is None:
        return ConstraintSatisfaction(
            constraint_name="range_m",
            satisfied=False,
            margin=0.0,
            unit="meter",
            details="working distance not specified",
        )

    satisfied = wd_min <= required_range_m <= wd_max
    margin = min(required_range_m - wd_min, wd_max - required_range_m)

    return ConstraintSatisfaction(
        constraint_name="range_m",
        satisfied=satisfied,
        margin=margin,
        unit="meter",
        details="" if satisfied else (
            f"required {required_range_m}m outside [{wd_min}, {wd_max}]m"
        ),
    )


def _check_ambient_light(
    sensor: SensorNode, ambient: str,
) -> ConstraintSatisfaction:
    """Check if the sensor's dynamic range handles the ambient light level."""
    dr = sensor.radiometric.dynamic_range_db

    if ambient == "dark":
        return ConstraintSatisfaction(
            constraint_name="ambient_light",
            satisfied=True,
            margin=dr if dr is not None else 0.0,
            unit="dB",
            details="dark environment compatible with all sensors",
        )

    threshold = 80.0 if ambient == "outdoor" else 60.0  # indoor

    if dr is None:
        return ConstraintSatisfaction(
            constraint_name="ambient_light",
            satisfied=True,
            margin=0.0,
            unit="dB",
            details="dynamic range not specified, assuming compatible",
        )

    satisfied = dr >= threshold
    margin = dr - threshold

    return ConstraintSatisfaction(
        constraint_name="ambient_light",
        satisfied=satisfied,
        margin=margin,
        unit="dB",
        details="" if satisfied else (
            f"dynamic range {dr}dB below {ambient} threshold {threshold}dB"
        ),
    )


def _check_temporal_resolution(
    sensor: SensorNode, required_s: float,
) -> ConstraintSatisfaction:
    """Check temporal resolution using Pint for unit normalization."""
    tr_value = sensor.temporal.temporal_resolution
    tr_unit = sensor.temporal.temporal_resolution_unit

    if tr_value is None:
        return ConstraintSatisfaction(
            constraint_name="temporal_resolution_s",
            satisfied=False,
            margin=0.0,
            unit="second",
            details="temporal resolution not specified",
        )

    # Convert sensor value to seconds via Pint (never hand-roll conversions)
    sensor_quantity = _ureg.Quantity(tr_value, tr_unit)
    sensor_in_seconds = sensor_quantity.to("second").magnitude

    satisfied = sensor_in_seconds <= required_s
    margin = required_s - sensor_in_seconds

    return ConstraintSatisfaction(
        constraint_name="temporal_resolution_s",
        satisfied=satisfied,
        margin=margin,
        unit="second",
        details="" if satisfied else (
            f"sensor {sensor_in_seconds:.2e}s exceeds required {required_s:.2e}s"
        ),
    )


def _check_budget(sensor: SensorNode, budget: float) -> ConstraintSatisfaction:
    """Check if the sensor cost fits within budget."""
    if sensor.operational is None or sensor.operational.cost_max_usd is None:
        return ConstraintSatisfaction(
            constraint_name="budget_usd",
            satisfied=True,
            margin=0.0,
            unit="USD",
            details="cost not specified, assuming within budget",
        )

    cost = sensor.operational.cost_max_usd
    satisfied = cost <= budget
    margin = budget - cost

    return ConstraintSatisfaction(
        constraint_name="budget_usd",
        satisfied=satisfied,
        margin=margin,
        unit="USD",
        details="" if satisfied else f"cost ${cost} exceeds budget ${budget}",
    )


def _check_weight(sensor: SensorNode, max_weight: float) -> ConstraintSatisfaction:
    """Check if the sensor weight is within limit."""
    if sensor.operational is None or sensor.operational.weight_g is None:
        return ConstraintSatisfaction(
            constraint_name="weight_g",
            satisfied=True,
            margin=0.0,
            unit="gram",
            details="weight not specified",
        )

    weight = sensor.operational.weight_g
    satisfied = weight <= max_weight
    margin = max_weight - weight

    return ConstraintSatisfaction(
        constraint_name="weight_g",
        satisfied=satisfied,
        margin=margin,
        unit="gram",
        details="" if satisfied else f"weight {weight}g exceeds limit {max_weight}g",
    )


def _check_power(sensor: SensorNode, max_power: float) -> ConstraintSatisfaction:
    """Check if the sensor power draw is within limit."""
    if sensor.operational is None or sensor.operational.power_w is None:
        return ConstraintSatisfaction(
            constraint_name="power_w",
            satisfied=True,
            margin=0.0,
            unit="watt",
            details="power not specified",
        )

    power = sensor.operational.power_w
    satisfied = power <= max_power
    margin = max_power - power

    return ConstraintSatisfaction(
        constraint_name="power_w",
        satisfied=satisfied,
        margin=margin,
        unit="watt",
        details="" if satisfied else f"power {power}W exceeds limit {max_power}W",
    )


def _check_spatial_resolution(
    sensor: SensorNode, required: float,
) -> ConstraintSatisfaction:
    """Check if the sensor spatial resolution meets the requirement (higher = better)."""
    sr = sensor.geometric.spatial_resolution

    if sr is None:
        return ConstraintSatisfaction(
            constraint_name="spatial_resolution",
            satisfied=False,
            margin=0.0,
            unit="pixel",
            details="spatial resolution not specified",
        )

    satisfied = sr >= required
    margin = sr - required

    return ConstraintSatisfaction(
        constraint_name="spatial_resolution",
        satisfied=satisfied,
        margin=margin,
        unit="pixel",
        details="" if satisfied else (
            f"spatial resolution {sr} below required {required}"
        ),
    )


# Dispatch table for constraint checkers.
_CONSTRAINT_DISPATCHERS: dict[str, object] = {
    "range_m": _check_range,
    "ambient_light": _check_ambient_light,
    "temporal_resolution_s": _check_temporal_resolution,
    "budget_usd": _check_budget,
    "weight_g": _check_weight,
    "power_w": _check_power,
    "spatial_resolution": _check_spatial_resolution,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_constraints(
    sensor: SensorNode,
    constraints: dict[str, float | str],
) -> tuple[ConstraintSatisfaction, ...]:
    """Evaluate a sensor against a set of constraints.

    Args:
        sensor: The sensor node to check.
        constraints: Dict of constraint name to value. Supported keys:
            range_m, ambient_light, temporal_resolution_s, budget_usd,
            weight_g, power_w, spatial_resolution.

    Returns:
        Tuple of ConstraintSatisfaction, one per recognized constraint.
        Unknown constraint keys are logged and skipped.
    """
    results: list[ConstraintSatisfaction] = []

    for key, value in constraints.items():
        checker = _CONSTRAINT_DISPATCHERS.get(key)
        if checker is None:
            logger.warning("unknown_constraint", constraint=key)
            continue
        results.append(checker(sensor, value))  # type: ignore[operator]

    return tuple(results)


def feasibility_score(
    satisfaction: tuple[ConstraintSatisfaction, ...],
) -> float:
    """Compute a feasibility score from constraint satisfaction results.

    Score is the fraction of satisfied constraints (0.0 to 1.0).
    Per D-16, weights are configurable -- this is the base implementation
    using satisfied fraction as the primary signal.

    Args:
        satisfaction: Tuple of constraint satisfaction results.

    Returns:
        Float in [0.0, 1.0]. Returns 0.0 for empty tuple.
    """
    if not satisfaction:
        return 0.0

    satisfied_count = sum(1.0 for s in satisfaction if s.satisfied)
    return satisfied_count / len(satisfaction)


def detect_conflicts(
    constraints: dict[str, float | str],
    sensors: tuple[SensorNode, ...],
) -> ConstraintConflict | None:
    """Detect when no sensor can satisfy all constraints simultaneously.

    Args:
        constraints: The constraint dict to evaluate.
        sensors: All available sensors to check.

    Returns:
        ConstraintConflict if no sensor satisfies all constraints, None otherwise.
    """
    if not sensors:
        return ConstraintConflict(
            conflicting_constraints=tuple(constraints.keys()),
            reason="No sensors available to evaluate constraints.",
            closest_sensor="",
            closest_satisfaction=(),
        )

    best_score = -1.0
    best_sensor_name = ""
    best_satisfaction: tuple[ConstraintSatisfaction, ...] = ()

    # Track which constraints are unsatisfied by ALL sensors
    constraint_keys = [k for k in constraints if k in _CONSTRAINT_DISPATCHERS]
    unsatisfied_counts: dict[str, int] = {k: 0 for k in constraint_keys}

    for sensor in sensors:
        satisfaction = check_constraints(sensor, constraints)
        score = feasibility_score(satisfaction)

        # If any sensor fully satisfies all constraints, no conflict
        if all(s.satisfied for s in satisfaction) and satisfaction:
            return None

        if score > best_score:
            best_score = score
            best_sensor_name = sensor.name
            best_satisfaction = satisfaction

        # Count unsatisfied per constraint
        satisfied_names = {s.constraint_name for s in satisfaction if s.satisfied}
        for key in constraint_keys:
            if key not in satisfied_names:
                unsatisfied_counts[key] += 1

    # Constraints unsatisfied by ALL sensors
    total_sensors = len(sensors)
    universally_unsatisfied = tuple(
        k for k, count in unsatisfied_counts.items()
        if count == total_sensors
    )

    reason = (
        f"No sensor satisfies all constraints. "
        f"The closest is {best_sensor_name} (score {best_score:.0%}). "
        f"Unsatisfiable: {', '.join(universally_unsatisfied) if universally_unsatisfied else 'none universally'}."
    )

    return ConstraintConflict(
        conflicting_constraints=universally_unsatisfied,
        reason=reason,
        closest_sensor=best_sensor_name,
        closest_satisfaction=best_satisfaction,
    )
