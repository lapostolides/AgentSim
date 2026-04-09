"""Unit tests for Gaussian Process surrogate and Expected Improvement acquisition.

Tests cover GP fit/predict immutability, interpolation accuracy, numerical
stability, EI computation, acquisition optimization, and adaptive stopping.
"""

from __future__ import annotations

import numpy as np
import pytest

from agentsim.knowledge_graph.optimizer.acquisition import (
    CONVERGENCE_THRESHOLD,
    HARD_CAP_EVALUATIONS,
    expected_improvement,
    should_stop,
)
from agentsim.knowledge_graph.optimizer.gaussian_process import MinimalGP


# ---------------------------------------------------------------------------
# MinimalGP tests
# ---------------------------------------------------------------------------


class TestMinimalGP:
    """Tests for the minimal Gaussian Process surrogate."""

    def test_fit_returns_new_instance(self) -> None:
        gp = MinimalGP(length_scale=1.0, noise=1e-6)
        X = np.array([[0.0], [1.0], [2.0]])
        y = np.array([0.0, 1.0, 0.0])
        fitted = gp.fit(X, y)
        assert fitted is not gp

    def test_predict_interpolation_sin(self) -> None:
        X_train = np.linspace(0, 2 * np.pi, 10).reshape(-1, 1)
        y_train = np.sin(X_train.ravel())

        gp = MinimalGP(length_scale=1.0, noise=1e-6)
        fitted = gp.fit(X_train, y_train)

        # Test at training points (interpolation).
        mean, _var = fitted.predict(X_train)
        assert np.allclose(mean, y_train, atol=0.1)

    def test_predict_non_negative_variance(self) -> None:
        X_train = np.array([[0.0], [1.0], [2.0], [3.0]])
        y_train = np.array([1.0, 2.0, 1.5, 3.0])

        gp = MinimalGP(length_scale=1.0, noise=1e-6)
        fitted = gp.fit(X_train, y_train)

        X_test = np.linspace(-1, 4, 20).reshape(-1, 1)
        _mean, var = fitted.predict(X_test)
        assert np.all(var >= 0.0)

    def test_numerical_stability_closely_spaced(self) -> None:
        # 50 closely-spaced points should not cause LinAlgError.
        X = np.linspace(0, 0.1, 50).reshape(-1, 1)
        y = np.sin(X.ravel())

        gp = MinimalGP(length_scale=0.5, noise=1e-6)
        fitted = gp.fit(X, y)  # Should not raise.
        mean, var = fitted.predict(X)
        assert mean.shape == (50,)
        assert var.shape == (50,)


# ---------------------------------------------------------------------------
# Expected Improvement tests
# ---------------------------------------------------------------------------


class TestExpectedImprovement:
    """Tests for the EI acquisition function."""

    def test_zero_when_mean_equals_best_and_zero_variance(self) -> None:
        mean = np.array([1.0])
        variance = np.array([0.0])
        best_observed = 1.0
        ei = expected_improvement(mean, variance, best_observed)
        assert ei[0] == 0.0

    def test_positive_when_mean_better_than_best(self) -> None:
        mean = np.array([0.5])
        variance = np.array([0.1])
        best_observed = 1.0  # We want to minimize, so lower is better.
        ei = expected_improvement(mean, variance, best_observed)
        assert ei[0] > 0.0

    def test_vectorized(self) -> None:
        mean = np.array([0.5, 1.5, 0.8])
        variance = np.array([0.1, 0.1, 0.1])
        best_observed = 1.0
        ei = expected_improvement(mean, variance, best_observed)
        assert ei.shape == (3,)


# ---------------------------------------------------------------------------
# Adaptive stopping tests
# ---------------------------------------------------------------------------


class TestShouldStop:
    """Tests for the adaptive convergence stopping criterion."""

    def test_stops_at_hard_cap(self) -> None:
        acq = [0.1] * 10
        assert should_stop(acq, HARD_CAP_EVALUATIONS) is True

    def test_stops_when_converged(self) -> None:
        # Window=5: last 5 values nearly identical to previous 5.
        acq = [1.0, 1.0, 1.0, 1.0, 1.0, 1.001, 1.001, 1.001, 1.001, 1.001, 1.001]
        assert should_stop(acq, n_evaluations=11, window=5) is True

    def test_does_not_stop_when_insufficient_data(self) -> None:
        acq = [0.1, 0.2, 0.3]
        assert should_stop(acq, n_evaluations=3, window=5) is False

    def test_does_not_stop_when_improving(self) -> None:
        acq = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 2.0]
        assert should_stop(acq, n_evaluations=11, window=5) is False
