"""Tests for CRB dispatch -- unified routing across all 14 sensor families.

Verifies that compute_crb never raises for any sensor family (D-07),
routes analytical/numerical families correctly, and degrades gracefully
when JAX is unavailable (D-05).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agentsim.knowledge_graph.crb.analytical import ANALYTICAL_FAMILIES
from agentsim.knowledge_graph.crb.dispatch import SUPPORTED_FAMILIES, compute_crb
from agentsim.knowledge_graph.crb.models import CRBResult
from agentsim.knowledge_graph.crb.numerical import NUMERICAL_FAMILIES
from agentsim.knowledge_graph.loader import load_sensors
from agentsim.knowledge_graph.models import ConfidenceQualifier, SensorFamily, SensorNode


# ---------------------------------------------------------------------------
# Fixtures: load one sensor per family
# ---------------------------------------------------------------------------

_ALL_SENSORS = load_sensors()
_SENSORS_BY_FAMILY: dict[SensorFamily, SensorNode] = {}
for _s in _ALL_SENSORS:
    if _s.family not in _SENSORS_BY_FAMILY:
        _SENSORS_BY_FAMILY[_s.family] = _s


def _sensor_for(family: SensorFamily) -> SensorNode:
    return _SENSORS_BY_FAMILY[family]


# ---------------------------------------------------------------------------
# Dispatch routing tests
# ---------------------------------------------------------------------------


class TestDispatchRouting:
    """Verify analytical/numerical/unsupported routing."""

    def test_spad_routes_to_analytical(self) -> None:
        result = compute_crb(_sensor_for(SensorFamily.SPAD))
        assert result.confidence == ConfidenceQualifier.ANALYTICAL
        assert result.bound_type == "analytical"

    def test_cw_tof_routes_to_analytical(self) -> None:
        result = compute_crb(_sensor_for(SensorFamily.CW_TOF))
        assert result.confidence == ConfidenceQualifier.ANALYTICAL

    def test_coded_aperture_routes_to_numerical_or_unknown(self) -> None:
        """Numerical if JAX present, UNKNOWN if absent."""
        result = compute_crb(_sensor_for(SensorFamily.CODED_APERTURE))
        assert result.confidence in (
            ConfidenceQualifier.NUMERICAL,
            ConfidenceQualifier.UNKNOWN,
        )

    def test_rgb_returns_unknown_never_raises(self) -> None:
        result = compute_crb(_sensor_for(SensorFamily.RGB))
        assert result.confidence == ConfidenceQualifier.UNKNOWN
        assert result.bound_value == float("inf")

    def test_lidar_mechanical_returns_unknown(self) -> None:
        result = compute_crb(_sensor_for(SensorFamily.LIDAR_MECHANICAL))
        assert result.confidence == ConfidenceQualifier.UNKNOWN
        assert result.bound_value == float("inf")

    def test_lidar_solid_state_returns_unknown(self) -> None:
        result = compute_crb(_sensor_for(SensorFamily.LIDAR_SOLID_STATE))
        assert result.confidence == ConfidenceQualifier.UNKNOWN
        assert result.bound_value == float("inf")


class TestSupportedFamilies:
    """SUPPORTED_FAMILIES = ANALYTICAL | NUMERICAL (11 families)."""

    def test_supported_equals_union(self) -> None:
        assert SUPPORTED_FAMILIES == ANALYTICAL_FAMILIES | NUMERICAL_FAMILIES

    def test_supported_count(self) -> None:
        assert len(SUPPORTED_FAMILIES) == 11


class TestKwargPassthrough:
    """Verify kwargs forwarded to analytical functions."""

    def test_snr_passthrough(self) -> None:
        sensor = _sensor_for(SensorFamily.CW_TOF)
        r1 = compute_crb(sensor, snr=10.0)
        r2 = compute_crb(sensor, snr=1000.0)
        # Higher SNR -> lower bound
        assert r2.bound_value < r1.bound_value

    def test_n_photons_passthrough(self) -> None:
        sensor = _sensor_for(SensorFamily.SPAD)
        r1 = compute_crb(sensor, n_photons=100)
        r2 = compute_crb(sensor, n_photons=100000)
        assert r2.bound_value < r1.bound_value


class TestJaxFallback:
    """When JAX unavailable, numerical families degrade to UNKNOWN."""

    def test_coded_aperture_fallback_no_jax(self) -> None:
        with patch(
            "agentsim.knowledge_graph.crb.dispatch.jax_available",
            return_value=False,
        ):
            result = compute_crb(_sensor_for(SensorFamily.CODED_APERTURE))
            assert result.confidence == ConfidenceQualifier.UNKNOWN
            assert result.bound_value == float("inf")
            # No ImportError raised
            assert isinstance(result, CRBResult)


class TestAllFamiliesNeverRaise:
    """compute_crb returns CRBResult for every SensorFamily -- never raises."""

    @pytest.mark.parametrize("family", list(SensorFamily))
    def test_no_exception(self, family: SensorFamily) -> None:
        if family not in _SENSORS_BY_FAMILY:
            pytest.skip(f"No sensor loaded for {family.value}")
        result = compute_crb(_SENSORS_BY_FAMILY[family])
        assert isinstance(result, CRBResult)
