"""Stability guards for Fisher information matrix inversion (CRB-06, D-06).

All functions accept and return numpy arrays. No JAX dependency.
Used by numerical.py after computing the Fisher information matrix.

Threshold rationale: 1e12 is conservative. Float64 has ~15 digits of
precision, so condition numbers above ~1e15 mean total precision loss.
1e12 leaves a 3-order-of-magnitude safety margin (Golub & Van Loan,
"Matrix Computations," 4th ed.).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

CONDITION_THRESHOLD: float = 1e12


def check_condition_number(matrix: NDArray[np.floating]) -> float:
    """Compute the 2-norm condition number of a square matrix.

    Args:
        matrix: Square numpy array.

    Returns:
        Condition number as float. Returns np.inf for singular matrices.
    """
    return float(np.linalg.cond(matrix))


def regularize_fisher(
    fisher: NDArray[np.floating],
    alpha: float = 1e-6,
) -> NDArray[np.floating]:
    """Apply Tikhonov regularization: F_reg = F + alpha * I.

    Returns a NEW array -- does not mutate the input.

    Args:
        fisher: Square Fisher information matrix.
        alpha: Regularization strength. Default 1e-6 is small enough
            to minimally perturb well-conditioned matrices but large
            enough to stabilize near-singular ones.

    Returns:
        New regularized Fisher matrix.
    """
    return fisher + alpha * np.eye(fisher.shape[0])


def assert_positive_variance(
    inv_fisher: NDArray[np.floating],
) -> None:
    """Assert all diagonal elements of the inverse Fisher matrix are positive.

    Negative diagonal elements mean negative variance (physically impossible).
    This catches numerical inversion errors before they propagate.

    Args:
        inv_fisher: Inverted Fisher information matrix.

    Raises:
        ValueError: If any diagonal element is non-positive.
    """
    diag = np.diag(inv_fisher)
    if np.any(diag <= 0):
        raise ValueError(
            f"Non-positive variance detected on Fisher inverse diagonal: {diag}"
        )
