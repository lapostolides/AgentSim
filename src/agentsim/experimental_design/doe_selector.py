"""DoE strategy selection based on parameter space dimensionality and budget.

Automatically picks the most appropriate sampling strategy (LHS, Sobol,
full factorial, or Bayesian) given the number of parameters and the
computational budget (max number of simulation runs).
"""

from __future__ import annotations

import structlog

from agentsim.experimental_design.models import (
    DoEStrategy,
    DoEStrategyType,
    ParameterSpace,
)

logger = structlog.get_logger()

# Decision thresholds for strategy selection
_FACTORIAL_MAX_DIM = 2
_FACTORIAL_MAX_BUDGET = 50
_SOBOL_MIN_DIM = 5
_BAYESIAN_MIN_DIM = 10
_BAYESIAN_MIN_BUDGET = 300


def _largest_power_of_two(n: int) -> int:
    """Return the largest power of 2 that is <= n.

    Args:
        n: Upper bound (must be >= 1).

    Returns:
        Largest power of 2 not exceeding n.
    """
    if n < 1:
        return 1
    power = 1
    while power * 2 <= n:
        power *= 2
    return power


def select_doe_strategy(
    parameter_space: ParameterSpace,
    budget: int,
) -> DoEStrategy:
    """Select the optimal DoE strategy for a given parameter space and budget.

    Decision logic (checked in order):
    1. Low dimensionality (<=2) with small budget (<=50): full factorial
    2. Very high dimensionality (>=10) with large budget (>=300): Bayesian
    3. High dimensionality (>=5): Sobol sequence
    4. Default (3-4 dims or other): Latin Hypercube Sampling

    Args:
        parameter_space: The parameter space to sample.
        budget: Maximum number of simulation runs allowed.

    Returns:
        A DoEStrategy with the selected type, sample count, and rationale.
    """
    dim = parameter_space.dimensionality

    if dim <= _FACTORIAL_MAX_DIM and budget <= _FACTORIAL_MAX_BUDGET:
        strategy_type = DoEStrategyType.FULL_FACTORIAL
        n_samples = budget
        rationale = (
            f"Full factorial design for {dim}D space with budget {budget}: "
            f"low dimensionality allows complete enumeration of parameter combinations."
        )
    elif dim >= _BAYESIAN_MIN_DIM and budget >= _BAYESIAN_MIN_BUDGET:
        strategy_type = DoEStrategyType.BAYESIAN
        n_samples = budget
        rationale = (
            f"Bayesian adaptive design for {dim}D space with budget {budget}: "
            f"high dimensionality benefits from sequential, model-guided sampling "
            f"that focuses on promising regions."
        )
    elif dim >= _SOBOL_MIN_DIM:
        strategy_type = DoEStrategyType.SOBOL
        n_samples = _largest_power_of_two(budget)
        rationale = (
            f"Sobol quasi-random sequence for {dim}D space: "
            f"low-discrepancy sequence provides better uniformity than LHS "
            f"in high-dimensional spaces. Using {n_samples} samples "
            f"(largest power of 2 within budget {budget})."
        )
    else:
        strategy_type = DoEStrategyType.LHS
        n_samples = budget
        rationale = (
            f"Latin Hypercube Sampling for {dim}D space with budget {budget}: "
            f"space-filling design ensures each parameter range is evenly covered "
            f"with stratified sampling."
        )

    logger.info(
        "doe_strategy_selected",
        strategy=strategy_type.value,
        dim=dim,
        budget=budget,
        n_samples=n_samples,
    )

    return DoEStrategy(
        strategy_type=strategy_type,
        n_samples=n_samples,
        rationale=rationale,
    )
