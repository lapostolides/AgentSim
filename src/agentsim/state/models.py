"""Frozen Pydantic models defining all experiment state.

Every model is immutable (frozen=True). Agents receive serialized state
and return new instances — no mutation anywhere in the pipeline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agentsim.physics.models import PhysicsConsultationSummary, PhysicsValidation
from agentsim.physics.reasoning.models import ExplorerResult, OptimizerResult


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ExperimentStatus(str, Enum):
    INITIALIZED = "initialized"
    LITERATURE_REVIEWED = "literature_reviewed"
    HYPOTHESIS_READY = "hypothesis_ready"
    PLAN_READY = "plan_ready"
    SCENES_READY = "scenes_ready"
    PHYSICS_VALIDATED = "physics_validated"
    EXECUTED = "executed"
    EVALUATED = "evaluated"
    ANALYZED = "analyzed"
    COMPLETED = "completed"
    FAILED = "failed"


class FileReference(BaseModel, frozen=True):
    """Reference to a user-provided file."""

    path: str
    file_type: str  # e.g. "stl", "yaml", "json", "csv", "image"
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParameterSpec(BaseModel, frozen=True):
    """A single parameter in the experiment's parameter space."""

    name: str
    description: str = ""
    values: list[Any] = Field(default_factory=list)
    range_min: float | None = None
    range_max: float | None = None
    step: float | None = None


class QualityRatings(BaseModel, frozen=True):
    """Self-assessed quality scores for a hypothesis.

    Each dimension is scored 0.0 to 1.0 by the hypothesis agent
    during generation, guiding it toward high-value hypotheses.
    """

    decision_relevance: float = 0.0
    non_triviality: float = 0.0
    informative_either_way: float = 0.0
    downstream_actionability: float = 0.0
    expected_impact: float = 0.0
    falsifiability: float = 0.0
    composite_score: float = 0.0
    reasoning: str = ""


class Hypothesis(BaseModel, frozen=True):
    """Structured hypothesis parsed from natural language."""

    id: str = Field(default_factory=_new_id)
    raw_text: str
    formalized: str = ""
    variables: list[str] = Field(default_factory=list)
    parameter_space: list[ParameterSpec] = Field(default_factory=list)
    predictions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    quality_ratings: QualityRatings | None = None


class AvailablePackage(BaseModel, frozen=True):
    """A Python package available in the environment for simulation."""

    name: str  # e.g. "mitsuba", "bpy", "carla"
    version: str = ""
    import_name: str = ""  # The actual import name if different from package name


class EnvironmentInfo(BaseModel, frozen=True):
    """Describes what simulation tools are available in the Python environment."""

    packages: tuple[AvailablePackage, ...] = ()
    python_version: str = ""
    notes: str = ""


class ExperimentPlan(BaseModel, frozen=True):
    """Plan for executing an experiment."""

    id: str = Field(default_factory=_new_id)
    hypothesis_id: str
    simulation_approach: str = ""  # e.g. "Use mitsuba for rendering, numpy for analysis"
    scene_descriptions: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    ground_truth_source: str = ""
    notes: str = ""


class SceneSpec(BaseModel, frozen=True):
    """Generated simulation scene — contains code, not templates."""

    id: str = Field(default_factory=_new_id)
    plan_id: str
    code: str  # Generated Python code
    language: str = "python"
    parameters: dict[str, Any] = Field(default_factory=dict)
    file_refs: list[str] = Field(default_factory=list)


class ScenePreview(BaseModel, frozen=True):
    """Preview render of a scene before execution."""

    scene_id: str
    preview_path: str = ""
    is_valid: bool = True
    warnings: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel, frozen=True):
    """Result of running a simulation scene."""

    scene_id: str
    status: str  # "success", "error", "timeout"
    output_paths: list[str] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    error_message: str = ""


class EvaluationResult(BaseModel, frozen=True):
    """Result of evaluating simulation outputs."""

    scene_id: str
    metrics: dict[str, float] = Field(default_factory=dict)
    ground_truth_comparison: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    artifacts: list[str] = Field(default_factory=list)


class LiteratureEntry(BaseModel, frozen=True):
    """A single paper or reference from the literature review."""

    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    key_findings: tuple[str, ...] = ()
    relevance: str = ""
    url: str = ""
    doi: str = ""
    verification_status: str = "unverified"  # "verified", "unverified", "fabricated"
    verification_note: str = ""


class OpenQuestion(BaseModel, frozen=True):
    """An open research question with its practical significance."""

    question: str
    significance: str = ""


class LiteratureContext(BaseModel, frozen=True):
    """Literature context produced by the Literature Scout agent.

    Injected into all subsequent agent prompts so they can ground
    their work in established research.
    """

    entries: tuple[LiteratureEntry, ...] = ()
    summary: str = ""
    open_questions: tuple[OpenQuestion, ...] = ()
    trivial_gaps: tuple[str, ...] = ()
    methodology_notes: str = ""


class LiteratureValidation(BaseModel, frozen=True):
    """Validation of experiment results against literature.

    Produced by the Literature Validator agent after the analyst phase.
    """

    hypothesis_id: str
    consistency_assessment: str = ""
    novel_findings: tuple[str, ...] = ()
    concerns: tuple[str, ...] = ()
    suggested_citations: tuple[str, ...] = ()
    overall_confidence_adjustment: float = 0.0
    reasoning: str = ""


class AnalysisReport(BaseModel, frozen=True):
    """High-level analysis and recommendations from the Analyst agent."""

    hypothesis_id: str
    findings: list[str] = Field(default_factory=list)
    confidence: float = 0.0  # 0.0 to 1.0
    supports_hypothesis: bool | None = None
    next_experiments: list[str] = Field(default_factory=list)
    should_stop: bool = False
    reasoning: str = ""


class PhysicsRecommendation(BaseModel, frozen=True):
    """Physics-space reasoning output -- optimizer and/or explorer results.

    Stored in ExperimentState after pre-scene optimization. Both fields
    are optional since optimizer and explorer can run independently.
    """

    optimizer_result: OptimizerResult | None = None
    explorer_result: ExplorerResult | None = None


class ExperimentState(BaseModel, frozen=True):
    """Top-level envelope containing all experiment state.

    This is the single object serialized between agent phases.
    Each transition function returns a new ExperimentState — never mutated.
    """

    id: str = Field(default_factory=_new_id)
    created_at: datetime = Field(default_factory=_now)
    status: ExperimentStatus = ExperimentStatus.INITIALIZED
    iteration: int = 0

    # User input
    raw_hypothesis: str = ""
    files: tuple[FileReference, ...] = ()

    # Agent outputs (accumulated across iterations)
    hypothesis: Hypothesis | None = None
    plan: ExperimentPlan | None = None
    scenes: tuple[SceneSpec, ...] = ()
    scene_previews: tuple[ScenePreview, ...] = ()
    execution_results: tuple[ExecutionResult, ...] = ()
    evaluations: tuple[EvaluationResult, ...] = ()
    analyses: tuple[AnalysisReport, ...] = ()

    # Environment discovery
    environment: EnvironmentInfo | None = None

    # Literature grounding
    literature_context: LiteratureContext | None = None
    literature_validation: LiteratureValidation | None = None

    # Physics validation
    physics_validations: tuple[PhysicsValidation, ...] = ()
    consultation_summary: PhysicsConsultationSummary | None = None

    # Physics-space reasoning
    physics_recommendation: PhysicsRecommendation | None = None

    # Error tracking
    errors: tuple[str, ...] = ()
