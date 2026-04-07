"""Tests for SymPy dimensional equation tracing."""

from __future__ import annotations

import time

import pytest
from sympy.physics.units import length, time as sym_time, mass
from sympy.physics.units.dimensions import Dimension

from agentsim.physics.checks.equations import (
    check_equation_dimensions,
    check_expression_dimensions,
)
from agentsim.physics.models import Severity


class TestExpressionDimensions:
    """Test single expression dimensional comparison."""

    def test_matching_dimensions_length_over_time(self) -> None:
        lhs = length / sym_time
        rhs = length / sym_time
        assert check_expression_dimensions(lhs, rhs) is True

    def test_mismatched_dimensions_length_vs_time(self) -> None:
        assert check_expression_dimensions(length, sym_time) is False

    def test_dimensionless_match(self) -> None:
        # Dimensionless = Dimension(1)
        d1 = Dimension(1)
        d2 = Dimension(1)
        assert check_expression_dimensions(d1, d2) is True

    def test_complex_dimensions_force(self) -> None:
        # force = mass * length / time^2
        force_lhs = mass * length / sym_time**2
        force_rhs = mass * length / sym_time**2
        assert check_expression_dimensions(force_lhs, force_rhs) is True

    def test_complex_mismatch(self) -> None:
        # mass*length/time^2 vs mass*length/time
        force = mass * length / sym_time**2
        momentum_rate = mass * length / sym_time
        assert check_expression_dimensions(force, momentum_rate) is False


class TestCheckEquationDimensions:
    """Test batch equation dimensional checking."""

    def test_returns_check_results_per_pair(self) -> None:
        equations = (
            (length, length, "x = L"),
            (length, sym_time, "x = t (wrong)"),
        )
        results = check_equation_dimensions(equations)
        assert len(results) == 2
        # First should be INFO (consistent)
        assert results[0].severity == Severity.INFO
        # Second should be ERROR (mismatch)
        assert results[1].severity == Severity.ERROR

    def test_all_consistent(self) -> None:
        equations = (
            (length / sym_time, length / sym_time, "v = dx/dt"),
            (mass, mass, "m = m0"),
        )
        results = check_equation_dimensions(equations)
        assert all(r.severity == Severity.INFO for r in results)

    def test_all_mismatched(self) -> None:
        equations = (
            (length, sym_time, "x = t"),
            (mass, length, "m = L"),
        )
        results = check_equation_dimensions(equations)
        assert all(r.severity == Severity.ERROR for r in results)

    def test_check_field_is_equations(self) -> None:
        equations = ((length, length, "test"),)
        results = check_equation_dimensions(equations)
        assert results[0].check == "equations"

    def test_performance_20_pairs_under_1s(self) -> None:
        equations = tuple(
            (length / sym_time, length / sym_time, f"eq_{i}")
            for i in range(20)
        )
        start = time.perf_counter()
        results = check_equation_dimensions(equations)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"Took {elapsed:.3f}s, exceeds 1s budget"
        assert len(results) == 20
