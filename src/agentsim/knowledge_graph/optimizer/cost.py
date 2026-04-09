"""Operational cost computation with configurable weights (D-04, D-09, D-10).

Computes a normalized weighted sum of USD cost, power consumption, and
physical weight for a sensor configuration. Each dimension is normalized
to [0, 1] using per-family min/max ranges before weighting.
"""

from __future__ import annotations

from agentsim.knowledge_graph.models import SensorNode
from agentsim.knowledge_graph.optimizer.models import CostWeights


def _normalize(value: float, range_min: float, range_max: float) -> float:
    """Normalize a value to [0, 1] using min-max scaling.

    Returns 0.5 when range span is zero (avoids division by zero).
    Clamps result to [0, 1].
    """
    span = range_max - range_min
    if span <= 0.0:
        return 0.5
    normalized = (value - range_min) / span
    return max(0.0, min(1.0, normalized))


def compute_operational_cost(
    sensor: SensorNode,
    weights: CostWeights,
    family_cost_range: tuple[float, float] = (0.0, 1.0),
    family_power_range: tuple[float, float] = (0.0, 1.0),
    family_weight_range: tuple[float, float] = (0.0, 1.0),
) -> float:
    """Compute weighted normalized operational cost for a sensor configuration.

    If sensor.operational is None, returns 0.0 (no cost data available).

    Each dimension (USD cost, power in watts, weight in grams) is normalized
    to [0, 1] using the provided family-level min/max ranges, then combined
    with the given weights.

    Args:
        sensor: Sensor node with optional operational properties.
        weights: CostWeights with usd, power, weight multipliers.
        family_cost_range: (min, max) USD cost range for normalization.
        family_power_range: (min, max) power range in watts.
        family_weight_range: (min, max) weight range in grams.

    Returns:
        Weighted normalized cost in [0, 1].
    """
    if sensor.operational is None:
        return 0.0

    ops = sensor.operational

    norm_cost = _normalize(
        ops.cost_max_usd if ops.cost_max_usd is not None else 0.0,
        family_cost_range[0],
        family_cost_range[1],
    )
    norm_power = _normalize(
        ops.power_w if ops.power_w is not None else 0.0,
        family_power_range[0],
        family_power_range[1],
    )
    norm_weight = _normalize(
        ops.weight_g if ops.weight_g is not None else 0.0,
        family_weight_range[0],
        family_weight_range[1],
    )

    return weights.usd * norm_cost + weights.power * norm_power + weights.weight * norm_weight
