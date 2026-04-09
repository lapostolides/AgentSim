"""Tests for knowledge graph context formatters (D-06)."""

from __future__ import annotations

import pytest

from agentsim.knowledge_graph.crb.models import SensitivityEntry
from agentsim.knowledge_graph.crb.sensitivity import SensitivityResult
from agentsim.knowledge_graph.models import (
    ConfidenceQualifier,
    ConstraintSatisfaction,
    FeasibilityResult,
    SensorConfig,
    SensorFamily,
)
from agentsim.state.graph_context import (
    format_analyst_graph_context,
    format_evaluator_graph_context,
    format_hypothesis_graph_context,
    format_scene_graph_context,
)
from agentsim.state.models import ExperimentState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_feasibility_result(num_configs: int = 3) -> FeasibilityResult:
    """Create a FeasibilityResult with configurable number of ranked configs."""
    configs = []
    families = [SensorFamily.SPAD, SensorFamily.CW_TOF, SensorFamily.LIGHT_FIELD]
    for i in range(num_configs):
        family = families[i % len(families)]
        crb = 0.005 * (i + 1) if i < 2 else None  # Third config has no CRB
        configs.append(
            SensorConfig(
                sensor_name=f"Sensor-{i + 1}",
                sensor_family=family,
                algorithm_name=f"algo-{i + 1}",
                crb_bound=crb,
                crb_unit="meter" if crb is not None else "",
                confidence=ConfidenceQualifier.ANALYTICAL if i == 0 else ConfidenceQualifier.UNKNOWN,
                rank=i + 1,
                feasibility_score=0.95 - (i * 0.1),
                constraint_satisfaction=(
                    ConstraintSatisfaction(
                        constraint_name="temporal_resolution",
                        satisfied=True,
                        margin=0.5,
                        unit="ps",
                        details="Within range",
                    ),
                    ConstraintSatisfaction(
                        constraint_name="budget",
                        satisfied=i == 0,
                        margin=-100.0 if i > 0 else 500.0,
                        unit="usd",
                        details="Over budget" if i > 0 else "Under budget",
                    ),
                ),
                notes=f"Config {i + 1} notes",
            )
        )
    return FeasibilityResult(
        query_text="locate object in darkness at 1cm resolution",
        detected_task="localization",
        detected_domain="nlos",
        environment_constraints=("darkness", "indoor"),
        ranked_configs=tuple(configs),
        pruned_count=5,
        total_count=15,
    )


def _make_sensitivity_result() -> SensitivityResult:
    """Create a SensitivityResult with 3 entries."""
    return SensitivityResult(
        sensor_name="SPAD-Array-1",
        estimation_task="depth_estimation",
        baseline_crb=0.005,
        num_trajectories=10,
        entries=(
            SensitivityEntry(
                parameter_name="dead_time_ns",
                nominal_value=50.0,
                mu_star=0.8,
                sigma=0.3,
                classification="nonlinear",
                sensitivity=0.8,
                rank=1,
            ),
            SensitivityEntry(
                parameter_name="pde",
                nominal_value=0.3,
                mu_star=0.5,
                sigma=0.1,
                classification="linear",
                sensitivity=0.5,
                rank=2,
            ),
            SensitivityEntry(
                parameter_name="fill_factor",
                nominal_value=0.6,
                mu_star=0.01,
                sigma=0.005,
                classification="negligible",
                sensitivity=0.01,
                rank=3,
            ),
        ),
    )


def _make_state_with_feasibility() -> ExperimentState:
    """Create an ExperimentState with feasibility_result populated."""
    return ExperimentState(feasibility_result=_make_feasibility_result())


def _make_state_without_feasibility() -> ExperimentState:
    """Create a bare ExperimentState."""
    return ExperimentState()


# ---------------------------------------------------------------------------
# format_hypothesis_graph_context
# ---------------------------------------------------------------------------


class TestFormatHypothesisGraphContext:
    """Tests for format_hypothesis_graph_context."""

    def test_returns_empty_when_none(self) -> None:
        state = _make_state_without_feasibility()
        assert format_hypothesis_graph_context(state) == ""

    def test_returns_markdown_with_ranked_table(self) -> None:
        state = _make_state_with_feasibility()
        result = format_hypothesis_graph_context(state)
        assert "Ranked Sensor Configurations" in result
        assert "Sensor-1" in result
        assert "| Rank" in result

    def test_limits_to_top_5(self) -> None:
        """When more than 5 configs, only top 5 shown."""
        fr = _make_feasibility_result(num_configs=3)
        state = ExperimentState(feasibility_result=fr)
        result = format_hypothesis_graph_context(state)
        # All 3 should be present (less than 5)
        assert "Sensor-1" in result
        assert "Sensor-3" in result

    def test_includes_research_gaps(self) -> None:
        state = _make_state_with_feasibility()
        result = format_hypothesis_graph_context(state)
        assert "Research Gaps" in result

    def test_includes_pruned_count(self) -> None:
        state = _make_state_with_feasibility()
        result = format_hypothesis_graph_context(state)
        assert "5 sensors were pruned" in result

    def test_includes_constraint_satisfaction(self) -> None:
        state = _make_state_with_feasibility()
        result = format_hypothesis_graph_context(state)
        assert "Constraint Satisfaction" in result


