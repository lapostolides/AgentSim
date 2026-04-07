"""Integration tests for physics validation pipeline.

Tests the wiring of the checker pipeline, physics advisor agent,
and runner integration. Uses mocks for LLM calls.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agentsim.physics.checker import run_deterministic_checks
from agentsim.physics.models import (
    PhysicsValidation,
    ValidationReport,
)
from agentsim.state.models import ExperimentState, ExperimentStatus, SceneSpec


# ---------------------------------------------------------------------------
# Agent registry tests
# ---------------------------------------------------------------------------


def test_agent_registry_includes_physics_advisor():
    """build_agent_registry() includes 'physics_advisor' key."""
    from agentsim.orchestrator.agent_registry import build_agent_registry

    registry = build_agent_registry()
    assert "physics_advisor" in registry


def test_agent_names_order():
    """get_agent_names() has 'physics_advisor' between 'scene' and 'executor'."""
    from agentsim.orchestrator.agent_registry import get_agent_names

    names = get_agent_names()
    scene_idx = names.index("scene")
    advisor_idx = names.index("physics_advisor")
    executor_idx = names.index("executor")
    assert scene_idx < advisor_idx < executor_idx


# ---------------------------------------------------------------------------
# Checker pipeline integration
# ---------------------------------------------------------------------------


def test_checker_pipeline_with_scene_code():
    """Run deterministic checks on realistic scene code, get ValidationReport."""
    code = """\
import numpy as np

dt = 0.001
dx = 0.1
velocity = 2.0

grid = np.zeros(100)
for step in range(1000):
    grid[1:] = grid[1:] + velocity * dt / dx * (grid[:-1] - grid[1:])
"""
    params = {
        "temperature": (300.0, "kelvin"),
        "velocity": (2.0, "meter / second"),
    }
    report = run_deterministic_checks(code=code, parameters=params)
    assert isinstance(report, ValidationReport)
    assert report.duration_seconds > 0
    assert len(report.results) > 0


# ---------------------------------------------------------------------------
# Physics validation phase tests
# ---------------------------------------------------------------------------


def test_run_physics_validation_phase_callable():
    """_run_physics_validation_phase is an async function."""
    from agentsim.orchestrator.runner import _run_physics_validation_phase

    assert asyncio.iscoroutinefunction(_run_physics_validation_phase)


@pytest.mark.asyncio
async def test_physics_validation_populates_state():
    """State after physics validation has physics_validations populated."""
    from agentsim.orchestrator.runner import _run_physics_validation_phase
    from agentsim.orchestrator.config import OrchestratorConfig

    scene = SceneSpec(
        plan_id="test-plan",
        code="x = 1.0\ny = 2.0\nresult = x + y",
        parameters={"temperature": [300.0, "kelvin"]},
    )
    state = ExperimentState(
        raw_hypothesis="test hypothesis",
        scenes=(scene,),
        status=ExperimentStatus.SCENES_READY,
    )
    config = OrchestratorConfig()
    agents = {}

    result_state = await _run_physics_validation_phase(state, config, agents)

    assert len(result_state.physics_validations) == 1
    assert result_state.physics_validations[0].scene_id == scene.id
    assert result_state.status == ExperimentStatus.PHYSICS_VALIDATED


@pytest.mark.asyncio
async def test_physics_validation_multiple_scenes():
    """Physics validation processes all scenes in state."""
    from agentsim.orchestrator.runner import _run_physics_validation_phase
    from agentsim.orchestrator.config import OrchestratorConfig

    scenes = tuple(
        SceneSpec(
            plan_id=f"plan-{i}",
            code=f"x_{i} = {i}.0",
            parameters={},
        )
        for i in range(3)
    )
    state = ExperimentState(
        raw_hypothesis="test",
        scenes=scenes,
        status=ExperimentStatus.SCENES_READY,
    )
    config = OrchestratorConfig()

    result_state = await _run_physics_validation_phase(state, config, {})
    assert len(result_state.physics_validations) == 3


@pytest.mark.asyncio
async def test_physics_validation_with_numeric_params():
    """Numeric-only parameters are wrapped as (value, 'dimensionless')."""
    from agentsim.orchestrator.runner import _run_physics_validation_phase
    from agentsim.orchestrator.config import OrchestratorConfig

    scene = SceneSpec(
        plan_id="test",
        code="n = 100",
        parameters={"grid_size": 100, "scale_factor": 0.5},
    )
    state = ExperimentState(
        raw_hypothesis="test",
        scenes=(scene,),
    )
    config = OrchestratorConfig()

    result_state = await _run_physics_validation_phase(state, config, {})
    assert len(result_state.physics_validations) == 1
    assert result_state.physics_validations[0].report.passed is True


# ---------------------------------------------------------------------------
# Runner integration test (verify wiring exists)
# ---------------------------------------------------------------------------


def test_runner_has_physics_validation_phase():
    """Runner module exposes _run_physics_validation_phase."""
    from agentsim.orchestrator import runner

    assert hasattr(runner, "_run_physics_validation_phase")


def test_runner_imports_physics():
    """Runner imports run_deterministic_checks and PhysicsValidation."""
    from agentsim.orchestrator import runner

    # These should be importable after our modifications
    assert hasattr(runner, "run_deterministic_checks")
    assert hasattr(runner, "PhysicsValidation")
    assert hasattr(runner, "add_physics_validation")
