"""Integration tests for physics-space reasoning wiring.

Tests the connection between reasoning engine outputs and the pipeline:
- PhysicsRecommendation model on ExperimentState
- set_physics_recommendation transition
- format_optimizer_recommendation context formatter
- _route_reasoning_query advisor routing
- Scene agent prompt contains optimizer recommendation after domain_context rebuild
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentsim.physics.reasoning.models import (
    ComputedValue,
    ExplorerResult,
    NovelParameter,
    OptimizerResult,
    ScoredSetup,
)


# ---------------------------------------------------------------------------
# PhysicsRecommendation model tests
# ---------------------------------------------------------------------------


class TestPhysicsRecommendation:
    """Test PhysicsRecommendation model on ExperimentState."""

    def test_physics_recommendation_has_optimizer_result(self) -> None:
        from agentsim.state.models import PhysicsRecommendation

        rec = PhysicsRecommendation(
            optimizer_result=OptimizerResult(paradigm="test"),
        )
        assert rec.optimizer_result is not None
        assert rec.optimizer_result.paradigm == "test"

    def test_physics_recommendation_has_explorer_result(self) -> None:
        from agentsim.state.models import PhysicsRecommendation

        rec = PhysicsRecommendation(
            explorer_result=ExplorerResult(paradigm="test"),
        )
        assert rec.explorer_result is not None
        assert rec.explorer_result.paradigm == "test"

    def test_physics_recommendation_defaults_none(self) -> None:
        from agentsim.state.models import PhysicsRecommendation

        rec = PhysicsRecommendation()
        assert rec.optimizer_result is None
        assert rec.explorer_result is None

    def test_experiment_state_has_physics_recommendation(self) -> None:
        from agentsim.state.models import ExperimentState

        state = ExperimentState()
        assert state.physics_recommendation is None

    def test_experiment_state_accepts_physics_recommendation(self) -> None:
        from agentsim.state.models import ExperimentState, PhysicsRecommendation

        rec = PhysicsRecommendation(
            optimizer_result=OptimizerResult(paradigm="nlos"),
        )
        state = ExperimentState(physics_recommendation=rec)
        assert state.physics_recommendation is not None
        assert state.physics_recommendation.optimizer_result is not None


# ---------------------------------------------------------------------------
# set_physics_recommendation transition tests
# ---------------------------------------------------------------------------


class TestSetPhysicsRecommendation:
    """Test set_physics_recommendation transition."""

    def test_returns_new_state_with_recommendation(self) -> None:
        from agentsim.state.models import ExperimentState, PhysicsRecommendation
        from agentsim.state.transitions import set_physics_recommendation

        state = ExperimentState()
        rec = PhysicsRecommendation(
            optimizer_result=OptimizerResult(paradigm="nlos"),
        )
        new_state = set_physics_recommendation(state, rec)
        assert new_state is not state
        assert new_state.physics_recommendation is rec

    def test_does_not_change_status(self) -> None:
        from agentsim.state.models import (
            ExperimentState,
            ExperimentStatus,
            PhysicsRecommendation,
        )
        from agentsim.state.transitions import set_physics_recommendation

        state = ExperimentState(status=ExperimentStatus.HYPOTHESIS_READY)
        rec = PhysicsRecommendation()
        new_state = set_physics_recommendation(state, rec)
        assert new_state.status == ExperimentStatus.HYPOTHESIS_READY

    def test_preserves_other_fields(self) -> None:
        from agentsim.state.models import ExperimentState, PhysicsRecommendation
        from agentsim.state.transitions import set_physics_recommendation

        state = ExperimentState(raw_hypothesis="test hypothesis")
        rec = PhysicsRecommendation()
        new_state = set_physics_recommendation(state, rec)
        assert new_state.raw_hypothesis == "test hypothesis"


# ---------------------------------------------------------------------------
# format_optimizer_recommendation tests
# ---------------------------------------------------------------------------


class TestFormatOptimizerRecommendation:
    """Test format_optimizer_recommendation context formatter."""

    def test_two_setups_produces_markdown_with_both(self) -> None:
        from agentsim.physics.context import format_optimizer_recommendation

        result = OptimizerResult(
            paradigm="nlos",
            setups=(
                ScoredSetup(
                    sensor_class="spad_array",
                    algorithm="lct",
                    score=5.0,
                    computed_metrics=(
                        ComputedValue(
                            parameter="temporal_resolution",
                            value=50.0,
                            relationship="linear",
                            source_tf_formula="t = d/c",
                        ),
                    ),
                ),
                ScoredSetup(
                    sensor_class="streak_camera",
                    algorithm="fk_migration",
                    score=3.0,
                ),
            ),
        )
        text = format_optimizer_recommendation(result)
        assert "spad_array" in text
        assert "lct" in text
        assert "streak_camera" in text
        assert "fk_migration" in text

    def test_empty_setups_returns_empty_string(self) -> None:
        from agentsim.physics.context import format_optimizer_recommendation

        result = OptimizerResult(paradigm="nlos", setups=())
        text = format_optimizer_recommendation(result)
        assert text == ""

    def test_contains_recommended_setup_header(self) -> None:
        from agentsim.physics.context import format_optimizer_recommendation

        result = OptimizerResult(
            paradigm="nlos",
            setups=(
                ScoredSetup(
                    sensor_class="spad",
                    algorithm="lct",
                    score=1.0,
                ),
            ),
        )
        text = format_optimizer_recommendation(result)
        assert "Recommended Setup" in text

    def test_includes_computed_metrics(self) -> None:
        from agentsim.physics.context import format_optimizer_recommendation

        result = OptimizerResult(
            paradigm="nlos",
            setups=(
                ScoredSetup(
                    sensor_class="spad",
                    algorithm="lct",
                    score=1.0,
                    computed_metrics=(
                        ComputedValue(
                            parameter="temporal_resolution",
                            value=50.0,
                            relationship="linear",
                            source_tf_formula="t = d/c",
                        ),
                    ),
                ),
            ),
        )
        text = format_optimizer_recommendation(result)
        assert "temporal_resolution" in text
        assert "50" in text


# ---------------------------------------------------------------------------
# _route_reasoning_query routing tests
# ---------------------------------------------------------------------------


class TestRouteReasoningQuery:
    """Test _route_reasoning_query advisor routing."""

    def _make_query(self, query_type: str) -> "PhysicsQuery":
        from agentsim.physics.models import PhysicsQuery

        return PhysicsQuery(
            query_type=query_type,
            context="test",
            parameters={"distance_m": 1.0, "time_ps": 100.0},
        )

    @patch("agentsim.physics.reasoning.optimize_setup")
    def test_optimize_setup_routes_to_optimize(self, mock_opt: MagicMock) -> None:
        from agentsim.physics.consultation import _route_reasoning_query

        mock_opt.return_value = OptimizerResult(paradigm="nlos")
        query = self._make_query("optimize_setup")
        mock_bundle = MagicMock()
        mock_paradigm = MagicMock()
        result = _route_reasoning_query(query, mock_bundle, mock_paradigm)
        mock_opt.assert_called_once()
        assert isinstance(result, OptimizerResult)

    @patch("agentsim.physics.reasoning.optimize_setup")
    def test_sensor_query_routes_to_optimize(self, mock_opt: MagicMock) -> None:
        from agentsim.physics.consultation import _route_reasoning_query

        mock_opt.return_value = OptimizerResult(paradigm="nlos")
        query = self._make_query("sensor_query")
        mock_bundle = MagicMock()
        mock_paradigm = MagicMock()
        result = _route_reasoning_query(query, mock_bundle, mock_paradigm)
        mock_opt.assert_called_once()
        assert isinstance(result, OptimizerResult)

    @patch("agentsim.physics.reasoning.optimize_setup")
    def test_algorithm_query_routes_to_optimize(self, mock_opt: MagicMock) -> None:
        from agentsim.physics.consultation import _route_reasoning_query

        mock_opt.return_value = OptimizerResult(paradigm="nlos")
        query = self._make_query("algorithm_query")
        mock_bundle = MagicMock()
        mock_paradigm = MagicMock()
        result = _route_reasoning_query(query, mock_bundle, mock_paradigm)
        mock_opt.assert_called_once()
        assert isinstance(result, OptimizerResult)

    @patch("agentsim.physics.reasoning.find_novel_regions")
    def test_explore_novel_routes_to_explorer(self, mock_exp: MagicMock) -> None:
        from agentsim.physics.consultation import _route_reasoning_query

        mock_exp.return_value = ExplorerResult(paradigm="nlos")
        query = self._make_query("explore_novel")
        mock_paradigm = MagicMock()
        result = _route_reasoning_query(query, None, mock_paradigm)
        mock_exp.assert_called_once()
        assert isinstance(result, ExplorerResult)

    def test_unknown_query_type_returns_none(self) -> None:
        from agentsim.physics.consultation import _route_reasoning_query

        query = self._make_query("unknown_type")
        mock_paradigm = MagicMock()
        result = _route_reasoning_query(query, None, mock_paradigm)
        assert result is None

    def test_none_paradigm_returns_none(self) -> None:
        from agentsim.physics.consultation import _route_reasoning_query

        query = self._make_query("optimize_setup")
        result = _route_reasoning_query(query, MagicMock(), None)
        assert result is None


# ---------------------------------------------------------------------------
# Scene agent prompt integration test
# ---------------------------------------------------------------------------


class TestSceneAgentPromptContainsRecommendation:
    """Verify scene agent prompt includes optimizer output after domain_context rebuild."""

    def test_scene_agent_prompt_contains_optimizer_recommendation(self) -> None:
        """After optimizer runs, rebuilt agent registry scene agent must include 'Recommended Setup'."""
        from agentsim.orchestrator.agent_registry import build_agent_registry
        from agentsim.physics.context import format_optimizer_recommendation

        # 1. Create a domain_context dict with a base scene string
        domain_context: dict[str, str] = {
            "hypothesis": "test hypothesis context",
            "analyst": "test analyst context",
            "advisor": "test advisor context",
            "scene": "## Base Scene Context\nSome physics constraints.",
        }

        # 2. Create an OptimizerResult with at least one ScoredSetup
        optimizer_result = OptimizerResult(
            paradigm="nlos",
            setups=(
                ScoredSetup(
                    sensor_class="spad_array",
                    algorithm="lct",
                    score=5.0,
                    computed_metrics=(
                        ComputedValue(
                            parameter="temporal_resolution",
                            value=50.0,
                            relationship="linear",
                            source_tf_formula="t = d/c",
                        ),
                    ),
                ),
            ),
        )

        # 3. Call format_optimizer_recommendation to get opt_text
        opt_text = format_optimizer_recommendation(optimizer_result)
        assert opt_text  # Should not be empty

        # 4. Rebuild domain_context immutably
        updated_context = {
            **domain_context,
            "scene": domain_context["scene"] + "\n" + opt_text,
        }

        # 5. Call build_agent_registry with the updated domain_context
        agents = build_agent_registry(domain_context=updated_context)

        # 6. Assert the scene agent definition's prompt contains "Recommended Setup"
        scene_agent = agents["scene"]
        assert "Recommended Setup" in scene_agent.prompt

        # 7. Assert the scene agent definition's prompt contains the sensor_class name
        assert "spad_array" in scene_agent.prompt
        assert "lct" in scene_agent.prompt

    def test_original_domain_context_not_mutated(self) -> None:
        """Rebuilding domain_context must not mutate the original dict."""
        from agentsim.physics.context import format_optimizer_recommendation

        original_context: dict[str, str] = {
            "scene": "base scene text",
        }
        original_scene = original_context["scene"]

        result = OptimizerResult(
            paradigm="nlos",
            setups=(
                ScoredSetup(sensor_class="spad", algorithm="lct", score=1.0),
            ),
        )
        opt_text = format_optimizer_recommendation(result)

        # Rebuild immutably
        _updated = {**original_context, "scene": original_context["scene"] + "\n" + opt_text}

        # Original should be unchanged
        assert original_context["scene"] == original_scene
