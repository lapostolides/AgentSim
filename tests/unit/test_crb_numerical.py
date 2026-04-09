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


# ---------------------------------------------------------------------------
# Numerical CRB tests -- always-run (mock JAX availability)
# ---------------------------------------------------------------------------


class TestNumericalCRBAlwaysRun:
    """Tests that run regardless of JAX installation."""

    def test_jax_available_returns_bool(self) -> None:
        """jax_available() must return a bool."""
        from agentsim.knowledge_graph.crb.numerical import jax_available

        result = jax_available()
        assert isinstance(result, bool)

    def test_numerical_families_is_frozenset_of_four(self) -> None:
        """NUMERICAL_FAMILIES must contain exactly the 4 exotic families."""
        from agentsim.knowledge_graph.crb.numerical import NUMERICAL_FAMILIES
        from agentsim.knowledge_graph.models import SensorFamily

        assert isinstance(NUMERICAL_FAMILIES, frozenset)
        assert NUMERICAL_FAMILIES == frozenset({
            SensorFamily.CODED_APERTURE,
            SensorFamily.LENSLESS,
            SensorFamily.EVENT_CAMERA,
            SensorFamily.LIGHT_FIELD,
        })

    def test_compute_numerical_crb_raises_import_error_without_jax(self) -> None:
        """ImportError with install message when JAX unavailable."""
        from unittest.mock import patch

        from agentsim.knowledge_graph.crb.numerical import compute_numerical_crb
        from agentsim.knowledge_graph.models import (
            GeometricProps,
            RadiometricProps,
            SensorFamily,
            SensorNode,
            TemporalProps,
        )

        sensor = SensorNode(
            name="test",
            family=SensorFamily.CODED_APERTURE,
            geometric=GeometricProps(fov=40.0),
            temporal=TemporalProps(),
            radiometric=RadiometricProps(),
            family_specs={
                "mask_pattern_type": "mura",
                "mask_transmittance": 0.5,
                "psf_condition_number": 8.0,
            },
        )
        with patch(
            "agentsim.knowledge_graph.crb.numerical.jax_available",
            return_value=False,
        ):
            with pytest.raises(ImportError, match="pip install jax jaxlib"):
                compute_numerical_crb(sensor)

    def test_compute_numerical_crb_raises_value_error_for_unsupported_family(
        self,
    ) -> None:
        """ValueError for families not in NUMERICAL_FAMILIES (e.g., SPAD)."""
        from unittest.mock import patch

        from agentsim.knowledge_graph.crb.numerical import compute_numerical_crb
        from agentsim.knowledge_graph.models import (
            GeometricProps,
            RadiometricProps,
            SensorFamily,
            SensorNode,
            TemporalProps,
        )

        sensor = SensorNode(
            name="test_spad",
            family=SensorFamily.SPAD,
            geometric=GeometricProps(fov=40.0),
            temporal=TemporalProps(temporal_resolution=100.0),
            radiometric=RadiometricProps(),
            family_specs={
                "dead_time_ns": 50.0,
                "afterpulsing_probability": 0.01,
                "crosstalk_probability": 0.02,
                "fill_factor": 0.5,
                "pde": 0.3,
            },
        )
        with patch(
            "agentsim.knowledge_graph.crb.numerical.jax_available",
            return_value=True,
        ):
            with pytest.raises(ValueError, match="not supported"):
                compute_numerical_crb(sensor)


# ---------------------------------------------------------------------------
# Numerical CRB tests -- JAX-dependent (skip if JAX unavailable)
# ---------------------------------------------------------------------------


