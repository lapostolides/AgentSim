"""Tests for _run_feasibility_phase in the orchestrator runner.

Validates that the feasibility phase:
- Skips gracefully when Neo4j is unavailable
- Stores FeasibilityResult when graph is available
- Uses hypothesis text as the task string
- Accepts optional constraint overrides
- Catches query engine exceptions and returns state unchanged
- Logs appropriate warnings
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentsim.orchestrator.config import OrchestratorConfig
from agentsim.state.transitions import start_experiment


# We import the function under test lazily since it may not exist yet
def _get_run_feasibility_phase():
    from agentsim.orchestrator.runner import _run_feasibility_phase
    return _run_feasibility_phase


@pytest.fixture()
def base_state():
    """Create a minimal ExperimentState with a hypothesis."""
    return start_experiment("detect objects behind wall using SPAD sensor")


@pytest.fixture()
def config():
    """Create a default OrchestratorConfig."""
    return OrchestratorConfig()


@pytest.fixture()
def mock_feasibility_result():
    """Create a mock FeasibilityResult."""
    from agentsim.knowledge_graph.models import FeasibilityResult

    return FeasibilityResult(
        query_text="detect objects behind wall using SPAD sensor",
        environment_constraints=(),
        ranked_configs=(),
        pruned_count=0,
        total_count=5,
        computation_time_s=0.1,
    )


@pytest.mark.asyncio()
async def test_skips_when_graph_unavailable(base_state, config):
    """Test 1: returns state unchanged when is_graph_available returns False."""
    run_phase = _get_run_feasibility_phase()

    with patch(
        "agentsim.knowledge_graph.degradation.is_graph_available", return_value=False
    ):
        result = await run_phase(base_state, config)

    assert result is base_state
    assert result.feasibility_result is None


@pytest.mark.asyncio()
async def test_stores_feasibility_result_when_available(
    base_state, config, mock_feasibility_result
):
    """Test 2: returns state with feasibility_result when graph is available."""
    run_phase = _get_run_feasibility_phase()

    mock_engine = MagicMock()
    mock_engine.query.return_value = mock_feasibility_result

    with (
        patch(
            "agentsim.knowledge_graph.degradation.is_graph_available",
            return_value=True,
        ),
        patch(
            "agentsim.orchestrator.runner.GraphClient",
            return_value=MagicMock(),
        ),
        patch(
            "agentsim.orchestrator.runner.FeasibilityQueryEngine",
            return_value=mock_engine,
        ),
    ):
        result = await run_phase(base_state, config)

    assert result.feasibility_result is not None
    assert result.feasibility_result.total_count == 5


@pytest.mark.asyncio()
async def test_uses_hypothesis_as_task(base_state, config, mock_feasibility_result):
    """Test 3: uses hypothesis_text as task string for query."""
    run_phase = _get_run_feasibility_phase()

    mock_engine = MagicMock()
    mock_engine.query.return_value = mock_feasibility_result

    with (
        patch(
            "agentsim.knowledge_graph.degradation.is_graph_available",
            return_value=True,
        ),
        patch(
            "agentsim.orchestrator.runner.GraphClient",
            return_value=MagicMock(),
        ),
        patch(
            "agentsim.orchestrator.runner.FeasibilityQueryEngine",
            return_value=mock_engine,
        ),
    ):
        await run_phase(base_state, config)

    mock_engine.query.assert_called_once()
    call_kwargs = mock_engine.query.call_args
    assert call_kwargs.kwargs.get("task") == "detect objects behind wall using SPAD sensor" or \
        call_kwargs.args[0] == "detect objects behind wall using SPAD sensor" if call_kwargs.args else False


@pytest.mark.asyncio()
async def test_accepts_constraint_overrides(
    base_state, config, mock_feasibility_result
):
    """Test 4: accepts optional constraint_overrides dict."""
    run_phase = _get_run_feasibility_phase()

    mock_engine = MagicMock()
    mock_engine.query.return_value = mock_feasibility_result

    overrides = {"max_range_m": 50.0, "min_resolution_m": 0.01}

    with (
        patch(
            "agentsim.knowledge_graph.degradation.is_graph_available",
            return_value=True,
        ),
        patch(
            "agentsim.orchestrator.runner.GraphClient",
            return_value=MagicMock(),
        ),
        patch(
            "agentsim.orchestrator.runner.FeasibilityQueryEngine",
            return_value=mock_engine,
        ),
    ):
        result = await run_phase(base_state, config, constraint_overrides=overrides)

    assert result.feasibility_result is not None
    call_kwargs = mock_engine.query.call_args
    assert call_kwargs.kwargs.get("constraints") == overrides or \
        (len(call_kwargs.args) > 1 and call_kwargs.args[1] == overrides)


@pytest.mark.asyncio()
async def test_catches_query_exceptions(base_state, config):
    """Test 5: catches exceptions from query engine and returns state unchanged."""
    run_phase = _get_run_feasibility_phase()

    mock_engine = MagicMock()
    mock_engine.query.side_effect = RuntimeError("Neo4j connection lost")

    with (
        patch(
            "agentsim.knowledge_graph.degradation.is_graph_available",
            return_value=True,
        ),
        patch(
            "agentsim.orchestrator.runner.GraphClient",
            return_value=MagicMock(),
        ),
        patch(
            "agentsim.orchestrator.runner.FeasibilityQueryEngine",
            return_value=mock_engine,
        ),
    ):
        result = await run_phase(base_state, config)

    assert result.feasibility_result is None


@pytest.mark.asyncio()
async def test_logs_warning_when_graph_unavailable(base_state, config):
    """Test 6: logs warning 'feasibility_phase_skipped' when graph unavailable."""
    run_phase = _get_run_feasibility_phase()

    with (
        patch(
            "agentsim.knowledge_graph.degradation.is_graph_available",
            return_value=False,
        ),
        patch("agentsim.orchestrator.runner.logger") as mock_logger,
    ):
        await run_phase(base_state, config)

    mock_logger.warning.assert_called_once_with(
        "feasibility_phase_skipped", reason="graph_unavailable"
    )
