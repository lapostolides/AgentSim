"""Tests for pure state transition functions."""

from agentsim.state.models import (
    AnalysisReport,
    AvailablePackage,
    EnvironmentInfo,
    EvaluationResult,
    ExecutionResult,
    ExperimentPlan,
    ExperimentStatus,
    Hypothesis,
    ParameterSpec,
    QualityRatings,
    SceneSpec,
)
from agentsim.state.transitions import (
    add_analysis,
    add_error,
    add_evaluation,
    add_execution_result,
    add_hypothesis,
    add_plan,
    add_scene,
    add_scenes,
    mark_failed,
    set_environment,
    start_experiment,
)


class TestStartExperiment:
    def test_basic(self):
        state = start_experiment("Does roughness matter?")
        assert state.raw_hypothesis == "Does roughness matter?"
        assert state.status == ExperimentStatus.INITIALIZED
        assert state.files == ()

    def test_with_files(self):
        state = start_experiment(
            "Test hypothesis",
            file_paths=["/data/scene.stl", "/data/config.yaml"],
            file_descriptions={"/data/scene.stl": "Wall mesh"},
        )
        assert len(state.files) == 2
        assert state.files[0].file_type == "stl"
        assert state.files[0].description == "Wall mesh"
        assert state.files[1].file_type == "yaml"

    def test_file_type_detection(self):
        state = start_experiment(
            "test",
            file_paths=["/a.stl", "/b.json", "/c.png", "/d.py", "/e.xyz"],
        )
        types = [f.file_type for f in state.files]
        assert types == ["stl", "json", "image", "script", "unknown"]


class TestTransitionsAreImmutable:
    """Verify that every transition returns a new state without mutating the original."""

    def test_add_hypothesis_immutable(self):
        original = start_experiment("test")
        hypothesis = Hypothesis(raw_text="test", formalized="Formalized test")
        new_state = add_hypothesis(original, hypothesis)

        assert original.hypothesis is None  # original unchanged
        assert new_state.hypothesis is not None
        assert new_state.hypothesis.formalized == "Formalized test"
        assert original.id == new_state.id  # same experiment

    def test_add_plan_immutable(self):
        state = start_experiment("test")
        state = add_hypothesis(state, Hypothesis(raw_text="test"))
        original = state

        plan = ExperimentPlan(
            hypothesis_id=state.hypothesis.id,
            simulation_approach="Use mock renderer",
            metrics=["PSNR"],
        )
        new_state = add_plan(state, plan)

        assert original.plan is None
        assert new_state.plan is not None
        assert new_state.status == ExperimentStatus.PLAN_READY

    def test_add_scene_immutable(self):
        state = start_experiment("test")
        scene = SceneSpec(plan_id="p1", code="print('hello')")
        new_state = add_scene(state, scene)

        assert state.scenes == ()
        assert len(new_state.scenes) == 1

    def test_add_execution_result_immutable(self):
        state = start_experiment("test")
        result = ExecutionResult(scene_id="s1", status="success")
        new_state = add_execution_result(state, result)

        assert state.execution_results == ()
        assert len(new_state.execution_results) == 1


class TestTransitionChain:
    """Test a full chain of transitions simulating an experiment lifecycle."""

    def test_full_lifecycle(self):
        # 1. Start
        state = start_experiment("Does roughness affect accuracy?")
        assert state.status == ExperimentStatus.INITIALIZED

        # 2. Set environment
        env = EnvironmentInfo(
            packages=(AvailablePackage(name="numpy", version="1.26", import_name="numpy"),),
            python_version="3.12.1",
        )
        state = set_environment(state, env)
        assert state.environment is not None
        assert len(state.environment.packages) == 1

        # 3. Hypothesis (with quality ratings)
        hypothesis = Hypothesis(
            raw_text="Does roughness affect accuracy?",
            formalized="Surface roughness inversely correlates with reconstruction accuracy",
            variables=["roughness", "accuracy"],
            parameter_space=[ParameterSpec(name="roughness", values=[0.1, 0.5, 0.9])],
            quality_ratings=QualityRatings(
                decision_relevance=0.8,
                non_triviality=0.7,
                informative_either_way=0.6,
                downstream_actionability=0.9,
                expected_impact=0.5,
                falsifiability=0.85,
                composite_score=0.725,
                reasoning="Strong hypothesis with clear engineering implications.",
            ),
        )
        state = add_hypothesis(state, hypothesis)
        assert state.status == ExperimentStatus.HYPOTHESIS_READY
        assert state.hypothesis.quality_ratings is not None
        assert state.hypothesis.quality_ratings.composite_score == 0.725

        # 4. Plan
        plan = ExperimentPlan(
            hypothesis_id=hypothesis.id,
            simulation_approach="Use numpy for synthetic data generation",
            scene_descriptions=["low roughness", "medium roughness", "high roughness"],
            metrics=["PSNR", "SSIM"],
        )
        state = add_plan(state, plan)
        assert state.status == ExperimentStatus.PLAN_READY

        # 5. Scenes
        scenes = [
            SceneSpec(plan_id=plan.id, code=f"render(roughness={r})")
            for r in [0.1, 0.5, 0.9]
        ]
        state = add_scenes(state, scenes)
        assert state.status == ExperimentStatus.SCENES_READY
        assert len(state.scenes) == 3

        # 6. Execution
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

        # 7. Evaluation
        for scene in state.scenes:
            evaluation = EvaluationResult(
                scene_id=scene.id,
                metrics={"PSNR": 28.5, "SSIM": 0.92},
            )
            state = add_evaluation(state, evaluation)
        assert state.status == ExperimentStatus.EVALUATED

        # 8. Analysis — continue
        report = AnalysisReport(
            hypothesis_id=hypothesis.id,
            findings=["Weak correlation observed"],
            confidence=0.6,
            supports_hypothesis=True,
            should_stop=False,
            next_experiments=["Test with more roughness values"],
        )
        state = add_analysis(state, report)
        assert state.status == ExperimentStatus.ANALYZED
        assert state.iteration == 1

        # 9. Analysis — stop
        final_report = AnalysisReport(
            hypothesis_id=hypothesis.id,
            findings=["Strong correlation confirmed"],
            confidence=0.95,
            supports_hypothesis=True,
            should_stop=True,
        )
        state = add_analysis(state, final_report)
        assert state.status == ExperimentStatus.COMPLETED
        assert state.iteration == 2
        assert len(state.analyses) == 2


class TestErrorHandling:
    def test_add_error(self):
        state = start_experiment("test")
        state = add_error(state, "Something went wrong")
        assert len(state.errors) == 1
        assert state.status == ExperimentStatus.INITIALIZED  # unchanged

    def test_mark_failed(self):
        state = start_experiment("test")
        state = mark_failed(state, "Fatal error")
        assert state.status == ExperimentStatus.FAILED
        assert "Fatal error" in state.errors

    def test_multiple_errors(self):
        state = start_experiment("test")
        state = add_error(state, "Error 1")
        state = add_error(state, "Error 2")
        assert len(state.errors) == 2
