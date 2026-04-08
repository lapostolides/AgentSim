"""Parameter sampling engines for Design of Experiments.

Provides LHS, Sobol, and full factorial samplers that generate design matrices
with values scaled to declared parameter bounds. Uses SALib for LHS and Sobol
sequences, and itertools for full factorial enumeration.
"""

from __future__ import annotations

import itertools

import numpy as np
import structlog
from SALib.sample import latin as salib_latin
from SALib.sample import sobol as salib_sobol

from agentsim.experimental_design.models import (
    DoEStrategy,
    ParameterSpace,
    SampledDesign,
)

logger = structlog.get_logger()


def _to_salib_problem(space: ParameterSpace) -> dict:
    """Convert a ParameterSpace to a SALib problem dictionary.

    Args:
        space: The parameter space to convert.

    Returns:
        Dict with 'num_vars', 'names', and 'bounds' keys for SALib.
    """
    return {
        "num_vars": space.dimensionality,
        "names": list(space.names),
        "bounds": [[p.low, p.high] for p in space.parameters],
    }


def _matrix_to_tuples(matrix: np.ndarray) -> tuple[tuple[float, ...], ...]:
    """Convert a numpy matrix to nested tuples for Pydantic immutability.

    Args:
        matrix: 2D numpy array of shape (n_runs, n_params).

    Returns:
        Nested tuples of float values.
    """
    return tuple(
        tuple(float(v) for v in row)
        for row in matrix
    )


def generate_lhs_design(
    parameter_space: ParameterSpace,
    strategy: DoEStrategy,
) -> SampledDesign:
    """Generate a Latin Hypercube Sampling design.

    Uses SALib's LHS implementation which produces space-filling designs
    where each parameter column covers the full range with stratified sampling.

    Args:
        parameter_space: The parameter space defining bounds.
        strategy: DoE strategy with n_samples count.

    Returns:
        SampledDesign with design matrix scaled to parameter bounds.
    """
    problem = _to_salib_problem(parameter_space)
    matrix = salib_latin.sample(problem, N=strategy.n_samples)
    nested_tuples = _matrix_to_tuples(matrix)

    logger.info(
        "lhs_design_generated",
        n_runs=strategy.n_samples,
        dim=parameter_space.dimensionality,
    )

    return SampledDesign(
        strategy=strategy,
        parameter_names=parameter_space.names,
        design_matrix=nested_tuples,
    )


def generate_sobol_design(
    parameter_space: ParameterSpace,
    strategy: DoEStrategy,
) -> SampledDesign:
    """Generate a Sobol quasi-random sequence design.

    Uses SALib's Saltelli sampling which generates (N*(2D+2)) samples for
    sensitivity analysis. We slice to the first n_samples rows for a
    predictable output size.

    Args:
        parameter_space: The parameter space defining bounds.
        strategy: DoE strategy with n_samples count.

    Returns:
        SampledDesign with design matrix scaled to parameter bounds.
    """
    problem = _to_salib_problem(parameter_space)
    # SALib Sobol/Saltelli generates N*(2D+2) rows; we take first n_samples
    raw_n = max(1, strategy.n_samples // (2 * parameter_space.dimensionality + 2))
    matrix = salib_sobol.sample(problem, N=max(raw_n, 1))
    # Slice to requested number of samples
    matrix = matrix[: strategy.n_samples]
    nested_tuples = _matrix_to_tuples(matrix)

    logger.info(
        "sobol_design_generated",
        n_runs=len(nested_tuples),
        dim=parameter_space.dimensionality,
    )

    return SampledDesign(
        strategy=strategy,
        parameter_names=parameter_space.names,
        design_matrix=nested_tuples,
    )


def generate_full_factorial_design(
    parameter_space: ParameterSpace,
    strategy: DoEStrategy,
    levels: int = 5,
) -> SampledDesign:
    """Generate a full factorial design with evenly spaced levels.

    Creates all combinations of parameter levels using np.linspace for each
    parameter, then takes the Cartesian product. Caps at n_samples rows.

    Args:
        parameter_space: The parameter space defining bounds.
        strategy: DoE strategy with n_samples cap.
        levels: Number of evenly spaced levels per parameter.

    Returns:
        SampledDesign with design matrix of all (or capped) combinations.
    """
    level_arrays = [
        np.linspace(p.low, p.high, levels)
        for p in parameter_space.parameters
    ]
    all_combinations = list(itertools.product(*level_arrays))
    # Cap at n_samples
    capped = all_combinations[: strategy.n_samples]
    nested_tuples = tuple(
        tuple(float(v) for v in combo)
        for combo in capped
    )

    logger.info(
        "factorial_design_generated",
        n_runs=len(nested_tuples),
        dim=parameter_space.dimensionality,
        levels=levels,
        total_combinations=len(all_combinations),
    )

    return SampledDesign(
        strategy=strategy,
        parameter_names=parameter_space.names,
        design_matrix=nested_tuples,
    )
