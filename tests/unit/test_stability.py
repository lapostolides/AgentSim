"""Tests for CFL numerical stability checks."""

from __future__ import annotations

import pytest

from agentsim.physics.checks.stability import check_cfl_stability
from agentsim.physics.models import ExtractedSimulationParams, Severity


def _make_params(
    velocity: float | None = None,
    timestep: float | None = None,
    mesh_spacing: float | None = None,
    solver_type: str = "explicit",
) -> ExtractedSimulationParams:
    """Helper to build ExtractedSimulationParams with specific fields."""
    return ExtractedSimulationParams(
        velocity=velocity,
        timestep=timestep,
        mesh_spacing=mesh_spacing,
        solver_type=solver_type,
    )


class TestCFLExplicitSolver:
    """Test CFL checks for explicit solvers."""

    def test_cfl_0_5_is_stable(self) -> None:
        # CFL = 10 * 0.005 / 0.1 = 0.5
        params = _make_params(velocity=10.0, timestep=0.005, mesh_spacing=0.1)
        results = check_cfl_stability(params)
        assert len(results) == 1
        assert results[0].severity == Severity.INFO
        assert "stable" in results[0].message.lower() or "within" in results[0].message.lower()

    def test_cfl_1_5_is_unstable(self) -> None:
        # CFL = 10 * 0.015 / 0.1 = 1.5
        params = _make_params(velocity=10.0, timestep=0.015, mesh_spacing=0.1)
        results = check_cfl_stability(params)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR

    def test_cfl_0_9_is_warning(self) -> None:
        # CFL = 10 * 0.009 / 0.1 = 0.9
        params = _make_params(velocity=10.0, timestep=0.009, mesh_spacing=0.1)
        results = check_cfl_stability(params)
        assert len(results) == 1
        assert results[0].severity == Severity.WARNING
        assert "close" in results[0].message.lower() or "stability limit" in results[0].message.lower()


class TestCFLImplicitSolver:
    """Test CFL checks for implicit solvers."""

    def test_implicit_solver_skips_cfl(self) -> None:
        params = _make_params(
            velocity=10.0, timestep=0.1, mesh_spacing=0.01, solver_type="implicit"
        )
        results = check_cfl_stability(params)
        assert len(results) == 1
        assert results[0].severity == Severity.INFO
        assert "not applicable" in results[0].message.lower()


class TestCFLMissingParams:
    """Test CFL checks with insufficient parameters."""

    def test_missing_velocity(self) -> None:
        params = _make_params(velocity=None, timestep=0.001, mesh_spacing=0.1)
        results = check_cfl_stability(params)
        assert len(results) == 1
        assert results[0].severity == Severity.INFO
        assert "insufficient" in results[0].message.lower()

    def test_missing_timestep(self) -> None:
        params = _make_params(velocity=10.0, timestep=None, mesh_spacing=0.1)
        results = check_cfl_stability(params)
        assert results[0].severity == Severity.INFO

    def test_missing_mesh_spacing(self) -> None:
        params = _make_params(velocity=10.0, timestep=0.001, mesh_spacing=None)
        results = check_cfl_stability(params)
        assert results[0].severity == Severity.INFO


class TestCFLUnknownSolver:
    """Test CFL checks for unknown solver type."""

    def test_unknown_solver_cfl_above_1_is_warning(self) -> None:
        # CFL = 10 * 0.015 / 0.1 = 1.5
        params = _make_params(
            velocity=10.0, timestep=0.015, mesh_spacing=0.1, solver_type="unknown"
        )
        results = check_cfl_stability(params)
        assert len(results) == 1
        assert results[0].severity == Severity.WARNING  # Not ERROR for unknown


class TestCFLDetails:
    """Test that CFL results include details."""

    def test_details_include_parameters(self) -> None:
        params = _make_params(velocity=10.0, timestep=0.005, mesh_spacing=0.1)
        results = check_cfl_stability(params)
        assert "velocity=" in results[0].details
        assert "dt=" in results[0].details
        assert "dx=" in results[0].details


class TestCFLZeroMeshSpacing:
    """Test zero mesh spacing edge case."""

    def test_zero_mesh_spacing_returns_error(self) -> None:
        params = _make_params(velocity=10.0, timestep=0.001, mesh_spacing=0.0)
        results = check_cfl_stability(params)
        assert results[0].severity == Severity.ERROR
        assert "zero" in results[0].message.lower()
