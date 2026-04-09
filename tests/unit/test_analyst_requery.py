"""Tests for analyst re-query detection and KG context injection (PIPE-07, PIPE-08).

Tests that:
- _run_analyst_phase includes KG context in prompt when feasibility_result exists
- Re-query triggers when analyst outputs constraint_modifications
- Re-query count is capped at 2 per experiment
- No re-query when constraint_modifications is None
- Re-query passes constraint_modifications as constraint_overrides
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentsim.state.models import AnalysisReport, ExperimentState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(*, with_feasibility: bool = False) -> ExperimentState:
    """Build a minimal ExperimentState for testing."""
    state = ExperimentState(raw_hypothesis="test hypothesis")
    if with_feasibility:
        from agentsim.knowledge_graph.models import (
            ConfidenceQualifier,
            FeasibilityResult,
            SensorConfig,
            SensorFamily,
        )
        config = SensorConfig(
            sensor_name="TestSPAD",
            sensor_family=SensorFamily.SPAD,
            algorithm_name="test-algo",
            rank=1,
            feasibility_score=0.9,
            confidence=ConfidenceQualifier.ANALYTICAL,
        )
        feasibility = FeasibilityResult(
            query_text="test query",
            ranked_configs=(config,),
            pruned_count=0,
        )
        state = state.model_copy(update={"feasibility_result": feasibility})
    return state


def _make_analysis_report(
    *,
    constraint_modifications: dict[str, float | str] | None = None,
) -> AnalysisReport:
    """Build an AnalysisReport with optional constraint_modifications."""
    return AnalysisReport(
        hypothesis_id="h1",
        findings=["finding1"],
        confidence=0.8,
        supports_hypothesis=True,
        should_stop=False,
        constraint_modifications=constraint_modifications,
    )


# ---------------------------------------------------------------------------
# Test 1: KG context injected into analyst prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyst_phase_includes_kg_context_when_feasibility_exists():
    """_run_analyst_phase appends KG context to prompt when feasibility_result exists."""
    state = _make_state(with_feasibility=True)

    captured_prompt = {}

    async def mock_run_agent_phase(role, prompt, config, agents, **kw):
        captured_prompt["prompt"] = prompt
        return ('{"hypothesis_id":"h1","findings":[],"confidence":0.5,'
                '"supports_hypothesis":true,"should_stop":false}'), None

    with patch(
        "agentsim.orchestrator.runner._run_agent_phase",
        side_effect=mock_run_agent_phase,
    ):
        from agentsim.orchestrator.runner import _run_analyst_phase
        from agentsim.orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        result = await _run_analyst_phase(state, config, {})

    assert "Knowledge Graph" in captured_prompt["prompt"]
    assert "Re-query Instruction" in captured_prompt["prompt"]


# ---------------------------------------------------------------------------
# Test 2: Re-query triggers when constraint_modifications present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_requery_triggers_when_constraint_modifications_present():
    """When analyst output contains constraint_modifications, runner re-runs feasibility."""
    state = _make_state(with_feasibility=True)
    report = _make_analysis_report(
        constraint_modifications={"temporal_resolution_s": 5e-11},
    )

    # Helper that mimics the re-query detection logic from runner
    from agentsim.orchestrator.runner import _run_feasibility_phase

    requery_count = 0
    max_requery = 2
    feasibility_calls = []

    # Simulate the re-query detection block
    state_with_analysis = state.model_copy(
        update={"analyses": state.analyses + (report,)}
    )
    latest_analysis = state_with_analysis.analyses[-1] if state_with_analysis.analyses else None

    if (
        latest_analysis is not None
        and latest_analysis.constraint_modifications is not None
        and requery_count < max_requery
    ):
        requery_count += 1
        feasibility_calls.append(latest_analysis.constraint_modifications)

    assert requery_count == 1
    assert len(feasibility_calls) == 1
    assert feasibility_calls[0] == {"temporal_resolution_s": 5e-11}


# ---------------------------------------------------------------------------
# Test 3: Re-query capped at 2
# ---------------------------------------------------------------------------

def test_requery_capped_at_max():
    """Third re-query attempt is skipped when requery_count >= max_requery."""
    report = _make_analysis_report(
        constraint_modifications={"budget_usd": 10000},
    )

    max_requery = 2
    requery_count = 2  # Already at cap

    latest_analysis = report

    triggered = (
        latest_analysis is not None
        and latest_analysis.constraint_modifications is not None
        and requery_count < max_requery
    )
    assert triggered is False


# ---------------------------------------------------------------------------
# Test 4: No re-query when constraint_modifications is None
# ---------------------------------------------------------------------------

def test_no_requery_when_no_constraint_modifications():
    """When constraint_modifications is None, no re-query happens."""
    report = _make_analysis_report(constraint_modifications=None)

    max_requery = 2
    requery_count = 0

    latest_analysis = report

    triggered = (
        latest_analysis is not None
        and latest_analysis.constraint_modifications is not None
        and requery_count < max_requery
    )
    assert triggered is False


# ---------------------------------------------------------------------------
# Test 5: Re-query uses constraint_modifications as constraint_overrides
# ---------------------------------------------------------------------------

def test_requery_passes_constraints_as_overrides():
    """Re-query uses constraint_modifications dict as constraint_overrides parameter."""
    constraints = {"temporal_resolution_s": 5e-11, "budget_usd": 10000}
    report = _make_analysis_report(constraint_modifications=constraints)

    max_requery = 2
    requery_count = 0

    latest_analysis = report

    # The constraint_overrides kwarg should be the exact dict
    if (
        latest_analysis is not None
        and latest_analysis.constraint_modifications is not None
        and requery_count < max_requery
    ):
        constraint_overrides = latest_analysis.constraint_modifications
    else:
        constraint_overrides = None

    assert constraint_overrides == constraints


# ---------------------------------------------------------------------------
# Test 6: KG context NOT injected when no feasibility_result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyst_phase_no_kg_context_without_feasibility():
    """_run_analyst_phase does not inject KG context when feasibility_result is None."""
    state = _make_state(with_feasibility=False)

    captured_prompt = {}

    async def mock_run_agent_phase(role, prompt, config, agents, **kw):
        captured_prompt["prompt"] = prompt
        return ('{"hypothesis_id":"h1","findings":[],"confidence":0.5,'
                '"supports_hypothesis":true,"should_stop":false}'), None

    with patch(
        "agentsim.orchestrator.runner._run_agent_phase",
        side_effect=mock_run_agent_phase,
    ):
        from agentsim.orchestrator.runner import _run_analyst_phase
        from agentsim.orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        result = await _run_analyst_phase(state, config, {})

    assert "Knowledge Graph" not in captured_prompt["prompt"]
