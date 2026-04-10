"""Integration tests for optimization pipeline wiring (Phase 11 Plan 04).

Tests ExperimentState extension, transitions, runner phase, CLI scope,
and graph context formatters with Pareto front information.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentsim.knowledge_graph.models import (
    ConfidenceQualifier,
    FeasibilityResult,
    SensorConfig,
    SensorFamily,
)
from agentsim.knowledge_graph.optimizer.models import (
    BOMetadata,
    CostWeights,
    FamilyOptimizationResult,
    OptimizationResult,
    ParetoPoint,
)
from agentsim.orchestrator.config import OrchestratorConfig
from agentsim.state.models import ExperimentState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_pareto_point(
    name: str = "sensor_a",
    family: SensorFamily = SensorFamily.SPAD,
    crb: float = 0.01,
    cost: float = 5000.0,
) -> ParetoPoint:
    return ParetoPoint(
        sensor_name=name,
        family=family,
        parameter_values={"pixel_count": 512.0, "gate_width_ns": 1.0},
        crb_bound=crb,
        crb_unit="m",
        operational_cost=cost,
        constraint_margin=0.1,
        confidence=ConfidenceQualifier.ANALYTICAL,
    )


def _make_optimization_result(scope: str = "medium") -> OptimizationResult:
    points = (
        _make_pareto_point("sensor_a", crb=0.01, cost=5000.0),
        _make_pareto_point("sensor_b", crb=0.05, cost=2000.0),
        _make_pareto_point("sensor_c", crb=0.03, cost=3000.0),
        _make_pareto_point("sensor_d", crb=0.08, cost=1000.0),
    )
    family_result = FamilyOptimizationResult(
        family=SensorFamily.SPAD,
        pareto_front=points,
        bo_metadata=BOMetadata(
            evaluations=20,
            converged=True,
            final_acquisition_improvement=0.001,
            computation_time_s=1.5,
        ),
    )
    return OptimizationResult(
        family_results=(family_result,),
        scope=scope,
        total_evaluations=20,
        total_computation_time_s=1.5,
    )


def _make_feasibility_result() -> FeasibilityResult:
    config = SensorConfig(
        sensor_name="test_spad",
        sensor_family=SensorFamily.SPAD,
        algorithm_name="matched_filter",
        feasibility_score=0.85,
        rank=1,
        confidence=ConfidenceQualifier.ANALYTICAL,
        constraint_satisfaction=(),
        crb_bound=0.01,
        crb_unit="m",
        notes="",
    )
    return FeasibilityResult(
        query_text="test hypothesis",
        ranked_configs=(config,),
        pruned_count=2,
    )


def _make_empty_feasibility() -> FeasibilityResult:
    return FeasibilityResult(
        query_text="test",
        ranked_configs=(),
        pruned_count=0,
    )


# ===========================================================================
# Task 1: ExperimentState, transitions, config, runner, CLI
# ===========================================================================


class TestExperimentStateOptimization:
    """ExperimentState extension with optimization_result field."""

    def test_default_optimization_result_is_none(self) -> None:
        state = ExperimentState()
        assert state.optimization_result is None

    def test_construct_with_optimization_result(self) -> None:
        opt = _make_optimization_result()
        state = ExperimentState(optimization_result=opt)
        assert state.optimization_result is not None
        assert state.optimization_result.total_evaluations == 20

    def test_round_trip_json(self) -> None:
        opt = _make_optimization_result()
        state = ExperimentState(optimization_result=opt)
        json_str = state.model_dump_json()
        restored = ExperimentState.model_validate_json(json_str)
        assert restored.optimization_result is not None
        assert restored.optimization_result.scope == "medium"
        assert len(restored.optimization_result.family_results) == 1


class TestSetOptimizationResultTransition:
    """set_optimization_result transition function."""

    def test_returns_new_state(self) -> None:
        from agentsim.state.transitions import set_optimization_result

        state = ExperimentState()
        opt = _make_optimization_result()
        new_state = set_optimization_result(state, opt)
        assert new_state is not state
        assert new_state.optimization_result is not None
        assert state.optimization_result is None  # original unchanged


class TestOrchestratorConfigScope:
    """OrchestratorConfig scope field."""

    def test_default_scope_is_medium(self) -> None:
        config = OrchestratorConfig()
        assert config.scope == "medium"

    def test_accepts_wide(self) -> None:
        config = OrchestratorConfig(scope="wide")
        assert config.scope == "wide"

    def test_accepts_narrow(self) -> None:
        config = OrchestratorConfig(scope="narrow")
        assert config.scope == "narrow"


class TestRunOptimizationPhase:
    """_run_optimization_phase pipeline phase."""

    @pytest.mark.asyncio
    async def test_skips_when_no_feasibility(self) -> None:
        from agentsim.orchestrator.runner import _run_optimization_phase

        state = ExperimentState()
        config = OrchestratorConfig()
        result = await _run_optimization_phase(state, config)
        assert result.optimization_result is None

    @pytest.mark.asyncio
    async def test_skips_when_empty_ranked_configs(self) -> None:
        from agentsim.orchestrator.runner import _run_optimization_phase

        empty_feasibility = _make_empty_feasibility()
        state = ExperimentState(feasibility_result=empty_feasibility)
        config = OrchestratorConfig()
        result = await _run_optimization_phase(state, config)
        assert result.optimization_result is None

    @pytest.mark.asyncio
    async def test_populates_optimization_result(self) -> None:
        from agentsim.orchestrator.runner import _run_optimization_phase

        feasibility = _make_feasibility_result()
        state = ExperimentState(
            feasibility_result=feasibility,
            raw_hypothesis="test hypothesis",
        )
        config = OrchestratorConfig()
        mock_result = _make_optimization_result()

        with patch(
            "agentsim.knowledge_graph.optimizer.optimizer.optimize_sensors",
            return_value=mock_result,
        ):
            result = await _run_optimization_phase(state, config)

        assert result.optimization_result is not None
        assert result.optimization_result.total_evaluations == 20

    @pytest.mark.asyncio
    async def test_scope_auto_override_for_comparison(self) -> None:
        from agentsim.orchestrator.runner import _run_optimization_phase

        feasibility = _make_feasibility_result()
        state = ExperimentState(
            feasibility_result=feasibility,
            raw_hypothesis="compare sensor families for NLOS",
        )
        config = OrchestratorConfig(scope="medium")  # default
        mock_result = _make_optimization_result(scope="wide")

        with patch(
            "agentsim.knowledge_graph.optimizer.optimizer.optimize_sensors",
            return_value=mock_result,
        ) as mock_opt:
            await _run_optimization_phase(state, config)
            # detect_scope should return "wide" for comparison language
            call_kwargs = mock_opt.call_args
            assert call_kwargs.kwargs.get("scope") == "wide" or call_kwargs[1].get("scope") == "wide"


class TestCliScopeFlag:
    """--scope CLI flag flows to OrchestratorConfig."""

    def test_scope_in_run_command(self) -> None:
        from click.testing import CliRunner

        from agentsim.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert "--scope" in result.output
        assert "wide" in result.output
        assert "narrow" in result.output


# ===========================================================================
# Task 2: Graph context formatters for Pareto front
# ===========================================================================


class TestScopeFilteredOptimization:
    """_scope_filtered_optimization helper."""

    def test_applies_filter_by_scope(self) -> None:
        from agentsim.state.graph_context import _scope_filtered_optimization

        opt = _make_optimization_result(scope="narrow")
        filtered = _scope_filtered_optimization(opt)
        # narrow scope -> 1 config per family
        for fr in filtered.family_results:
            assert len(fr.pareto_front) <= 1


class TestParetoFrontSection:
    """_pareto_front_section rendering."""

    def test_full_detail_renders_all_points(self) -> None:
        from agentsim.state.graph_context import _pareto_front_section

        opt = _make_optimization_result()
        lines = _pareto_front_section(opt, detail_level="full")
        text = "\n".join(lines)
        # All 4 points rendered
        assert "sensor_a" in text
        assert "sensor_b" in text
        assert "sensor_c" in text
        assert "sensor_d" in text

    def test_summary_detail_limits_to_3(self) -> None:
        from agentsim.state.graph_context import _pareto_front_section

        opt = _make_optimization_result()
        lines = _pareto_front_section(opt, detail_level="summary")
        text = "\n".join(lines)
        # At most 3 shown, rest indicated
        assert "more Pareto-optimal" in text


class TestAnalystFormatterFull:
    """format_analyst_graph_context passes FULL unfiltered Pareto front."""

    def test_analyst_includes_pareto(self) -> None:
        from agentsim.state.graph_context import format_analyst_graph_context

        state = ExperimentState(
            feasibility_result=_make_feasibility_result(),
            optimization_result=_make_optimization_result(),
        )
        text = format_analyst_graph_context(state)
        assert "Full Pareto Analysis" in text
        # All 4 points visible (no scope filtering)
        assert "sensor_a" in text
        assert "sensor_d" in text

    def test_analyst_no_optimization_unchanged(self) -> None:
        from agentsim.state.graph_context import format_analyst_graph_context

        state = ExperimentState(feasibility_result=_make_feasibility_result())
        text = format_analyst_graph_context(state)
        assert "Pareto" not in text


class TestNonAnalystFormattersFiltered:
    """Non-analyst formatters apply filter_by_scope."""

    def test_hypothesis_applies_scope_filter(self) -> None:
        from agentsim.state.graph_context import format_hypothesis_graph_context

        state = ExperimentState(
            feasibility_result=_make_feasibility_result(),
            optimization_result=_make_optimization_result(),
        )
        text = format_hypothesis_graph_context(state)
        assert "Pareto-Optimal Operating Points" in text

    def test_scene_applies_scope_filter(self) -> None:
        from agentsim.state.graph_context import format_scene_graph_context

        state = ExperimentState(
            feasibility_result=_make_feasibility_result(),
            optimization_result=_make_optimization_result(),
        )
        text = format_scene_graph_context(state)
        assert "Optimized Parameter Settings" in text

    def test_evaluator_applies_scope_filter(self) -> None:
        from agentsim.state.graph_context import format_evaluator_graph_context

        state = ExperimentState(
            feasibility_result=_make_feasibility_result(),
            optimization_result=_make_optimization_result(),
        )
        text = format_evaluator_graph_context(state)
        assert "Optimized CRB" in text

    def test_hypothesis_no_optimization_unchanged(self) -> None:
        from agentsim.state.graph_context import format_hypothesis_graph_context

        state = ExperimentState(feasibility_result=_make_feasibility_result())
        text = format_hypothesis_graph_context(state)
        assert "Pareto" not in text

    def test_scene_no_optimization_unchanged(self) -> None:
        from agentsim.state.graph_context import format_scene_graph_context

        state = ExperimentState(feasibility_result=_make_feasibility_result())
        text = format_scene_graph_context(state)
        assert "Optimized" not in text

    def test_evaluator_no_optimization_unchanged(self) -> None:
        from agentsim.state.graph_context import format_evaluator_graph_context

        state = ExperimentState(feasibility_result=_make_feasibility_result())
        text = format_evaluator_graph_context(state)
        assert "Optimized" not in text
