"""Feasibility query engine with cross-family ranking and optional CRB bounds.

Accepts a task description and environment constraints, loads sensors from
the graph (or offline), evaluates constraints, optionally computes CRB
bounds, and returns ranked SensorConfig entries in a FeasibilityResult.
"""

from __future__ import annotations

import time

import structlog

from agentsim.knowledge_graph.client import GraphClient
from agentsim.knowledge_graph.constraint_checker import (
    check_constraints,
    feasibility_score,
)
from agentsim.knowledge_graph.models import (
    ConfidenceQualifier,
    FeasibilityResult,
    SensorConfig,
    SensorFamily,
    SensorNode,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# CRB integration helper
# ---------------------------------------------------------------------------


def _try_compute_crb(
    sensor: SensorNode,
    task: str,
) -> tuple[float | None, str, ConfidenceQualifier]:
    """Attempt CRB computation for a sensor, returning (bound, unit, confidence).

    If the CRB module is unavailable or computation fails, returns
    (None, "", UNKNOWN) without raising.
    """
    try:
        from agentsim.knowledge_graph.crb.dispatch import compute_crb  # noqa: PLC0415
    except ImportError:
        return None, "", ConfidenceQualifier.UNKNOWN

    try:
        result = compute_crb(sensor, estimation_task=task)
        # CRB dispatch returns inf for unsupported families -- treat as None
        if result.bound_value == float("inf"):
            return None, "", ConfidenceQualifier.UNKNOWN
        return result.bound_value, result.bound_unit, result.confidence
    except Exception:
        logger.debug("crb_computation_failed", sensor=sensor.name, task=task)
        return None, "", ConfidenceQualifier.UNKNOWN


# ---------------------------------------------------------------------------
# Sort key for ranking: primary = score desc, secondary = crb_bound asc (None last)
# ---------------------------------------------------------------------------


def _sort_key(config: SensorConfig) -> tuple[float, float]:
    """Return sort key: (-score, crb_bound_or_inf).

    Higher score sorts first (negated). Lower CRB bound sorts first
    for tied scores. None CRB sorts last (inf).
    """
    crb = config.crb_bound if config.crb_bound is not None else float("inf")
    return (-config.feasibility_score, crb)


# ---------------------------------------------------------------------------
# FeasibilityQueryEngine
# ---------------------------------------------------------------------------


class FeasibilityQueryEngine:
    """Query engine that ranks sensors across families by feasibility.

    Wraps a GraphClient for loading sensors and evaluates constraints
    with optional CRB bounds.
    """

    def __init__(self, client: GraphClient) -> None:
        """Initialize the engine with a GraphClient.

        Args:
            client: An open GraphClient connected to Neo4j (or mock).
        """
        self._client = client

    def query(
        self,
        task: str,
        constraints: dict[str, float | str],
        family_filter: SensorFamily | None = None,
        max_results: int = 10,
    ) -> FeasibilityResult:
        """Run a feasibility query and return ranked results.

        Args:
            task: Task description (e.g., "NLOS reconstruction").
            constraints: Dict of constraint name to value.
            family_filter: Optional filter to a single sensor family.
            max_results: Maximum number of ranked results to return.

        Returns:
            Frozen FeasibilityResult with ranked SensorConfig entries.
        """
        start = time.monotonic()

        # Load sensors from graph
        sensors = self._client.get_sensors(family=family_filter)

        if not sensors:
            elapsed = time.monotonic() - start
            return FeasibilityResult(
                query_text=task,
                environment_constraints=tuple(
                    f"{k}={v}" for k, v in constraints.items()
                ),
                ranked_configs=(),
                pruned_count=0,
                total_count=0,
                computation_time_s=elapsed,
            )

        # Evaluate each sensor
        configs: list[SensorConfig] = []
        for sensor in sensors:
            satisfaction = check_constraints(sensor, constraints)
            score = feasibility_score(satisfaction)

            # Optional CRB integration
            crb_bound, crb_unit, confidence = _try_compute_crb(sensor, task)

            config = SensorConfig(
                sensor_name=sensor.name,
                sensor_family=sensor.family,
                algorithm_name="generic",
                crb_bound=crb_bound,
                crb_unit=crb_unit,
                confidence=confidence,
                feasibility_score=score,
                constraint_satisfaction=satisfaction,
            )
            configs.append(config)

        # Sort: highest score first, lowest CRB bound as tiebreaker
        configs.sort(key=_sort_key)

        # Assign ranks and cap
        ranked: list[SensorConfig] = []
        for i, config in enumerate(configs[:max_results], start=1):
            ranked.append(
                config.model_copy(update={"rank": i})
            )

        # Count feasible (score > 0)
        feasible_count = sum(1 for c in configs if c.feasibility_score > 0.0)
        pruned = len(configs) - feasible_count

        elapsed = time.monotonic() - start

        return FeasibilityResult(
            query_text=task,
            environment_constraints=tuple(
                f"{k}={v}" for k, v in constraints.items()
            ),
            ranked_configs=tuple(ranked),
            pruned_count=pruned,
            total_count=len(sensors),
            computation_time_s=elapsed,
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def query_feasibility(
    task: str,
    constraints: dict[str, float | str],
    client: GraphClient,
    max_results: int = 10,
) -> FeasibilityResult:
    """Convenience wrapper for FeasibilityQueryEngine.query().

    Args:
        task: Task description.
        constraints: Constraint dict.
        client: An open GraphClient.
        max_results: Maximum number of ranked results.

    Returns:
        Frozen FeasibilityResult.
    """
    engine = FeasibilityQueryEngine(client)
    return engine.query(task, constraints, max_results=max_results)
