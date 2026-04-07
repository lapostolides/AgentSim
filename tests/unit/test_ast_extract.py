"""Tests for AST-based physics parameter extraction from generated Python code."""

from __future__ import annotations

import time

import pytest

from agentsim.physics.checks.ast_extract import extract_physics_from_ast
from agentsim.physics.models import ASTExtractionResult, ExtractedParameter, Severity


class TestSimpleAssignment:
    """Test extraction from simple variable assignments."""

    def test_simple_float_assignment(self) -> None:
        code = "dt = 0.001"
        result = extract_physics_from_ast(code)
        assert isinstance(result, ASTExtractionResult)
        params = result.params.parameters
        assert len(params) >= 1
        match = [p for p in params if p.name == "dt"]
        assert len(match) == 1
        assert match[0].value == pytest.approx(0.001)
        assert match[0].line == 1

    def test_negative_value_assignment(self) -> None:
        code = "g = -9.81"
        result = extract_physics_from_ast(code)
        params = result.params.parameters
        match = [p for p in params if p.name == "g"]
        assert len(match) == 1
        assert match[0].value == pytest.approx(-9.81)


class TestDictLiteral:
    """Test extraction from dictionary literal definitions."""

    def test_dict_literal_extracts_both_parameters(self) -> None:
        code = 'params = {"velocity": 10.0, "density": 1000.0}'
        result = extract_physics_from_ast(code)
        params = result.params.parameters
        names = {p.name for p in params}
        assert "velocity" in names
        assert "density" in names
        vel = [p for p in params if p.name == "velocity"][0]
        assert vel.value == pytest.approx(10.0)
        dens = [p for p in params if p.name == "density"][0]
        assert dens.value == pytest.approx(1000.0)


class TestKeywordArgument:
    """Test extraction from function call keyword arguments."""

    def test_keyword_arg_extraction(self) -> None:
        code = "solver.set_timestep(dt=0.001)"
        result = extract_physics_from_ast(code)
        params = result.params.parameters
        match = [p for p in params if p.name == "dt"]
        assert len(match) == 1
        assert match[0].value == pytest.approx(0.001)


class TestSubscriptAssignment:
    """Test extraction from dictionary subscript assignments."""

    def test_subscript_assignment(self) -> None:
        code = 'config["dt"] = 0.001'
        result = extract_physics_from_ast(code)
        params = result.params.parameters
        match = [p for p in params if p.name == "dt"]
        assert len(match) == 1
        assert match[0].value == pytest.approx(0.001)


class TestSolverDetection:
    """Test detection of solver type from function calls."""

    def test_implicit_solver_bdf(self) -> None:
        code = "scipy.integrate.solve_ivp(rhs, t_span, y0, method='BDF')"
        result = extract_physics_from_ast(code)
        assert result.params.solver_type == "implicit"

    def test_explicit_solver_rk45(self) -> None:
        code = "scipy.integrate.solve_ivp(rhs, t_span, y0, method='RK45')"
        result = extract_physics_from_ast(code)
        assert result.params.solver_type == "explicit"


class TestMeshPathDetection:
    """Test detection of mesh file paths from load function calls."""

    def test_trimesh_load(self) -> None:
        code = 'trimesh.load("mesh.stl")'
        result = extract_physics_from_ast(code)
        assert "mesh.stl" in result.params.mesh_paths

    def test_load_mesh_function(self) -> None:
        code = 'load_mesh("bunny.obj")'
        result = extract_physics_from_ast(code)
        assert "bunny.obj" in result.params.mesh_paths


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_code_returns_empty_params(self) -> None:
        code = "x = 'hello'\nprint(42)"
        result = extract_physics_from_ast(code)
        # String assignments and print calls don't yield physics params
        assert isinstance(result, ASTExtractionResult)
        assert len(result.issues) == 0

    def test_syntax_error_returns_error_issue(self) -> None:
        code = "def broken(:\n  pass"
        result = extract_physics_from_ast(code)
        assert len(result.issues) >= 1
        assert any(i.severity == Severity.ERROR for i in result.issues)
        assert any("parse" in i.message.lower() or "syntax" in i.message.lower() for i in result.issues)


class TestKnownParamMapping:
    """Test that known physics parameter names are mapped to ExtractedSimulationParams fields."""

    def test_timestep_mapped(self) -> None:
        code = "dt = 0.001"
        result = extract_physics_from_ast(code)
        assert result.params.timestep == pytest.approx(0.001)

    def test_velocity_mapped(self) -> None:
        code = "velocity = 10.0"
        result = extract_physics_from_ast(code)
        assert result.params.velocity == pytest.approx(10.0)

    def test_mesh_spacing_mapped(self) -> None:
        code = "dx = 0.01"
        result = extract_physics_from_ast(code)
        assert result.params.mesh_spacing == pytest.approx(0.01)


class TestPerformance:
    """Test performance requirements."""

    def test_extraction_under_100ms_for_500_lines(self) -> None:
        lines = []
        for i in range(500):
            lines.append(f"param_{i} = {float(i) * 0.1}")
        code = "\n".join(lines)

        start = time.perf_counter()
        result = extract_physics_from_ast(code)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"Extraction took {elapsed:.3f}s, exceeds 100ms budget"
        assert len(result.params.parameters) == 500
