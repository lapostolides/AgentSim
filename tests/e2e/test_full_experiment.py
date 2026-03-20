"""E2E tests for the full experiment pipeline.

These tests verify the complete state flow through the experiment
lifecycle WITHOUT making real API calls. They test that all the
pieces fit together correctly.
"""

from agentsim.orchestrator.agent_registry import build_agent_registry
from agentsim.state.models import (
    AnalysisReport,
    AvailablePackage,
    EnvironmentInfo,
    EvaluationResult,
    ExecutionResult,
    ExperimentPlan,
    ExperimentStatus,
    Hypothesis,
    LiteratureContext,
    LiteratureEntry,
    LiteratureValidation,
    ParameterSpec,
    SceneSpec,
)
from agentsim.state.serialization import deserialize_state, serialize_state
from agentsim.state.transitions import (
    add_analysis,
    add_evaluation,
    add_execution_result,
    add_hypothesis,
    add_plan,
    add_scenes,
    set_environment,
    set_literature_context,
    set_literature_validation,
    start_experiment,
)


class TestFullExperimentLifecycle:
    """Simulate a complete experiment without API calls.

    This walks through every state transition that would happen
    in a real experiment, verifying state integrity throughout.
    """

    def test_complete_experiment_flow(self, sample_environment):
        # 1. User starts experiment
        state = start_experiment(
            "Does increasing surface roughness reduce NLOS reconstruction accuracy?",
            file_paths=[],
        )
        assert state.status == ExperimentStatus.INITIALIZED

        # 2. Environment discovered
        state = set_environment(state, sample_environment)
        assert state.environment is not None

        # 3. Agent registry built
        agents = build_agent_registry(state.environment)
        assert "literature_scout" in agents
        assert "hypothesis" in agents
        assert "scene" in agents
        assert "executor" in agents
        assert "evaluator" in agents
        assert "analyst" in agents
        assert "literature_validator" in agents

        # 3b. Literature scout output
        lit_context = LiteratureContext(
            entries=(
                LiteratureEntry(
                    title="NLOS Imaging Under Surface Roughness",
                    authors=("Smith, J.",),
                    year=2021,
                    key_findings=("Roughness > 0.5 degrades PSNR by 30%",),
                    relevance="Directly relevant prior work",
                ),
            ),
            summary="Prior work shows roughness degrades NLOS reconstruction.",
            open_questions=("Non-linear effects at extreme roughness?",),
            methodology_notes="Standard: PSNR, SSIM metrics, 5+ roughness levels",
        )
        state = set_literature_context(state, lit_context)
        assert state.status == ExperimentStatus.LITERATURE_REVIEWED
        assert state.literature_context is not None

        # 4. Hypothesis agent output
        hypothesis = Hypothesis(
            raw_text=state.raw_hypothesis,
            formalized="Surface roughness inversely correlates with PSNR",
            variables=["roughness", "PSNR"],
            parameter_space=[
                ParameterSpec(name="roughness", values=[0.1, 0.5, 0.9]),
            ],
            predictions=["PSNR decreases monotonically with roughness"],
        )
        state = add_hypothesis(state, hypothesis)
        assert state.status == ExperimentStatus.HYPOTHESIS_READY

        # 5. Scene agent output
        plan = ExperimentPlan(
            hypothesis_id=hypothesis.id,
            simulation_approach="Use numpy for synthetic data generation",
            scene_descriptions=["low", "mid", "high"],
            metrics=["PSNR", "SSIM"],
        )
        state = add_plan(state, plan)

        scenes = [
            SceneSpec(
                plan_id=plan.id,
                code=f"import numpy as np\nrender(roughness={r})",
                parameters={"roughness": r, "spp": 256},
            )
            for r in [0.1, 0.5, 0.9]
        ]
        state = add_scenes(state, scenes)
        assert state.status == ExperimentStatus.SCENES_READY
        assert len(state.scenes) == 3

        # 6. Executor agent output
        for scene in state.scenes:
            result = ExecutionResult(
                scene_id=scene.id,
                status="success",
                output_paths=[f"/output/{scene.id}.exr"],
                duration_seconds=5.0,
            )
            state = add_execution_result(state, result)
        assert state.status == ExperimentStatus.EXECUTED
        assert len(state.execution_results) == 3

        # 7. Evaluator agent output
        psnr_values = [32.1, 26.4, 19.8]  # Decreasing with roughness
        for scene, psnr in zip(state.scenes, psnr_values):
            evaluation = EvaluationResult(
                scene_id=scene.id,
                metrics={"PSNR": psnr, "SSIM": psnr / 40.0},
                summary=f"PSNR={psnr:.1f} for roughness={scene.parameters['roughness']}",
            )
            state = add_evaluation(state, evaluation)
        assert state.status == ExperimentStatus.EVALUATED
        assert len(state.evaluations) == 3

        # 8. Analyst agent output — conclude
        report = AnalysisReport(
            hypothesis_id=hypothesis.id,
            findings=[
                "PSNR monotonically decreases: 32.1 → 26.4 → 19.8",
                "Strong inverse correlation (r=-0.99)",
            ],
            confidence=0.95,
            supports_hypothesis=True,
            should_stop=True,
            reasoning="Clear monotonic decrease in PSNR with increasing roughness",
        )
        state = add_analysis(state, report)
        assert state.status == ExperimentStatus.COMPLETED
        assert state.iteration == 1

        # 9. Literature validator output
        lit_validation = LiteratureValidation(
            hypothesis_id=hypothesis.id,
            consistency_assessment="Results align with Smith (2021) findings.",
            novel_findings=("Non-linear PSNR drop observed at high roughness",),
            concerns=("Only 3 roughness levels tested vs 5+ in literature",),
            suggested_citations=("Smith et al. (2021) - roughness effects",),
            overall_confidence_adjustment=0.05,
            reasoning="Strong agreement with prior work boosts confidence slightly.",
        )
        state = set_literature_validation(state, lit_validation)
        assert state.literature_validation is not None
        assert state.literature_validation.overall_confidence_adjustment == 0.05

        # 10. Verify serialization roundtrip
        json_str = serialize_state(state)
        restored = deserialize_state(json_str)
        assert restored.status == ExperimentStatus.COMPLETED
        assert restored.iteration == 1
        assert len(restored.scenes) == 3
        assert len(restored.analyses) == 1
        assert restored.analyses[0].confidence == 0.95
        assert restored.literature_context is not None
        assert len(restored.literature_context.entries) == 1
        assert restored.literature_validation is not None

    def test_multi_iteration_experiment(self, sample_environment):
        """Test experiment that continues for multiple iterations."""
        state = start_experiment("Test multi-iteration")
        state = set_environment(state, sample_environment)

        # Iteration 1: inconclusive
        hypothesis = Hypothesis(raw_text="Test multi-iteration", formalized="Test")
        state = add_hypothesis(state, hypothesis)

        plan = ExperimentPlan(
            hypothesis_id=hypothesis.id,
            simulation_approach="Synthetic test",
            metrics=["metric1"],
        )
        state = add_plan(state, plan)

        scene = SceneSpec(plan_id=plan.id, code="test()")
        state = add_scenes(state, [scene])

        result = ExecutionResult(scene_id=scene.id, status="success")
        state = add_execution_result(state, result)

        evaluation = EvaluationResult(scene_id=scene.id, metrics={"metric1": 0.5})
        state = add_evaluation(state, evaluation)

        report = AnalysisReport(
            hypothesis_id=hypothesis.id,
            findings=["Inconclusive"],
            confidence=0.4,
            should_stop=False,
            next_experiments=["Try with more samples"],
        )
        state = add_analysis(state, report)
        assert state.status == ExperimentStatus.ANALYZED
        assert state.iteration == 1

        # Iteration 2: conclusive
        report2 = AnalysisReport(
            hypothesis_id=hypothesis.id,
            findings=["Strong evidence"],
            confidence=0.92,
            supports_hypothesis=True,
            should_stop=True,
        )
        state = add_analysis(state, report2)
        assert state.status == ExperimentStatus.COMPLETED
        assert state.iteration == 2
        assert len(state.analyses) == 2

    def test_experiment_with_execution_failure(self, sample_environment):
        """Test handling of execution failures."""
        state = start_experiment("Test failure handling")
        state = set_environment(state, sample_environment)

        hypothesis = Hypothesis(raw_text="Test failure", formalized="Test")
        state = add_hypothesis(state, hypothesis)

        plan = ExperimentPlan(
            hypothesis_id=hypothesis.id,
            simulation_approach="Test",
            metrics=["PSNR"],
        )
        state = add_plan(state, plan)

        scenes = [
            SceneSpec(plan_id=plan.id, code=f"test({i})")
            for i in range(3)
        ]
        state = add_scenes(state, scenes)

        # Some succeed, one fails
        state = add_execution_result(
            state,
            ExecutionResult(scene_id=scenes[0].id, status="success"),
        )
        state = add_execution_result(
            state,
            ExecutionResult(
                scene_id=scenes[1].id,
                status="error",
                error_message="Renderer crashed",
            ),
        )
        state = add_execution_result(
            state,
            ExecutionResult(scene_id=scenes[2].id, status="success"),
        )

        # Verify mixed results are preserved
        assert len(state.execution_results) == 3
        statuses = [r.status for r in state.execution_results]
        assert statuses == ["success", "error", "success"]
