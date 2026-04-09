"""Tests for CRB result models and analytical CRB computation.

Verifies frozen Pydantic models (CRBResult, CRBBound, SensitivityEntry)
and closed-form CRB functions for all 7 analytical sensor families using
real sensor data from Phase 7 YAML files.
"""

from __future__ import annotations

import math

import pytest

from agentsim.knowledge_graph.crb.models import CRBBound, CRBResult, SensitivityEntry
from agentsim.knowledge_graph.loader import load_sensors
from agentsim.knowledge_graph.models import ConfidenceQualifier, SensorFamily

# ---------------------------------------------------------------------------
# Unit conversion constants (replicate for test verification)
# ---------------------------------------------------------------------------

_C = 299_792_458.0
_MHZ_TO_HZ = 1e6
_PS_TO_S = 1e-12
_NS_TO_S = 1e-9
_GHZ_TO_HZ = 1e9
_MM_TO_M = 1e-3


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _first_sensor(family: SensorFamily) -> object:
    """Load first sensor for a given family."""
    sensors = load_sensors(families=(family,))
    assert len(sensors) > 0, f"No sensors loaded for {family.value}"
    return sensors[0]


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestCRBModels:
    """Tests for frozen CRB data models."""

    def test_crb_result_is_frozen(self) -> None:
        result = CRBResult(
            sensor_family=SensorFamily.SPAD,
            estimation_task="depth",
            bound_value=0.001,
            bound_unit="meter",
            bound_type="analytical",
            confidence=ConfidenceQualifier.ANALYTICAL,
            sensor_name="test",
        )
        with pytest.raises(Exception):
            result.bound_value = 0.002  # type: ignore[misc]

    def test_crb_result_fields(self) -> None:
        result = CRBResult(
            sensor_family=SensorFamily.SPAD,
            estimation_task="depth",
            bound_value=0.001,
            bound_unit="meter",
            bound_type="analytical",
            confidence=ConfidenceQualifier.ANALYTICAL,
            condition_number=None,
            model_assumptions=("Poisson",),
            sensor_name="test_sensor",
        )
        assert result.sensor_family == SensorFamily.SPAD
        assert result.estimation_task == "depth"
        assert result.bound_value == 0.001
        assert result.bound_unit == "meter"
        assert result.bound_type == "analytical"
        assert result.confidence == ConfidenceQualifier.ANALYTICAL
        assert result.condition_number is None
        assert result.model_assumptions == ("Poisson",)
        assert result.sensor_name == "test_sensor"

    def test_crb_bound_is_frozen(self) -> None:
        bound = CRBBound(
            parameter_name="depth",
            bound_value=0.001,
            bound_unit="meter",
        )
        with pytest.raises(Exception):
            bound.bound_value = 0.002  # type: ignore[misc]

    def test_crb_bound_fields(self) -> None:
        bound = CRBBound(
            parameter_name="depth",
            bound_value=0.001,
            bound_unit="meter",
        )
        assert bound.parameter_name == "depth"
        assert bound.bound_value == 0.001
        assert bound.bound_unit == "meter"

    def test_sensitivity_entry_is_frozen(self) -> None:
        entry = SensitivityEntry(
            parameter_name="pde",
            nominal_value=0.25,
            perturbed_crb=0.002,
            sensitivity=1.5,
            rank=1,
        )
        with pytest.raises(Exception):
            entry.rank = 2  # type: ignore[misc]

    def test_sensitivity_entry_fields(self) -> None:
        entry = SensitivityEntry(
            parameter_name="pde",
            nominal_value=0.25,
            perturbed_crb=0.002,
            sensitivity=1.5,
            rank=1,
        )
        assert entry.parameter_name == "pde"
        assert entry.nominal_value == 0.25
        assert entry.perturbed_crb == 0.002
        assert entry.sensitivity == 1.5
        assert entry.rank == 1


# ---------------------------------------------------------------------------
# Analytical CRB tests
# ---------------------------------------------------------------------------


