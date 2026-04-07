"""Tests for parameter range plausibility checks.

Verifies that range checks cross-reference the constants registry
and flag out-of-range values with correct severity.
"""

from __future__ import annotations

import time

import pytest

from agentsim.physics.checks.ranges import check_parameter_ranges
from agentsim.physics.models import Severity


class TestCheckParameterRanges:
    def test_in_range_wavelength_no_errors(self) -> None:
        params = {"wavelength": (550e-9, "meter")}
        results = check_parameter_ranges(params, domain="computational_imaging")
        # Should have no ERROR results
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_wavelength_way_above_range_returns_error(self) -> None:
        params = {"wavelength": (100.0, "meter")}
        results = check_parameter_ranges(params, domain="computational_imaging")
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert "wavelength" in errors[0].parameter

    def test_unknown_parameter_returns_info(self) -> None:
        params = {"unknown_param": (42.0, "meter")}
        results = check_parameter_ranges(params)
        info_results = [r for r in results if r.severity == Severity.INFO]
        assert len(info_results) >= 1
        assert "unknown_param" in info_results[0].message

    def test_domain_specific_ranges(self) -> None:
        # pixel_pitch is only in computational_imaging ranges
        params = {"pixel_pitch": (3.45e-6, "meter")}
        results = check_parameter_ranges(params, domain="computational_imaging")
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_negative_temperature_returns_error(self) -> None:
        params = {"temperature": (-10.0, "kelvin")}
        results = check_parameter_ranges(params)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1

    def test_velocity_at_speed_of_light_boundary(self) -> None:
        # Exactly at the boundary should be fine
        params = {"velocity": (3e8, "meter / second")}
        results = check_parameter_ranges(params)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_velocity_above_speed_of_light_returns_error(self) -> None:
        params = {"velocity": (4e8, "meter / second")}
        results = check_parameter_ranges(params)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1

    def test_empty_params_returns_empty(self) -> None:
        results = check_parameter_ranges({})
        assert results == ()

    def test_returns_immutable_tuple(self) -> None:
        params = {"temperature": (300.0, "kelvin")}
        results = check_parameter_ranges(params)
        assert isinstance(results, tuple)

    def test_unit_conversion_for_range_check(self) -> None:
        """Wavelength in nanometers should be converted to meters for comparison."""
        params = {"wavelength": (550.0, "nanometer")}
        results = check_parameter_ranges(params, domain="computational_imaging")
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_incompatible_units_returns_warning(self) -> None:
        """Wavelength in kelvin should produce a warning about unit mismatch."""
        params = {"wavelength": (550.0, "kelvin")}
        results = check_parameter_ranges(params, domain="computational_imaging")
        warnings = [r for r in results if r.severity == Severity.WARNING]
        assert len(warnings) >= 1

    def test_performance_100_params(self) -> None:
        """100 parameters should check in under 100ms."""
        params = {f"temperature": (300.0, "kelvin")}
        # Use a single known param repeated with unique keys
        params = {f"temperature": (300.0, "kelvin")}
        big_params = {}
        for i in range(100):
            big_params[f"temperature_{i}"] = (300.0, "kelvin")
        start = time.monotonic()
        check_parameter_ranges(big_params)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1, f"Took {elapsed:.3f}s for 100 params"