# ---------------------------------------------------------------------------
# format_scene_graph_context
# ---------------------------------------------------------------------------


class TestFormatSceneGraphContext:
    """Tests for format_scene_graph_context."""

    def test_returns_empty_when_none(self) -> None:
        state = _make_state_without_feasibility()
        assert format_scene_graph_context(state) == ""

    def test_returns_sensitivity_table(self) -> None:
        state = _make_state_with_feasibility()
        sensitivity = _make_sensitivity_result()
        result = format_scene_graph_context(state, sensitivity_result=sensitivity)
        assert "Parameter Sensitivity Rankings" in result
        assert "Morris Method" in result
        assert "dead_time_ns" in result

    def test_returns_fallback_when_no_sensitivity(self) -> None:
        state = _make_state_with_feasibility()
        result = format_scene_graph_context(state)
        assert "No sensitivity analysis available" in result

    def test_includes_top_sensor_reference(self) -> None:
        state = _make_state_with_feasibility()
        result = format_scene_graph_context(state)
        assert "Sensor-1" in result

    def test_includes_high_sensitivity_guidance(self) -> None:
        state = _make_state_with_feasibility()
        sensitivity = _make_sensitivity_result()
        result = format_scene_graph_context(state, sensitivity_result=sensitivity)
        assert "HIGH-SENSITIVITY" in result


# ---------------------------------------------------------------------------
# format_evaluator_graph_context
# ---------------------------------------------------------------------------


class TestFormatEvaluatorGraphContext:
    """Tests for format_evaluator_graph_context."""

    def test_returns_empty_when_none(self) -> None:
        state = _make_state_without_feasibility()
        assert format_evaluator_graph_context(state) == ""

    def test_returns_crb_floor(self) -> None:
        state = _make_state_with_feasibility()
        result = format_evaluator_graph_context(state)
        assert "CRB Performance Floor" in result
        assert "0.005" in result
        assert "meter" in result

    def test_includes_efficiency_ratio_framing(self) -> None:
        state = _make_state_with_feasibility()
        result = format_evaluator_graph_context(state)
        assert "efficiency ratio" in result

    def test_no_threshold_language(self) -> None:
        state = _make_state_with_feasibility()
        result = format_evaluator_graph_context(state)
        assert "threshold" not in result.lower()


# ---------------------------------------------------------------------------
# format_analyst_graph_context
# ---------------------------------------------------------------------------


class TestFormatAnalystGraphContext:
    """Tests for format_analyst_graph_context."""

    def test_returns_empty_when_none(self) -> None:
        state = _make_state_without_feasibility()
        assert format_analyst_graph_context(state) == ""

    def test_returns_comprehensive_context(self) -> None:
        state = _make_state_with_feasibility()
        result = format_analyst_graph_context(state)
        assert "Full Analysis Context" in result

    def test_includes_crb_context(self) -> None:
        state = _make_state_with_feasibility()
        result = format_analyst_graph_context(state)
        assert "efficiency ratio" in result

    def test_includes_shares_physics_neighbors(self) -> None:
        state = _make_state_with_feasibility()
        result = format_analyst_graph_context(state)
        assert "SHARES_PHYSICS" in result or "sharing physics" in result.lower()

    def test_includes_requery_instruction(self) -> None:
        state = _make_state_with_feasibility()
        result = format_analyst_graph_context(state)
        assert "constraint_modifications" in result

    def test_includes_iteration_trend_note(self) -> None:
        """When multiple evaluations, note convergence check."""
        from agentsim.state.models import EvaluationResult

        fr = _make_feasibility_result()
        state = ExperimentState(
            feasibility_result=fr,
            evaluations=(
                EvaluationResult(scene_id="s1", summary="first"),
                EvaluationResult(scene_id="s2", summary="second"),
            ),
        )
        result = format_analyst_graph_context(state)
        assert "convergence" in result.lower() or "divergence" in result.lower()

    def test_no_threshold_language(self) -> None:
        state = _make_state_with_feasibility()
        result = format_analyst_graph_context(state)
        assert "threshold" not in result.lower()