class TestSpadDepthCRB:
    """Tests for SPAD depth CRB computation."""

    def test_spad_depth_crb_numerical(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.SPAD)
        # TMF8828: pde=0.25, fill_factor=0.30, temporal_resolution=200 ps
        result = compute_analytical_crb(sensor, n_photons=10000)

        # Manual calculation:
        n_eff = 10000 * 0.25 * 0.30  # = 750
        b_eff = 1.0 / (200.0 * _PS_TO_S)  # = 5e9 Hz
        variance = _C**2 / (8.0 * n_eff * b_eff**2)
        expected = math.sqrt(variance)

        assert math.isfinite(result.bound_value)
        assert result.bound_value > 0
        assert abs(result.bound_value - expected) / expected < 0.01  # 1% tolerance

    def test_spad_depth_crb_metadata(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.SPAD)
        result = compute_analytical_crb(sensor)

        assert result.confidence == ConfidenceQualifier.ANALYTICAL
        assert result.bound_unit == "meter"
        assert result.estimation_task == "depth"
        assert result.bound_type == "analytical"
        assert result.condition_number is None
        assert result.sensor_name == "TMF8828"

    def test_spad_depth_crb_range(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.SPAD)
        result = compute_analytical_crb(sensor, n_photons=10000)
        # Expected ~0.000774 m, verify in range 0.0005 to 0.001
        assert 0.0005 < result.bound_value < 0.001


class TestCwTofRangeCRB:
    """Tests for CW-ToF range CRB computation."""

    def test_cw_tof_range_crb_numerical(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.CW_TOF)
        # PMD CamBoard: modulation_frequency_mhz=80.0
        result = compute_analytical_crb(sensor, snr=100.0)

        f_mod = 80.0 * _MHZ_TO_HZ
        variance = _C**2 / (32.0 * math.pi**2 * f_mod**2 * 100.0)
        expected = math.sqrt(variance)

        assert math.isfinite(result.bound_value)
        assert result.bound_value > 0
        assert abs(result.bound_value - expected) / expected < 0.01

    def test_cw_tof_range_crb_metadata(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.CW_TOF)
        result = compute_analytical_crb(sensor)

        assert result.confidence == ConfidenceQualifier.ANALYTICAL
        assert result.bound_unit == "meter"
        assert result.estimation_task == "range"


class TestPulsedDtofRangeCRB:
    """Tests for pulsed dToF range CRB computation."""

    def test_pulsed_dtof_range_crb_numerical(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.PULSED_DTOF)
        # Garmin LIDAR-Lite v4: pulse_width_ns=5.0
        result = compute_analytical_crb(sensor, snr=100.0)

        tau_p = 5.0 * _NS_TO_S
        variance = _C**2 * tau_p**2 / (8.0 * 100.0)
        expected = math.sqrt(variance)

        assert math.isfinite(result.bound_value)
        assert result.bound_value > 0
        assert abs(result.bound_value - expected) / expected < 0.01

    def test_pulsed_dtof_range_crb_metadata(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.PULSED_DTOF)
        result = compute_analytical_crb(sensor)

        assert result.confidence == ConfidenceQualifier.ANALYTICAL
        assert result.bound_unit == "meter"
        assert result.estimation_task == "range"


class TestFmcwRangeCRB:
    """Tests for FMCW range CRB computation."""

    def test_fmcw_range_crb_numerical(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.LIDAR_FMCW)
        # Aeva Aeries II: chirp_bandwidth_ghz=10.0
        result = compute_analytical_crb(sensor, snr=100.0)

        b_chirp = 10.0 * _GHZ_TO_HZ
        variance = _C**2 / (8.0 * math.pi**2 * b_chirp**2 * 100.0)
        expected = math.sqrt(variance)

        assert math.isfinite(result.bound_value)
        assert result.bound_value > 0
        assert abs(result.bound_value - expected) / expected < 0.01

    def test_fmcw_range_crb_metadata(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.LIDAR_FMCW)
        result = compute_analytical_crb(sensor)

        assert result.confidence == ConfidenceQualifier.ANALYTICAL
        assert result.bound_unit == "meter"
        assert result.estimation_task == "range"


class TestPolarimetricStokesCRB:
    """Tests for polarimetric Stokes CRB computation."""

    def test_polarimetric_stokes_crb_numerical(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.POLARIMETRIC)
        # Lucid Vision Phoenix: extinction_ratio=350.0, qe=0.72
        result = compute_analytical_crb(sensor, n_photons=10000)

        n_eff = 10000 * 0.72
        k_ext = 350.0
        variance = 1.0 / (n_eff * k_ext**2)
        expected = math.sqrt(variance)

        assert math.isfinite(result.bound_value)
        assert result.bound_value > 0
        assert abs(result.bound_value - expected) / expected < 0.01

    def test_polarimetric_stokes_crb_metadata(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.POLARIMETRIC)
        result = compute_analytical_crb(sensor)

        assert result.confidence == ConfidenceQualifier.ANALYTICAL
        assert result.bound_unit == "dimensionless"
        assert result.estimation_task == "dolp"


