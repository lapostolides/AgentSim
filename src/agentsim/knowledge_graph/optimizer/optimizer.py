"""Bayesian optimization orchestrator for sensor configuration space (D-01, D-02, D-03).

Composes GP surrogate, EI acquisition, Pareto extraction, and operational cost
into a complete multi-objective BO loop. For each sensor family in a
FeasibilityResult, searches the numeric parameter space, evaluates CRB + cost +
constraint margin, and extracts the Pareto front.

CRITICAL (D-05): optimize_sensors returns the FULL unfiltered Pareto front.
Scope filtering is applied per-agent in graph_context.py (Plan 04).
"""

from __future__ import annotations

import math
import time

import numpy as np
import structlog
from scipy.stats.qmc import LatinHypercube

from agentsim.knowledge_graph.constraint_checker import check_constraints
from agentsim.knowledge_graph.crb.dispatch import compute_crb
from agentsim.knowledge_graph.loader import load_family_ranges, load_sensors
from agentsim.knowledge_graph.models import (
    FAMILY_SCHEMAS,
    ConfidenceQualifier,
    FeasibilityResult,
    SensorFamily,
    SensorNode,
)
from agentsim.knowledge_graph.optimizer.acquisition import (
    expected_improvement,
    optimize_acquisition,
    should_stop,
)
from agentsim.knowledge_graph.optimizer.cost import compute_operational_cost
from agentsim.knowledge_graph.optimizer.gaussian_process import MinimalGP
from agentsim.knowledge_graph.optimizer.models import (
    BOMetadata,
    CostWeights,
    FamilyOptimizationResult,
    OptimizationResult,
    ParetoPoint,
)
from agentsim.knowledge_graph.optimizer.pareto import extract_pareto_front
from agentsim.knowledge_graph.ranges import SensorFamilyRanges

logger = structlog.get_logger()

_DEFAULT_INITIAL_SAMPLES_FACTOR: int = 2
"""Initial Latin Hypercube samples = max(10, factor * n_params)."""

_N_SCALARIZATION_WEIGHTS: int = 10
"""Number of scalarization weight vectors for multi-objective BO."""

_LOG_SCALE_RATIO: float = 100.0
"""If max/min > this ratio, use log10 scale for search bounds."""


# ---------------------------------------------------------------------------
# Helper: load sensor by name
# ---------------------------------------------------------------------------


def _load_sensor_by_name(name: str, family: SensorFamily) -> SensorNode:
    """Find a SensorNode by name from the YAML files for a given family.

    Bridges SensorConfig (which has sensor_name) to the full SensorNode
    needed by the optimizer.

    Args:
        name: Sensor name to look up.
        family: SensorFamily to filter YAML loading.

    Returns:
        The matching SensorNode.

    Raises:
        ValueError: If no sensor with that name exists in the family YAML.
    """
    sensors = load_sensors(families=(family,))
    for sensor in sensors:
        if sensor.name == name:
            return sensor
    raise ValueError(
        f"Sensor '{name}' not found in {family.value} family YAML"
    )


# ---------------------------------------------------------------------------
# Helper: numeric parameter extraction
# ---------------------------------------------------------------------------


def _numeric_params(family: SensorFamily) -> list[str]:
    """Return keys from FAMILY_SCHEMAS where the type is numeric (not str).

    Only float and (int, float) types are considered numeric. String-typed
    parameters (mask_pattern_type, pattern_type, etc.) are excluded from
    the BO search space (Research Pitfall 4).

    Args:
        family: Sensor family to inspect.

    Returns:
        List of parameter names with numeric types.
    """
    schema = FAMILY_SCHEMAS.get(family, {})
    result: list[str] = []
    for key, expected_type in schema.items():
        if expected_type is str:
            continue
        if isinstance(expected_type, tuple) and str in expected_type:
            continue
        result.append(key)
    return result


# ---------------------------------------------------------------------------
# Helper: search bounds
# ---------------------------------------------------------------------------


