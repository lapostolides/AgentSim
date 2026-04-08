"""Unit tests for transient validation module.

Tests OPL-to-time conversion, peak timing extraction from synthetic
transient data, and peak timing comparison/validation.
"""

from __future__ import annotations

import numpy as np
import pytest


SPEED_OF_LIGHT = 299_792_458.0


class TestOplToTimeNs:
    """Tests for opl_to_time_ns conversion."""

    def test_known_value(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            opl_to_time_ns,
        )

        result = opl_to_time_ns(0.003)
        expected = (0.003 / SPEED_OF_LIGHT) * 1e9
        assert abs(result - expected) < 1e-12

    def test_zero(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            opl_to_time_ns,
        )

        assert opl_to_time_ns(0.0) == 0.0

    def test_large_value(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            opl_to_time_ns,
        )

        # 1 meter OPL -> ~3.336 ns
        result = opl_to_time_ns(1.0)
        expected = (1.0 / SPEED_OF_LIGHT) * 1e9
        assert abs(result - expected) < 1e-6


class TestTimeNsToOpl:
    """Tests for time_ns_to_opl conversion."""

    def test_known_value(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            time_ns_to_opl,
        )

        result = time_ns_to_opl(10.0)
        expected = 10.0 * 1e-9 * SPEED_OF_LIGHT
        assert abs(result - expected) < 1e-6

    def test_roundtrip(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            opl_to_time_ns,
            time_ns_to_opl,
        )

        opl_original = 3.5
        time_ns = opl_to_time_ns(opl_original)
        opl_back = time_ns_to_opl(time_ns)
        assert abs(opl_back - opl_original) < 1e-10


class TestExtractPeakTimingNs:
    """Tests for extract_peak_timing_ns with synthetic data."""

    def test_synthetic_peak_at_bin_50(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            extract_peak_timing_ns,
            opl_to_time_ns,
        )

        # Create (W=4, H=4, T=100, C=3) shaped array with peak at bin 50
        data = np.zeros((4, 4, 100, 3), dtype=np.float32)
        data[:, :, 50, :] = 10.0  # peak at temporal bin 50

        bin_width_opl = 0.01  # 1 cm per bin
        start_opl = 0.0
        result = extract_peak_timing_ns(data, bin_width_opl, start_opl)

        expected_opl = start_opl + 50 * bin_width_opl
        expected_ns = opl_to_time_ns(expected_opl)
        assert abs(result - expected_ns) < 1e-6

    def test_all_zero_array(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            extract_peak_timing_ns,
            opl_to_time_ns,
        )

        data = np.zeros((4, 4, 100, 3), dtype=np.float32)
        bin_width_opl = 0.01
        start_opl = 0.5
        result = extract_peak_timing_ns(data, bin_width_opl, start_opl)

        # Should return opl_to_time_ns(start_opl) for all-zero data
        expected = opl_to_time_ns(start_opl)
        assert abs(result - expected) < 1e-6

    def test_nonzero_start_opl(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            extract_peak_timing_ns,
            opl_to_time_ns,
        )

        data = np.zeros((4, 4, 50, 3), dtype=np.float32)
        data[:, :, 10, :] = 5.0  # peak at bin 10

        bin_width_opl = 0.02
        start_opl = 1.0
        result = extract_peak_timing_ns(data, bin_width_opl, start_opl)

        expected_opl = 1.0 + 10 * 0.02
        expected_ns = opl_to_time_ns(expected_opl)
        assert abs(result - expected_ns) < 1e-6


class TestValidatePeakTiming:
    """Tests for validate_peak_timing comparison."""

    def test_matching_values(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            validate_peak_timing,
        )

        result = validate_peak_timing(
            measured_peak_ns=10.0,
            expected_peak_ns=10.3,
            tolerance_ns=0.5,
        )
        assert result.match is True
        assert abs(result.delta_ns - 0.3) < 1e-10

    def test_mismatching_values(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            validate_peak_timing,
        )

        result = validate_peak_timing(
            measured_peak_ns=10.0,
            expected_peak_ns=12.0,
            tolerance_ns=0.5,
        )
        assert result.match is False
        assert abs(result.delta_ns - 2.0) < 1e-10

    def test_result_fields(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            validate_peak_timing,
        )

        result = validate_peak_timing(
            measured_peak_ns=5.0,
            expected_peak_ns=5.1,
            tolerance_ns=0.5,
        )
        assert result.measured_peak_ns == 5.0
        assert result.expected_peak_ns == 5.1
        assert result.tolerance_ns == 0.5
        assert result.match is True

    def test_result_is_frozen(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.validation import (
            TransientValidationResult,
        )

        result = TransientValidationResult(
            measured_peak_ns=1.0,
            expected_peak_ns=1.0,
            delta_ns=0.0,
            tolerance_ns=0.5,
            match=True,
        )
        with pytest.raises(Exception):
            result.match = False  # type: ignore[misc]