class TestNumericalCRBWithJAX:
    """Tests that require JAX. Skipped gracefully when JAX is not installed."""

    @pytest.fixture(autouse=True)
    def _require_jax(self) -> None:
        pytest.importorskip("jax")

    def _make_sensor(
        self, family_str: str, specs: dict[str, float | str]
    ) -> object:
        """Helper to create a SensorNode for a given family."""
        from agentsim.knowledge_graph.models import (
            GeometricProps,
            RadiometricProps,
            SensorFamily,
            SensorNode,
            TemporalProps,
        )

        return SensorNode(
            name=f"test_{family_str}",
            family=SensorFamily(family_str),
            geometric=GeometricProps(fov=40.0),
            temporal=TemporalProps(),
            radiometric=RadiometricProps(quantum_efficiency=0.45),
            family_specs=specs,
        )

    def test_coded_aperture_crb(self) -> None:
        """Coded aperture returns positive finite bound with NUMERICAL confidence."""
        from agentsim.knowledge_graph.crb.numerical import compute_numerical_crb
        from agentsim.knowledge_graph.models import ConfidenceQualifier

        sensor = self._make_sensor("coded_aperture", {
            "mask_pattern_type": "mura",
            "mask_transmittance": 0.5,
            "psf_condition_number": 8.0,
        })
        result = compute_numerical_crb(sensor)
        assert result.bound_value > 0
        assert np.isfinite(result.bound_value)
        assert result.confidence == ConfidenceQualifier.NUMERICAL
        assert result.condition_number is not None

    def test_lensless_crb(self) -> None:
        """Lensless returns positive finite bound with NUMERICAL confidence."""
        from agentsim.knowledge_graph.crb.numerical import compute_numerical_crb
        from agentsim.knowledge_graph.models import ConfidenceQualifier

        sensor = self._make_sensor("lensless", {
            "mask_type": "diffuser",
            "mask_sensor_distance_mm": 3.0,
            "psf_condition_number": 12.0,
        })
        result = compute_numerical_crb(sensor)
        assert result.bound_value > 0
        assert np.isfinite(result.bound_value)
        assert result.confidence == ConfidenceQualifier.NUMERICAL

    def test_event_camera_crb(self) -> None:
        """Event camera returns positive finite bound with NUMERICAL confidence."""
        from agentsim.knowledge_graph.crb.numerical import compute_numerical_crb
        from agentsim.knowledge_graph.models import ConfidenceQualifier

        sensor = self._make_sensor("event_camera", {
            "contrast_threshold": 0.2,
            "refractory_period_us": 2.0,
            "bandwidth_khz": 200000.0,
        })
        result = compute_numerical_crb(sensor)
        assert result.bound_value > 0
        assert np.isfinite(result.bound_value)
        assert result.confidence == ConfidenceQualifier.NUMERICAL

    def test_light_field_crb(self) -> None:
        """Light field returns positive finite bound with NUMERICAL confidence."""
        from agentsim.knowledge_graph.crb.numerical import compute_numerical_crb
        from agentsim.knowledge_graph.models import ConfidenceQualifier

        sensor = self._make_sensor("light_field", {
            "microlens_pitch_um": 14.0,
            "angular_samples": 15.0,
            "baseline_mm": 0.5,
        })
        result = compute_numerical_crb(sensor)
        assert result.bound_value > 0
        assert np.isfinite(result.bound_value)
        assert result.confidence == ConfidenceQualifier.NUMERICAL

    def test_numerical_result_has_condition_number(self) -> None:
        """All numerical results include condition_number (float, not None)."""
        from agentsim.knowledge_graph.crb.numerical import compute_numerical_crb

        sensor = self._make_sensor("coded_aperture", {
            "mask_pattern_type": "mura",
            "mask_transmittance": 0.5,
            "psf_condition_number": 8.0,
        })
        result = compute_numerical_crb(sensor)
        assert isinstance(result.condition_number, float)

    def test_numerical_result_bound_type(self) -> None:
        """All numerical results have bound_type='numerical'."""
        from agentsim.knowledge_graph.crb.numerical import compute_numerical_crb

        sensor = self._make_sensor("lensless", {
            "mask_type": "diffuser",
            "mask_sensor_distance_mm": 3.0,
            "psf_condition_number": 12.0,
        })
        result = compute_numerical_crb(sensor)
        assert result.bound_type == "numerical"

    def test_jax_float64_enabled(self) -> None:
        """Verify that jax_enable_x64 is set after numerical CRB computation."""
        from agentsim.knowledge_graph.crb.numerical import compute_numerical_crb

        sensor = self._make_sensor("coded_aperture", {
            "mask_pattern_type": "mura",
            "mask_transmittance": 0.5,
            "psf_condition_number": 8.0,
        })
        _ = compute_numerical_crb(sensor)

        import jax

        assert jax.config.jax_enable_x64 is True
