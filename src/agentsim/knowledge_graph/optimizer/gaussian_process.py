"""Minimal Gaussian Process with RBF kernel for Bayesian optimization surrogate.

Uses scipy Cholesky factorization for numerical stability. Follows
Rasmussen & Williams (2006) Gaussian Processes for Machine Learning.
The GP is used as a surrogate model in the BO loop (D-01, Research Pattern 1).
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import cho_factor, cho_solve


class MinimalGP:
    """Gaussian Process regression with RBF (squared exponential) kernel.

    Immutable pattern: fit() returns a NEW MinimalGP instance rather than
    mutating internal state. Predictions require a fitted instance.

    Args:
        length_scale: RBF kernel length scale parameter.
        noise: Diagonal noise (jitter) added for numerical stability.
    """

    def __init__(
        self,
        length_scale: float = 1.0,
        noise: float = 1e-6,
        *,
        _X: np.ndarray | None = None,
        _y: np.ndarray | None = None,
        _L: tuple | None = None,
        _alpha: np.ndarray | None = None,
    ) -> None:
        self._length_scale = length_scale
        self._noise = noise
        self._X = _X
        self._y = _y
        self._L = _L
        self._alpha = _alpha

    def fit(self, X: np.ndarray, y: np.ndarray) -> MinimalGP:
        """Fit the GP to training data, returning a NEW fitted instance.

        Args:
            X: Training inputs, shape (N, D).
            y: Training targets, shape (N,).

        Returns:
            A new MinimalGP instance with computed Cholesky factor and alpha.
        """
        X = np.atleast_2d(X)
        y = np.asarray(y).ravel()

        K = self._rbf_kernel(X, X)
        K_noisy = K + self._noise * np.eye(K.shape[0])

        L = cho_factor(K_noisy, lower=True)
        alpha = cho_solve(L, y)

        return MinimalGP(
            length_scale=self._length_scale,
            noise=self._noise,
            _X=X,
            _y=y,
            _L=L,
            _alpha=alpha,
        )

    def predict(self, X_new: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Predict mean and variance at new input locations.

        Args:
            X_new: Test inputs, shape (M, D).

        Returns:
            Tuple of (mean, variance) arrays, each shape (M,).

        Raises:
            RuntimeError: If called on an unfitted GP instance.
        """
        if self._X is None or self._alpha is None or self._L is None:
            raise RuntimeError("GP must be fitted before calling predict().")

        X_new = np.atleast_2d(X_new)

        K_star = self._rbf_kernel(self._X, X_new)
        mean = K_star.T @ self._alpha

        v = cho_solve(self._L, K_star)
        K_new = self._rbf_kernel(X_new, X_new)
        var = np.diag(K_new - K_star.T @ v).clip(min=0.0)

        return mean, var

    def _rbf_kernel(self, X1: np.ndarray, X2: np.ndarray) -> np.ndarray:
        """Compute the RBF (squared exponential) kernel matrix.

        K(x1, x2) = exp(-0.5 * ||x1 - x2||^2 / length_scale^2)

        Args:
            X1: First input array, shape (N, D).
            X2: Second input array, shape (M, D).

        Returns:
            Kernel matrix, shape (N, M).
        """
        X1 = np.atleast_2d(X1)
        X2 = np.atleast_2d(X2)

        sq_dist = (
            np.sum(X1**2, axis=1, keepdims=True)
            + np.sum(X2**2, axis=1)
            - 2.0 * X1 @ X2.T
        )
        return np.exp(-0.5 * sq_dist / (self._length_scale**2))
