"""Tests for CRB stability guards and numerical CRB computation.

Stability guard tests always run (pure numpy).
Numerical CRB tests skip gracefully when JAX is unavailable.
"""

from __future__ import annotations

import numpy as np
import pytest

from agentsim.knowledge_graph.crb.stability import (
    CONDITION_THRESHOLD,
    assert_positive_variance,
    check_condition_number,
    regularize_fisher,
)


# ---------------------------------------------------------------------------
# Stability guard tests (always run -- pure numpy, no JAX)
# ---------------------------------------------------------------------------


class TestStabilityGuards:
    """Tests for stability.py: condition number, Tikhonov, positive variance."""

    def test_condition_number_identity(self) -> None:
        """Identity matrix has condition number 1.0."""
        assert check_condition_number(np.eye(3)) == pytest.approx(1.0)

    def test_condition_number_near_singular(self) -> None:
        """Near-singular matrix has large condition number (>1e10)."""
        near_singular = np.array([[1.0, 1e6], [0.0, 1e-6]])
        cond = check_condition_number(near_singular)
        assert cond > 1e10

    def test_condition_number_singular(self) -> None:
        """Singular (zero) matrix returns inf condition number."""
        assert check_condition_number(np.zeros((2, 2))) == np.inf

    def test_regularize_fisher_adds_alpha_identity(self) -> None:
        """Tikhonov regularization adds alpha * I to the matrix."""
        matrix = np.array([[1.0, 2.0], [3.0, 4.0]])
        alpha = 1e-6
        result = regularize_fisher(matrix, alpha=alpha)
        expected = matrix + alpha * np.eye(2)
        np.testing.assert_allclose(result, expected)

    def test_regularize_fisher_does_not_mutate_input(self) -> None:
        """Input matrix must not be mutated by regularize_fisher."""
        original = np.array([[1.0, 0.0], [0.0, 1.0]])
        original_copy = original.copy()
        _ = regularize_fisher(original, alpha=0.1)
        np.testing.assert_array_equal(original, original_copy)

    def test_regularize_fisher_reduces_condition_number(self) -> None:
        """Regularization should reduce condition number of near-singular matrix."""
        near_singular = np.array([[1.0, 1e6], [0.0, 1e-6]])
        cond_before = check_condition_number(near_singular)
        regularized = regularize_fisher(near_singular, alpha=1e-3)
        cond_after = check_condition_number(regularized)
        assert cond_after < cond_before

    def test_assert_positive_variance_passes_for_positive_diagonal(self) -> None:
        """No error raised for matrix with all positive diagonal elements."""
        good_matrix = np.array([[1.0, 0.0], [0.0, 2.0]])
        # Should not raise
        assert_positive_variance(good_matrix)

    def test_assert_positive_variance_raises_for_negative_diagonal(self) -> None:
        """ValueError raised when any diagonal element is negative."""
        bad_matrix = np.array([[1.0, 0.0], [0.0, -0.5]])
        with pytest.raises(ValueError, match="Non-positive variance"):
            assert_positive_variance(bad_matrix)

    def test_assert_positive_variance_raises_for_zero_diagonal(self) -> None:
        """ValueError raised when any diagonal element is zero."""
        zero_diag = np.array([[1.0, 0.0], [0.0, 0.0]])
        with pytest.raises(ValueError, match="Non-positive variance"):
            assert_positive_variance(zero_diag)

    def test_condition_threshold_value(self) -> None:
        """CONDITION_THRESHOLD must be 1e12."""
        assert CONDITION_THRESHOLD == 1e12

    def test_no_jax_import_in_stability(self) -> None:
        """stability.py must not import JAX anywhere."""
        import inspect

        import agentsim.knowledge_graph.crb.stability as stability_mod

        source = inspect.getsource(stability_mod)
        assert "import jax" not in source