def _build_search_bounds(
    family_ranges: SensorFamilyRanges,
    param_names: list[str],
) -> np.ndarray:
    """Build (D, 2) array of search bounds from family parameter ranges.

    For ranges spanning >100x (max/min > 100), uses log10 scale.
    If min or max is None, falls back to typical * 0.5 and typical * 2.0.

    Args:
        family_ranges: Parameter ranges for the sensor family.
        param_names: Ordered list of parameter names.

    Returns:
        Shape (D, 2) array of [lower, upper] bounds.
    """
    bounds = np.zeros((len(param_names), 2))
    for i, name in enumerate(param_names):
        pr = family_ranges.ranges.get(name)
        if pr is None:
            # No range data -- use a default [0.5, 2.0] relative range
            bounds[i, 0] = 0.5
            bounds[i, 1] = 2.0
            continue

        lo = pr.min
        hi = pr.max

        # Fallback to typical-based range
        if lo is None or hi is None:
            typical = pr.typical if pr.typical is not None else 1.0
            lo = lo if lo is not None else typical * 0.5
            hi = hi if hi is not None else typical * 2.0

        # Log scale for wide ranges
        if lo > 0.0 and hi > 0.0 and hi / lo > _LOG_SCALE_RATIO:
            bounds[i, 0] = math.log10(lo)
            bounds[i, 1] = math.log10(hi)
        else:
            bounds[i, 0] = lo
            bounds[i, 1] = hi

    return bounds


def _is_log_scaled(lo: float, hi: float) -> bool:
    """Check if a bound pair represents log10 scale.

    We detect log scale by checking if the original range would have had
    a ratio > _LOG_SCALE_RATIO. Since we store log10 values, the span
    in log space indicates the original ratio.
    """
    return lo < 0.0 or (hi - lo) > math.log10(_LOG_SCALE_RATIO)


# ---------------------------------------------------------------------------
# Helper: normalization
# ---------------------------------------------------------------------------


def _normalize(values: np.ndarray, bounds: np.ndarray) -> np.ndarray:
    """Map physical/log values to [0, 1] using bounds.

    Args:
        values: Array of parameter values.
        bounds: Shape (D, 2) array of [lower, upper] bounds.

    Returns:
        Normalized array in [0, 1].
    """
    span = bounds[:, 1] - bounds[:, 0]
    span = np.where(span == 0.0, 1.0, span)
    return (values - bounds[:, 0]) / span


def _denormalize(normalized: np.ndarray, bounds: np.ndarray) -> np.ndarray:
    """Map [0, 1] values back to physical/log space.

    Args:
        normalized: Array in [0, 1].
        bounds: Shape (D, 2) array of [lower, upper] bounds.

    Returns:
        Physical/log-space values.
    """
    span = bounds[:, 1] - bounds[:, 0]
    return normalized * span + bounds[:, 0]


# ---------------------------------------------------------------------------
# Helper: build sensor at a point
# ---------------------------------------------------------------------------


def _build_sensor_at_point(
    base_sensor: SensorNode,
    param_names: list[str],
    physical_values: np.ndarray,
) -> SensorNode:
    """Create a new SensorNode with updated numeric family_specs.

    String-typed parameters are preserved from the base sensor.

    Args:
        base_sensor: Template sensor to copy.
        param_names: Names of numeric parameters being varied.
        physical_values: New values for each parameter.

    Returns:
        New SensorNode with updated family_specs.
    """
    new_specs = dict(base_sensor.family_specs)
    for name, val in zip(param_names, physical_values):
        new_specs[name] = float(val)
    return base_sensor.model_copy(update={"family_specs": new_specs})


# ---------------------------------------------------------------------------
# Helper: evaluate a single point
# ---------------------------------------------------------------------------


def _evaluate_point(
    sensor: SensorNode,
    estimation_task: str,
    constraints: dict[str, float | str],
    cost_weights: CostWeights,
    family_cost_range: tuple[float, float],
    family_power_range: tuple[float, float],
    family_weight_range: tuple[float, float],
) -> tuple[float, float, float]:
    """Evaluate CRB, operational cost, and constraint margin for a sensor.

    Returns:
        (crb_bound, operational_cost, neg_constraint_margin).
        If CRB is inf, returns (inf, inf, inf) to exclude the point.
    """
    crb_result = compute_crb(sensor, estimation_task)
    crb_bound = crb_result.bound_value

    if math.isinf(crb_bound):
        return (float("inf"), float("inf"), float("inf"))

    cost = compute_operational_cost(
        sensor,
        cost_weights,
        family_cost_range=family_cost_range,
        family_power_range=family_power_range,
        family_weight_range=family_weight_range,
    )

    if constraints:
        satisfaction = check_constraints(sensor, constraints)
        margins = [s.margin for s in satisfaction]
        constraint_margin = min(margins) if margins else 0.0
    else:
        constraint_margin = 0.0

    # Negate margin for minimization (higher margin = better = lower negated)
    neg_margin = -constraint_margin

    return (crb_bound, cost, neg_margin)


