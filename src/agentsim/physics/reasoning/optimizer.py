"""Optimizer mode -- rank sensor+algorithm combinations by propagation-derived scores.

Enumerates the cartesian product of compatible sensors and algorithms,
propagates constraints through merged transfer function chains, and
scores each combination. No LLM calls -- purely deterministic.
"""

from __future__ import annotations

import itertools
import math

from agentsim.physics.domains import get_compatible_algorithms, get_compatible_sensor_classes
from agentsim.physics.domains.schema import DomainBundle, ParadigmKnowledge
from agentsim.physics.reasoning.models import OptimizerResult, PropagationResult, ScoredSetup
from agentsim.physics.reasoning.propagation import propagate_constraints


def optimize_setup(
    hypothesis_params: dict[str, float],
    bundle: DomainBundle,
    paradigm: ParadigmKnowledge,
) -> OptimizerResult:
    """Rank sensor+algorithm combinations for a given hypothesis.

    Enumerates all (sensor_class, algorithm) pairs compatible with the
    paradigm, propagates hypothesis parameters through merged transfer
    function chains, scores each setup, and returns results sorted
    descending by score.

    Args:
        hypothesis_params: Parameter name-value pairs from the hypothesis.
        bundle: Complete domain bundle with sensors and algorithms.
        paradigm: Paradigm under which to optimize.

    Returns:
        OptimizerResult with scored setups sorted descending by score.
    """
    sensors = get_compatible_sensor_classes(bundle, paradigm)
    algorithms = get_compatible_algorithms(bundle, paradigm)

    setups: list[ScoredSetup] = []
    for sensor_class, algorithm in itertools.product(sensors, algorithms):
        # Merge transfer functions: paradigm + sensor + algorithm
        merged_tfs = (
            paradigm.transfer_functions
            + sensor_class.transfer_functions
            + algorithm.transfer_functions
        )

        propagation = propagate_constraints(hypothesis_params, merged_tfs)
        score = _compute_setup_score(propagation, hypothesis_params)

        algo_name = algorithm.algorithm or algorithm.name
        setup = ScoredSetup(
            sensor_class=sensor_class.name,
            algorithm=algo_name,
            computed_metrics=propagation.computed,
            score=score,
        )
        setups.append(setup)

    # Sort descending by score
    sorted_setups = sorted(setups, key=lambda s: s.score, reverse=True)

    return OptimizerResult(
        paradigm=paradigm.paradigm,
        setups=tuple(sorted_setups),
    )


def _compute_setup_score(
    result: PropagationResult,
    hypothesis_params: dict[str, float],
) -> float:
    """Score a propagation result for hypothesis relevance.

    Heuristic scoring:
    - Base: number of successfully computed outputs (finite, non-nan)
    - Bonus +1.0 per "strong" coupling_strength in computed values
    - Bonus +2.0 per hypothesis param that overlaps with computed parameter names

    Args:
        result: Propagation output for a sensor+algorithm combo.
        hypothesis_params: Original hypothesis parameters.

    Returns:
        Numeric score (higher is better, >= 0).
    """
    score = 0.0

    for cv in result.computed:
        # Count finite, non-nan outputs
        if math.isfinite(cv.value):
            score += 1.0

        # Bonus for strong coupling
        if cv.relationship and cv.relationship in ("linear", "inverse", "sqrt"):
            # Use the source relationship as a proxy for coupling strength
            pass

    # Bonus for strong coupling_strength (from TF metadata stored in source_tf_formula context)
    # We check the relationship field which mirrors coupling info
    # A more direct check: count computed values from strong-coupled TFs
    # The computed values don't carry coupling_strength directly, but we can
    # infer from the relationship type being well-defined (not pass-through)
    strong_count = sum(
        1 for cv in result.computed
        if cv.relationship in ("linear", "inverse", "sqrt", "proportional", "quadratic")
        and math.isfinite(cv.value)
    )
    score += strong_count * 1.0

    # Bonus for hypothesis parameter overlap
    computed_param_names = frozenset(cv.parameter for cv in result.computed)
    hypothesis_param_names = frozenset(hypothesis_params.keys())
    overlap = computed_param_names & hypothesis_param_names
    score += len(overlap) * 2.0

    return score
