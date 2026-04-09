"""Expected Improvement acquisition function with adaptive convergence (D-02).

Provides the EI acquisition function for guiding Bayesian optimization search,
acquisition optimization via L-BFGS-B with random restarts, and an adaptive
stopping criterion based on improvement rate (Research Pattern 4).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize as scipy_minimize
from scipy.stats import norm

from agentsim.knowledge_graph.optimizer.gaussian_process import MinimalGP

CONVERGENCE_THRESHOLD: float = 0.01
"""Relative improvement threshold (1%) for convergence detection."""

HARD_CAP_EVALUATIONS: int = 200
"""Maximum number of BO evaluations before forced stop."""


def expected_improvement(
    mean: np.ndarray,
    variance: np.ndarray,
    best_observed: float,
    xi: float = 0.01,
) -> np.ndarray:
    """Compute Expected Improvement at candidate points.

    Standard EI formula for minimization. Higher EI indicates more promising
    candidates for reducing the objective below the current best.

    Args:
        mean: Predicted mean at candidate points, shape (N,).
        variance: Predicted variance at candidate points, shape (N,).
        best_observed: Best (lowest) objective value observed so far.
        xi: Exploration-exploitation trade-off parameter.

    Returns:
        EI values, shape (N,). Non-negative everywhere.
    """
    mean = np.asarray(mean)
    variance = np.asarray(variance)

    ei = np.zeros_like(mean)
    mask = variance > 1e-12

    std = np.sqrt(variance[mask] + 1e-12)
    improvement = best_observed - mean[mask] - xi
    z = improvement / std
    ei[mask] = improvement * norm.cdf(z) + std * norm.pdf(z)

    # EI should be non-negative.
    return np.maximum(ei, 0.0)


def optimize_acquisition(
    gp: MinimalGP,
    best_observed: float,
    bounds: np.ndarray,
    n_restarts: int = 5,
) -> np.ndarray:
    """Find the point that maximizes Expected Improvement via L-BFGS-B.

    Uses multiple random restarts to avoid local optima in the acquisition
    landscape.

    Args:
        gp: Fitted GP surrogate.
        best_observed: Best (lowest) objective value observed so far.
        bounds: Parameter bounds, shape (D, 2), in [0, 1] normalized space.
        n_restarts: Number of random starting points.

    Returns:
        Best candidate point, shape (D,).
    """
    dim = bounds.shape[0]
    best_x = None
    best_ei = -np.inf

    for _ in range(n_restarts):
        x0 = np.random.uniform(bounds[:, 0], bounds[:, 1], size=dim)

        def neg_ei(x: np.ndarray) -> float:
            x_2d = x.reshape(1, -1)
            mean, var = gp.predict(x_2d)
            ei_val = expected_improvement(mean, var, best_observed)
            return -float(ei_val[0])

        result = scipy_minimize(
            neg_ei,
            x0,
            bounds=bounds.tolist(),
            method="L-BFGS-B",
        )

        if -result.fun > best_ei:
            best_ei = -result.fun
            best_x = result.x

    if best_x is None:
        return np.random.uniform(bounds[:, 0], bounds[:, 1], size=dim)

    return best_x


def should_stop(
    acq_values: list[float],
    n_evaluations: int,
    window: int = 5,
) -> bool:
    """Check whether the BO loop should terminate.

    Stops when either:
    1. The hard cap on evaluations is reached.
    2. The relative improvement in max acquisition value between recent
       windows falls below CONVERGENCE_THRESHOLD.

    Args:
        acq_values: History of max acquisition values per iteration.
        n_evaluations: Total evaluations performed so far.
        window: Size of the comparison window.

    Returns:
        True if optimization should stop, False otherwise.
    """
    if n_evaluations >= HARD_CAP_EVALUATIONS:
        return True

    if len(acq_values) < window + 1:
        return False

    recent = acq_values[-window:]
    previous = acq_values[-(window + 1) : -1]

    max_recent = max(recent)
    max_previous = max(previous)

    if max_previous == 0.0:
        return max_recent == 0.0

    relative_improvement = abs(max_recent - max_previous) / abs(max_previous)
    return relative_improvement < CONVERGENCE_THRESHOLD
