"""Tests for frozen Pydantic state models."""

import pytest
from pydantic import ValidationError

from agentsim.state.models import (
    AnalysisReport,
    AvailablePackage,
    EnvironmentInfo,
    EvaluationResult,
    ExecutionResult,
    ExperimentPlan,
    ExperimentState,
    ExperimentStatus,
    FileReference,
    Hypothesis,
    ParameterSpec,
    QualityRatings,
    SceneSpec,
)


class TestFileReference:
    def test_create(self):
        ref = FileReference(path="/data/scene.stl", file_type="stl", description="test mesh")
        assert ref.path == "/data/scene.stl"
        assert ref.file_type == "stl"
        assert ref.description == "test mesh"
        assert ref.metadata == {}

    def test_frozen(self):
        ref = FileReference(path="/data/scene.stl", file_type="stl")
        with pytest.raises(ValidationError):
            ref.path = "/other/path"  # type: ignore[misc]

    def test_with_metadata(self):
        ref = FileReference(
            path="/data/scene.stl",
            file_type="stl",
            metadata={"vertices": 1000, "format": "binary"},
        )
        assert ref.metadata["vertices"] == 1000


class TestParameterSpec:
    def test_discrete_values(self):
        param = ParameterSpec(name="roughness", values=[0.1, 0.5, 0.9])
        assert param.name == "roughness"
        assert len(param.values) == 3

    def test_range(self):
        param = ParameterSpec(name="angle", range_min=0.0, range_max=90.0, step=5.0)
        assert param.range_min == 0.0
        assert param.range_max == 90.0
        assert param.step == 5.0


class TestHypothesis:
    def test_create_minimal(self):
        h = Hypothesis(raw_text="Does roughness affect reconstruction?")
        assert h.raw_text == "Does roughness affect reconstruction?"
        assert h.id  # auto-generated
        assert h.variables == []
        assert h.parameter_space == []

    def test_create_full(self):
        h = Hypothesis(
            raw_text="Does roughness affect reconstruction?",
            formalized="Increasing surface roughness reduces NLOS accuracy",
            variables=["roughness", "accuracy"],
            parameter_space=[ParameterSpec(name="roughness", values=[0.1, 0.5, 0.9])],
            predictions=["accuracy decreases with roughness"],
            assumptions=["Lambertian BRDF model"],
        )
        assert len(h.parameter_space) == 1
        assert h.parameter_space[0].name == "roughness"

    def test_frozen(self):
        h = Hypothesis(raw_text="test")
        with pytest.raises(ValidationError):
            h.raw_text = "changed"  # type: ignore[misc]


class TestQualityRatings:
    def test_create_defaults(self):
        qr = QualityRatings()
        assert qr.decision_relevance == 0.0
        assert qr.composite_score == 0.0
        assert qr.reasoning == ""

    def test_create_full(self):
        qr = QualityRatings(
            decision_relevance=0.8,
            non_triviality=0.7,
            informative_either_way=0.6,
            downstream_actionability=0.9,
            expected_impact=0.5,
            falsifiability=0.85,
            composite_score=0.725,
            reasoning="Strong hypothesis with clear engineering implications.",
        )
        assert qr.composite_score == 0.725
        assert qr.downstream_actionability == 0.9

    def test_frozen(self):
        qr = QualityRatings()
        with pytest.raises(ValidationError):
            qr.decision_relevance = 0.5  # type: ignore[misc]


class TestHypothesisWithQualityRatings:
    def test_hypothesis_without_ratings(self):
        h = Hypothesis(raw_text="test")
        assert h.quality_ratings is None

    def test_hypothesis_with_ratings(self):
        ratings = QualityRatings(
            decision_relevance=0.9,
            non_triviality=0.8,
            composite_score=0.85,
        )
        h = Hypothesis(raw_text="test", quality_ratings=ratings)
        assert h.quality_ratings is not None
        assert h.quality_ratings.decision_relevance == 0.9

    def test_serialization_roundtrip(self):
        ratings = QualityRatings(
            decision_relevance=0.9,
            falsifiability=0.7,
            composite_score=0.8,
            reasoning="Well-scoped question.",
        )
        h = Hypothesis(raw_text="test", quality_ratings=ratings)
        json_str = h.model_dump_json()
        restored = Hypothesis.model_validate_json(json_str)
        assert restored.quality_ratings is not None
        assert restored.quality_ratings.decision_relevance == 0.9
        assert restored.quality_ratings.reasoning == "Well-scoped question."


