"""Tests for Pint-based unit consistency validation.

Verifies that the unit checker catches undefined units, NaN, inf,
and returns appropriate CheckResult objects.
"""

from __future__ import annotations

import math
import time

import pytest

from agentsim.physics.checks.units import check_unit_consistency
from agentsim.physics.models import Severity


class TestCheckUnitConsistency:
    def test_valid_params_returns_empty(self) -> None:
        params = {
            "velocity": (10.0, "meter / second"),
            "mass": (5.0, "kilogram"),
        }
        results = check_unit_consistency(params)
        assert results == ()

    def test_undefined_unit_returns_error(self) -> None:
        params = {"length": (1.0, "foobar")}
        results = check_unit_consistency(params)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "foobar" in results[0].message
        assert results[0].parameter == "length"

    def test_nan_magnitude_returns_error(self) -> None:
        params = {"velocity": (float("nan"), "meter / second")}
        results = check_unit_consistency(params)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "NaN" in results[0].message

    def test_inf_magnitude_returns_error(self) -> None:
        params = {"velocity": (float("inf"), "meter / second")}
        results = check_unit_consistency(params)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "infinite" in results[0].message.lower() or "inf" in results[0].message.lower()

    def test_negative_inf_magnitude_returns_error(self) -> None:
        params = {"temp": (float("-inf"), "kelvin")}
        results = check_unit_consistency(params)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR

    def test_multiple_params_checks_all(self) -> None:
        params = {
            "good": (1.0, "meter"),
            "bad_unit": (1.0, "foobar"),
            "bad_nan": (float("nan"), "second"),
        }
        results = check_unit_consistency(params)
        assert len(results) == 2
        param_names = {r.parameter for r in results}
        assert "bad_unit" in param_names
        assert "bad_nan" in param_names

    def test_empty_params_returns_empty(self) -> None:
        results = check_unit_consistency({})
        assert results == ()

    def test_dimensionless_unit_valid(self) -> None:
        params = {"ratio": (0.5, "dimensionless")}
        results = check_unit_consistency(params)
        assert results == ()

    def test_returns_immutable_tuple(self) -> None:
        params = {"x": (1.0, "foobar")}
        results = check_unit_consistency(params)
        assert isinstance(results, tuple)

    def test_performance_100_params(self) -> None:
        """100 parameters should validate in under 100ms."""
        params = {f"param_{i}": (float(i), "meter") for i in range(100)}
        start = time.monotonic()
        check_unit_consistency(params)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1, f"Took {elapsed:.3f}s for 100 params"