# ---------------------------------------------------------------------------
# Helper: scalarization weights
# ---------------------------------------------------------------------------


def _generate_scalarization_weights(n: int) -> list[tuple[float, float, float]]:
    """Generate n diverse weight vectors for scalarized multi-objective BO.

    Uses a simple spread across the 3-objective simplex.

    Args:
        n: Number of weight vectors.

    Returns:
        List of (w_crb, w_cost, w_margin) tuples summing to 1.0.
    """
    weights: list[tuple[float, float, float]] = []
    # Always include the extremes and balanced
    weights.append((0.7, 0.2, 0.1))
    weights.append((0.2, 0.7, 0.1))
    weights.append((0.2, 0.1, 0.7))
    weights.append((0.34, 0.33, 0.33))

    # Fill remaining with evenly spaced along simplex
    rng = np.random.RandomState(42)
    while len(weights) < n:
        raw = rng.dirichlet([1.0, 1.0, 1.0])
        weights.append((float(raw[0]), float(raw[1]), float(raw[2])))

    return weights[:n]


# ---------------------------------------------------------------------------
# Helper: objective normalization
# ---------------------------------------------------------------------------


def _normalize_objectives(
    objectives: np.ndarray,
) -> np.ndarray:
    """Normalize each objective column to [0, 1] from observed range.

    Args:
        objectives: Shape (N, 3) array.

    Returns:
        Normalized objectives, same shape.
    """
    mins = objectives.min(axis=0)
    maxs = objectives.max(axis=0)
    spans = maxs - mins
    spans = np.where(spans == 0.0, 1.0, spans)
    return (objectives - mins) / spans


# ---------------------------------------------------------------------------
# Helper: family cost/power/weight ranges
# ---------------------------------------------------------------------------