class TestSpectralUnmixingCRB:
    """Tests for hyperspectral unmixing CRB computation."""

    def test_spectral_unmixing_crb_numerical(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.SPECTRAL)
        # Ximea: band_count=25, spectral_range 600-875, spectral_resolution_nm=15.0
        result = compute_analytical_crb(sensor, snr=100.0)

        band_count = 25.0
        spectral_range = 875.0 - 600.0  # = 275
        spectral_resolution_ratio = spectral_range / 15.0
        variance = band_count / (100.0**2 * spectral_resolution_ratio)
        expected = math.sqrt(variance)

        assert math.isfinite(result.bound_value)
        assert result.bound_value > 0
        assert abs(result.bound_value - expected) / expected < 0.01

    def test_spectral_unmixing_crb_metadata(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.SPECTRAL)
        result = compute_analytical_crb(sensor)

        assert result.confidence == ConfidenceQualifier.ANALYTICAL
        assert result.bound_unit == "dimensionless"
        assert result.estimation_task == "abundance"


class TestStructuredLightDepthCRB:
    """Tests for structured light depth CRB computation."""

    def test_structured_light_depth_crb_numerical(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.STRUCTURED_LIGHT)
        # Intel D415: projector_resolution="1280x720", baseline_mm=55.0
        result = compute_analytical_crb(sensor, snr=100.0, target_depth_m=5.0)

        baseline = 55.0 * _MM_TO_M
        f_proj = 1280.0  # max(1280, 720)
        sigma_px = 1.0 / math.sqrt(100.0)
        variance = (5.0**2 * sigma_px**2) / (baseline**2 * f_proj**2)
        expected = math.sqrt(variance)

        assert math.isfinite(result.bound_value)
        assert result.bound_value > 0
        assert abs(result.bound_value - expected) / expected < 0.01

    def test_structured_light_depth_crb_metadata(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.STRUCTURED_LIGHT)
        result = compute_analytical_crb(sensor)

        assert result.confidence == ConfidenceQualifier.ANALYTICAL
        assert result.bound_unit == "meter"
        assert result.estimation_task == "depth"

    def test_projector_resolution_parsing_1280x720(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import _parse_projector_resolution

        assert _parse_projector_resolution("1280x720") == 1280

    def test_projector_resolution_parsing_2064x1544(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import _parse_projector_resolution

        assert _parse_projector_resolution("2064x1544") == 2064

    def test_projector_resolution_parsing_3200x1(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import _parse_projector_resolution

        assert _parse_projector_resolution("3200x1") == 3200


# ---------------------------------------------------------------------------
# Dispatch tests
# ---------------------------------------------------------------------------


class TestDispatch:
    """Tests for the analytical CRB dispatch function."""

    def test_all_7_families_return_analytical(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import (
            ANALYTICAL_FAMILIES,
            compute_analytical_crb,
        )

        for family in ANALYTICAL_FAMILIES:
            sensor = _first_sensor(family)
            result = compute_analytical_crb(sensor)
            assert result.confidence == ConfidenceQualifier.ANALYTICAL, (
                f"Expected ANALYTICAL for {family.value}, got {result.confidence}"
            )

    def test_unsupported_family_raises_value_error(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.EVENT_CAMERA)
        with pytest.raises(ValueError, match="not supported"):
            compute_analytical_crb(sensor)

    def test_analytical_families_has_7_members(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import ANALYTICAL_FAMILIES

        assert len(ANALYTICAL_FAMILIES) == 7
        assert isinstance(ANALYTICAL_FAMILIES, frozenset)


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for SNR edge cases."""

    def test_high_snr_produces_smaller_bound(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.CW_TOF)
        default_result = compute_analytical_crb(sensor, snr=100.0)
        high_snr_result = compute_analytical_crb(sensor, snr=1e6)
        assert high_snr_result.bound_value < default_result.bound_value

    def test_low_snr_produces_larger_bound(self) -> None:
        from agentsim.knowledge_graph.crb.analytical import compute_analytical_crb

        sensor = _first_sensor(SensorFamily.CW_TOF)
        default_result = compute_analytical_crb(sensor, snr=100.0)
        low_snr_result = compute_analytical_crb(sensor, snr=1.0)
        assert low_snr_result.bound_value > default_result.bound_value
