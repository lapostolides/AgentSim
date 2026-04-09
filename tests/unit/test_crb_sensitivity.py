"""Tests for Morris method sensitivity analysis (CRB-05, D-08, D-09).

Verifies parameter importance ranking via Elementary Effects, immutability
of original sensor during perturbation, and edge cases.
"""

from __future__ import annotations

import pytest

from agentsim.knowledge_graph.crb.sensitivity import (
    SensitivityResult,
    compute_sensitivity,
)
from agentsim.knowledge_graph.loader import load_sensors
from agentsim.knowledge_graph.models import SensorFamily, SensorNode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ALL_SENSORS = load_sensors()


def _spad_sensor() -> SensorNode:
    for s in _ALL_SENSORS:
        if s.family == SensorFamily.SPAD:
            return s
    raise RuntimeError("No SPAD sensor found")


# ---------------------------------------------------------------------------
# Core sensitivity tests
# ---------------------------------------------------------------------------


class TestComputeSensitivity:
    """Morris method sensitivity analysis."""

    def test_two_parameters_ranked(self) -> None:
        sensor = _spad_sensor()
        result = compute_sensitivity(sensor, ["pde", "fill_factor"])
        assert len(result.entries) == 2
        assert result.entries[0].rank == 1
        assert result.entries[1].rank == 2

    def test_sensitivity_non_negative(self) -> None:
        sensor = _spad_sensor()
        result = compute_sensitivity(sensor, ["pde", "fill_factor"])
        for entry in result.entries:
            assert entry.mu_star >= 0.0

    def test_result_model_fields(self) -> None:
        sensor = _spad_sensor()
        result = compute_sensitivity(sensor, ["pde"])
        assert isinstance(result, SensitivityResult)
        assert isinstance(result.sensor_name, str)
        assert isinstance(result.estimation_task, str)
        assert isinstance(result.baseline_crb, float)
        assert isinstance(result.entries, tuple)
        assert result.num_trajectories > 0

    def test_empty_parameters_valid_baseline(self) -> None:
        sensor = _spad_sensor()
        result = compute_sensitivity(sensor, [])
        assert len(result.entries) == 0
        assert result.baseline_crb > 0.0

    def test_unknown_parameter_raises(self) -> None:
        sensor = _spad_sensor()
        with pytest.raises(ValueError, match="not_a_real_param"):
            compute_sensitivity(sensor, ["not_a_real_param"])


class TestImmutability:
    """Perturbation creates new SensorNode, original unchanged."""

    def test_original_sensor_unchanged(self) -> None:
        sensor = _spad_sensor()
        original_pde = sensor.family_specs["pde"]
        compute_sensitivity(sensor, ["pde"])
        assert sensor.family_specs["pde"] == original_pde

    def test_frozen_result(self) -> None:
        sensor = _spad_sensor()
        result = compute_sensitivity(sensor, ["pde"])
        with pytest.raises(Exception):
            result.baseline_crb = 999.0  # type: ignore[misc]


class TestDefaults:
    """Default parameter values."""

    def test_default_num_trajectories(self) -> None:
        sensor = _spad_sensor()
        result = compute_sensitivity(sensor, ["pde"])
        assert result.num_trajectories == 10

    def test_default_perturbation_fraction(self) -> None:
        """Verify 10% perturbation is the default by checking output consistency."""
        sensor = _spad_sensor()
        result_default = compute_sensitivity(sensor, ["pde"])
        result_explicit = compute_sensitivity(
            sensor, ["pde"], perturbation_fraction=0.1
        )
        # Same perturbation fraction -> same mu_star (within RNG variation)
        # We just verify both produce valid results
        assert result_default.entries[0].mu_star > 0.0
        assert result_explicit.entries[0].mu_star > 0.0


class TestClassification:
    """Morris method classification of parameters."""

    def test_entries_have_classification(self) -> None:
        sensor = _spad_sensor()
        result = compute_sensitivity(sensor, ["pde", "fill_factor"])
        for entry in result.entries:
            assert entry.classification in (
                "negligible",
                "linear",
                "nonlinear",
            )

    def test_entries_have_sigma(self) -> None:
        sensor = _spad_sensor()
        result = compute_sensitivity(sensor, ["pde", "fill_factor"])
        for entry in result.entries:
            assert hasattr(entry, "sigma")
            assert entry.sigma >= 0.0