def _extract_family_ranges(
    base_sensor: SensorNode,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Extract cost/power/weight ranges from a sensor's operational data.

    Uses 0.5x to 2x of the base sensor values as family ranges.

    Returns:
        (cost_range, power_range, weight_range) tuples.
    """
    ops = base_sensor.operational
    if ops is None:
        return ((0.0, 1.0), (0.0, 1.0), (0.0, 1.0))

    cost = ops.cost_max_usd if ops.cost_max_usd is not None else 1.0
    power = ops.power_w if ops.power_w is not None else 1.0
    weight = ops.weight_g if ops.weight_g is not None else 1.0

    return (
        (cost * 0.5, cost * 2.0),
        (power * 0.5, power * 2.0),
        (weight * 0.5, weight * 2.0),
    )


# ---------------------------------------------------------------------------
# Core: per-family optimization
# ---------------------------------------------------------------------------


def _optimize_family(
    base_sensor: SensorNode,
    family_ranges: SensorFamilyRanges,
    estimation_task: str,
    constraints: dict[str, float | str],
    cost_weights: CostWeights,
) -> FamilyOptimizationResult:
    """Run multi-objective BO for one sensor family.

    Uses scalarized BO with multiple weight vectors to explore the
    CRB/cost/margin tradeoff surface. Collects all evaluated points,
    filters infeasible ones, and extracts the Pareto front.

    Args:
        base_sensor: Template sensor for the family.
        family_ranges: Parameter ranges from YAML.
        estimation_task: CRB estimation task label.
        constraints: Constraint dict for check_constraints.
        cost_weights: Weights for operational cost computation.

    Returns:
        FamilyOptimizationResult with Pareto front and metadata.
    """
    t_start = time.monotonic()
    family = base_sensor.family
    numeric_params = _numeric_params(family)

    family_cost_range, family_power_range, family_weight_range = (
        _extract_family_ranges(base_sensor)
    )

    # Edge case: no numeric parameters to optimize
    if not numeric_params:
        crb_val, cost_val, neg_margin = _evaluate_point(
            base_sensor, estimation_task, constraints, cost_weights,
            family_cost_range, family_power_range, family_weight_range,
        )
        point = ParetoPoint(
            sensor_name=base_sensor.name,
            family=family,
            parameter_values={},
            crb_bound=crb_val,
            crb_unit="meter",
            operational_cost=cost_val,
            constraint_margin=-neg_margin,
            confidence=ConfidenceQualifier.ANALYTICAL,
        )
        elapsed = time.monotonic() - t_start
        return FamilyOptimizationResult(
            family=family,
            pareto_front=(point,) if not math.isinf(crb_val) else (),
            bo_metadata=BOMetadata(
                evaluations=1,
                converged=True,
                final_acquisition_improvement=0.0,
                computation_time_s=elapsed,
            ),
        )

    # Build search bounds
    bounds = _build_search_bounds(family_ranges, numeric_params)
    n_params = len(numeric_params)
    n_initial = max(10, _DEFAULT_INITIAL_SAMPLES_FACTOR * n_params)

    # Generate initial samples via Latin Hypercube
    lhs = LatinHypercube(d=n_params, seed=42)
    lhs_samples = lhs.random(n=n_initial)  # shape (n_initial, n_params) in [0,1]

    # Storage for all evaluated points
    all_X_norm: list[np.ndarray] = []
    all_objectives: list[np.ndarray] = []
    all_params: list[dict[str, float]] = []
    all_crb_units: list[str] = []
    all_confidences: list[ConfidenceQualifier] = []

    total_evals = 0

    def _eval_normalized(x_norm: np.ndarray) -> np.ndarray | None:
        """Evaluate a normalized point. Returns (3,) objectives or None if inf."""
        nonlocal total_evals
        physical = _denormalize(x_norm, bounds)

        # Convert log-scaled params back to physical space
        physical_actual = np.copy(physical)
        for i, name in enumerate(numeric_params):
            pr = family_ranges.ranges.get(name)
            if pr is not None and pr.min is not None and pr.max is not None:
                if pr.min > 0.0 and pr.max > 0.0 and pr.max / pr.min > _LOG_SCALE_RATIO:
                    physical_actual[i] = 10.0 ** physical[i]

        sensor = _build_sensor_at_point(base_sensor, numeric_params, physical_actual)
        crb_result = compute_crb(sensor, estimation_task)
        crb_val = crb_result.bound_value

        total_evals += 1

        if math.isinf(crb_val):
            return None

        cost = compute_operational_cost(
            sensor, cost_weights,
            family_cost_range=family_cost_range,
            family_power_range=family_power_range,
            family_weight_range=family_weight_range,
        )

        if constraints:
            satisfaction = check_constraints(sensor, constraints)
            margins = [s.margin for s in satisfaction]
            margin = min(margins) if margins else 0.0
        else:
            margin = 0.0

        obj = np.array([crb_val, cost, -margin])
        all_X_norm.append(x_norm.copy())
        all_objectives.append(obj)
        all_params.append(
            {name: float(physical_actual[j]) for j, name in enumerate(numeric_params)}
        )
        all_crb_units.append(crb_result.bound_unit)
        all_confidences.append(
            ConfidenceQualifier(crb_result.confidence)
            if isinstance(crb_result.confidence, str)
            else crb_result.confidence
            if isinstance(crb_result.confidence, ConfidenceQualifier)
            else ConfidenceQualifier.UNKNOWN
        )

        return obj

    # Evaluate initial samples
    for i in range(n_initial):
        _eval_normalized(lhs_samples[i])

    # Scalarized multi-objective BO
    weight_vectors = _generate_scalarization_weights(_N_SCALARIZATION_WEIGHTS)
    final_acq_improvement = 0.0

    if all_objectives:
        obj_array = np.array(all_objectives)
        norm_obj = _normalize_objectives(obj_array)

        for weights_tuple in weight_vectors:
            w = np.array(weights_tuple)

            # Scalarize: weighted sum of normalized objectives
            X_train = np.array(all_X_norm)
            scalarized = norm_obj @ w

            gp = MinimalGP(length_scale=1.0, noise=1e-4)
            gp = gp.fit(X_train, scalarized)

            best_scalar = float(np.min(scalarized))
            acq_history: list[float] = []

            # BO inner loop for this weight vector
            norm_bounds = np.column_stack(
                [np.zeros(n_params), np.ones(n_params)]
            )

            for _step in range(20):  # max 20 steps per weight vector
                x_next = optimize_acquisition(gp, best_scalar, norm_bounds)
                result = _eval_normalized(x_next)

                if result is not None:
                    # Update training data
                    X_train = np.array(all_X_norm)
                    obj_array = np.array(all_objectives)
                    norm_obj = _normalize_objectives(obj_array)
                    scalarized = norm_obj @ w
                    best_scalar = float(np.min(scalarized))

                    gp = gp.fit(X_train, scalarized)

                # Track acquisition for convergence
                mean_pred, var_pred = gp.predict(x_next.reshape(1, -1))
                ei_val = expected_improvement(mean_pred, var_pred, best_scalar)
                acq_history.append(float(ei_val[0]))

                if should_stop(acq_history, total_evals):
                    break

            if acq_history:
                final_acq_improvement = max(
                    final_acq_improvement, acq_history[-1]
                )

    # Extract Pareto front from all evaluated points
    if not all_objectives:
        elapsed = time.monotonic() - t_start
        return FamilyOptimizationResult(
            family=family,
            pareto_front=(),
            bo_metadata=BOMetadata(
                evaluations=total_evals,
                converged=True,
                final_acquisition_improvement=0.0,
                computation_time_s=elapsed,
            ),
        )

    obj_array = np.array(all_objectives)
    pareto_indices = extract_pareto_front(obj_array)

    pareto_points: list[ParetoPoint] = []
    for idx in pareto_indices:
        obj = all_objectives[idx]
        pareto_points.append(
            ParetoPoint(
                sensor_name=base_sensor.name,
                family=family,
                parameter_values=all_params[idx],
                crb_bound=float(obj[0]),
                crb_unit=all_crb_units[idx],
                operational_cost=float(obj[1]),
                constraint_margin=float(-obj[2]),  # un-negate
                confidence=all_confidences[idx],
            )
        )

    elapsed = time.monotonic() - t_start
    converged = (
        final_acq_improvement < 0.01
        or len(all_objectives) <= n_initial
    )

    logger.info(
        "family_optimization_complete",
        family=family.value,
        evaluations=total_evals,
        pareto_size=len(pareto_points),
        converged=converged,
        time_s=round(elapsed, 2),
    )

    return FamilyOptimizationResult(
        family=family,
        pareto_front=tuple(pareto_points),
        bo_metadata=BOMetadata(
            evaluations=total_evals,
            converged=converged,
            final_acquisition_improvement=final_acq_improvement,
            computation_time_s=elapsed,
        ),
    )


# ---------------------------------------------------------------------------
# Public API: optimize_sensors
# ---------------------------------------------------------------------------


def optimize_sensors(
    feasibility_result: FeasibilityResult,
    scope: str = "medium",
    task: str = "",
    constraints: dict[str, float | str] | None = None,
    cost_weights: CostWeights | None = None,
) -> OptimizationResult:
    """Optimize sensor configurations across all families in a FeasibilityResult.

    For each family present in ranked_configs, loads the top-ranked sensor,
    runs per-family BO, and collects results. Returns the FULL unfiltered
    Pareto front per D-05 (no scope filtering here).

    Args:
        feasibility_result: Result from feasibility query with ranked configs.
        scope: Scope metadata string (NOT used for filtering -- stored only).
        task: Estimation task label for CRB computation.
        constraints: Optional constraint dict.
        cost_weights: Optional cost weights (defaults to CostWeights()).

    Returns:
        OptimizationResult with full Pareto fronts per family.
    """
    if cost_weights is None:
        cost_weights = CostWeights()

    if not feasibility_result.ranked_configs:
        return OptimizationResult(
            family_results=(),
            scope=scope,
            cost_weights=cost_weights,
            total_evaluations=0,
            total_computation_time_s=0.0,
        )

    # Load family ranges
    all_ranges = load_family_ranges()

    # Group configs by family, pick top-ranked per family
    family_top: dict[SensorFamily, str] = {}
    for config in feasibility_result.ranked_configs:
        if config.sensor_family not in family_top:
            family_top[config.sensor_family] = config.sensor_name

    estimation_task = task or feasibility_result.detected_task or "unknown"
    safe_constraints = constraints if constraints is not None else {}

    family_results: list[FamilyOptimizationResult] = []
    total_evals = 0
    total_time = 0.0

    for family, sensor_name in family_top.items():
        logger.info(
            "optimizing_family",
            family=family.value,
            sensor=sensor_name,
        )

        sensor = _load_sensor_by_name(sensor_name, family)
        family_range = all_ranges.get(
            family,
            SensorFamilyRanges(family=family),
        )

        result = _optimize_family(
            base_sensor=sensor,
            family_ranges=family_range,
            estimation_task=estimation_task,
            constraints=safe_constraints,
            cost_weights=cost_weights,
        )

        family_results.append(result)
        if result.bo_metadata is not None:
            total_evals += result.bo_metadata.evaluations
            total_time += result.bo_metadata.computation_time_s

    # D-05: Return FULL unfiltered Pareto front. No filter_by_scope() call.
    return OptimizationResult(
        family_results=tuple(family_results),
        scope=scope,
        cost_weights=cost_weights,
        total_evaluations=total_evals,
        total_computation_time_s=total_time,
    )
