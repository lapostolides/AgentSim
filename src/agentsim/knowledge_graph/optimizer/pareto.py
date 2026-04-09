"""Non-dominated sorting and Pareto front extraction.

Extracts the Pareto-optimal subset from a set of evaluated objective vectors.
Infeasible points (negative original constraint margin) are excluded before
ranking per D-03.
"""

from __future__ import annotations

import numpy as np


def extract_pareto_front(objectives: np.ndarray) -> np.ndarray:
    """Return indices of non-dominated points from an (N, 3) objective array.

    All objectives are minimization targets. Column layout:
        0 = CRB bound (minimize)
        1 = operational cost (minimize)
        2 = negated constraint margin (minimize; original margin was positive
            for feasible points, so negated value is negative for feasible)

    Points with objectives[:, 2] > 0 are infeasible (original margin < 0)
    and are excluded before dominance checking.

    A point p dominates q if p <= q in all dimensions and p < q in at least
    one dimension.

    Args:
        objectives: Shape (N, 3) array of objective values.

    Returns:
        1-D integer array of row indices that belong to the Pareto front.
    """
    if objectives.shape[0] == 0:
        return np.array([], dtype=int)

    # Filter infeasible points (negated margin > 0 means original margin < 0).
    feasible_mask = objectives[:, 2] <= 0.0
    feasible_indices = np.where(feasible_mask)[0]

    if len(feasible_indices) == 0:
        return np.array([], dtype=int)

    feasible_obj = objectives[feasible_indices]
    n = feasible_obj.shape[0]

    is_dominated = np.zeros(n, dtype=bool)
    for i in range(n):
        if is_dominated[i]:
            continue
        for j in range(n):
            if i == j or is_dominated[j]:
                continue
            # Check if j dominates i: j <= i in all dims and j < i in at least one.
            if np.all(feasible_obj[j] <= feasible_obj[i]) and np.any(
                feasible_obj[j] < feasible_obj[i]
            ):
                is_dominated[i] = True
                break

    return feasible_indices[~is_dominated]