class TestExperimentPlan:
    def test_create(self):
        plan = ExperimentPlan(
            hypothesis_id="abc123",
            simulation_approach="Use mitsuba for rendering",
            scene_descriptions=["diffuse wall scene", "specular wall scene"],
            metrics=["PSNR", "SSIM"],
        )
        assert plan.simulation_approach == "Use mitsuba for rendering"
        assert len(plan.scene_descriptions) == 2


class TestSceneSpec:
    def test_create(self):
        scene = SceneSpec(
            plan_id="plan123",
            code="import mitsuba as mi\nmi.render(scene)",
            parameters={"spp": 256},
        )
        assert "mitsuba" in scene.code
        assert scene.parameters["spp"] == 256


class TestExecutionResult:
    def test_success(self):
        result = ExecutionResult(
            scene_id="scene1",
            status="success",
            output_paths=["/output/render.exr"],
            duration_seconds=12.5,
        )
        assert result.status == "success"
        assert result.error_message == ""

    def test_error(self):
        result = ExecutionResult(
            scene_id="scene1",
            status="error",
            error_message="Mitsuba render failed: invalid scene",
        )
        assert result.status == "error"
        assert "invalid scene" in result.error_message


class TestEvaluationResult:
    def test_create(self):
        evaluation = EvaluationResult(
            scene_id="scene1",
            metrics={"PSNR": 28.5, "SSIM": 0.92},
            summary="Good reconstruction quality",
        )
        assert evaluation.metrics["PSNR"] == 28.5


class TestAnalysisReport:
    def test_continue(self):
        report = AnalysisReport(
            hypothesis_id="h1",
            findings=["Roughness correlation found"],
            confidence=0.7,
            supports_hypothesis=True,
            should_stop=False,
            next_experiments=["Test with higher roughness values"],
        )
        assert not report.should_stop
        assert len(report.next_experiments) == 1

    def test_stop(self):
        report = AnalysisReport(
            hypothesis_id="h1",
            findings=["Strong evidence"],
            confidence=0.95,
            supports_hypothesis=True,
            should_stop=True,
        )
        assert report.should_stop


class TestEnvironmentInfo:
    def test_create(self):
        env = EnvironmentInfo(
            packages=(
                AvailablePackage(name="mitsuba", version="3.5.0", import_name="mitsuba"),
                AvailablePackage(name="numpy", version="1.26.0", import_name="numpy"),
            ),
            python_version="3.12.1",
        )
        assert len(env.packages) == 2
        assert env.packages[0].name == "mitsuba"
        assert env.python_version == "3.12.1"

    def test_empty(self):
        env = EnvironmentInfo()
        assert env.packages == ()


class TestExperimentState:
    def test_initial_state(self):
        state = ExperimentState(raw_hypothesis="test hypothesis")
        assert state.status == ExperimentStatus.INITIALIZED
        assert state.iteration == 0
        assert state.hypothesis is None
        assert state.scenes == ()
        assert state.errors == ()

    def test_frozen(self):
        state = ExperimentState(raw_hypothesis="test")
        with pytest.raises(ValidationError):
            state.status = ExperimentStatus.COMPLETED  # type: ignore[misc]

    def test_with_files(self):
        files = (
            FileReference(path="/data/scene.stl", file_type="stl"),
            FileReference(path="/data/config.yaml", file_type="yaml"),
        )
        state = ExperimentState(raw_hypothesis="test", files=files)
        assert len(state.files) == 2

    def test_unique_ids(self):
        s1 = ExperimentState(raw_hypothesis="test1")
        s2 = ExperimentState(raw_hypothesis="test2")
        assert s1.id != s2.id

    def test_serialization_roundtrip(self):
        state = ExperimentState(
            raw_hypothesis="test",
            files=(FileReference(path="/data/scene.stl", file_type="stl"),),
        )
        json_str = state.model_dump_json()
        restored = ExperimentState.model_validate_json(json_str)
        assert restored.raw_hypothesis == state.raw_hypothesis
        assert len(restored.files) == 1
        assert restored.files[0].path == "/data/scene.stl"
